"""Aggregate Zotero governance labels into candidate research directions.

This tool reads ResearchOS governance outputs only. It does not read
zotero.sqlite, write to Zotero, move PDFs, or modify Zotero tags/collections.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import DOCS_LIBRARY_GOVERNANCE, M002_LIBRARY_GOVERNANCE


DEFAULT_PLAN_MD = DOCS_LIBRARY_GOVERNANCE / "local-semantic-governance-plan.md"
DEFAULT_CORPUS_JSONL = M002_LIBRARY_GOVERNANCE / "ai-governance-corpus.jsonl"
DEFAULT_ITEM_MATRIX = M002_LIBRARY_GOVERNANCE / "research-direction-item-matrix.csv"
DEFAULT_CLUSTER_CSV = M002_LIBRARY_GOVERNANCE / "research-direction-clusters.csv"
DEFAULT_COOCCURRENCE_CSV = M002_LIBRARY_GOVERNANCE / "research-direction-cooccurrence.csv"
DEFAULT_SUMMARY_JSON = M002_LIBRARY_GOVERNANCE / "research-direction-aggregation-summary.json"
DEFAULT_REPORT_MD = DOCS_LIBRARY_GOVERNANCE / "research-direction-aggregation-report.md"

NAMESPACES = ("Field", "Method", "Object", "Parameter", "Status", "Type")

EMPIRICAL_HINTS = (
    "Experiment",
    "Experimental",
    "Measurement",
    "FieldMeasurement",
    "OnSite",
    "HumanSubject",
    "Survey",
    "Monitoring",
)
MODELING_HINTS = (
    "Simulation",
    "Model",
    "CFD",
    "EnergyPlus",
    "TRNSYS",
    "Numerical",
    "HeatTransfer",
)
AI_CONTROL_HINTS = (
    "MachineLearning",
    "DeepLearning",
    "Neural",
    "Optimization",
    "ModelPredictiveControl",
    "Reinforcement",
    "ArtificialIntelligence",
)
REFERENCE_STATUS = {
    "#Status/ReferenceTheory",
    "#Status/ReferenceBook",
    "#Status/Standard",
    "#Status/Textbook",
    "#Status/Report",
    "#Status/PolicyDocument",
}
PERIPHERAL_STATUS_PREFIXES = (
    "#Status/Peripheral",
    "#Status/NeedsManualReview",
    "#Status/MissingAbstract",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def zotero_link(key: str) -> str:
    return f"[{key}](zotero://select/library/items/{key})"


def split_collection_name(value: str) -> dict[str, str]:
    parts = value.split("-", 2)
    return {
        "code": parts[0] if parts else value,
        "zh": parts[1] if len(parts) > 1 else "",
        "en": parts[2] if len(parts) > 2 else "",
        "raw": value,
    }


def split_semicolon_cell(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def parse_tags(tags: list[str]) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {namespace: [] for namespace in NAMESPACES}
    for tag in tags:
        match = re.match(r"^#([^/]+)/(.+)$", tag)
        if match and match.group(1) in parsed:
            parsed[match.group(1)].append(tag)
    return parsed


def parse_plan(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    items: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("| ["):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        match = re.search(r"\[([A-Z0-9]+)\]\(zotero://select/library/items/\1\)", cells[0])
        if not match:
            continue
        item_key = match.group(1)
        collections = re.findall(r"`([^`]+)`", cells[1])
        if not collections:
            collections = split_semicolon_cell(cells[1])
        tags = re.findall(r"`([^`]+)`", cells[2])
        if not tags:
            tags = split_semicolon_cell(cells[2])
        by_namespace = parse_tags(tags)
        items.append(
            {
                "item_key": item_key,
                "collections": collections,
                "tags": tags,
                "explanation": cells[3],
                **{f"{namespace.lower()}_tags": by_namespace[namespace] for namespace in NAMESPACES},
            }
        )
    return items


def load_corpus(path: Path) -> dict[str, dict[str, Any]]:
    corpus: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return corpus
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            key = str(record.get("item_key") or "")
            if key:
                corpus[key] = record
    return corpus


def matches_any(value: str, hints: tuple[str, ...]) -> bool:
    normalized = value.lower()
    return any(hint.lower() in normalized for hint in hints)


def top_values(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def classify_family(collection: str, counters: dict[str, Counter[str]]) -> str:
    code = split_collection_name(collection)["code"]
    code_map = {
        "RHVAC": "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort",
        "ITC": "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort",
        "PCE": "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort",
        "ADAPT": "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort",
        "SLEEP": "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort",
        "BEEC": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "BOC": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "HVAC": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "BEM": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "MLBE": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "MPC": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "BRES": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "CL": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "HSCW": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "OB": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "EDU": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "GB": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "BEN": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "REFIT": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "NZEB": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "LEB": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "BDIAG": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "TRANS": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "HTM": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "MTP": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "IR": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "PRC": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "MAT": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "RAD": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "LCA": "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement",
        "VENT": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "IAQ": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "CFD": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "HYGRO": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "MET": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "FIRE": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "FURN": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "TES": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "SOLAR": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "SBE": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "BIPV": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "TABS": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "TEC": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "ENERGY": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "DHC": "E.太阳能-蓄热-近零能耗-Solar TES and NZEB",
        "MLM": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "STAT": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "DIGI": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "OPT": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "MATH": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "DATA": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "SIGNAL": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "CTRL": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "SOFT": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "BIM": "F.数据方法-优化-统计-Data Methods Optimization and Statistics",
        "RHE": "G.场景综述-政策背景-Context Review and Policy",
        "SOC": "G.场景综述-政策背景-Context Review and Policy",
        "POLICY": "G.场景综述-政策背景-Context Review and Policy",
        "GIS": "G.场景综述-政策背景-Context Review and Policy",
        "CLIM": "G.场景综述-政策背景-Context Review and Policy",
        "PLAN": "G.场景综述-政策背景-Context Review and Policy",
        "UHE": "G.场景综述-政策背景-Context Review and Policy",
        "UHI": "G.场景综述-政策背景-Context Review and Policy",
        "HEALTH": "G.场景综述-政策背景-Context Review and Policy",
        "HERITAGE": "G.场景综述-政策背景-Context Review and Policy",
        "AGE": "G.场景综述-政策背景-Context Review and Policy",
        "VERN": "G.场景综述-政策背景-Context Review and Policy",
        "BSTOCK": "G.场景综述-政策背景-Context Review and Policy",
        "BSC": "G.场景综述-政策背景-Context Review and Policy",
        "LCC": "G.场景综述-政策背景-Context Review and Policy",
        "CLIMATE": "G.场景综述-政策背景-Context Review and Policy",
        "URBD": "G.场景综述-政策背景-Context Review and Policy",
        "MED": "G.场景综述-政策背景-Context Review and Policy",
        "FM": "G.场景综述-政策背景-Context Review and Policy",
        "ECON": "G.场景综述-政策背景-Context Review and Policy",
        "IND": "G.场景综述-政策背景-Context Review and Policy",
        "REF": "H.基础参考-标准-工具-Reference Standards and Tools",
        "STD": "H.基础参考-标准-工具-Reference Standards and Tools",
        "PHYS": "H.基础参考-标准-工具-Reference Standards and Tools",
        "SYS": "H.基础参考-标准-工具-Reference Standards and Tools",
        "ZOTOOL": "H.基础参考-标准-工具-Reference Standards and Tools",
        "ACOUST": "D.通风-流场-室内空气-Ventilation Airflow and IAQ",
        "MOD": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
        "BED": "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control",
    }
    if code in code_map:
        return code_map[code]
    text = collection.lower()
    top_fields = " ".join(counters["field"].keys()).lower()
    probe = f"{code.lower()} {text} {top_fields}"
    if any(token in probe for token in ("radiant", "rhvac", "mrt", "thermalcomfort", "thermal comfort")):
        return "A.辐射暖通-热舒适-Radiant HVAC and Thermal Comfort"
    if any(token in probe for token in ("envelope", "energy carbon", "operation control", "building energy", "mpc", "mlbe", "bem", "beec", "boc")):
        return "B.建筑能耗-围护结构-运行控制-Building Energy Envelope and Control"
    if any(token in probe for token in ("material", "emissivity", "radiative cooling", "infrared", "mtp", "prc", "ir")):
        return "C.传热-材料-辐射测量-Heat Transfer Materials and Radiation Measurement"
    if any(token in probe for token in ("ventilation", "cfd", "airflow", "indoor air", "voc", "vent")):
        return "D.通风-流场-室内环境-Ventilation Airflow and Indoor Environment"
    if any(token in probe for token in ("solar", "thermal storage", "phase change", "tes", "nzeb")):
        return "E.太阳能-蓄热-近零能耗-Solar TES and NZEB"
    if any(token in probe for token in ("machine learning", "deep learning", "neural", "optimization", "model predictive")):
        return "F.数据驱动-优化控制-Data Driven Optimization"
    if any(token in probe for token in ("rural", "residential", "policy", "bibliometric", "review")):
        return "G.场景综述-政策背景-Context Review and Policy"
    if any(token in probe for token in ("reference", "standard", "classic", "fundamentals", "ref")):
        return "H.基础参考-标准-工具-Reference Standards and Tools"
    return "Z.待人工复核-Unassigned"


def scope_tier(item_count: int, total_items: int, peripheral_rate: float, bridge_degree: int, potential_score: float) -> str:
    share = item_count / max(total_items, 1)
    if peripheral_rate >= 0.35:
        return "参考/外围"
    if item_count >= 70 or share >= 0.04 or (item_count >= 35 and bridge_degree >= 6 and potential_score >= 5.5):
        return "核心主线"
    if item_count >= 20 or (item_count >= 10 and bridge_degree >= 3):
        return "可并入支线"
    return "长尾备选"


def direction_score(
    item_count: int,
    total_items: int,
    bridge_degree: int,
    evidence_rate: float,
    peripheral_rate: float,
    empirical_count: int,
    modeling_count: int,
    ai_control_count: int,
) -> float:
    size_score = math.sqrt(item_count) / math.sqrt(max(total_items, 1)) * 10
    bridge_score = min(bridge_degree, 12) / 12 * 3
    evidence_score = evidence_rate * 2
    method_score = min(empirical_count + modeling_count + ai_control_count, 30) / 30 * 2
    penalty = peripheral_rate * 3
    return round(size_score + bridge_score + evidence_score + method_score - penalty, 2)


def build_outputs(items: list[dict[str, Any]], corpus: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_key = {item["item_key"]: item for item in items}
    collection_items: dict[str, set[str]] = defaultdict(set)
    collection_counters: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    collection_pair_counter: Counter[tuple[str, str]] = Counter()
    family_items: dict[str, set[str]] = defaultdict(set)
    namespace_counters: dict[str, Counter[str]] = {namespace: Counter() for namespace in NAMESPACES}
    years: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    with_abstract = 0
    with_text = 0

    for item in items:
        item_key = item["item_key"]
        record = corpus.get(item_key, {})
        year = str(record.get("year") or "")
        if year:
            years[year] += 1
        item_type = str(record.get("item_type") or "")
        if item_type:
            type_counter[item_type] += 1
        if record.get("abstract_present"):
            with_abstract += 1
        if record.get("has_normalized_text"):
            with_text += 1

        collections = item["collections"]
        for collection in collections:
            collection_items[collection].add(item_key)
            counters = collection_counters[collection]
            for namespace in NAMESPACES:
                values = item[f"{namespace.lower()}_tags"]
                counters[namespace.lower()].update(values)
                namespace_counters[namespace].update(values)
        for i, left in enumerate(collections):
            for right in collections[i + 1 :]:
                if left != right:
                    collection_pair_counter[tuple(sorted((left, right)))] += 1

    cooccurrence_rows: list[dict[str, Any]] = []
    bridge_counter: Counter[str] = Counter()
    for (left, right), count in collection_pair_counter.items():
        left_items = collection_items[left]
        right_items = collection_items[right]
        union_count = len(left_items | right_items)
        jaccard = count / union_count if union_count else 0
        cooccurrence_rows.append(
            {
                "left_collection": left,
                "right_collection": right,
                "cooccurrence_count": count,
                "jaccard": round(jaccard, 4),
            }
        )
        if count >= 2:
            bridge_counter[left] += 1
            bridge_counter[right] += 1

    cluster_rows: list[dict[str, Any]] = []
    for collection, keys in collection_items.items():
        counters = collection_counters[collection]
        item_count = len(keys)
        collection_records = [corpus.get(key, {}) for key in keys]
        evidence_hits = sum(1 for record in collection_records if record.get("abstract_present") or record.get("has_normalized_text"))
        evidence_rate = evidence_hits / item_count if item_count else 0
        statuses = counters["status"]
        peripheral_hits = sum(
            count
            for status, count in statuses.items()
            if any(status.startswith(prefix) for prefix in PERIPHERAL_STATUS_PREFIXES)
        )
        peripheral_rate = peripheral_hits / item_count if item_count else 0
        empirical_count = sum(count for method, count in counters["method"].items() if matches_any(method, EMPIRICAL_HINTS))
        modeling_count = sum(count for method, count in counters["method"].items() if matches_any(method, MODELING_HINTS))
        ai_control_count = sum(count for method, count in counters["method"].items() if matches_any(method, AI_CONTROL_HINTS))
        reference_count = sum(statuses.get(status, 0) for status in REFERENCE_STATUS)
        score = direction_score(
            item_count=item_count,
            total_items=len(items),
            bridge_degree=bridge_counter[collection],
            evidence_rate=evidence_rate,
            peripheral_rate=peripheral_rate,
            empirical_count=empirical_count,
            modeling_count=modeling_count,
            ai_control_count=ai_control_count,
        )
        family = classify_family(collection, counters)
        for key in keys:
            family_items[family].add(key)
        cluster_rows.append(
            {
                "collection": collection,
                "collection_code": split_collection_name(collection)["code"],
                "family": family,
                "item_count": item_count,
                "share": round(item_count / max(len(items), 1), 4),
                "bridge_degree": bridge_counter[collection],
                "evidence_rate": round(evidence_rate, 4),
                "peripheral_rate": round(peripheral_rate, 4),
                "reference_count": reference_count,
                "empirical_method_count": empirical_count,
                "modeling_method_count": modeling_count,
                "ai_control_method_count": ai_control_count,
                "potential_score": score,
                "scope_tier": scope_tier(item_count, len(items), peripheral_rate, bridge_counter[collection], score),
                "top_fields": "; ".join(f"{v} ({c})" for v, c in counters["field"].most_common(8)),
                "top_methods": "; ".join(f"{v} ({c})" for v, c in counters["method"].most_common(8)),
                "top_objects": "; ".join(f"{v} ({c})" for v, c in counters["object"].most_common(8)),
                "top_parameters": "; ".join(f"{v} ({c})" for v, c in counters["parameter"].most_common(8)),
                "top_statuses": "; ".join(f"{v} ({c})" for v, c in statuses.most_common(8)),
                "sample_item_keys": "; ".join(sorted(keys)[:8]),
            }
        )

    item_rows: list[dict[str, Any]] = []
    for item in items:
        key = item["item_key"]
        record = corpus.get(key, {})
        item_rows.append(
            {
                "item_key": key,
                "zotero_link": f"zotero://select/library/items/{key}",
                "title": record.get("title", ""),
                "year": record.get("year", ""),
                "item_type": record.get("item_type", ""),
                "publication": record.get("publication", ""),
                "abstract_present": "yes" if record.get("abstract_present") else "no",
                "has_normalized_text": "yes" if record.get("has_normalized_text") else "no",
                "collections": "; ".join(item["collections"]),
                "fields": "; ".join(item["field_tags"]),
                "methods": "; ".join(item["method_tags"]),
                "objects": "; ".join(item["object_tags"]),
                "parameters": "; ".join(item["parameter_tags"]),
                "statuses": "; ".join(item["status_tags"]),
                "types": "; ".join(item["type_tags"]),
                "explanation": item["explanation"],
            }
        )

    family_rows = []
    for family, keys in family_items.items():
        child_clusters = [row for row in cluster_rows if row["family"] == family]
        field_counter: Counter[str] = Counter()
        method_counter: Counter[str] = Counter()
        object_counter: Counter[str] = Counter()
        parameter_counter: Counter[str] = Counter()
        for row in child_clusters:
            collection = row["collection"]
            field_counter.update(collection_counters[collection]["field"])
            method_counter.update(collection_counters[collection]["method"])
            object_counter.update(collection_counters[collection]["object"])
            parameter_counter.update(collection_counters[collection]["parameter"])
        family_rows.append(
            {
                "family": family,
                "item_count": len(keys),
                "collection_count": len(child_clusters),
                "top_collections": sorted(child_clusters, key=lambda row: (-row["item_count"], row["collection"]))[:8],
                "top_fields": field_counter.most_common(10),
                "top_methods": method_counter.most_common(10),
                "top_objects": object_counter.most_common(10),
                "top_parameters": parameter_counter.most_common(10),
            }
        )

    return {
        "items": items,
        "by_key": by_key,
        "cluster_rows": sorted(cluster_rows, key=lambda row: (-row["potential_score"], -row["item_count"], row["collection"])),
        "cooccurrence_rows": sorted(cooccurrence_rows, key=lambda row: (-row["cooccurrence_count"], -row["jaccard"], row["left_collection"])),
        "item_rows": sorted(item_rows, key=lambda row: row["item_key"]),
        "family_rows": sorted(family_rows, key=lambda row: row["family"]),
        "summary": {
            "generated_at": utc_now(),
            "source_plan": str(DEFAULT_PLAN_MD),
            "source_corpus": str(DEFAULT_CORPUS_JSONL),
            "items_total": len(items),
            "unique_items": len(by_key),
            "corpus_records_matched": sum(1 for key in by_key if key in corpus),
            "collections_total": len(collection_items),
            "collection_assignments_total": sum(len(item["collections"]) for item in items),
            "unique_tags_total": len({tag for item in items for tag in item["tags"]}),
            "items_with_abstract": with_abstract,
            "items_with_normalized_text": with_text,
            "top_item_types": top_values(type_counter, 20),
            "year_min": min(years) if years else "",
            "year_max": max(years) if years else "",
            "top_years": top_values(years, 20),
            "namespace_top": {namespace: top_values(counter, 25) for namespace, counter in namespace_counters.items()},
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def render_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    cluster_rows = result["cluster_rows"]
    family_rows = result["family_rows"]
    cooccurrence_rows = result["cooccurrence_rows"]
    core = [row for row in cluster_rows if row["scope_tier"] == "核心主线"]
    branch = [row for row in cluster_rows if row["scope_tier"] == "可并入支线"]
    longtail = [row for row in cluster_rows if row["scope_tier"] == "长尾备选"]
    peripheral = [row for row in cluster_rows if row["scope_tier"] == "参考/外围"]

    lines: list[str] = []
    lines.append("# Zotero 1600 条文献聚合与研究方向收束报告")
    lines.append("")
    lines.append("## 1. 数据来源与边界")
    lines.append("")
    lines.append(f"- 条目级分类草案：`{DEFAULT_PLAN_MD}`。")
    lines.append(f"- 题录与全文状态语料：`{DEFAULT_CORPUS_JSONL}`。")
    lines.append(f"- 解析到 item：{summary['items_total']} 条；唯一 item：{summary['unique_items']} 条。")
    lines.append(f"- 匹配到语料记录：{summary['corpus_records_matched']} 条。")
    lines.append(f"- collection 数：{summary['collections_total']}；collection 归属次数：{summary['collection_assignments_total']}。")
    lines.append(f"- unique governance tags：{summary['unique_tags_total']}。")
    lines.append(f"- 有 abstract：{summary['items_with_abstract']} 条；有 normalized PDF text：{summary['items_with_normalized_text']} 条。")
    lines.append("")
    lines.append("本报告是只读聚合与初筛建议，不写入 Zotero，不删除或移动 PDF，不把候选方向写成已证实 research gap。")
    lines.append("")
    lines.append("## 2. 方法")
    lines.append("")
    lines.append("1. 解析 `local-semantic-governance-plan.md` 中每条 item 的 collection、`#Field`、`#Method`、`#Object`、`#Parameter`、`#Status`、`#Type`。")
    lines.append("2. 与 `ai-governance-corpus.jsonl` 按 item key 对齐，补充题名、年份、类型、abstract 与 normalized text 状态。")
    lines.append("3. 做频次统计、collection 共现、标签命名空间聚合，形成方向簇。")
    lines.append("4. 对每个方向簇计算初筛分数：规模、共现桥接度、证据可用率、方法支撑、外围/待复核惩罚。")
    lines.append("5. 按 `核心主线 / 可并入支线 / 长尾备选 / 参考外围` 收束，供人工二次判断。")
    lines.append("")
    lines.append("## 3. 一阶聚合结果：主题家族")
    lines.append("")
    lines.append("说明：同一 item 最多可归入 2 个 collections，因此主题家族之间允许交叉，家族 item 数不能简单相加为 1600。")
    lines.append("")
    lines.append("| 主题家族 | items | collections | 主要 collections |")
    lines.append("|---|---:|---:|---|")
    for row in sorted(family_rows, key=lambda item: (-item["item_count"], item["family"])):
        top_collections = "; ".join(f"{item['collection_code']}({item['item_count']})" for item in row["top_collections"][:6])
        lines.append(f"| {row['family']} | {row['item_count']} | {row['collection_count']} | {top_collections} |")
    lines.append("")
    lines.append("## 4. 核心主线")
    lines.append("")
    lines.append("| collection | items | score | bridge | evidence | top methods | top parameters |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for row in core[:18]:
        lines.append(
            f"| `{row['collection']}` | {row['item_count']} | {row['potential_score']} | {row['bridge_degree']} | "
            f"{row['evidence_rate']:.2f} | {row['top_methods']} | {row['top_parameters']} |"
        )
    lines.append("")
    lines.append("## 5. 可并入支线")
    lines.append("")
    lines.append("| collection | items | score | 建议归并逻辑 |")
    lines.append("|---|---:|---:|---|")
    for row in branch[:30]:
        lines.append(
            f"| `{row['collection']}` | {row['item_count']} | {row['potential_score']} | "
            f"{row['family']}；fields: {row['top_fields']} |"
        )
    lines.append("")
    lines.append("## 6. 高价值交叉方向")
    lines.append("")
    lines.append("| collection A | collection B | 共现次数 | Jaccard | 初步含义 |")
    lines.append("|---|---|---:|---:|---|")
    for row in cooccurrence_rows[:25]:
        left_code = split_collection_name(row["left_collection"])["code"]
        right_code = split_collection_name(row["right_collection"])["code"]
        meaning = f"{left_code} 与 {right_code} 的交叉文献，可作为综述矩阵或选题收束入口。"
        lines.append(
            f"| `{row['left_collection']}` | `{row['right_collection']}` | "
            f"{row['cooccurrence_count']} | {row['jaccard']:.4f} | {meaning} |"
        )
    lines.append("")
    lines.append("## 7. 收束建议")
    lines.append("")
    lines.append("### 建议优先推进")
    lines.append("")
    lines.append("- 辐射暖通系统与热舒适：文献规模最大，且和热舒适、传热、蓄热、太阳能、控制都有交叉，适合作为主干方向。")
    lines.append("- 建筑围护结构、建筑运行控制与能耗模拟：和间歇用能、热惰性、能耗预测、MPC 等方向可形成方法链。")
    lines.append("- 材料热物性、红外辐射测量与被动辐射冷却：适合作为材料/测量/辐射机理支撑方向，不宜和系统运行问题混为一类。")
    lines.append("")
    lines.append("### 建议并入或作为支撑")
    lines.append("")
    lines.append("- 通风、CFD 与室内环境可作为辐射系统和热舒适的边界条件/耦合机制。")
    lines.append("- 太阳能、TES、NZEB 可作为供能侧或蓄热侧支撑，不建议单独扩成过宽方向。")
    lines.append("- 机器学习、优化控制与 MPC 可作为方法主线嵌入建筑运行控制，不建议只按算法名单独成题。")
    lines.append("")
    lines.append("### 建议暂缓作为主线")
    lines.append("")
    lines.append("- 纯综述、标准、教材、基础理论和政策背景类条目应保留为证据库或方法背景。")
    lines.append("- `#Status/PeripheralTopic`、`#Status/PeripheralMaterial`、`#Status/MissingAbstract` 较多的 collection 应先人工复核后再纳入主线。")
    lines.append("")
    lines.append("## 8. 输出文件")
    lines.append("")
    lines.append(f"- 机器条目矩阵：`{DEFAULT_ITEM_MATRIX}`")
    lines.append(f"- 方向簇表：`{DEFAULT_CLUSTER_CSV}`")
    lines.append(f"- collection 共现边表：`{DEFAULT_COOCCURRENCE_CSV}`")
    lines.append(f"- 聚合摘要 JSON：`{DEFAULT_SUMMARY_JSON}`")
    lines.append("")
    lines.append("## 9. 需要人工复核的边界")
    lines.append("")
    lines.append(f"- 长尾备选 collection：{len(longtail)} 个；参考/外围 collection：{len(peripheral)} 个。")
    lines.append("- 初筛分数用于排序，不等同于学术价值或创新性。真正选题还需要进入 open / contribution / feasibility gate。")
    lines.append("- 本报告没有重新抽取全文，也没有调用外部数据库核查期刊等级或引用影响。")
    lines.append("")
    return "\n".join(lines)


def command_aggregate(args: argparse.Namespace) -> int:
    items = parse_plan(Path(args.plan_md))
    corpus = load_corpus(Path(args.corpus_jsonl))
    result = build_outputs(items, corpus)

    write_csv(
        Path(args.item_matrix),
        result["item_rows"],
        [
            "item_key",
            "zotero_link",
            "title",
            "year",
            "item_type",
            "publication",
            "abstract_present",
            "has_normalized_text",
            "collections",
            "fields",
            "methods",
            "objects",
            "parameters",
            "statuses",
            "types",
            "explanation",
        ],
    )
    write_csv(
        Path(args.cluster_csv),
        result["cluster_rows"],
        [
            "collection",
            "collection_code",
            "family",
            "item_count",
            "share",
            "bridge_degree",
            "evidence_rate",
            "peripheral_rate",
            "reference_count",
            "empirical_method_count",
            "modeling_method_count",
            "ai_control_method_count",
            "potential_score",
            "scope_tier",
            "top_fields",
            "top_methods",
            "top_objects",
            "top_parameters",
            "top_statuses",
            "sample_item_keys",
        ],
    )
    write_csv(
        Path(args.cooccurrence_csv),
        result["cooccurrence_rows"],
        ["left_collection", "right_collection", "cooccurrence_count", "jaccard"],
    )
    write_json(
        Path(args.summary_json),
        {
            **result["summary"],
            "families": result["family_rows"],
            "top_clusters": result["cluster_rows"][:50],
            "top_cooccurrences": result["cooccurrence_rows"][:100],
        },
    )
    report = render_report(result)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(report, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "items_total": result["summary"]["items_total"],
                "collections_total": result["summary"]["collections_total"],
                "report_md": str(args.report_md),
                "item_matrix": str(args.item_matrix),
                "cluster_csv": str(args.cluster_csv),
                "cooccurrence_csv": str(args.cooccurrence_csv),
                "summary_json": str(args.summary_json),
            },
            ensure_ascii=False,
        )
    )
    return 0
