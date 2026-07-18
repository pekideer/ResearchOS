"""Build resumable ResearchOS reading assets from the Zotero parent SQLite.

The pipeline is local-only: it never writes Zotero, never opens ``zotero.sqlite``
and never changes PDF files. Existing human-edited reading cards are preserved;
new cards are deliberately conservative screening cards without project section 6.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.reading_cards.card_common import (  # noqa: E402
    AFFILIATION_FINAL_STATUSES,
    RANK_ORDER,
    affiliation_publish_blockers,
    content_sha256,
    known,
    normalized_affiliation_status,
    parse_frontmatter,
    parse_metadata,
    parse_publication_tags,
    reading_card_identity,
    reading_card_project_links,
    yaml_scalar,
)
from tools.reading_cards.sync_first_author_affiliations import candidate_affiliation, set_metadata  # noqa: E402
from tools.reading_cards.sync_journal_rankings import normalize_journal_name  # noqa: E402
from tools.researchos_outputs import (  # noqa: E402
    CORPUS_READING_CARDS_ROOT,
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
    M006_ZOTERO_INGESTION_PIPELINE,
)
from tools.zotero.zotero_library_index import ZoteroClient, acquire_writer_lock, release_writer_lock  # noqa: E402


CARDS_ROOT = CORPUS_READING_CARDS_ROOT / "cards"
INDEX_PATH = CORPUS_READING_CARDS_ROOT / "indexes" / "reading-card-master-index.md"
AFFILIATION_INDEX_PATH = CORPUS_READING_CARDS_ROOT / "indexes" / "affiliation-dictionary.csv"
PIPELINE_VERSION = "2"
MISSING_DISPLAY = {"", "?", "？", "未填写", "unknown", "none", "null"}
SEMANTIC_RESULT_STATUSES = {
    "semantic_confirmed",
    "manual_confirmed",
    "semantic_needs_check",
    "semantic_not_found",
    "source_unavailable",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class FileWriteRollback:
    """Restore protected local files when a multi-asset update raises."""

    def __init__(self) -> None:
        self._originals: dict[Path, bytes | None] = {}

    def protect(self, path: Path) -> None:
        resolved = path.resolve()
        if resolved not in self._originals:
            self._originals[resolved] = resolved.read_bytes() if resolved.exists() else None

    def write_text(self, path: Path, text: str, encoding: str = "utf-8") -> None:
        self.protect(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)

    def restore(self) -> list[str]:
        errors: list[str] = []
        for path, original in reversed(list(self._originals.items())):
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(original)
            except OSError as exc:
                errors.append(f"{path}: {exc}")
        return errors


@contextmanager
def rollback_file_writes() -> Any:
    guard = FileWriteRollback()
    try:
        yield guard
    except BaseException as exc:
        restore_errors = guard.restore()
        if restore_errors:
            raise RuntimeError(
                "Local asset update failed and rollback was incomplete: " + "; ".join(restore_errors)
            ) from exc
        raise


def portable_path(value: str | Path) -> str:
    path = Path(value)
    try:
        return path.resolve().relative_to(RESEARCHOS_ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return str(value)


def machine_network_env(root: Path) -> tuple[dict[str, str], str]:
    """Load optional per-machine proxy settings without exposing their values."""
    env = dict(os.environ)
    source = "environment"
    config_path = root / ".local" / "machine_config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            config = {}
        proxy = config.get("proxy", {}) if isinstance(config, dict) else {}
        if isinstance(proxy, dict):
            for field, env_name in [
                ("http_proxy", "HTTP_PROXY"),
                ("https_proxy", "HTTPS_PROXY"),
                ("all_proxy", "ALL_PROXY"),
                ("no_proxy", "NO_PROXY"),
            ]:
                value = str(proxy.get(field) or "").strip()
                if value and not str(env.get(env_name) or env.get(env_name.lower()) or "").strip():
                    env[env_name] = value
                    source = "machine_config+environment"
    no_proxy_parts = [part.strip() for part in str(env.get("NO_PROXY") or env.get("no_proxy") or "").split(",") if part.strip()]
    for local_host in ("127.0.0.1", "localhost", "::1"):
        if local_host not in no_proxy_parts:
            no_proxy_parts.append(local_host)
    env["NO_PROXY"] = ",".join(no_proxy_parts)
    env["no_proxy"] = env["NO_PROXY"]
    return env, source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--researchos-root", type=Path, default=RESEARCHOS_ROOT)
    parser.add_argument("--db", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    process = sub.add_parser("process", help="Build affiliations, cards, index and pipeline state.")
    process.add_argument("--scope", choices=["all", "new"], default="new")
    process.add_argument("--item-key", action="append", default=[])
    process.add_argument("--limit", type=int)
    process.add_argument("--dry-run", action="store_true")
    process.add_argument("--force-lock", action="store_true")

    audit = sub.add_parser("audit", help="Report pipeline coverage without writes.")
    audit.add_argument("--item-key", action="append", default=[])
    audit.add_argument("--strict", action="store_true", help="Fail while cards or affiliation semantic review remain incomplete.")

    packet = sub.add_parser("semantic-packet", help="Build a bounded page-1..3 evidence packet for model/human review.")
    packet.add_argument("--scope", choices=["pending", "all"], default="pending")
    packet.add_argument("--item-key", action="append", default=[])
    packet.add_argument("--batch-size", type=int, default=20)
    packet.add_argument("--max-pages", type=int, default=3)
    packet.add_argument("--max-chars-per-item", type=int, default=12000)
    packet.add_argument("--output-dir", type=Path)

    apply_semantic = sub.add_parser("semantic-apply", help="Validate model/human affiliation JSONL and optionally write local assets.")
    apply_semantic.add_argument("--results", type=Path, required=True)
    apply_semantic.add_argument("--write-local", action="store_true")
    apply_semantic.add_argument("--max-pages", type=int, default=3)
    apply_semantic.add_argument("--max-chars-per-item", type=int, default=12000)
    apply_semantic.add_argument("--force-lock", action="store_true")

    run = sub.add_parser("run", help="Run incremental Zotero sync, normalization, dictionaries and cards.")
    run.add_argument("--scope", choices=["all", "new"], default="new")
    run.add_argument("--item-key", action="append", default=[])
    run.add_argument("--no-journal-api", action="store_true")
    run.add_argument("--skip-sync", action="store_true")
    run.add_argument("--limit", type=int)
    return parser


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    root = args.researchos_root.resolve()
    db = args.db.resolve() if args.db else (root / CORPUS_ZOTERO_LIBRARY_DB).resolve()
    cards_root = (root / CARDS_ROOT).resolve()
    index_path = (root / INDEX_PATH).resolve()
    return root, db, cards_root, index_path


def ensure_pipeline_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS library_pipeline_state (
            item_key TEXT PRIMARY KEY,
            item_version INTEGER NOT NULL DEFAULT 0,
            pipeline_version TEXT NOT NULL,
            text_status TEXT,
            affiliation_status TEXT,
            journal_status TEXT,
            card_status TEXT,
            card_path TEXT,
            processed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS affiliation_entities (
            canonical_id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            occurrence_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS affiliation_aliases (
            normalized_alias TEXT PRIMARY KEY,
            alias_raw TEXT NOT NULL,
            canonical_id TEXT NOT NULL,
            status TEXT NOT NULL,
            occurrence_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS item_affiliations (
            item_key TEXT PRIMARY KEY,
            canonical_id TEXT,
            affiliation_raw TEXT,
            affiliation_display TEXT,
            source TEXT,
            status TEXT NOT NULL,
            evidence_path TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )


def load_existing_cards(cards_root: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    if not cards_root.exists():
        return output
    for path in sorted(cards_root.glob("*.md")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        card_id, item_key = reading_card_identity(text, path)
        if not item_key:
            continue
        metadata = parse_metadata(text)
        frontmatter = parse_frontmatter(text)
        record = {
            "path": path,
            "text": text,
            "card_id": card_id,
            "metadata": metadata,
            "frontmatter": frontmatter,
            "project_links": reading_card_project_links(text),
        }
        current = output.get(item_key)
        if current is None or int(card_number(card_id)) < int(card_number(str(current["card_id"]))):
            output[item_key] = record
    return output


def card_number(card_id: str) -> int:
    match = re.search(r"(\d+)", card_id or "")
    return int(match.group(1)) if match else 10**9


def decode_json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def creator_names(creators_json: str) -> list[str]:
    creators = decode_json(creators_json, [])
    names: list[str] = []
    for creator in creators if isinstance(creators, list) else []:
        if not isinstance(creator, dict):
            continue
        name = str(creator.get("name") or "").strip()
        if not name:
            first = str(creator.get("firstName") or "").strip()
            last = str(creator.get("lastName") or "").strip()
            name = " ".join(part for part in [first, last] if part)
        if name:
            names.append(name)
    return names


def author_year_label(creators_json: str, year: str) -> str:
    names = creator_names(creators_json)
    author = names[0] if names else "无作者"
    if re.search(r"[\u4e00-\u9fff]", author):
        author = re.sub(r"\s+", "", author)[:8]
    else:
        author = re.split(r"\s+", author.strip())[-1][:18]
    return f"{author}({year or '无年份'})"


def safe_filename_part(value: str, max_length: int = 48) -> str:
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "", value)
    value = re.sub(r"\s+", "", value).strip(". ")
    return (value or "未命名")[:max_length]


def canonicalize_affiliation(raw: str) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", raw or "").strip(" ,;；。")
    text = re.sub(r"\b\S+@\S+\b", "", text).strip()
    chinese = re.findall(r"[\u4e00-\u9fffA-Za-z0-9·（）()\-]{2,45}?(?:大学|学院|研究院|研究所|医院|实验室|集团|公司)", text)
    english_patterns = [
        r"(?:[A-Z][A-Za-z&'.\-]*\s+){1,5}(?:University of (?:Science and )?Technology|University|Institute of Technology|Academy of Sciences|Research Institute|Hospital|Laborator(?:y|ies)|Corporation|Company)",
        r"(?:[A-Z][A-Za-z&'.\-]*\s+){1,6}(?:Co\.?,?\s*Ltd\.?|Corporation|Company|Inc\.?)",
        r"(?:University|Institute|College|School|Faculty|Department) of [A-Z][A-Za-z&'().\- ]{2,65}(?:,\s*[A-Z][A-Za-z&'.\-]+)?",
    ]
    english: list[str] = []
    for pattern in english_patterns:
        english.extend(re.findall(pattern, text))
    candidates = chinese or english
    canonical = re.sub(r"\s+", " ", candidates[0]).strip(" ,;；。") if candidates else text[:120]
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", canonical.casefold())
    return canonical, normalized


def plausible_affiliation(canonical: str) -> bool:
    text = re.sub(r"\s+", " ", canonical or "").strip()
    if not text or len(text) > 100:
        return False
    top_level = re.search(
        r"(?i)(University|Institute of Technology|Academy of Sciences|Research Institute|Hospital|Laborator(?:y|ies)|Corporation|Company|Co\.?,?\s*Ltd|Inc\.|大学|学院|研究院|研究所|实验室|医院|集团|公司)",
        text,
    )
    if not top_level:
        return False
    if re.search(r"(?i)(event-trigger|model setup|experimental chamber|temperature meas|introduction|abstract)", text):
        return False
    if re.match(r"(?i)^(Department|School|Faculty|College)\b", text) and not re.search(
        r"(?i)(University|Institute of Technology|Academy|Hospital|Corporation|Company|Co\.?,?\s*Ltd)", text
    ):
        return False
    return True


def first_page_region(text: str) -> str:
    match = re.search(r"(?s)===== Page 1 =====\s*(.*?)(?===== Page 2 =====|\Z)", text)
    page = match.group(1) if match else text[:8000]
    return re.split(r"(?i)\b(?:ARTICLE INFO|ABSTRACT|KEYWORDS?)\b", page, maxsplit=1)[0].strip()


def page_one_affiliation_candidate(text: str) -> str:
    page = first_page_region(text)
    direct_patterns = [
        r"(?:[A-Z][A-Za-z&'.\-]*\s+){1,5}University(?: of (?:Science and )?Technology)?",
        r"University of [A-Z][A-Za-z&'.\-]+(?:\s+[A-Z][A-Za-z&'.\-]+){0,4}(?:,\s*[A-Z][A-Za-z&'.\-]+)?",
        r"(?:[A-Z][A-Za-z&'.\-]*\s+){1,5}Institute of Technology",
        r"(?:[A-Z][A-Za-z&'.\-]*\s+){1,5}(?:Corporation|Company|Co\.?,?\s*Ltd\.?)",
    ]
    for pattern in direct_patterns:
        match = re.search(pattern, page)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip(" ,;")
    country = r"China|USA|United States|UK|United Kingdom|Japan|Germany|France|Italy|Denmark|Australia|Canada|Netherlands|Singapore|Switzerland|Korea|India"
    english = re.search(
        rf"(?i)(?:Department|School|Faculty|College|Institute|Laboratory|Centre|Center)\b.{{4,260}}?\b(?:{country})\b",
        page,
    )
    if english:
        return re.sub(r"\s+", " ", english.group(0)).strip(" ,;")
    chinese = re.search(
        r"[\u4e00-\u9fffA-Za-z0-9（），、()\-\s]{0,120}(?:大学|学院|研究院|研究所|实验室|医院|集团|公司)[\u4e00-\u9fffA-Za-z0-9（），、()\-\s]{0,100}",
        page,
    )
    if chinese:
        return re.sub(r"\s+", " ", chinese.group(0)).strip(" ,;；。")
    return candidate_affiliation(page)


def authoritative_affiliation(card: dict[str, Any] | None) -> tuple[str, str, str] | None:
    if not card:
        return None
    metadata = card["metadata"]
    value = str(metadata.get("first_author_affiliation") or "").strip().strip("'\"")
    status = normalized_affiliation_status(metadata)
    source = str(metadata.get("first_author_affiliation_source") or "existing reading card").strip()
    if known(value):
        evidence_status = status if status in AFFILIATION_FINAL_STATUSES else "existing_card_candidate"
        return value, source, evidence_status
    return None


def first_text_record(conn: sqlite3.Connection, item_key: str) -> tuple[str, str, str]:
    row = conn.execute(
        """
        SELECT p.status, COALESCE(p.text_normalized_cache_path, p.text_cache_path, ''),
               COALESCE(p.error, '')
        FROM pdf_texts p
        WHERE p.item_key = ?
        ORDER BY CASE p.status WHEN 'ok' THEN 0 WHEN 'needs_ocr' THEN 1 ELSE 2 END,
                 p.pages_with_text DESC, p.attachment_key
        LIMIT 1
        """,
        (item_key,),
    ).fetchone()
    return (str(row[0]), str(row[1]), str(row[2])) if row else ("no_pdf", "", "")


def extract_marked_pages(text: str, max_pages: int) -> str:
    marker = re.compile(r"(?m)^===== Page (\d+) =====\s*$")
    matches = list(marker.finditer(text))
    if not matches:
        return text
    chunks: list[str] = []
    for index, match in enumerate(matches):
        page = int(match.group(1))
        if page > max_pages:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunks.append(text[match.start() : end].strip())
    return "\n\n".join(chunks)


def resolve_normalized_text_path(root: Path, item_key: str, stored_path: str) -> Path | None:
    candidates: list[Path] = []
    if stored_path:
        stored = Path(stored_path)
        candidates.append(stored if stored.is_absolute() else root / stored)
    normalized_root = root / CORPUS_ZOTERO_FULLTEXT_NORMALIZED
    if normalized_root.exists():
        candidates.extend(sorted(normalized_root.glob(f"{item_key}__*.txt")))
        candidates.append(normalized_root / f"{item_key}.txt")
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def semantic_evidence(
    conn: sqlite3.Connection,
    root: Path,
    item: sqlite3.Row,
    max_pages: int,
    max_chars: int,
) -> dict[str, Any]:
    item_key = str(item["item_key"])
    text_status, stored_path, error = first_text_record(conn, item_key)
    path = resolve_normalized_text_path(root, item_key, stored_path)
    front_text = ""
    if text_status == "ok" and path:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        front_text = extract_marked_pages(raw, max_pages)[:max_chars].rstrip()
    payload = {
        "item_key": item_key,
        "item_version": int(item["version"] or 0),
        "text_status": text_status,
        "text_path": portable_path(path) if path else portable_path(stored_path) if stored_path else "",
        "text_error": error,
        "pages_scope": list(range(1, max_pages + 1)),
        "front_text": front_text,
    }
    hash_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["input_hash"] = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()
    return payload


def semantic_packet_items(conn: sqlite3.Connection, args: argparse.Namespace) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM items WHERE zotero_deleted=0"
    params: list[Any] = []
    if args.item_key:
        keys = [key.strip().upper() for key in args.item_key if key.strip()]
        query += f" AND item_key IN ({','.join('?' for _ in keys)})"
        params.extend(keys)
    query += " ORDER BY date_added,item_key"
    rows = list(conn.execute(query, params))
    if args.scope == "all":
        return rows[: args.batch_size]
    pending: list[sqlite3.Row] = []
    for item in rows:
        status_row = conn.execute("SELECT status FROM item_affiliations WHERE item_key=?", (item["item_key"],)).fetchone()
        status = str(status_row[0] or "") if status_row else "not_processed"
        if status not in AFFILIATION_FINAL_STATUSES:
            pending.append(item)
        if len(pending) >= args.batch_size:
            break
    return pending


def semantic_packet_command(args: argparse.Namespace) -> int:
    root, db, cards_root, _index_path = resolve_paths(args)
    if args.batch_size < 1 or args.max_pages < 1 or args.max_chars_per_item < 500:
        raise SystemExit("semantic-packet limits must be positive and max chars must be at least 500")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_dir = args.output_dir.resolve() if args.output_dir else root / M006_ZOTERO_INGESTION_PIPELINE / f"{timestamp}-semantic-packet"
    output_dir.mkdir(parents=True, exist_ok=False)
    cards = load_existing_cards(cards_root)
    with closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        items = semantic_packet_items(conn, args)
        records: list[dict[str, Any]] = []
        for item in items:
            evidence = semantic_evidence(conn, root, item, args.max_pages, args.max_chars_per_item)
            current = cards.get(str(item["item_key"]))
            records.append({
                **evidence,
                "title": str(item["title"] or ""),
                "authors_zotero": creator_names(str(item["creators_json"] or "")),
                "current_affiliation": (current or {}).get("metadata", {}).get("first_author_affiliation", ""),
                "current_affiliation_status": (current or {}).get("metadata", {}).get("first_author_affiliation_status", ""),
                "expected_result": {
                    "item_key": str(item["item_key"]),
                    "item_version": int(item["version"] or 0),
                    "input_hash": evidence["input_hash"],
                    "authors": "",
                    "first_author_affiliation": "",
                    "first_author_affiliation_raw": "",
                    "first_author_affiliation_source": "规范化 PDF 第 1-3 页语义识别",
                    "first_author_affiliation_status": "semantic_confirmed|semantic_needs_check|semantic_not_found|source_unavailable",
                    "pages_checked": [],
                },
            })
    jsonl_path = output_dir / "semantic-packet.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""), encoding="utf-8")
    lines = [
        "# 第一作者单位语义识别批次", "",
        "必须由模型或人工阅读下列首页证据；Python 候选不得作为最终依据。", "",
        "结果按 `expected_result` 字段输出为 JSONL，并先运行 `semantic-apply` 预检。", "",
    ]
    for record in records:
        lines.extend([
            f"## {record['item_key']}｜{record['title'] or '未命名'}", "",
            f"- item version：{record['item_version']}",
            f"- 文本状态：{record['text_status']}",
            f"- 证据哈希：`{record['input_hash']}`", "",
            "```text", record["front_text"] or "[无可用首页文本]", "```", "",
        ])
    (output_dir / "semantic-packet.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({
        "records": len(records),
        "output_dir": portable_path(output_dir),
        "jsonl": portable_path(jsonl_path),
    }, ensure_ascii=False, indent=2))
    return 0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise SystemExit(f"Invalid JSONL object at line {line_number}")
        records.append(value)
    return records


def semantic_result_record(result: dict[str, Any], evidence: dict[str, Any]) -> dict[str, str]:
    status = str(result.get("first_author_affiliation_status") or "").strip().lower()
    pages = result.get("pages_checked") or []
    if status not in SEMANTIC_RESULT_STATUSES:
        raise ValueError(f"unsupported semantic status: {status or 'missing'}")
    if status != "source_unavailable" and not isinstance(pages, list):
        raise ValueError("pages_checked must be a list")
    source = str(result.get("first_author_affiliation_source") or "").strip()
    if status != "source_unavailable" and pages and not re.search(r"(?i)(page|页)", source):
        source = f"{source or '规范化 PDF'} 第 {','.join(str(page) for page in pages)} 页语义识别"
    metadata = {
        "first_author_affiliation": str(result.get("first_author_affiliation") or "").strip(),
        "first_author_affiliation_raw": str(result.get("first_author_affiliation_raw") or "").strip(),
        "first_author_affiliation_source": source,
        "first_author_affiliation_status": status,
    }
    blockers = affiliation_publish_blockers(metadata)
    if blockers:
        raise ValueError(", ".join(blockers))
    if status == "source_unavailable" and evidence["text_status"] == "ok" and evidence["front_text"]:
        raise ValueError("source_unavailable conflicts with available normalized text")
    _canonical, normalized = canonicalize_affiliation(metadata["first_author_affiliation"])
    return {
        "raw": metadata["first_author_affiliation_raw"],
        "display": metadata["first_author_affiliation"] if known(metadata["first_author_affiliation"]) else "",
        "normalized": normalized if known(metadata["first_author_affiliation"]) else "",
        "source": source,
        "status": status,
        "evidence_path": evidence["text_path"],
    }


def semantic_unit_label(record: dict[str, str], pages: list[Any]) -> str:
    if record["status"] in {"semantic_confirmed", "manual_confirmed"}:
        return record["display"]
    page_text = ",".join(str(page) for page in pages) if pages else ""
    if record["status"] == "semantic_needs_check":
        return f"需要核查（已检查 PDF 第 {page_text} 页）" if page_text else "需要核查（已完成语义检查）"
    if record["status"] == "semantic_not_found":
        return f"未识别（已检查 PDF 第 {page_text} 页）" if page_text else "未识别（已完成语义检查）"
    return "未识别（来源材料不可用）"


def apply_semantic_to_card(card: dict[str, Any], result: dict[str, Any], record: dict[str, str]) -> str:
    current_status = normalized_affiliation_status(card["metadata"])
    if current_status in AFFILIATION_FINAL_STATUSES:
        raise ValueError(f"existing card already has final affiliation status: {current_status}")
    metadata = dict(card["metadata"])
    metadata["authors"] = str(result.get("authors") or metadata.get("authors") or "").strip()
    metadata["first_author_affiliation"] = record["display"]
    metadata["first_author_affiliation_raw"] = record["raw"]
    metadata["first_author_affiliation_source"] = record["source"]
    metadata["first_author_affiliation_status"] = record["status"]
    metadata["first_author_affiliation_pages"] = result.get("pages_checked") or []
    metadata["first_author_affiliation_input_hash"] = str(result.get("input_hash") or "")
    updated = set_metadata(card["text"], metadata)
    label = semantic_unit_label(record, result.get("pages_checked") or [])
    updated = re.sub(r"(?m)^- \*\*单位：\*\*\s*.*$", f"- **单位：** {label}", updated, count=1)
    if result.get("authors"):
        updated = re.sub(r"(?m)^- \*\*作者：\*\*\s*.*$", f"- **作者：** {str(result['authors']).strip()}", updated, count=1)
    return updated.rstrip() + "\n"


def semantic_apply_command(args: argparse.Namespace) -> int:
    root, db, cards_root, index_path = resolve_paths(args)
    results_path = args.results.resolve()
    results = read_jsonl(results_path)
    cards = load_existing_cards(cards_root)
    validated: list[tuple[dict[str, Any], dict[str, str], sqlite3.Row, dict[str, Any], str]] = []
    with closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        for result in results:
            item_key = str(result.get("item_key") or "").strip().upper()
            item = conn.execute("SELECT * FROM items WHERE item_key=? AND zotero_deleted=0", (item_key,)).fetchone()
            if not item:
                raise SystemExit(f"Semantic result targets a missing or inactive item: {item_key or '?'}")
            if int(result.get("item_version") or -1) != int(item["version"] or 0):
                raise SystemExit(f"Semantic result item version is stale: {item_key}")
            evidence = semantic_evidence(conn, root, item, args.max_pages, args.max_chars_per_item)
            if str(result.get("input_hash") or "") != evidence["input_hash"]:
                raise SystemExit(f"Semantic result evidence hash is stale: {item_key}")
            try:
                record = semantic_result_record(result, evidence)
            except ValueError as exc:
                raise SystemExit(f"Invalid semantic result for {item_key}: {exc}") from exc
            card = cards.get(item_key)
            if not card:
                raise SystemExit(f"Semantic result has no centralized reading card: {item_key}")
            try:
                updated = apply_semantic_to_card(card, result, record)
            except ValueError as exc:
                raise SystemExit(f"Refusing to overwrite {item_key}: {exc}") from exc
            validated.append((result, record, item, evidence, updated))
    if not args.write_local:
        print(json.dumps({"validated": len(validated), "write_local": False, "results": portable_path(results_path)}, ensure_ascii=False, indent=2))
        return 0
    lock_path: Path | None = None
    timestamp = now_iso()
    try:
        lock_path = acquire_writer_lock(db, 1800, args.force_lock)
        with rollback_file_writes() as file_rollback:
            with closing(sqlite3.connect(db, timeout=30)) as conn:
                ensure_pipeline_schema(conn)
                for result, record, item, evidence, updated in validated:
                    item_key = str(item["item_key"])
                    card = cards[item_key]
                    file_rollback.write_text(card["path"], updated)
                    upsert_affiliation(conn, item_key, record, timestamp)
                    conn.execute(
                        """UPDATE library_pipeline_state
                           SET affiliation_status=?, card_status='semantic_reviewed', processed_at=?
                           WHERE item_key=?""",
                        (record["status"], timestamp, item_key),
                    )
                rebuild_affiliation_frequencies(conn)
                refreshed = load_existing_cards(cards_root)
                rebuild_card_registry(conn, refreshed, root, timestamp)
                affiliation_index = root / AFFILIATION_INDEX_PATH
                file_rollback.protect(affiliation_index)
                export_affiliation_dictionary(conn, affiliation_index)
                file_rollback.protect(index_path)
                write_master_index(cards_root, index_path)
                conn.commit()
    finally:
        release_writer_lock(lock_path)
    print(json.dumps({"validated": len(validated), "write_local": True, "results": portable_path(results_path)}, ensure_ascii=False, indent=2))
    return 0


def detect_affiliation(conn: sqlite3.Connection, item_key: str, card: dict[str, Any] | None) -> dict[str, str]:
    authoritative = authoritative_affiliation(card)
    if authoritative:
        raw, source, status = authoritative
        canonical, normalized = canonicalize_affiliation(raw)
        return {"raw": raw, "display": canonical or raw, "normalized": normalized, "source": source, "status": status, "evidence_path": portable_path(card["path"])}
    text_status, cache_path, _error = first_text_record(conn, item_key)
    if text_status != "ok" or not cache_path:
        return {"raw": "", "display": "", "normalized": "", "source": text_status, "status": "not_found", "evidence_path": portable_path(cache_path) if cache_path else ""}
    path = Path(cache_path)
    if not path.is_absolute():
        path = RESEARCHOS_ROOT / path
    if not path.exists():
        return {"raw": "", "display": "", "normalized": "", "source": "cache_missing", "status": "not_found", "evidence_path": portable_path(path)}
    first_region = path.read_text(encoding="utf-8-sig", errors="replace")[:24000]
    raw = page_one_affiliation_candidate(first_region).strip()
    if not raw:
        return {"raw": "", "display": "", "normalized": "", "source": "normalized PDF first-page region heuristic", "status": "not_found", "evidence_path": portable_path(path)}
    canonical, normalized = canonicalize_affiliation(raw)
    if not plausible_affiliation(canonical):
        return {"raw": raw, "display": "", "normalized": "", "source": "normalized PDF first-page region heuristic", "status": "not_found", "evidence_path": portable_path(path)}
    return {"raw": raw, "display": canonical or raw[:120], "normalized": normalized, "source": "normalized PDF first-page region heuristic", "status": "heuristic_candidate", "evidence_path": portable_path(path)}


def canonical_id(normalized: str) -> str:
    return "AFF-" + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12].upper()


def upsert_affiliation(conn: sqlite3.Connection, item_key: str, record: dict[str, str], timestamp: str) -> None:
    entity_id = canonical_id(record["normalized"]) if record["normalized"] else None
    if entity_id:
        conn.execute(
            """
            INSERT INTO affiliation_entities(canonical_id, canonical_name, normalized_name, status, occurrence_count, updated_at)
            VALUES(?,?,?,?,0,?)
            ON CONFLICT(canonical_id) DO UPDATE SET
              canonical_name=excluded.canonical_name,
              status=CASE WHEN affiliation_entities.status='authoritative_card' THEN affiliation_entities.status ELSE excluded.status END,
              updated_at=excluded.updated_at
            """,
            (entity_id, record["display"], record["normalized"], record["status"], timestamp),
        )
        alias_norm = re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", record["raw"].casefold()) or record["normalized"]
        conn.execute(
            """
            INSERT INTO affiliation_aliases(normalized_alias, alias_raw, canonical_id, status, occurrence_count, updated_at)
            VALUES(?,?,?,?,0,?)
            ON CONFLICT(normalized_alias) DO UPDATE SET
              alias_raw=excluded.alias_raw, canonical_id=excluded.canonical_id,
              status=excluded.status, updated_at=excluded.updated_at
            """,
            (alias_norm, record["raw"] or record["display"], entity_id, record["status"], timestamp),
        )
    conn.execute(
        """
        INSERT INTO item_affiliations(item_key, canonical_id, affiliation_raw, affiliation_display, source, status, evidence_path, updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(item_key) DO UPDATE SET
          canonical_id=excluded.canonical_id, affiliation_raw=excluded.affiliation_raw,
          affiliation_display=excluded.affiliation_display, source=excluded.source,
          status=excluded.status, evidence_path=excluded.evidence_path, updated_at=excluded.updated_at
        """,
        (item_key, entity_id, record["raw"], record["display"], record["source"], record["status"], record["evidence_path"], timestamp),
    )


def rebuild_affiliation_frequencies(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE affiliation_entities SET occurrence_count=0")
    conn.execute("UPDATE affiliation_aliases SET occurrence_count=0")
    conn.execute(
        """UPDATE affiliation_entities
           SET occurrence_count=(SELECT COUNT(*) FROM item_affiliations i WHERE i.canonical_id=affiliation_entities.canonical_id)"""
    )
    alias_counts: dict[str, int] = {}
    for (raw,) in conn.execute("SELECT affiliation_raw FROM item_affiliations WHERE TRIM(COALESCE(affiliation_raw,'')) != ''"):
        normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", str(raw).casefold())
        if normalized:
            alias_counts[normalized] = alias_counts.get(normalized, 0) + 1
    conn.executemany(
        "UPDATE affiliation_aliases SET occurrence_count=? WHERE normalized_alias=?",
        [(count, alias) for alias, count in alias_counts.items()],
    )


def journal_record(conn: sqlite3.Connection, publication: str, item_type: str) -> tuple[str, str]:
    if item_type != "journalArticle" or not publication.strip():
        return "not_applicable", ""
    normalized = normalize_journal_name(publication)
    row = conn.execute(
        "SELECT status, COALESCE(publication_tags,'') FROM journal_rankings WHERE normalized_name=?",
        (normalized,),
    ).fetchone()
    return (str(row[0]), str(row[1])) if row else ("unqueried", "")


def journal_display(status: str, tags: str) -> str:
    ranks = parse_publication_tags(tags)
    values = [ranks[field] for field in RANK_ORDER if known(ranks.get(field))]
    if values:
        return " ".join(values)
    return {
        "not_applicable": "不适用",
        "no_match": "未收录",
        "error": "查询失败，待重试",
        "unqueried": "待查询",
        "no_query": "不适用",
    }.get(status, "待核查")


def text_evidence(conn: sqlite3.Connection, item_key: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT p.status, p.pages_total, p.pages_extracted, p.pages_with_text,
               p.text_chars, COALESCE(p.text_normalized_cache_path,''), a.attachment_key
        FROM attachments a LEFT JOIN pdf_texts p ON p.attachment_key=a.attachment_key
        WHERE a.parent_item_key=? AND a.content_type='application/pdf'
        ORDER BY CASE p.status WHEN 'ok' THEN 0 WHEN 'needs_ocr' THEN 1 ELSE 2 END,
                 COALESCE(p.pages_with_text,0) DESC LIMIT 1
        """,
        (item_key,),
    ).fetchone()
    if not row:
        return {"status": "no_pdf", "pages_total": 0, "pages_extracted": 0, "pages_with_text": 0, "text_chars": 0, "path": "", "attachment_key": ""}
    return {
        "status": str(row[0] or "pending"), "pages_total": int(row[1] or 0),
        "pages_extracted": int(row[2] or 0), "pages_with_text": int(row[3] or 0),
        "text_chars": int(row[4] or 0), "path": portable_path(str(row[5])) if row[5] else "", "attachment_key": str(row[6] or ""),
    }


def fulltext_status(evidence: dict[str, Any], abstract: str) -> str:
    if evidence["status"] == "ok":
        return "full_text_available_needs_review"
    if evidence["status"] == "needs_ocr":
        return "needs_ocr"
    if abstract.strip():
        return "metadata_or_abstract_only"
    return "metadata_only_no_pdf" if evidence["status"] == "no_pdf" else f"pdf_{evidence['status']}"


def compact_excerpt(value: str, limit: int = 1800) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "……"


def render_card(item: sqlite3.Row, card_id: str, affiliation: dict[str, str], journal_status: str, journal_tags: str, evidence: dict[str, Any], timestamp: str) -> str:
    title = str(item["title"] or "未命名条目").strip()
    authors = "; ".join(creator_names(str(item["creators_json"] or ""))) or "未记录"
    abstract = compact_excerpt(str(item["abstract_note"] or ""))
    status = fulltext_status(evidence, abstract)
    affiliation_final = affiliation["status"] in AFFILIATION_FINAL_STATUSES
    if affiliation["status"] in {"semantic_confirmed", "manual_confirmed"} and affiliation["display"]:
        unit = affiliation["display"]
    elif affiliation["status"] == "semantic_needs_check":
        unit = "需要核查（已完成语义检查）"
    elif affiliation["status"] == "semantic_not_found":
        unit = "未识别（已完成语义检查）"
    elif affiliation["status"] == "source_unavailable":
        unit = "未识别（来源材料不可用）"
    else:
        unit = "待语义识别"
    rank = journal_display(journal_status, journal_tags)
    source_path = str(evidence["path"] or "")
    metadata = {
        "item_key": f"[{item['item_key']}](zotero://select/library/items/{item['item_key']})",
        "manual_ref_id": card_id,
        "title": title,
        "authors": authors,
        "first_author_affiliation": affiliation["display"] if affiliation_final else "",
        "first_author_affiliation_raw": affiliation["raw"] if affiliation_final else "",
        "first_author_affiliation_source": affiliation["source"] if affiliation_final else "",
        "first_author_affiliation_status": affiliation["status"],
        "first_author_affiliation_candidate": affiliation["display"] if affiliation["status"] == "heuristic_candidate" else "",
        "first_author_affiliation_candidate_raw": affiliation["raw"] if affiliation["status"] == "heuristic_candidate" else "",
        "first_author_affiliation_candidate_source": affiliation["source"] if affiliation["status"] == "heuristic_candidate" else "",
        "year": str(item["year"] or ""),
        "venue": str(item["publication"] or ""),
        "publication_tags": journal_tags,
        "journal_ranking_source": "EasyScholar dictionary",
        "journal_ranking_status": journal_status,
        "abstract_note": str(item["abstract_note"] or ""),
        "doi": str(item["doi"] or ""),
        "evidence_strength": status,
        "fulltext_status": status,
        "generated_at": timestamp,
        "normalized_at": timestamp[:10],
        "pdf_attachment_key": evidence["attachment_key"],
        "source_text": source_path,
        "status": "自动初筛，待精读",
        "zotero_item_type": str(item["item_type"] or ""),
        "zotero_key": str(item["item_key"]),
        "zotero_version": str(item["version"] or ""),
    }
    metadata_lines = "\n".join(f"{key}: {yaml_scalar(value)}" for key, value in metadata.items() if known(value))
    abstract_section = abstract or "当前 Zotero 题录未记录摘要；需结合全文或外部题录补充。"
    evidence_line = (
        f"PDF attachment `{evidence['attachment_key']}`；抽取 {evidence['pages_extracted']}/{evidence['pages_total']} 页，"
        f"其中 {evidence['pages_with_text']} 页有文本；规范化文本：`{source_path}`。"
        if evidence["attachment_key"] else "当前条目没有可用 PDF 子附件。"
    )
    return f'''---
card_id: {yaml_scalar(card_id)}
zotero_key: {yaml_scalar(str(item["item_key"]))}
project_links: []
title: {yaml_scalar(title)}
fulltext_status: {yaml_scalar(status)}
source: "corpus/reading-cards/cards"
normalized_at: {yaml_scalar(timestamp[:10])}
generation_mode: "auto_initial_screening"
---

# [{title}](zotero://select/library/items/{item["item_key"]})

- **Zotero条目：** [{item["item_key"]}](zotero://select/library/items/{item["item_key"]})
- **作者：** {authors}
- **单位：** {unit}
- **出版年份：** {str(item["year"] or "未记录")}
- **期刊名称：** {str(item["publication"] or "不适用/未记录")}
- **期刊等级：** {rank}

## 1. 创新摘要

这是一张自动生成的初筛卡，不等同于人工或模型精读结论。根据现有题录，本文题名为“{title}”。具体创新、方法贡献和定量结论需要结合下列摘要与全文证据进一步核查。

## 2. 背景与摘要证据

{abstract_section}

> 证据边界：以上为 Zotero 摘要原文或缺失说明，未将摘要内容改写为已经核实的全文结论。

## 3. 研究内容与材料状态

- 条目类型：`{str(item["item_type"] or "未记录")}`。
- DOI：{str(item["doi"] or "未记录")}。
- 文本状态：`{evidence["status"]}`。
- {evidence_line}
- 单位识别状态：`{affiliation["status"]}`；机器候选不作为正式事实，需核对论文首页作者—单位标号。

## 4. 研究结果

当前初筛流水线不自动把摘要或正文片段提升为“已确认结果”。精读时应补充研究对象、方法、数据、主要结果、数值及页码，并区分事实、作者解释和 ResearchOS 推断。

## 5. 初筛判断与待核查项

- 判断是否与当前研究项目相关，并决定是否精读。
- 核对第一作者单位及同一单位的中英文/缩写别名。
- 核对期刊等级词典状态：`{journal_status}`。
- 若文本状态为 `needs_ocr`、`missing_pdf` 或 `error`，先处理全文可用性。
- 本卡不生成第 6 章“借鉴”；项目关联确认后再按关联时间顺序追加 6.1.1、6.1.2 等三级目录。

## 7. 元数据（折叠）

<details>
<summary>Reading card metadata</summary>

```yaml
{metadata_lines}
```

</details>
'''


def visible_value_missing(text: str, label: str) -> bool:
    match = re.search(rf"(?m)^- \*\*{re.escape(label)}：\*\*\s*(.*?)\s*$", text)
    return bool(match and match.group(1).strip().casefold() in MISSING_DISPLAY)


def enrich_existing_card(text: str, affiliation: dict[str, str], journal_status: str, journal_tags: str) -> str:
    updated = text
    if visible_value_missing(updated, "单位"):
        unit = affiliation["display"] if affiliation["status"] in {"semantic_confirmed", "manual_confirmed"} and affiliation["display"] else "待语义识别"
        updated = re.sub(r"(?m)^- \*\*单位：\*\*\s*[?？]\s*$", f"- **单位：** {unit}", updated, count=1)
    if visible_value_missing(updated, "期刊等级"):
        updated = re.sub(r"(?m)^- \*\*期刊等级：\*\*\s*[?？]\s*$", f"- **期刊等级：** {journal_display(journal_status, journal_tags)}", updated, count=1)
    return updated


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def select_items(
    conn: sqlite3.Connection,
    scope: str,
    item_keys: list[str],
    limit: int | None,
    state_table_exists: bool = True,
) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM items i WHERE i.zotero_deleted=0"
    params: list[Any] = []
    if item_keys:
        keys = [key.strip().upper() for key in item_keys if key.strip()]
        query += f" AND i.item_key IN ({','.join('?' for _ in keys)})"
        params.extend(keys)
    elif scope == "new" and state_table_exists:
        query += " AND NOT EXISTS (SELECT 1 FROM library_pipeline_state s WHERE s.item_key=i.item_key AND s.item_version>=i.version AND s.pipeline_version=?)"
        params.append(PIPELINE_VERSION)
    query += " ORDER BY i.date_added, i.item_key"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(query, params))


def max_card_number(cards: dict[str, dict[str, Any]]) -> int:
    values = [card_number(str(record["card_id"])) for record in cards.values()]
    return max([value for value in values if value < 10**9], default=0)


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def rebuild_card_registry(conn: sqlite3.Connection, cards: dict[str, dict[str, Any]], root: Path, timestamp: str) -> None:
    for item_key, record in cards.items():
        path = record["path"]
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        header = parse_frontmatter(text)
        title = str(header.get("title") or parse_metadata(text).get("title") or path.stem)
        conn.execute(
            """
            INSERT INTO reading_cards(item_key, display_label, card_title, master_card_path, content_hash, status, generated_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(item_key) DO UPDATE SET
              display_label=excluded.display_label, card_title=excluded.card_title,
              master_card_path=excluded.master_card_path, content_hash=excluded.content_hash,
              status=excluded.status, updated_at=excluded.updated_at
            """,
            (item_key, record["card_id"], title, relative_to_root(path, root), content_sha256(text), "authoritative_master", timestamp, timestamp),
        )


def relative_link_path(path: Path, from_dir: Path) -> str:
    return Path(os.path.relpath(path, from_dir)).as_posix()


def write_master_index(cards_root: Path, index_path: Path) -> None:
    rows: list[tuple[int, str, Path, str, str, str]] = []
    for path in cards_root.glob("*.md"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        card_id, item_key = reading_card_identity(text, path)
        if not item_key:
            continue
        header = parse_frontmatter(text)
        projects = reading_card_project_links(text)
        project_label = "；".join(link.get("project_id", "") for link in projects if link.get("project_id")) or "未分配"
        status = str(header.get("fulltext_status") or parse_metadata(text).get("fulltext_status") or "待核查")
        rows.append((card_number(card_id), card_id, path, item_key, project_label, status))
    rows.sort(key=lambda row: (row[0], row[3]))
    timestamp = now_iso()
    lines = [
        "# ResearchOS 读书卡主索引", "", f"- 更新时间：{timestamp}", f"- 主卡数量：{len(rows)}", "",
        "| 序号 | 卡片 | 项目 | 文献 | 状态 |", "|---:|---|---|---|---|",
    ]
    for number, card_id, path, item_key, project, status in rows:
        rel = relative_link_path(path, index_path.parent)
        lines.append(f"| {number} | [{card_id}]({rel}) | {project} | [{item_key}](zotero://select/library/items/{item_key}) | {status} |")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_affiliation_dictionary(conn: sqlite3.Connection, path: Path) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """SELECT e.canonical_id,e.canonical_name,e.status,e.occurrence_count,
                  a.alias_raw,a.status,a.occurrence_count
           FROM affiliation_entities e LEFT JOIN affiliation_aliases a ON a.canonical_id=e.canonical_id
           ORDER BY e.occurrence_count DESC,e.canonical_name,a.alias_raw"""
    ).fetchall()
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["canonical_id", "canonical_name", "canonical_status", "canonical_frequency", "alias", "alias_status", "alias_frequency"])
        writer.writerows(rows)


def process_assets(args: argparse.Namespace) -> int:
    root, db, cards_root, index_path = resolve_paths(args)
    if not db.exists():
        print(f"ERROR: database not found: {db}", file=sys.stderr)
        return 2
    cards_root.mkdir(parents=True, exist_ok=True)
    timestamp = now_iso()
    existing = load_existing_cards(cards_root)
    next_number = max_card_number(existing) + 1
    lock_path: Path | None = None
    file_rollback = FileWriteRollback()
    stats = {"selected": 0, "created": 0, "enriched": 0, "deleted_preserved": 0, "affiliation_candidates": 0, "affiliation_not_found": 0}
    try:
        if not args.dry_run:
            lock_path = acquire_writer_lock(db, 1800, args.force_lock)
        with closing(sqlite3.connect(db, timeout=30)) as conn:
            conn.row_factory = sqlite3.Row
            if not args.dry_run:
                ensure_pipeline_schema(conn)
                stats["deleted_preserved"] = conn.execute(
                    """
                    UPDATE library_pipeline_state
                    SET card_status='zotero_deleted_preserved', processed_at=?
                    WHERE item_key IN (SELECT item_key FROM items WHERE zotero_deleted=1)
                      AND card_status!='zotero_deleted_preserved'
                    """,
                    (timestamp,),
                ).rowcount
            has_state = table_exists(conn, "library_pipeline_state")
            items = select_items(conn, args.scope, args.item_key, args.limit, has_state)
            stats["selected"] = len(items)
            for item in items:
                item_key = str(item["item_key"])
                card = existing.get(item_key)
                affiliation = detect_affiliation(conn, item_key, card)
                if affiliation["status"] == "heuristic_candidate":
                    stats["affiliation_candidates"] += 1
                if affiliation["status"] == "not_found":
                    stats["affiliation_not_found"] += 1
                journal_status, journal_tags = journal_record(conn, str(item["publication"] or ""), str(item["item_type"] or ""))
                evidence = text_evidence(conn, item_key)
                if not args.dry_run:
                    upsert_affiliation(conn, item_key, affiliation, timestamp)
                if card:
                    updated = enrich_existing_card(str(card["text"]), affiliation, journal_status, journal_tags)
                    if updated != card["text"]:
                        stats["enriched"] += 1
                        if not args.dry_run:
                            file_rollback.write_text(card["path"], updated)
                            card["text"] = updated
                else:
                    card_id = f"RC-{next_number:03d}"
                    next_number += 1
                    filename = safe_filename_part(author_year_label(str(item["creators_json"] or ""), str(item["year"] or "")))
                    path = cards_root / f"{card_id}_{item_key}_{filename}.md"
                    rendered = render_card(item, card_id, affiliation, journal_status, journal_tags, evidence, timestamp)
                    stats["created"] += 1
                    record = {"path": path, "text": rendered, "card_id": card_id, "metadata": parse_metadata(rendered), "frontmatter": parse_frontmatter(rendered), "project_links": []}
                    existing[item_key] = record
                    if not args.dry_run:
                        file_rollback.write_text(path, rendered)
                if not args.dry_run:
                    card_path = relative_to_root(existing[item_key]["path"], root)
                    conn.execute(
                        """
                        INSERT INTO library_pipeline_state(item_key,item_version,pipeline_version,text_status,affiliation_status,journal_status,card_status,card_path,processed_at)
                        VALUES(?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(item_key) DO UPDATE SET
                          item_version=excluded.item_version,pipeline_version=excluded.pipeline_version,
                          text_status=excluded.text_status,affiliation_status=excluded.affiliation_status,
                          journal_status=excluded.journal_status,card_status=excluded.card_status,
                          card_path=excluded.card_path,processed_at=excluded.processed_at
                        """,
                        (item_key, int(item["version"] or 0), PIPELINE_VERSION, evidence["status"], affiliation["status"], journal_status, "available", card_path, timestamp),
                    )
            if not args.dry_run:
                rebuild_affiliation_frequencies(conn)
                refreshed = load_existing_cards(cards_root)
                rebuild_card_registry(conn, refreshed, root, timestamp)
                affiliation_index = root / AFFILIATION_INDEX_PATH
                file_rollback.protect(affiliation_index)
                export_affiliation_dictionary(conn, affiliation_index)
                file_rollback.protect(index_path)
                write_master_index(cards_root, index_path)
                conn.commit()
    except BaseException as exc:
        restore_errors = file_rollback.restore()
        if restore_errors:
            raise RuntimeError(
                "Reading-card pipeline failed and local file rollback was incomplete: " + "; ".join(restore_errors)
            ) from exc
        raise
    finally:
        release_writer_lock(lock_path)
    print("ResearchOS Zotero library reading pipeline")
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"dry_run: {args.dry_run}")
    return 0


def strict_audit_failures(
    active_keys: set[str],
    state_keys: set[str],
    affiliation_status_by_key: dict[str, str],
    card_keys: set[str],
) -> dict[str, int]:
    active_state_keys = active_keys.intersection(state_keys)
    active_affiliation_keys = active_keys.intersection(affiliation_status_by_key)
    pending = sum(
        1
        for key in active_affiliation_keys
        if affiliation_status_by_key[key] not in AFFILIATION_FINAL_STATUSES
    )
    return {
        "missing_cards": len(active_keys.difference(card_keys)),
        "missing_pipeline_state": len(active_keys.difference(active_state_keys)),
        "missing_affiliation_state": len(active_keys.difference(active_affiliation_keys)),
        "affiliation_semantic_pending": pending,
    }


def audit_assets(args: argparse.Namespace) -> int:
    _root, db, cards_root, _index_path = resolve_paths(args)
    existing = load_existing_cards(cards_root)
    with closing(sqlite3.connect(db)) as conn:
        filters = ""
        params: list[str] = []
        if args.item_key:
            keys = [key.upper() for key in args.item_key]
            filters = f" AND item_key IN ({','.join('?' for _ in keys)})"
            params = keys
        active_keys = {str(row[0]) for row in conn.execute("SELECT item_key FROM items WHERE zotero_deleted=0" + filters, params)}
        active = len(active_keys)
        deleted = conn.execute("SELECT COUNT(*) FROM items WHERE zotero_deleted=1" + filters, params).fetchone()[0]
        all_state_keys = {
            str(row[0])
            for row in conn.execute("SELECT item_key FROM library_pipeline_state")
        } if table_exists(conn, "library_pipeline_state") else set()
        state_keys = active_keys.intersection(all_state_keys)
        affiliation_filter = ""
        if args.item_key:
            affiliation_filter = f" AND a.item_key IN ({','.join('?' for _ in args.item_key)})"
        affiliation_rows = conn.execute(
            """SELECT a.item_key,a.status
               FROM item_affiliations a JOIN items i ON i.item_key=a.item_key
               WHERE i.zotero_deleted=0""" + affiliation_filter,
            params,
        ).fetchall() if table_exists(conn, "item_affiliations") else []
        journals = conn.execute("SELECT status,COUNT(*) FROM journal_rankings GROUP BY status ORDER BY status").fetchall()
        text = conn.execute("SELECT status,COUNT(*) FROM pdf_texts GROUP BY status ORDER BY status").fetchall()
    print("ResearchOS Zotero library pipeline audit")
    print(f"active_items: {active}")
    print(f"soft_deleted_items: {deleted}")
    active_cards = len(active_keys.intersection(existing))
    print(f"reading_cards: {len(existing)}")
    print(f"active_item_cards: {active_cards}")
    print(f"preserved_cards_outside_active_scope: {len(set(existing).difference(active_keys))}")
    print(f"pipeline_state: {len(state_keys)}")
    print(f"missing_cards: {max(0, active-active_cards)}")
    print("pdf_text_status: " + json.dumps(dict(text), ensure_ascii=False))
    print("journal_dictionary_status: " + json.dumps(dict(journals), ensure_ascii=False))
    affiliation_status_by_key = {str(key): str(status or "") for key, status in affiliation_rows}
    affiliation_counts: dict[str, int] = {}
    for status in affiliation_status_by_key.values():
        affiliation_counts[status] = affiliation_counts.get(status, 0) + 1
    print("affiliation_status: " + json.dumps(affiliation_counts, ensure_ascii=False))
    if not args.strict:
        return 0
    strict_failures = strict_audit_failures(
        active_keys,
        state_keys,
        affiliation_status_by_key,
        set(existing),
    )
    print("strict_failures: " + json.dumps(strict_failures, ensure_ascii=False))
    return 2 if any(strict_failures.values()) else 0


def run_step(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print("RUN: " + " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def reconcile_soft_deleted_items(db: Path) -> tuple[int, int]:
    """Mirror current Local API visibility using a guarded temporary key table."""
    client = ZoteroClient("http://127.0.0.1:23119/api", "0")
    records = client.fetch_paged("items/top", {"sort": "dateModified", "direction": "desc"})
    keys = {
        str(record.get("key") or (record.get("data") or {}).get("key") or "").strip().upper()
        for record in records
        if str((record.get("data") or {}).get("itemType") or "") not in {"attachment", "note", "annotation"}
    }
    keys.discard("")
    if not keys:
        raise RuntimeError("Local API full pagination returned an empty top-level key set; soft-delete reconciliation aborted.")
    lock_path: Path | None = None
    try:
        lock_path = acquire_writer_lock(db, 1800, False)
        with closing(sqlite3.connect(db, timeout=30)) as conn:
            conn.execute("CREATE TEMP TABLE visible_zotero_keys(item_key TEXT PRIMARY KEY)")
            conn.executemany("INSERT INTO visible_zotero_keys(item_key) VALUES(?)", [(key,) for key in sorted(keys)])
            deleted = conn.execute(
                """UPDATE items SET zotero_deleted=1
                   WHERE COALESCE(zotero_deleted,0)=0
                     AND NOT EXISTS(SELECT 1 FROM visible_zotero_keys v WHERE v.item_key=items.item_key)"""
            ).rowcount
            restored = conn.execute(
                """UPDATE items SET zotero_deleted=0
                   WHERE COALESCE(zotero_deleted,0)=1
                     AND EXISTS(SELECT 1 FROM visible_zotero_keys v WHERE v.item_key=items.item_key)"""
            ).rowcount
            conn.commit()
        return deleted, restored
    finally:
        release_writer_lock(lock_path)


def run_pipeline(args: argparse.Namespace) -> int:
    root, db, _cards_root, _index_path = resolve_paths(args)
    python = sys.executable
    network_env, proxy_source = machine_network_env(root)
    print(f"proxy_configuration_source: {proxy_source}")
    print("local_api_proxy_bypass: 127.0.0.1,localhost,::1")
    if not args.skip_sync:
        command = [python, "tools/zotero/zotero_library_index.py", "sync"]
        if args.scope == "new":
            command.append("--only-new-or-modified")
        run_step(command, root, network_env)
        deleted, restored = reconcile_soft_deleted_items(db)
        print(f"soft_deleted_marked: {deleted}")
        print(f"soft_deleted_restored: {restored}")
    run_step([python, "tools/runtime/ensure_ocr_needed.py"], root, network_env)
    run_step([python, "tools/zotero/zotero_library_index.py", "normalize-text-cache", "--only-missing"], root, network_env)
    journal = [python, "tools/reading_cards/sync_journal_rankings.py", "--include-library-items"]
    if args.no_journal_api:
        journal.append("--no-api")
    run_step(journal, root, network_env)
    process = [python, str(Path(__file__).resolve()), "--researchos-root", str(root), "--db", str(db), "process", "--scope", args.scope]
    for key in args.item_key:
        process.extend(["--item-key", key])
    if args.limit is not None:
        process.extend(["--limit", str(args.limit)])
    run_step(process, root, network_env)
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "process":
        return process_assets(args)
    if args.command == "audit":
        return audit_assets(args)
    if args.command == "semantic-packet":
        return semantic_packet_command(args)
    if args.command == "semantic-apply":
        return semantic_apply_command(args)
    if args.command == "run":
        return run_pipeline(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
