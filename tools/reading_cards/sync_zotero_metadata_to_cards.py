"""Sync Zotero Local API metadata into ResearchOS reading card tail metadata.

This script is local-file only for ResearchOS cards and read-only for Zotero.
It never writes to Zotero.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from card_common import metadata_heading_pattern, parse_metadata, yaml_scalar
from tools.zotero.zotero_local_api import fetch_json as fetch_zotero_json, year_from_date


UNKNOWN = {"", "?", "[]", "none", "null", "未填写"}
MACHINE_METADATA_HEADING = "元数据（折叠）"

PUBLIC_FRONTMATTER_FIELDS = {
    "item_key",
    "zotero_item_key",
    "manual_ref_id",
    "generated_at",
    "generated_by",
    "read_status",
    "status",
    "importance",
    "planned_use",
    "topic_relevance",
    "tags",
    "research_tags",
    "title",
    "title_zh",
    "authors",
    "year",
    "date",
    "venue",
    "publication_title",
    "journal_abbrev",
    "first_author_affiliation",
    "first_author_affiliation_raw",
    "first_author_affiliation_source",
    "first_author_affiliation_status",
    "corresponding_author",
    "abstract_note",
    "rating_5",
    "rating",
    "prisma_record_id",
    "prisma_stage",
    "screening_decision",
    "exclude_reason",
    "evidence_strength",
    "gap_ids",
    "one_paragraph_review",
    "source_text",
    "source_text_range",
}


PRESERVE_FIELDS = {
    "manual_ref_id",
    "generated_at",
    "generated_by",
    "read_status",
    "status",
    "importance",
    "planned_use",
    "topic_relevance",
    "tags",
    "research_tags",
    "title_zh",
    "first_author_affiliation",
    "first_author_affiliation_raw",
    "first_author_affiliation_source",
    "first_author_affiliation_status",
    "corresponding_author",
    "rating_5",
    "rating",
    "prisma_record_id",
    "prisma_stage",
    "screening_decision",
    "exclude_reason",
    "evidence_strength",
    "gap_ids",
    "one_paragraph_review",
    "source_text",
    "source_text_range",
}


FIELD_INSERT_ORDER = [
    "item_key",
    "zotero_item_key",
    "zotero_item_type",
    "zotero_version",
    "zotero_library_type",
    "zotero_library_id",
    "zotero_library_name",
    "pdf_attachment_key",
    "pdf_attachment_keys",
    "child_keys",
    "child_types",
    "title",
    "title_zh",
    "authors",
    "creators_json",
    "first_author_affiliation",
    "first_author_affiliation_raw",
    "first_author_affiliation_source",
    "first_author_affiliation_status",
    "year",
    "date",
    "venue",
    "publication_title",
    "journal_abbrev",
    "doi",
    "issn",
    "isbn",
    "volume",
    "issue",
    "pages",
    "series",
    "language",
    "library_catalog",
    "url",
    "access_date",
    "citation_key",
    "abstract_note",
    "extra",
    "zotero_tags",
    "zotero_collections",
    "zotero_relations",
    "zotero_self_link",
    "zotero_alternate_link",
    "zotero_attachment_link",
    "zotero_date_added",
    "zotero_date_modified",
    "zotero_num_children",
    "zotero_metadata_synced_at",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Zotero metadata into reading cards.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--researchos-root",
        default=str(Path(__file__).resolve().parent.parent.parent),
        help="ResearchOS root. Used to locate corpus/reading-cards/cards when --cards-root is omitted.",
    )
    parser.add_argument("--cards-root")
    parser.add_argument("--api-base", default="http://127.0.0.1:23119/api")
    parser.add_argument("--user-id", default="0")
    parser.add_argument(
        "--metadata-layout",
        choices=["tail", "split", "frontmatter"],
        default="tail",
        help=(
            "tail writes all metadata to the folded tail section. split keeps legacy high-value "
            "human fields in frontmatter. frontmatter preserves the oldest layout."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def is_known(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().strip("'\"")
    return text.lower() not in UNKNOWN


def normalize_frontmatter_value(value: str) -> str:
    return value.strip().strip("'\"")


def raw_zotero_item_key(value: Any) -> str:
    text = str(value or "").strip().strip("'\"")
    patterns = [
        r"(?i)items/([A-Z0-9]{8})",
        r"\[([A-Z0-9]{8})\]\(zotero://select/library/items/[A-Z0-9]{8}\)",
        r"^([A-Z0-9]{8})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).upper()
    return text


def zotero_item_markdown_link(key: Any) -> str:
    raw = raw_zotero_item_key(key)
    if not raw or raw == "?":
        return "?"
    return f"[{raw}](zotero://select/library/items/{raw})"


def read_frontmatter(path: Path) -> tuple[list[str], str]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[:index], "\n".join(lines[index:])
    raise ValueError(f"unclosed frontmatter: {path}")


def frontmatter_map(lines: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for line in lines:
        if ":" not in line or line.strip() == "---":
            continue
        key, value = line.split(":", 1)
        output[key.strip()] = normalize_frontmatter_value(value)
    return output


def machine_metadata_map(body: str) -> dict[str, str]:
    return parse_metadata(body)


def write_frontmatter(path: Path, lines: list[str], closing_and_body: str) -> None:
    if lines:
        path.write_text("\n".join(lines) + "\n" + closing_and_body + "\n", encoding="utf-8")
    else:
        path.write_text(closing_and_body.rstrip() + "\n", encoding="utf-8")


def set_frontmatter_values(lines: list[str], values: dict[str, Any]) -> list[str]:
    key_to_index: dict[str, int] = {}
    for index, line in enumerate(lines):
        if ":" not in line or line.strip() == "---":
            continue
        key, _value = line.split(":", 1)
        key_to_index[key.strip()] = index

    for key, value in values.items():
        if key in {"item_key", "zotero_item_key"}:
            value = zotero_item_markdown_link(value)
        rendered = f"{key}: {yaml_scalar(value)}"
        if key in key_to_index:
            lines[key_to_index[key]] = rendered

    insert_at = len(lines)
    for key in reversed(FIELD_INSERT_ORDER):
        if key in values and key not in key_to_index:
            lines.insert(insert_at, f"{key}: {yaml_scalar(values[key])}")
    return lines


def set_split_frontmatter_values(lines: list[str], values: dict[str, Any]) -> list[str]:
    public_values = {key: value for key, value in values.items() if key in PUBLIC_FRONTMATTER_FIELDS}
    for key in ("item_key", "zotero_item_key"):
        if key in public_values:
            public_values[key] = zotero_item_markdown_link(public_values[key])
    key_to_index: dict[str, int] = {}
    for index, line in enumerate(lines):
        if ":" not in line or line.strip() == "---":
            continue
        key, _value = line.split(":", 1)
        key_to_index[key.strip()] = index

    for key, value in public_values.items():
        rendered = f"{key}: {yaml_scalar(value)}"
        if key in key_to_index:
            lines[key_to_index[key]] = rendered

    # Legacy machine fields are removed from the visible header when split mode is used.
    cleaned = []
    for line in lines:
        if ":" not in line or line.strip() == "---":
            cleaned.append(line)
            continue
        key, _value = line.split(":", 1)
        if key.strip() in FIELD_INSERT_ORDER and key.strip() not in PUBLIC_FRONTMATTER_FIELDS:
            continue
        cleaned.append(line)
    lines = cleaned

    key_to_index = {}
    for index, line in enumerate(lines):
        if ":" not in line or line.strip() == "---":
            continue
        key, _value = line.split(":", 1)
        key_to_index[key.strip()] = index

    insert_at = len(lines)
    for key in reversed(FIELD_INSERT_ORDER):
        if key in public_values and key not in key_to_index:
            lines.insert(insert_at, f"{key}: {yaml_scalar(public_values[key])}")
    return lines


def render_machine_metadata(values: dict[str, Any], include_public: bool = False) -> str:
    if include_public:
        ordered_keys = [key for key in FIELD_INSERT_ORDER if key in values]
        remaining = sorted(key for key in values if key not in ordered_keys)
    else:
        ordered_keys = [key for key in FIELD_INSERT_ORDER if key in values and key not in PUBLIC_FRONTMATTER_FIELDS]
        remaining = sorted(key for key in values if key not in PUBLIC_FRONTMATTER_FIELDS and key not in ordered_keys)
    lines = [f"{key}: {yaml_scalar(values[key])}" for key in [*ordered_keys, *remaining]]
    body = "\n".join(lines).strip()
    return (
        f"## 7. {MACHINE_METADATA_HEADING}\n\n"
        "<details>\n"
        "<summary>Reading card metadata</summary>\n\n"
        "```yaml\n"
        f"{body}\n"
        "```\n\n"
        "</details>\n"
    )


def set_machine_metadata_section(body: str, values: dict[str, Any], include_public: bool = False) -> str:
    section = render_machine_metadata(values, include_public=include_public)
    pattern = re.compile(
        rf"(?ms)\n*{metadata_heading_pattern()}"
        r".*?```(?:yaml|yml)\s*\n.*?\n```\s*</details>\s*$"
    )
    if pattern.search(body):
        return pattern.sub("\n\n" + section.rstrip(), body).rstrip()
    return body.rstrip() + "\n\n" + section.rstrip()


def fetch_local_api_json(api_base: str, user_id: str, path: str) -> Any:
    url = f"{api_base.rstrip('/')}/users/{user_id}/{path.lstrip('/')}"
    return fetch_zotero_json(url, timeout=15)


def creator_name(creator: dict[str, Any]) -> str:
    if creator.get("name"):
        return str(creator["name"]).strip()
    return " ".join(
        part.strip()
        for part in [str(creator.get("firstName", "")), str(creator.get("lastName", ""))]
        if part and part.strip()
    ).strip()


def creators_text(creators: list[dict[str, Any]]) -> str:
    return "; ".join(name for creator in creators if (name := creator_name(creator)))


def first_known(*values: Any) -> str:
    for value in values:
        if is_known(value):
            return str(value).strip()
    return ""


def link_href(item: dict[str, Any], name: str) -> str:
    value = item.get("links", {}).get(name, {})
    if isinstance(value, dict):
        return str(value.get("href", "") or "")
    return ""


def child_summary(children: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str], list[str]]:
    child_keys: list[str] = []
    child_types: list[str] = []
    pdf_keys: list[str] = []
    pdf_paths: list[str] = []
    for child in children:
        key = child.get("key", "")
        data = child.get("data", {})
        item_type = data.get("itemType", "")
        title = data.get("title", "")
        content_type = data.get("contentType", "")
        path = data.get("path", "")
        if key:
            child_keys.append(key)
        child_types.append(f"{item_type}:{title}".strip(":"))
        if item_type == "attachment" and (
            content_type == "application/pdf" or str(title).lower().endswith(".pdf")
        ):
            if key:
                pdf_keys.append(key)
            if path:
                pdf_paths.append(path)
    return child_keys, child_types, pdf_keys, pdf_paths


def metadata_values(
    item: dict[str, Any],
    children: list[dict[str, Any]],
    existing: dict[str, str],
) -> dict[str, Any]:
    data = item.get("data", {})
    meta = item.get("meta", {})
    library = item.get("library", {})
    creators = data.get("creators", []) or []
    tags = [tag.get("tag", "") for tag in data.get("tags", []) if tag.get("tag")]
    collections = data.get("collections", []) or []
    child_keys, child_types, pdf_keys, pdf_paths = child_summary(children)
    attachment_href = link_href(item, "attachment")
    attachment_key = attachment_href.rstrip("/").split("/")[-1] if attachment_href else ""
    if attachment_key and attachment_key not in pdf_keys:
        pdf_keys.insert(0, attachment_key)

    item_key_field = "item_key" if "item_key" in existing else "zotero_item_key"
    values: dict[str, Any] = {
        item_key_field: data.get("key") or item.get("key"),
        "zotero_item_type": data.get("itemType", ""),
        "zotero_version": item.get("version", ""),
        "zotero_library_type": library.get("type", ""),
        "zotero_library_id": library.get("id", ""),
        "zotero_library_name": library.get("name", ""),
        "title": data.get("title", ""),
        "authors": creators_text(creators),
        "creators_json": creators,
        "date": data.get("date", ""),
        "year": year_from_date(data.get("date", "")),
        "venue": first_known(
            data.get("publicationTitle"),
            data.get("bookTitle"),
            data.get("conferenceName"),
            data.get("university"),
            data.get("publisher"),
        ),
        "publication_title": first_known(data.get("publicationTitle"), data.get("bookTitle")),
        "journal_abbrev": data.get("journalAbbreviation", ""),
        "doi": data.get("DOI", ""),
        "issn": data.get("ISSN", ""),
        "isbn": data.get("ISBN", ""),
        "volume": data.get("volume", ""),
        "issue": data.get("issue", ""),
        "pages": data.get("pages", ""),
        "series": data.get("series", ""),
        "language": data.get("language", ""),
        "library_catalog": data.get("libraryCatalog", ""),
        "url": data.get("url", ""),
        "access_date": data.get("accessDate", ""),
        "citation_key": data.get("citationKey", ""),
        "abstract_note": data.get("abstractNote", ""),
        "zotero_tags": tags,
        "zotero_collections": collections,
        "zotero_relations": data.get("relations", {}),
        "zotero_self_link": link_href(item, "self"),
        "zotero_alternate_link": link_href(item, "alternate"),
        "zotero_attachment_link": attachment_href,
        "zotero_date_added": data.get("dateAdded", ""),
        "zotero_date_modified": data.get("dateModified", ""),
        "zotero_num_children": meta.get("numChildren", len(children)),
        "child_keys": child_keys,
        "child_types": child_types,
        "pdf_attachment_keys": pdf_keys,
        "pdf_attachment_paths": pdf_paths,
        "zotero_metadata_synced_at": datetime.now().isoformat(timespec="seconds"),
    }
    if pdf_keys:
        values["pdf_attachment_key"] = pdf_keys[0]
    elif not is_known(existing.get("pdf_attachment_key")):
        values["pdf_attachment_key"] = "?"
    return values


def compact_tail_metadata(values: dict[str, Any]) -> dict[str, Any]:
    output = dict(values)
    if is_known(output.get("publication_title")) and not is_known(output.get("venue")):
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


def find_cards(cards_root: Path) -> list[Path]:
    return sorted(
        path
        for path in cards_root.rglob("*.md")
        if path.is_file() and not path.name.startswith("_") and path.name.lower() != "readme.md"
    )


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(args.project_root).resolve()
    researchos_root = Path(args.researchos_root).resolve()
    cards_root = Path(args.cards_root).resolve() if args.cards_root else researchos_root / "corpus" / "reading-cards" / "cards"
    if not cards_root.exists():
        raise ValueError(f"cards root not found: {cards_root}")

    changed = 0
    rows: list[dict[str, Any]] = []
    for card in find_cards(cards_root):
        lines, body = read_frontmatter(card)
        existing = machine_metadata_map(body)
        existing.update(frontmatter_map(lines))
        key = raw_zotero_item_key(first_known(existing.get("item_key"), existing.get("zotero_item_key")))
        if not key:
            continue
        item = fetch_local_api_json(args.api_base, args.user_id, f"items/{key}")
        children = fetch_local_api_json(args.api_base, args.user_id, f"items/{key}/children")
        children = children if isinstance(children, list) else []
        values = metadata_values(item, children, existing)

        before = "\n".join(lines) + "\n" + body
        merged_values = {**existing, **values}
        for link_key in ("item_key", "zotero_item_key"):
            if link_key in merged_values:
                merged_values[link_key] = zotero_item_markdown_link(merged_values[link_key])

        if args.metadata_layout == "frontmatter":
            updated = set_frontmatter_values(lines[:], values)
            updated_body = body
        elif args.metadata_layout == "tail":
            updated = []
            updated_body = set_machine_metadata_section(body, compact_tail_metadata(merged_values), include_public=True)
        else:
            updated = set_split_frontmatter_values(lines[:], values)
            updated_body = set_machine_metadata_section(body, values)
        after = "\n".join(updated) + "\n" + updated_body
        if before != after:
            changed += 1
            if not args.dry_run:
                write_frontmatter(card, updated, updated_body)
        rows.append(
            {
                "card": str(card),
                "item_key": key,
                "title": values.get("title", ""),
                "venue": values.get("venue", ""),
                "journal_abbrev": values.get("journal_abbrev", ""),
                "pdf_attachment_key": values.get("pdf_attachment_key", ""),
                "pdf_attachment_keys": "; ".join(values.get("pdf_attachment_keys", [])),
                "children": len(children),
                "changed": before != after,
            }
        )

    report_path = project_root / "03-文献矩阵" / "03-文献管理元数据" / "zotero-metadata-card-sync-report.csv"
    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        import csv

        with report_path.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "card",
                "item_key",
                "title",
                "venue",
                "journal_abbrev",
                "pdf_attachment_key",
                "pdf_attachment_keys",
                "children",
                "changed",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print("ResearchOS Zotero metadata card sync")
    print(f"cards_root: {cards_root}")
    print(f"cards_seen: {len(rows)}")
    print(f"cards_changed: {changed}")
    print(f"metadata_layout: {args.metadata_layout}")
    print(f"dry_run: {args.dry_run}")
    if not args.dry_run:
        print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
