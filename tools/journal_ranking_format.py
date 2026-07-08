"""Format EasyScholar journal ranking fields for ResearchOS outputs."""

from __future__ import annotations

import html
import re
from typing import Any


MISSING = {"", "?", "[]", "null", "none", "未填写"}

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
