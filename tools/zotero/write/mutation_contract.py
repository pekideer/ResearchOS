from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ItemSnapshot:
    version: int
    tags: tuple[str, ...]
    collection_keys: tuple[str, ...]


@dataclass(frozen=True)
class ItemMutation:
    add_tags: tuple[str, ...]
    remove_tags: tuple[str, ...]
    add_collection_paths: tuple[str, ...]
    remove_collection_paths: tuple[str, ...]


@dataclass(frozen=True)
class MutationAction:
    item_key: str
    expected_before: ItemSnapshot
    mutation: ItemMutation
    expected_after_tags: tuple[str, ...]
    expected_after_collection_keys: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class MutationPlan:
    plan_id: str
    plan_kind: str
    source_packet_hash: str
    approval_status: str
    actions: tuple[MutationAction, ...]
    raw: dict[str, Any]


def _string_array(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must be an array of non-empty strings")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} contains duplicates")
    return normalized


def _snapshot(value: Any, field: str) -> ItemSnapshot:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    if set(value) != {"version", "tags", "collection_keys"}:
        raise ValueError(f"{field} must contain exactly version, tags, collection_keys")
    version = value.get("version")
    if not isinstance(version, int) or version <= 0:
        raise ValueError(f"{field}.version must be a positive integer")
    return ItemSnapshot(
        version=version,
        tags=_string_array(value.get("tags"), f"{field}.tags"),
        collection_keys=_string_array(value.get("collection_keys"), f"{field}.collection_keys"),
    )


def load_plan(path: Path) -> MutationPlan:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    allowed_top = {
        "schema_version", "plan_id", "plan_kind", "source_packet_hash",
        "approval_status", "generated_at", "approved_at", "approval_note", "actions",
    }
    unexpected_top = sorted(set(raw) - allowed_top)
    if unexpected_top:
        raise ValueError("unexpected top-level mutation plan fields: " + ", ".join(unexpected_top))
    if raw.get("schema_version") != 1:
        raise ValueError("mutation plan schema_version must be 1")
    plan_id = str(raw.get("plan_id") or "").strip()
    plan_kind = str(raw.get("plan_kind") or "").strip()
    source_packet_hash = str(raw.get("source_packet_hash") or "").strip().lower()
    approval_status = str(raw.get("approval_status") or "pending").strip()
    if not plan_id or not plan_kind:
        raise ValueError("plan_id and plan_kind are required")
    if len(source_packet_hash) != 64 or any(char not in "0123456789abcdef" for char in source_packet_hash):
        raise ValueError("source_packet_hash must be a 64-character lowercase SHA-256 digest")
    if approval_status not in {"pending", "approved", "rejected"}:
        raise ValueError("approval_status must be pending, approved, or rejected")
    action_rows = raw.get("actions")
    if not isinstance(action_rows, list) or not action_rows:
        raise ValueError("actions must be a non-empty array")
    actions: list[MutationAction] = []
    keys: set[str] = set()
    for index, row in enumerate(action_rows):
        if not isinstance(row, dict):
            raise ValueError(f"actions[{index}] must be an object")
        if set(row) != {"item_key", "expected_before", "mutation", "expected_after", "evidence_refs"}:
            raise ValueError(f"actions[{index}] fields do not match the canonical mutation schema")
        item_key = str(row.get("item_key") or "").strip().upper()
        if not item_key or item_key in keys:
            raise ValueError(f"actions[{index}].item_key is missing or duplicated")
        keys.add(item_key)
        mutation = row.get("mutation")
        if not isinstance(mutation, dict):
            raise ValueError(f"actions[{index}].mutation must be an object")
        if set(mutation) != {"add_tags", "remove_tags", "add_collection_paths", "remove_collection_paths"}:
            raise ValueError(f"actions[{index}].mutation fields do not match the canonical mutation schema")
        expected_after = row.get("expected_after")
        if not isinstance(expected_after, dict):
            raise ValueError(f"actions[{index}].expected_after must be an object")
        if set(expected_after) != {"tags", "collection_keys"}:
            raise ValueError(f"actions[{index}].expected_after must contain exactly tags and collection_keys")
        parsed_mutation = ItemMutation(
            add_tags=_string_array(mutation.get("add_tags"), f"actions[{index}].mutation.add_tags"),
            remove_tags=_string_array(mutation.get("remove_tags"), f"actions[{index}].mutation.remove_tags"),
            add_collection_paths=_string_array(mutation.get("add_collection_paths"), f"actions[{index}].mutation.add_collection_paths"),
            remove_collection_paths=_string_array(mutation.get("remove_collection_paths"), f"actions[{index}].mutation.remove_collection_paths"),
        )
        if not any((parsed_mutation.add_tags, parsed_mutation.remove_tags, parsed_mutation.add_collection_paths, parsed_mutation.remove_collection_paths)):
            raise ValueError(f"actions[{index}].mutation must contain at least one change")
        if set(parsed_mutation.add_tags) & set(parsed_mutation.remove_tags):
            raise ValueError(f"actions[{index}].mutation cannot add and remove the same tag")
        if set(parsed_mutation.add_collection_paths) & set(parsed_mutation.remove_collection_paths):
            raise ValueError(f"actions[{index}].mutation cannot add and remove the same collection path")
        actions.append(MutationAction(
            item_key=item_key,
            expected_before=_snapshot(row.get("expected_before"), f"actions[{index}].expected_before"),
            mutation=parsed_mutation,
            expected_after_tags=_string_array(expected_after.get("tags"), f"actions[{index}].expected_after.tags"),
            expected_after_collection_keys=_string_array(expected_after.get("collection_keys"), f"actions[{index}].expected_after.collection_keys"),
            evidence_refs=_string_array(row.get("evidence_refs", []), f"actions[{index}].evidence_refs"),
        ))
    return MutationPlan(plan_id, plan_kind, source_packet_hash, approval_status, tuple(actions), raw)


def plan_hash(plan: MutationPlan) -> str:
    canonical = json.dumps(plan.raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def snapshot_from_item(item: dict[str, Any]) -> ItemSnapshot:
    data = item.get("data", {})
    return ItemSnapshot(
        version=int(item.get("version") or data.get("version") or 0),
        tags=tuple(row["tag"] for row in data.get("tags", []) or [] if row.get("tag")),
        collection_keys=tuple(str(key) for key in data.get("collections", []) or [] if key),
    )


def snapshot_drift(expected: ItemSnapshot, live: ItemSnapshot) -> list[str]:
    drift: list[str] = []
    if expected.version != live.version:
        drift.append("version")
    if set(expected.tags) != set(live.tags):
        drift.append("tags")
    if set(expected.collection_keys) != set(live.collection_keys):
        drift.append("collections")
    return drift


def apply_mutation(
    before: ItemSnapshot,
    mutation: ItemMutation,
    key_by_path: dict[str, str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    missing_paths = [
        path for path in (*mutation.add_collection_paths, *mutation.remove_collection_paths)
        if path not in key_by_path
    ]
    if missing_paths:
        raise ValueError("unknown collection paths: " + ", ".join(missing_paths))
    remove_collection_keys = {key_by_path[path] for path in mutation.remove_collection_paths}
    add_collection_keys = [key_by_path[path] for path in mutation.add_collection_paths]
    tags: list[str] = []
    for tag in (*before.tags, *mutation.add_tags):
        if tag not in mutation.remove_tags and tag not in tags:
            tags.append(tag)
    collections: list[str] = []
    for key in (*before.collection_keys, *add_collection_keys):
        if key not in remove_collection_keys and key not in collections:
            collections.append(key)
    return tuple(tags), tuple(collections)
