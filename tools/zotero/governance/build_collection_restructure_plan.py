"""Build a read-only Zotero collection restructure plan.

The plan keeps item assignments bounded to at most three collections:
up to two base research-direction collections, plus one high-value
intersection collection when an item belongs to a configured pair.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import DOCS_LIBRARY_GOVERNANCE, M002_LIBRARY_GOVERNANCE


DEFAULT_ITEM_MATRIX = M002_LIBRARY_GOVERNANCE / "research-direction-item-matrix.csv"
DEFAULT_CLUSTER_CSV = M002_LIBRARY_GOVERNANCE / "research-direction-clusters.csv"
DEFAULT_ASSIGNMENT_CSV = M002_LIBRARY_GOVERNANCE / "collection-restructure-assignment-plan.csv"
DEFAULT_HIERARCHY_JSON = M002_LIBRARY_GOVERNANCE / "collection-restructure-hierarchy-plan.json"
DEFAULT_REPORT_MD = DOCS_LIBRARY_GOVERNANCE / "collection-restructure-plan.md"

HIGH_VALUE_PAIRS = [
    ("HTM", "RHVAC", "HTM × RHVAC", "传热模型 × 辐射暖通", "Heat Transfer Modeling × Radiant HVAC Systems"),
    ("RHVAC", "TES", "RHVAC × TES", "辐射暖通 × 热能储存", "Radiant HVAC Systems × Thermal Energy Storage"),
    ("IR", "MTP", "IR × MTP", "红外辐射测量 × 材料热物性", "Infrared Radiation Measurement × Material Thermal Properties"),
    ("ITC", "RHVAC", "ITC × RHVAC", "室内热舒适 × 辐射暖通", "Indoor Thermal Comfort × Radiant HVAC Systems"),
    ("BOC", "RHVAC", "BOC × RHVAC", "建筑运行控制 × 辐射暖通", "Building Operation Control × Radiant HVAC Systems"),
]

FAMILY_ORDER = {
    "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort": "01.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort",
    "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control": "02.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
    "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement": "03.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
    "D.通风-流场-室内空气-Ventilation Airflow and IAQ": "04.通风-流场-室内空气-Ventilation Airflow and IAQ",
    "E.太阳能-蓄热-近零能耗-Solar TES and NZEB": "05.太阳能-蓄热-近零能耗-Solar TES and NZEB",
    "F.数据方法-优化-统计-Data Methods Optimization and Statistics": "06.数据方法-优化-统计-Data Methods Optimization and Statistics",
    "G.场景综述-政策背景-Context Review and Policy": "07.场景综述-政策背景-Context Review and Policy",
    "H.基础参考-标准-工具-Reference Standards and Tools": "08.基础参考-标准-工具-Reference Standards and Tools",
}
HIGH_VALUE_TOP = "09.高价值交叉-High Value Intersections"
FALLBACK_COLLECTION = "08.基础参考-标准-工具-Reference Standards and Tools/REVIEW-待人工复核-Needs Manual Review"
REVIEW_CODE_TAGS = {
    "SYS": ["#Status/NeedsManualReview", "#Status/NonLiteratureItem", "#Status/DoNotModify"],
    "ZOTOOL": ["#Status/NeedsManualReview", "#Status/NonLiteratureItem", "#Status/DoNotModify"],
    "SOFT": ["#Status/NeedsManualReview"],
    "MED": ["#Status/NeedsManualReview", "#Status/PeripheralTopic"],
    "SIGNAL": ["#Status/NeedsManualReview", "#Status/PeripheralTheory"],
    "ECON": ["#Status/NeedsManualReview", "#Status/PeripheralTheory"],
    "URBD": ["#Status/NeedsManualReview", "#Status/PeripheralTopic"],
    "MOD": ["#Status/NeedsManualReview", "#Status/PeripheralTopic"],
    "ACOUST": ["#Status/NeedsManualReview", "#Status/PeripheralTopic"],
    "CTRL": ["#Status/NeedsManualReview", "#Status/ReferenceTheory"],
}
REVIEW_STATUS_TAG_PREFIXES = ("#Status/Peripheral",)
REVIEW_STATUS_TAG_EXACT = {"#Status/NeedsManualReview", "#Status/NonLiteratureItem", "#Status/DoNotModify"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def collection_code(collection: str) -> str:
    return collection.split("-", 1)[0]


def cross_collection_name(label: str, zh: str, en: str) -> str:
    return f"{label}-{zh}-{en}"


def zotero_link(key: str) -> str:
    return f"[{key}](zotero://select/library/items/{key})"


def load_clusters(path: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    by_collection: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
            by_collection[row["collection"]] = row
    return by_collection, rows


def load_item_matrix(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def path_for_collection(collection: str, cluster_by_collection: dict[str, dict[str, str]]) -> str:
    cluster = cluster_by_collection.get(collection)
    family = cluster.get("family", "Z.待人工复核-Unassigned") if cluster else "Z.待人工复核-Unassigned"
    top = FAMILY_ORDER.get(family, FALLBACK_COLLECTION.split("/", 1)[0])
    return f"{top}/{collection}"


def find_cross_path(collections: list[str]) -> tuple[str, str]:
    codes = {collection_code(collection) for collection in collections}
    for left, right, label, zh, en in HIGH_VALUE_PAIRS:
        if left in codes and right in codes:
            name = cross_collection_name(label, zh, en)
            return f"{HIGH_VALUE_TOP}/{name}", label
    return "", ""


def split_statuses(value: str) -> list[str]:
    statuses: list[str] = []
    for part in (value or "").split(";"):
        clean = part.strip()
        if clean:
            statuses.append(clean.split(" ", 1)[0])
    return statuses


def review_tags_for_item(item: dict[str, str], collections: list[str]) -> tuple[list[str], str]:
    tags: list[str] = []
    reasons: list[str] = []
    for collection in collections:
        code = collection_code(collection)
        if code in REVIEW_CODE_TAGS:
            tags.extend(REVIEW_CODE_TAGS[code])
            reasons.append(f"source collection `{code}` needs manual governance review")
    for status in split_statuses(item.get("statuses", "")):
        if status in REVIEW_STATUS_TAG_EXACT or any(status.startswith(prefix) for prefix in REVIEW_STATUS_TAG_PREFIXES):
            tags.append(status)
            reasons.append(f"existing governance status `{status}`")
    deduped_tags = sorted(set(tags))
    deduped_reasons = sorted(set(reasons))
    return deduped_tags, "; ".join(deduped_reasons)


def build_plan(item_rows: list[dict[str, str]], cluster_by_collection: dict[str, dict[str, str]]) -> dict[str, Any]:
    assignment_rows: list[dict[str, str]] = []
    base_counts: Counter[str] = Counter()
    cross_counts: Counter[str] = Counter()
    top_counts: Counter[str] = Counter()
    over_limit = 0
    missing_collection_map: Counter[str] = Counter()

    for item in item_rows:
        collections = split_semicolon(item.get("collections", ""))
        base_paths = []
        for collection in collections[:2]:
            path = path_for_collection(collection, cluster_by_collection)
            if collection not in cluster_by_collection:
                missing_collection_map[collection] += 1
            base_paths.append(path)
            base_counts[path] += 1
            top_counts[path.split("/", 1)[0]] += 1
        if not base_paths:
            base_paths.append(FALLBACK_COLLECTION)
            base_counts[FALLBACK_COLLECTION] += 1
            top_counts[FALLBACK_COLLECTION.split("/", 1)[0]] += 1

        cross_path, cross_label = find_cross_path(collections)
        review_tags, review_reason = review_tags_for_item(item, collections)
        target_paths = list(base_paths)
        if cross_path:
            target_paths.append(cross_path)
            cross_counts[cross_path] += 1
            top_counts[HIGH_VALUE_TOP] += 1
        if len(target_paths) > 3:
            over_limit += 1
            target_paths = target_paths[:3]

        padded = target_paths + ["", "", ""]
        assignment_rows.append(
            {
                "item_key": item.get("item_key", ""),
                "zotero_link": item.get("zotero_link", ""),
                "title": item.get("title", ""),
                "year": item.get("year", ""),
                "item_type": item.get("item_type", ""),
                "source_collections": "; ".join(collections),
                "target_collection_1": padded[0],
                "target_collection_2": padded[1],
                "target_collection_3": padded[2],
                "assignment_count": str(len(target_paths)),
                "high_value_cross": cross_label,
                "proposed_governance_tags": "; ".join(review_tags),
                "review_reason": review_reason,
                "rule": "base collections plus configured high-value cross" if cross_path else "base collections only",
            }
        )

    hierarchy: dict[str, Any] = {
        "generated_at": utc_now(),
        "policy": {
            "collection_format": "一级目录/二级目录",
            "top_level_format": "NN.中文主题-English Topic",
            "second_level_format": "ABBR-中文主题-English Topic",
            "high_value_cross_top": HIGH_VALUE_TOP,
            "max_collections_per_item": 3,
            "write_to_zotero": False,
        },
        "top_level": [],
        "high_value_pairs": [],
        "validation": {
            "items_total": len(item_rows),
            "items_over_limit_after_truncation": over_limit,
            "missing_collection_mappings": dict(missing_collection_map),
        },
    }

    children_by_top: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path, count in sorted(base_counts.items(), key=lambda item: (item[0].split("/", 1)[0], -item[1], item[0])):
        top, child = path.split("/", 1)
        children_by_top[top].append({"name": child, "path": path, "item_count": count})
    for top in FAMILY_ORDER.values():
        children = children_by_top.get(top, [])
        if children:
            hierarchy["top_level"].append({"name": top, "item_count": top_counts[top], "children": children})
    if top_counts[FALLBACK_COLLECTION.split("/", 1)[0]] and not any(
        top["name"] == FALLBACK_COLLECTION.split("/", 1)[0] for top in hierarchy["top_level"]
    ):
        top = FALLBACK_COLLECTION.split("/", 1)[0]
        hierarchy["top_level"].append(
            {"name": top, "item_count": top_counts[top], "children": children_by_top.get(top, [])}
        )
    for path, count in sorted(cross_counts.items(), key=lambda item: item[0]):
        hierarchy["high_value_pairs"].append({"name": path.split("/", 1)[1], "path": path, "item_count": count})
    if hierarchy["high_value_pairs"]:
        hierarchy["top_level"].append(
            {
                "name": HIGH_VALUE_TOP,
                "item_count": top_counts[HIGH_VALUE_TOP],
                "children": hierarchy["high_value_pairs"],
            }
        )

    return {
        "assignment_rows": assignment_rows,
        "hierarchy": hierarchy,
        "base_counts": base_counts,
        "cross_counts": cross_counts,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def render_report(plan: dict[str, Any], output_csv: Path, output_json: Path) -> str:
    hierarchy = plan["hierarchy"]
    cross_counts: Counter[str] = plan["cross_counts"]
    lines: list[str] = []
    lines.append("# Zotero Collection 重构建议")
    lines.append("")
    lines.append("## 1. 执行边界")
    lines.append("")
    lines.append("- 本文件是只读治理建议，不写入 Zotero。")
    lines.append("- 每个 item 最多归属 3 个 collections：最多 2 个基础二级目录，加 1 个命中的高价值交叉目录。")
    lines.append("- 基础二级目录来自上一轮 1600 条 item 的 collection 归类；高价值交叉目录只覆盖用户指定的 5 个交叉。")
    lines.append("")
    lines.append("## 2. 命名格式")
    lines.append("")
    lines.append("- 一级目录：`NN.中文主题-English Topic`。")
    lines.append("- 二级目录：`ABBR-中文主题-English Topic`。")
    lines.append("- 高价值交叉二级目录：`ABBR × ABBR-中文主题 × 中文主题-English Topic × English Topic`。")
    lines.append("- item 写入规则：先写入各自基础二级目录；如果同时属于指定交叉 pair，再额外写入 `09.高价值交叉-High Value Intersections/...`。")
    lines.append("- 需要人工复核的 item 在计划表中用 `proposed_governance_tags` 标记。")
    lines.append("")
    lines.append("## 3. 建议 Collection 层级")
    lines.append("")
    for top in hierarchy["top_level"]:
        lines.append(f"### {top['name']}")
        lines.append("")
        lines.append(f"- item assignments: {top['item_count']}")
        lines.append("")
        for child in top["children"]:
            lines.append(f"- `{child['name']}`：{child['item_count']} 条")
        lines.append("")
    lines.append("## 4. 高价值交叉目录")
    lines.append("")
    lines.append("| 二级目录 | item 数 | 写入条件 |")
    lines.append("|---|---:|---|")
    for left, right, label, zh, en in HIGH_VALUE_PAIRS:
        name = cross_collection_name(label, zh, en)
        path = f"{HIGH_VALUE_TOP}/{name}"
        count = cross_counts.get(path, 0)
        lines.append(f"| `{name}` | {count} | item 同时属于 `{left}` 与 `{right}` 基础二级目录 |")
    lines.append("")
    lines.append("## 5. 输出文件")
    lines.append("")
    lines.append(f"- item 归属计划 CSV：`{output_csv}`")
    lines.append(f"- collection 层级 JSON：`{output_json}`")
    lines.append("")
    lines.append("## 6. 校验")
    lines.append("")
    validation = hierarchy["validation"]
    lines.append(f"- item 总数：{validation['items_total']}。")
    lines.append(f"- 超过 3 个 collection 的 item：{validation['items_over_limit_after_truncation']}。")
    if validation["missing_collection_mappings"]:
        lines.append(f"- 缺失 collection 映射：{validation['missing_collection_mappings']}。")
    else:
        lines.append("- 所有基础 collection 均有一级目录映射。")
    lines.append("")
    return "\n".join(lines)


def command_build(args: argparse.Namespace) -> int:
    cluster_by_collection, _ = load_clusters(Path(args.cluster_csv))
    item_rows = load_item_matrix(Path(args.item_matrix))
    plan = build_plan(item_rows, cluster_by_collection)

    fields = [
        "item_key",
        "zotero_link",
        "title",
        "year",
        "item_type",
        "source_collections",
        "target_collection_1",
        "target_collection_2",
        "target_collection_3",
        "assignment_count",
        "high_value_cross",
        "proposed_governance_tags",
        "review_reason",
        "rule",
    ]
    write_csv(Path(args.assignment_csv), plan["assignment_rows"], fields)
    write_json(Path(args.hierarchy_json), plan["hierarchy"])
    report = render_report(plan, Path(args.assignment_csv), Path(args.hierarchy_json))
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(report, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "items_total": len(plan["assignment_rows"]),
                "cross_counts": {path: count for path, count in plan["cross_counts"].items()},
                "assignment_csv": str(args.assignment_csv),
                "hierarchy_json": str(args.hierarchy_json),
                "report_md": str(args.report_md),
            },
            ensure_ascii=False,
        )
    )
    return 0
