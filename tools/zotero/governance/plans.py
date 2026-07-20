from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.researchos_outputs import write_json

from .contracts import CONTENT_NAMESPACES, TaskKind, validate_result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_tags(values: Any, prefix: str, maximum: int = 8) -> list[str]:
    tags: list[str] = []
    for value in values or []:
        tag = str(value or "").strip()
        if not tag:
            continue
        if not tag.startswith(prefix):
            raise ValueError(f"tag {tag!r} is outside namespace {prefix}")
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= maximum:
            break
    return tags


def _collection_identity(candidate: dict[str, Any]) -> tuple[str, str, str]:
    abbr = re.sub(r"[^A-Z0-9]", "", str(candidate.get("abbr") or "").upper())[:8] or "UNK"
    zh = str(candidate.get("zh") or "").strip() or "未命名"
    en = re.sub(r"\s+", " ", str(candidate.get("en") or "").strip()) or "Unnamed"
    return abbr, zh, en


def build_plan(task: TaskKind, results_path: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    collection_counter: Counter[tuple[str, str, str]] = Counter()
    parsed_rows: list[tuple[str, dict[str, Any]]] = []
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item_key, result, error = validate_result(task, json.loads(line))
        if error or result is None:
            errors.append({"item_key": item_key, "error": error})
            continue
        parsed_rows.append((item_key, result))
        if task is TaskKind.LIBRARY_STRUCTURE:
            collection_counter.update(_collection_identity(row) for row in result.get("collection_candidates") or [])

    collection_names = {
        identity: f"{index:02d}.{identity[0]}-{identity[1]}-{identity[2]}"
        for index, (identity, _count) in enumerate(collection_counter.most_common(), start=1)
    }
    for item_key, result in parsed_rows:
        if task is TaskKind.CONTENT_TAGS:
            tags: list[str] = []
            type_tag = str(result.get("type_tag") or "").strip()
            if type_tag:
                tags.extend(_normalize_tags([type_tag], CONTENT_NAMESPACES["type_tag"], 1))
            for field in ("status_tags", "method_tags", "object_tags", "parameter_tags", "field_tags"):
                tags.extend(_normalize_tags(result.get(field), CONTENT_NAMESPACES[field]))
            item = {
                "item_key": item_key,
                "evidence_hash": result["evidence_hash"],
                "proposed_content_tags": list(dict.fromkeys(tags)),
                "needs_manual_review": bool(result["needs_manual_review"]),
                "evidence": str(result["evidence"]),
            }
        else:
            candidates = [_collection_identity(row) for row in result.get("collection_candidates") or []]
            item = {
                "item_key": item_key,
                "evidence_hash": result["evidence_hash"],
                "proposed_collections": [collection_names[value] for value in candidates if value in collection_names],
                "domain_candidates": result.get("domain_candidates") or [],
                "needs_manual_review": bool(result["needs_manual_review"]),
                "evidence": str(result["evidence"]),
            }
        items.append(item)
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "task": task.value,
        "semantic_scope": "document_content_only" if task is TaskKind.CONTENT_TAGS else "library_structure",
        "source_agent_results": str(results_path),
        "source_results_hash": hashlib.sha256(results_path.read_bytes()).hexdigest(),
        "items": items,
        "errors": errors,
    }


def write_plan_outputs(plan: dict[str, Any], output_json: Path, output_csv: Path, report: Path) -> None:
    write_json(output_json, plan)
    task = TaskKind.parse(plan["task"])
    if task is TaskKind.CONTENT_TAGS:
        fields = ["item_key", "evidence_hash", "proposed_content_tags", "needs_manual_review", "evidence"]
    else:
        fields = ["item_key", "evidence_hash", "proposed_collections", "domain_candidates", "needs_manual_review", "evidence"]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in plan["items"]:
            row = dict(item)
            for field in fields:
                if isinstance(row.get(field), (list, dict)):
                    row[field] = json.dumps(row[field], ensure_ascii=False)
            writer.writerow({field: row.get(field, "") for field in fields})
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Zotero Governance Semantic Plan\n\n"
        f"- Task: `{plan['task']}`\n- Items: {len(plan['items'])}\n- Errors: {len(plan['errors'])}\n"
        "- This plan is read-only and requires a separately frozen mutation plan before Zotero write approval.\n",
        encoding="utf-8",
    )
