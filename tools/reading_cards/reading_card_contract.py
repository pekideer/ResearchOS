"""Deterministic structure and provenance contract for ResearchOS reading cards.

Scientific interpretation remains an agent task.  This module only verifies
that a card's declared reading depth agrees with its evidence receipt and
human-readable section structure.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from tools.reading_cards.card_common import (
    content_sha256,
    known,
    parse_frontmatter,
    parse_metadata,
    raw_zotero_item_key,
    reading_card_identity,
    reading_card_project_links,
)


CONTRACT_SCHEMA = "researchos-reading-card/v2"
INITIAL_MODE = "auto_initial_screening"
DEEP_MODE = "llm_fulltext_deep_reading"
PARTIAL_MODE = "llm_partial_fulltext_review"
SUPPORTED_MODES = {INITIAL_MODE, DEEP_MODE, PARTIAL_MODE}
DEEP_READ_STATUSES = {"deep", "deep-read", "全文精读", "精读完成"}
REQUIRED_BODY_SECTIONS = (1, 2, 3, 4, 5, 7)
MIN_SECTION_CONTENT = {1: 40, 2: 80, 3: 100, 4: 100, 5: 30}
PROJECT_USE_FIELDS = (
    "对应项目问题/任务",
    "具体借鉴点",
    "拟使用位置",
    "证据位置",
    "适用边界",
    "状态",
)


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ReadingCardValidation:
    card_id: str
    item_key: str
    schema: str
    generation_mode: str
    profile: str
    sections: tuple[int, ...]
    errors: tuple[ContractIssue, ...]
    warnings: tuple[ContractIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def deep_read_complete(self) -> bool:
        return self.valid and self.profile == "deep"

    @property
    def issue_codes(self) -> list[str]:
        return [issue.code for issue in self.errors]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract_schema": CONTRACT_SCHEMA,
            "card_schema": self.schema,
            "card_id": self.card_id,
            "item_key": self.item_key,
            "generation_mode": self.generation_mode,
            "profile": self.profile,
            "sections": list(self.sections),
            "valid": self.valid,
            "deep_read_complete": self.deep_read_complete,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }
        payload["receipt_hash"] = content_sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        return payload


def _clean_heading(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def _numbered_sections(body: str) -> dict[int, str]:
    headings: list[tuple[int, int, int]] = []
    for match in re.finditer(r"(?m)^##(?!#)\s+(.+?)\s*$", body):
        clean = _clean_heading(match.group(1))
        number = re.search(r"(?:^|\s)([1-7])\.\s*", clean)
        if number:
            headings.append((int(number.group(1)), match.start(), match.end()))
    sections: dict[int, str] = {}
    for index, (number, _start, content_start) in enumerate(headings):
        content_end = headings[index + 1][1] if index + 1 < len(headings) else len(body)
        sections[number] = body[content_start:content_end]
    return sections


def _content_size(value: str) -> int:
    text = re.sub(r"(?m)^#{1,6}\s+.*$", "", value)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?m)^\s*[-|:]+\s*$", "", text)
    text = re.sub(r"[`*_>#|\-]", "", text)
    return len(re.findall(r"[\w\u3400-\u9fff]", text, re.UNICODE))


def _metadata_value(frontmatter: dict[str, str], metadata: dict[str, str], *names: str) -> str:
    for name in names:
        value = str(frontmatter.get(name) or metadata.get(name) or "").strip()
        if value:
            return value
    return ""


def _profile(mode: str, fulltext_status: str, read_status: str) -> str:
    deep_status = read_status.casefold() in DEEP_READ_STATUSES
    if mode == DEEP_MODE and fulltext_status == "full_text_reviewed" and deep_status:
        return "deep"
    if mode == INITIAL_MODE and fulltext_status != "full_text_reviewed" and not deep_status:
        return "initial"
    if mode == PARTIAL_MODE and fulltext_status != "full_text_reviewed" and not deep_status:
        return "partial"
    return "inconsistent"


def _project_section_issues(body: str, section: str, links: list[dict[str, Any]]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if "本课题" in section:
        issues.append(ContractIssue("ambiguous_project_reference", "第 6 节不得使用含义不明的“本课题”。"))
    for heading in ("6.1 项目关联与具体用途", "6.2 跨项目可复用观点", "6.3 不建议引用或需要核查"):
        if not re.search(rf"(?m)^###\s+{re.escape(heading)}\s*$", section):
            issues.append(ContractIssue("project_section_structure_incomplete", f"第 6 节缺少 {heading}。"))
    block_matches = list(re.finditer(r"(?m)^####\s+6\.1\.\d+\s+(.+?)\s*$", section))
    if links and not block_matches:
        issues.append(ContractIssue("project_links_without_use_blocks", "已声明 project_links，但第 6 节没有逐项目用途块。"))
    if block_matches and not links:
        issues.append(ContractIssue("project_use_blocks_without_links", "第 6 节存在项目用途块，但头部没有 project_links。"))
    for index, match in enumerate(block_matches):
        end = block_matches[index + 1].start() if index + 1 < len(block_matches) else len(section)
        block = section[match.end():end]
        missing = [field for field in PROJECT_USE_FIELDS if not re.search(rf"\*\*{re.escape(field)}：\*\*", block)]
        if missing:
            issues.append(ContractIssue(
                "project_use_block_incomplete",
                f"项目用途块 {match.group(1).strip()} 缺少字段：{', '.join(missing)}。",
            ))
    headings_text = "\n".join(match.group(1) for match in block_matches)
    for link in links:
        project_id = str(link.get("project_id") or "").strip()
        if project_id and project_id not in headings_text:
            issues.append(ContractIssue("project_link_not_represented", f"project_links 中的 {project_id} 未在第 6 节单独表示。"))
    return issues


def validate_reading_card(body: str, expected_item_key: str = "") -> ReadingCardValidation:
    """Validate one card without making scientific-content judgments."""
    frontmatter = parse_frontmatter(body)
    metadata = parse_metadata(body)
    card_id, item_key = reading_card_identity(body)
    schema = _metadata_value(frontmatter, metadata, "reading_card_schema")
    mode = _metadata_value(frontmatter, metadata, "generation_mode")
    fulltext_status = _metadata_value(frontmatter, metadata, "fulltext_status")
    read_status = _metadata_value(frontmatter, metadata, "read_status", "status")
    profile = _profile(mode, fulltext_status, read_status)
    sections = _numbered_sections(body)
    errors: list[ContractIssue] = []
    warnings: list[ContractIssue] = []

    expected = raw_zotero_item_key(expected_item_key)
    if not card_id:
        errors.append(ContractIssue("card_id_missing", "缺少稳定 card_id。"))
    if not item_key:
        errors.append(ContractIssue("item_key_missing", "缺少 Zotero 母条目 key。"))
    elif expected and item_key != expected:
        errors.append(ContractIssue("item_key_mismatch", f"卡片 key {item_key} 与预期 {expected} 不一致。"))
    if mode not in SUPPORTED_MODES:
        errors.append(ContractIssue("generation_mode_unsupported", f"不支持 generation_mode={mode or 'missing'}。"))
    if profile == "inconsistent":
        errors.append(ContractIssue("reading_depth_declaration_inconsistent", "generation_mode、fulltext_status 与 read_status 不一致。"))
    for number in REQUIRED_BODY_SECTIONS:
        if number not in sections:
            errors.append(ContractIssue("required_section_missing", f"缺少第 {number} 节。"))
    if profile in {"deep", "partial"}:
        for number, minimum in MIN_SECTION_CONTENT.items():
            if number in sections and _content_size(sections[number]) < minimum:
                errors.append(ContractIssue("section_not_substantive", f"第 {number} 节内容不足以支持所声明的阅读深度。"))
        text_source = _metadata_value(frontmatter, metadata, "text_source", "source_text", "source")
        pages_read = _metadata_value(frontmatter, metadata, "text_pages_read", "text_page_range")
        if not known(text_source):
            errors.append(ContractIssue("text_source_missing", "全文或局部精读缺少可回溯文本来源。"))
        if not known(pages_read) or not re.search(r"\d", pages_read):
            errors.append(ContractIssue("text_pages_read_missing", "全文或局部精读缺少已读页码范围。"))
    if profile == "deep" and fulltext_status != "full_text_reviewed":
        errors.append(ContractIssue("fulltext_review_receipt_missing", "精读卡必须声明 full_text_reviewed。"))

    links = reading_card_project_links(body)
    if 6 in sections:
        errors.extend(_project_section_issues(body, sections[6], links))
    elif links and profile == "deep":
        errors.append(ContractIssue("project_links_without_section_6", "精读卡已关联项目，但缺少结构化第 6 节。"))
    if profile == "initial" and 6 in sections and not links:
        errors.append(ContractIssue("initial_card_unmapped_section_6", "未关联项目的初筛卡不得生成第 6 节。"))

    if schema:
        if schema != CONTRACT_SCHEMA:
            errors.append(ContractIssue("reading_card_schema_unsupported", f"不支持 reading_card_schema={schema}。"))
        elif profile == "deep":
            reviewed = _metadata_value(frontmatter, metadata, "reviewed_sections")
            source_hash = _metadata_value(frontmatter, metadata, "source_text_sha256")
            reviewed_numbers = {int(value) for value in re.findall(r"\d+", reviewed)}
            if not set(REQUIRED_BODY_SECTIONS).issubset(reviewed_numbers):
                errors.append(ContractIssue("reviewed_sections_incomplete", "v2 精读回执未覆盖 1–5、7 节。"))
            if not re.fullmatch(r"[0-9a-f]{64}", source_hash.lower()):
                errors.append(ContractIssue("source_text_sha256_invalid", "v2 精读回执缺少有效 source_text_sha256。"))
    else:
        warnings.append(ContractIssue("legacy_schema_compatibility", "卡片按 v1 兼容模式校验；后续语义更新时再升级 v2 回执。"))

    return ReadingCardValidation(
        card_id=card_id,
        item_key=item_key,
        schema=schema or "legacy-v1",
        generation_mode=mode,
        profile=profile,
        sections=tuple(sorted(sections)),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
