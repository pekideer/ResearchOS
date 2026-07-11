"""Execute additive Zotero Web API writes from a guarded dry-run plan."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.zotero.write.zotero_web_api import env_config, fetch_web_api_paged, selected_proxy
from tools.zotero.write.zotero_web_api import zotero_request as shared_zotero_request

from tools.researchos_outputs import (
    A001_LIBRARY_GOVERNANCE as ARCHIVE_DIR,
    M002_LIBRARY_GOVERNANCE as MACHINE_DIR,
    ensure_output_dirs,
    find_researchos_root,
    write_json,
)


DEFAULT_PLAN = MACHINE_DIR / "zotero-unfiled-additive-write-plan-dry-run.json"
RUNS_DIR = ARCHIVE_DIR / "zotero-unfiled-write-runs"
AUDIT_FIELDS = [
    "timestamp",
    "mode",
    "item_key",
    "write_performed",
    "target_collections",
    "add_tags",
    "http_status",
    "before_version",
    "after_version",
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


def slug(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "-", value).strip("-")[:80] or "run"


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


zotero_request = partial(shared_zotero_request, error_cls=ZoteroApiError)


def fetch_paged(config: dict[str, str], endpoint: str, opener: urllib.request.OpenerDirector) -> list[dict[str, Any]]:
    def request_fn(cfg: dict[str, str], method: str, path: str, body: Any | None, headers: dict[str, str] | None):
        return zotero_request(cfg, method, path, body, headers, opener)

    return fetch_web_api_paged(config, endpoint, request_fn=request_fn, error_cls=ZoteroApiError)


def collection_maps(collections: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    by_key = {row["key"]: row for row in collections}
    path_cache: dict[str, str] = {}

    def path_for(key: str) -> str:
        if key in path_cache:
            return path_cache[key]
        data = by_key[key].get("data", {})
        name = str(data.get("name") or key)
        parent = data.get("parentCollection")
        if parent and parent in by_key:
            value = f"{path_for(parent)}/{name}"
        else:
            value = name
        path_cache[key] = value
        return value

    path_by_key = {key: path_for(key) for key in by_key}
    key_by_path = {path: key for key, path in path_by_key.items()}
    return key_by_path, path_by_key


def read_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    policy = plan.get("policy", {})
    if not policy.get("preserve_existing_collections") or not policy.get("preserve_existing_tags"):
        raise SystemExit("Refusing plan: additive preserve policy is not present")
    return plan


def target_actions(plan: dict[str, Any], max_items: int | None, item_key: str | None) -> list[dict[str, Any]]:
    actions = [row for row in plan.get("item_actions", []) if row.get("write_enabled")]
    if item_key:
        wanted = item_key.upper()
        actions = [row for row in actions if str(row.get("item_key", "")).upper() == wanted]
    if max_items:
        actions = actions[:max_items]
    return actions


def update_preview(item: dict[str, Any], target_collection_keys: list[str], add_tags: list[str], path_by_key: dict[str, str]) -> dict[str, Any]:
    data = item.get("data", {})
    before_collections = list(data.get("collections", []) or [])
    after_collections: list[str] = []
    for key in before_collections + target_collection_keys:
        if key and key not in after_collections:
            after_collections.append(key)
    before_tags = [tag.get("tag", "") for tag in data.get("tags", []) or [] if tag.get("tag")]
    after_tags: list[str] = []
    for tag in before_tags + add_tags:
        if tag and tag not in after_tags:
            after_tags.append(tag)
    return {
        "item_key": item.get("key"),
        "before_collection_keys": before_collections,
        "before_collection_paths": [path_by_key.get(key, key) for key in before_collections],
        "target_collection_keys": target_collection_keys,
        "target_collection_paths": [path_by_key.get(key, key) for key in target_collection_keys],
        "after_collection_keys": after_collections,
        "after_collection_paths": [path_by_key.get(key, key) for key in after_collections],
        "before_tags": before_tags,
        "add_tags": add_tags,
        "after_tags": after_tags,
    }


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else find_researchos_root(Path(__file__))
    ensure_output_dirs(root)
    plan_path = Path(args.write_plan)
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    plan = read_plan(plan_path)
    actions = target_actions(plan, args.max_items, args.item_key)
    if not actions:
        raise SystemExit("No enabled item actions selected")

    config = env_config()
    opener, proxy_info = selected_proxy()
    run_dir = root / RUNS_DIR / f"{safe_timestamp()}-{'write' if args.write else 'preflight'}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "proxy_info.redacted.json", proxy_info)
    write_json(run_dir / "selected_actions.json", actions)

    collections = fetch_paged(config, "collections", opener)
    key_by_path, path_by_key = collection_maps(collections)
    write_json(run_dir / "collections_snapshot.json", collections)
    audit_rows: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    rollback_items: list[dict[str, Any]] = []
    before_items: list[dict[str, Any]] = []
    after_items: list[dict[str, Any]] = []

    for action in actions:
        item_key = str(action["item_key"])
        target_paths = split_semicolon(action.get("target_collections", ""))
        missing = [path for path in target_paths if path not in key_by_path]
        if missing:
            audit_rows.append(
                {
                    "timestamp": utc_now(),
                    "mode": "missing_target_collection",
                    "item_key": item_key,
                    "write_performed": False,
                    "target_collections": "; ".join(target_paths),
                    "add_tags": action.get("add_tags", ""),
                    "http_status": "",
                    "before_version": "",
                    "after_version": "",
                    "blocking_conditions": "; ".join(missing),
                }
            )
            continue
        _, _, item_before = zotero_request(config, "GET", f"items/{item_key}", opener=opener)
        target_keys = [key_by_path[path] for path in target_paths]
        add_tags = split_semicolon(action.get("add_tags", ""))
        preview = update_preview(item_before, target_keys, add_tags, path_by_key)
        previews.append(preview)
        before_items.append(item_before)
        if not args.write:
            audit_rows.append(
                {
                    "timestamp": utc_now(),
                    "mode": "preflight",
                    "item_key": item_key,
                    "write_performed": False,
                    "target_collections": "; ".join(target_paths),
                    "add_tags": "; ".join(add_tags),
                    "http_status": 200,
                    "before_version": item_before.get("version"),
                    "after_version": "",
                    "blocking_conditions": "",
                }
            )
            continue
        status, _headers, _payload = zotero_request(
            config,
            "PATCH",
            f"items/{item_key}",
            {
                "collections": preview["after_collection_keys"],
                "tags": [{"tag": tag} for tag in preview["after_tags"]],
            },
            {"If-Unmodified-Since-Version": str(item_before["version"])},
            opener=opener,
        )
        if status != 204:
            raise ZoteroApiError(status, f"Unexpected status for {item_key}")
        time.sleep(0.05)
        _, _, item_after = zotero_request(config, "GET", f"items/{item_key}", opener=opener)
        after_items.append(item_after)
        rollback_items.append(
            {
                "item_key": item_key,
                "method": "PATCH",
                "endpoint": f"items/{item_key}",
                "restore_collections": item_before.get("data", {}).get("collections", []) or [],
                "restore_tags": item_before.get("data", {}).get("tags", []) or [],
                "current_after_version": item_after.get("version"),
            }
        )
        audit_rows.append(
            {
                "timestamp": utc_now(),
                "mode": "additive_write",
                "item_key": item_key,
                "write_performed": True,
                "target_collections": "; ".join(target_paths),
                "add_tags": "; ".join(add_tags),
                "http_status": 204,
                "before_version": item_before.get("version"),
                "after_version": item_after.get("version"),
                "blocking_conditions": "",
            }
        )

    write_json(run_dir / "before_items.json", before_items)
    write_json(run_dir / "update_previews.json", previews)
    write_json(run_dir / "after_items.json", after_items)
    write_json(run_dir / "rollback_plan.json", {"generated_at": utc_now(), "rollback_items": rollback_items})
    write_csv(run_dir / "write_audit.csv", audit_rows, AUDIT_FIELDS)
    summary = {
        "generated_at": utc_now(),
        "mode": "write" if args.write else "preflight",
        "run_dir": str(run_dir),
        "selected_items": len(actions),
        "writes_performed": sum(1 for row in audit_rows if row.get("write_performed") is True),
        "proxy": proxy_info,
        "blocked_rows": sum(1 for row in audit_rows if row.get("blocking_conditions")),
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
    parser.add_argument("--write", action="store_true", help="Actually PATCH Zotero items. Omit for read-only preflight.")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
