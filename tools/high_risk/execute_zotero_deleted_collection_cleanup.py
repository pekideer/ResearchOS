"""Remove deleted collection references from Zotero items via Web API.

The script patches only the ``collections`` field of selected items. It keeps
all active collection keys listed in the approved plan and preserves the item's
current tags exactly as returned by Zotero Web API.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    M002_LIBRARY_GOVERNANCE as MACHINE_DIR,
    ensure_output_dirs,
    find_researchos_root,
    write_json,
)


DEFAULT_PLAN = MACHINE_DIR / "zotero-deleted-collection-reference-cleanup-plan-dry-run.json"
RUNS_DIR = MACHINE_DIR / "zotero-deleted-collection-cleanup-runs"
AUDIT_FIELDS = [
    "timestamp",
    "mode",
    "item_key",
    "write_performed",
    "removed_deleted_collection_keys",
    "kept_collection_keys",
    "before_version",
    "after_version",
    "http_status",
    "blocking_conditions",
]


class ZoteroApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def env_config() -> dict[str, str]:
    api_key = os.environ.get("ZOTERO_API_KEY", "")
    user_id = os.environ.get("ZOTERO_USER_ID", "")
    api_base = os.environ.get("ZOTERO_API_BASE", "https://api.zotero.org").rstrip("/")
    missing = [name for name, value in [("ZOTERO_API_KEY", api_key), ("ZOTERO_USER_ID", user_id)] if not value]
    if missing:
        raise SystemExit(f"Missing required environment variable(s): {', '.join(missing)}")
    return {"api_key": api_key, "user_id": user_id, "api_base": api_base}


def selected_proxy() -> tuple[urllib.request.OpenerDirector, dict[str, str]]:
    proxy_value = ""
    source = ""
    for name in ["ZOTERO_HTTPS_PROXY", "HTTPS_PROXY", "HTTP_PROXY"]:
        value = os.environ.get(name) or os.environ.get(name.lower())
        if value:
            proxy_value = value
            source = name
            break
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
    if not proxy_value:
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
) -> tuple[int, dict[str, str], Any]:
    url = f"{config['api_base']}/users/{config['user_id']}/{path.lstrip('/')}"
    req_headers = {
        "Zotero-API-Key": config["api_key"],
        "Zotero-API-Version": "3",
    }
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
        raise ZoteroApiError(exc.code, message) from exc


def read_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    policy = plan.get("policy", {})
    if not policy.get("preserve_active_collections") or not policy.get("preserve_tags"):
        raise SystemExit("Refusing plan: cleanup preserve policy is missing")
    if policy.get("delete_items_or_pdfs") or policy.get("delete_collections"):
        raise SystemExit("Refusing plan: destructive deletion policy is enabled")
    return plan


def selected_actions(plan: dict[str, Any], item_key: str | None, max_items: int | None) -> list[dict[str, Any]]:
    actions = [row for row in plan.get("item_actions", []) if row.get("write_enabled")]
    if item_key:
        wanted = item_key.upper()
        actions = [row for row in actions if str(row.get("item_key", "")).upper() == wanted]
    if max_items:
        actions = actions[:max_items]
    return actions


def validate_deleted_collection(
    config: dict[str, str],
    key: str,
    opener: urllib.request.OpenerDirector,
) -> tuple[bool, str]:
    current = key
    names: list[str] = []
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        _status, _headers, payload = zotero_request(config, "GET", f"collections/{current}", opener=opener)
        data = (payload or {}).get("data", {})
        names.append(str(data.get("name") or current))
        if data.get("deleted"):
            return True, " / ".join(reversed(names))
        parent = data.get("parentCollection")
        current = str(parent) if parent else ""
    return False, " / ".join(reversed(names))


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else find_researchos_root(Path(__file__))
    ensure_output_dirs(root)
    plan_path = Path(args.write_plan)
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    plan = read_plan(plan_path)
    actions = selected_actions(plan, args.item_key, args.max_items)
    if not actions:
        raise SystemExit("No enabled item actions selected")

    config = env_config()
    opener, proxy_info = selected_proxy()
    run_dir = root / RUNS_DIR / f"{safe_timestamp()}-{'write' if args.write else 'preflight'}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "proxy_info.redacted.json", proxy_info)
    write_json(run_dir / "selected_actions.json", actions)

    before_items: list[dict[str, Any]] = []
    after_items: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    rollback_items: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    for action in actions:
        item_key = str(action["item_key"])
        remove_keys = split_semicolon(action.get("remove_deleted_collection_keys", ""))
        keep_keys = split_semicolon(action.get("preserve_active_collection_keys", ""))
        blockers: list[str] = []
        for key in remove_keys:
            deleted, name = validate_deleted_collection(config, key, opener)
            if not deleted:
                blockers.append(f"{key} is not deleted collection ({name})")
        _status, _headers, before = zotero_request(config, "GET", f"items/{item_key}", opener=opener)
        before_items.append(before)
        data = before.get("data", {})
        current_collections = [str(key) for key in data.get("collections", []) if str(key)]
        current_tags = list(data.get("tags", []) or [])
        after_collections = [key for key in current_collections if key not in remove_keys]
        missing_keep_keys = [key for key in keep_keys if key not in after_collections]
        if missing_keep_keys:
            blockers.append(f"planned active keys missing from computed result: {';'.join(missing_keep_keys)}")
        unexpected_removed = [key for key in current_collections if key not in after_collections and key not in remove_keys]
        if unexpected_removed:
            blockers.append(f"unexpected removed keys: {';'.join(unexpected_removed)}")
        preview = {
            "item_key": item_key,
            "before_collections": current_collections,
            "remove_deleted_collection_keys": remove_keys,
            "after_collections": after_collections,
            "tags_preserved_count": len(current_tags),
        }
        previews.append(preview)
        if blockers:
            audit_rows.append(
                {
                    "timestamp": utc_now(),
                    "mode": "blocked",
                    "item_key": item_key,
                    "write_performed": False,
                    "removed_deleted_collection_keys": "; ".join(remove_keys),
                    "kept_collection_keys": "; ".join(after_collections),
                    "before_version": before.get("version"),
                    "after_version": "",
                    "http_status": "",
                    "blocking_conditions": "; ".join(blockers),
                }
            )
            continue
        if not args.write:
            audit_rows.append(
                {
                    "timestamp": utc_now(),
                    "mode": "preflight",
                    "item_key": item_key,
                    "write_performed": False,
                    "removed_deleted_collection_keys": "; ".join(remove_keys),
                    "kept_collection_keys": "; ".join(after_collections),
                    "before_version": before.get("version"),
                    "after_version": "",
                    "http_status": 200,
                    "blocking_conditions": "",
                }
            )
            continue
        status, _headers, _payload = zotero_request(
            config,
            "PATCH",
            f"items/{item_key}",
            {"collections": after_collections, "tags": current_tags},
            {"If-Unmodified-Since-Version": str(before.get("version"))},
            opener=opener,
        )
        if status != 204:
            raise ZoteroApiError(status, f"Unexpected item update status for {item_key}")
        time.sleep(0.05)
        _status, _headers, after = zotero_request(config, "GET", f"items/{item_key}", opener=opener)
        after_items.append(after)
        rollback_items.append(
            {
                "item_key": item_key,
                "method": "PATCH",
                "endpoint": f"items/{item_key}",
                "restore_collections": current_collections,
                "restore_tags": current_tags,
                "current_after_version": after.get("version"),
            }
        )
        audit_rows.append(
            {
                "timestamp": utc_now(),
                "mode": "deleted_collection_cleanup",
                "item_key": item_key,
                "write_performed": True,
                "removed_deleted_collection_keys": "; ".join(remove_keys),
                "kept_collection_keys": "; ".join(after_collections),
                "before_version": before.get("version"),
                "after_version": after.get("version"),
                "http_status": 204,
                "blocking_conditions": "",
            }
        )

    write_json(run_dir / "before_items.json", before_items)
    write_json(run_dir / "after_items.json", after_items)
    write_json(run_dir / "update_previews.json", previews)
    write_json(run_dir / "rollback_plan.json", {"generated_at": utc_now(), "rollback_items": rollback_items})
    write_csv(run_dir / "write_audit.csv", audit_rows, AUDIT_FIELDS)
    summary = {
        "generated_at": utc_now(),
        "mode": "write" if args.write else "preflight",
        "run_dir": str(run_dir),
        "selected_items": len(actions),
        "writes_performed": sum(1 for row in audit_rows if row.get("write_performed") is True),
        "blocked_rows": sum(1 for row in audit_rows if row.get("blocking_conditions")),
        "proxy": proxy_info,
    }
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["blocked_rows"] == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--write-plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--item-key")
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
