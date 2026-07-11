"""Sync journal rankings from EasyScholar into reading card tail metadata.

This script never reads Zotero and never writes Zotero. It reads local reading
cards, queries EasyScholar with the configured endpoint/key, and writes ranking
fields back to the cards' folded metadata section.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from card_common import RANK_ORDER, format_publication_tags, known, metadata_heading_pattern, normalized_publication_tags, parse_metadata, parse_publication_tags, yaml_scalar
from tools.researchos_outputs import CORPUS_ZOTERO_LIBRARY_DB


RANKING_TABLE_FIELDS = [
    "journal_name",
    "normalized_name",
    "status",
    "publication_tags",
    "fields_json",
    "source_query",
    "source",
    "updated_at",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root")
    parser.add_argument("--cards-root")
    parser.add_argument("--researchos-root", default=str(Path(__file__).resolve().parent.parent.parent))
    parser.add_argument("--journal-rankings-db", help="Defaults to the ResearchOS Zotero parent SQLite under corpus/.")
    parser.add_argument("--provider-config", help="Defaults to <researchos-root>/.researchos/providers/easyscholar.yml")
    parser.add_argument("--no-api", action="store_true", help="Only use the SQLite journal ranking dictionary and existing card-derived mappings.")
    parser.add_argument("--report-csv")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def normalize_yaml_value(value: str) -> str:
    text = value.strip().strip("'\"")
    text = text.replace("\\\\", "\\")
    return os.path.expandvars(text)


def read_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if current_list and line.startswith("  - "):
            data.setdefault(current_list, []).append(normalize_yaml_value(line[4:]))
            continue
        current_list = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            current_list = key
            data[key] = []
        else:
            data[key] = normalize_yaml_value(value)
    return data


def load_secret_key(path: Path) -> str:
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if raw.startswith("EASYSCHOLAR_API_KEY="):
            return raw.split("=", 1)[1].strip()
    return ""


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    data: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return data, "\n".join(lines[index + 1 :])
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data, text


def raw_zotero_key(value: Any) -> str:
    text = str(value or "").strip().strip("'\"")
    for pattern in [r"items/([A-Z0-9]{8})", r"^([A-Z0-9]{8})$"]:
        match = re.search(pattern, text)
        if match:
            return match.group(1).upper()
    return text


def decode_yaml_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if "\\\"" not in text and "\\\\" not in text:
        return value
    try:
        return json.loads(f'"{text}"')
    except Exception:
        return value


def set_metadata(body: str, metadata: dict[str, Any]) -> str:
    ordered = []
    preferred = [
        "item_key",
        "manual_ref_id",
        "title",
        "title_zh",
        "authors",
        "first_author_affiliation",
        "first_author_affiliation_raw",
        "first_author_affiliation_source",
        "first_author_affiliation_status",
        "year",
        "venue",
        "journal_abbrev",
        "publication_tags",
        "journal_ranking_source",
        "journal_ranking_status",
    ]
    for key in preferred:
        if key in metadata:
            ordered.append(key)
    ordered.extend(sorted(key for key in metadata if key not in ordered))
    yaml_body = "\n".join(f"{key}: {yaml_scalar(metadata[key])}" for key in ordered if known(metadata.get(key)))
    section = (
        "## 7. 元数据（折叠）\n\n"
        "<details>\n"
        "<summary>Reading card metadata</summary>\n\n"
        "```yaml\n"
        f"{yaml_body}\n"
        "```\n\n"
        "</details>"
    )
    pattern = re.compile(rf"(?ms)\n*{metadata_heading_pattern()}.*?```(?:yaml|yml)\s*\n.*?\n```\s*</details>\s*")
    if pattern.search(body):
        return pattern.sub("\n\n" + section, body).rstrip()
    return body.rstrip() + "\n\n" + section


def set_metadata_fields(body: str, metadata: dict[str, Any], fields: list[str]) -> str:
    pattern = re.compile(rf"(?ms)({metadata_heading_pattern()}.*?```(?:yaml|yml)\s*\n)(.*?)(\n```\s*</details>)")
    match = pattern.search(body)
    if not match:
        return set_metadata(body, metadata)

    prefix, block, suffix = match.groups()
    field_set = set(fields)
    seen: set[str] = set()
    lines: list[str] = []
    for raw in block.splitlines():
        if ":" not in raw or raw.lstrip().startswith("#"):
            lines.append(raw)
            continue
        key, _value = raw.split(":", 1)
        name = key.strip()
        if name not in field_set:
            lines.append(raw)
            continue
        seen.add(name)
        if known(metadata.get(name, "")):
            lines.append(f"{name}: {yaml_scalar(metadata[name])}")

    for name in fields:
        if name not in seen and known(metadata.get(name, "")):
            lines.append(f"{name}: {yaml_scalar(metadata[name])}")

    replacement = prefix + "\n".join(lines).rstrip() + suffix
    return body[: match.start()] + replacement + body[match.end() :]


def frontmatter_from_metadata(frontmatter: dict[str, str], metadata: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = dict(frontmatter)
    field_map = {
        "card_id": ["card_id", "manual_ref_id"],
        "zotero_key": ["zotero_key", "item_key", "zotero_item_key"],
        "project_id": ["project_id"],
        "title": ["title"],
        "fulltext_status": ["fulltext_status"],
        "source": ["source"],
        "normalized_at": ["normalized_at"],
    }
    for target, candidates in field_map.items():
        if known(output.get(target, "")):
            continue
        for candidate in candidates:
            value = metadata.get(candidate, "")
            if known(value):
                output[target] = raw_zotero_key(value) if target == "zotero_key" else value
                break
    return output


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    preferred = ["card_id", "zotero_key", "project_id", "title", "fulltext_status", "source", "normalized_at"]
    keys = [key for key in preferred if known(frontmatter.get(key, ""))]
    keys.extend(sorted(key for key in frontmatter if key not in keys and known(frontmatter.get(key, ""))))
    if not keys:
        return ""
    body = "\n".join(f"{key}: {yaml_scalar(frontmatter[key])}" for key in keys)
    return f"---\n{body}\n---\n\n"


def find_cards(cards_root: Path) -> list[Path]:
    return sorted(
        path
        for path in cards_root.rglob("*.md")
        if path.is_file() and not path.name.startswith("_") and path.name.lower() != "readme.md"
    )


def normalize_journal_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.U)
    return text


def load_ranking_table(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        normalized = normalize_journal_name(row.get("normalized_name") or row.get("journal_name", ""))
        if not normalized:
            continue
        output[normalized] = {field: str(row.get(field, "") or "") for field in RANKING_TABLE_FIELDS}
        output[normalized]["normalized_name"] = normalized
        output[normalized]["publication_tags"] = normalized_publication_tags(output[normalized].get("publication_tags", ""))
        output[normalized]["fields_json"] = json.dumps(
            parse_publication_tags(output[normalized].get("publication_tags", "")),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return output


def table_record(journal_name: str, status: str, publication_tags: str, source_query: str = "") -> dict[str, str]:
    publication_tags = normalized_publication_tags(publication_tags)
    fields = parse_publication_tags(publication_tags) if known(publication_tags) else {}
    return {
        "journal_name": journal_name,
        "normalized_name": normalize_journal_name(journal_name),
        "status": status,
        "publication_tags": publication_tags,
        "fields_json": json.dumps(fields, ensure_ascii=False, separators=(",", ":")) if fields else "",
        "source_query": source_query or journal_name,
        "source": "cards",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def remember_ranking(
    table: dict[str, dict[str, str]],
    journal_name: str,
    status: str,
    publication_tags: str,
    source_query: str = "",
) -> None:
    normalized = normalize_journal_name(journal_name)
    if not normalized:
        return
    if status == "error":
        return
    if status == "ok" and not known(publication_tags):
        return
    record = table_record(journal_name, status, publication_tags, source_query)
    record["source"] = "cards" if (source_query or journal_name) == journal_name else "easyscholar"
    table[normalized] = record


def write_ranking_table(path: Path, table: dict[str, dict[str, str]]) -> None:
    rows = sorted(table.values(), key=lambda row: (row.get("journal_name", "").lower(), row.get("normalized_name", "")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RANKING_TABLE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def ensure_sqlite_ranking_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS journal_rankings (
            normalized_name TEXT PRIMARY KEY,
            journal_name TEXT NOT NULL,
            status TEXT NOT NULL,
            publication_tags TEXT,
            fields_json TEXT,
            source_query TEXT,
            source TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )


def load_sqlite_ranking_table(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    con = sqlite3.connect(path)
    try:
        ensure_sqlite_ranking_table(con)
        rows = con.execute(
            """
            SELECT journal_name, normalized_name, status, publication_tags,
                   fields_json, source_query, source, updated_at
            FROM journal_rankings
            """
        ).fetchall()
        output: dict[str, dict[str, str]] = {}
        for journal_name, normalized_name, status, publication_tags, fields_json, source_query, source, updated_at in rows:
            normalized = normalize_journal_name(normalized_name or journal_name)
            if not normalized:
                continue
            output[normalized] = {
                "journal_name": str(journal_name or ""),
                "normalized_name": normalized,
                "status": str(status or ""),
                "publication_tags": normalized_publication_tags(str(publication_tags or "")),
                "fields_json": str(fields_json or ""),
                "source_query": str(source_query or ""),
                "source": str(source or "sqlite"),
                "updated_at": str(updated_at or ""),
            }
        return output
    finally:
        con.close()


def write_sqlite_ranking_table(path: Path, table: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        ensure_sqlite_ranking_table(con)
        rows = []
        for row in table.values():
            if not known(row.get("normalized_name", "")):
                continue
            rows.append(
                {
                    "normalized_name": row.get("normalized_name", ""),
                    "journal_name": row.get("journal_name", ""),
                    "status": row.get("status", ""),
                    "publication_tags": row.get("publication_tags", ""),
                    "fields_json": row.get("fields_json", ""),
                    "source_query": row.get("source_query", ""),
                    "source": row.get("source", "cards"),
                    "updated_at": row.get("updated_at", datetime.now().isoformat(timespec="seconds")),
                }
            )
        con.executemany(
            """
            INSERT INTO journal_rankings (
                normalized_name, journal_name, status, publication_tags,
                fields_json, source_query, source, updated_at
            )
            VALUES (
                :normalized_name, :journal_name, :status, :publication_tags,
                :fields_json, :source_query, :source, :updated_at
            )
            ON CONFLICT(normalized_name) DO UPDATE SET
                journal_name=excluded.journal_name,
                status=excluded.status,
                publication_tags=excluded.publication_tags,
                fields_json=excluded.fields_json,
                source_query=excluded.source_query,
                source=excluded.source,
                updated_at=excluded.updated_at
            """,
            rows,
        )
        con.commit()
    finally:
        con.close()


def cached_ranking(table: dict[str, dict[str, str]], candidates: list[str]) -> tuple[str, str, str]:
    for candidate in candidates:
        record = table.get(normalize_journal_name(candidate))
        if not record:
            continue
        status = record.get("status", "")
        tags = record.get("publication_tags", "")
        if status == "ok" and known(tags):
            return candidate, status, tags
        if status == "no_match":
            return candidate, status, ""
    return "", "", ""


def seed_ranking_table_from_cards(cards: list[Path], table: dict[str, dict[str, str]], priority: list[str]) -> None:
    for card in cards:
        text = card.read_text(encoding="utf-8-sig")
        frontmatter, body = split_frontmatter(text)
        metadata = {key: decode_yaml_string(value) for key, value in parse_metadata(body).items()}
        metadata.update(frontmatter)
        tags = str(metadata.get("publication_tags", "") or "").strip().strip("'\"")
        if not known(tags):
            continue
        for candidate in query_candidates(metadata, priority):
            remember_ranking(table, candidate, "ok", tags, candidate)


def first_known(metadata: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = metadata.get(key, "")
        if known(value):
            return str(value).strip().strip("'\"")
    return ""


def query_candidates(metadata: dict[str, Any], config_priority: list[str]) -> list[str]:
    base_priority = ["venue", "publication_title", "journal", "publication", "journal_abbrev"]
    priority = [*base_priority, *(key for key in config_priority if key not in base_priority)]
    candidates: list[str] = []
    for key in priority:
        value = first_known(metadata, [key])
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def compact_card_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    output = dict(metadata)
    if known(output.get("publication_title")) and not known(output.get("venue")):
        output["venue"] = output["publication_title"]
    if str(output.get("publication_title", "")).strip().strip("'\"").lower() == str(output.get("venue", "")).strip().strip("'\"").lower():
        output.pop("publication_title", None)
    output.pop("zotero_item_key", None)
    output.pop("journal_level", None)
    output.pop("journal_ranking_query", None)
    output.pop("journal_ranking_synced_at", None)
    output.pop("journal_ranking_fields", None)
    output.pop("extra", None)
    if str(output.get("journal_ranking_status", "")).strip().strip("'\"").lower() == "ok":
        output.pop("journal_ranking_status", None)
    return output


def display_publication_tags(publication_tags: str) -> str:
    ranks = parse_publication_tags(publication_tags)
    parts = [ranks[field] for field in RANK_ORDER if known(ranks.get(field))]
    return " ".join(parts) if parts else "?"


def set_visible_journal_ranking(body: str, publication_tags: str) -> str:
    replacement = f"- **期刊等级：** {display_publication_tags(publication_tags)}"
    pattern = re.compile(r"(?m)^- \*\*期刊等级：\*\* .*$")
    if pattern.search(body):
        return pattern.sub(replacement, body, count=1)
    return body


def request_rank(endpoint: str, params: dict[str, str], timeout: int) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(params)
    url = endpoint + ("&" if "?" in endpoint else "?") + encoded
    request = urllib.request.Request(url, headers={"User-Agent": "ResearchOS/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_rank(endpoint: str, secret_key: str, publication_name: str, timeout: int) -> dict[str, Any]:
    params = {
        "secretKey": secret_key,
        "publicationName": publication_name,
    }
    return request_rank(endpoint, params, timeout)


def format_rank(response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    data = response.get("data") if isinstance(response, dict) else {}
    official = data.get("officialRank", {}) if isinstance(data, dict) else {}
    selected = official.get("select", {}) if isinstance(official, dict) else {}
    all_ranks = official.get("all", {}) if isinstance(official, dict) else {}
    if not isinstance(selected, dict):
        selected = {}
    if not isinstance(all_ranks, dict):
        all_ranks = {}
    raw_merged = {**all_ranks, **selected}
    return format_publication_tags(raw_merged)


def main() -> int:
    args = build_parser().parse_args()
    researchos_root = Path(args.researchos_root).resolve()
    project_root = Path(args.project_root).resolve() if args.project_root else None
    if args.cards_root:
        cards_root = Path(args.cards_root).resolve()
    else:
        cards_root = researchos_root / "corpus" / "reading-cards" / "cards"
    journal_rankings_db = Path(args.journal_rankings_db).resolve() if args.journal_rankings_db else researchos_root / CORPUS_ZOTERO_LIBRARY_DB
    provider_config = Path(args.provider_config).resolve() if args.provider_config else researchos_root / ".researchos" / "providers" / "easyscholar.yml"
    config = read_simple_yaml(provider_config) if provider_config.exists() else {}
    endpoint = str(config.get("endpoint", "")).strip()
    secret_file = Path(str(config.get("secret_env_file", Path.home() / ".researchos" / "secrets" / "easyscholar.env")))
    secret_key = load_secret_key(secret_file) if secret_file.exists() else ""
    timeout = int(config.get("timeout_seconds", 20) or 20)
    rate_limit = int(config.get("rate_limit_per_minute", 30) or 30)
    priority = config.get("query_field_priority", [])
    priority = priority if isinstance(priority, list) else []
    api_enabled = bool(endpoint and secret_key and not args.no_api)

    cards = find_cards(cards_root)
    ranking_table_path = researchos_root / "corpus" / "reading-cards" / "indexes" / "easyscholar-journal-ranking-table.csv"
    cache_json = researchos_root / "corpus" / "reading-cards" / "indexes" / "easyscholar-journal-ranking-cache.json"
    if project_root:
        report_csv = (
            Path(args.report_csv).resolve()
            if args.report_csv
            else project_root / "03-文献矩阵" / "05-读书卡审计与证据" / "easyscholar-journal-ranking-report.csv"
        )
    else:
        report_csv = Path(args.report_csv).resolve() if args.report_csv else None
    ranking_table = load_sqlite_ranking_table(journal_rankings_db)
    for normalized, row in load_ranking_table(ranking_table_path).items():
        ranking_table.setdefault(normalized, row)
    seed_ranking_table_from_cards(cards, ranking_table, priority)
    cache: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    changed = 0
    table_hits = 0
    api_requests = 0
    delay = 60 / rate_limit if rate_limit > 0 else 0
    last_request = 0.0

    for card in cards:
        original = card.read_text(encoding="utf-8-sig")
        frontmatter, body = split_frontmatter(original)
        metadata = {key: decode_yaml_string(value) for key, value in parse_metadata(body).items()}
        metadata.update(frontmatter)
        candidates = query_candidates(metadata, priority)
        status = "no_query"
        query = ""
        tags = ""
        merged_rank: dict[str, Any] = {}
        response: dict[str, Any] | None = None
        error = ""
        query, cached_status, cached_tags = cached_ranking(ranking_table, candidates)
        if cached_status:
            status = cached_status
            tags = cached_tags
            table_hits += 1
        elif api_enabled:
            for candidate in candidates:
                query = candidate
                try:
                    wait = delay - (time.monotonic() - last_request)
                    if wait > 0:
                        time.sleep(wait)
                    api_requests += 1
                    response = fetch_rank(endpoint, secret_key, candidate, timeout)
                    last_request = time.monotonic()
                    tags, merged_rank = format_rank(response)
                    cache[candidate] = {
                        "code": response.get("code") if isinstance(response, dict) else "",
                        "msg": response.get("msg") if isinstance(response, dict) else "",
                        "rank_fields": merged_rank,
                    }
                    status = "ok" if tags else "no_match"
                    remember_ranking(ranking_table, candidate, status, tags, candidate)
                    if tags:
                        break
                except Exception as exc:  # noqa: BLE001 - report per-card API failure without leaking key.
                    status = "error"
                    error = str(exc).replace(secret_key, "<REDACTED_KEY>")
                    cache[candidate] = {"error": error}
        else:
            status = "no_match"
        if tags:
            metadata["publication_tags"] = tags
            metadata["journal_ranking_source"] = "EasyScholar"
            metadata["journal_ranking_status"] = status
        elif status == "no_match":
            metadata["publication_tags"] = tags
            metadata["journal_ranking_source"] = "EasyScholar"
            metadata["journal_ranking_status"] = status
        else:
            metadata["journal_ranking_source"] = "EasyScholar"
            metadata["journal_ranking_status"] = status
        metadata = compact_card_metadata(metadata)
        body = set_visible_journal_ranking(body, tags)
        updated_body = set_metadata_fields(
            body,
            metadata,
            ["publication_tags", "journal_ranking_source", "journal_ranking_status"],
        )
        restored_frontmatter = frontmatter_from_metadata(frontmatter, metadata)
        updated = render_frontmatter(restored_frontmatter) + updated_body.lstrip("\n").rstrip() + "\n"
        if updated != original:
            changed += 1
            if not args.dry_run:
                card.write_text(updated, encoding="utf-8")
        rows.append(
            {
                "card": str(card),
                "query": query,
                "status": status,
                "publication_tags": tags,
                "error": error,
                "source": "table" if cached_status else "api",
            }
        )

    if not args.dry_run:
        write_sqlite_ranking_table(journal_rankings_db, ranking_table)
        if project_root:
            write_ranking_table(ranking_table_path, ranking_table)
            if cache_json is not None:
                cache_json.parent.mkdir(parents=True, exist_ok=True)
                cache_json.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        if report_csv is not None:
            report_csv.parent.mkdir(parents=True, exist_ok=True)
            with report_csv.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["card", "query", "status", "publication_tags", "error", "source"])
                writer.writeheader()
                writer.writerows(rows)

    print("ResearchOS EasyScholar journal ranking sync")
    print(f"cards_seen: {len(cards)}")
    print(f"cards_changed: {changed}")
    print(f"ranking_table_hits: {table_hits}")
    print(f"api_requests: {api_requests}")
    print(f"api_enabled: {api_enabled}")
    print(f"journal_rankings_db: {journal_rankings_db}")
    print(f"dry_run: {args.dry_run}")
    print(f"provider_config: {provider_config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
