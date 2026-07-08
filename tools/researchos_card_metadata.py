"""Shared helpers for ResearchOS reading-card metadata."""

from __future__ import annotations

import json
import re
from typing import Any


METADATA_HEADINGS = ("元数据（折叠）", "机器元数据（折叠）")
MISSING_VALUES = {"", "?", "[]", "null", "none", "未填写"}


def known(value: Any) -> bool:
    return str(value or "").strip().strip("'\"").lower() not in MISSING_VALUES


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
