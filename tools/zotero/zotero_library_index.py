"""Build and watch a read-only Zotero metadata and PDF text-cache SQLite library.

The script reads Zotero Local API and local PDF attachments only as needed. If a
fulltext cache root is supplied, cached text is reused before PDF extraction and
newly extracted text is written back to that cache. SQLite stores text metadata and cache paths, not inline full text or FTS copies. It never writes to Zotero,
never reads zotero.sqlite, and never copies, moves, deletes, or renames Zotero
PDF files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_FULLTEXT,
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
)
from tools.zotero.zotero_local_api import file_url_to_path, year_from_date


DEFAULT_API_BASE = "http://localhost:23119/api"
DEFAULT_USER_ID = "0"
PAGE_LIMIT = 100
TIMEOUT_SECONDS = 30
SKIP_TOP_LEVEL_TYPES = {"attachment", "note", "annotation"}
DEFAULT_STALE_AFTER_SECONDS = 3600
DEFAULT_OCR_LANGUAGE = "eng+chi_sim"
DEFAULT_OCR_DPI = 220
DEFAULT_LOCK_STALE_AFTER_SECONDS = 1800
DEFAULT_OCR_MAX_SOURCE_PAGES = 80
DEFAULT_OCR_SKIP_ITEM_TYPES = ("book", "thesis")
DEFAULT_FULLTEXT_CACHE_ROOT = CORPUS_ZOTERO_FULLTEXT
DEFAULT_NORMALIZED_CACHE_ROOT = CORPUS_ZOTERO_FULLTEXT_NORMALIZED
FTS_TABLE_NAMES = (
    "pdf_text_fts",
    "pdf_text_fts_data",
    "pdf_text_fts_idx",
    "pdf_text_fts_content",
    "pdf_text_fts_docsize",
    "pdf_text_fts_config",
)


def default_local_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ResearchOS"
    return Path.home() / ".researchos"


DEFAULT_DB = CORPUS_ZOTERO_LIBRARY_DB


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def default_tesseract_exe() -> Path:
    return default_local_root() / "tesseract" / "bin" / "tesseract.exe"


def default_tessdata_dir() -> Path:
    return default_local_root() / "tesseract" / "share" / "tessdata"


def resolve_tesseract_cmd() -> str | None:
    configured = os.environ.get("RESEARCHOS_TESSERACT_CMD") or os.environ.get("TESSERACT_CMD")
    if configured and Path(configured).exists():
        return configured
    local_build = default_tesseract_exe()
    if local_build.exists():
        return str(local_build)
    return shutil.which("tesseract")


def configure_tessdata_prefix() -> None:
    if os.environ.get("TESSDATA_PREFIX"):
        return
    tessdata = default_tessdata_dir()
    if tessdata.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata)


def writer_lock_path(db_path: Path) -> Path:
    return db_path.with_suffix(db_path.suffix + ".writer.lock")


def owner_id() -> str:
    host = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown-host"
    return f"{host}:{os.getpid()}"


def read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def acquire_writer_lock(db_path: Path, stale_after_seconds: int, force: bool = False) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = writer_lock_path(db_path)
    now_dt = utc_now_dt()
    payload = {
        "owner": owner_id(),
        "pid": os.getpid(),
        "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "",
        "created_at": now_dt.isoformat(timespec="seconds"),
        "heartbeat_at": now_dt.isoformat(timespec="seconds"),
        "db": str(db_path),
    }
    while True:
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            return lock_path
        except FileExistsError:
            existing = read_json_file(lock_path)
            heartbeat = parse_utc_timestamp((existing or {}).get("heartbeat_at"))
            stale = heartbeat is None or heartbeat <= now_dt - timedelta(seconds=max(stale_after_seconds, 0))
            if force or stale:
                stale_path = lock_path.with_name(f"{lock_path.name}.{int(time.time())}.stale")
                try:
                    lock_path.replace(stale_path)
                except OSError:
                    pass
                continue
            raise RuntimeError(f"writer lock is active: {lock_path}; owner={(existing or {}).get('owner', 'unknown')}")


def heartbeat_writer_lock(lock_path: Path | None) -> None:
    if lock_path is None or not lock_path.exists():
        return
    payload = read_json_file(lock_path) or {}
    payload["heartbeat_at"] = utc_now()
    payload["owner"] = payload.get("owner") or owner_id()
    lock_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def release_writer_lock(lock_path: Path | None) -> None:
    if lock_path is not None:
        lock_path.unlink(missing_ok=True)


def creators_to_json(creators: list[dict[str, Any]]) -> str:
    values: list[dict[str, str]] = []
    for creator in creators:
        item: dict[str, str] = {"creatorType": str(creator.get("creatorType", ""))}
        if creator.get("name"):
            item["name"] = str(creator["name"])
        else:
            item["firstName"] = str(creator.get("firstName", ""))
            item["lastName"] = str(creator.get("lastName", ""))
        values.append(item)
    return json.dumps(values, ensure_ascii=False)


def clean_text(value: Any) -> str:
    """Remove invalid surrogate code points before SQLite/FTS insertion."""
    return str(value or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def tags_to_list(tags: list[dict[str, Any]]) -> list[str]:
    return [str(tag.get("tag", "")).strip() for tag in tags if str(tag.get("tag", "")).strip()]


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


@dataclass
class PdfExtraction:
    status: str
    method: str
    text: str
    pages_total: int
    pages_extracted: int
    pages_with_text: int
    error: str = ""


class ZoteroClient:
    def __init__(self, api_base: str, user_id: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.user_id = user_id

    def fetch_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        query = "?" + urlencode(params or {})
        url = f"{self.api_base}/users/{self.user_id}/{endpoint.lstrip('/')}{query}"
        request = Request(url, headers={"Zotero-API-Version": "3"})
        # Local API must stay direct even when different workstations use
        # different HTTP(S) proxy hosts or ports.
        with build_opener(ProxyHandler({})).open(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    def fetch_paged(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_records: int | None = None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        start = 0
        while True:
            remaining = None if max_records is None else max_records - len(records)
            if remaining is not None and remaining <= 0:
                break
            limit = PAGE_LIMIT if remaining is None else min(PAGE_LIMIT, remaining)
            page_params = {"format": "json", "include": "data", "limit": limit, "start": start}
            if params:
                page_params.update(params)
            batch = self.fetch_json(endpoint, page_params)
            if not batch:
                break
            records.extend(batch)
            if len(batch) < limit:
                break
            start += limit
        return records

    def resolve_file_url(self, attachment_key: str) -> tuple[str | None, Path | None]:
        url = f"{self.api_base}/users/{self.user_id}/items/{attachment_key}/file/view/url"
        request = Request(url, headers={"Zotero-API-Version": "3"})
        opener = build_opener(ProxyHandler({}), NoRedirectHandler)
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                headers = response.headers
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                headers = exc.headers
                body = exc.read().decode("utf-8", errors="replace")
            else:
                raise
        file_url = headers.get("Location") or body.strip()
        if not file_url:
            return None, None
        try:
            payload = json.loads(file_url)
        except ValueError:
            pass
        else:
            if isinstance(payload, dict):
                file_url = str(payload.get("url") or payload.get("file") or payload.get("path") or "")
        return file_url, file_url_to_path(file_url) if file_url else None


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS sync_runs (
          run_id INTEGER PRIMARY KEY AUTOINCREMENT,
          mode TEXT NOT NULL,
          started_at TEXT NOT NULL,
          heartbeat_at TEXT,
          finished_at TEXT,
          status TEXT NOT NULL,
          process_id INTEGER,
          owner TEXT,
          items_seen INTEGER DEFAULT 0,
          items_processed INTEGER DEFAULT 0,
          pdfs_seen INTEGER DEFAULT 0,
          texts_extracted INTEGER DEFAULT 0,
          errors INTEGER DEFAULT 0,
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS collections (
          collection_key TEXT PRIMARY KEY,
          name TEXT,
          parent_key TEXT,
          path TEXT,
          raw_json TEXT NOT NULL,
          last_seen_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS items (
          item_key TEXT PRIMARY KEY,
          version INTEGER,
          item_type TEXT,
          title TEXT,
          creators_json TEXT,
          year TEXT,
          date TEXT,
          publication TEXT,
          journal_abbreviation TEXT,
          doi TEXT,
          isbn TEXT,
          url TEXT,
          language TEXT,
          abstract_note TEXT,
          raw_json TEXT NOT NULL,
          collections_json TEXT,
          collection_paths_json TEXT,
          tags_json TEXT,
          date_added TEXT,
          date_modified TEXT,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          last_synced_at TEXT NOT NULL,
          zotero_deleted INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS item_collections (
          item_key TEXT NOT NULL,
          collection_key TEXT NOT NULL,
          collection_path TEXT,
          PRIMARY KEY (item_key, collection_key)
        );

        CREATE TABLE IF NOT EXISTS tags (
          tag TEXT PRIMARY KEY,
          last_seen_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS item_tags (
          item_key TEXT NOT NULL,
          tag TEXT NOT NULL,
          PRIMARY KEY (item_key, tag)
        );

        CREATE TABLE IF NOT EXISTS attachments (
          attachment_key TEXT PRIMARY KEY,
          parent_item_key TEXT NOT NULL,
          version INTEGER,
          title TEXT,
          content_type TEXT,
          link_mode TEXT,
          filename TEXT,
          file_url TEXT,
          pdf_path TEXT,
          file_exists INTEGER DEFAULT 0,
          file_size INTEGER,
          file_mtime TEXT,
          file_sha256 TEXT,
          raw_json TEXT NOT NULL,
          last_seen_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS annotations (
          annotation_key TEXT PRIMARY KEY,
          attachment_key TEXT NOT NULL,
          parent_item_key TEXT NOT NULL,
          version INTEGER,
          annotation_type TEXT,
          annotation_text TEXT,
          annotation_comment TEXT,
          annotation_color TEXT,
          annotation_page_label TEXT,
          annotation_sort_index TEXT,
          annotation_position_json TEXT,
          tags_json TEXT,
          raw_json TEXT NOT NULL,
          date_added TEXT,
          date_modified TEXT,
          content_hash TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          last_synced_at TEXT NOT NULL,
          zotero_deleted INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS annotation_sync_runs (
          run_id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          status TEXT NOT NULL,
          scope TEXT NOT NULL,
          items_scanned INTEGER DEFAULT 0,
          attachments_scanned INTEGER DEFAULT 0,
          annotations_seen INTEGER DEFAULT 0,
          annotations_upserted INTEGER DEFAULT 0,
          annotations_soft_deleted INTEGER DEFAULT 0,
          errors INTEGER DEFAULT 0,
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS reading_card_zotero_notes (
          card_id TEXT PRIMARY KEY,
          item_key TEXT NOT NULL,
          card_path TEXT NOT NULL,
          note_key TEXT,
          note_version INTEGER,
          source_hash TEXT NOT NULL,
          published_note_hash TEXT,
          publish_status TEXT NOT NULL,
          last_planned_at TEXT,
          last_published_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pdf_texts (
          attachment_key TEXT PRIMARY KEY,
          item_key TEXT NOT NULL,
          extraction_method TEXT,
          status TEXT NOT NULL,
          pages_total INTEGER DEFAULT 0,
          pages_extracted INTEGER DEFAULT 0,
          pages_with_text INTEGER DEFAULT 0,
          text_chars INTEGER DEFAULT 0,
          text TEXT,
          text_cache_path TEXT,
          text_normalized_cache_path TEXT,
          error TEXT,
          source_file_sha256 TEXT,
          source_file_mtime TEXT,
          extracted_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS item_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_key TEXT NOT NULL,
          event_type TEXT NOT NULL,
          event_at TEXT NOT NULL,
          details_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_items_date_modified ON items(date_modified);
        CREATE INDEX IF NOT EXISTS idx_attachments_parent ON attachments(parent_item_key);
        CREATE INDEX IF NOT EXISTS idx_annotations_parent_item ON annotations(parent_item_key);
        CREATE INDEX IF NOT EXISTS idx_annotations_attachment ON annotations(attachment_key);
        CREATE INDEX IF NOT EXISTS idx_annotations_modified ON annotations(date_modified);
        """
    )
    ensure_sync_run_columns(conn)
    ensure_pdf_text_columns(conn)
    conn.commit()


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_sync_run_columns(conn: sqlite3.Connection) -> None:
    existing = column_names(conn, "sync_runs")
    columns = {
        "heartbeat_at": "TEXT",
        "process_id": "INTEGER",
        "owner": "TEXT",
    }
    for name, declaration in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE sync_runs ADD COLUMN {name} {declaration}")


def ensure_pdf_text_columns(conn: sqlite3.Connection) -> None:
    existing = column_names(conn, "pdf_texts")
    if "text_cache_path" not in existing:
        conn.execute("ALTER TABLE pdf_texts ADD COLUMN text_cache_path TEXT")
    if "text_normalized_cache_path" not in existing:
        conn.execute("ALTER TABLE pdf_texts ADD COLUMN text_normalized_cache_path TEXT")


def recover_stale_runs(conn: sqlite3.Connection, stale_after_seconds: int, reason: str) -> int:
    threshold = utc_now_dt() - timedelta(seconds=max(stale_after_seconds, 0))
    recovered = 0
    now = utc_now()
    rows = conn.execute(
        "SELECT run_id, started_at, heartbeat_at, notes FROM sync_runs WHERE status = 'running'"
    ).fetchall()
    for run_id, started_at, heartbeat_at, notes in rows:
        last_seen = parse_utc_timestamp(heartbeat_at) or parse_utc_timestamp(started_at)
        if last_seen is not None and last_seen > threshold:
            continue
        detail = f"{notes or ''}; recovered_stale_running={reason}; stale_after_seconds={stale_after_seconds}".strip("; ")
        conn.execute(
            """
            UPDATE sync_runs
            SET status = 'interrupted',
                finished_at = COALESCE(finished_at, ?),
                heartbeat_at = COALESCE(heartbeat_at, ?),
                notes = ?
            WHERE run_id = ? AND status = 'running'
            """,
            (now, now, detail, run_id),
        )
        recovered += 1
    if recovered:
        conn.commit()
    return recovered


def collection_maps(collections: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_key: dict[str, dict[str, Any]] = {}
    for collection in collections:
        data = collection.get("data", {})
        key = str(collection.get("key") or data.get("key") or "")
        if key:
            by_key[key] = data

    path_cache: dict[str, str] = {}

    def build_path(key: str, seen: set[str] | None = None) -> str:
        if key in path_cache:
            return path_cache[key]
        seen = seen or set()
        data = by_key.get(key, {})
        name = str(data.get("name") or key)
        parent = data.get("parentCollection")
        if parent and str(parent) not in seen:
            seen.add(key)
            path = build_path(str(parent), seen) + "/" + name
        else:
            path = name
        path_cache[key] = path
        return path

    for key in by_key:
        build_path(key)
    return by_key, path_cache


def upsert_collections(conn: sqlite3.Connection, collections: list[dict[str, Any]], paths: dict[str, str]) -> None:
    now = utc_now()
    for collection in collections:
        data = collection.get("data", {})
        key = str(collection.get("key") or data.get("key") or "")
        if not key:
            continue
        conn.execute(
            """
            INSERT INTO collections (collection_key, name, parent_key, path, raw_json, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_key) DO UPDATE SET
              name=excluded.name,
              parent_key=excluded.parent_key,
              path=excluded.path,
              raw_json=excluded.raw_json,
              last_seen_at=excluded.last_seen_at
            """,
            (
                key,
            clean_text(data.get("name", "")),
            clean_text(data.get("parentCollection") or ""),
                paths.get(key, key),
                json.dumps(collection, ensure_ascii=False),
                now,
            ),
        )


def existing_item_state(conn: sqlite3.Connection, item_key: str) -> tuple[int | None, str | None]:
    row = conn.execute("SELECT version, date_modified FROM items WHERE item_key = ?", (item_key,)).fetchone()
    if row is None:
        return None, None
    return int(row[0]) if row[0] is not None else None, row[1]


def item_has_unextracted_pdf(conn: sqlite3.Connection, item_key: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM attachments AS a
        LEFT JOIN pdf_texts AS t ON t.attachment_key = a.attachment_key
        WHERE a.parent_item_key = ?
          AND a.content_type = 'application/pdf'
          AND t.attachment_key IS NULL
        """,
        (item_key,),
    ).fetchone()
    return bool(row and row[0])


def insert_event(conn: sqlite3.Connection, item_key: str, event_type: str, details: dict[str, Any] | None = None) -> None:
    conn.execute(
        "INSERT INTO item_events (item_key, event_type, event_at, details_json) VALUES (?, ?, ?, ?)",
        (item_key, event_type, utc_now(), json.dumps(details or {}, ensure_ascii=False)),
    )


def upsert_item(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    collection_paths: dict[str, str],
) -> tuple[str, bool]:
    data = item.get("data", {})
    item_key = str(item.get("key") or data.get("key") or "")
    old_version, old_modified = existing_item_state(conn, item_key)
    is_new = old_version is None
    now = utc_now()
    collection_keys = [str(key) for key in data.get("collections", [])]
    paths = [collection_paths.get(key, key) for key in collection_keys]
    tags = tags_to_list(data.get("tags", []))
    publication = str(data.get("publicationTitle") or data.get("conferenceName") or data.get("bookTitle") or "")
    version = int(item.get("version") or data.get("version") or 0)

    conn.execute(
        """
        INSERT INTO items (
          item_key, version, item_type, title, creators_json, year, date,
          publication, journal_abbreviation, doi, isbn, url, language,
          abstract_note, raw_json, collections_json, collection_paths_json,
          tags_json, date_added, date_modified, first_seen_at, last_seen_at,
          last_synced_at, zotero_deleted
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(item_key) DO UPDATE SET
          version=excluded.version,
          item_type=excluded.item_type,
          title=excluded.title,
          creators_json=excluded.creators_json,
          year=excluded.year,
          date=excluded.date,
          publication=excluded.publication,
          journal_abbreviation=excluded.journal_abbreviation,
          doi=excluded.doi,
          isbn=excluded.isbn,
          url=excluded.url,
          language=excluded.language,
          abstract_note=excluded.abstract_note,
          raw_json=excluded.raw_json,
          collections_json=excluded.collections_json,
          collection_paths_json=excluded.collection_paths_json,
          tags_json=excluded.tags_json,
          date_added=excluded.date_added,
          date_modified=excluded.date_modified,
          last_seen_at=excluded.last_seen_at,
          last_synced_at=excluded.last_synced_at,
          zotero_deleted=0
        """,
        (
            item_key,
            version,
            clean_text(data.get("itemType", "")),
            clean_text(data.get("title", "")),
            creators_to_json(data.get("creators", [])),
            year_from_date(data.get("date")),
            clean_text(data.get("date", "")),
            clean_text(publication),
            clean_text(data.get("journalAbbreviation", "")),
            clean_text(data.get("DOI", "")),
            clean_text(data.get("ISBN", "")),
            clean_text(data.get("url", "")),
            clean_text(data.get("language", "")),
            clean_text(data.get("abstractNote", "")),
            json.dumps(item, ensure_ascii=False),
            json.dumps(collection_keys, ensure_ascii=False),
            json.dumps(paths, ensure_ascii=False),
            json.dumps(tags, ensure_ascii=False),
            clean_text(data.get("dateAdded", "")),
            clean_text(data.get("dateModified", "")),
            now,
            now,
            now,
        ),
    )
    conn.execute("DELETE FROM item_collections WHERE item_key = ?", (item_key,))
    for collection_key, path in zip(collection_keys, paths):
        conn.execute(
            "INSERT OR REPLACE INTO item_collections (item_key, collection_key, collection_path) VALUES (?, ?, ?)",
            (item_key, collection_key, path),
        )
    conn.execute("DELETE FROM item_tags WHERE item_key = ?", (item_key,))
    for tag in tags:
        conn.execute(
            "INSERT INTO tags (tag, last_seen_at) VALUES (?, ?) ON CONFLICT(tag) DO UPDATE SET last_seen_at=excluded.last_seen_at",
            (tag, now),
        )
        conn.execute("INSERT OR REPLACE INTO item_tags (item_key, tag) VALUES (?, ?)", (item_key, tag))
    if is_new:
        insert_event(conn, item_key, "new_item", {"version": version})
    elif old_version != version or old_modified != str(data.get("dateModified", "")):
        insert_event(conn, item_key, "updated_item", {"old_version": old_version, "new_version": version})
    return item_key, is_new


def should_extract(conn: sqlite3.Connection, attachment_key: str, file_sha256: str | None, force: bool, use_ocr: bool) -> bool:
    if force:
        return True
    row = conn.execute(
        "SELECT status, source_file_sha256 FROM pdf_texts WHERE attachment_key = ?",
        (attachment_key,),
    ).fetchone()
    if row is None:
        return True
    status, old_sha = row
    if status == "needs_ocr" and use_ocr:
        return True
    if status in {"error", "needs_ocr", "missing_pdf"}:
        return False
    return bool(file_sha256 and old_sha and file_sha256 != old_sha)


def extract_pdf_text(pdf_path: Path, max_pages: int | None = None, use_ocr: bool = False, ocr_language: str = DEFAULT_OCR_LANGUAGE, ocr_dpi: int = DEFAULT_OCR_DPI) -> PdfExtraction:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        return PdfExtraction("error", "pypdf", "", 0, 0, 0, f"缺少依赖 pypdf: {exc}")

    try:
        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)
        page_limit = min(max_pages, total_pages) if max_pages else total_pages
        chunks: list[str] = []
        non_empty = 0
        for index in range(page_limit):
            text = reader.pages[index].extract_text() or ""
            if text.strip():
                non_empty += 1
            chunks.append(f"\n\n===== Page {index + 1} =====\n\n{text.strip()}")
        full_text = "".join(chunks).strip()
    except Exception as exc:
        return PdfExtraction("error", "pypdf", "", 0, 0, 0, str(exc))

    if non_empty == 0 or len(full_text) < 100:
        if use_ocr:
            return extract_pdf_text_ocr(pdf_path, page_limit, total_pages, ocr_language, ocr_dpi, full_text)
        return PdfExtraction("needs_ocr", "pypdf", full_text, total_pages, page_limit, non_empty, "抽取文本很少，可能是扫描版 PDF。")
    return PdfExtraction("ok", "pypdf", full_text, total_pages, page_limit, non_empty)


def extract_pdf_text_ocr(
    pdf_path: Path,
    page_limit: int,
    total_pages: int,
    ocr_language: str,
    ocr_dpi: int,
    fallback_text: str = "",
) -> PdfExtraction:
    try:
        import fitz  # type: ignore[import-not-found]
        import pytesseract  # type: ignore[import-not-found]
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:
        return PdfExtraction("needs_ocr", "pypdf", fallback_text, total_pages, page_limit, 0, f"OCR 依赖不可用：{exc}")

    tesseract_cmd = resolve_tesseract_cmd()
    if tesseract_cmd is None:
        return PdfExtraction("needs_ocr", "pypdf", fallback_text, total_pages, page_limit, 0, "OCR 引擎不可用：未找到本机 Tesseract 构建。")
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    configure_tessdata_prefix()

    chunks: list[str] = []
    pages_with_text = 0
    zoom = max(ocr_dpi, 72) / 72
    matrix = fitz.Matrix(zoom, zoom)
    try:
        with fitz.open(str(pdf_path)) as document:
            limit = min(page_limit, len(document))
            for index in range(limit):
                page = document.load_page(index)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                mode = "RGB" if pixmap.n < 4 else "RGBA"
                image = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
                text = pytesseract.image_to_string(image, lang=ocr_language).strip()
                if text:
                    pages_with_text += 1
                chunks.append(f"\n\n===== Page {index + 1} OCR =====\n\n{text}")
    except Exception as exc:
        return PdfExtraction("error", "ocr", fallback_text, total_pages, page_limit, pages_with_text, f"OCR failed: {exc}")

    ocr_text = "".join(chunks).strip()
    if len(ocr_text) < 100:
        return PdfExtraction("needs_ocr", "ocr", ocr_text or fallback_text, total_pages, page_limit, pages_with_text, "OCR 抽取文本仍然很少，需要人工复核。")
    return PdfExtraction("ok", "ocr", ocr_text, total_pages, page_limit, pages_with_text)


def extraction_to_json(result: PdfExtraction) -> dict[str, Any]:
    return {
        "status": result.status,
        "method": result.method,
        "text": result.text,
        "pages_total": result.pages_total,
        "pages_extracted": result.pages_extracted,
        "pages_with_text": result.pages_with_text,
        "error": result.error,
    }


def extract_pdf_text_with_timeout(
    pdf_path: Path,
    max_pages: int | None,
    timeout_seconds: int,
    use_ocr: bool = False,
    ocr_language: str = DEFAULT_OCR_LANGUAGE,
    ocr_dpi: int = DEFAULT_OCR_DPI,
) -> PdfExtraction:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        output_json = Path(handle.name)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "__extract_pdf_worker",
        "--pdf",
        str(pdf_path),
        "--output-json",
        str(output_json),
    ]
    if max_pages is not None:
        command.extend(["--max-pages", str(max_pages)])
    if use_ocr:
        command.append("--ocr")
        command.extend(["--ocr-language", ocr_language, "--ocr-dpi", str(ocr_dpi)])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        output_json.unlink(missing_ok=True)
        return PdfExtraction("error", "pypdf", "", 0, 0, 0, f"PDF extraction timed out after {timeout_seconds} seconds.")
    if completed.returncode != 0:
        output_json.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout or "").strip()
        return PdfExtraction("error", "pypdf", "", 0, 0, 0, f"PDF extraction worker exited with code {completed.returncode}. {detail[:500]}")
    try:
        payload = json.loads(output_json.read_text(encoding="utf-8"))
    except Exception as exc:
        output_json.unlink(missing_ok=True)
        return PdfExtraction("error", "pypdf", "", 0, 0, 0, f"PDF extraction worker returned invalid JSON: {exc}")
    output_json.unlink(missing_ok=True)
    return PdfExtraction(
        str(payload.get("status", "error")),
        str(payload.get("method", "pypdf")),
        str(payload.get("text", "")),
        int(payload.get("pages_total", 0) or 0),
        int(payload.get("pages_extracted", 0) or 0),
        int(payload.get("pages_with_text", 0) or 0),
        str(payload.get("error", "")),
    )


def fulltext_cache_path(fulltext_cache_root: Path | None, item_key: str, attachment_key: str | None = None) -> Path | None:
    if fulltext_cache_root is None or not item_key:
        return None
    if attachment_key:
        return fulltext_cache_root / f"{item_key.upper()}__{attachment_key.upper()}.txt"
    return fulltext_cache_root / f"{item_key.upper()}.txt"


def read_fulltext_cache(fulltext_cache_root: Path | None, item_key: str, attachment_key: str | None = None) -> tuple[PdfExtraction, Path] | None:
    paths = [fulltext_cache_path(fulltext_cache_root, item_key, attachment_key)]
    if attachment_key:
        paths.append(fulltext_cache_path(fulltext_cache_root, item_key))
    path = next((candidate for candidate in paths if candidate is not None and candidate.exists()), None)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    status = "ok" if text.strip() else "needs_ocr"
    non_empty = len([line for line in text.splitlines() if line.strip()])
    return PdfExtraction(status, "fulltext_cache", text, 0, 0, non_empty, ""), path


def write_fulltext_cache(fulltext_cache_root: Path | None, item_key: str, attachment_key: str | None, text: str) -> Path | None:
    path = fulltext_cache_path(fulltext_cache_root, item_key, attachment_key)
    if path is None or not text:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_existing_text_file(path_value: Any) -> str:
    if not path_value:
        return ""
    try:
        path = Path(str(path_value))
    except OSError:
        return ""
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def materialize_pdf_text_cache(
    conn: sqlite3.Connection,
    fulltext_cache_root: Path,
    overwrite: bool = False,
) -> dict[str, int]:
    fulltext_cache_root.mkdir(parents=True, exist_ok=True)
    stats = {"exported": 0, "linked_existing": 0, "skipped": 0}
    rows = conn.execute(
        """
        SELECT attachment_key, item_key, text, text_cache_path
        FROM pdf_texts
        WHERE status IN ('ok', 'needs_ocr')
        ORDER BY item_key, attachment_key
        """
    ).fetchall()
    for attachment_key, item_key, text, text_cache_path in rows:
        target = fulltext_cache_path(fulltext_cache_root, str(item_key), str(attachment_key))
        if target is None:
            stats["skipped"] += 1
            continue
        inline_text = clean_text(text) if text else ""
        source_text = inline_text or read_existing_text_file(text_cache_path)
        if target.exists() and not overwrite:
            conn.execute(
                "UPDATE pdf_texts SET text_cache_path = ? WHERE attachment_key = ?",
                (str(target.resolve()), attachment_key),
            )
            stats["linked_existing"] += 1
            continue
        if source_text:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_text, encoding="utf-8")
            conn.execute(
                "UPDATE pdf_texts SET text_cache_path = ? WHERE attachment_key = ?",
                (str(target.resolve()), attachment_key),
            )
            stats["exported"] += 1
            continue
        if target.exists():
            conn.execute(
                "UPDATE pdf_texts SET text_cache_path = ? WHERE attachment_key = ?",
                (str(target.resolve()), attachment_key),
            )
            stats["linked_existing"] += 1
        else:
            stats["skipped"] += 1
    return stats


def drop_legacy_fts_tables(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'pdf_text_fts%'"
    ).fetchall()
    existing = {str(row[0]) for row in rows}
    dropped = 0
    if "pdf_text_fts" in existing:
        conn.execute("DROP TABLE IF EXISTS pdf_text_fts")
        dropped += 1
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'pdf_text_fts%'"
        ).fetchall()
        existing = {str(row[0]) for row in rows}
    for name in FTS_TABLE_NAMES:
        if name == "pdf_text_fts" or name not in existing:
            continue
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        dropped += 1
    return dropped


PAGE_MARKER_RE = re.compile(r"^=+\s*Page\s+\d+.*=+$", re.IGNORECASE)
LIST_MARKER_RE = re.compile(r"^(\(?\d+[\).]|[A-Za-z][\).]|[-*+•])\s+")


def is_cjk_char(value: str) -> bool:
    if not value:
        return False
    code = ord(value)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
        or 0x3040 <= code <= 0x30FF
        or 0xAC00 <= code <= 0xD7AF
    )


def join_text_lines(lines: list[str]) -> str:
    result = ""
    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line.strip())
        if not line:
            continue
        if not result:
            result = line
            continue
        left = result[-1]
        right = line[0]
        if result.endswith("-") and left.isascii() and right.isascii() and right.islower():
            result = result[:-1] + line
        elif is_cjk_char(left) and is_cjk_char(right):
            result += line
        elif right in ",.;:!?)]}%，。；：！？、）】》":
            result += line
        elif left in "([{《【":
            result += line
        else:
            result += " " + line
    return result


def normalize_pdf_text_for_ai(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    output: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        joined = join_text_lines(paragraph).strip()
        if joined:
            output.append(joined)
        paragraph = []

    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue
        if PAGE_MARKER_RE.match(line):
            flush_paragraph()
            output.append(line)
            continue
        if LIST_MARKER_RE.match(line):
            flush_paragraph()
            output.append(re.sub(r"\s+", " ", line))
            continue
        paragraph.append(line)
    flush_paragraph()

    compact = "\n\n".join(part for part in output if part.strip())
    return compact.strip() + ("\n" if compact else "")


def command_extract_pdf_worker(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Internal PDF extraction worker.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--ocr-language", default=DEFAULT_OCR_LANGUAGE)
    parser.add_argument("--ocr-dpi", type=int, default=DEFAULT_OCR_DPI)
    args = parser.parse_args(argv)
    result = extract_pdf_text(Path(args.pdf), args.max_pages, args.ocr, args.ocr_language, args.ocr_dpi)
    Path(args.output_json).write_text(json.dumps(extraction_to_json(result), ensure_ascii=False), encoding="utf-8")
    return 0


def upsert_attachment(
    conn: sqlite3.Connection,
    client: ZoteroClient,
    item_key: str,
    attachment: dict[str, Any],
    extract_text: bool,
    force_extract: bool,
    max_pages: int | None,
    pdf_timeout: int,
    fulltext_cache_root: Path | None,
    use_ocr: bool,
    ocr_language: str,
    ocr_dpi: int,
) -> tuple[bool, bool]:
    data = attachment.get("data", {})
    attachment_key = str(attachment.get("key") or data.get("key") or "")
    content_type = str(data.get("contentType", ""))
    is_pdf = content_type.casefold() == "application/pdf"
    file_url = ""
    pdf_path = ""
    file_exists = False
    file_size: int | None = None
    file_mtime = ""
    file_sha256 = ""

    if is_pdf and extract_text:
        try:
            resolved_url, resolved_path = client.resolve_file_url(attachment_key)
        except Exception as exc:
            resolved_url, resolved_path = f"ERROR: {exc}", None
        file_url = resolved_url or ""
        if resolved_path:
            pdf_path = str(resolved_path)
            file_exists = resolved_path.exists() and resolved_path.is_file()
            if file_exists:
                stat = resolved_path.stat()
                file_size = stat.st_size
                file_mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds")
                file_sha256 = f"size={file_size};mtime={file_mtime}"

    conn.execute(
        """
        INSERT INTO attachments (
          attachment_key, parent_item_key, version, title, content_type,
          link_mode, filename, file_url, pdf_path, file_exists, file_size,
          file_mtime, file_sha256, raw_json, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(attachment_key) DO UPDATE SET
          parent_item_key=excluded.parent_item_key,
          version=excluded.version,
              title=excluded.title,
          content_type=excluded.content_type,
          link_mode=excluded.link_mode,
          filename=excluded.filename,
          file_url=excluded.file_url,
          pdf_path=excluded.pdf_path,
          file_exists=excluded.file_exists,
          file_size=excluded.file_size,
          file_mtime=excluded.file_mtime,
          file_sha256=excluded.file_sha256,
          raw_json=excluded.raw_json,
          last_seen_at=excluded.last_seen_at
        """,
        (
            attachment_key,
            item_key,
            int(attachment.get("version") or data.get("version") or 0),
            clean_text(data.get("title", "")),
            content_type,
            clean_text(data.get("linkMode", "")),
            clean_text(data.get("filename", "")),
            clean_text(file_url),
            clean_text(pdf_path),
            1 if file_exists else 0,
            file_size,
            file_mtime,
            file_sha256,
            json.dumps(attachment, ensure_ascii=False),
            utc_now(),
        ),
    )

    if not is_pdf:
        return False, False
    if not extract_text:
        return True, False
    if not file_exists:
        conn.execute(
            """
            INSERT INTO pdf_texts (
              attachment_key, item_key, status, text_chars, text, error,
              text_cache_path, source_file_sha256, source_file_mtime, extracted_at
            )
            VALUES (?, ?, 'missing_pdf', 0, NULL, 'PDF path is missing or does not exist.', '', ?, ?, ?)
            ON CONFLICT(attachment_key) DO UPDATE SET
              item_key=excluded.item_key,
              status=excluded.status,
              text_chars=excluded.text_chars,
              text=excluded.text,
              error=excluded.error,
              text_cache_path=excluded.text_cache_path,
              source_file_sha256=excluded.source_file_sha256,
              source_file_mtime=excluded.source_file_mtime,
              extracted_at=excluded.extracted_at
            """,
            (attachment_key, item_key, file_sha256, file_mtime, utc_now()),
        )
        return True, False
    if not should_extract(conn, attachment_key, file_sha256, force_extract, use_ocr):
        return True, False

    cache_path: Path | None = None
    cache_hit = None if force_extract else read_fulltext_cache(fulltext_cache_root, item_key, attachment_key)
    if cache_hit is None:
        result = None
    else:
        result, cache_path = cache_hit
    if result is not None and result.status == "needs_ocr" and use_ocr:
        result = None
        cache_path = None
    if result is None:
        result = extract_pdf_text_with_timeout(Path(pdf_path), max_pages, pdf_timeout, use_ocr, ocr_language, ocr_dpi)
        if result.text and result.status in {"ok", "needs_ocr"}:
            cache_path = write_fulltext_cache(fulltext_cache_root, item_key, attachment_key, result.text)
    conn.execute(
        """
        INSERT INTO pdf_texts (
          attachment_key, item_key, extraction_method, status, pages_total,
          pages_extracted, pages_with_text, text_chars, text, error,
          text_cache_path, source_file_sha256, source_file_mtime, extracted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(attachment_key) DO UPDATE SET
          item_key=excluded.item_key,
          extraction_method=excluded.extraction_method,
          status=excluded.status,
          pages_total=excluded.pages_total,
          pages_extracted=excluded.pages_extracted,
          pages_with_text=excluded.pages_with_text,
          text_chars=excluded.text_chars,
          text=excluded.text,
          error=excluded.error,
          text_cache_path=excluded.text_cache_path,
          source_file_sha256=excluded.source_file_sha256,
          source_file_mtime=excluded.source_file_mtime,
          extracted_at=excluded.extracted_at
        """,
        (
            attachment_key,
            item_key,
            result.method,
            result.status,
            result.pages_total,
            result.pages_extracted,
            result.pages_with_text,
            len(result.text),
            None,
            clean_text(result.error),
            clean_text(str(cache_path) if cache_path else ""),
            file_sha256,
            file_mtime,
            utc_now(),
        ),
    )

    return True, result.status == "ok"


def process_item(
    conn: sqlite3.Connection,
    client: ZoteroClient,
    item: dict[str, Any],
    collection_paths: dict[str, str],
    extract_text: bool,
    force_extract: bool,
    max_pages: int | None,
    pdf_timeout: int,
    fulltext_cache_root: Path | None,
    use_ocr: bool,
    ocr_language: str,
    ocr_dpi: int,
) -> tuple[bool, int, int]:
    item_key, is_new = upsert_item(conn, item, collection_paths)
    children = client.fetch_paged(f"items/{item_key}/children")
    pdf_count = 0
    extracted_count = 0
    for child in children:
        data = child.get("data", {})
        if data.get("itemType") != "attachment":
            continue
        is_pdf, extracted = upsert_attachment(
            conn,
            client,
            item_key,
            child,
            extract_text,
            force_extract,
            max_pages,
            pdf_timeout,
            fulltext_cache_root,
            use_ocr,
            ocr_language,
            ocr_dpi,
        )
        if is_pdf:
            pdf_count += 1
        if extracted:
            extracted_count += 1
    return is_new, pdf_count, extracted_count


def start_run(conn: sqlite3.Connection, mode: str, notes: str = "") -> int:
    now = utc_now()
    cursor = conn.execute(
        """
        INSERT INTO sync_runs (mode, started_at, heartbeat_at, status, process_id, owner, notes)
        VALUES (?, ?, ?, 'running', ?, ?, ?)
        """,
        (mode, now, now, os.getpid(), os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "", notes),
    )
    conn.commit()
    return int(cursor.lastrowid)


def heartbeat_run(conn: sqlite3.Connection, run_id: int, stats: dict[str, int], lock_path: Path | None = None) -> None:
    conn.execute(
        """
        UPDATE sync_runs
        SET heartbeat_at = ?,
            items_seen = ?,
            items_processed = ?,
            pdfs_seen = ?,
            texts_extracted = ?,
            errors = ?
        WHERE run_id = ? AND status = 'running'
        """,
        (
            utc_now(),
            stats.get("items_seen", 0),
            stats.get("items_processed", 0),
            stats.get("pdfs_seen", 0),
            stats.get("texts_extracted", 0),
            stats.get("errors", 0),
            run_id,
        ),
    )
    heartbeat_writer_lock(lock_path)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    items_seen: int,
    items_processed: int,
    pdfs_seen: int,
    texts_extracted: int,
    errors: int,
    notes: str = "",
) -> None:
    conn.execute(
        """
        UPDATE sync_runs
        SET finished_at = ?, status = ?, items_seen = ?, items_processed = ?,
            pdfs_seen = ?, texts_extracted = ?, errors = ?, notes = ?
        WHERE run_id = ?
        """,
        (utc_now(), status, items_seen, items_processed, pdfs_seen, texts_extracted, errors, notes, run_id),
    )
    conn.commit()


def sync_library(
    conn: sqlite3.Connection,
    client: ZoteroClient,
    mode: str,
    run_id: int,
    extract_text: bool,
    force_extract: bool,
    max_pages: int | None,
    pdf_timeout: int,
    fulltext_cache_root: Path | None,
    max_items: int | None,
    max_process_items: int | None,
    only_new_or_modified: bool,
    use_ocr: bool,
    ocr_language: str,
    ocr_dpi: int,
    lock_path: Path | None,
) -> dict[str, int]:
    collections = client.fetch_paged("collections")
    collections_by_key, collection_paths = collection_maps(collections)
    del collections_by_key
    upsert_collections(conn, collections, collection_paths)
    items = client.fetch_paged("items/top", {"sort": "dateModified", "direction": "desc"}, max_items)
    stats = {"items_seen": 0, "items_processed": 0, "pdfs_seen": 0, "texts_extracted": 0, "errors": 0}
    for item in items:
        data = item.get("data", {})
        if data.get("itemType") in SKIP_TOP_LEVEL_TYPES:
            continue
        item_key = str(item.get("key") or data.get("key") or "")
        version = int(item.get("version") or data.get("version") or 0)
        old_version, old_modified = existing_item_state(conn, item_key)
        stats["items_seen"] += 1
        if max_process_items is not None and stats["items_processed"] >= max_process_items:
            break
        unchanged = old_version == version and old_modified == str(data.get("dateModified", ""))
        if only_new_or_modified and unchanged and not (extract_text and item_has_unextracted_pdf(conn, item_key)):
            continue
        try:
            _is_new, pdf_count, extracted_count = process_item(
                conn,
                client,
                item,
                collection_paths,
                extract_text,
                force_extract,
                max_pages,
                pdf_timeout,
                fulltext_cache_root,
                use_ocr,
                ocr_language,
                ocr_dpi,
            )
            stats["items_processed"] += 1
            stats["pdfs_seen"] += pdf_count
            stats["texts_extracted"] += extracted_count
            heartbeat_run(conn, run_id, stats, lock_path)
            conn.commit()
        except Exception as exc:
            stats["errors"] += 1
            insert_event(conn, item_key or "(unknown)", "sync_error", {"error": str(exc)})
            heartbeat_run(conn, run_id, stats, lock_path)
            conn.commit()
            print(f"ERROR item {item_key}: {exc}", file=sys.stderr)
    return stats


def command_sync(args: argparse.Namespace) -> int:
    args.db.parent.mkdir(parents=True, exist_ok=True)
    client = ZoteroClient(args.api_base, args.user_id)
    lock_path = None
    try:
        lock_path = acquire_writer_lock(args.db, args.lock_stale_after, args.force_lock)
        with closing(sqlite3.connect(args.db)) as conn:
            init_db(conn)
            recovered = recover_stale_runs(conn, args.stale_after, "sync-start")
            run_id = start_run(conn, "sync", f"extract_text={not args.no_pdf_text}; max_pages={args.max_pages}; ocr={args.ocr}; recovered_stale_runs={recovered}")
            try:
                stats = sync_library(
                    conn,
                    client,
                    "sync",
                    run_id,
                    not args.no_pdf_text,
                    args.force_extract,
                    args.max_pages,
                    args.pdf_timeout,
                    args.fulltext_cache_root,
                    args.max_items,
                    args.max_process_items,
                    args.only_new_or_modified,
                    args.ocr,
                    args.ocr_language,
                    args.ocr_dpi,
                    lock_path,
                )
            except (HTTPError, URLError, json.JSONDecodeError) as exc:
                finish_run(conn, run_id, "error", 0, 0, 0, 0, 1, str(exc))
                print(f"ERROR: Zotero Local API 读取失败：{exc}", file=sys.stderr)
                return 2
            finish_run(conn, run_id, "ok", **stats)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        release_writer_lock(lock_path)
    print(f"OK: Zotero library indexed -> {args.db}")
    for key, value in stats.items():
        print(f"{key}: {value}")
    return 0 if stats["errors"] == 0 else 1


def command_watch(args: argparse.Namespace) -> int:
    args.db.parent.mkdir(parents=True, exist_ok=True)
    client = ZoteroClient(args.api_base, args.user_id)
    print(f"watching Zotero every {args.interval} seconds; db={args.db}")
    lock_path = None
    try:
        lock_path = acquire_writer_lock(args.db, args.lock_stale_after, args.force_lock)
        with closing(sqlite3.connect(args.db)) as conn:
            init_db(conn)
            recovered = recover_stale_runs(conn, args.stale_after, "watch-start")
            if recovered:
                print(f"recovered_stale_runs: {recovered}")
            loops = 0
            while True:
                loops += 1
                run_id = start_run(conn, "watch", f"loop={loops}; ocr={args.ocr}")
                try:
                    stats = sync_library(
                        conn,
                        client,
                        "watch",
                        run_id,
                        not args.no_pdf_text,
                        args.force_extract,
                        args.max_pages,
                        args.pdf_timeout,
                        args.fulltext_cache_root,
                        args.max_items,
                        args.max_process_items,
                        True,
                        args.ocr,
                        args.ocr_language,
                        args.ocr_dpi,
                        lock_path,
                    )
                    finish_run(conn, run_id, "ok", **stats)
                    print(f"{utc_now()} loop={loops} processed={stats['items_processed']} extracted={stats['texts_extracted']} errors={stats['errors']}")
                except KeyboardInterrupt:
                    finish_run(conn, run_id, "stopped", 0, 0, 0, 0, 0, "KeyboardInterrupt")
                    return 0
                except Exception as exc:
                    finish_run(conn, run_id, "error", 0, 0, 0, 0, 1, str(exc))
                    print(f"ERROR watch loop {loops}: {exc}", file=sys.stderr)
                if args.once:
                    return 0
                heartbeat_writer_lock(lock_path)
                time.sleep(args.interval)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        release_writer_lock(lock_path)


def parse_skip_item_types(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def ocr_needed_where_clause(skip_item_types: set[str], max_source_pages: int | None) -> tuple[str, list[Any]]:
    clauses = [
        "t.status = 'needs_ocr'",
        "a.content_type = 'application/pdf'",
    ]
    params: list[Any] = []
    if skip_item_types:
        placeholders = ",".join("?" for _ in skip_item_types)
        clauses.append(f"COALESCE(i.item_type, '') NOT IN ({placeholders})")
        params.extend(sorted(skip_item_types))
    if max_source_pages is not None:
        clauses.append("(COALESCE(t.pages_total, 0) = 0 OR t.pages_total <= ?)")
        params.append(max_source_pages)
    return " AND ".join(clauses), params


def count_ocr_needed_candidates(
    conn: sqlite3.Connection,
    skip_item_types: set[str],
    max_source_pages: int | None,
) -> tuple[int, int]:
    total = int(conn.execute("SELECT COUNT(*) FROM pdf_texts WHERE status = 'needs_ocr'").fetchone()[0] or 0)
    where_sql, params = ocr_needed_where_clause(skip_item_types, max_source_pages)
    eligible = int(
        conn.execute(
            f"""
            SELECT COUNT(*)
            FROM pdf_texts AS t
            JOIN attachments AS a ON a.attachment_key = t.attachment_key
            JOIN items AS i ON i.item_key = t.item_key
            WHERE {where_sql}
            """,
            params,
        ).fetchone()[0]
        or 0
    )
    return total, eligible

def write_normalized_text_cache(normalized_cache_root: Path | None, item_key: str, attachment_key: str, source_text: str) -> Path | None:
    if normalized_cache_root is None or not source_text:
        return None
    output_path = fulltext_cache_path(normalized_cache_root, item_key, attachment_key)
    if output_path is None:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalize_pdf_text_for_ai(source_text), encoding="utf-8")
    return output_path

def command_ocr_needed(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 2
    lock_path = None
    try:
        lock_path = acquire_writer_lock(args.db, args.lock_stale_after, args.force_lock)
        with closing(sqlite3.connect(args.db)) as conn:
            init_db(conn)
            run_id = start_run(
                conn,
                "ocr-needed",
                f"only status=needs_ocr; max_pages={args.max_pages}; limit={args.limit}; ocr_language={args.ocr_language}; skip_item_types={args.skip_item_types}; max_source_pages={args.max_source_pages}; normalized_cache_root={args.normalized_cache_root}",
            )
            stats = {"items_seen": 0, "items_processed": 0, "pdfs_seen": 0, "texts_extracted": 0, "errors": 0}
            skip_item_types = parse_skip_item_types(args.skip_item_types)
            total_needs_ocr, eligible_needs_ocr = count_ocr_needed_candidates(conn, skip_item_types, args.max_source_pages)
            where_sql, params_list = ocr_needed_where_clause(skip_item_types, args.max_source_pages)
            query = f"""
                SELECT t.attachment_key, t.item_key, a.pdf_path, a.file_sha256, a.file_mtime
                FROM pdf_texts AS t
                JOIN attachments AS a ON a.attachment_key = t.attachment_key
                JOIN items AS i ON i.item_key = t.item_key
                WHERE {where_sql}
                ORDER BY t.item_key, t.attachment_key
            """
            params: tuple[Any, ...] = tuple(params_list)
            if args.limit is not None:
                query += " LIMIT ?"
                params = tuple(params_list + [args.limit])
            rows = conn.execute(query, params).fetchall()
            stats["items_seen"] = len(rows)
            try:
                for attachment_key, item_key, pdf_path, file_sha256, file_mtime in rows:
                    stats["items_processed"] += 1
                    stats["pdfs_seen"] += 1
                    path = Path(str(pdf_path or ""))
                    if not path.exists():
                        conn.execute(
                            """
                            UPDATE pdf_texts
                            SET status = 'missing_pdf',
                                text_chars = 0,
                                text = NULL,
                                error = 'PDF path is missing or does not exist.',
                                text_cache_path = '',
                                source_file_sha256 = ?,
                                source_file_mtime = ?,
                                extracted_at = ?
                            WHERE attachment_key = ?
                            """,
                            (file_sha256, file_mtime, utc_now(), attachment_key),
                        )
                        stats["errors"] += 1
                        heartbeat_run(conn, run_id, stats, lock_path)
                        continue
                    result = extract_pdf_text_with_timeout(
                        path,
                        args.max_pages,
                        args.pdf_timeout,
                        True,
                        args.ocr_language,
                        args.ocr_dpi,
                    )
                    cache_path = None
                    normalized_cache_path = None
                    if result.text and result.status in {"ok", "needs_ocr"}:
                        cache_path = write_fulltext_cache(args.fulltext_cache_root, str(item_key), str(attachment_key), result.text)
                        normalized_cache_path = write_normalized_text_cache(args.normalized_cache_root, str(item_key), str(attachment_key), result.text)
                    conn.execute(
                        """
                        UPDATE pdf_texts
                        SET extraction_method = ?,
                            status = ?,
                            pages_total = ?,
                            pages_extracted = ?,
                            pages_with_text = ?,
                            text_chars = ?,
                            text = NULL,
                            error = ?,
                            text_cache_path = ?,
                            text_normalized_cache_path = ?,
                            source_file_sha256 = ?,
                            source_file_mtime = ?,
                            extracted_at = ?
                        WHERE attachment_key = ?
                        """,
                        (
                            result.method,
                            result.status,
                            result.pages_total,
                            result.pages_extracted,
                            result.pages_with_text,
                            len(result.text),
                            clean_text(result.error),
                            clean_text(str(cache_path) if cache_path else ""),
                            clean_text(str(normalized_cache_path) if normalized_cache_path else ""),
                            file_sha256,
                            file_mtime,
                            utc_now(),
                            attachment_key,
                        ),
                    )
                    if result.status == "ok":
                        stats["texts_extracted"] += 1
                    elif result.status == "error":
                        stats["errors"] += 1
                    heartbeat_run(conn, run_id, stats, lock_path)
                finish_run(conn, run_id, "ok", **stats)
            except KeyboardInterrupt:
                finish_run(conn, run_id, "stopped", **stats, notes="KeyboardInterrupt")
                return 130
            except Exception as exc:
                stats["errors"] += 1
                finish_run(conn, run_id, "error", **stats, notes=str(exc))
                raise
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        release_writer_lock(lock_path)
    print("OK: processed local needs_ocr PDF records")
    print(f"needs_ocr_total: {total_needs_ocr}")
    print(f"eligible_after_skip_rules: {eligible_needs_ocr}")
    print(f"skipped_by_type_or_length: {total_needs_ocr - eligible_needs_ocr}")
    print(f"candidates: {stats['items_seen']}")
    print(f"processed: {stats['items_processed']}")
    print(f"ocr_ok: {stats['texts_extracted']}")
    print(f"errors: {stats['errors']}")
    print(f"fulltext_cache_root: {args.fulltext_cache_root}")
    print(f"normalized_cache_root: {args.normalized_cache_root}")
    return 0

def command_export_text_cache(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 2
    lock_path = None
    try:
        lock_path = acquire_writer_lock(args.db, args.lock_stale_after, args.force_lock)
        with closing(sqlite3.connect(args.db)) as conn:
            init_db(conn)
            stats = materialize_pdf_text_cache(conn, args.fulltext_cache_root, args.overwrite)
            conn.commit()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        release_writer_lock(lock_path)
    print(f"OK: exported or linked PDF text cache -> {args.fulltext_cache_root}")
    print(f"exported: {stats['exported']}")
    print(f"linked_existing: {stats['linked_existing']}")
    print(f"skipped_no_text_or_cache: {stats['skipped']}")
    return 0


def command_slim_db(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 2
    lock_path = None
    before_size = args.db.stat().st_size
    try:
        lock_path = acquire_writer_lock(args.db, args.lock_stale_after, args.force_lock)
        with closing(sqlite3.connect(args.db)) as conn:
            init_db(conn)
            inline_row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(length(text)), 0) FROM pdf_texts WHERE COALESCE(text, '') != ''"
            ).fetchone()
            inline_rows = int(inline_row[0] or 0)
            inline_bytes = int(inline_row[1] or 0)
            stats = materialize_pdf_text_cache(conn, args.fulltext_cache_root, args.overwrite_cache)
            dropped_fts = drop_legacy_fts_tables(conn)
            cleared = conn.execute(
                "UPDATE pdf_texts SET text = NULL WHERE COALESCE(text, '') != ''"
            ).rowcount
            conn.commit()
            if not args.no_vacuum:
                conn.execute("VACUUM")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        release_writer_lock(lock_path)
    after_size = args.db.stat().st_size
    print(f"OK: slimmed SQLite database -> {args.db}")
    print(f"fulltext_cache_root: {args.fulltext_cache_root}")
    print(f"inline_text_rows_before: {inline_rows}")
    print(f"inline_text_bytes_before: {inline_bytes}")
    print(f"cache_exported: {stats['exported']}")
    print(f"cache_linked_existing: {stats['linked_existing']}")
    print(f"cache_skipped_no_text_or_cache: {stats['skipped']}")
    print(f"legacy_fts_tables_dropped: {dropped_fts}")
    print(f"inline_text_rows_cleared: {cleared}")
    print(f"size_before_bytes: {before_size}")
    print(f"size_after_bytes: {after_size}")
    return 0

def command_normalize_text_cache(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 2
    lock_path = None
    normalized_count = 0
    skipped = 0
    try:
        lock_path = acquire_writer_lock(args.db, args.lock_stale_after, args.force_lock)
        with closing(sqlite3.connect(args.db)) as conn:
            init_db(conn)
            args.normalized_cache_root.mkdir(parents=True, exist_ok=True)
            query = """
                SELECT attachment_key, item_key, text, text_cache_path
                FROM pdf_texts
                WHERE status = 'ok'
                  AND (COALESCE(text_cache_path, '') != '' OR COALESCE(text, '') != '')
            """
            params_list: list[Any] = []
            if args.attachment_key:
                query += " AND attachment_key = ?"
                params_list.append(args.attachment_key)
            if args.only_missing:
                query += " AND COALESCE(text_normalized_cache_path, '') = ''"
            query += " ORDER BY item_key, attachment_key"
            params: tuple[Any, ...] = tuple(params_list)
            if args.limit is not None:
                query += " LIMIT ?"
                params = tuple(params_list + [args.limit])
            rows = conn.execute(query, params).fetchall()
            for attachment_key, item_key, text, text_cache_path in rows:
                source_path = Path(str(text_cache_path)) if text_cache_path else None
                if source_path and source_path.exists():
                    source_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
                else:
                    source_text = str(text or "")
                if not source_text.strip():
                    skipped += 1
                    continue
                output_path = fulltext_cache_path(args.normalized_cache_root, str(item_key), str(attachment_key))
                if output_path is None:
                    skipped += 1
                    continue
                if output_path.exists() and not args.overwrite:
                    skipped += 1
                else:
                    output_path.write_text(normalize_pdf_text_for_ai(source_text), encoding="utf-8")
                    normalized_count += 1
                conn.execute(
                    """
                    UPDATE pdf_texts
                    SET text_normalized_cache_path = ?
                    WHERE attachment_key = ?
                    """,
                    (str(output_path.resolve()), attachment_key),
                )
            conn.commit()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        release_writer_lock(lock_path)
    print(f"OK: normalized PDF texts -> {args.normalized_cache_root}")
    print(f"normalized: {normalized_count}")
    print(f"linked: {normalized_count + skipped}")
    print(f"skipped_existing_or_empty: {skipped}")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 2
    with closing(sqlite3.connect(args.db)) as conn:
        init_db(conn)
        if args.recover_stale:
            recovered = recover_stale_runs(conn, args.stale_after, "summary")
            print(f"recovered_stale_runs: {recovered}")
        tables = {
            "items": "SELECT COUNT(*) FROM items WHERE zotero_deleted = 0",
            "attachments": "SELECT COUNT(*) FROM attachments",
            "pdf_attachments": "SELECT COUNT(*) FROM attachments WHERE content_type = 'application/pdf'",
            "existing_pdfs": "SELECT COUNT(*) FROM attachments WHERE content_type = 'application/pdf' AND file_exists = 1",
            "pdf_text_ok": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'ok'",
            "pdf_text_ok_with_cache_path": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'ok' AND COALESCE(text_cache_path, '') != ''",
            "pdf_text_ok_with_normalized_cache_path": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'ok' AND COALESCE(text_normalized_cache_path, '') != ''",
            "pdf_text_rows_with_inline_text": "SELECT COUNT(*) FROM pdf_texts WHERE COALESCE(text, '') != ''",
            "pdf_text_inline_chars": "SELECT COALESCE(SUM(length(text)), 0) FROM pdf_texts",
            "pdf_text_ocr_ok": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'ok' AND extraction_method = 'ocr'",
            "pdf_text_needs_ocr": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'needs_ocr'",
            "pdf_missing": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'missing_pdf'",
            "pdf_errors": "SELECT COUNT(*) FROM pdf_texts WHERE status = 'error'",
            "pdf_text_pending": """
                SELECT COUNT(*)
                FROM attachments AS a
                LEFT JOIN pdf_texts AS t ON t.attachment_key = a.attachment_key
                WHERE a.content_type = 'application/pdf'
                  AND t.attachment_key IS NULL
            """,
        }
        for label, query in tables.items():
            value = conn.execute(query).fetchone()[0]
            print(f"{label}: {value}")
        print("latest_runs:")
        for row in conn.execute(
            """
            SELECT run_id, mode, started_at, heartbeat_at, finished_at, status,
                   process_id, items_processed, texts_extracted, errors
            FROM sync_runs
            ORDER BY run_id DESC
            LIMIT 5
            """
        ):
            print("  " + " | ".join(str(value) for value in row))
    return 0


def command_recover_runs(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 2
    with closing(sqlite3.connect(args.db)) as conn:
        init_db(conn)
        recovered = recover_stale_runs(conn, args.stale_after, "recover-runs")
    print(f"recovered_stale_runs: {recovered}")
    return 0


def command_ocr_check(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []
    try:
        import fitz  # type: ignore[import-not-found]

        checks.append(("PyMuPDF", True, str(getattr(fitz, "__doc__", "")).splitlines()[0] if getattr(fitz, "__doc__", "") else "ok"))
    except ImportError as exc:
        checks.append(("PyMuPDF", False, str(exc)))
    try:
        from PIL import Image  # type: ignore[import-not-found]

        checks.append(("Pillow", True, str(getattr(Image, "__version__", "ok"))))
    except ImportError as exc:
        checks.append(("Pillow", False, str(exc)))
    try:
        import pytesseract  # type: ignore[import-not-found]

        checks.append(("pytesseract", True, str(getattr(pytesseract, "__version__", "ok"))))
    except ImportError as exc:
        checks.append(("pytesseract", False, str(exc)))
    tesseract_path = resolve_tesseract_cmd()
    checks.append(("tesseract", bool(tesseract_path), tesseract_path or f"not found; expected local build at {default_tesseract_exe()}"))
    tessdata_dir = default_tessdata_dir()
    for language in ("eng", "chi_sim"):
        traineddata = tessdata_dir / f"{language}.traineddata"
        checks.append((f"tessdata:{language}", traineddata.exists(), str(traineddata)))

    ok = True
    for name, passed, detail in checks:
        ok = ok and passed
        print(f"{name}: {'ok' if passed else 'missing'} - {detail}")
    if not ok:
        print("NOTE: install Python OCR packages with tools\\runtime\\build_local_python_env.ps1 and use tools\\runtime\\ensure_ocr_needed.py for Tesseract setup.")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite output database.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Zotero Local API base URL.")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Zotero user ID for Local API, usually 0.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="One-shot full or incremental sync.")
    sync_parser.add_argument("--no-pdf-text", action="store_true", help="Index PDF metadata but do not extract text.")
    sync_parser.add_argument("--force-extract", action="store_true", help="Re-extract existing PDF texts.")
    sync_parser.add_argument("--max-pages", type=int, default=None, help="Optional page limit per PDF.")
    sync_parser.add_argument("--pdf-timeout", type=int, default=300, help="Per-PDF extraction timeout in seconds.")
    sync_parser.add_argument("--fulltext-cache-root", type=Path, default=DEFAULT_FULLTEXT_CACHE_ROOT, help="Text cache root; ITEMKEY__ATTACHMENTKEY.txt is reused before PDF extraction and written after extraction, with legacy ITEMKEY.txt fallback.")
    sync_parser.add_argument("--ocr", action="store_true", help="Run local OCR for PDFs that pypdf cannot extract.")
    sync_parser.add_argument("--ocr-language", default=DEFAULT_OCR_LANGUAGE, help="Tesseract language list for OCR.")
    sync_parser.add_argument("--ocr-dpi", type=int, default=DEFAULT_OCR_DPI, help="PDF render DPI for OCR.")
    sync_parser.add_argument("--stale-after", type=int, default=DEFAULT_STALE_AFTER_SECONDS, help="Recover running sync records older than this many seconds.")
    sync_parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS, help="Recover writer lock files older than this many seconds.")
    sync_parser.add_argument("--force-lock", action="store_true", help="Force takeover of the cloud DB writer lock.")
    sync_parser.add_argument("--max-items", type=int, default=None, help="Optional item limit for testing.")
    sync_parser.add_argument("--max-process-items", type=int, default=None, help="Stop after processing this many items.")
    sync_parser.add_argument("--only-new-or-modified", action="store_true", help="Skip unchanged items already in the DB.")
    sync_parser.set_defaults(func=command_sync)

    watch_parser = subparsers.add_parser("watch", help="Poll Zotero for new or modified items.")
    watch_parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds.")
    watch_parser.add_argument("--once", action="store_true", help="Run one watch loop and exit.")
    watch_parser.add_argument("--no-pdf-text", action="store_true", help="Index PDF metadata but do not extract text.")
    watch_parser.add_argument("--force-extract", action="store_true", help="Re-extract existing PDF texts.")
    watch_parser.add_argument("--max-pages", type=int, default=None, help="Optional page limit per PDF.")
    watch_parser.add_argument("--pdf-timeout", type=int, default=300, help="Per-PDF extraction timeout in seconds.")
    watch_parser.add_argument("--fulltext-cache-root", type=Path, default=DEFAULT_FULLTEXT_CACHE_ROOT, help="Text cache root; ITEMKEY__ATTACHMENTKEY.txt is reused before PDF extraction and written after extraction, with legacy ITEMKEY.txt fallback.")
    watch_parser.add_argument("--ocr", action="store_true", help="Run local OCR for PDFs that pypdf cannot extract.")
    watch_parser.add_argument("--ocr-language", default=DEFAULT_OCR_LANGUAGE, help="Tesseract language list for OCR.")
    watch_parser.add_argument("--ocr-dpi", type=int, default=DEFAULT_OCR_DPI, help="PDF render DPI for OCR.")
    watch_parser.add_argument("--stale-after", type=int, default=DEFAULT_STALE_AFTER_SECONDS, help="Recover running watch records older than this many seconds.")
    watch_parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS, help="Recover writer lock files older than this many seconds.")
    watch_parser.add_argument("--force-lock", action="store_true", help="Force takeover of the cloud DB writer lock.")
    watch_parser.add_argument("--max-items", type=int, default=None, help="Optional item limit for testing.")
    watch_parser.add_argument("--max-process-items", type=int, default=None, help="Stop each watch loop after processing this many items.")
    watch_parser.set_defaults(func=command_watch)

    ocr_needed_parser = subparsers.add_parser("ocr-needed", help="Run OCR only for local PDF records currently marked as needs_ocr.")
    ocr_needed_parser.add_argument("--fulltext-cache-root", type=Path, default=DEFAULT_FULLTEXT_CACHE_ROOT, help="Text cache root for OCR output ITEMKEY__ATTACHMENTKEY.txt files.")
    ocr_needed_parser.add_argument("--normalized-cache-root", type=Path, default=DEFAULT_NORMALIZED_CACHE_ROOT, help="Normalized text cache root written after OCR succeeds.")
    ocr_needed_parser.add_argument("--max-pages", type=int, default=None, help="Optional page limit per PDF.")
    ocr_needed_parser.add_argument("--pdf-timeout", type=int, default=300, help="Per-PDF OCR timeout in seconds.")
    ocr_needed_parser.add_argument("--ocr-language", default=DEFAULT_OCR_LANGUAGE, help="Tesseract language list for OCR.")
    ocr_needed_parser.add_argument("--ocr-dpi", type=int, default=DEFAULT_OCR_DPI, help="PDF render DPI for OCR.")
    ocr_needed_parser.add_argument("--limit", type=int, default=None, help="Optional number of needs_ocr PDFs to process.")
    ocr_needed_parser.add_argument("--max-source-pages", type=int, default=DEFAULT_OCR_MAX_SOURCE_PAGES, help="Skip needs_ocr PDFs whose known source page count is above this threshold; use 0 to disable.")
    ocr_needed_parser.add_argument("--skip-item-types", default=",".join(DEFAULT_OCR_SKIP_ITEM_TYPES), help="Comma-separated Zotero item types to skip for OCR, default book,thesis.")
    ocr_needed_parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS, help="Recover writer lock files older than this many seconds.")
    ocr_needed_parser.add_argument("--force-lock", action="store_true", help="Force takeover of the cloud DB writer lock.")
    ocr_needed_parser.set_defaults(func=command_ocr_needed)
    summary_parser = subparsers.add_parser("summary", help="Print database summary.")
    summary_parser.add_argument("--recover-stale", action="store_true", help="Recover stale running records before printing the summary.")
    summary_parser.add_argument("--stale-after", type=int, default=DEFAULT_STALE_AFTER_SECONDS, help="Recover running records older than this many seconds.")
    summary_parser.set_defaults(func=command_summary)

    recover_parser = subparsers.add_parser("recover-runs", help="Mark stale running records as interrupted.")
    recover_parser.add_argument("--stale-after", type=int, default=DEFAULT_STALE_AFTER_SECONDS, help="Recover running records older than this many seconds.")
    recover_parser.set_defaults(func=command_recover_runs)

    export_parser = subparsers.add_parser("export-text-cache", help="Export successful PDF texts from SQLite into one text file per PDF attachment and link paths back into SQLite.")
    export_parser.add_argument("--fulltext-cache-root", type=Path, required=True, help="Directory for ITEMKEY__ATTACHMENTKEY.txt files.")
    export_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing exported text files.")
    export_parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS, help="Recover writer lock files older than this many seconds.")
    export_parser.add_argument("--force-lock", action="store_true", help="Force takeover of the cloud DB writer lock.")
    export_parser.set_defaults(func=command_export_text_cache)

    slim_parser = subparsers.add_parser("slim-db", help="Move legacy inline PDF text out of SQLite, drop FTS tables, and VACUUM the database.")
    slim_parser.add_argument("--fulltext-cache-root", type=Path, default=DEFAULT_FULLTEXT_CACHE_ROOT, help="Directory for ITEMKEY__ATTACHMENTKEY.txt files before clearing inline text.")
    slim_parser.add_argument("--overwrite-cache", action="store_true", help="Overwrite existing cache files when exporting legacy inline text.")
    slim_parser.add_argument("--no-vacuum", action="store_true", help="Do not run VACUUM after clearing inline text and FTS tables.")
    slim_parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS, help="Recover writer lock files older than this many seconds.")
    slim_parser.add_argument("--force-lock", action="store_true", help="Force takeover of the cloud DB writer lock.")
    slim_parser.set_defaults(func=command_slim_db)
    normalize_parser = subparsers.add_parser("normalize-text-cache", help="Normalize exported PDF text files for downstream AI reading and link paths back into SQLite.")
    normalize_parser.add_argument("--normalized-cache-root", type=Path, default=DEFAULT_NORMALIZED_CACHE_ROOT, help="Directory for normalized ITEMKEY__ATTACHMENTKEY.txt files.")
    normalize_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing normalized text files.")
    normalize_parser.add_argument("--limit", type=int, default=None, help="Optional number of PDF texts to normalize.")
    normalize_parser.add_argument("--attachment-key", default="", help="Normalize only one PDF attachment key.")
    normalize_parser.add_argument("--only-missing", action="store_true", help="Normalize only rows with empty text_normalized_cache_path.")
    normalize_parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS, help="Recover writer lock files older than this many seconds.")
    normalize_parser.add_argument("--force-lock", action="store_true", help="Force takeover of the cloud DB writer lock.")
    normalize_parser.set_defaults(func=command_normalize_text_cache)

    ocr_check_parser = subparsers.add_parser("ocr-check", help="Check local OCR Python packages and Tesseract executable.")
    ocr_check_parser.set_defaults(func=command_ocr_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "max_pages", None) is not None and args.max_pages < 1:
        parser.error("--max-pages must be >= 1")
    if getattr(args, "pdf_timeout", 1) < 1:
        parser.error("--pdf-timeout must be >= 1")
    if getattr(args, "ocr_dpi", DEFAULT_OCR_DPI) < 72:
        parser.error("--ocr-dpi must be >= 72")
    if getattr(args, "stale_after", DEFAULT_STALE_AFTER_SECONDS) < 0:
        parser.error("--stale-after must be >= 0")
    if getattr(args, "lock_stale_after", DEFAULT_LOCK_STALE_AFTER_SECONDS) < 0:
        parser.error("--lock-stale-after must be >= 0")
    if getattr(args, "max_source_pages", None) == 0:
        args.max_source_pages = None
    if getattr(args, "max_source_pages", None) is not None and args.max_source_pages < 0:
        parser.error("--max-source-pages must be >= 0")
    if getattr(args, "max_process_items", None) is not None and args.max_process_items < 1:
        parser.error("--max-process-items must be >= 1")
    if getattr(args, "limit", None) is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    if getattr(args, "interval", 1) < 1:
        parser.error("--interval must be >= 1")
    return args.func(args)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "__extract_pdf_worker":
        raise SystemExit(command_extract_pdf_worker(sys.argv[2:]))
    raise SystemExit(main())
