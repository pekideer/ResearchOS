"""Build PRISMA status outputs from a ResearchOS PRISMA records CSV.

The script treats ``prisma-records.csv`` and the folded reading-card metadata block as the
authoritative state. It never writes to Zotero. It only creates a dry-run tag
mirror plan that can later enter the Zotero write approval workflow.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from card_common import parse_metadata
from tools.runtime.project_write_guard import add_project_write_guard_args, require_discovered_project_write


READ_STATUS_TAGS = {
    "todo": "rs:read/todo",
    "skimmed": "rs:read/initial-card",
    "done": "rs:read/initial-card",
    "deep": "rs:read/deep-read",
}

IMPORTANCE_TAGS = {
    "core": "rs:priority/core",
    "high": "rs:priority/high",
    "normal": "rs:priority/normal",
    "low": "rs:priority/low",
}

PLANNED_USE_TAGS = {
    "review": "rs:use/review",
    "intro": "rs:use/intro",
    "background": "rs:use/background",
    "method": "rs:use/method",
    "discussion": "rs:use/discussion",
    "exclude": "rs:use/exclude",
}

CONFLICT_TAG_PREFIXES = ("rs:read/", "rs:priority/", "rs:use/")

REQUIRED_COLUMNS = {
    "Record ID",
    "Zotero Item Key",
    "Title",
    "Reading Card Path",
    "Reading Card Generated At",
    "Read Status",
    "Importance",
    "Planned Use",
    "PRISMA Stage",
    "Screening Decision",
    "Exclude Reason",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate PRISMA reminders, flow counts, and a dry-run Zotero tag "
            "mirror plan from prisma-records.csv."
        )
    )
    parser.add_argument(
        "--records",
        required=True,
        help="Path to prisma-records.csv.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for generated outputs. Defaults to the records file directory.",
    )
    parser.add_argument(
        "--reading-card-root",
        help=(
            "Base directory for relative Reading Card Path values. Defaults to "
            "the records file directory."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when validation reminders are generated.",
    )
    add_project_write_guard_args(parser)
    return parser


def normalize_scalar(value: str | None) -> str:
    return (value or "").strip().lower()


def raw_zotero_item_key(value: str | None) -> str:
    text = (value or "").strip().strip("'\"")
    patterns = [
        r"(?i)items/([A-Z0-9]{8})",
        r"\[([A-Z0-9]{8})\]\(zotero://select/library/items/[A-Z0-9]{8}\)",
        r"^([A-Z0-9]{8})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).upper()
    return text


def split_values(value: str | None) -> list[str]:
    text = normalize_scalar(value)
    if not text or text == "?":
        return []
    return [part.strip() for part in re.split(r"[;|,/]+", text) if part.strip()]


def maybe_list_from_frontmatter(value: str) -> list[str]:
    text = value.strip()
    if not text or text == "[]":
        return []
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("'\"") for part in inner.split(",") if part.strip()]
    return split_values(text)


def read_frontmatter(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}

    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return parse_machine_metadata(text)

    frontmatter: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[index + 1 :])
            machine = parse_machine_metadata(body)
            machine.update(frontmatter)
            return machine
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")
    return frontmatter


def parse_machine_metadata(body: str) -> dict[str, str]:
    return parse_metadata(body)


def resolve_card_path(raw_path: str, root: Path) -> Path | None:
    text = (raw_path or "").strip()
    if not text or text == "?":
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return root / candidate


def portable_path(path: Path, base: Path) -> str:
    resolved = path.resolve()
    for token, root in (("{OUTPUT_DIR}", base.resolve()), ("{CWD}", Path.cwd().resolve())):
        try:
            return token + "/" + str(resolved.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
    return "{LOCAL_PATH}/" + resolved.name


def validate_columns(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise ValueError("prisma-records.csv 没有表头。")
    missing = sorted(REQUIRED_COLUMNS.difference(fieldnames))
    if missing:
        raise ValueError("prisma-records.csv 缺少必要字段：" + ", ".join(missing))


def build_tags(row: dict[str, str]) -> tuple[list[str], list[str]]:
    tags: list[str] = []
    warnings: list[str] = []

    read_status = normalize_scalar(row.get("Read Status"))
    if read_status and read_status != "?":
        tag = READ_STATUS_TAGS.get(read_status)
        if tag:
            tags.append(tag)
        else:
            warnings.append(f"unknown Read Status: {read_status}")

    importance = normalize_scalar(row.get("Importance"))
    if importance and importance != "?":
        tag = IMPORTANCE_TAGS.get(importance)
        if tag:
            tags.append(tag)
        else:
            warnings.append(f"unknown Importance: {importance}")

    for planned_use in split_values(row.get("Planned Use")):
        tag = PLANNED_USE_TAGS.get(planned_use)
        if tag:
            tags.append(tag)
        else:
            warnings.append(f"unknown Planned Use: {planned_use}")

    return sorted(set(tags)), warnings


def reminder(
    reminders: list[dict[str, str]],
    row: dict[str, str],
    severity: str,
    message: str,
) -> None:
    reminders.append(
        {
            "Record ID": row.get("Record ID", ""),
            "Zotero Item Key": row.get("Zotero Item Key", ""),
            "Severity": severity,
            "Message": message,
        }
    )


def compare_frontmatter(
    row: dict[str, str],
    card_frontmatter: dict[str, str],
    reminders: list[dict[str, str]],
) -> None:
    if not card_frontmatter:
        return

    pairs = [
        ("zotero_item_key", "Zotero Item Key"),
        ("generated_at", "Reading Card Generated At"),
        ("read_status", "Read Status"),
        ("importance", "Importance"),
    ]
    for fm_key, csv_key in pairs:
        if fm_key == "zotero_item_key":
            fm_value = raw_zotero_item_key(card_frontmatter.get(fm_key)).lower()
            csv_value = raw_zotero_item_key(row.get(csv_key)).lower()
        else:
            fm_value = normalize_scalar(card_frontmatter.get(fm_key))
            csv_value = normalize_scalar(row.get(csv_key))
        if fm_value and csv_value and fm_value != csv_value:
            reminder(
                reminders,
                row,
                "warning",
                f"reading card metadata {fm_key} differs from CSV {csv_key}",
            )

    fm_use = sorted(maybe_list_from_frontmatter(card_frontmatter.get("planned_use", "")))
    csv_use = sorted(split_values(row.get("Planned Use")))
    if fm_use and csv_use and fm_use != csv_use:
        reminder(
            reminders,
            row,
            "warning",
            "reading card metadata planned_use differs from CSV Planned Use",
        )


def flow_counts(rows: list[dict[str, str]]) -> dict[str, Any]:
    stage_counts = Counter(normalize_scalar(row.get("PRISMA Stage")) or "unknown" for row in rows)
    decision_counts = Counter(
        normalize_scalar(row.get("Screening Decision")) or "unknown" for row in rows
    )
    exclusion_counts = Counter(
        normalize_scalar(row.get("Exclude Reason")) or "unspecified"
        for row in rows
        if normalize_scalar(row.get("Screening Decision")) in {"exclude", "excluded"}
    )
    duplicate_groups = {
        normalize_scalar(row.get("Duplicate Group ID"))
        for row in rows
        if normalize_scalar(row.get("Duplicate Group ID")) not in {"", "?"}
    }

    return {
        "total_records": len(rows),
        "stage_counts": dict(sorted(stage_counts.items())),
        "screening_decision_counts": dict(sorted(decision_counts.items())),
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "duplicate_group_count": len(duplicate_groups),
        "records_with_zotero_item_key": sum(
            1 for row in rows if normalize_scalar(row.get("Zotero Item Key")) not in {"", "?"}
        ),
        "records_with_reading_card": sum(
            1 for row in rows if normalize_scalar(row.get("Reading Card Path")) not in {"", "?"}
        ),
    }


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = build_parser().parse_args()
    records_path = Path(args.records).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else records_path.parent
    card_root = (
        Path(args.reading_card_root).expanduser().resolve()
        if args.reading_card_root
        else records_path.parent
    )
    require_discovered_project_write(
        [output_dir],
        agent_root=args.agent_root,
        corpus_root=args.corpus_root,
        role_config=args.role_config,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    with records_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_columns(reader.fieldnames)
        rows = list(reader)

    reminders: list[dict[str, str]] = []
    actions: list[dict[str, Any]] = []

    for row in rows:
        record_id = row.get("Record ID", "").strip()
        item_key = raw_zotero_item_key(row.get("Zotero Item Key", ""))

        if not record_id or record_id == "?":
            reminder(reminders, row, "error", "missing Record ID")
        if not item_key or item_key == "?":
            reminder(reminders, row, "warning", "missing Zotero Item Key; Zotero tag mirror skipped")
        if normalize_scalar(row.get("Read Status")) in {"", "?"}:
            reminder(reminders, row, "warning", "missing Read Status")
        if normalize_scalar(row.get("Importance")) in {"", "?"}:
            reminder(reminders, row, "warning", "missing Importance")
        if not split_values(row.get("Planned Use")):
            reminder(reminders, row, "info", "missing Planned Use")
        if normalize_scalar(row.get("Reading Card Generated At")) in {"", "?"}:
            reminder(reminders, row, "info", "missing Reading Card Generated At")

        if normalize_scalar(row.get("Screening Decision")) in {"exclude", "excluded"} and normalize_scalar(
            row.get("Exclude Reason")
        ) in {"", "?"}:
            reminder(reminders, row, "warning", "excluded record missing Exclude Reason")

        card_path = resolve_card_path(row.get("Reading Card Path", ""), card_root)
        if card_path:
            card_frontmatter = read_frontmatter(card_path)
            if not card_frontmatter:
                reminder(
                    reminders,
                    row,
                    "warning",
                    f"reading card missing or has no metadata block: {card_path}",
                )
            else:
                compare_frontmatter(row, card_frontmatter, reminders)

        ensure_tags, tag_warnings = build_tags(row)
        for warning in tag_warnings:
            reminder(reminders, row, "warning", warning)

        if item_key and item_key != "?" and ensure_tags:
            actions.append(
                {
                    "action": "mirror_researchos_tags",
                    "zotero_item_key": item_key,
                    "record_id": record_id,
                    "title": row.get("Title", ""),
                    "ensure_tags": ensure_tags,
                    "remove_conflicting_tag_prefixes": list(CONFLICT_TAG_PREFIXES),
                    "source_fields": {
                        "read_status": row.get("Read Status", ""),
                        "importance": row.get("Importance", ""),
                        "planned_use": row.get("Planned Use", ""),
                    },
                }
            )

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    source_records = portable_path(records_path, output_dir)
    tag_plan = {
        "plan_type": "zotero_tag_mirror",
        "generated_at": generated_at,
        "source_records": source_records,
        "write_policy": "dry-run only; execute writes via POLICIES/ZOTERO_WRITE_POLICY.md",
        "authoritative_state": [
            "prisma-records.csv",
            "reading card tail metadata",
        ],
        "zotero_mirror_scope": {
            "allowed_tag_prefixes": list(CONFLICT_TAG_PREFIXES),
            "read_status_tags": READ_STATUS_TAGS,
            "importance_tags": IMPORTANCE_TAGS,
            "planned_use_tags": PLANNED_USE_TAGS,
        },
        "actions": actions,
    }

    counts = flow_counts(rows)
    counts["generated_at"] = generated_at
    counts["source_records"] = source_records

    reminders_path = output_dir / "prisma-reminders.csv"
    counts_path = output_dir / "prisma-flow-counts.json"
    plan_path = output_dir / "zotero-tag-mirror-plan.json"

    write_csv(reminders_path, reminders, ["Record ID", "Zotero Item Key", "Severity", "Message"])
    counts_path.write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan_path.write_text(json.dumps(tag_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("ResearchOS PRISMA status outputs")
    print(f"records: {records_path}")
    print(f"reminders: {reminders_path}")
    print(f"flow_counts: {counts_path}")
    print(f"zotero_tag_mirror_plan: {plan_path}")
    print(f"rows: {len(rows)}")
    print(f"tag_actions: {len(actions)}")
    print(f"reminders_count: {len(reminders)}")

    if args.strict and reminders:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
