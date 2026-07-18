"""Fast Zotero Local API sync for collection trees and project assignments.

This script is intentionally lightweight. It updates the ResearchOS Zotero
parent SQLite mirror for collections and, optionally, item membership under one
project collection path. It does not read PDFs, extract text, write Zotero, or
touch zotero.sqlite.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener


RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.zotero.zotero_local_api import year_from_date
from tools.researchos_outputs import CORPUS_ZOTERO_LIBRARY_DB

DEFAULT_DB = RESEARCHOS_ROOT / CORPUS_ZOTERO_LIBRARY_DB
DEFAULT_API_BASE = "http://127.0.0.1:23119/api"
DEFAULT_USER_ID = "0"
PAGE_LIMIT = 100
TIMEOUT_SECONDS = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--project-path", help="Optional collection path whose direct and child item memberships should be refreshed.")
    parser.add_argument("--include-items", action="store_true", help="Refresh item_collections for collections under --project-path.")
    return parser


class ZoteroClient:
    def __init__(self, api_base: str, user_id: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.user_id = user_id

    def fetch_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        query = "?" + urlencode(params or {})
        url = f"{self.api_base}/users/{self.user_id}/{endpoint.lstrip('/')}{query}"
        request = Request(url, headers={"Zotero-API-Version": "3"})
        with build_opener(ProxyHandler({})).open(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    def fetch_paged(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        start = 0
        while True:
            page_params = dict(params or {})
            page_params.update({"limit": PAGE_LIMIT, "start": start})
            page = self.fetch_json(endpoint, page_params)
            if not isinstance(page, list) or not page:
                break
            records.extend(page)
            if len(page) < PAGE_LIMIT:
                break
            start += PAGE_LIMIT
        return records


def collection_rows(collections: list[dict[str, Any]]) -> tuple[list[dict[str, str]], dict[str, str]]:
    by_key = {record["key"]: record for record in collections}
    path_cache: dict[str, str] = {}

    def path_for(key: str) -> str:
        if key in path_cache:
            return path_cache[key]
        record = by_key[key]
        data = record.get("data", {})
        name = str(data.get("name") or "")
        parent = data.get("parentCollection")
        if parent and parent in by_key:
            value = f"{path_for(str(parent))}/{name}"
        else:
            value = name
        path_cache[key] = value
        return value

    rows: list[dict[str, str]] = []
    for record in collections:
        data = record.get("data", {})
        key = str(record.get("key") or data.get("key") or "")
        if not key:
            continue
        rows.append(
            {
                "collection_key": key,
                "name": str(data.get("name") or ""),
                "parent_key": "" if not data.get("parentCollection") else str(data.get("parentCollection")),
                "path": path_for(key),
                "raw_json": json.dumps(record, ensure_ascii=False),
                "last_seen_at": utc_now(),
            }
        )
    return rows, path_cache


def item_row(record: dict[str, Any], path_by_key: dict[str, str]) -> dict[str, Any]:
    data = record.get("data", {})
    item_key = str(record.get("key") or data.get("key") or "")
    collections = [str(key) for key in data.get("collections", []) if str(key)]
    collection_paths = [path_by_key[key] for key in collections if key in path_by_key]
    creators = data.get("creators", [])
    tags = [tag.get("tag", "") for tag in data.get("tags", []) if tag.get("tag")]
    now = utc_now()
    return {
        "item_key": item_key,
        "version": int(record.get("version") or data.get("version") or 0),
        "item_type": str(data.get("itemType") or ""),
        "title": str(data.get("title") or ""),
        "creators_json": json.dumps(creators, ensure_ascii=False),
        "year": year_from_date(str(data.get("date") or "")),
        "date": str(data.get("date") or ""),
        "publication": str(data.get("publicationTitle") or data.get("conferenceName") or data.get("bookTitle") or ""),
        "journal_abbreviation": str(data.get("journalAbbreviation") or ""),
        "doi": str(data.get("DOI") or ""),
        "isbn": str(data.get("ISBN") or ""),
        "url": str(data.get("url") or ""),
        "language": str(data.get("language") or ""),
        "abstract_note": str(data.get("abstractNote") or ""),
        "raw_json": json.dumps(record, ensure_ascii=False),
        "collections_json": json.dumps(collections, ensure_ascii=False),
        "collection_paths_json": json.dumps(collection_paths, ensure_ascii=False),
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "date_added": str(data.get("dateAdded") or ""),
        "date_modified": str(data.get("dateModified") or ""),
        "first_seen_at": now,
        "last_seen_at": now,
        "last_synced_at": now,
        "zotero_deleted": 0,
    }


def upsert_collections(connection: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    connection.executemany(
        """
        INSERT INTO collections(collection_key, name, parent_key, path, raw_json, last_seen_at)
        VALUES(:collection_key, :name, :parent_key, :path, :raw_json, :last_seen_at)
        ON CONFLICT(collection_key) DO UPDATE SET
            name=excluded.name,
            parent_key=excluded.parent_key,
            path=excluded.path,
            raw_json=excluded.raw_json,
            last_seen_at=excluded.last_seen_at
        """,
        rows,
    )


def upsert_items(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    connection.executemany(
        """
        INSERT INTO items(
            item_key, version, item_type, title, creators_json, year, date, publication,
            journal_abbreviation, doi, isbn, url, language, abstract_note, raw_json,
            collections_json, collection_paths_json, tags_json, date_added, date_modified,
            first_seen_at, last_seen_at, last_synced_at, zotero_deleted
        )
        VALUES(
            :item_key, :version, :item_type, :title, :creators_json, :year, :date, :publication,
            :journal_abbreviation, :doi, :isbn, :url, :language, :abstract_note, :raw_json,
            :collections_json, :collection_paths_json, :tags_json, :date_added, :date_modified,
            :first_seen_at, :last_seen_at, :last_synced_at, :zotero_deleted
        )
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
        rows,
    )


def main() -> int:
    args = build_parser().parse_args()
    client = ZoteroClient(args.api_base, args.user_id)
    collections = client.fetch_paged("collections")
    collection_table_rows, path_by_key = collection_rows(collections)
    project_keys: list[str] = []
    item_rows: list[dict[str, Any]] = []
    item_collection_rows: list[tuple[str, str, str]] = []

    if args.include_items:
        if not args.project_path:
            raise SystemExit("--include-items requires --project-path")
        project_keys = [
            row["collection_key"]
            for row in collection_table_rows
            if row["path"] == args.project_path or row["path"].startswith(args.project_path + "/")
        ]
        for collection_key in project_keys:
            for record in client.fetch_paged(f"collections/{collection_key}/items/top"):
                row = item_row(record, path_by_key)
                if row["item_key"]:
                    item_rows.append(row)
                    item_collection_rows.append((row["item_key"], collection_key, path_by_key[collection_key]))

    db_path = Path(args.db)
    with sqlite3.connect(str(db_path), timeout=30) as connection:
        started = utc_now()
        cursor = connection.execute(
            """
            INSERT INTO sync_runs(mode, started_at, status, notes)
            VALUES(?, ?, ?, ?)
            """,
            (
                "fast-collection-sync",
                started,
                "running",
                f"collections={len(collection_table_rows)}; project_path={args.project_path or ''}; include_items={args.include_items}",
            ),
        )
        run_id = int(cursor.lastrowid)
        try:
            upsert_collections(connection, collection_table_rows)
            if args.include_items and project_keys:
                placeholders = ",".join("?" for _ in project_keys)
                connection.execute(
                    f"DELETE FROM item_collections WHERE collection_key IN ({placeholders})",
                    project_keys,
                )
                upsert_items(connection, item_rows)
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO item_collections(item_key, collection_key, collection_path)
                    VALUES(?, ?, ?)
                    """,
                    item_collection_rows,
                )
            connection.execute(
                """
                UPDATE sync_runs
                SET finished_at=?, status=?, items_seen=?, items_processed=?, errors=?
                WHERE run_id=?
                """,
                (utc_now(), "ok", len(item_rows), len(item_rows), 0, run_id),
            )
        except Exception:
            connection.execute(
                "UPDATE sync_runs SET finished_at=?, status=?, errors=? WHERE run_id=?",
                (utc_now(), "error", 1, run_id),
            )
            raise

    print(f"collections_synced: {len(collection_table_rows)}")
    print(f"project_collections_synced: {len(project_keys)}")
    print(f"project_item_rows_seen: {len(item_rows)}")
    print(f"db: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
