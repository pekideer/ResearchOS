"""Sync project-level reading summary tables from ResearchOS reading cards.

The HTML table is the human-facing click-through table. The Markdown table is
a fallback, and the CSV table is a machine-readable mirror stored under
.internal by default. This script never writes to Zotero.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from journal_ranking_format import html_badges as journal_ranking_badges
from researchos_card_metadata import metadata_heading_pattern, parse_metadata as parse_machine_metadata


FIELDS = [
    "人工参阅编号",
    "序号",
    "Zotero Item Key",
    "PDF Attachment Key",
    "题目",
    "作者",
    "年份",
    "期刊/来源",
    "期刊缩写",
    "DOI",
    "一段话综述",
    "与主题相关性",
    "Tags",
    "期刊级别",
    "Zotero引用链接",
    "Zotero PDF链接",
    "评价(5星)",
    "阅读状态",
    "重要性",
    "计划用途",
    "PRISMA Record ID",
    "PRISMA Stage",
    "筛选决策",
    "排除原因",
    "读书卡路径",
    "文本来源页码",
    "证据强度",
    "关联Gap",
    "最后更新",
]

REMINDER_FIELDS = [
    "提醒编号",
    "人工参阅编号",
    "Severity",
    "Zotero Item Key",
    "Reading Card Path",
    "Message",
]

UNKNOWN = {"", "?", "[]", "none", "null", "未填写"}

DEFAULT_TOPIC_DIRECTIONS: list[dict[str, str]] = []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or update numbered reading summary tables, Markdown fallback, and CSV mirror."
    )
    parser.add_argument(
        "--project-root",
        help=(
            "Project root. Defaults cards to corpus/reading-cards/cards under "
            "--researchos-root, and writes project summary outputs to "
            "03-文献矩阵/04-阅读总表/."
        ),
    )
    parser.add_argument(
        "--researchos-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="ResearchOS root. Used to locate corpus/reading-cards/cards when --cards-root is omitted.",
    )
    parser.add_argument("--cards-root", help="Directory containing reading cards.")
    parser.add_argument("--output", help="Output CSV path. Defaults to .internal CSV.")
    parser.add_argument(
        "--markdown-output",
        help=(
            "Markdown fallback table path. Defaults to "
            "03-文献矩阵/04-阅读总表/LM-004_reading-summary-table.md when --project-root is used."
        ),
    )
    parser.add_argument(
        "--html-output",
        help=(
            "Human-facing HTML wide table path. Defaults to "
            "03-文献矩阵/04-阅读总表/LM-004_reading-summary-table.html when --project-root is used."
        ),
    )
    parser.add_argument(
        "--prisma-records",
        help="Optional prisma-records.csv for PRISMA stage and screening fields.",
    )
    parser.add_argument(
        "--topic-config",
        help=(
            "Optional CSV/YAML-like topic direction config. Defaults to "
            ".research/project_manifest.yml when --project-root is used."
        ),
    )
    parser.add_argument(
        "--reminders-output",
        help=(
            "Output CSV path for reminders. Defaults to "
            "03-文献矩阵/04-阅读总表/LM-004_reading-summary-reminders.csv when "
            "--project-root is used."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings are generated.",
    )
    return parser


def normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip().strip("'\"")


def is_known(value: Any) -> bool:
    text = normalize(value)
    if text.lower() in UNKNOWN:
        return False
    return not is_placeholder_text(text)


def is_placeholder_text(text: str) -> bool:
    compact = re.sub(r"[\s:：;；,，.。?？\-_/\\|()\[\]{}\"']", "", text)
    compact = re.sub(r"(背景|目的|方法|结论|意义)", "", compact)
    return text.strip() != "" and compact == ""


def split_values(value: str) -> list[str]:
    text = normalize(value)
    if not is_known(text):
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip().strip("'\"") for part in re.split(r"[;,|]+", text) if part.strip()]


def compact_authors(authors: str, corresponding_author: str = "") -> str:
    parts = split_values(authors)
    corresponding_parts = split_values(corresponding_author)
    if not parts:
        return normalize(authors)
    if corresponding_parts:
        selected = [parts[0]]
        for author in corresponding_parts:
            if author not in selected:
                selected.append(author)
        return "; ".join(selected[:2])
    return "; ".join(parts[:2])


def repair_mojibake(value: str) -> str:
    try:
        repaired = value.encode("gbk").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def clean_config_value(value: str) -> str:
    return repair_mojibake(normalize(value).strip().strip("'\""))


def split_inline_list(value: str) -> list[str]:
    text = clean_config_value(value)
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip().strip("'\"") for part in re.split(r"[,;|]+", text) if part.strip().strip("'\"")]


def normalize_topic_direction(entry: dict[str, str], fallback_index: int) -> dict[str, str]:
    code = clean_config_value(entry.get("code", "")) or f"T{fallback_index}"
    label = clean_config_value(entry.get("label", "")) or clean_config_value(entry.get("name", "")) or code
    if not label.startswith(f"{code}_") and code.upper().startswith("T"):
        tag = f"{code}_{label}"
    else:
        tag = label
    display = clean_config_value(entry.get("display", "")) or (tag.split("_", 1)[1] if "_" in tag else tag)
    relevance_default = clean_config_value(entry.get("relevance_default", "")) or clean_config_value(entry.get("relevance", ""))
    return {
        "code": code,
        "label": tag,
        "display": display,
        "relevance_default": relevance_default,
    }


def parse_topic_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [normalize_topic_direction(row, index) for index, row in enumerate(rows, start=1)]


def parse_topic_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    in_section = False
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("topic_directions:"):
            in_section = True
            current = None
            continue
        if in_section and raw and not raw.startswith(" ") and not raw.startswith("-"):
            break
        if not in_section:
            continue
        stripped = raw.strip()
        if stripped.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped and ":" in stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = clean_config_value(value)
            elif stripped:
                current["label"] = clean_config_value(stripped)
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = clean_config_value(value)
    if current:
        entries.append(current)
    return [normalize_topic_direction(entry, index) for index, entry in enumerate(entries, start=1)]


def infer_topic_directions_from_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    pattern = re.compile(r"\b(T\d+)_([^;|,，、]+)")
    for row in rows:
        for value in split_values(row.get("Tags", "")):
            match = pattern.search(value)
            if not match:
                continue
            code = match.group(1)
            label = f"{code}_{match.group(2).strip()}"
            if code not in seen:
                seen[code] = normalize_topic_direction({"code": code, "label": label}, len(seen) + 1)
    return [seen[key] for key in sorted(seen, key=lambda item: int(item[1:]) if item[1:].isdigit() else item)]


def load_topic_directions(project_root: Path | None, config_path: Path | None = None) -> list[dict[str, str]]:
    candidates: list[Path] = []
    if config_path:
        candidates.append(config_path)
    if project_root:
        candidates.extend(
            [
                project_root / ".research" / "topic_directions.csv",
                project_root / ".research" / "project_manifest.yml",
            ]
        )
    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.suffix.lower() == ".csv":
            directions = parse_topic_csv(candidate)
        else:
            directions = parse_topic_manifest(candidate)
        if directions:
            return directions
    return list(DEFAULT_TOPIC_DIRECTIONS)


def infer_topic_relevance(tags: str, topic_directions: list[dict[str, str]]) -> str:
    values = split_values(tags)
    text = "; ".join(values)
    for direction in topic_directions:
        if direction["label"] in text or direction["code"] in values:
            return direction.get("relevance_default", "")
    return ""


def normalize_relevance_degree(value: str, tags: str, topic_directions: list[dict[str, str]]) -> str:
    text = normalize(value)
    if not is_known(text):
        return infer_topic_relevance(tags, topic_directions)
    if "直接相关" in text:
        return "直接相关"
    if "支撑相关" in text:
        return "支撑相关"
    if "背景相关" in text:
        return "背景相关"
    if "相邻相关" in text or "待复核" in text or "待筛除" in text:
        return "待复核"
    return text


def topic_directions_for_row(row: dict[str, str], topic_directions: list[dict[str, str]]) -> list[dict[str, str]]:
    tags = row.get("Tags", "")
    tag_values = split_values(tags)
    text = "; ".join(tag_values)
    matches = [direction for direction in topic_directions if direction["label"] in text or direction["code"] in tag_values]
    if matches:
        return matches
    return [{"code": "UNCLASSIFIED", "label": "未分类", "display": "未分类", "relevance_default": ""}]


def topic_table_path(html_output: Path, code: str) -> Path:
    return html_output.parent / "分主题阅读总表" / f"{html_output.stem}-{code}.html"


def read_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return parse_machine_metadata(text), text

    frontmatter: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[index + 1 :])
            machine = parse_machine_metadata(body)
            machine.update(frontmatter)
            return machine, body
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")
    return frontmatter, text


def normalize_heading(title: str) -> str:
    title = re.sub(r"^[^\dA-Za-z\u4e00-\u9fff]+", "", title).strip()
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", title).strip()


def extract_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        html_match = re.match(r"^<h[23]\b[^>]*>(.*?)</h[23]>\s*$", line)
        if match:
            current = normalize_heading(match.group(1).strip())
            sections.setdefault(current, [])
            continue
        if html_match:
            heading = re.sub(r"<[^>]+>", "", html_match.group(1)).strip()
            current = normalize_heading(heading)
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {key: clean_section("\n".join(value)) for key, value in sections.items()}


def clean_section(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and line != "?"]
    cleaned = " ".join(lines).strip()
    if is_placeholder_text(cleaned):
        return ""
    return cleaned


def first_known(*values: Any) -> str:
    for value in values:
        text = normalize(value)
        if is_known(text):
            return text
    return ""


def raw_zotero_item_key(value: Any) -> str:
    text = normalize(value)
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
    if not raw:
        return ""
    return f"[{raw}](zotero://select/library/items/{raw})"


def extract_pdf_attachment_key(*values: Any) -> str:
    for value in values:
        text = normalize(value)
        if not is_known(text):
            continue
        patterns = [
            r"(?i)^([A-Z0-9]{8})$",
            r"(?i)pdf[_\s-]*attachment[_\s-]*key[:\s`'\"]+([A-Z0-9]{8})",
            r"(?i)attachment[_\s-]*key[:\s`'\"]+([A-Z0-9]{8})",
            r"(?i)\bpdf\s+([A-Z0-9]{8})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return ""


def refresh_zotero_links(row: dict[str, str]) -> None:
    item_key = raw_zotero_item_key(first_known(row.get("Zotero Item Key")))
    pdf_attachment_key = first_known(row.get("PDF Attachment Key"))
    row["Zotero Item Key"] = item_key
    row["Zotero引用链接"] = f"zotero://select/library/items/{item_key}" if item_key else ""
    row["Zotero PDF链接"] = (
        f"zotero://open-pdf/library/items/{pdf_attachment_key}" if pdf_attachment_key else ""
    )


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def parse_card(path: Path, project_root: Path | None, topic_directions: list[dict[str, str]]) -> dict[str, str]:
    frontmatter, body = read_frontmatter(path)
    sections = extract_sections(body)

    item_key = raw_zotero_item_key(first_known(frontmatter.get("zotero_item_key"), frontmatter.get("item_key")))
    title = first_known(frontmatter.get("title"))
    authors = first_known(frontmatter.get("authors"), frontmatter.get("creators"))
    corresponding_author = first_known(
        frontmatter.get("corresponding_author"),
        frontmatter.get("corresponding_authors"),
        frontmatter.get("correspondence_author"),
    )
    year = first_known(frontmatter.get("year"))
    venue = first_known(frontmatter.get("venue"), frontmatter.get("publication"), frontmatter.get("journal"))
    doi = first_known(frontmatter.get("doi"))
    planned_use = first_known(frontmatter.get("planned_use"))
    tags = first_known(frontmatter.get("tags"), frontmatter.get("research_tags"))
    gap_ids = first_known(frontmatter.get("gap_ids"), frontmatter.get("gap_id"))
    source_text = first_known(frontmatter.get("source_text_range"), frontmatter.get("source_text"))
    pdf_attachment_key = extract_pdf_attachment_key(
        frontmatter.get("pdf_attachment_key"),
        frontmatter.get("pdf_key"),
        frontmatter.get("attachment_key"),
        source_text,
    )
    review = first_known(
        frontmatter.get("one_paragraph_review"),
        frontmatter.get("review_paragraph"),
        sections.get("一段话综述"),
    )
    topic_relevance = first_known(
        frontmatter.get("topic_relevance"),
        frontmatter.get("relevance_to_topic"),
        frontmatter.get("relevance_to_project"),
        frontmatter.get("project_relevance"),
        frontmatter.get("relevance"),
    )
    if not topic_relevance:
        topic_relevance = infer_topic_relevance(tags, topic_directions)
    topic_relevance = normalize_relevance_degree(topic_relevance, tags, topic_directions)

    base = project_root or path.parent
    row = {
        "人工参阅编号": first_known(frontmatter.get("manual_ref_id"), frontmatter.get("reading_ref_id")),
        "Zotero Item Key": item_key,
        "PDF Attachment Key": pdf_attachment_key,
        "题目": title,
        "作者": authors,
        "年份": year,
        "期刊/来源": venue,
        "期刊缩写": first_known(
            frontmatter.get("journal_abbrev"),
            frontmatter.get("journal_abbreviation"),
            frontmatter.get("venue_abbrev"),
            frontmatter.get("publication_abbrev"),
        ),
        "DOI": doi,
        "一段话综述": review,
        "与主题相关性": topic_relevance,
        "Tags": "; ".join(split_values(tags)),
        "期刊级别": first_known(frontmatter.get("publication_tags")),
        "Zotero引用链接": "",
        "Zotero PDF链接": "",
        "评价(5星)": first_known(frontmatter.get("rating_5"), frontmatter.get("rating")),
        "阅读状态": first_known(frontmatter.get("read_status"), frontmatter.get("status")),
        "重要性": first_known(frontmatter.get("importance")),
        "计划用途": "; ".join(split_values(planned_use)),
        "PRISMA Record ID": first_known(frontmatter.get("prisma_record_id")),
        "PRISMA Stage": first_known(frontmatter.get("prisma_stage")),
        "筛选决策": first_known(frontmatter.get("screening_decision")),
        "排除原因": first_known(frontmatter.get("exclude_reason")),
        "读书卡路径": relpath(path, base),
        "文本来源页码": source_text,
        "证据强度": first_known(frontmatter.get("evidence_strength")),
        "关联Gap": "; ".join(split_values(gap_ids)),
        "最后更新": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }
    refresh_zotero_links(row)
    return row


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{field: row.get(field, "") for field in FIELDS} for row in reader]


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_escape(value: Any) -> str:
    text = normalize(value)
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\r", " ").replace("\n", " ")
    return text


def markdown_link(label: str, url: str) -> str:
    if not is_known(url):
        return ""
    return f"[{markdown_escape(label)}]({url})"


def html_escape(value: Any) -> str:
    return html.escape(normalize(value), quote=True)


def html_link(label: str, url: str) -> str:
    if not is_known(url):
        return ""
    return f'<a href="{html_escape(url)}">{html_escape(label)}</a>'


def local_open_anchor(label: str, url: str) -> str:
    if not is_known(url):
        return ""
    return f'<a href="{html_escape(url)}" title="打开读书卡">{html_escape(label)}</a>'


def display_width(value: Any) -> int:
    text = normalize(value)
    width = 0
    for char in text:
        width += 2 if ord(char) > 127 else 1
    return width


def markdown_card_link(card_path: str, project_root: Path | None, markdown_path: Path) -> str:
    if not card_path:
        return ""
    if project_root:
        target = project_root / card_path
        return Path(os.path.relpath(target, markdown_path.parent)).as_posix()
    return card_path


def html_card_link(card_path: str, project_root: Path | None) -> str:
    if not card_path or not project_root:
        return ""
    return (project_root / card_path).resolve().as_uri()


def topic_base_stem(path: Path) -> str:
    return re.sub(r"-(?:T\d+|UNCLASSIFIED)$", "", path.stem)


def write_markdown(path: Path, rows: list[dict[str, str]], project_root: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "人工参阅编号",
        "序号",
        "题目",
        "作者",
        "年份",
        "读书卡",
        "Zotero条目",
        "ZoteroPDF",
        "一段话综述",
        "与主题相关性",
        "期刊缩写",
        "期刊等级",
        "评价(5星)",
        "PRISMA Stage",
        "阅读状态",
        "Tags",
    ]
    lines = [
        "# Reading Summary Table",
        "",
        "此表为人工活动表。点击 Zotero 条目或 Zotero PDF 需要本机已安装 Zotero，并注册 `zotero://` 协议。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        card_path = row.get("读书卡路径", "")
        card_link = markdown_card_link(card_path, project_root, path)
        markdown_row = {
            "人工参阅编号": row.get("人工参阅编号", ""),
            "序号": row.get("序号", ""),
            "题目": row.get("题目", ""),
            "作者": compact_authors(row.get("作者", "")),
            "年份": row.get("年份", ""),
            "读书卡": markdown_link("读书卡", card_link) if card_link else "",
            "Zotero条目": html_link(row.get("Zotero Item Key", ""), row.get("Zotero引用链接", "")),
            "ZoteroPDF": markdown_link("PDF", row.get("Zotero PDF链接", "")),
            "一段话综述": row.get("一段话综述", ""),
            "与主题相关性": row.get("与主题相关性", ""),
            "期刊缩写": row.get("期刊缩写", ""),
            "期刊等级": row.get("期刊级别", ""),
            "评价(5星)": row.get("评价(5星)", ""),
            "PRISMA Stage": row.get("PRISMA Stage", ""),
            "阅读状态": row.get("阅读状态", ""),
            "Tags": row.get("Tags", ""),
        }
        lines.append("| " + " | ".join(markdown_escape(markdown_row[field]) for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def width_px(rows: list[dict[str, str]], field: str, label: str, minimum: int, maximum: int) -> int:
    observed = [display_width(label)]
    observed.extend(display_width(row.get(field, "")) for row in rows)
    return min(maximum, max(minimum, max(observed) * 8 + 36))



def topic_nav_html(path: Path, topic_direction: str, topic_directions: list[dict[str, str]]) -> list[str]:
    current_code = "ALL"
    for direction in topic_directions:
        if topic_direction == direction["label"]:
            current_code = direction["code"]
            break
    if topic_direction == "未分类":
        current_code = "UNCLASSIFIED"

    child_page = path.parent.name == "分主题阅读总表"
    base_stem = topic_base_stem(path) if child_page else path.stem
    main_href = f"../{base_stem}.html" if child_page else f"{base_stem}.html"
    entries = [{"code": "ALL", "display_code": "全部", "display": "全部课题方向"}]
    entries.extend(
        {
            "code": direction["code"],
            "display_code": direction["code"],
            "display": direction.get("display", direction["label"]),
        }
        for direction in topic_directions
    )
    if current_code == "UNCLASSIFIED":
        entries.append({"code": "UNCLASSIFIED", "display_code": "未分类", "display": "未分类"})

    lines = ['<nav class="topic-nav" aria-label="课题方向导航">']
    for entry in entries:
        target_code = entry["code"]
        if target_code == "ALL":
            href = main_href
        elif target_code == "UNCLASSIFIED":
            filename = f"{base_stem}-UNCLASSIFIED.html"
            href = filename if child_page else f"分主题阅读总表/{filename}"
        else:
            filename = f"{base_stem}-{target_code}.html"
            href = filename if child_page else f"分主题阅读总表/{filename}"
        class_name = "topic-pill current" if target_code == current_code else "topic-pill"
        lines.append(
            f'<a class="{class_name}" href="{html_escape(href)}">'
            f'<span class="topic-code">{html_escape(entry["display_code"])}</span>{html_escape(entry["display"])}</a>'
        )
    lines.append("</nav>")
    return lines


def write_html(
    path: Path,
    rows: list[dict[str, str]],
    project_root: Path | None = None,
    topic_direction: str = "全部课题方向",
    topic_directions: list[dict[str, str]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        ("人工参阅编号", "编号", 70, 76, "compact sticky-col"),
        ("序号", "序", 44, 50, "compact"),
        ("题目", "题目", 260, 300, "title"),
        ("作者", "作者", 140, 160, "authors"),
        ("年份", "年", 52, 56, "compact"),
        ("读书卡", "读书卡", 86, 96, "compact"),
        ("Zotero 条目", "条目", 72, 82, "compact"),
        ("Zotero PDF", "PDF", 64, 74, "compact"),
        ("一段话综述", "一段话综述", 540, 600, "review"),
        ("与主题相关性", "相关性", 260, 360, "relevance"),
        ("期刊缩写", "期刊", 88, 130, "compact"),
        ("期刊级别", "等级", 110, 180, "rank"),
        ("评价(5星)", "评分", 64, 76, "compact"),
        ("PRISMA Stage", "PRISMA", 82, 110, "compact"),
        ("阅读状态", "状态", 76, 92, "compact"),
        ("Tags", "Tags", 160, 260, "tags"),
    ]
    col_widths: list[int] = []
    for key, label, minimum, maximum, _class_name in columns:
        if key in {"Zotero 条目", "Zotero PDF", "读书卡"}:
            col_widths.append(minimum)
        else:
            col_widths.append(width_px(rows, key, label, minimum, maximum))

    total_width = sum(col_widths)
    generated = datetime.now().isoformat(timespec="seconds")
    project_title = project_root.name if project_root else "ResearchOS"
    parts = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html_escape(project_title)} - {html_escape(topic_direction)}</title>",
        "<style>",
        ":root { --border: #d9dee7; --header: #f2f5f9; --stripe: #fbfcfe; --text: #17202a; --muted: #5f6b7a; --link: #0b63ce; }",
        "body { margin: 0; padding: 24px; font: 15px/1.55 -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; color: var(--text); background: #fff; }",
        "h1 { margin: 0 0 8px; font-size: 32px; line-height: 1.2; }",
        ".meta { margin: 0 0 16px; color: var(--muted); }",
        ".topic-nav { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 18px; padding: 12px; border: 1px solid #c8d3e3; border-radius: 8px; background: #f8fafc; }",
        ".topic-pill { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid #c8d3e3; border-radius: 6px; background: #fff; color: var(--text); text-decoration: none; font-weight: 700; box-shadow: 0 1px 2px rgba(16,24,40,.05); }",
        ".topic-pill:hover { border-color: var(--link); color: var(--link); text-decoration: none; }",
        ".topic-pill.current { border-color: var(--link); background: #eef6ff; color: var(--link); }",
        ".topic-code { display: inline-flex; min-width: 34px; height: 24px; align-items: center; justify-content: center; border-radius: 4px; background: #17202a; color: #fff; font-size: 13px; line-height: 1; }",
        ".table-scrollbar { width: 100%; height: 16px; overflow-x: auto; overflow-y: hidden; border: 1px solid var(--border); border-bottom: 0; border-radius: 8px 8px 0 0; box-shadow: 0 1px 2px rgba(16,24,40,.04); background: #fff; position: sticky; top: 0; z-index: 6; }",
        ".table-scrollbar.hidden { display: none; }",
        ".table-scrollbar-inner { height: 1px; }",
        ".table-shell { width: 100%; overflow: auto; border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 1px 2px rgba(16,24,40,.04); max-height: calc(100vh - 206px); background: #fff; }",
        ".table-scrollbar:not(.hidden) + .table-shell { border-top-left-radius: 0; border-top-right-radius: 0; }",
        f"table {{ border-collapse: separate; border-spacing: 0; table-layout: fixed; min-width: {total_width}px; width: {total_width}px; }}",
        "col { width: auto; }",
        "th, td { border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 8px 10px; vertical-align: top; background: #fff; overflow-wrap: anywhere; word-break: normal; }",
        "th { position: sticky; top: 0; z-index: 3; background: var(--header); text-align: left; font-weight: 700; white-space: normal; }",
        "th { user-select: none; }",
        "tbody tr:nth-child(even) td { background: var(--stripe); }",
        "tbody tr:hover td { background: #eef6ff; }",
        "td.compact, th.compact { text-align: center; vertical-align: middle; white-space: nowrap; }",
        "td.title, td.authors, td.tags { line-height: 1.4; }",
        "td.relevance { line-height: 1.45; }",
        "td.review { line-height: 1.55; }",
        "td.title, td.review { max-height: 13.5em; }",
        ".sticky-col { position: sticky; left: 0; z-index: 2; box-shadow: 1px 0 0 var(--border); }",
        "th.sticky-col { z-index: 4; }",
        "a { color: var(--link); text-decoration: none; font-weight: 600; }",
        "a:hover { text-decoration: underline; }",
        ".empty { color: #9aa4b2; }",
        ".resize-handle { position: absolute; top: 0; right: -3px; width: 8px; height: 100%; cursor: col-resize; z-index: 5; }",
        ".resize-handle:hover, .resize-handle.active { background: rgba(11,99,206,.18); }",
        "th.sortable { cursor: pointer; padding-right: 18px; }",
        "th.sortable::after { content: '↕'; position: absolute; right: 8px; color: #8b96a6; font-size: 11px; }",
        "th.sort-asc::after { content: '↑'; color: var(--link); }",
        "th.sort-desc::after { content: '↓'; color: var(--link); }",
        ".table-shell::-webkit-scrollbar, .table-scrollbar::-webkit-scrollbar { width: 14px; height: 14px; }",
        "@media print { body { padding: 0; } .table-scrollbar { display: none; } .table-shell { position: static; overflow: visible; max-height: none; border: 0; } th { position: static; } .sticky-col { position: static; } }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html_escape(project_title)}</h1>",
        *topic_nav_html(path, topic_direction, topic_directions or []),
        f'<p class="meta">课题方向：<strong>{html_escape(topic_direction)}</strong>。人工操作表，生成时间：{html_escape(generated)}。评分和 PRISMA 字段从读书卡或可选 PRISMA CSV 同步；点击 Zotero 条目或 Zotero PDF 需要本机已安装 Zotero，并注册 <code>zotero://</code> 协议。</p>',
        '<div class="table-scrollbar hidden" aria-hidden="true"><div class="table-scrollbar-inner"></div></div>',
        '<div class="table-shell">',
        "<table>",
        "<colgroup>",
    ]
    for width in col_widths:
        parts.append(f'<col style="width: {width}px;">')
    parts.extend(["</colgroup>", "<thead>", "<tr>"])
    for _key, label, _minimum, _maximum, class_name in columns:
        parts.append(f'<th class="{class_name}">{html_escape(label)}</th>')
    parts.extend(["</tr>", "</thead>", "<tbody>"])
    for row in rows:
        card_path = row.get("读书卡路径", "")
        card_link = html_card_link(card_path, project_root)
        values = {
            "人工参阅编号": row.get("人工参阅编号", ""),
            "序号": row.get("序号", ""),
            "题目": row.get("题目", ""),
            "作者": compact_authors(row.get("作者", "")),
            "年份": row.get("年份", ""),
            "一段话综述": row.get("一段话综述", ""),
            "与主题相关性": row.get("与主题相关性", ""),
            "读书卡": local_open_anchor("卡", card_link),
            "Zotero 条目": html_link(row.get("Zotero Item Key", ""), row.get("Zotero引用链接", "")),
            "Zotero PDF": html_link("PDF", row.get("Zotero PDF链接", "")),
            "期刊缩写": row.get("期刊缩写", ""),
            "期刊级别": journal_ranking_badges(row.get("期刊级别", "")) or html_escape(row.get("期刊级别", "")),
            "评价(5星)": row.get("评价(5星)", ""),
            "PRISMA Stage": row.get("PRISMA Stage", ""),
            "阅读状态": row.get("阅读状态", ""),
            "Tags": row.get("Tags", ""),
        }
        parts.append("<tr>")
        for key, _label, _minimum, _maximum, class_name in columns:
            value = values[key]
            if not value:
                value = '<span class="empty">-</span>'
            elif key != "期刊级别" and not value.startswith("<a "):
                value = html_escape(value)
            parts.append(f'<td class="{class_name}">{value}</td>')
        parts.append("</tr>")
    parts.extend(
        [
            "</tbody>",
            "</table>",
            "</div>",
            "<script>",
            "(() => {",
            "  const table = document.querySelector('table');",
            "  const tableShell = document.querySelector('.table-shell');",
            "  const topScrollbar = document.querySelector('.table-scrollbar');",
            "  const topScrollbarInner = document.querySelector('.table-scrollbar-inner');",
            "  const cols = Array.from(document.querySelectorAll('col'));",
            "  const headers = Array.from(document.querySelectorAll('th'));",
            "  const tbody = document.querySelector('tbody');",
            "  const collator = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'base' });",
            "  const sortState = { index: -1, direction: 1 };",
            "  const key = 'ResearchOS:reading-summary-table:col-widths:' + location.pathname;",
            "  const readWidths = () => cols.map(col => parseInt(col.style.width, 10) || Math.round(col.getBoundingClientRect().width));",
            "  const updateTopScrollbar = () => {",
            "    if (!tableShell || !topScrollbar || !topScrollbarInner) return;",
            "    const tableWidth = Math.ceil(table.getBoundingClientRect().width || table.scrollWidth);",
            "    topScrollbarInner.style.width = tableWidth + 'px';",
            "    const hasOverflow = tableShell.scrollWidth > tableShell.clientWidth + 1;",
            "    topScrollbar.classList.toggle('hidden', !hasOverflow);",
            "    if (hasOverflow) topScrollbar.scrollLeft = tableShell.scrollLeft;",
            "  };",
            "  const applyWidths = widths => {",
            "    let total = 0;",
            "    widths.forEach((width, index) => {",
            "      if (!cols[index]) return;",
            "      const next = Math.max(42, Math.round(Number(width) || 42));",
            "      cols[index].style.width = next + 'px';",
            "      total += next;",
            "    });",
            "    table.style.width = total + 'px';",
            "    table.style.minWidth = total + 'px';",
            "    updateTopScrollbar();",
            "  };",
            "  let syncingScroll = false;",
            "  const syncScroll = (source, target) => {",
            "    if (!source || !target || syncingScroll) return;",
            "    syncingScroll = true;",
            "    target.scrollLeft = source.scrollLeft;",
            "    requestAnimationFrame(() => { syncingScroll = false; });",
            "  };",
            "  tableShell?.addEventListener('scroll', () => syncScroll(tableShell, topScrollbar));",
            "  topScrollbar?.addEventListener('scroll', () => syncScroll(topScrollbar, tableShell));",
            "  window.addEventListener('resize', updateTopScrollbar);",
            "  try {",
            "    const saved = JSON.parse(localStorage.getItem(key) || 'null');",
            "    if (Array.isArray(saved) && saved.length === cols.length) applyWidths(saved);",
            "  } catch (_error) {}",
            "  updateTopScrollbar();",
            "  headers.forEach((header, index) => {",
            "    const handle = document.createElement('span');",
            "    header.classList.add('sortable');",
            "    header.title = (header.title ? header.title + '；' : '') + '点击排序；拖动右边界调整列宽；双击边界重置列宽记忆';",
            "    handle.className = 'resize-handle';",
            "    handle.title = '拖动调整列宽，浏览器会记住本表设置';",
            "    header.appendChild(handle);",
            "    handle.addEventListener('mousedown', event => {",
            "      event.preventDefault();",
            "      handle.classList.add('active');",
            "      const startX = event.clientX;",
            "      const startWidths = readWidths();",
            "      const onMove = moveEvent => {",
            "        const widths = startWidths.slice();",
            "        widths[index] = Math.max(42, startWidths[index] + moveEvent.clientX - startX);",
            "        applyWidths(widths);",
            "      };",
            "      const onUp = () => {",
            "        handle.classList.remove('active');",
            "        document.removeEventListener('mousemove', onMove);",
            "        document.removeEventListener('mouseup', onUp);",
            "        try { localStorage.setItem(key, JSON.stringify(readWidths())); } catch (_error) {}",
            "      };",
            "      document.addEventListener('mousemove', onMove);",
            "      document.addEventListener('mouseup', onUp);",
            "    });",
            "    handle.addEventListener('dblclick', event => {",
            "      event.preventDefault();",
            "      try { localStorage.removeItem(key); } catch (_error) {}",
            "      location.reload();",
            "    });",
            "    header.addEventListener('click', event => {",
            "      if (event.target.closest('.resize-handle')) return;",
            "      sortState.direction = sortState.index === index ? -sortState.direction : 1;",
            "      sortState.index = index;",
            "      headers.forEach(item => item.classList.remove('sort-asc', 'sort-desc'));",
            "      header.classList.add(sortState.direction === 1 ? 'sort-asc' : 'sort-desc');",
            "      const rows = Array.from(tbody.querySelectorAll('tr'));",
            "      rows.sort((left, right) => {",
            "        const a = left.children[index]?.textContent.trim() || '';",
            "        const b = right.children[index]?.textContent.trim() || '';",
            "        const na = Number(a.replace(/[^0-9.\\-]/g, ''));",
            "        const nb = Number(b.replace(/[^0-9.\\-]/g, ''));",
            "        const bothNumeric = a !== '' && b !== '' && Number.isFinite(na) && Number.isFinite(nb);",
            "        const result = bothNumeric ? na - nb : collator.compare(a, b);",
            "        return result * sortState.direction;",
            "      });",
            "      rows.forEach(row => tbody.appendChild(row));",
            "    });",
            "  });",
            "})();",
            "</script>",
            "</body>",
            "</html>",
        ]
    )
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_topic_html_tables(
    html_output: Path,
    rows: list[dict[str, str]],
    project_root: Path | None,
    topic_directions: list[dict[str, str]],
) -> list[Path]:
    written: list[Path] = []
    for direction in topic_directions:
        topic_rows = [
            row
            for row in rows
            if direction in topic_directions_for_row(row, topic_directions)
        ]
        path = topic_table_path(html_output, direction["code"])
        write_html(path, topic_rows, project_root, direction["label"], topic_directions)
        written.append(path)
    unclassified_rows = [
        row
        for row in rows
        if topic_directions_for_row(row, topic_directions)
        == [{"code": "UNCLASSIFIED", "label": "未分类", "display": "未分类", "relevance_default": ""}]
    ]
    if unclassified_rows:
        path = topic_table_path(html_output, "UNCLASSIFIED")
        write_html(path, unclassified_rows, project_root, "未分类", topic_directions)
        written.append(path)
    return written


def cleanup_stale_topic_tables(html_output: Path, active_outputs: list[Path]) -> int:
    topic_root = (html_output.parent / "分主题阅读总表").resolve()
    if topic_root == topic_root.parent or topic_root.name != "分主题阅读总表":
        raise ValueError(f"refuse to clean unexpected topic table directory: {topic_root}")
    active = {path.resolve() for path in active_outputs if path.resolve().parent == topic_root}
    removed = 0
    for path in topic_root.glob(f"{html_output.stem}-*.html"):
        resolved = path.resolve()
        if resolved.parent != topic_root:
            raise ValueError(f"refuse to remove path outside topic table directory: {resolved}")
        if resolved not in active:
            resolved.unlink()
            removed += 1
    return removed


def read_prisma(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {
        raw_zotero_item_key(row.get("Zotero Item Key")): row
        for row in rows
        if is_known(row.get("Zotero Item Key"))
    }


def merge_prisma(row: dict[str, str], prisma_rows: dict[str, dict[str, str]]) -> None:
    key = raw_zotero_item_key(row.get("Zotero Item Key", ""))
    prisma = prisma_rows.get(key)
    if not prisma:
        return
    mappings = [
        ("PRISMA Record ID", "Record ID"),
        ("PDF Attachment Key", "PDF Attachment Key"),
        ("PRISMA Stage", "PRISMA Stage"),
        ("筛选决策", "Screening Decision"),
        ("排除原因", "Exclude Reason"),
        ("阅读状态", "Read Status"),
        ("重要性", "Importance"),
        ("计划用途", "Planned Use"),
    ]
    for target, source in mappings:
        if not is_known(row.get(target)) and is_known(prisma.get(source)):
            row[target] = normalize(prisma.get(source))
    refresh_zotero_links(row)


def row_key(row: dict[str, str]) -> str:
    if is_known(row.get("Zotero Item Key")):
        return raw_zotero_item_key(row.get("Zotero Item Key")).lower()
    return ""


def merge_rows(
    existing_rows: list[dict[str, str]],
    card_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    existing_by_key = {row_key(row): row for row in existing_rows if row_key(row)}
    used_existing: set[str] = set()
    next_sequence = max(
        [int(row.get("序号", "0")) for row in existing_rows if row.get("序号", "").isdigit()]
        or [0]
    )

    merged: list[dict[str, str]] = []
    for card_row in card_rows:
        key = row_key(card_row)
        existing = existing_by_key.get(key, {})
        if key:
            used_existing.add(key)
        output = {field: existing.get(field, "") for field in FIELDS}
        for field in FIELDS:
            if field == "序号":
                continue
            if is_known(card_row.get(field)):
                output[field] = card_row[field]
            elif not is_known(output.get(field)):
                output[field] = ""
        if not output.get("序号"):
            next_sequence += 1
            output["序号"] = str(next_sequence)
        if not is_known(output.get("人工参阅编号")):
            output["人工参阅编号"] = f"RC-{int(output['序号']):03d}"
        refresh_zotero_links(output)
        merged.append(output)

    for existing in existing_rows:
        key = row_key(existing)
        if key and key not in used_existing:
            merged.append(existing)

    merged.sort(key=lambda row: int(row.get("序号", "0") or 0))
    for row in merged:
        if not is_known(row.get("人工参阅编号")) and row.get("序号", "").isdigit():
            row["人工参阅编号"] = f"RC-{int(row['序号']):03d}"
        refresh_zotero_links(row)
    return merged


def build_reminders(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    reminders: list[dict[str, str]] = []
    required = ["Zotero Item Key", "题目", "作者", "年份", "读书卡路径"]
    useful = ["一段话综述", "与主题相关性", "评价(5星)", "期刊缩写", "PRISMA Stage"]
    for row in rows:
        for field in required:
            if not is_known(row.get(field)):
                reminders.append(
                    {
                        "人工参阅编号": row.get("人工参阅编号", ""),
                        "Severity": "error",
                        "Zotero Item Key": row.get("Zotero Item Key", ""),
                        "Reading Card Path": row.get("读书卡路径", ""),
                        "Message": f"missing required field: {field}",
                    }
                )
        for field in useful:
            if not is_known(row.get(field)):
                reminders.append(
                    {
                        "人工参阅编号": row.get("人工参阅编号", ""),
                        "Severity": "warning",
                        "Zotero Item Key": row.get("Zotero Item Key", ""),
                        "Reading Card Path": row.get("读书卡路径", ""),
                        "Message": f"missing recommended field: {field}",
                    }
                )
    for index, reminder in enumerate(reminders, start=1):
        reminder["提醒编号"] = f"TODO-{index:03d}"
    return reminders


def find_cards(cards_root: Path) -> list[Path]:
    return sorted(
        path
        for path in cards_root.rglob("*.md")
        if path.is_file()
        and not path.name.startswith("_")
        and path.name.lower() != "readme.md"
        and (
            re.search(r"^(?:item_key|zotero_item_key):", path.read_text(encoding="utf-8-sig"), re.M)
            or parse_machine_metadata(path.read_text(encoding="utf-8-sig"))
        )
    )


def resolve_paths(args: argparse.Namespace) -> tuple[Path | None, Path, Path, Path, Path, Path]:
    researchos_root = Path(args.researchos_root).resolve()
    project_root = Path(args.project_root).resolve() if args.project_root else None
    if args.cards_root:
        cards_root = Path(args.cards_root).resolve()
    else:
        cards_root = researchos_root / "corpus" / "reading-cards" / "cards"

    if args.output:
        output = Path(args.output).resolve()
    elif project_root:
        output = project_root / "03-文献矩阵" / "04-阅读总表" / "LM-004_reading-summary-table.csv"
    else:
        output = researchos_root / "corpus" / "reading-cards" / "indexes" / "reading-summary-table.csv"

    if args.markdown_output:
        markdown_output = Path(args.markdown_output).resolve()
    elif project_root:
        markdown_output = project_root / "03-文献矩阵" / "04-阅读总表" / "LM-004_reading-summary-table.md"
    else:
        markdown_output = cards_root.parent / "reading-summary-table.md"

    if args.html_output:
        html_output = Path(args.html_output).resolve()
    elif project_root:
        html_output = project_root / "03-文献矩阵" / "04-阅读总表" / "LM-004_reading-summary-table.html"
    else:
        html_output = cards_root.parent / "reading-summary-table.html"

    if args.reminders_output:
        reminders_output = Path(args.reminders_output).resolve()
    elif project_root:
        reminders_output = (
            project_root
            / "03-文献矩阵"
            / "04-阅读总表"
            / "LM-004_reading-summary-reminders.csv"
        )
    else:
        reminders_output = cards_root.parent / ".internal" / "reading-summary-reminders.csv"

    return project_root, cards_root, output, markdown_output, html_output, reminders_output


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    project_root, cards_root, output, markdown_output, html_output, reminder_path = resolve_paths(args)
    if not cards_root.exists() or not cards_root.is_dir():
        raise ValueError(f"读书卡目录不存在：{cards_root}")

    prisma_path = Path(args.prisma_records).resolve() if args.prisma_records else None
    prisma_rows = read_prisma(prisma_path)
    topic_config = Path(args.topic_config).resolve() if args.topic_config else None
    topic_directions = load_topic_directions(project_root, topic_config)
    card_paths = find_cards(cards_root)
    card_rows = [parse_card(path, project_root, topic_directions) for path in card_paths]
    if not topic_directions:
        topic_directions = infer_topic_directions_from_rows(card_rows)
        card_rows = [parse_card(path, project_root, topic_directions) for path in card_paths]
    for row in card_rows:
        merge_prisma(row, prisma_rows)

    existing_rows = read_csv(output)
    merged_rows = merge_rows(existing_rows, card_rows)
    write_csv(output, merged_rows, FIELDS)
    write_html(html_output, merged_rows, project_root, "全部课题方向", topic_directions)
    topic_outputs = write_topic_html_tables(html_output, merged_rows, project_root, topic_directions)
    stale_topic_outputs = cleanup_stale_topic_tables(html_output, topic_outputs)
    write_markdown(markdown_output, merged_rows, project_root)

    reminders = build_reminders(merged_rows)
    write_csv(reminder_path, reminders, REMINDER_FIELDS)

    print("ResearchOS reading summary sync")
    print(f"cards_root: {cards_root}")
    print(f"cards: {len(card_rows)}")
    print(f"rows: {len(merged_rows)}")
    print(f"html_output: {html_output}")
    print(f"topic_directions: {len(topic_directions)}")
    print(f"topic_html_outputs: {len(topic_outputs)} -> {html_output.parent / '分主题阅读总表'}")
    print(f"stale_topic_html_removed: {stale_topic_outputs}")
    print(f"markdown_output: {markdown_output}")
    print(f"csv_output: {output}")
    print(f"reminders: {len(reminders)} -> {reminder_path}")
    if args.strict and reminders:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
