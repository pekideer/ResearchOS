"""Build context packets from the canonical ResearchOS Zotero library mirror.

The canonical sources are the synchronized SQLite index under
`corpus/zotero/M-001-zotero-library/` and normalized PDF text files under
`corpus/fulltext/zotero-library-normalized/`. `.researchos/outputs/machine/` is not a
canonical fact-source location.

This tool does not call Zotero, does not read zotero.sqlite, and does not read
PDF files. It only reads ResearchOS parent documents and writes compact packets.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[1]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
    DOCS_LIBRARY_GOVERNANCE,
    M002_LIBRARY_GOVERNANCE,
)
from tools.zotero_local_api import creators_to_text as creators_list_to_text


DEFAULT_DB = CORPUS_ZOTERO_LIBRARY_DB
DEFAULT_NORMALIZED_ROOT = CORPUS_ZOTERO_FULLTEXT_NORMALIZED
DEFAULT_OUTPUT = DOCS_LIBRARY_GOVERNANCE / "zotero-library-context-packet.md"
DEFAULT_JSONL_OUTPUT = M002_LIBRARY_GOVERNANCE / "zotero-library-context-packet.jsonl"
DEFAULT_CSV_OUTPUT = M002_LIBRARY_GOVERNANCE / "zotero-library-context-index.csv"


@dataclass
class TextLink:
    attachment_key: str
    status: str
    text_chars: int
    cache_path: str
    resolved_path: Path | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--normalized-root", default=str(DEFAULT_NORMALIZED_ROOT))
    parser.add_argument("--item-key", action="append", help="Limit to one or more Zotero top-level item keys.")
    parser.add_argument("--query", help="Case-insensitive search over title, abstract, publication, year, and item key.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--include-text", action="store_true", help="Include normalized text snippets in Markdown/JSONL output.")
    parser.add_argument("--max-chars-per-item", type=int, default=12000)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--jsonl-output", default=str(DEFAULT_JSONL_OUTPUT))
    parser.add_argument("--csv-output", default=str(DEFAULT_CSV_OUTPUT))
    return parser


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_key(value: str) -> str:
    return str(value or "").strip().upper()


def creators_json_to_text(value: str | None) -> str:
    try:
        creators = json.loads(value or "[]")
    except json.JSONDecodeError:
        return ""
    return creators_list_to_text(creators if isinstance(creators, list) else [])


def compact_text(text: str, max_chars: int) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text[:max_chars].rstrip()


def resolve_text_path(raw_path: str, normalized_root: Path, item_key: str, attachment_key: str) -> Path | None:
    candidates: list[Path] = []
    if raw_path:
        candidates.append(Path(raw_path))
    candidates.append(normalized_root / f"{item_key}__{attachment_key}.txt")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def item_query(args: argparse.Namespace) -> tuple[str, list[Any]]:
    clauses = ["COALESCE(i.zotero_deleted, 0) = 0"]
    params: list[Any] = []
    if args.item_key:
        keys = [normalize_key(key) for key in args.item_key]
        placeholders = ",".join("?" for _ in keys)
        clauses.append(f"i.item_key IN ({placeholders})")
        params.extend(keys)
    if args.query:
        pattern = f"%{args.query.casefold()}%"
        clauses.append(
            "(lower(i.item_key) LIKE ? OR lower(i.title) LIKE ? OR lower(i.abstract_note) LIKE ? "
            "OR lower(i.publication) LIKE ? OR lower(i.year) LIKE ?)"
        )
        params.extend([pattern] * 5)
    where = " AND ".join(clauses)
    limit = "" if args.item_key else " LIMIT ?"
    if not args.item_key:
        params.append(max(args.limit, 1))
    sql = f"""
        SELECT i.item_key, i.item_type, i.title, i.creators_json, i.year, i.date,
               i.publication, i.journal_abbreviation, i.doi, i.isbn, i.url,
               i.language, i.abstract_note, i.tags_json, i.collection_paths_json,
               i.date_added, i.date_modified
        FROM items i
        WHERE {where}
        ORDER BY i.year DESC, i.title COLLATE NOCASE
        {limit}
    """
    return sql, params


def load_text_links(connection: sqlite3.Connection, item_key: str, normalized_root: Path) -> list[TextLink]:
    rows = connection.execute(
        """
        SELECT attachment_key, status, text_chars, text_normalized_cache_path
        FROM pdf_texts
        WHERE item_key = ?
        ORDER BY CASE status WHEN 'ok' THEN 0 WHEN 'needs_ocr' THEN 1 ELSE 2 END,
                 text_chars DESC
        """,
        (item_key,),
    ).fetchall()
    links: list[TextLink] = []
    for row in rows:
        attachment_key = str(row["attachment_key"] or "")
        links.append(
            TextLink(
                attachment_key=attachment_key,
                status=str(row["status"] or ""),
                text_chars=int(row["text_chars"] or 0),
                cache_path=str(row["text_normalized_cache_path"] or ""),
                resolved_path=resolve_text_path(
                    str(row["text_normalized_cache_path"] or ""),
                    normalized_root,
                    item_key,
                    attachment_key,
                ),
            )
        )
    return links


def build_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    db_path = Path(args.db)
    normalized_root = Path(args.normalized_root)
    sql, params = item_query(args)
    records: list[dict[str, Any]] = []
    with connect_readonly(db_path) as connection:
        for row in connection.execute(sql, params):
            item_key = str(row["item_key"])
            text_links = load_text_links(connection, item_key, normalized_root)
            best_link = next((link for link in text_links if link.status == "ok" and link.resolved_path), None)
            packet_text = ""
            if args.include_text and best_link and best_link.resolved_path:
                packet_text = compact_text(best_link.resolved_path.read_text(encoding="utf-8-sig", errors="replace"), args.max_chars_per_item)
            tags = json.loads(row["tags_json"] or "[]")
            collections = json.loads(row["collection_paths_json"] or "[]")
            records.append(
                {
                    "item_key": item_key,
                    "item_type": row["item_type"] or "",
                    "title": row["title"] or "",
                    "creators": creators_json_to_text(row["creators_json"]),
                    "year": row["year"] or "",
                    "date": row["date"] or "",
                    "publication": row["publication"] or "",
                    "journal_abbreviation": row["journal_abbreviation"] or "",
                    "doi": row["doi"] or "",
                    "isbn": row["isbn"] or "",
                    "url": row["url"] or "",
                    "language": row["language"] or "",
                    "abstract_note": row["abstract_note"] or "",
                    "tags": tags,
                    "collection_paths": collections,
                    "date_added": row["date_added"] or "",
                    "date_modified": row["date_modified"] or "",
                    "normalized_text_statuses": "; ".join(f"{link.attachment_key}:{link.status}" for link in text_links),
                    "normalized_text_paths": "; ".join(str(link.resolved_path or link.cache_path) for link in text_links if link.resolved_path or link.cache_path),
                    "has_normalized_text": bool(best_link),
                    "text_scope": f"normalized library text truncated to {args.max_chars_per_item} chars" if packet_text else "",
                    "packet_text": packet_text,
                }
            )
    return records


def markdown_packet(records: list[dict[str, Any]], args: argparse.Namespace) -> str:
    lines = [
        "# Zotero Library Context Packet",
        "",
        "Source of truth: ResearchOS Zotero SQLite mirror plus normalized PDF text cache.",
        "",
        f"- SQLite: `{args.db}`",
        f"- Normalized text root: `{args.normalized_root}`",
        f"- Include text: `{bool(args.include_text)}`",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"## [{record['item_key']}](zotero://select/library/items/{record['item_key']})",
                "",
                f"- Title: {record['title'] or '?'}",
                f"- Type/year: {record['item_type'] or '?'} / {record['year'] or '?'}",
                f"- Creators: {record['creators'] or '?'}",
                f"- Publication: {record['publication'] or '?'}",
                f"- DOI: {record['doi'] or '?'}",
                f"- Normalized text: {'yes' if record['has_normalized_text'] else 'no'}",
                f"- Text statuses: {record['normalized_text_statuses'] or '?'}",
                f"- Text paths: `{record['normalized_text_paths'] or '?'}`",
                "",
                "### Abstract",
                "",
                record["abstract_note"] or "[NO ABSTRACT]",
                "",
            ]
        )
        if args.include_text:
            lines.extend(
                [
                    "### Normalized Text Snippet",
                    "",
                    "```text",
                    record["packet_text"] or "[NO NORMALIZED TEXT]",
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(records: list[dict[str, Any]], args: argparse.Namespace) -> None:
    output = Path(args.output)
    jsonl_output = Path(args.jsonl_output)
    csv_output = Path(args.csv_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    jsonl_output.parent.mkdir(parents=True, exist_ok=True)
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_packet(records, args), encoding="utf-8")
    jsonl_output.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )
    fields = [
        "item_key",
        "item_type",
        "title",
        "year",
        "publication",
        "doi",
        "has_normalized_text",
        "normalized_text_statuses",
        "normalized_text_paths",
    ]
    with csv_output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def main() -> int:
    args = build_parser().parse_args()
    records = build_records(args)
    write_outputs(records, args)
    print("ResearchOS Zotero library context packet")
    print(f"records: {len(records)}")
    print(f"with_normalized_text: {sum(1 for record in records if record['has_normalized_text'])}")
    print(f"output: {args.output}")
    print(f"jsonl_output: {args.jsonl_output}")
    print(f"csv_output: {args.csv_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
