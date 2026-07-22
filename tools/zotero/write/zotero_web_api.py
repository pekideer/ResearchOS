"""Shared narrow helpers for guarded Zotero Web API workflows."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


WebApiRequest = Callable[[dict[str, str], str, str, Any | None, dict[str, str] | None], tuple[int, dict[str, str], Any]]
RESEARCHOS_ROOT = Path(__file__).resolve().parents[3]


def normalize_proxy(value: str) -> str:
    """Normalize per-machine proxy values without exposing credentials."""
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if "://" not in normalized:
        normalized = "http://" + normalized
    return normalized


def env_config() -> dict[str, str]:
    """Load required Zotero Web API configuration without logging secrets."""
    api_key = os.environ.get("ZOTERO_API_KEY", "")
    user_id = os.environ.get("ZOTERO_USER_ID", "")
    api_base = os.environ.get("ZOTERO_API_BASE", "https://api.zotero.org").rstrip("/")
    missing = [name for name, value in (("ZOTERO_API_KEY", api_key), ("ZOTERO_USER_ID", user_id)) if not value]
    if missing:
        raise SystemExit(f"Missing required environment variable(s): {', '.join(missing)}")
    return {"api_key": api_key, "user_id": user_id, "api_base": api_base}


def _machine_config_proxy() -> tuple[str, str]:
    path = RESEARCHOS_ROOT / ".local" / "machine_config.json"
    if not path.exists():
        return "", ""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "", ""
    proxy = data.get("proxy", {}) if isinstance(data, dict) else {}
    if not isinstance(proxy, dict):
        return "", ""
    for field in ("https_proxy", "http_proxy", "all_proxy"):
        value = str(proxy.get(field) or "").strip()
        if value:
            return f"machine_config.{field}", value
    return "", ""


def selected_proxy(require_proxy: bool = True) -> tuple[urllib.request.OpenerDirector, dict[str, str]]:
    """Build a Web API proxy opener and return only redacted audit metadata."""
    proxy_value = ""
    source = ""
    for name in ("ZOTERO_HTTPS_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        value = os.environ.get(name) or os.environ.get(name.lower())
        if value:
            proxy_value = value
            source = name
            break
    if not proxy_value:
        source, proxy_value = _machine_config_proxy()
    if not proxy_value and os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
                enabled = int(winreg.QueryValueEx(key, "ProxyEnable")[0])
                server = str(winreg.QueryValueEx(key, "ProxyServer")[0])
            if enabled and server:
                entries: dict[str, str] = {}
                for part in server.split(";"):
                    if "=" in part:
                        scheme, value = part.split("=", 1)
                        entries[scheme.strip().lower()] = value.strip()
                proxy_value = entries.get("https") or entries.get("http") or server.split(";", 1)[0].strip()
                if proxy_value and "://" not in proxy_value:
                    proxy_value = "http://" + proxy_value
                source = "WindowsSystemProxy"
        except OSError:
            proxy_value = ""
            source = ""
    proxy_value = normalize_proxy(proxy_value)
    if not proxy_value:
        if require_proxy:
            raise SystemExit(
                "Zotero Web API requires a per-machine proxy. Set ZOTERO_HTTPS_PROXY/HTTPS_PROXY/HTTP_PROXY/ALL_PROXY "
                "or configure .local/machine_config.json; do not hardcode a shared host/port."
            )
        return urllib.request.build_opener(), {"enabled": "no", "source": "", "host_port": ""}
    parsed = urllib.parse.urlparse(proxy_value)
    host_port = parsed.netloc.rsplit("@", 1)[-1] if parsed.netloc else parsed.path
    handler = urllib.request.ProxyHandler({"https": proxy_value, "http": proxy_value})
    return urllib.request.build_opener(handler), {"enabled": "yes", "source": source, "host_port": host_port}


def zotero_request(
    config: dict[str, str],
    method: str,
    path: str,
    body: Any | None = None,
    headers: dict[str, str] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
    error_cls: type[Exception] = RuntimeError,
) -> tuple[int, dict[str, str], Any]:
    """Send one Zotero Web API request through a caller-selected opener."""
    url = f"{config['api_base']}/users/{config['user_id']}/{path.lstrip('/')}"
    req_headers = {"Zotero-API-Key": config["api_key"], "Zotero-API-Version": "3"}
    if headers:
        req_headers.update(headers)
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with (opener or urllib.request.build_opener()).open(request, timeout=60) as response:
            raw = response.read()
            text = raw.decode("utf-8") if raw else ""
            parsed = json.loads(text) if text else None
            return response.status, dict(response.headers.items()), parsed
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise error_cls(exc.code, message) from exc


def fetch_web_api_paged(
    config: dict[str, str],
    endpoint: str,
    request_fn: WebApiRequest,
    error_cls: type[Exception] = RuntimeError,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch paginated Zotero Web API rows through a caller-owned request function."""
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        separator = "&" if "?" in endpoint else "?"
        status, headers, payload = request_fn(config, "GET", f"{endpoint}{separator}limit={limit}&start={start}", None, None)
        if status != 200:
            raise error_cls(status, f"Unexpected status for {endpoint}")
        batch = payload or []
        rows.extend(batch)
        total = int(headers.get("Total-Results", len(rows)))
        start += len(batch)
        if not batch or start >= total:
            break
    return rows
