"""Shared read-only Zotero Local API helpers for ResearchOS tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


DEFAULT_API_BASE = "http://localhost:23119/api"
DEFAULT_USER_ID = "0"
DEFAULT_TIMEOUT_SECONDS = 20


def load_env_file(env_path: Path = Path(".env")) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> tuple[str, str]:
    load_env_file()
    api_base = os.getenv("ZOTERO_API_BASE", DEFAULT_API_BASE).rstrip("/")
    user_id = os.getenv("ZOTERO_USER_ID", DEFAULT_USER_ID)
    return api_base, user_id


def zotero_request(url: str, params: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    full_url = url + ("?" + urlencode(params) if params else "")
    request = Request(full_url, headers={"Zotero-API-Version": "3"})
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, params: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    return json.loads(zotero_request(url, params, timeout))


def fetch_children(api_base: str, user_id: str, item_key: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    url = f"{api_base}/users/{user_id}/items/{item_key}/children"
    return fetch_json(url, {"format": "json", "include": "data"}, timeout)


def fetch_paged(
    api_base: str,
    user_id: str,
    endpoint: str,
    include: str = "data",
    max_records: int | None = None,
    page_limit: int = 100,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    start = 0
    while True:
        remaining = None if max_records is None else max_records - len(records)
        if remaining is not None and remaining <= 0:
            break
        limit = page_limit if remaining is None else min(page_limit, remaining)
        url = f"{api_base}/users/{user_id}/{endpoint.lstrip('/')}"
        batch = fetch_json(url, {"format": "json", "include": include, "limit": limit, "start": start}, timeout)
        if not batch:
            break
        records.extend(batch)
        if len(batch) < limit:
            break
        start += limit
    return records


def creators_to_text(creators: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for creator in creators:
        if creator.get("name"):
            names.append(str(creator["name"]))
            continue
        full_name = " ".join(
            part
            for part in [creator.get("firstName"), creator.get("lastName")]
            if part
        ).strip()
        if full_name:
            names.append(full_name)
    return "; ".join(names)


def year_from_date(date_value: str | None) -> str:
    if not date_value:
        return ""
    for token in str(date_value).replace("/", "-").replace(".", "-").split("-"):
        if len(token) == 4 and token.isdigit():
            return token
    return str(date_value)[:4] if str(date_value)[:4].isdigit() else ""


def file_url_to_path(value: str) -> Path:
    value = value.strip().strip('"')
    parsed = urlparse(value)
    if parsed.scheme.lower() != "file":
        return Path(value)

    if parsed.netloc and parsed.netloc not in {"localhost", ""}:
        raw = f"//{parsed.netloc}{parsed.path}"
    else:
        raw = parsed.path

    raw = unquote(raw)
    if raw.startswith("/") and len(raw) >= 4 and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def response_to_file_url(headers: Any, body: str) -> str | None:
    location = headers.get("Location")
    if location:
        return location

    text = body.strip()
    if not text:
        return None

    try:
        payload = json.loads(text)
    except ValueError:
        return text

    if isinstance(payload, dict):
        for key in ["url", "file", "path"]:
            if payload.get(key):
                return str(payload[key])
    return text


def resolve_pdf_file_url(
    api_base: str,
    user_id: str,
    attachment_key: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[str | None, Path | None]:
    url = f"{api_base}/users/{user_id}/items/{attachment_key}/file/view/url"
    request = Request(url, headers={"Zotero-API-Version": "3"})
    opener = build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:
            headers = response.headers
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        if getattr(exc, "code", 0) and 300 <= exc.code < 400:
            headers = exc.headers
            body = exc.read().decode("utf-8", errors="replace")
        else:
            raise
    file_url = response_to_file_url(headers, body)
    if not file_url:
        return None, None
    return file_url, file_url_to_path(file_url)
