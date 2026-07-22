from __future__ import annotations

from enum import Enum
from typing import Any


class TaskKind(str, Enum):
    CONTENT_TAGS = "content-tags"
    LIBRARY_STRUCTURE = "library-structure"

    @classmethod
    def parse(cls, value: str) -> "TaskKind":
        try:
            return cls(value)
        except ValueError as exc:
            choices = ", ".join(item.value for item in cls)
            raise ValueError(f"unknown task kind {value!r}; expected one of: {choices}") from exc


CONTENT_NAMESPACES = {
    "type_tag": "#Type/",
    "status_tags": "#Status/",
    "method_tags": "#Method/",
    "object_tags": "#Object/",
    "parameter_tags": "#Parameter/",
    "field_tags": "#Field/",
}


def _tag_array() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "maxItems": 8}


def _domain_candidate_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "zh": {"type": "string"},
                "en": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["zh", "en", "confidence", "reason"],
        },
        "maxItems": 2,
    }


def _collection_candidate_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "level": {"type": "integer"},
                "abbr": {"type": "string"},
                "zh": {"type": "string"},
                "en": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["level", "abbr", "zh", "en", "confidence", "reason"],
        },
        "maxItems": 2,
    }


def result_schema(task: TaskKind) -> dict[str, Any]:
    common = {
        "item_key": {"type": "string"},
        "evidence_hash": {"type": "string"},
        "needs_manual_review": {"type": "boolean"},
        "evidence": {"type": "string"},
    }
    if task is TaskKind.CONTENT_TAGS:
        properties = {
            **common,
            "type_tag": {"type": "string"},
            "status_tags": _tag_array(),
            "method_tags": _tag_array(),
            "object_tags": _tag_array(),
            "parameter_tags": _tag_array(),
            "field_tags": _tag_array(),
        }
        required = [
            "item_key", "evidence_hash", "type_tag", "status_tags", "method_tags", "object_tags",
            "parameter_tags", "field_tags", "needs_manual_review", "evidence",
        ]
    else:
        properties = {
            **common,
            "domain_candidates": _domain_candidate_schema(),
            "collection_candidates": _collection_candidate_schema(),
        }
        required = ["item_key", "evidence_hash", "domain_candidates", "collection_candidates", "needs_manual_review", "evidence"]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def task_instructions(task: TaskKind) -> str:
    shared = (
        "Use only the evidence fields in each record. ResearchOS code does not make research-semantic "
        "decisions and must not call a language-model API. Return one plain JSON object per line. "
        "Mark needs_manual_review when evidence is insufficient."
    )
    if task is TaskKind.CONTENT_TAGS:
        return (
            "Classify each document from its own scholarly content only. The collection or project that selected "
            "an item is never semantic evidence. Current Zotero tags, collection membership, project routes, "
            "importance, planned use, and project-association notes are physically excluded from this packet. "
            "Use only #Type/, #Status/, #Method/, #Object/, #Parameter/, and #Field/ namespaces. "
            "Do not produce domain or collection suggestions. " + shared
        )
    return (
        "Propose broad library domains and collection structure. Current library state is supplied separately "
        "from document evidence and may be used only to audit or organize the library. Do not produce content tags. "
        "Use concise Chinese and English collection names with 2-5 letter uppercase abbreviations. " + shared
    )


def validate_result(task: TaskKind, payload: Any) -> tuple[str, dict[str, Any] | None, str]:
    if not isinstance(payload, dict):
        return "", None, "result must be a JSON object"
    if "response" in payload or "custom_id" in payload:
        return str(payload.get("custom_id") or ""), None, "legacy model API response envelopes are not accepted"
    result = payload.get("classification", payload)
    if not isinstance(result, dict):
        return str(payload.get("item_key") or ""), None, "classification must be a JSON object"
    item_key = str(result.get("item_key") or payload.get("item_key") or "").strip().upper()
    schema = result_schema(task)
    missing = [field for field in schema["required"] if field not in result]
    unexpected = sorted(set(result) - set(schema["properties"]))
    if not item_key:
        missing.insert(0, "item_key")
    if missing:
        return item_key, None, "missing required fields: " + ", ".join(dict.fromkeys(missing))
    if unexpected:
        return item_key, None, "unexpected fields for task: " + ", ".join(unexpected)
    if not isinstance(result.get("needs_manual_review"), bool) or not isinstance(result.get("evidence"), str):
        return item_key, None, "needs_manual_review must be boolean and evidence must be string"
    evidence_hash = result.get("evidence_hash")
    if not isinstance(evidence_hash, str) or len(evidence_hash) != 64 or any(char not in "0123456789abcdef" for char in evidence_hash.lower()):
        return item_key, None, "evidence_hash must be a 64-character SHA-256 digest"
    if task is TaskKind.CONTENT_TAGS:
        if not isinstance(result.get("type_tag"), str):
            return item_key, None, "type_tag must be a string"
        for field, prefix in CONTENT_NAMESPACES.items():
            raw_values = [result.get(field)] if field == "type_tag" else result.get(field)
            if field != "type_tag" and (
                not isinstance(raw_values, list) or any(not isinstance(value, str) for value in raw_values)
            ):
                return item_key, None, f"{field} must be an array of strings"
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            for value in values:
                tag = str(value or "").strip()
                if tag and not tag.startswith(prefix):
                    return item_key, None, f"{field} contains tag outside {prefix}"
    else:
        candidate_fields = {
            "domain_candidates": {"zh", "en", "confidence", "reason"},
            "collection_candidates": {"level", "abbr", "zh", "en", "confidence", "reason"},
        }
        for field, allowed in candidate_fields.items():
            candidates = result.get(field)
            if not isinstance(candidates, list):
                return item_key, None, f"{field} must be an array"
            for index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict) or set(candidate) != allowed:
                    return item_key, None, f"{field}[{index}] fields do not match the task schema"
                if not isinstance(candidate.get("confidence"), (int, float)):
                    return item_key, None, f"{field}[{index}].confidence must be numeric"
                if field == "collection_candidates" and not isinstance(candidate.get("level"), int):
                    return item_key, None, f"{field}[{index}].level must be integer"
                text_fields = allowed - {"confidence", "level"}
                if any(not isinstance(candidate.get(name), str) for name in text_fields):
                    return item_key, None, f"{field}[{index}] text fields must be strings"
    return item_key, result, ""
