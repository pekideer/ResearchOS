"""Monitor newly added Zotero top-level item metadata without touching PDFs.

This tool compares Zotero Local API top-level item metadata against the
ResearchOS Zotero SQLite parent document. It deliberately reads only item and
collection metadata. It does not request attachment contents, does not open PDF
files, does not read normalized full-text caches, does not classify research
semantics, and does not write to Zotero.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_LIBRARY_DB,
    DOCS_ZOTERO_NEW_ITEM_MONITOR,
    M004_ZOTERO_NEW_ITEM_MONITOR,
)
from tools.zotero.zotero_library_index import (
    collection_maps,
    init_db,
    upsert_collections,
    upsert_item,
)
from tools.zotero.zotero_local_api import (
    DEFAULT_API_BASE,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_ID,
    creators_to_text,
    fetch_json,
    fetch_paged,
    year_from_date,
)


DEFAULT_DB = CORPUS_ZOTERO_LIBRARY_DB
DEFAULT_STATE = M004_ZOTERO_NEW_ITEM_MONITOR / "monitor_state.jsonl"
DEFAULT_LATEST_JSONL = M004_ZOTERO_NEW_ITEM_MONITOR / "new-items-latest.jsonl"
DEFAULT_REPORT_MD = DOCS_ZOTERO_NEW_ITEM_MONITOR / "new-items-report.md"
DEFAULT_REPORT_CSV = M004_ZOTERO_NEW_ITEM_MONITOR / "new-items-report.csv"
TOP_LEVEL_ENDPOINT = "items/top"
SKIP_ITEM_TYPES = {"attachment", "note", "annotation"}

JsonFetcher = Callable[[str, dict[str, Any] | None, int], Any]


@dataclass(frozen=True)
class Watermark:
    date_added: str
    timestamp: datetime
    item_keys: set[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_zotero_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_watermark(db_path: Path) -> Watermark | None:
    if not db_path.exists():
        raise FileNotFoundError(f"ResearchOS Zotero parent document not found: {db_path}")
    rows: list[sqlite3.Row]
    with connect_readonly(db_path) as connection:
        rows = connection.execute(
            """
            SELECT item_key, date_added
            FROM items
            WHERE COALESCE(zotero_deleted, 0) = 0
              AND COALESCE(date_added, '') <> ''
            """
        ).fetchall()
    best_dt: datetime | None = None
    best_raw = ""
    keys: set[str] = set()
    for row in rows:
        raw = str(row["date_added"] or "")
        parsed = parse_zotero_time(raw)
        if parsed is None:
            continue
        if best_dt is None or parsed > best_dt:
            best_dt = parsed
            best_raw = raw
            keys = {str(row["item_key"])}
        elif parsed == best_dt:
            keys.add(str(row["item_key"]))
    if best_dt is None:
        return None
    return Watermark(best_raw, best_dt, keys)


def item_key(item: dict[str, Any]) -> str:
    data = item.get("data", {})
    return str(item.get("key") or data.get("key") or "")


def item_data(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    return data if isinstance(data, dict) else {}


def is_top_level_literature_item(item: dict[str, Any]) -> bool:
    return str(item_data(item).get("itemType") or "") not in SKIP_ITEM_TYPES


def safe_json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def compact_item_record(item: dict[str, Any], detected_at: str, source: str = "zotero-local-api") -> dict[str, Any]:
    data = item_data(item)
    creators = safe_json_list(data.get("creators", []))
    tags = [
        str(tag.get("tag", "")).strip()
        for tag in safe_json_list(data.get("tags", []))
        if isinstance(tag, dict) and str(tag.get("tag", "")).strip()
    ]
    publication = (
        data.get("publicationTitle")
        or data.get("conferenceName")
        or data.get("bookTitle")
        or ""
    )
    return {
        "item_key": item_key(item),
        "item_type": str(data.get("itemType") or ""),
        "title": str(data.get("title") or ""),
        "creators": creators_to_text(creators),
        "year": year_from_date(str(data.get("date") or "")),
        "date": str(data.get("date") or ""),
        "publication": str(publication),
        "doi": str(data.get("DOI") or ""),
        "url": str(data.get("url") or ""),
        "abstract_note": str(data.get("abstractNote") or ""),
        "date_added": str(data.get("dateAdded") or ""),
        "date_modified": str(data.get("dateModified") or ""),
        "collections": [str(key) for key in safe_json_list(data.get("collections", []))],
        "tags": tags,
        "detected_at": detected_at,
        "source": source,
        "zotero_link": f"zotero://select/library/items/{item_key(item)}",
    }


def fetch_metadata_batch(
    api_base: str,
    user_id: str,
    start: int,
    limit: int,
    timeout: int,
    fetcher: JsonFetcher = fetch_json,
) -> list[dict[str, Any]]:
    url = f"{api_base.rstrip('/')}/users/{user_id}/{TOP_LEVEL_ENDPOINT}"
    params = {
        "format": "json",
        "include": "data",
        "sort": "dateAdded",
        "direction": "desc",
        "limit": limit,
        "start": start,
    }
    payload = fetcher(url, params, timeout)
    return payload if isinstance(payload, list) else []


def fetch_new_items(
    db_path: Path,
    api_base: str = DEFAULT_API_BASE,
    user_id: str = DEFAULT_USER_ID,
    batch_size: int = 50,
    max_records: int = 200,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    fetcher: JsonFetcher = fetch_json,
    allow_initial_scan: bool = False,
    watermark_override: Watermark | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    watermark = watermark_override if watermark_override is not None else load_watermark(db_path)
    if watermark is None and not allow_initial_scan:
        raise RuntimeError(
            "ResearchOS parent document has no date_added watermark; "
            "rerun with --allow-initial-scan if you intentionally want a bounded initial metadata scan."
        )

    detected_at = utc_now()
    records: list[dict[str, Any]] = []
    start = 0
    batches = 0
    stopped_at_watermark = False
    while len(records) < max_records:
        limit = min(batch_size, max_records - len(records))
        if limit <= 0:
            break
        batch = fetch_metadata_batch(api_base, user_id, start, limit, timeout, fetcher)
        batches += 1
        if not batch:
            break
        for item in batch:
            if not is_top_level_literature_item(item):
                continue
            key = item_key(item)
            added_raw = str(item_data(item).get("dateAdded") or "")
            added_dt = parse_zotero_time(added_raw)
            if watermark is None:
                records.append(compact_item_record(item, detected_at))
                continue
            if added_dt is None:
                continue
            if added_dt > watermark.timestamp or (added_dt == watermark.timestamp and key not in watermark.item_keys):
                records.append(compact_item_record(item, detected_at))
                continue
            stopped_at_watermark = True
            break
        if stopped_at_watermark or len(batch) < limit:
            break
        start += limit

    diagnostics = {
        "detected_at": detected_at,
        "watermark_date_added": watermark.date_added if watermark else "",
        "watermark_item_keys": sorted(watermark.item_keys) if watermark else [],
        "api_batches_read": batches,
        "metadata_records_read_limit": max_records,
        "stopped_at_watermark": stopped_at_watermark,
        "pdf_access_policy": "forbidden in check/report/sync-selected",
    }
    records.sort(key=lambda row: (parse_zotero_time(row.get("date_added")) or datetime.min.replace(tzinfo=timezone.utc), row["item_key"]), reverse=True)
    return records, diagnostics


def load_state(state_path: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    if not state_path.exists():
        return state
    with state_path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(payload.get("item_key") or "")
            if key:
                state[key] = payload
    return state


def append_state_events(state_path: Path, rows: list[dict[str, Any]], **updates: Any) -> None:
    if not rows:
        return
    state_path.parent.mkdir(parents=True, exist_ok=True)
    event_at = utc_now()
    with state_path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            payload = {
                "item_key": row.get("item_key", ""),
                "date_added": row.get("date_added", ""),
                "event_at": event_at,
                "detected_at": row.get("detected_at", event_at),
                "reported_at": "",
                "classification_status": "",
                "write_plan_status": "",
                "zotero_write_status": "",
                "researchos_sync_status": "",
                "card_status": "",
            }
            payload.update(updates)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def filter_unreported(rows: list[dict[str, Any]], state: dict[str, dict[str, Any]], include_reported: bool) -> list[dict[str, Any]]:
    if include_reported:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        existing = state.get(str(row.get("item_key") or ""), {})
        if existing.get("reported_at") or existing.get("card_status") == "card_done":
            continue
        filtered.append(row)
    return filtered


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def citation_label(row: dict[str, Any]) -> str:
    creators = str(row.get("creators") or "")
    first = creators.split(";", 1)[0].strip()
    last = first.split()[-1] if first else "Unknown"
    year = str(row.get("year") or "n.d.")
    return f"{last}({year})"


def render_report(rows: list[dict[str, Any]], diagnostics: dict[str, Any]) -> str:
    lines = [
        "# Zotero 新增条目监控报告",
        "",
        "来源：Zotero Local API 顶层条目元数据 + ResearchOS Zotero SQLite 父文档。",
        "",
        f"- 生成时间：{diagnostics.get('detected_at', '')}",
        f"- ResearchOS 当前水位线：{diagnostics.get('watermark_date_added', '') or '无'}",
        f"- 本次发现新增条目：{len(rows)}",
        "- 访问边界：未读取 PDF、附件文件、全文缓存，未抽取全文，未写入 Zotero。",
        "",
    ]
    if not rows:
        lines.append("未发现新于 ResearchOS 父文档水位线的 Zotero 顶层条目。")
        return "\n".join(lines) + "\n"
    lines.extend(["| 条目 | 年份 | 来源 | 添加日期 | DOI | 现有标签 |", "| --- | --- | --- | --- | --- | --- |"])
    for row in rows:
        key = row.get("item_key", "")
        label = citation_label(row)
        title = str(row.get("title") or "").replace("|", "\\|")
        tags = "; ".join(row.get("tags") or [])
        doi = str(row.get("doi") or "")
        lines.append(
            f"| [{label}](zotero://select/library/items/{key}) {title} | {row.get('year', '')} | "
            f"{str(row.get('publication') or '').replace('|', '\\|')} | {row.get('date_added', '')} | {doi} | {tags} |"
        )
    return "\n".join(lines) + "\n"


def command_check(args: argparse.Namespace) -> int:
    rows, diagnostics = fetch_new_items(
        Path(args.db),
        args.api_base,
        args.user_id,
        args.batch_size,
        args.max_records,
        args.timeout,
        allow_initial_scan=args.allow_initial_scan,
    )
    state = load_state(Path(args.state))
    rows = filter_unreported(rows, state, args.include_reported)
    write_jsonl(Path(args.output_jsonl), rows)
    append_state_events(Path(args.state), rows, detected_at=diagnostics["detected_at"])
    print(json.dumps({"new_items": len(rows), "output_jsonl": str(args.output_jsonl), **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def command_report(args: argparse.Namespace) -> int:
    rows, diagnostics = fetch_new_items(
        Path(args.db),
        args.api_base,
        args.user_id,
        args.batch_size,
        args.max_records,
        args.timeout,
        allow_initial_scan=args.allow_initial_scan,
    )
    state = load_state(Path(args.state))
    rows = filter_unreported(rows, state, args.include_reported)
    write_jsonl(Path(args.output_jsonl), rows)
    fields = ["item_key", "title", "creators", "year", "publication", "doi", "url", "date_added", "date_modified", "collections", "tags"]
    csv_rows = [
        {**row, "collections": "; ".join(row.get("collections") or []), "tags": "; ".join(row.get("tags") or [])}
        for row in rows
    ]
    write_csv(Path(args.output_csv), csv_rows, fields)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(render_report(rows, diagnostics), encoding="utf-8", newline="\n")
    append_state_events(Path(args.state), rows, reported_at=utc_now())
    print(json.dumps({"reported_items": len(rows), "report_md": str(args.output_md), "report_csv": str(args.output_csv)}, ensure_ascii=False, indent=2))
    return 0


def selected_item_keys(args: argparse.Namespace) -> list[str]:
    keys = [key.strip().upper() for key in args.item_key or [] if key.strip()]
    if args.input_jsonl:
        for row in read_jsonl(Path(args.input_jsonl)):
            key = str(row.get("item_key") or "").strip().upper()
            if key:
                keys.append(key)
    return sorted(dict.fromkeys(keys))


def fetch_single_item(api_base: str, user_id: str, key: str, timeout: int) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/users/{user_id}/items/{key}"
    payload = fetch_json(url, {"format": "json", "include": "data"}, timeout)
    return payload if isinstance(payload, dict) else {}


def command_sync_selected(args: argparse.Namespace) -> int:
    keys = selected_item_keys(args)
    if not keys:
        raise SystemExit("sync-selected requires --item-key or --input-jsonl")
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    collections = fetch_paged(args.api_base, args.user_id, "collections", include="data", timeout=args.timeout)
    _collections_by_key, collection_paths = collection_maps(collections)
    synced_rows: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        init_db(conn)
        upsert_collections(conn, collections, collection_paths)
        for key in keys:
            item = fetch_single_item(args.api_base, args.user_id, key, args.timeout)
            if not item or not is_top_level_literature_item(item):
                continue
            upsert_item(conn, item, collection_paths)
            synced_rows.append(compact_item_record(item, utc_now()))
        conn.commit()
    append_state_events(Path(args.state), synced_rows, researchos_sync_status="metadata_synced")
    print(json.dumps({"synced_items": len(synced_rows), "db": str(db_path), "pdf_access_policy": "not used"}, ensure_ascii=False, indent=2))
    return 0


def add_common_monitor_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-records", type=int, default=200)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--allow-initial-scan", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Detect new Zotero top-level item metadata.")
    add_common_monitor_args(check)
    check.add_argument("--output-jsonl", default=str(DEFAULT_LATEST_JSONL))
    check.add_argument("--include-reported", action="store_true")
    check.set_defaults(func=command_check)

    report = subparsers.add_parser("report", help="Detect and report new Zotero item metadata.")
    add_common_monitor_args(report)
    report.add_argument("--output-jsonl", default=str(DEFAULT_LATEST_JSONL))
    report.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    report.add_argument("--output-csv", default=str(DEFAULT_REPORT_CSV))
    report.add_argument("--include-reported", action="store_true")
    report.set_defaults(func=command_report)

    sync_selected = subparsers.add_parser("sync-selected", help="Sync selected item metadata into the ResearchOS parent document.")
    sync_selected.add_argument("--db", default=str(DEFAULT_DB))
    sync_selected.add_argument("--api-base", default=DEFAULT_API_BASE)
    sync_selected.add_argument("--user-id", default=DEFAULT_USER_ID)
    sync_selected.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    sync_selected.add_argument("--state", default=str(DEFAULT_STATE))
    sync_selected.add_argument("--item-key", action="append")
    sync_selected.add_argument("--input-jsonl")
    sync_selected.set_defaults(func=command_sync_selected)

    return parser


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(effective_argv)
    if getattr(args, "batch_size", 1) < 1:
        parser.error("--batch-size must be >= 1")
    if getattr(args, "max_records", 1) < 1:
        parser.error("--max-records must be >= 1")
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: Zotero Local API metadata read failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
