"""Prepare Zotero governance evidence for the active ChatGPT/Codex agent.

This tool reads ResearchOS governance assets only. It does not read zotero.sqlite, write
to Zotero, move PDFs, modify Zotero tags/collections, or call a language-model API.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
    DOCS_LIBRARY_GOVERNANCE,
    M002_LIBRARY_GOVERNANCE,
)


DEFAULT_DB = CORPUS_ZOTERO_LIBRARY_DB
DEFAULT_HISTORY_PLAN = (
    Path(".researchos")
    / "outputs"
    / "archive"
    / "A-001-library-governance"
    / "legacy-library-governance"
    / "archives"
    / "20260625T142627-strict-title-abstract-zotero-tags"
    / "item_assignment_plan.csv"
)
DEFAULT_KEYWORDS_CSV = M002_LIBRARY_GOVERNANCE / "ai-governance-keyword-recovery.csv"
DEFAULT_KEYWORDS_JSON = M002_LIBRARY_GOVERNANCE / "ai-governance-keyword-recovery.json"
DEFAULT_CORPUS_JSONL = M002_LIBRARY_GOVERNANCE / "ai-governance-corpus.jsonl"
DEFAULT_CORPUS_CSV = M002_LIBRARY_GOVERNANCE / "ai-governance-corpus-preview.csv"
DEFAULT_AGENT_PACKET_JSONL = M002_LIBRARY_GOVERNANCE / "ai-governance-agent-packet.jsonl"
DEFAULT_AGENT_INSTRUCTIONS_MD = M002_LIBRARY_GOVERNANCE / "ai-governance-agent-instructions.md"
DEFAULT_SEMANTIC_RESULTS_JSONL = M002_LIBRARY_GOVERNANCE / "ai-governance-semantic-results.jsonl"
DEFAULT_CLASSIFICATION_PLAN_CSV = M002_LIBRARY_GOVERNANCE / "ai-governance-classification-plan.csv"
DEFAULT_CLASSIFICATION_PLAN_JSON = M002_LIBRARY_GOVERNANCE / "ai-governance-classification-plan.json"
DEFAULT_COLLECTION_PLAN_CSV = M002_LIBRARY_GOVERNANCE / "ai-governance-collection-plan.csv"
DEFAULT_COLLECTION_PLAN_JSON = M002_LIBRARY_GOVERNANCE / "ai-governance-collection-plan.json"
DEFAULT_CLASSIFICATION_REPORT = DOCS_LIBRARY_GOVERNANCE / "ai-governance-classification-plan-report.md"
DEFAULT_REPORT = DOCS_LIBRARY_GOVERNANCE / "ai-governance-preparation-report.md"
DEFAULT_NORMALIZED_ROOT = CORPUS_ZOTERO_FULLTEXT_NORMALIZED

GOVERNANCE_PREFIXES = (
    "#Domain/",
    "#Field/",
    "#Method/",
    "#Object/",
    "#Parameter/",
    "#Status/",
    "#Type/",
    "#Device/",
)
GOVERNANCE_EXACT = {"/unread"}
PROJECT_TAG_PATTERNS = (
    re.compile(r"^[A-Z]\."),
    re.compile(r"^\d+[.．]"),
)
CORPUS_FIELDS = [
    "item_key",
    "item_type",
    "title",
    "year",
    "date",
    "publication",
    "journal_abbreviation",
    "language",
    "doi_present",
    "isbn_present",
    "url_present",
    "abstract_present",
    "has_normalized_text",
    "normalized_text_statuses",
    "normalized_text_paths",
    "pdf_first_page_chars",
    "pdf_first_page_source",
    "pdf_first_page_text",
    "keywords_for_ai",
    "abstract_note",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def split_tags(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def is_keyword_candidate(tag: str) -> bool:
    if tag in GOVERNANCE_EXACT:
        return False
    if tag.startswith(GOVERNANCE_PREFIXES):
        return False
    if tag.startswith("#"):
        return False
    return not any(pattern.search(tag) for pattern in PROJECT_TAG_PATTERNS)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_keyword_recovery(path: Path) -> dict[str, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    return {
        str(item["item_key"]): list(item.get("keywords_for_ai", []))
        for item in items
        if item.get("item_key")
    }


def command_recover_keywords(args: argparse.Namespace) -> int:
    rows = list(csv.DictReader(Path(args.history_plan).open("r", encoding="utf-8-sig")))
    output_rows: list[dict[str, Any]] = []
    keyword_counter: Counter[str] = Counter()
    excluded_counter: Counter[str] = Counter()
    items_with_raw = 0
    items_with_keywords = 0

    for row in rows:
        raw_tags = split_tags(row.get("current_tags"))
        kept = [tag for tag in raw_tags if is_keyword_candidate(tag)]
        excluded = [tag for tag in raw_tags if not is_keyword_candidate(tag)]
        if raw_tags:
            items_with_raw += 1
        if kept:
            items_with_keywords += 1
        keyword_counter.update(kept)
        excluded_counter.update(excluded)
        output_rows.append(
            {
                "item_key": row.get("item_key", ""),
                "item_type": row.get("item_type", ""),
                "title": row.get("title", ""),
                "keywords_recovered_raw": raw_tags,
                "keywords_for_ai": kept,
                "excluded_keyword_like_tags": excluded,
                "keyword_source": "pre_20260625_current_tags_archive",
            }
        )

    csv_rows = [
        {
            "item_key": row["item_key"],
            "item_type": row["item_type"],
            "title": row["title"],
            "keywords_recovered_raw": "; ".join(row["keywords_recovered_raw"]),
            "keywords_for_ai": "; ".join(row["keywords_for_ai"]),
            "excluded_keyword_like_tags": "; ".join(row["excluded_keyword_like_tags"]),
            "keyword_source": row["keyword_source"],
        }
        for row in output_rows
    ]
    write_csv(
        Path(args.output_csv),
        csv_rows,
        [
            "item_key",
            "item_type",
            "title",
            "keywords_recovered_raw",
            "keywords_for_ai",
            "excluded_keyword_like_tags",
            "keyword_source",
        ],
    )
    write_json(
        Path(args.output_json),
        {
            "generated_at": utc_now(),
            "source_history_plan": str(Path(args.history_plan)),
            "items_total": len(output_rows),
            "items_with_raw_tags": items_with_raw,
            "items_with_keywords_for_ai": items_with_keywords,
            "unique_keywords_for_ai": len(keyword_counter),
            "unique_excluded_tags": len(excluded_counter),
            "filter_policy": {
                "excluded_prefixes": list(GOVERNANCE_PREFIXES),
                "excluded_exact": sorted(GOVERNANCE_EXACT),
                "exclude_all_hash_tags": True,
                "exclude_project_like_numbered_or_lettered_tags": True,
            },
            "top_keywords_for_ai": keyword_counter.most_common(100),
            "top_excluded_tags": excluded_counter.most_common(100),
            "items": output_rows,
        },
    )
    print(
        json.dumps(
            {
                "items_total": len(output_rows),
                "items_with_raw_tags": items_with_raw,
                "items_with_keywords_for_ai": items_with_keywords,
                "unique_keywords_for_ai": len(keyword_counter),
                "csv": str(args.output_csv),
                "json": str(args.output_json),
            },
            ensure_ascii=False,
        )
    )
    return 0


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def portable_researchos_path(path: Path | str | None) -> str:
    if not path:
        return ""
    resolved = Path(path).resolve()
    try:
        return "{RESEARCHOS_ROOT}/" + str(resolved.relative_to(RESEARCHOS_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return "{LOCAL_PATH}/" + resolved.name


def resolve_normalized_text_path(raw_path: str, normalized_root: Path, item_key: str, attachment_key: str) -> Path | None:
    candidates: list[Path] = []
    if raw_path:
        candidates.append(Path(raw_path))
    if item_key and attachment_key:
        candidates.append(normalized_root / f"{item_key}__{attachment_key}.txt")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def compact_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_first_page_text(text: str, max_chars: int) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    page_matches = list(re.finditer(r"^===== Page \d+ =====\s*$", text, flags=re.MULTILINE))
    if page_matches:
        first = page_matches[0]
        start = first.end()
        end = page_matches[1].start() if len(page_matches) > 1 else len(text)
        page_text = text[start:end]
    else:
        page_text = text
    return compact_whitespace(page_text)[:max_chars].rstrip()


def load_first_page_text(
    text_links: list[dict[str, Any]],
    normalized_root: Path,
    item_key: str,
    max_chars: int,
) -> tuple[str, str]:
    for link in text_links:
        if link.get("status") != "ok":
            continue
        path = resolve_normalized_text_path(
            str(link.get("text_normalized_cache_path") or ""),
            normalized_root,
            item_key,
            str(link.get("attachment_key") or ""),
        )
        if not path:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        first_page = extract_first_page_text(text, max_chars)
        if first_page:
            return first_page, portable_researchos_path(path)
    return "", ""


def command_prepare_corpus(args: argparse.Namespace) -> int:
    keywords = load_keyword_recovery(Path(args.keywords_json))
    normalized_root = Path(args.normalized_root)
    with connect_readonly(Path(args.db)) as connection:
        rows = connection.execute(
            """
            SELECT item_key, item_type, title, year, date, publication,
                   journal_abbreviation, doi, isbn, url, language, abstract_note
            FROM items
            WHERE COALESCE(zotero_deleted, 0) = 0
            ORDER BY item_key
            """
        ).fetchall()
        text_rows = connection.execute(
            """
            SELECT item_key, attachment_key, status, text_chars, text_normalized_cache_path
            FROM pdf_texts
            ORDER BY CASE status WHEN 'ok' THEN 0 WHEN 'needs_ocr' THEN 1 ELSE 2 END,
                     text_chars DESC
            """
        ).fetchall()

    corpus: list[dict[str, Any]] = []
    preview_rows: list[dict[str, Any]] = []
    type_counter: Counter[str] = Counter()
    with_abstract = 0
    with_keywords = 0
    with_first_page_text = 0
    text_by_item: dict[str, list[dict[str, Any]]] = {}
    for text_row in text_rows:
        item_key = str(text_row["item_key"] or "")
        if not item_key:
            continue
        text_by_item.setdefault(item_key, []).append(
            {
                "attachment_key": str(text_row["attachment_key"] or ""),
                "status": str(text_row["status"] or ""),
                "text_chars": int(text_row["text_chars"] or 0),
                "text_normalized_cache_path": str(text_row["text_normalized_cache_path"] or ""),
            }
        )

    for row in rows:
        item_keywords = keywords.get(str(row["item_key"]), [])
        text_links = text_by_item.get(str(row["item_key"]), [])
        ok_text_links = [link for link in text_links if link["status"] == "ok" and link["text_normalized_cache_path"]]
        abstract = str(row["abstract_note"] or "").strip()
        if abstract:
            with_abstract += 1
        if item_keywords:
            with_keywords += 1
        first_page_text, first_page_source = load_first_page_text(
            ok_text_links,
            normalized_root,
            str(row["item_key"] or ""),
            args.max_first_page_chars,
        )
        resolved_normalized_paths = [
            portable_researchos_path(path)
            for link in ok_text_links
            for path in [
                resolve_normalized_text_path(
                    str(link.get("text_normalized_cache_path") or ""),
                    normalized_root,
                    str(row["item_key"] or ""),
                    str(link.get("attachment_key") or ""),
                )
            ]
            if path
        ]
        if first_page_text:
            with_first_page_text += 1
        type_counter.update([str(row["item_type"] or "")])
        record = {
            "item_key": row["item_key"],
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
            "abstract_present": bool(abstract),
            "has_normalized_text": bool(ok_text_links),
            "normalized_text_statuses": [f"{link['attachment_key']}:{link['status']}" for link in text_links],
            "normalized_text_paths": resolved_normalized_paths,
            "pdf_first_page_chars": len(first_page_text),
            "pdf_first_page_source": first_page_source,
            "pdf_first_page_text": first_page_text,
            "keywords_for_ai": item_keywords,
            "abstract_note": abstract,
        }
        corpus.append(record)
        preview_rows.append(
            {
                **{field: record.get(field, "") for field in CORPUS_FIELDS},
                "doi_present": "yes" if record["doi_present"] else "no",
                "isbn_present": "yes" if record["isbn_present"] else "no",
                "url_present": "yes" if record["url_present"] else "no",
                "abstract_present": "yes" if record["abstract_present"] else "no",
                "has_normalized_text": "yes" if record["has_normalized_text"] else "no",
                "normalized_text_statuses": "; ".join(record["normalized_text_statuses"]),
                "normalized_text_paths": "; ".join(record["normalized_text_paths"]),
                "pdf_first_page_text": first_page_text,
                "keywords_for_ai": "; ".join(item_keywords),
            }
        )

    output_jsonl = Path(args.output_jsonl)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for record in corpus:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_csv(Path(args.preview_csv), preview_rows, CORPUS_FIELDS)
    write_report(
        Path(args.report),
        {
            "corpus_items": len(corpus),
            "items_with_abstract": with_abstract,
            "items_with_keywords_for_ai": with_keywords,
            "items_with_normalized_text": sum(1 for record in corpus if record["has_normalized_text"]),
            "items_with_pdf_first_page_text": with_first_page_text,
            "item_types": type_counter.most_common(),
            "corpus_jsonl": str(output_jsonl),
            "preview_csv": str(args.preview_csv),
            "keywords_json": str(args.keywords_json),
            "normalized_root": str(normalized_root),
            "max_first_page_chars": args.max_first_page_chars,
        },
    )
    print(
        json.dumps(
            {
                "corpus_items": len(corpus),
                "items_with_abstract": with_abstract,
                "items_with_keywords_for_ai": with_keywords,
                "items_with_normalized_text": sum(1 for record in corpus if record["has_normalized_text"]),
                "items_with_pdf_first_page_text": with_first_page_text,
                "jsonl": str(output_jsonl),
                "preview_csv": str(args.preview_csv),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


def write_report(path: Path, stats: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Governance Preparation Report",
        "",
        f"- Generated at: {utc_now()}",
        f"- Corpus items: {stats['corpus_items']}",
        f"- Items with abstract: {stats['items_with_abstract']}",
        f"- Items with recovered keywords for AI: {stats['items_with_keywords_for_ai']}",
        f"- Items with normalized PDF text links: {stats['items_with_normalized_text']}",
        f"- Items with PDF first-page text: {stats['items_with_pdf_first_page_text']}",
        f"- Normalized text root: `{stats['normalized_root']}`",
        f"- Max first-page chars per item: {stats['max_first_page_chars']}",
        f"- Corpus JSONL: `{stats['corpus_jsonl']}`",
        f"- Preview CSV: `{stats['preview_csv']}`",
        f"- Keyword recovery JSON: `{stats['keywords_json']}`",
        "",
        "## Input Isolation",
        "",
        "- Current Zotero collections are excluded from AI input.",
        "- Current Zotero tags are excluded from AI input.",
        "- Recovered keywords come only from the pre-20260625 `current_tags` archive after governance-tag filtering.",
        "- PDF first-page text is read from the normalized text parent document and included as semantic evidence.",
        "- Full normalized PDF text is not inlined; AI input carries availability/status/path links from the SQLite parent document.",
        "",
        "## Item Types",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in stats["item_types"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This preparation step does not write to Zotero.",
            "- This preparation step does not read or modify `zotero.sqlite`.",
            "- This preparation step does not move, copy, rename, or delete PDF files.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def classification_schema() -> dict[str, Any]:
    tag_array = {"type": "array", "items": {"type": "string"}, "maxItems": 8}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "item_key": {"type": "string"},
            "type_tag": {"type": "string"},
            "status_tags": tag_array,
            "method_tags": tag_array,
            "object_tags": tag_array,
            "parameter_tags": tag_array,
            "field_tags": tag_array,
            "domain_candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "abbr": {"type": "string"},
                        "zh": {"type": "string"},
                        "en": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["abbr", "zh", "en", "confidence"],
                },
                "minItems": 1,
                "maxItems": 3,
            },
            "collection_candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "level": {"type": "integer"},
                        "abbr": {"type": "string"},
                        "zh": {"type": "string"},
                        "en": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["level", "abbr", "zh", "en", "confidence", "reason"],
                },
                "minItems": 1,
                "maxItems": 2,
            },
            "needs_manual_review": {"type": "boolean"},
            "evidence": {"type": "string"},
        },
        "required": [
            "item_key",
            "type_tag",
            "status_tags",
            "method_tags",
            "object_tags",
            "parameter_tags",
            "field_tags",
            "domain_candidates",
            "collection_candidates",
            "needs_manual_review",
            "evidence",
        ],
    }


def system_prompt() -> str:
    return (
        "You classify Zotero research-library items for a building science and "
        "research-methods library. Use only the provided title, abstract, "
        "recovered original keywords, PDF first-page text, venue, year, language, and item type. "
        "Do not infer from any current Zotero collection or current Zotero tag. "
        "Domain and field are related but not identical: Domain is the broad collection family; "
        "Field is the fine-grained research topic tag. Do not output #Domain tags because "
        "domain is represented by collections. Tags must use these namespaces only: "
        "#Field/, #Method/, #Object/, #Parameter/, #Status/, #Type/. "
        "Each item may have at most two collection candidates. Prefer Chinese "
        "domain and collection names with concise English names and 2-5 letter uppercase abbreviations. "
        "Collection names will later be numbered as 编号.ABBR-中文-English. "
        "Mark needs_manual_review when title/abstract/keywords are insufficient or off-scope."
    )


def item_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_key": item.get("item_key", ""),
        "item_type": item.get("item_type", ""),
        "title": item.get("title", ""),
        "year": item.get("year", ""),
        "date": item.get("date", ""),
        "publication": item.get("publication", ""),
        "journal_abbreviation": item.get("journal_abbreviation", ""),
        "language": item.get("language", ""),
        "doi_present": item.get("doi_present", False),
        "isbn_present": item.get("isbn_present", False),
        "url_present": item.get("url_present", False),
        "has_normalized_text": item.get("has_normalized_text", False),
        "normalized_text_statuses": item.get("normalized_text_statuses", []),
        "normalized_text_paths": item.get("normalized_text_paths", []),
        "pdf_first_page_text": item.get("pdf_first_page_text", ""),
        "keywords_for_ai": item.get("keywords_for_ai", []),
        "abstract_note": item.get("abstract_note", ""),
    }


def command_build_agent_packet(args: argparse.Namespace) -> int:
    """Build bounded evidence records for the active agent without any model API call."""
    schema = classification_schema()
    output = Path(args.output_jsonl)
    instructions = Path(args.instructions_md)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with Path(args.corpus_jsonl).open("r", encoding="utf-8") as source, output.open("w", encoding="utf-8", newline="\n") as target:
        for line in source:
            if not line.strip():
                continue
            item = json.loads(line)
            target.write(
                json.dumps(
                    {
                        "item_key": str(item["item_key"]),
                        "evidence": item_evidence(item),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            count += 1
            if args.limit and count >= args.limit:
                break
    instructions.parent.mkdir(parents=True, exist_ok=True)
    instructions.write_text(
        "# Zotero governance agent instructions\n\n"
        + system_prompt()
        + "\n\nRead each JSONL evidence record yourself. Return one plain classification JSON object per line; "
        "do not wrap results in an API response envelope. ResearchOS code must not call a language-model API.\n\n"
        "## Result schema\n\n```json\n"
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps({"items": count, "agent_packet": str(output), "instructions": str(instructions)}, ensure_ascii=False))
    return 0


def parse_agent_result_line(line: str) -> tuple[str, dict[str, Any] | None, str]:
    payload = json.loads(line)
    if not isinstance(payload, dict):
        return "", None, "result must be a JSON object"
    if "response" in payload or "custom_id" in payload:
        return str(payload.get("custom_id") or ""), None, "legacy model API response envelopes are not accepted"
    classification = payload.get("classification", payload)
    if not isinstance(classification, dict):
        return str(payload.get("item_key") or ""), None, "classification must be a JSON object"
    item_key = str(classification.get("item_key") or payload.get("item_key") or "").strip().upper()
    missing = [field for field in classification_schema()["required"] if field not in classification]
    if not item_key:
        missing.insert(0, "item_key")
    if missing:
        return item_key, None, "missing required fields: " + ", ".join(dict.fromkeys(missing))
    return item_key, classification, ""


def normalize_tag_list(values: Any, prefix: str, max_items: int = 8) -> list[str]:
    tags: list[str] = []
    for value in values or []:
        tag = str(value or "").strip()
        if not tag:
            continue
        if not tag.startswith(prefix):
            tag = prefix + tag.lstrip("#/")
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= max_items:
            break
    return tags


def normalize_type_tag(value: Any) -> str:
    tag = str(value or "").strip()
    if not tag:
        return ""
    if not tag.startswith("#Type/"):
        tag = "#Type/" + tag.lstrip("#/")
    return tag


def collection_identity(candidate: dict[str, Any]) -> tuple[str, str, str]:
    abbr = re.sub(r"[^A-Z0-9]", "", str(candidate.get("abbr") or "").upper())[:8] or "UNK"
    zh = str(candidate.get("zh") or "").strip() or "未命名"
    en = re.sub(r"\s+", " ", str(candidate.get("en") or "").strip()) or "Unnamed"
    return abbr, zh, en


def collection_display_name(index: int, abbr: str, zh: str, en: str) -> str:
    return f"{index:02d}.{abbr}-{zh}-{en}"


def command_build_plan(args: argparse.Namespace) -> int:
    item_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    collection_counter: Counter[tuple[str, str, str]] = Counter()
    collection_confidence: dict[tuple[str, str, str], list[float]] = {}

    for raw_line in Path(args.results_jsonl).read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        item_key, classification, error = parse_agent_result_line(raw_line)
        if error or classification is None:
            errors.append({"item_key": item_key, "error": error})
            continue
        candidates = list(classification.get("collection_candidates") or [])[:2]
        collection_keys: list[tuple[str, str, str]] = []
        for candidate in candidates:
            key = collection_identity(candidate)
            collection_keys.append(key)
            collection_counter.update([key])
            collection_confidence.setdefault(key, []).append(float(candidate.get("confidence") or 0))
        tags = []
        tags.extend(normalize_tag_list(classification.get("field_tags"), "#Field/"))
        tags.extend(normalize_tag_list(classification.get("method_tags"), "#Method/"))
        tags.extend(normalize_tag_list(classification.get("object_tags"), "#Object/"))
        tags.extend(normalize_tag_list(classification.get("parameter_tags"), "#Parameter/"))
        tags.extend(normalize_tag_list(classification.get("status_tags"), "#Status/"))
        type_tag = normalize_type_tag(classification.get("type_tag"))
        if type_tag:
            tags.append(type_tag)
        deduped_tags = list(dict.fromkeys(tags))
        item_rows.append(
            {
                "item_key": item_key or str(classification.get("item_key") or ""),
                "proposed_tags": deduped_tags,
                "collection_identities": ["|".join(key) for key in collection_keys],
                "needs_manual_review": bool(classification.get("needs_manual_review")),
                "evidence": str(classification.get("evidence") or ""),
                "raw_classification": classification,
            }
        )

    collection_index: dict[tuple[str, str, str], str] = {}
    collection_rows: list[dict[str, Any]] = []
    for index, (key, count) in enumerate(collection_counter.most_common(), start=1):
        abbr, zh, en = key
        display_name = collection_display_name(index, abbr, zh, en)
        collection_index[key] = display_name
        confidences = collection_confidence.get(key, [])
        collection_rows.append(
            {
                "collection_name": display_name,
                "abbr": abbr,
                "zh": zh,
                "en": en,
                "item_count": count,
                "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0,
            }
        )

    plan_rows: list[dict[str, Any]] = []
    for row in item_rows:
        collection_names = []
        for identity in row["collection_identities"][:2]:
            parts = identity.split("|", 2)
            if len(parts) == 3:
                collection_names.append(collection_index.get((parts[0], parts[1], parts[2]), ""))
        plan_rows.append(
            {
                "item_key": row["item_key"],
                "proposed_tags": "; ".join(row["proposed_tags"]),
                "proposed_collections": "; ".join(name for name in collection_names if name),
                "needs_manual_review": "yes" if row["needs_manual_review"] else "no",
                "evidence": row["evidence"],
            }
        )

    write_csv(Path(args.output_csv), plan_rows, ["item_key", "proposed_tags", "proposed_collections", "needs_manual_review", "evidence"])
    write_csv(Path(args.collection_csv), collection_rows, ["collection_name", "abbr", "zh", "en", "item_count", "mean_confidence"])
    write_json(
        Path(args.output_json),
        {
            "generated_at": utc_now(),
            "source_agent_results": str(args.results_jsonl),
            "items": item_rows,
            "errors": errors,
        },
    )
    write_json(
        Path(args.collection_json),
        {
            "generated_at": utc_now(),
            "source_agent_results": str(args.results_jsonl),
            "collections": collection_rows,
        },
    )
    write_classification_report(
        Path(args.report),
        {
            "items": len(item_rows),
            "errors": len(errors),
            "collections": len(collection_rows),
            "manual_review": sum(1 for row in item_rows if row["needs_manual_review"]),
            "output_csv": str(args.output_csv),
            "output_json": str(args.output_json),
            "collection_csv": str(args.collection_csv),
            "collection_json": str(args.collection_json),
        },
    )
    print(
        json.dumps(
            {
                "items": len(item_rows),
                "errors": len(errors),
                "collections": len(collection_rows),
                "manual_review": sum(1 for row in item_rows if row["needs_manual_review"]),
                "output_csv": str(args.output_csv),
                "collection_csv": str(args.collection_csv),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


def write_classification_report(path: Path, stats: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Governance Classification Plan Report",
        "",
        f"- Generated at: {utc_now()}",
        f"- Classified items: {stats['items']}",
        f"- Parse errors: {stats['errors']}",
        f"- Proposed collections: {stats['collections']}",
        f"- Items needing manual review: {stats['manual_review']}",
        f"- Item plan CSV: `{stats['output_csv']}`",
        f"- Item plan JSON: `{stats['output_json']}`",
        f"- Collection plan CSV: `{stats['collection_csv']}`",
        f"- Collection plan JSON: `{stats['collection_json']}`",
        "",
        "## Rules",
        "",
        "- Domain is represented as collection, not as `#Domain/` tag.",
        "- Field is represented as `#Field/` tag.",
        "- Each item is assigned to at most two proposed collections.",
        "- Collection names use `编号.ABBR-中文-English`.",
        "- This plan is read-only and requires human approval before any Zotero write stage.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    recover = subparsers.add_parser("recover-keywords", help="Recover original keyword-like tags from archived pre-governance tags.")
    recover.add_argument("--history-plan", default=str(DEFAULT_HISTORY_PLAN))
    recover.add_argument("--output-csv", default=str(DEFAULT_KEYWORDS_CSV))
    recover.add_argument("--output-json", default=str(DEFAULT_KEYWORDS_JSON))
    recover.set_defaults(func=command_recover_keywords)

    corpus = subparsers.add_parser("prepare-corpus", help="Build an agent evidence corpus from the read-only ResearchOS SQLite index.")
    corpus.add_argument("--db", default=str(DEFAULT_DB))
    corpus.add_argument("--normalized-root", default=str(DEFAULT_NORMALIZED_ROOT))
    corpus.add_argument("--max-first-page-chars", type=int, default=4000)
    corpus.add_argument("--keywords-json", default=str(DEFAULT_KEYWORDS_JSON))
    corpus.add_argument("--output-jsonl", default=str(DEFAULT_CORPUS_JSONL))
    corpus.add_argument("--preview-csv", default=str(DEFAULT_CORPUS_CSV))
    corpus.add_argument("--report", default=str(DEFAULT_REPORT))
    corpus.set_defaults(func=command_prepare_corpus)

    packet = subparsers.add_parser("build-agent-packet", help="Build bounded JSONL evidence for the active ChatGPT/Codex agent.")
    packet.add_argument("--corpus-jsonl", default=str(DEFAULT_CORPUS_JSONL))
    packet.add_argument("--output-jsonl", default=str(DEFAULT_AGENT_PACKET_JSONL))
    packet.add_argument("--instructions-md", default=str(DEFAULT_AGENT_INSTRUCTIONS_MD))
    packet.add_argument("--limit", type=int, default=None, help="Optional item limit for review batches.")
    packet.set_defaults(func=command_build_agent_packet)

    plan = subparsers.add_parser("build-plan", help="Validate agent classifications and build a read-only tag/collection plan.")
    plan.add_argument("--results-jsonl", "--batch-results-jsonl", dest="results_jsonl", default=str(DEFAULT_SEMANTIC_RESULTS_JSONL))
    plan.add_argument("--output-csv", default=str(DEFAULT_CLASSIFICATION_PLAN_CSV))
    plan.add_argument("--output-json", default=str(DEFAULT_CLASSIFICATION_PLAN_JSON))
    plan.add_argument("--collection-csv", default=str(DEFAULT_COLLECTION_PLAN_CSV))
    plan.add_argument("--collection-json", default=str(DEFAULT_COLLECTION_PLAN_JSON))
    plan.add_argument("--report", default=str(DEFAULT_CLASSIFICATION_REPORT))
    plan.set_defaults(func=command_build_plan)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
