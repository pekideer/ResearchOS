from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .contracts import TaskKind, result_schema, task_instructions


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def portable_path(path: Path | str | None, root: Path) -> str:
    if not path:
        return ""
    resolved = Path(path).resolve()
    try:
        return "{RESEARCHOS_ROOT}/" + str(resolved.relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return "{LOCAL_PATH}/" + resolved.name


def resolve_text_path(raw: str, normalized_root: Path, item_key: str, attachment_key: str) -> Path | None:
    candidates = [Path(raw)] if raw else []
    if item_key and attachment_key:
        candidates.append(normalized_root / f"{item_key}__{attachment_key}.txt")
    return next((path for path in candidates if path.exists()), None)


def first_page_text(text: str, max_chars: int) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    markers = list(re.finditer(r"^===== Page \d+ =====\s*$", normalized, flags=re.MULTILINE))
    if markers:
        start = markers[0].end()
        end = markers[1].start() if len(markers) > 1 else len(normalized)
        normalized = normalized[start:end]
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized[:max_chars].rstrip()


def _item_sql(item_keys: list[str] | None, query: str | None) -> tuple[str, list[Any]]:
    clauses = ["COALESCE(zotero_deleted, 0) = 0"]
    params: list[Any] = []
    if item_keys:
        keys = [str(key).strip().upper() for key in item_keys if str(key).strip()]
        clauses.append("item_key IN (" + ",".join("?" for _ in keys) + ")")
        params.extend(keys)
    if query:
        value = f"%{query.casefold()}%"
        clauses.append("(lower(item_key) LIKE ? OR lower(title) LIKE ? OR lower(abstract_note) LIKE ? OR lower(publication) LIKE ?)")
        params.extend([value] * 4)
    return " AND ".join(clauses), params


def build_records(
    db_path: Path,
    normalized_root: Path,
    root: Path,
    task: TaskKind,
    max_first_page_chars: int = 4000,
    max_text_chars: int = 0,
    item_keys: list[str] | None = None,
    query: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    where, params = _item_sql(item_keys, query)
    limit_sql = " LIMIT ?" if limit else ""
    if limit:
        params.append(limit)
    with connect_readonly(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT item_key, item_type, title, year, date, publication, journal_abbreviation,
                   doi, isbn, url, language, abstract_note, tags_json, collection_paths_json
            FROM items WHERE {where} ORDER BY item_key{limit_sql}
            """,
            params,
        ).fetchall()
        text_rows = connection.execute(
            """
            SELECT item_key, attachment_key, status, text_chars, text_normalized_cache_path
            FROM pdf_texts
            ORDER BY CASE status WHEN 'ok' THEN 0 WHEN 'needs_ocr' THEN 1 ELSE 2 END, text_chars DESC
            """
        ).fetchall()

    text_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in text_rows:
        text_by_item.setdefault(str(row["item_key"] or ""), []).append(dict(row))

    records: list[dict[str, Any]] = []
    for row in rows:
        item_key = str(row["item_key"] or "")
        links = text_by_item.get(item_key, [])
        paths: list[str] = []
        page_text = ""
        text_excerpt = ""
        statuses: list[str] = []
        for link in links:
            attachment_key = str(link.get("attachment_key") or "")
            status = str(link.get("status") or "")
            statuses.append(f"{attachment_key}:{status}")
            path = resolve_text_path(str(link.get("text_normalized_cache_path") or ""), normalized_root, item_key, attachment_key)
            if path and status == "ok":
                paths.append(portable_path(path, root))
                raw_text = path.read_text(encoding="utf-8-sig", errors="replace")
                if not page_text:
                    page_text = first_page_text(raw_text, max_first_page_chars)
                if max_text_chars and not text_excerpt:
                    text_excerpt = re.sub(r"\s+", " ", raw_text).strip()[:max_text_chars]
        semantic_evidence = {
            "item_type": row["item_type"] or "",
            "title": row["title"] or "",
            "year": row["year"] or "",
            "date": row["date"] or "",
            "publication": row["publication"] or "",
            "journal_abbreviation": row["journal_abbreviation"] or "",
            "language": row["language"] or "",
            "doi_present": bool(str(row["doi"] or "").strip()),
            "isbn_present": bool(str(row["isbn"] or "").strip()),
            "url_present": bool(str(row["url"] or "").strip()),
            "abstract_note": str(row["abstract_note"] or "").strip(),
            "has_normalized_text": bool(paths),
            "normalized_text_statuses": statuses,
            "normalized_text_paths": paths,
            "pdf_first_page_text": page_text,
            "normalized_text_excerpt": text_excerpt,
        }
        record: dict[str, Any] = {
            "item_key": item_key,
            "semantic_scope": "document_content_only" if task is TaskKind.CONTENT_TAGS else "library_structure",
            "selection_is_not_evidence": True,
            "semantic_evidence": semantic_evidence,
            "evidence_hash": canonical_hash(semantic_evidence),
        }
        if task is TaskKind.LIBRARY_STRUCTURE:
            record["current_state"] = {
                "tags": json.loads(row["tags_json"] or "[]"),
                "collection_paths": json.loads(row["collection_paths_json"] or "[]"),
            }
        records.append(record)
    return records


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_preview(path: Path, records: list[dict[str, Any]]) -> None:
    fields = ["item_key", "semantic_scope", "title", "year", "publication", "abstract_present", "has_normalized_text", "evidence_hash"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            evidence = record["semantic_evidence"]
            writer.writerow({
                "item_key": record["item_key"],
                "semantic_scope": record["semantic_scope"],
                "title": evidence["title"],
                "year": evidence["year"],
                "publication": evidence["publication"],
                "abstract_present": "yes" if evidence["abstract_note"] else "no",
                "has_normalized_text": "yes" if evidence["has_normalized_text"] else "no",
                "evidence_hash": record["evidence_hash"],
            })


def write_preparation_report(path: Path, task: TaskKind, records: list[dict[str, Any]], output_jsonl: Path) -> None:
    types = Counter(record["semantic_evidence"]["item_type"] for record in records)
    lines = [
        "# Zotero Governance Evidence Report", "", f"- Generated at: {utc_now()}",
        f"- Task: `{task.value}`", f"- Records: {len(records)}", f"- JSONL: `{output_jsonl}`", "",
        "## Evidence boundary", "",
        "- Selection scope chooses item keys and is not semantic evidence.",
        "- Content-tag packets physically exclude current tags, collections, project routes, importance, and planned use.",
        "- Historical Zotero tags are not recovered as AI keywords.", "", "## Item types", "",
    ]
    lines.extend(f"- {name or '[unknown]'}: {count}" for name, count in types.most_common())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_agent_packet(corpus_path: Path, packet_path: Path, instructions_path: Path, task: TaskKind, limit: int | None = None) -> int:
    records: list[dict[str, Any]] = []
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("semantic_scope") != ("document_content_only" if task is TaskKind.CONTENT_TAGS else "library_structure"):
            raise ValueError("corpus semantic scope does not match requested task")
        if task is TaskKind.CONTENT_TAGS and "current_state" in record:
            raise ValueError("content-tag corpus contains operational context")
        records.append(record)
        if limit and len(records) >= limit:
            break
    write_jsonl(packet_path, records)
    instructions_path.parent.mkdir(parents=True, exist_ok=True)
    instructions_path.write_text(
        "# Zotero governance agent instructions\n\n" + task_instructions(task)
        + "\n\n## Result schema\n\n```json\n"
        + json.dumps(result_schema(task), ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return len(records)
