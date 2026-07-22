from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.researchos_outputs import write_json

from .mutation_contract import (
    MutationAction,
    MutationPlan,
    apply_mutation,
    plan_hash,
    snapshot_drift,
    snapshot_from_item,
)


RequestFn = Callable[[str, str, Any | None, dict[str, str] | None], tuple[int, dict[str, str], Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def collection_maps(collections: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    by_key = {str(row["key"]): row for row in collections}
    cache: dict[str, str] = {}

    def path_for(key: str) -> str:
        if key in cache:
            return cache[key]
        data = by_key[key].get("data", {})
        name = str(data.get("name") or key)
        parent = data.get("parentCollection")
        value = f"{path_for(str(parent))}/{name}" if parent and str(parent) in by_key else name
        cache[key] = value
        return value

    path_by_key = {key: path_for(key) for key in by_key}
    return {path: key for key, path in path_by_key.items()}, path_by_key


def select_actions(plan: MutationPlan, item_key: str | None, max_items: int | None) -> list[MutationAction]:
    actions = list(plan.actions)
    if item_key:
        actions = [action for action in actions if action.item_key == item_key.strip().upper()]
    if max_items:
        actions = actions[:max_items]
    if not actions:
        raise ValueError("no mutation actions selected")
    return actions


def freeze_and_validate(
    actions: list[MutationAction],
    request: RequestFn,
    key_by_path: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch and validate every selected item before any mutation is permitted."""
    prepared: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for action in actions:
        status, _headers, item = request("GET", f"items/{action.item_key}", None, None)
        reasons: list[str] = []
        if status != 200:
            reasons.append(f"preflight_get_status:{status}")
        live = snapshot_from_item(item)
        reasons.extend(snapshot_drift(action.expected_before, live))
        try:
            after_tags, after_collections = apply_mutation(live, action.mutation, key_by_path)
        except ValueError as exc:
            reasons.append(str(exc))
            after_tags, after_collections = (), ()
        if set(after_tags) != set(action.expected_after_tags):
            reasons.append("expected_after.tags")
        if set(after_collections) != set(action.expected_after_collection_keys):
            reasons.append("expected_after.collections")
        if action.mutation.remove_collection_paths and not after_collections:
            reasons.append("would_remove_all_collections")
        row = {
            "item_key": action.item_key,
            "action": action,
            "item_before": item,
            "live_snapshot": live,
            "after_tags": after_tags,
            "after_collection_keys": after_collections,
        }
        prepared.append(row)
        if reasons:
            blocked.append({"item_key": action.item_key, "blocking_conditions": list(dict.fromkeys(reasons))})
    return prepared, blocked


def _write_audit(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "timestamp", "mode", "item_key", "write_performed", "http_status",
        "before_version", "after_version", "blocking_conditions",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _finalize_run(
    run_dir: Path,
    plan: MutationPlan,
    actions: list[MutationAction],
    write: bool,
    proxy_info: dict[str, str],
    blocked: list[dict[str, Any]],
    audit: list[dict[str, Any]],
    after_items: list[dict[str, Any]],
    rollback: list[dict[str, Any]],
) -> dict[str, Any]:
    write_json(run_dir / "preflight_blocks.json", blocked)
    write_json(run_dir / "after_items.json", after_items)
    write_json(run_dir / "rollback_plan.json", {"generated_at": utc_now(), "rollback_items": rollback})
    _write_audit(run_dir / "write_audit.csv", audit)
    summary = {
        "generated_at": utc_now(),
        "mode": "write" if write else "preflight",
        "run_dir": str(run_dir),
        "plan_id": plan.plan_id,
        "plan_sha256": plan_hash(plan),
        "source_packet_hash": plan.source_packet_hash,
        "selected_items": len(actions),
        "writes_performed": sum(row.get("write_performed") is True for row in audit),
        "blocked_rows": len(blocked),
        "proxy": proxy_info,
    }
    write_json(run_dir / "summary.json", summary)
    return summary


def execute_plan(
    plan: MutationPlan,
    actions: list[MutationAction],
    collections: list[dict[str, Any]],
    request: RequestFn,
    run_dir: Path,
    write: bool,
    proxy_info: dict[str, str],
) -> dict[str, Any]:
    """Run global preflight, then mutate only an approved and completely frozen plan."""
    run_dir.mkdir(parents=True, exist_ok=True)
    key_by_path, _path_by_key = collection_maps(collections)
    prepared, blocked = freeze_and_validate(actions, request, key_by_path)
    if write and plan.approval_status != "approved":
        blocked.append({"item_key": "", "blocking_conditions": ["plan_not_approved"]})

    write_json(run_dir / "plan_snapshot.json", plan.raw)
    write_json(run_dir / "proxy_info.redacted.json", proxy_info)
    write_json(run_dir / "collections_snapshot.json", collections)
    write_json(run_dir / "selected_actions.json", [action.item_key for action in actions])
    write_json(run_dir / "before_items.json", [row["item_before"] for row in prepared])
    write_json(run_dir / "update_previews.json", [{
        "item_key": row["item_key"],
        "after_tags": list(row["after_tags"]),
        "after_collection_keys": list(row["after_collection_keys"]),
    } for row in prepared])

    audit: list[dict[str, Any]] = []
    after_items: list[dict[str, Any]] = []
    rollback: list[dict[str, Any]] = []
    if blocked:
        for row in blocked:
            audit.append({
                "timestamp": utc_now(), "mode": "global_preflight_block", "item_key": row["item_key"],
                "write_performed": False, "http_status": "", "before_version": "", "after_version": "",
                "blocking_conditions": "; ".join(row["blocking_conditions"]),
            })
        return _finalize_run(run_dir, plan, actions, write, proxy_info, blocked, audit, after_items, rollback)

    if not write:
        for row in prepared:
            audit.append({
                "timestamp": utc_now(), "mode": "preflight", "item_key": row["item_key"],
                "write_performed": False, "http_status": 200,
                "before_version": row["item_before"].get("version"), "after_version": "",
                "blocking_conditions": "",
            })
        return _finalize_run(run_dir, plan, actions, write, proxy_info, blocked, audit, after_items, rollback)

    for row in prepared:
        before = row["item_before"]
        key = row["item_key"]
        status: int | None = None
        try:
            status, _headers, _payload = request(
                "PATCH",
                f"items/{key}",
                {
                    "tags": [{"tag": tag} for tag in row["after_tags"]],
                    "collections": list(row["after_collection_keys"]),
                },
                {"If-Unmodified-Since-Version": str(before["version"])},
            )
            if status != 204:
                raise RuntimeError(f"patch_status:{status}")
            rollback_row = {
                "item_key": key, "method": "PATCH", "endpoint": f"items/{key}",
                "restore_tags": before.get("data", {}).get("tags", []) or [],
                "restore_collections": before.get("data", {}).get("collections", []) or [],
                "current_after_version": None,
            }
            rollback.append(rollback_row)
            time.sleep(0.05)
            get_status, _headers, after = request("GET", f"items/{key}", None, None)
            after_snapshot = snapshot_from_item(after)
            if get_status != 200:
                raise RuntimeError(f"readback_status:{get_status}")
            if set(after_snapshot.tags) != set(row["after_tags"]):
                raise RuntimeError("readback_tags_mismatch")
            if set(after_snapshot.collection_keys) != set(row["after_collection_keys"]):
                raise RuntimeError("readback_collections_mismatch")
            after_items.append(after)
            rollback_row["current_after_version"] = after.get("version")
            audit.append({
                "timestamp": utc_now(), "mode": "approved_item_mutation", "item_key": key,
                "write_performed": True, "http_status": 204, "before_version": before.get("version"),
                "after_version": after.get("version"), "blocking_conditions": "",
            })
        except Exception as exc:
            blocked.append({"item_key": key, "blocking_conditions": [str(exc)]})
            audit.append({
                "timestamp": utc_now(), "mode": "write_failure", "item_key": key,
                "write_performed": status == 204,
                "http_status": status or "",
                "before_version": before.get("version"), "after_version": "",
                "blocking_conditions": str(exc),
            })
            break

    return _finalize_run(run_dir, plan, actions, write, proxy_info, blocked, audit, after_items, rollback)
