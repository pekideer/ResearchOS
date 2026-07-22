"""Read Zotero-native PDF annotations into the ResearchOS parent document.

The command is read-only against Zotero. It scans only explicitly selected items or
items that already have centralized reading cards. Omit ``--write-mirror`` for a
machine-readable dry run that does not change the parent SQLite document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.reading_cards.card_common import reading_card_identity
from tools.researchos_outputs import (
    CORPUS_READING_CARDS_ROOT,
    CORPUS_ZOTERO_LIBRARY_DB,
    M005_READING_CARD_ANNOTATION_SYNC,
    ensure_output_dirs,
    write_json,
)
from tools.zotero.zotero_library_index import (
    DEFAULT_API_BASE,
    DEFAULT_LOCK_STALE_AFTER_SECONDS,
    DEFAULT_USER_ID,
    ZoteroClient,
    acquire_writer_lock,
    init_db,
    release_writer_lock,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decoded_json_value(value: Any) -> Any:
    """Decode Local API fields that may contain JSON encoded as a string."""
    decoded = value
    for _ in range(2):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            break
    return decoded


def annotation_hash(data: dict[str, Any]) -> str:
    fields = {
        "annotationType": data.get("annotationType", ""),
        "annotationText": data.get("annotationText", ""),
        "annotationComment": data.get("annotationComment", ""),
        "annotationColor": data.get("annotationColor", ""),
        "annotationPageLabel": data.get("annotationPageLabel", ""),
        "annotationSortIndex": data.get("annotationSortIndex", ""),
        "annotationPosition": decoded_json_value(data.get("annotationPosition", {})),
        "tags": data.get("tags", []),
    }
    return hashlib.sha256(canonical_json(fields).encode("utf-8")).hexdigest()


def card_item_map(cards_root: Path) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    if not cards_root.exists():
        return mapping
    for path in sorted(cards_root.glob("*.md")):
        try:
            body = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        _card_id, item_key = reading_card_identity(body, path)
        if item_key:
            mapping.setdefault(item_key, []).append(path.as_posix())
    return mapping


def is_pdf_attachment(row: dict[str, Any]) -> bool:
    data = row.get("data", {}) or {}
    if data.get("itemType") != "attachment":
        return False
    title = str(data.get("title") or "")
    filename = str(data.get("filename") or "")
    return data.get("contentType") == "application/pdf" or title.lower().endswith(".pdf") or filename.lower().endswith(".pdf")


def normalize_annotation(row: dict[str, Any], item_key: str, attachment_key: str, now: str) -> dict[str, Any]:
    data = row.get("data", {}) or {}
    key = str(row.get("key") or data.get("key") or "").upper()
    if not key or data.get("itemType") != "annotation":
        raise ValueError("annotation row is missing a valid key or itemType")
    return {
        "annotation_key": key,
        "attachment_key": attachment_key,
        "parent_item_key": item_key,
        "version": int(row.get("version") or data.get("version") or 0),
        "annotation_type": str(data.get("annotationType") or ""),
        "annotation_text": str(data.get("annotationText") or ""),
        "annotation_comment": str(data.get("annotationComment") or ""),
        "annotation_color": str(data.get("annotationColor") or ""),
        "annotation_page_label": str(data.get("annotationPageLabel") or ""),
        "annotation_sort_index": str(data.get("annotationSortIndex") or ""),
        "annotation_position_json": canonical_json(decoded_json_value(data.get("annotationPosition") or {})),
        "tags_json": canonical_json(data.get("tags") or []),
        "raw_json": canonical_json(row),
        "date_added": str(data.get("dateAdded") or ""),
        "date_modified": str(data.get("dateModified") or ""),
        "content_hash": annotation_hash(data),
        "first_seen_at": now,
        "last_seen_at": now,
        "last_synced_at": now,
        "zotero_deleted": 0,
    }


def upsert_annotation(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO annotations (
          annotation_key, attachment_key, parent_item_key, version,
          annotation_type, annotation_text, annotation_comment, annotation_color,
          annotation_page_label, annotation_sort_index, annotation_position_json,
          tags_json, raw_json, date_added, date_modified, content_hash,
          first_seen_at, last_seen_at, last_synced_at, zotero_deleted
        ) VALUES (
          :annotation_key, :attachment_key, :parent_item_key, :version,
          :annotation_type, :annotation_text, :annotation_comment, :annotation_color,
          :annotation_page_label, :annotation_sort_index, :annotation_position_json,
          :tags_json, :raw_json, :date_added, :date_modified, :content_hash,
          :first_seen_at, :last_seen_at, :last_synced_at, :zotero_deleted
        )
        ON CONFLICT(annotation_key) DO UPDATE SET
          attachment_key=excluded.attachment_key,
          parent_item_key=excluded.parent_item_key,
          version=excluded.version,
          annotation_type=excluded.annotation_type,
          annotation_text=excluded.annotation_text,
          annotation_comment=excluded.annotation_comment,
          annotation_color=excluded.annotation_color,
          annotation_page_label=excluded.annotation_page_label,
          annotation_sort_index=excluded.annotation_sort_index,
          annotation_position_json=excluded.annotation_position_json,
          tags_json=excluded.tags_json,
          raw_json=excluded.raw_json,
          date_added=excluded.date_added,
          date_modified=excluded.date_modified,
          content_hash=excluded.content_hash,
          last_seen_at=excluded.last_seen_at,
          last_synced_at=excluded.last_synced_at,
          zotero_deleted=0
        """,
        record,
    )


def soft_delete_missing(conn: sqlite3.Connection, attachment_key: str, seen_keys: set[str], now: str) -> int:
    rows = conn.execute(
        "SELECT annotation_key FROM annotations WHERE attachment_key = ? AND COALESCE(zotero_deleted, 0) = 0",
        (attachment_key,),
    ).fetchall()
    missing = [str(row[0]) for row in rows if str(row[0]) not in seen_keys]
    for key in missing:
        conn.execute(
            "UPDATE annotations SET zotero_deleted = 1, last_synced_at = ? WHERE annotation_key = ?",
            (now, key),
        )
    return len(missing)


def scan_item(
    client: ZoteroClient,
    item_key: str,
    annotation_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    children = client.fetch_paged(f"items/{item_key}/children")
    attachments = [row for row in children if is_pdf_attachment(row)]
    if annotation_rows is None:
        annotation_rows = client.fetch_paged("items", {"itemType": "annotation"})
    records: list[dict[str, Any]] = []
    scans: list[dict[str, Any]] = []
    now = utc_now()
    for attachment in attachments:
        attachment_key = str(attachment.get("key") or attachment.get("data", {}).get("key") or "").upper()
        if not attachment_key:
            continue
        matched_rows = [
            row
            for row in annotation_rows
            if (row.get("data", {}) or {}).get("itemType") == "annotation"
            and str((row.get("data", {}) or {}).get("parentItem") or "").upper() == attachment_key
        ]
        normalized = [normalize_annotation(row, item_key, attachment_key, now) for row in matched_rows]
        records.extend(normalized)
        scans.append(
            {
                "item_key": item_key,
                "attachment_key": attachment_key,
                "complete": True,
                "annotation_keys": [row["annotation_key"] for row in normalized],
            }
        )
    return records, scans


def start_run(conn: sqlite3.Connection, scope: str) -> int:
    cursor = conn.execute(
        "INSERT INTO annotation_sync_runs(started_at, status, scope) VALUES (?, 'running', ?)",
        (utc_now(), scope),
    )
    return int(cursor.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, status: str, summary: dict[str, Any], notes: str = "") -> None:
    conn.execute(
        """
        UPDATE annotation_sync_runs SET
          finished_at = ?, status = ?, items_scanned = ?, attachments_scanned = ?,
          annotations_seen = ?, annotations_upserted = ?, annotations_soft_deleted = ?,
          errors = ?, notes = ?
        WHERE run_id = ?
        """,
        (
            utc_now(),
            status,
            summary["items_scanned"],
            summary["attachments_scanned"],
            summary["annotations_seen"],
            summary["annotations_upserted"],
            summary["annotations_soft_deleted"],
            summary["errors"],
            notes,
            run_id,
        ),
    )


def preview_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "annotation_key": row["annotation_key"],
            "attachment_key": row["attachment_key"],
            "parent_item_key": row["parent_item_key"],
            "annotation_type": row["annotation_type"],
            "page_label": row["annotation_page_label"],
            "has_text": bool(row["annotation_text"].strip()),
            "has_comment": bool(row["annotation_comment"].strip()),
            "content_hash": row["content_hash"],
        }
        for row in records
    ]


def run(args: argparse.Namespace) -> int:
    if not args.allow_local_api:
        raise SystemExit("Refusing Local API access without --allow-local-api")
    root = Path(args.root).resolve() if args.root else RESEARCHOS_ROOT
    ensure_output_dirs(root)
    cards_root = Path(args.cards_root)
    if not cards_root.is_absolute():
        cards_root = root / cards_root
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = root / db_path
    item_map = card_item_map(cards_root)
    item_keys = [str(key).upper() for key in (args.item_key or [])]
    if not item_keys:
        item_keys = sorted(item_map)
    if not item_keys:
        raise SystemExit("No Zotero item keys selected and no centralized reading cards were mapped")

    client = ZoteroClient(args.api_base, args.user_id)
    all_records: list[dict[str, Any]] = []
    all_scans: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    items_scanned = 0
    try:
        annotation_rows = client.fetch_paged("items", {"itemType": "annotation"})
    except Exception as exc:
        annotation_rows = []
        errors.append({"item_key": "*annotation-index*", "error_type": type(exc).__name__, "message": str(exc)})
    scan_item_keys = item_keys if not errors else []
    for item_key in scan_item_keys:
        try:
            records, scans = scan_item(client, item_key, annotation_rows)
            all_records.extend(records)
            all_scans.extend(scans)
            items_scanned += 1
        except Exception as exc:
            errors.append({"item_key": item_key, "error_type": type(exc).__name__, "message": str(exc)})

    summary: dict[str, Any] = {
        "generated_at": utc_now(),
        "mode": "write_mirror" if args.write_mirror else "dry_run",
        "scope": "explicit_items" if args.item_key else "centralized_reading_cards",
        "items_selected": len(item_keys),
        "items_scanned": items_scanned,
        "attachments_scanned": len(all_scans),
        "annotations_seen": len(all_records),
        "annotations_upserted": 0,
        "annotations_soft_deleted": 0,
        "errors": len(errors),
    }

    lock_path: Path | None = None
    if args.write_mirror:
        lock_path = acquire_writer_lock(db_path, args.lock_stale_after, args.force_lock)
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(db_path)) as conn:
                init_db(conn)
                run_id = start_run(conn, summary["scope"])
                try:
                    for record in all_records:
                        upsert_annotation(conn, record)
                    summary["annotations_upserted"] = len(all_records)
                    now = utc_now()
                    for scan in all_scans:
                        summary["annotations_soft_deleted"] += soft_delete_missing(
                            conn,
                            scan["attachment_key"],
                            set(scan["annotation_keys"]),
                            now,
                        )
                    finish_run(conn, run_id, "ok" if not errors else "partial", summary, canonical_json(errors))
                    conn.commit()
                except Exception as exc:
                    summary["errors"] += 1
                    finish_run(conn, run_id, "error", summary, str(exc))
                    conn.commit()
                    raise
        finally:
            release_writer_lock(lock_path)

    output_dir = root / M005_READING_CARD_ANNOTATION_SYNC / f"{safe_timestamp()}-{'mirror' if args.write_mirror else 'dry-run'}"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary["output_dir"] = str(output_dir.relative_to(root)).replace("\\", "/")
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "annotations-preview.json", preview_rows(all_records))
    write_json(output_dir / "scan-completeness.json", all_scans)
    write_json(output_dir / "errors.json", errors)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--db", default=str(CORPUS_ZOTERO_LIBRARY_DB))
    parser.add_argument("--cards-root", default=str(CORPUS_READING_CARDS_ROOT / "cards"))
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--item-key", action="append", help="Scan one parent item; may be repeated.")
    parser.add_argument("--allow-local-api", action="store_true")
    parser.add_argument("--write-mirror", action="store_true", help="Persist annotations in the ResearchOS parent document.")
    parser.add_argument("--lock-stale-after", type=int, default=DEFAULT_LOCK_STALE_AFTER_SECONDS)
    parser.add_argument("--force-lock", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.lock_stale_after < 0:
        raise SystemExit("--lock-stale-after must be >= 0")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
