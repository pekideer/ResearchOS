"""Additively write a project collection overlay to Zotero Web API.

This script is intentionally narrow for ResearchOS project collection overlays:
- creates missing target collection paths;
- adds target collection memberships to items;
- preserves every existing item collection membership;
- never writes tags, notes, attachments, or PDFs;
- never prints API keys.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None

RESEARCHOS_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.zotero.write.zotero_web_api import fetch_web_api_paged
from tools.zotero.write.zotero_web_api import normalize_proxy


class ZoteroApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:80]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


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
    missing = [name for name, value in (("ZOTERO_API_KEY", api_key), ("ZOTERO_USER_ID", user_id)) if not value]
    if missing:
        raise SystemExit(f"Missing required environment variable(s): {', '.join(missing)}")
    return {"api_key": api_key, "user_id": user_id, "api_base": api_base}


def system_proxy() -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return ""
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except OSError:
        return ""
    value = str(proxy_server or "").strip()
    if not value:
        return ""
    # Windows may store protocol-specific values such as
    # "http=127.0.0.1:7890;https=127.0.0.1:7890".
    parts = [part.strip() for part in value.split(";") if part.strip()]
    protocol_map: dict[str, str] = {}
    for part in parts:
        if "=" in part:
            proto, address = part.split("=", 1)
            protocol_map[proto.lower()] = address
    return normalize_proxy(protocol_map.get("https") or protocol_map.get("http") or value)


def proxy_config() -> tuple[str, str]:
    candidates = [
        ("ZOTERO_HTTPS_PROXY", os.environ.get("ZOTERO_HTTPS_PROXY", "")),
        ("HTTPS_PROXY", os.environ.get("HTTPS_PROXY", "")),
        ("HTTP_PROXY", os.environ.get("HTTP_PROXY", "")),
        ("ALL_PROXY", os.environ.get("ALL_PROXY", "")),
    ]
    for source, value in candidates:
        proxy = normalize_proxy(value)
        if proxy:
            return source, proxy
    machine_config = RESEARCHOS_ROOT / ".local" / "machine_config.json"
    if machine_config.exists():
        try:
            data = json.loads(machine_config.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            data = {}
        proxy_fields = data.get("proxy", {}) if isinstance(data, dict) else {}
        if isinstance(proxy_fields, dict):
            for field in ("https_proxy", "http_proxy", "all_proxy"):
                proxy = normalize_proxy(str(proxy_fields.get(field) or ""))
                if proxy:
                    return f"machine_config.{field}", proxy
    proxy = system_proxy()
    if proxy:
        return "WindowsSystemProxy", proxy
    raise SystemExit(
        "Zotero Web API requires a per-machine proxy. Set ZOTERO_HTTPS_PROXY/HTTPS_PROXY/HTTP_PROXY/ALL_PROXY "
        "or configure .local/machine_config.json; do not hardcode a shared host/port."
    )


def safe_proxy_label(proxy: str) -> str:
    if not proxy:
        return ""
    parsed = urllib.parse.urlsplit(proxy)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}{port}" if host else scheme


def zotero_request(
    config: dict[str, str],
    method: str,
    path: str,
    body: Any | None = None,
    headers: dict[str, str] | None = None,
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
        _proxy_source, proxy = proxy_config()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy, "http": proxy})) if proxy else urllib.request
        with opener.open(request, timeout=60) as response:
            raw = response.read()
            text = raw.decode("utf-8") if raw else ""
            parsed = json.loads(text) if text else None
            return response.status, dict(response.headers.items()), parsed
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise ZoteroApiError(exc.code, message) from exc


fetch_paged = partial(fetch_web_api_paged, request_fn=zotero_request, error_cls=ZoteroApiError)



def fetch_items_by_keys(config: dict[str, str], item_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not item_keys:
        return {}
    encoded = urllib.parse.quote(",".join(item_keys), safe=",")
    rows = fetch_paged(config, f"items?itemKey={encoded}")
    found = {row["key"]: row for row in rows}
    missing = [key for key in item_keys if key not in found]
    if missing:
        raise RuntimeError(f"Zotero Web API did not return requested item(s): {missing}")
    return found


def library_version(config: dict[str, str]) -> int:
    _, headers, _ = zotero_request(config, "GET", "items?limit=1")
    version = headers.get("Last-Modified-Version")
    if not version:
        raise RuntimeError("Zotero Web API did not return Last-Modified-Version")
    return int(version)


def collection_paths(collections: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    by_key = {row["key"]: row for row in collections}
    memo: dict[str, str] = {}

    def path_for(key: str) -> str:
        if key in memo:
            return memo[key]
        row = by_key[key]
        data = row.get("data", {})
        name = data.get("name", key)
        parent = data.get("parentCollection")
        if parent and parent in by_key:
            path = f"{path_for(parent)}/{name}"
        else:
            path = name
        memo[key] = path
        return path

    path_by_key = {key: path_for(key) for key in by_key}
    key_by_path = {path: key for key, path in path_by_key.items()}
    return by_key, path_by_key, key_by_path


def target_map(assignments: list[dict[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in assignments:
        key = row.get("item_key", "").strip()
        path = row.get("目标项目文献集", "").strip()
        if not key or not path:
            continue
        if path not in grouped[key]:
            grouped[key].append(path)
    return dict(grouped)


TRIAGE_COLLECTION_NAME = "00-待分配-triage"


def collection_assignment_policy(
    target_paths: list[str],
    key_by_path: dict[str, str],
) -> dict[str, Any]:
    """Resolve one project's triage path and reject ambiguous assignment plans."""
    cleaned = [path.strip().strip("/") for path in target_paths if path.strip().strip("/")]
    if not cleaned:
        raise ValueError("item assignment has no target collection path")
    parents = {path.rsplit("/", 1)[0] if "/" in path else "" for path in cleaned}
    if len(parents) != 1:
        raise ValueError("all target project collections for one item must share one project parent")
    parent = next(iter(parents))
    triage_path = f"{parent}/{TRIAGE_COLLECTION_NAME}" if parent else TRIAGE_COLLECTION_NAME
    stable_paths = [path for path in cleaned if path != triage_path]
    if stable_paths and triage_path in cleaned:
        raise ValueError("triage and stable project collections cannot both be assignment targets")
    return {
        "triage_path": triage_path,
        "triage_key": key_by_path.get(triage_path, ""),
        "stable_assignment": bool(stable_paths),
    }


def exclusive_preview(
    item: dict[str, Any],
    target_collection_keys: list[str],
    target_collection_paths: list[str],
    path_by_key: dict[str, str],
    key_by_path: dict[str, str],
) -> dict[str, Any]:
    """Plan add-then-remove transitions while preserving unrelated collections."""
    policy = collection_assignment_policy(target_collection_paths, key_by_path)
    data = item.get("data", {})
    before_keys = list(data.get("collections", []) or [])
    add_phase_keys = list(before_keys)
    for key in target_collection_keys:
        if key not in add_phase_keys:
            add_phase_keys.append(key)
    final_keys = list(add_phase_keys)
    triage_key = str(policy["triage_key"] or "")
    if policy["stable_assignment"] and triage_key:
        final_keys = [key for key in final_keys if key != triage_key]
    return {
        "item_key": item.get("key"),
        "item_version": item.get("version"),
        "before_collection_keys": before_keys,
        "before_collection_paths": [path_by_key.get(key, key) for key in before_keys],
        "target_collection_keys": target_collection_keys,
        "target_collection_paths": target_collection_paths,
        "triage_collection_key": triage_key,
        "triage_collection_path": policy["triage_path"],
        "stable_assignment": policy["stable_assignment"],
        "add_phase_collection_keys": add_phase_keys,
        "add_phase_collection_paths": [path_by_key.get(key, key) for key in add_phase_keys],
        "after_collection_keys": final_keys,
        "after_collection_paths": [path_by_key.get(key, key) for key in final_keys],
        "collection_policy": "exclusive: add and verify stable targets, then remove project triage, preserving unrelated collections",
    }


def collection_postcondition_errors(item: dict[str, Any], preview: dict[str, Any]) -> list[str]:
    current = set((item.get("data", {}) or {}).get("collections", []) or [])
    errors: list[str] = []
    if not set(preview["target_collection_keys"]).issubset(current):
        errors.append("target_collection_missing_after_write")
    triage_key = str(preview.get("triage_collection_key") or "")
    if preview.get("stable_assignment") and triage_key and triage_key in current:
        errors.append("triage_collection_present_after_stable_assignment")
    return errors


def hierarchy_paths(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    paths: list[str] = []
    project = payload.get("project", {})
    parent = project.get("parent_path", "")
    name = project.get("name", "")
    if parent and name:
        paths.append(f"{parent}/{name}")
    for child in payload.get("children", []) or []:
        child_path = child.get("path", "")
        if child_path and child_path not in paths:
            paths.append(child_path)
    return paths


def create_collection(
    config: dict[str, str],
    name: str,
    parent_key: str | bool,
    run_dir: Path,
    audit_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    before_version = library_version(config)
    payload = [{"name": name, "parentCollection": parent_key}]
    status, headers, response = zotero_request(
        config,
        "POST",
        "collections",
        payload,
        {"If-Unmodified-Since-Version": str(before_version)},
    )
    if status != 200:
        raise ZoteroApiError(status, "Unexpected collection create status")
    failed = (response or {}).get("failed", {})
    if failed:
        raise RuntimeError(f"Collection create failed: {json.dumps(failed, ensure_ascii=False)}")
    successful = (response or {}).get("successful", {})
    created = successful.get("0") or successful.get(0)
    if not created:
        raise RuntimeError(f"Collection create response missing successful object: {response}")
    key = created.get("key") or created.get("data", {}).get("key")
    if not key:
        raise RuntimeError(f"Collection create response missing key: {created}")
    audit_rows.append(
        {
            "timestamp": utc_now(),
            "mode": "create_collection",
            "item_key": "",
            "write_performed": True,
            "target": name,
            "http_status": status,
            "before_version": before_version,
            "after_version": headers.get("Last-Modified-Version", ""),
            "created_key": key,
            "blocking_conditions": "",
        }
    )
    write_json(run_dir / f"created_collection_{slug(name)}_{key}.json", created)
    return created


def ensure_collection_path(
    config: dict[str, str],
    target_path: str,
    run_dir: Path,
    audit_rows: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    collections = fetch_paged(config, "collections")
    _, path_by_key, key_by_path = collection_paths(collections)
    created: list[dict[str, Any]] = []
    parent_key: str | bool = False
    current_parts: list[str] = []
    for part in target_path.split("/"):
        current_parts.append(part)
        current_path = "/".join(current_parts)
        if current_path in key_by_path:
            parent_key = key_by_path[current_path]
            continue
        created_collection = create_collection(config, part, parent_key, run_dir, audit_rows)
        created.append(created_collection)
        parent_key = created_collection.get("key") or created_collection.get("data", {}).get("key")
        collections = fetch_paged(config, "collections")
        _, path_by_key, key_by_path = collection_paths(collections)
        if current_path not in key_by_path:
            raise RuntimeError(f"Created collection but path is still missing: {current_path}")
    return key_by_path[target_path], created, path_by_key


def patch_item_collections(
    config: dict[str, str],
    item_key: str,
    target_collection_keys: list[str],
    target_collection_paths: list[str],
    path_by_key: dict[str, str],
    key_by_path: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], int]:
    _, _, item_before = zotero_request(config, "GET", f"items/{item_key}")
    preview = exclusive_preview(
        item_before,
        target_collection_keys,
        target_collection_paths,
        path_by_key,
        key_by_path,
    )
    wrote = False
    live = item_before
    if preview["add_phase_collection_keys"] != preview["before_collection_keys"]:
        status, _headers, _ = zotero_request(
            config,
            "PATCH",
            f"items/{item_key}",
            {"collections": preview["add_phase_collection_keys"]},
            {"If-Unmodified-Since-Version": str(item_before["version"])},
        )
        if status != 204:
            raise ZoteroApiError(status, f"Unexpected add-phase item update status for {item_key}")
        wrote = True
        time.sleep(0.1)
        _, _, live = zotero_request(config, "GET", f"items/{item_key}")
    if not set(target_collection_keys).issubset(set((live.get("data", {}) or {}).get("collections", []) or [])):
        raise RuntimeError(f"Add-phase postcondition failed for {item_key}: target collection missing")
    triage_key = str(preview.get("triage_collection_key") or "")
    live_keys = list((live.get("data", {}) or {}).get("collections", []) or [])
    if preview["stable_assignment"] and triage_key and triage_key in live_keys:
        final_keys = [key for key in live_keys if key != triage_key]
        status, _headers, _ = zotero_request(
            config,
            "PATCH",
            f"items/{item_key}",
            {"collections": final_keys},
            {"If-Unmodified-Since-Version": str(live["version"])},
        )
        if status != 204:
            raise ZoteroApiError(status, f"Unexpected triage-removal item update status for {item_key}")
        wrote = True
        time.sleep(0.1)
        _, _, live = zotero_request(config, "GET", f"items/{item_key}")
    errors = collection_postcondition_errors(live, preview)
    if errors:
        raise RuntimeError(f"Exclusive collection postcondition failed for {item_key}: {', '.join(errors)}")
    preview["after_collection_keys"] = list((live.get("data", {}) or {}).get("collections", []) or [])
    preview["after_collection_paths"] = [path_by_key.get(key, key) for key in preview["after_collection_keys"]]
    return item_before, live, preview, 204 if wrote else 304


def audit_fields() -> list[str]:
    return [
        "timestamp",
        "mode",
        "item_key",
        "write_performed",
        "target",
        "http_status",
        "before_version",
        "after_version",
        "created_key",
        "blocking_conditions",
    ]


def command_preflight(args: argparse.Namespace) -> int:
    config = env_config()
    proxy_source, proxy = proxy_config()
    assignments = read_csv(Path(args.assignments))
    targets = target_map(assignments)
    hierarchy_target_paths = hierarchy_paths(Path(args.hierarchy))
    run_dir = Path(args.runs_dir) / f"{safe_timestamp()}-preflight"
    run_dir.mkdir(parents=True, exist_ok=True)
    version = library_version(config)
    collections = fetch_paged(config, "collections")
    _, _path_by_key, key_by_path = collection_paths(collections)
    item_results: list[dict[str, Any]] = []
    for key in sorted(targets):
        status, _headers, item = zotero_request(config, "GET", f"items/{key}")
        try:
            policy = collection_assignment_policy(targets[key], key_by_path)
        except ValueError as exc:
            raise SystemExit(f"Invalid collection assignment for {key}: {exc}") from exc
        current_keys = set(item.get("data", {}).get("collections", []) or [])
        item_results.append(
            {
                "item_key": key,
                "http_status": status,
                "version": item.get("version"),
                "title": item.get("data", {}).get("title", ""),
                "current_collection_count": len(item.get("data", {}).get("collections", []) or []),
                "target_collection_count": len(targets[key]),
                "triage_collection_path": policy["triage_path"],
                "triage_present_before": bool(policy["triage_key"] and policy["triage_key"] in current_keys),
                "execution_order": "add_targets_verify_then_remove_triage" if policy["stable_assignment"] else "retain_triage_only",
            }
        )
    target_paths = sorted(
        set(hierarchy_target_paths) | {path for paths in targets.values() for path in paths},
        key=lambda value: (value.count("/"), value),
    )
    missing_paths = [path for path in target_paths if path not in key_by_path]
    write_json(run_dir / "collections_before.json", collections)
    write_json(run_dir / "preflight_summary.json", {
        "mode": "preflight",
        "write_performed": False,
        "proxy_source": proxy_source,
        "proxy": safe_proxy_label(proxy),
        "library_version": version,
        "planned_items": len(targets),
        "planned_assignment_paths": sum(len(paths) for paths in targets.values()),
        "target_paths": target_paths,
        "missing_target_paths": missing_paths,
        "items": item_results,
    })
    print(json.dumps({
        "run_dir": str(run_dir),
        "write_performed": False,
        "library_version": version,
        "planned_items": len(targets),
        "missing_target_paths": len(missing_paths),
        "proxy_source": proxy_source,
        "proxy": safe_proxy_label(proxy),
    }, ensure_ascii=False, indent=2))
    return 0


def command_canary(args: argparse.Namespace) -> int:
    config = env_config()
    proxy_source, proxy = proxy_config()
    assignments = read_csv(Path(args.assignments))
    rows = [row for row in assignments if row.get("item_key") == args.item_key]
    if not rows:
        raise SystemExit(f"Canary item {args.item_key} not found in assignments")
    target_path = args.target_path or rows[0]["目标项目文献集"]
    run_dir = Path(args.runs_dir) / f"{safe_timestamp()}-canary-{args.item_key}"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, Any]] = []
    collections_before = fetch_paged(config, "collections")
    write_json(run_dir / "collections_before.json", collections_before)
    _, _, item_before = zotero_request(config, "GET", f"items/{args.item_key}")
    write_json(run_dir / "canary_item_before.json", item_before)
    target_key, created, path_by_key = ensure_collection_path(config, target_path, run_dir, audit_rows)
    collections_live = fetch_paged(config, "collections")
    _, path_by_key, key_by_path = collection_paths(collections_live)
    _, item_after, preview, status = patch_item_collections(
        config,
        args.item_key,
        [target_key],
        [target_path],
        path_by_key,
        key_by_path,
    )
    write_json(run_dir / "canary_update_preview.json", preview)
    write_json(run_dir / "canary_item_after.json", item_after)
    rollback = {
        "mode": "canary_exclusive_collection_rollback",
        "item_key": args.item_key,
        "endpoint": f"items/{args.item_key}",
        "restore_collections": preview["before_collection_keys"],
        "created_collections_to_delete_if_rolling_back": [
            {
                "key": row.get("key") or row.get("data", {}).get("key"),
                "name": row.get("data", {}).get("name") or row.get("name"),
            }
            for row in reversed(created)
        ],
        "note": "Rollback must restore item collections before deleting created empty collections.",
    }
    write_json(run_dir / "canary_rollback_plan.json", rollback)
    audit_rows.append(
        {
            "timestamp": utc_now(),
            "mode": "canary_add_item_to_collection",
            "item_key": args.item_key,
            "write_performed": status == 204,
            "target": target_path,
            "http_status": status,
            "before_version": item_before.get("version"),
            "after_version": item_after.get("version"),
            "created_key": target_key,
            "blocking_conditions": "",
        }
    )
    write_csv(run_dir / "write_audit.csv", audit_rows, audit_fields())
    collections_after = fetch_paged(config, "collections")
    write_json(run_dir / "collections_after.json", collections_after)
    print(json.dumps({
        "run_dir": str(run_dir),
        "mode": "canary",
        "proxy_source": proxy_source,
        "proxy": safe_proxy_label(proxy),
        "item_key": args.item_key,
        "target_path": target_path,
        "created_collections": len(created),
        "item_write_status": status,
        "before_collection_count": len(preview["before_collection_keys"]),
        "after_collection_count": len(preview["after_collection_keys"]),
        "rollback_plan": str(run_dir / "canary_rollback_plan.json"),
    }, ensure_ascii=False, indent=2))
    return 0


def command_write(args: argparse.Namespace) -> int:
    config = env_config()
    proxy_source, proxy = proxy_config()
    assignments = read_csv(Path(args.assignments))
    targets = target_map(assignments)
    hierarchy_target_paths = hierarchy_paths(Path(args.hierarchy))
    selected_keys = sorted(targets)
    if args.start_after:
        if args.start_after not in selected_keys:
            raise SystemExit(f"start-after key not found: {args.start_after}")
        selected_keys = selected_keys[selected_keys.index(args.start_after) + 1 :]
    if args.max_items:
        selected_keys = selected_keys[: args.max_items]
    if not selected_keys:
        raise SystemExit("No items selected for write")

    run_dir = Path(args.runs_dir) / f"{safe_timestamp()}-write"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, Any]] = []
    collections_before = fetch_paged(config, "collections")
    write_json(run_dir / "collections_before.json", collections_before)
    _, path_by_key, key_by_path = collection_paths(collections_before)

    all_paths = sorted(
        set(hierarchy_target_paths) | {path for key in selected_keys for path in targets[key]},
        key=lambda value: (value.count("/"), value),
    )
    created_all: list[dict[str, Any]] = []
    for path in all_paths:
        if path in key_by_path:
            continue
        _target_key, created, path_by_key = ensure_collection_path(config, path, run_dir, audit_rows)
        created_all.extend(created)
        collections_live = fetch_paged(config, "collections")
        _, path_by_key, key_by_path = collection_paths(collections_live)

    before_items: dict[str, Any] = {}
    after_items: dict[str, Any] = {}
    previews: dict[str, Any] = {}
    rollback_items: list[dict[str, Any]] = []
    for key in selected_keys:
        target_keys = [key_by_path[path] for path in targets[key]]
        item_before, item_after, preview, status = patch_item_collections(
            config,
            key,
            target_keys,
            targets[key],
            path_by_key,
            key_by_path,
        )
        before_items[key] = item_before
        after_items[key] = item_after
        previews[key] = preview
        rollback_items.append(
            {
                "item_key": key,
                "endpoint": f"items/{key}",
                "restore_collections": preview["before_collection_keys"],
                "target_collection_paths": preview["target_collection_paths"],
                "triage_collection_path": preview["triage_collection_path"],
            }
        )
        audit_rows.append(
            {
                "timestamp": utc_now(),
                "mode": "assign_project_collections_exclusive",
                "item_key": key,
                "write_performed": status == 204,
                "target": "; ".join(targets[key]),
                "http_status": status,
                "before_version": item_before.get("version"),
                "after_version": item_after.get("version"),
                "created_key": "; ".join(target_keys),
                "blocking_conditions": "",
            }
        )

    write_json(run_dir / "items_before.json", before_items)
    write_json(run_dir / "items_after.json", after_items)
    write_json(run_dir / "item_update_previews.json", previews)
    write_csv(run_dir / "write_audit.csv", audit_rows, audit_fields())
    write_json(run_dir / "rollback_plan.json", {
        "mode": "project_collection_overlay_exclusive_rollback",
        "items": rollback_items,
        "created_collections_to_delete_if_rolling_back": [
            {
                "key": row.get("key") or row.get("data", {}).get("key"),
                "name": row.get("data", {}).get("name") or row.get("name"),
            }
            for row in reversed(created_all)
        ],
        "note": "Rollback must restore item collections before deleting newly created empty collections.",
    })
    collections_after = fetch_paged(config, "collections")
    write_json(run_dir / "collections_after.json", collections_after)
    print(json.dumps({
        "run_dir": str(run_dir),
        "mode": "write",
        "proxy_source": proxy_source,
        "proxy": safe_proxy_label(proxy),
        "items_selected": len(selected_keys),
        "created_collections": len(created_all),
        "audit": str(run_dir / "write_audit.csv"),
        "rollback_plan": str(run_dir / "rollback_plan.json"),
    }, ensure_ascii=False, indent=2))
    return 0


def command_write_batch(args: argparse.Namespace) -> int:
    config = env_config()
    proxy_source, proxy = proxy_config()
    assignments = read_csv(Path(args.assignments))
    targets = target_map(assignments)
    selected_keys = sorted(targets)
    if args.incomplete_only:
        collections_live = fetch_paged(config, "collections")
        _, live_path_by_key, live_key_by_path = collection_paths(collections_live)
        items_live = fetch_items_by_keys(config, selected_keys)
        incomplete: list[str] = []
        for key in selected_keys:
            target_keys = [live_key_by_path[path] for path in targets[key] if path in live_key_by_path]
            if len(target_keys) != len(targets[key]):
                incomplete.append(key)
                continue
            preview = exclusive_preview(
                items_live[key], target_keys, targets[key], live_path_by_key, live_key_by_path
            )
            if collection_postcondition_errors(items_live[key], preview):
                incomplete.append(key)
        selected_keys = incomplete
    if args.start_after:
        if args.start_after not in selected_keys:
            raise SystemExit(f"start-after key not found in selected keys: {args.start_after}")
        selected_keys = selected_keys[selected_keys.index(args.start_after) + 1 :]
    if args.batch_size:
        selected_keys = selected_keys[: args.batch_size]
    if not selected_keys:
        print(json.dumps({"mode": "write-batch", "items_selected": 0, "write_performed": False}, ensure_ascii=False, indent=2))
        return 0

    run_dir = Path(args.runs_dir) / f"{safe_timestamp()}-write-batch"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, Any]] = []

    collections_before = fetch_paged(config, "collections")
    write_json(run_dir / "collections_before.json", collections_before)
    _, path_by_key, key_by_path = collection_paths(collections_before)
    missing_paths = sorted(
        {path for key in selected_keys for path in targets[key] if path not in key_by_path},
        key=lambda value: (value.count("/"), value),
    )
    if missing_paths:
        raise SystemExit(f"Target collection paths are missing; create hierarchy first: {missing_paths[:10]}")

    before_items = fetch_items_by_keys(config, selected_keys)
    write_json(run_dir / "items_before.json", before_items)

    add_payload: list[dict[str, Any]] = []
    previews: dict[str, Any] = {}
    for key in selected_keys:
        target_keys = [key_by_path[path] for path in targets[key]]
        preview = exclusive_preview(
            before_items[key], target_keys, targets[key], path_by_key, key_by_path
        )
        previews[key] = preview
        if preview["add_phase_collection_keys"] != preview["before_collection_keys"]:
            add_payload.append({
                "key": key,
                "version": before_items[key]["version"],
                "collections": preview["add_phase_collection_keys"],
            })

    write_json(run_dir / "item_update_previews.json", previews)
    rollback_items = [
        {
            "item_key": key,
            "endpoint": f"items/{key}",
            "restore_collections": previews[key]["before_collection_keys"],
            "before_collection_paths": previews[key]["before_collection_paths"],
            "target_collection_paths": previews[key]["target_collection_paths"],
            "triage_collection_path": previews[key]["triage_collection_path"],
        }
        for key in selected_keys
    ]
    write_json(run_dir / "rollback_plan.json", {
        "mode": "project_collection_overlay_exclusive_batch_rollback",
        "items": rollback_items,
        "note": "Rollback must POST item objects with original collection arrays. No collections are deleted by this rollback plan.",
    })

    add_status = 304
    if add_payload:
        add_status, _headers, response = zotero_request(config, "POST", "items", add_payload)
        write_json(run_dir / "batch_add_response.json", response)
        if add_status != 200:
            raise ZoteroApiError(add_status, "Unexpected batch add-phase status")
        failed = (response or {}).get("failed", {})
        if failed:
            raise RuntimeError(f"Batch add phase had failed rows: {json.dumps(failed, ensure_ascii=False)}")

    add_after_items = fetch_items_by_keys(config, selected_keys)
    write_json(run_dir / "items_after_add_phase.json", add_after_items)
    for key in selected_keys:
        current = set((add_after_items[key].get("data", {}) or {}).get("collections", []) or [])
        if not set(previews[key]["target_collection_keys"]).issubset(current):
            raise RuntimeError(f"Batch add-phase postcondition failed for {key}: target collection missing")

    remove_payload: list[dict[str, Any]] = []
    for key in selected_keys:
        preview = previews[key]
        triage_key = str(preview.get("triage_collection_key") or "")
        live_keys = list((add_after_items[key].get("data", {}) or {}).get("collections", []) or [])
        if preview["stable_assignment"] and triage_key and triage_key in live_keys:
            remove_payload.append({
                "key": key,
                "version": add_after_items[key]["version"],
                "collections": [collection_key for collection_key in live_keys if collection_key != triage_key],
            })

    remove_status = 304
    if remove_payload:
        remove_status, _headers, response = zotero_request(config, "POST", "items", remove_payload)
        write_json(run_dir / "batch_triage_removal_response.json", response)
        if remove_status != 200:
            raise ZoteroApiError(remove_status, "Unexpected batch triage-removal status")
        failed = (response or {}).get("failed", {})
        if failed:
            raise RuntimeError(f"Batch triage removal had failed rows: {json.dumps(failed, ensure_ascii=False)}")

    after_items = fetch_items_by_keys(config, selected_keys)
    write_json(run_dir / "items_after.json", after_items)

    postcondition_failures: dict[str, list[str]] = {}
    for key in selected_keys:
        preview = previews[key]
        before_paths = preview["before_collection_paths"]
        after_paths = [path_by_key.get(collection_key, collection_key) for collection_key in after_items[key].get("data", {}).get("collections", []) or []]
        errors = collection_postcondition_errors(after_items[key], preview)
        if errors:
            postcondition_failures[key] = errors
        audit_rows.append(
            {
                "timestamp": utc_now(),
                "mode": "batch_assign_project_collections_exclusive",
                "item_key": key,
                "write_performed": preview["before_collection_keys"] != list((after_items[key].get("data", {}) or {}).get("collections", []) or []),
                "target": "; ".join(targets[key]),
                "http_status": f"add:{add_status};remove:{remove_status}",
                "before_version": before_items[key].get("version"),
                "after_version": after_items[key].get("version"),
                "created_key": "; ".join(preview["target_collection_keys"]),
                "blocking_conditions": ";".join(errors),
            }
        )
        for rollback in rollback_items:
            if rollback["item_key"] == key:
                rollback["after_collection_paths"] = after_paths
                break

    write_csv(run_dir / "write_audit.csv", audit_rows, audit_fields())
    write_json(run_dir / "rollback_plan.json", {
        "mode": "project_collection_overlay_exclusive_batch_rollback",
        "items": rollback_items,
        "note": "Rollback must POST item objects with original collection arrays. No collections are deleted by this rollback plan.",
    })
    if postcondition_failures:
        raise RuntimeError("Exclusive collection postcondition failures: " + json.dumps(postcondition_failures, ensure_ascii=False))
    items_written = sum(
        previews[key]["before_collection_keys"]
        != list((after_items[key].get("data", {}) or {}).get("collections", []) or [])
        for key in selected_keys
    )
    print(json.dumps({
        "run_dir": str(run_dir),
        "mode": "write-batch",
        "proxy_source": proxy_source,
        "proxy": safe_proxy_label(proxy),
        "items_selected": len(selected_keys),
        "items_written": items_written,
        "items_skipped_already_complete": len(selected_keys) - items_written,
        "add_phase_status": add_status,
        "triage_removal_status": remove_status,
        "audit": str(run_dir / "write_audit.csv"),
        "rollback_plan": str(run_dir / "rollback_plan.json"),
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assignments", required=True, help="Approved assignment CSV from a dry-run project collection overlay plan.")
    parser.add_argument("--hierarchy", required=True, help="Approved hierarchy JSON from a dry-run project collection overlay plan.")
    parser.add_argument("--runs-dir", required=True, help="Directory for preflight, canary, write, audit, and rollback outputs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.set_defaults(func=command_preflight)

    canary = subparsers.add_parser("canary")
    canary.add_argument("--item-key", required=True)
    canary.add_argument("--target-path", required=True)
    canary.set_defaults(func=command_canary)

    write = subparsers.add_parser("write")
    write.add_argument("--max-items", type=int, default=0)
    write.add_argument("--start-after", default="")
    write.set_defaults(func=command_write)

    write_batch = subparsers.add_parser("write-batch")
    write_batch.add_argument("--batch-size", type=int, default=20)
    write_batch.add_argument("--start-after", default="")
    write_batch.add_argument("--incomplete-only", action="store_true")
    write_batch.set_defaults(func=command_write_batch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
