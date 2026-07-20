"""Shared reading-card metadata and journal-ranking helpers."""

from __future__ import annotations

import html
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MISSING = {"", "?", "[]", "null", "none", "未填写"}
METADATA_HEADINGS = ("元数据（折叠）", "机器元数据（折叠）")
AFFILIATION_FINAL_STATUSES = {
    "semantic_confirmed",
    "manual_confirmed",
    "semantic_needs_check",
    "semantic_not_found",
    "source_unavailable",
}
AFFILIATION_PENDING_STATUSES = {
    "",
    "not_processed",
    "heuristic_candidate",
    "existing_card_candidate",
    "not_found",
    "authoritative_card",
}

RANK_ORDER = [
    "sciif",
    "sci",
    "ssci",
    "zhongguokejihexin",
    "eii",
    "cssci",
    "cscd",
    "xr",
    "xrWarn",
    "xrTop",
]

FIELD_ALIASES = {
    "sciif": ("sciif",),
    "sci": ("sci",),
    "ssci": ("ssci",),
    "zhongguokejihexin": ("zhongguokejihexin",),
    "eii": ("eii", "eei"),
    "cssci": ("cssci",),
    "cscd": ("cscd",),
    "xr": ("xr", "sciUp"),
    "xrWarn": ("xrWarn", "sciwarn"),
    "xrTop": ("xrTop",),
}

CANONICAL_FIELD = {
    alias.lower(): field
    for field, aliases in FIELD_ALIASES.items()
    for alias in aliases
}

TERM_REPLACEMENTS = [
    ("中国科技核心期刊", "科核"),
    ("北大中文核心", "北核"),
    ("CSSCI扩展版", "C刊扩"),
    ("CSSCI", "C刊"),
    ("CSCD", "C"),
    ("核心库", "核"),
    ("扩展库", "扩"),
    ("SSCI", "S"),
    ("SCIWARN", "🚫"),
    ("EI检索", "EI"),
    ("SCIIF(5)", "IF(5)"),
    ("SCIIF", ""),
    ("SCI升级版", ""),
]

CATEGORY_PATTERNS = [
    (r"医学(\d+)区", r"医\1"),
    (r"生物学(\d+)区", r"生\1"),
    (r"农林科学(\d+)区", r"农\1"),
    (r"环境科学与生态学(\d+)区", r"环\1"),
    (r"化学(\d+)区", r"化\1"),
    (r"工程技术(\d+)区", r"工\1"),
    (r"数学(\d+)区", r"数\1"),
    (r"物理与天体物理(\d+)区", r"物\1"),
    (r"地球科学(\d+)区", r"地\1"),
    (r"材料科学(\d+)区", r"材\1"),
    (r"计算机科学(\d+)区", r"计\1"),
    (r"社会学(\d+)区", r"社\1"),
    (r"心理学(\d+)区", r"心\1"),
    (r"经济学(\d+)区", r"经\1"),
    (r"艺术学(\d+)区", r"艺\1"),
    (r"法学(\d+)区", r"法\1"),
    (r"管理学(\d+)区", r"管\1"),
    (r"人文科学(\d+)区", r"人\1"),
    (r"教育学(\d+)区", r"教\1"),
    (r"综合性期刊(\d+)区", r"综\1"),
]


def known(value: Any) -> bool:
    text = str(value or "").strip().strip("'\"")
    return text.lower() not in MISSING


def normalized_affiliation_status(metadata: dict[str, Any]) -> str:
    """Normalize only legacy statuses whose semantic provenance is explicit."""
    status = str(metadata.get("first_author_affiliation_status") or "").strip().lower()
    if status not in {"ok", "confirmed"}:
        return status
    source = str(metadata.get("first_author_affiliation_source") or "")
    raw = metadata.get("first_author_affiliation_raw")
    if known(raw) and re.search(r"(?i)(semantic|语义)", source) and re.search(r"(?i)(page|页)", source):
        return "semantic_confirmed"
    return status


def affiliation_publish_blockers(metadata: dict[str, Any]) -> list[str]:
    """Return evidence blockers that must stop a Zotero reading-card publish."""
    status = normalized_affiliation_status(metadata)
    value = metadata.get("first_author_affiliation")
    raw = metadata.get("first_author_affiliation_raw")
    source = str(metadata.get("first_author_affiliation_source") or "").strip()
    if status in AFFILIATION_PENDING_STATUSES:
        return [f"affiliation_semantic_review_incomplete:{status or 'missing'}"]
    if status not in AFFILIATION_FINAL_STATUSES:
        return [f"affiliation_status_unsupported:{status or 'missing'}"]
    blockers: list[str] = []
    if status in {"semantic_confirmed", "manual_confirmed"} and not known(value):
        blockers.append("affiliation_confirmed_without_value")
    if status == "semantic_confirmed":
        if not known(raw):
            blockers.append("affiliation_semantic_confirmed_without_raw_evidence")
        if not source or not re.search(r"(?i)(page|页)", source):
            blockers.append("affiliation_semantic_confirmed_without_page_source")
    if status in {"semantic_needs_check", "semantic_not_found", "source_unavailable"} and not source:
        blockers.append("affiliation_nonconfirmed_without_reason_or_source")
    return blockers


def normalize_doi(value: Any) -> str:
    """Return a comparison-safe DOI without changing its semantic identity."""
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"^doi\s*:\s*", "", normalized)
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", normalized)
    return normalized.strip()


def chinese_affiliation_display_blockers(metadata: dict[str, Any]) -> list[str]:
    """Validate the publishable display form without performing translation.

    Semantic conversion remains an agent task.  This deterministic gate only
    accepts ``中文一级机构，中文国家`` for confirmed affiliations.
    """
    status = normalized_affiliation_status(metadata)
    if status not in {"semantic_confirmed", "manual_confirmed"}:
        return []
    value = str(metadata.get("first_author_affiliation") or "").strip()
    if value.count("，") != 1:
        return ["affiliation_display_not_chinese_institution_country"]
    institution, country = (part.strip() for part in value.split("，", 1))
    if not institution or not country:
        return ["affiliation_display_not_chinese_institution_country"]
    if re.search(r"[A-Za-z]", value) or not re.search(r"[\u3400-\u9fff]", institution) or not re.search(r"[\u3400-\u9fff]", country):
        return ["affiliation_display_not_chinese_institution_country"]
    return []


def researchos_reading_card_notes(children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every ResearchOS reading-card note under one Zotero parent."""
    matches: list[dict[str, Any]] = []
    for row in children:
        data = row.get("data", {}) or {}
        if data.get("itemType") != "note":
            continue
        tags = {
            str(tag.get("tag") or "")
            for tag in (data.get("tags") or [])
            if isinstance(tag, dict)
        }
        note_html = str(data.get("note") or "")
        if "rs:reading-card" in tags or "ResearchOS card id:" in note_html or "ResearchOS 读书卡｜" in note_html:
            matches.append(row)
    return matches


def yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return json.dumps(text, ensure_ascii=False)


def metadata_heading_pattern(headings: tuple[str, ...] = METADATA_HEADINGS) -> str:
    names = "|".join(re.escape(name) for name in headings)
    return rf"^##\s+(?:\d+\.\s*)?(?:{names})\s*"


def parse_metadata(body: str, headings: tuple[str, ...] = METADATA_HEADINGS) -> dict[str, str]:
    pattern = re.compile(rf"(?ms){metadata_heading_pattern(headings)}.*?```(?:yaml|yml)\s*\n(.*?)\n```", re.M)
    match = pattern.search(body)
    if not match:
        return {}
    data: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def parse_frontmatter(body: str) -> dict[str, str]:
    """Parse the deliberately small scalar YAML header used by reading cards."""
    if not body.startswith("---"):
        return {}
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", body, re.S)
    if not match:
        return {}
    data: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def reading_card_project_links(body: str) -> list[dict[str, Any]]:
    """Return multi-project links while preserving legacy ``project_id`` cards."""
    header = parse_frontmatter(body)
    raw_links = str(header.get("project_links") or "").strip()
    if raw_links:
        try:
            parsed = json.loads(raw_links)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            links: list[dict[str, Any]] = []
            for source_order, row in enumerate(parsed, start=1):
                if isinstance(row, str) and row.strip():
                    links.append({
                        "project_id": row.strip(),
                        "project_name": "",
                        "association_order": source_order,
                    })
                elif isinstance(row, dict) and str(row.get("project_id") or "").strip():
                    try:
                        association_order = int(row.get("association_order") or source_order)
                    except (TypeError, ValueError):
                        association_order = source_order
                    links.append({
                        "project_id": str(row.get("project_id") or "").strip(),
                        "project_name": str(row.get("project_name") or "").strip(),
                        "association_order": association_order,
                    })
            if links:
                return sorted(links, key=lambda row: int(row["association_order"]))
    legacy = str(header.get("project_id") or "").strip()
    return [{"project_id": legacy, "project_name": "", "association_order": 1}] if legacy else []


def reading_card_identity(body: str, path: Path | None = None) -> tuple[str, str]:
    """Return stable card id and Zotero parent item key from a reading card."""
    header = parse_frontmatter(body)
    metadata = parse_metadata(body)
    card_id = str(header.get("card_id") or metadata.get("card_id") or "").strip()
    if not card_id and path is not None:
        match = re.match(r"(RC-\d+)", path.stem, re.I)
        card_id = match.group(1).upper() if match else path.stem
    item_key = ""
    for value in (
        header.get("zotero_key"),
        header.get("item_key"),
        metadata.get("item_key"),
        metadata.get("zotero_item_key"),
    ):
        item_key = raw_zotero_item_key(value)
        if item_key:
            break
    return card_id, item_key


def content_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    return ""


def raw_item_key(value: Any) -> str:
    return raw_zotero_item_key(value)


def zotero_item_markdown_link(key: Any, missing: str = "") -> str:
    raw = raw_zotero_item_key(key)
    if not raw:
        return missing
    return f"[{raw}](zotero://select/library/items/{raw})"


def zotero_item_html_link(key: Any, missing: str = "") -> str:
    raw = raw_zotero_item_key(key)
    if not raw:
        return missing
    return f'<a href="zotero://select/library/items/{raw}">{raw}</a>'


def html_escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def raw_text(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(part).strip() for part in value if known(part))
    if isinstance(value, dict):
        return "、".join(str(part).strip() for part in value.values() if known(part))
    return str(value or "").strip().strip("'\"")


def clean_rank_text(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[;；,，/|]+", "、", text)
    text = re.sub(r"^[：:、]+|[：:、]+$", "", text)
    text = re.sub(r"、{2,}", "、", text)
    return text.strip()


def compact_rank_value(field: str, value: Any) -> str:
    text = raw_text(value)
    if not known(text):
        return ""
    if field == "sciif":
        match = re.search(r"\d+(?:\.\d+)?", text)
        return match.group(0) if match else text
    for old, new in TERM_REPLACEMENTS:
        text = text.replace(old, new)
    text = re.sub(r"\bSCI\b", "", text)
    for pattern, replacement in CATEGORY_PATTERNS:
        text = re.sub(pattern, replacement, text)
    if field == "xrWarn" and text.lower() in {"true", "yes", "y", "1", "是", "预警"}:
        text = "🚫"
    if field == "xrTop" and (re.search(r"TOP", text, re.I) or text.lower() in {"true", "yes", "y", "1", "是"}):
        text = "TOP"
    if field == "cscd":
        text = clean_rank_text(text)
        if text in {"核", "C核"}:
            return "CSCD核"
        if text in {"扩", "C扩"}:
            return "CSCD扩"
        if text in {"C", "CSCD"}:
            return "CSCD"
        if text.startswith("CSCD"):
            return text
        return f"CSCD{text}"
    return clean_rank_text(text)


def canonical_raw_ranks(raw_ranks: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for field in RANK_ORDER:
        for alias in FIELD_ALIASES[field]:
            if alias in raw_ranks and known(raw_ranks.get(alias)):
                compact = compact_rank_value(field, raw_ranks.get(alias))
                if compact:
                    output[field] = compact
                    break
    return output


def format_publication_tags(raw_ranks: dict[str, Any]) -> tuple[str, dict[str, str]]:
    ranks = canonical_raw_ranks(raw_ranks)
    parts = [f"{field}: {ranks[field]}" for field in RANK_ORDER if known(ranks.get(field))]
    return "; ".join(parts), ranks


def normalized_publication_tags(value: str) -> str:
    ranks = parse_publication_tags(value)
    return "; ".join(f"{field}: {ranks[field]}" for field in RANK_ORDER if known(ranks.get(field)))


def parse_publication_tags(value: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for part in str(value or "").split(";"):
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        canonical = CANONICAL_FIELD.get(key.strip().lower(), key.strip())
        if canonical and known(val):
            compact = compact_rank_value(canonical, val.strip())
            if compact:
                output[canonical] = compact
    return output


def badge(label: str, bg: str, color: str = "#111827") -> str:
    return (
        f'<span class="rank-badge" style="display:inline-block; margin: 0 0.18em 0.18em 0; '
        f'padding: 0.12em 0.42em; border-radius: 4px; background: {bg}; color: {color}; '
        f'font-size: 0.86em; line-height: 1.35; white-space: nowrap;">{html_escape(label)}</span>'
    )


def sciif_color(value: str) -> tuple[str, str]:
    try:
        score = float(re.search(r"\d+(?:\.\d+)?", value or "").group(0))  # type: ignore[union-attr]
    except Exception:
        return "#e5e7eb", "#111827"
    if score >= 10:
        return "#fee2e2", "#b91c1c"
    if score >= 7:
        return "#fce7f3", "#9d174d"
    if score >= 3:
        return "#fef3c7", "#92400e"
    return "#dcfce7", "#166534"


def zone_color(value: str) -> tuple[str, str]:
    text = value or ""
    if re.search(r"(?:^|[^0-9])(?:1|一)(?:区|$)", text) or "Q1" in text.upper():
        return "#fee2e2", "#b91c1c"
    if re.search(r"(?:^|[^0-9])(?:2|二)(?:区|$)", text) or "Q2" in text.upper():
        return "#fce7f3", "#9d174d"
    if re.search(r"(?:^|[^0-9])(?:3|三)(?:区|$)", text) or "Q3" in text.upper():
        return "#fef3c7", "#92400e"
    if re.search(r"(?:^|[^0-9])(?:4|四)(?:区|$)", text) or "Q4" in text.upper():
        return "#dcfce7", "#166534"
    return "#e5e7eb", "#111827"


def badge_color(field: str, value: str) -> tuple[str, str]:
    if field == "sciif":
        return sciif_color(value)
    if field == "xrWarn" or "🚫" in value:
        return "#fee2e2", "#b91c1c"
    if field in {"sci", "xr"} or re.search(r"(?:Q[1-4]|[医生农环化工数物地材计社心经艺法管人教综][1-4])", value):
        return zone_color(value)
    if field in {"zhongguokejihexin", "cscd"}:
        return "#dcfce7", "#166534"
    if field in {"ssci", "cssci"}:
        return "#ede9fe", "#5b21b6"
    if field == "eii":
        return "#dbeafe", "#1d4ed8"
    return "#e5e7eb", "#111827"


def html_badges(publication_tags: str) -> str:
    ranks = parse_publication_tags(publication_tags)
    parts: list[str] = []
    for field in RANK_ORDER:
        value = ranks.get(field, "")
        if not known(value):
            continue
        bg, color = badge_color(field, value)
        parts.append(badge(value, bg, color))
    return " ".join(parts)
