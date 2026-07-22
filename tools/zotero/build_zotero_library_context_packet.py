"""Build Zotero context packets through the authoritative evidence profiles."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
    DOCS_LIBRARY_GOVERNANCE,
    M002_LIBRARY_GOVERNANCE,
)
from tools.zotero.governance.contracts import TaskKind
from tools.zotero.governance.evidence import build_records, write_jsonl


def default_output(profile: str, suffix: str, human: bool = False) -> Path:
    root = DOCS_LIBRARY_GOVERNANCE if human else M002_LIBRARY_GOVERNANCE
    return root / f"zotero-{profile}-context-packet.{suffix}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("content", "library"), default="content")
    parser.add_argument("--db", default=str(CORPUS_ZOTERO_LIBRARY_DB))
    parser.add_argument("--normalized-root", default=str(CORPUS_ZOTERO_FULLTEXT_NORMALIZED))
    parser.add_argument("--item-key", action="append")
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--include-text", action="store_true")
    parser.add_argument("--max-chars-per-item", type=int, default=12000)
    parser.add_argument("--output")
    parser.add_argument("--jsonl-output")
    parser.add_argument("--csv-output")
    return parser


def markdown_packet(records: list[dict], profile: str) -> str:
    lines = [
        "# Zotero Library Context Packet", "",
        f"- Evidence profile: `{profile}`", "- Source: ResearchOS Zotero parent document and normalized text.", "",
    ]
    for record in records:
        evidence = record["semantic_evidence"]
        lines.extend([
            f"## [{record['item_key']}](zotero://select/library/items/{record['item_key']})", "",
            f"- Title: {evidence['title'] or '?'}", f"- Year: {evidence['year'] or '?'}",
            f"- Publication: {evidence['publication'] or '?'}", f"- Evidence hash: `{record['evidence_hash']}`",
        ])
        if "current_state" in record:
            lines.extend([
                f"- Current tags: {', '.join(record['current_state']['tags']) or '[none]'}",
                f"- Current collections: {', '.join(record['current_state']['collection_paths']) or '[none]'}",
            ])
        lines.extend([
            "", "### Abstract", "", evidence["abstract_note"] or "[NO ABSTRACT]", "",
            "### Normalized text", "", evidence.get("normalized_text_excerpt") or evidence["pdf_first_page_text"] or "[NO NORMALIZED TEXT]", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def write_csv(path: Path, records: list[dict]) -> None:
    fields = ["item_key", "title", "year", "publication", "has_normalized_text", "evidence_hash"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            evidence = record["semantic_evidence"]
            writer.writerow({
                "item_key": record["item_key"], "title": evidence["title"], "year": evidence["year"],
                "publication": evidence["publication"], "has_normalized_text": evidence["has_normalized_text"],
                "evidence_hash": record["evidence_hash"],
            })


def main() -> int:
    args = build_parser().parse_args()
    task = TaskKind.CONTENT_TAGS if args.profile == "content" else TaskKind.LIBRARY_STRUCTURE
    records = build_records(
        db_path=Path(args.db), normalized_root=Path(args.normalized_root), root=RESEARCHOS_ROOT, task=task,
        max_first_page_chars=min(args.max_chars_per_item, 4000),
        max_text_chars=args.max_chars_per_item if args.include_text else 0,
        item_keys=args.item_key, query=args.query,
        limit=None if args.item_key else max(args.limit, 1),
    )
    output = Path(args.output) if args.output else default_output(args.profile, "md", human=True)
    jsonl_output = Path(args.jsonl_output) if args.jsonl_output else default_output(args.profile, "jsonl")
    csv_output = Path(args.csv_output) if args.csv_output else default_output(args.profile, "csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_packet(records, args.profile), encoding="utf-8")
    write_jsonl(jsonl_output, records)
    write_csv(csv_output, records)
    print(json.dumps({
        "profile": args.profile, "records": len(records), "output": str(output),
        "jsonl_output": str(jsonl_output), "csv_output": str(csv_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
