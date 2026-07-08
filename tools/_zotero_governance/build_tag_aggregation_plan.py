"""Aggregate item-level Zotero governance tags into a compact tag plan.

This tool reads ResearchOS dry-run outputs only. It does not write to Zotero.
The goal is to make tags complementary to collections: collections carry the
main research direction, while tags carry cross-cutting facets such as method,
object, parameter, evidence/status, and item type.
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

RESEARCHOS_ROOT = Path(__file__).resolve().parents[1]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import DOCS_LIBRARY_GOVERNANCE, M002_LIBRARY_GOVERNANCE


DEFAULT_ITEM_MATRIX = M002_LIBRARY_GOVERNANCE / "research-direction-item-matrix.csv"
DEFAULT_COLLECTION_ASSIGNMENTS = M002_LIBRARY_GOVERNANCE / "collection-restructure-assignment-plan.csv"
DEFAULT_ALIAS_MAP = M002_LIBRARY_GOVERNANCE / "tag-aggregation-alias-map.csv"
DEFAULT_ITEM_TAG_PLAN = M002_LIBRARY_GOVERNANCE / "tag-aggregation-item-plan.csv"
DEFAULT_TAXONOMY_JSON = M002_LIBRARY_GOVERNANCE / "tag-aggregation-taxonomy.json"
DEFAULT_PERIPHERAL_TAGS = M002_LIBRARY_GOVERNANCE / "peripheral-tags-for-collection-review.csv"
DEFAULT_PARAMETER_TAGS = M002_LIBRARY_GOVERNANCE / "parameter-tags-review.csv"
DEFAULT_REPORT_MD = DOCS_LIBRARY_GOVERNANCE / "tag-aggregation-plan.md"

TAG_COLUMNS = ("fields", "methods", "objects", "parameters", "statuses", "types")
COLUMN_NAMESPACE = {
    "fields": "Field",
    "methods": "Method",
    "objects": "Object",
    "parameters": "Parameter",
    "statuses": "Status",
    "types": "Type",
}
NAMESPACE_LIMITS = {
    "Field": 2,
    "Method": 2,
    "Object": 2,
    "Parameter": 3,
    "Governance": 4,
    "Type": 1,
}
FIELD_COLLECTION_EQUIVALENCE = {
    "#Field/RadiantSystems": {"RHVAC"},
    "#Field/IndoorThermalComfort": {"ITC", "PCE", "ADAPT", "OTC", "OUTC", "SLEEP", "CHILD"},
    "#Field/BuildingEnergyEnvelope": {"BEEC", "HSCW", "REFIT"},
    "#Field/BuildingOperationControl": {"BOC"},
    "#Field/ModelPredictiveControl": {"MPC"},
    "#Field/MachineLearningEnergy": {"MLBE"},
    "#Field/HeatTransferModeling": {"HTM"},
    "#Field/ThermalStoragePCM": {"TES", "TABS"},
    "#Field/SolarEnergy": {"SOLAR", "SBE", "BIPV"},
    "#Field/MaterialRadiativeProperties": {"MTP"},
    "#Field/PassiveRadiativeCooling": {"PRC"},
    "#Field/InfraredMeasurement": {"IR"},
    "#Field/VentilationAirflow": {"VENT", "CFD"},
    "#Field/IndoorAirQualityVOC": {"IAQ"},
    "#Field/FurnitureIndoorEnvironment": {"FURN"},
    "#Field/HygrothermalCondensation": {"HYGRO"},
    "#Field/CarbonLowCarbonPolicy": {"POLICY", "GB", "LCA", "BSC"},
    "#Field/LifeCycleCircularity": {"LCA", "LCC", "LCCOST"},
    "#Field/RuralUrbanContext": {"RHE", "URBD", "GIS", "SOC"},
    "#Field/DigitalBIMScanning": {"BIM", "DIGI"},
    "#Field/StandardsReference": {"REF", "STD"},
}
QUANTIFIABLE_PARAMETER_TAGS = {
    "#Parameter/AirChangeRate",
    "#Parameter/AirTemperature",
    "#Parameter/AirVelocity",
    "#Parameter/CarbonEmission",
    "#Parameter/CO2Concentration",
    "#Parameter/CondensationRisk",
    "#Parameter/ControlHorizon",
    "#Parameter/CoolingCapacity",
    "#Parameter/CoolingLoad",
    "#Parameter/DewPointTemperature",
    "#Parameter/DiffusionCoefficient",
    "#Parameter/Emissivity",
    "#Parameter/EnergyConsumption",
    "#Parameter/EnergyEfficiency",
    "#Parameter/EnergyFlexibility",
    "#Parameter/EnergySavingRate",
    "#Parameter/FormaldehydeConcentration",
    "#Parameter/HeatFlux",
    "#Parameter/HeatOutput",
    "#Parameter/HeatingCapacity",
    "#Parameter/HeatingLoad",
    "#Parameter/HeatTransferCoefficient",
    "#Parameter/Illuminance",
    "#Parameter/InsulationThickness",
    "#Parameter/LatentHeat",
    "#Parameter/MeanRadiantTemperature",
    "#Parameter/OperatingCost",
    "#Parameter/OperativeTemperature",
    "#Parameter/Orientation",
    "#Parameter/PaybackPeriod",
    "#Parameter/PipeSpacing",
    "#Parameter/PM25Concentration",
    "#Parameter/PMV",
    "#Parameter/PPD",
    "#Parameter/PredictionError",
    "#Parameter/RadiantTemperatureAsymmetry",
    "#Parameter/Reflectance",
    "#Parameter/RelativeHumidity",
    "#Parameter/SetpointTemperature",
    "#Parameter/SolarFraction",
    "#Parameter/SolarIrradiance",
    "#Parameter/SurfaceTemperature",
    "#Parameter/ThermalConductivity",
    "#Parameter/ThermalMass",
    "#Parameter/ThermalResistance",
    "#Parameter/ThermalSensationVote",
    "#Parameter/ThermalStorageCapacity",
    "#Parameter/Transmittance",
    "#Parameter/TVOCConcentration",
    "#Parameter/UValue",
    "#Parameter/VentilationEffectiveness",
    "#Parameter/VentilationRate",
    "#Parameter/WindowWallRatio",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def split_tags(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def tag_value(tag: str) -> str:
    match = re.match(r"^#[^/]+/(.+)$", tag.strip())
    return match.group(1) if match else tag.strip().lstrip("#")


def compact_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def zotero_link(key: str) -> str:
    return f"[{key}](zotero://select/library/items/{key})"


def fallback_type_tag(item_type: str) -> str:
    mapping = {
        "journalArticle": "#Type/JournalArticle",
        "thesis": "#Type/Thesis",
        "book": "#Type/Book",
        "standard": "#Type/Standard",
        "conferencePaper": "#Type/ConferencePaper",
        "webpage": "#Type/Webpage",
        "report": "#Type/Report",
        "bookSection": "#Type/BookSection",
        "computerProgram": "#Type/Software",
        "patent": "#Type/Patent",
        "newspaperArticle": "#Type/NewsArticle",
        "document": "#Type/Document",
    }
    return mapping.get(item_type, "#Type/Document")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def top_level_from_path(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else path


def collection_code(collection: str) -> str:
    if "/" in collection:
        collection = collection.split("/", 1)[1]
    return collection.split("-", 1)[0].strip()


def item_collection_codes(collections_value: str) -> set[str]:
    codes: set[str] = set()
    for collection in split_tags(collections_value):
        code = collection_code(collection)
        if code:
            codes.add(code)
    return codes


def item_top_levels(assignments: list[dict[str, str]]) -> dict[str, list[str]]:
    by_key: dict[str, list[str]] = {}
    for row in assignments:
        tops: list[str] = []
        for column in ("target_collection_1", "target_collection_2", "target_collection_3"):
            path = row.get(column, "")
            if path:
                top = top_level_from_path(path)
                if top and top not in tops:
                    tops.append(top)
        by_key[row["item_key"]] = tops
    return by_key


def normalized_entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0 or len(counter) <= 1:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        p = count / total
        entropy -= p * math.log(p)
    return entropy / math.log(len(counter))


def choose_by_rules(namespace: str, value: str) -> str | None:
    token = compact_token(value)

    field_rules = [
        ("RadiantSystems", ("radiant", "floorheating", "floorcooling", "tabs", "ceilingcooling", "ondol")),
        ("IndoorThermalComfort", ("thermalcomfort", "mrt", "pmv", "thermalsensation", "personalcomfort", "skintemperature")),
        ("BuildingEnergyEnvelope", ("envelope", "insulation", "window", "uvalue", "thermalbridge", "retrofit")),
        ("BuildingOperationControl", ("operation", "control", "setpoint", "energyflexibility", "loadshifting", "intermittent")),
        ("ModelPredictiveControl", ("modelpredictivecontrol", "mpc", "predictivecontrol")),
        ("MachineLearningEnergy", ("machinelearning", "deeplearning", "neural", "prediction", "gaussianprocess", "kan")),
        ("HeatTransferModeling", ("heattransfer", "conduction", "convection", "thermalmodel", "thermalnetwork", "hammodel")),
        ("ThermalStoragePCM", ("thermalstorage", "phasechange", "pcm", "latentheat", "heatstorage")),
        ("SolarEnergy", ("solar", "photovoltaic", "bipv", "pv", "sunspot")),
        ("MaterialRadiativeProperties", ("emissivity", "radiativepropert", "reflectance", "transmittance", "lowemissivity")),
        ("PassiveRadiativeCooling", ("radiativecooling", "coolroof", "coolcoating", "daytimeradiative")),
        ("InfraredMeasurement", ("infrared", "thermograph", "spectral", "radiometry", "true temperature")),
        ("VentilationAirflow", ("ventilation", "airflow", "ufad", "displacement", "airdistribution", "aircurtain")),
        ("IndoorAirQualityVOC", ("iaq", "indoorair", "voc", "formaldehyde", "infection", "pm25", "airquality")),
        ("FurnitureIndoorEnvironment", ("furniture", "furnished", "officefurniture", "woodfurniture")),
        ("HygrothermalCondensation", ("hygro", "humidity", "condensation", "moisture", "dehumid")),
        ("CarbonLowCarbonPolicy", ("carbon", "emission", "neutrality", "lowcarbon", "policy")),
        ("LifeCycleCircularity", ("lifecycle", "lca", "circular", "11r", "cost")),
        ("RuralUrbanContext", ("rural", "urban", "village", "settlement", "city")),
        ("DigitalBIMScanning", ("bim", "scan", "digital", "reconstruction", "immersive")),
        ("StandardsReference", ("standard", "handbook", "fundamental", "reference")),
    ]
    method_rules = [
        ("ExperimentalStudy", ("experiment", "experimental", "test", "chamber")),
        ("FieldMeasurement", ("fieldmeasurement", "onsite", "monitoring", "longitudinal", "fieldtest")),
        ("HumanSubjectStudy", ("humansubject", "questionnaire", "survey", "subjective", "interview")),
        ("NumericalSimulation", ("numerical", "simulation", "simulink", "cosimulation")),
        ("EnergySimulation", ("energyplus", "dest", "doe2", "trnsys", "designbuilder", "energysimulation")),
        ("CFDSimulation", ("cfd", "fluent", "stream", "computationalfluid")),
        ("AnalyticalModeling", ("analytical", "model", "reducedorder", "thermalnetwork", "finiteelement", "finitevolume")),
        ("ModelPredictiveControl", ("modelpredictivecontrol", "predictivecontrol", "mpc")),
        ("MachineLearning", ("machinelearning", "deeplearning", "neural", "randomforest", "gaussianprocess", "kan")),
        ("Optimization", ("optimization", "geneticalgorithm", "multiobjective", "metaheuristic")),
        ("Review", ("review", "literaturereview", "stateoftheart", "systematic")),
        ("BibliometricAnalysis", ("bibliometric", "citespace", "vosviewer")),
        ("MeasurementMethod", ("measurement", "thermography", "spectroscopy", "radiometry", "calibration")),
        ("Benchmarking", ("benchmark", "comparison", "comparative")),
        ("StatisticalAnalysis", ("statistical", "regression", "correlation", "sensitivityanalysis", "markov")),
        ("LifeCycleAssessment", ("lifecycle", "lca", "economic", "exergy")),
    ]
    object_rules = [
        ("RadiantSystems", ("radiant", "floorheating", "floorcooling", "tabs", "ceiling", "panel")),
        ("HVACSystems", ("hvac", "aircondition", "heatpump", "chiller", "terminal")),
        ("ResidentialBuildings", ("residential", "dwelling", "housing", "apartment")),
        ("OfficeEducationalBuildings", ("office", "classroom", "school", "university", "campus")),
        ("BuildingEnvelopeWindows", ("envelope", "wall", "window", "roof", "glass", "insulating")),
        ("PCMMaterials", ("pcm", "phasechange", "thermalstorage")),
        ("RadiativeMaterialsCoatings", ("coating", "film", "porous", "polymer", "textile", "material")),
        ("InfraredMeasurementObjects", ("infrared", "spectral", "blackbody", "platinum", "imager")),
        ("VentilationAirflowSystems", ("ventilation", "airflow", "ufad", "displacement", "solar chimney")),
        ("FurnitureIndoorObjects", ("furniture", "wood", "desk", "partition", "fixture")),
        ("UrbanRuralContext", ("urban", "rural", "village", "city", "heritage")),
        ("DigitalModelsTools", ("bim", "software", "model", "zotero", "addon", "energyplus", "dest", "doe2")),
    ]
    parameter_rules = [
        ("#Field/IndoorThermalComfort", ("thermalcomfort", "indoorthermalenvironment")),
        ("#Field/IndoorAirQualityVOC", ("indoorairquality", "iaq", "airquality")),
        ("#Field/BuildingOperationControl", ("controlstrategy", "operationstrategy", "intermittentoperation")),
        ("#Field/FurnitureIndoorEnvironment", ("furniturearrangement", "furniturelayout", "roomlayout", "spacelayout")),
        ("MeanRadiantTemperature", ("mrt", "meanradianttemperature")),
        ("OperativeTemperature", ("operativetemperature",)),
        ("AirTemperature", ("airtemperature", "roomtemperature", "indoorairtemperature", "outdoorairtemperature")),
        ("SurfaceTemperature", ("surfacetemperature", "floorsurfacetemperature", "skintemperature", "supplywatertemperature", "truetemperature", "temperaturefield")),
        ("PMV", ("pmv",)),
        ("PPD", ("ppd",)),
        ("ThermalSensationVote", ("thermalsensation", "localthermalsensation", "thermalvote")),
        ("EnergyConsumption", ("energyconsumption", "buildingenergyconsumption", "annualenergyconsumption", "airconditioningenergyconsumption")),
        ("EnergySavingRate", ("energysavingrate", "energysaving", "energysavings", "energysavingpotential")),
        ("EnergyEfficiency", ("energyefficiency",)),
        ("CoolingLoad", ("coolingload", "latentload")),
        ("HeatingLoad", ("heatingload",)),
        ("CoolingCapacity", ("coolingcapacity",)),
        ("HeatingCapacity", ("heatingcapacity",)),
        ("EnergyFlexibility", ("energyflexibility", "loadshifting", "peakloadreduction")),
        ("CarbonEmission", ("carbonemission", "co2emission", "ghgemission", "greenhousegasemission")),
        ("SolarIrradiance", ("solarirradiance", "solarradiation", "shortwaveirradiance")),
        ("SolarFraction", ("solarfraction",)),
        ("Illuminance", ("illuminance", "daylightfactor")),
        ("Emissivity", ("emissivity", "infraredemissivity", "spectralemissivity", "surfaceemissivity", "normalemissivity")),
        ("Reflectance", ("reflectance", "solarreflectance", "reflectivity")),
        ("Transmittance", ("transmittance",)),
        ("RelativeHumidity", ("relativehumidity", "humidity")),
        ("DewPointTemperature", ("dewpoint",)),
        ("CondensationRisk", ("condensationrisk",)),
        ("#Field/HygrothermalCondensation", ("condensationcontrol", "condensationprevention", "condensation")),
        ("ThermalConductivity", ("thermalconductivity",)),
        ("ThermalResistance", ("thermalresistance",)),
        ("UValue", ("uvalue",)),
        ("HeatTransferCoefficient", ("heattransfercoefficient",)),
        ("HeatFlux", ("heatflux", "radiativeheatflux")),
        ("ThermalStorageCapacity", ("thermalstoragecapacity", "heatstoragecapacity")),
        ("ThermalMass", ("thermalmass", "thermalinertia")),
        ("#Field/ThermalStoragePCM", ("thermalstorage", "heatstorage", "latentheatstorage")),
        ("LatentHeat", ("latentheat", "latentheatstorage")),
        ("AirChangeRate", ("airchangerate",)),
        ("AirVelocity", ("airvelocity",)),
        ("VentilationRate", ("ventilationrate",)),
        ("VentilationEffectiveness", ("ventilationeffectiveness", "ventilationefficiency")),
        ("CO2Concentration", ("co2concentration",)),
        ("TVOCConcentration", ("tvoc", "vocconcentration", "voc")),
        ("PM25Concentration", ("pm25",)),
        ("FormaldehydeConcentration", ("formaldehyde",)),
        ("SetpointTemperature", ("setpoint", "indoorsetpoint")),
        ("PredictionError", ("predictionerror", "modelerror", "measurementaccuracy", "accuracy")),
        ("ControlHorizon", ("controlhorizon",)),
        ("OperatingCost", ("operatingcost", "energycost", "electricityprice")),
        ("PaybackPeriod", ("payback",)),
        ("PipeSpacing", ("pipespacing",)),
        ("WindowWallRatio", ("windowwallratio",)),
        ("InsulationThickness", ("insulationthickness", "fillinglayerthickness")),
        ("Orientation", ("orientation", "azimuth")),
        ("DiffusionCoefficient", ("diffusioncoefficient",)),
        ("RadiantTemperatureAsymmetry", ("radiantasymmetry",)),
        ("HeatOutput", ("heatoutput",)),
    ]
    type_rules = [
        ("ExperimentalStudy", ("experimental", "experiment", "measurement")),
        ("SimulationStudy", ("simulation", "numerical", "modeling")),
        ("Review", ("review", "bibliometric", "synthesis")),
        ("MethodStudy", ("method", "validation", "evaluation", "benchmark")),
        ("ComparativeStudy", ("comparison", "comparative")),
        ("ControlOptimizationStudy", ("control", "optimization")),
        ("Thesis", ("thesis",)),
        ("Book", ("book", "handbook", "textbook")),
        ("Standard", ("standard", "guideline")),
        ("Report", ("report", "policy")),
        ("PatentOrSoftware", ("patent", "software", "computerprogram")),
    ]
    rules_by_namespace = {
        "Field": field_rules,
        "Method": method_rules,
        "Object": object_rules,
        "Parameter": parameter_rules,
        "Type": type_rules,
    }
    for canonical, hints in rules_by_namespace.get(namespace, []):
        if any(compact_token(hint) in token for hint in hints):
            return canonical if canonical.startswith("#") else f"#{namespace}/{canonical}"
    return None


def direct_normalize(namespace: str, tag: str, count: int) -> str | None:
    value = tag_value(tag)
    token = compact_token(value)
    if namespace == "Status":
        if "peripheral" in token:
            return None
        governance_rules = [
            ("NeedsManualReview", ("needsmanualreview", "manualreview")),
            ("MissingMetadata", ("missingabstract", "missing")),
            ("PotentialDuplicate", ("potentialduplicate", "duplicate")),
            ("NonLiteratureItem", ("nonliterature", "softwareparameter", "addon")),
            ("DoNotModify", ("donotmodify",)),
        ]
        for canonical, hints in governance_rules:
            if any(compact_token(hint) in token for hint in hints):
                return f"#Governance/{canonical}"
        if "policy" in token:
            return "#Type/PolicyDocument"
        if "report" in token:
            return "#Type/Report"
        if "standard" in token:
            return "#Type/Standard"
        if "handbook" in token or "textbook" in token or "reference" in token:
            return "#Type/ReferenceWork"
        if "conferencepaper" in token:
            return "#Type/ConferencePaper"
    canonical = choose_by_rules(namespace, value)
    if canonical:
        if namespace == "Parameter" and canonical.startswith("#Parameter/") and canonical not in QUANTIFIABLE_PARAMETER_TAGS:
            return None
        return canonical
    if namespace == "Status":
        return None
    if namespace == "Parameter":
        return None
    if namespace == "Type":
        return f"#Type/{value}" if count >= 2 else None
    if count >= 3:
        safe_value = re.sub(r"[^A-Za-z0-9]+", "", value)
        return f"#{namespace}/{safe_value}" if safe_value else None
    return None


def collect_tag_stats(
    item_rows: list[dict[str, str]],
    top_levels_by_item: dict[str, list[str]],
) -> tuple[dict[str, Counter[str]], dict[str, Counter[str]], dict[str, list[str]]]:
    counts: dict[str, Counter[str]] = {namespace: Counter() for namespace in COLUMN_NAMESPACE.values()}
    top_counts: dict[str, Counter[str]] = defaultdict(Counter)
    item_tags: dict[str, list[str]] = {}
    for row in item_rows:
        key = row["item_key"]
        tags_for_item: list[str] = []
        for column in TAG_COLUMNS:
            namespace = COLUMN_NAMESPACE[column]
            for tag in split_tags(row.get(column, "")):
                counts[namespace][tag] += 1
                tags_for_item.append(tag)
                for top in top_levels_by_item.get(key, []):
                    top_counts[tag][top] += 1
        item_tags[key] = tags_for_item
    return counts, top_counts, item_tags


def build_alias_map(
    counts: dict[str, Counter[str]],
    top_counts: dict[str, Counter[str]],
) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    rows: list[dict[str, Any]] = []
    mapping: dict[str, str | None] = {}
    for namespace, counter in counts.items():
        for original_tag, count in counter.items():
            canonical = direct_normalize(namespace, original_tag, count)
            entropy = normalized_entropy(top_counts[original_tag])
            if canonical:
                action = "map_to_canonical"
                if canonical == original_tag:
                    action = "keep"
                reason = "keyword/frequency normalized"
            else:
                action = "move_to_collection_review" if namespace == "Status" and "peripheral" in compact_token(original_tag) else "drop_long_tail"
                reason = (
                    "peripheral status should be resolved by collection placement"
                    if action == "move_to_collection_review"
                    else "singleton or low-frequency tag without stable aggregation rule"
                )
            mapping[original_tag] = canonical
            rows.append(
                {
                    "namespace": namespace,
                    "original_tag": original_tag,
                    "canonical_tag": canonical or "",
                    "action": action,
                    "item_count": count,
                    "top_level_entropy": round(entropy, 4),
                    "top_level_count": len(top_counts[original_tag]),
                    "top_levels": "; ".join(f"{top} ({n})" for top, n in top_counts[original_tag].most_common(8)),
                    "reason": reason,
                }
            )
    return sorted(rows, key=lambda row: (row["namespace"], row["action"], -int(row["item_count"]), row["original_tag"])), mapping


def select_item_tags(
    original_tags: list[str],
    mapping: dict[str, str | None],
    collection_codes: set[str],
) -> tuple[list[str], list[str]]:
    by_namespace: dict[str, list[str]] = defaultdict(list)
    suppressed_fields: list[str] = []
    for original in original_tags:
        canonical = mapping.get(original)
        if not canonical:
            continue
        namespace = canonical.split("/", 1)[0].lstrip("#")
        if namespace == "Field" and FIELD_COLLECTION_EQUIVALENCE.get(canonical, set()) & collection_codes:
            if canonical not in suppressed_fields:
                suppressed_fields.append(canonical)
            continue
        if canonical not in by_namespace[namespace]:
            by_namespace[namespace].append(canonical)
    selected: list[str] = []
    for namespace in ("Field", "Method", "Object", "Parameter", "Governance", "Type"):
        selected.extend(by_namespace.get(namespace, [])[: NAMESPACE_LIMITS[namespace]])
    return selected, suppressed_fields


def build_item_tag_plan(
    item_rows: list[dict[str, str]],
    item_tags: dict[str, list[str]],
    mapping: dict[str, str | None],
    collection_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    governance_by_key = {
        row["item_key"]: split_tags(row.get("proposed_governance_tags", ""))
        for row in collection_rows
    }
    output_rows: list[dict[str, Any]] = []
    for row in item_rows:
        key = row["item_key"]
        collection_codes = item_collection_codes(row.get("collections", ""))
        canonical_tags, suppressed_fields = select_item_tags(item_tags.get(key, []), mapping, collection_codes)
        for governance_tag in governance_by_key.get(key, []):
            normalized = direct_normalize("Status", governance_tag, 1) if governance_tag else None
            if normalized and normalized not in canonical_tags:
                canonical_tags.append(normalized)
        if not canonical_tags:
            canonical_tags.append(fallback_type_tag(row.get("item_type", "")))
        dropped_count = sum(1 for tag in item_tags.get(key, []) if not mapping.get(tag))
        output_rows.append(
            {
                "item_key": key,
                "zotero_link": row.get("zotero_link", ""),
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "item_type": row.get("item_type", ""),
                "collections": row.get("collections", ""),
                "recommended_tags": "; ".join(canonical_tags),
                "recommended_tag_count": len(canonical_tags),
                "dropped_long_tail_tag_count": dropped_count,
                "suppressed_collection_duplicate_fields": "; ".join(suppressed_fields),
                "source_tags": "; ".join(item_tags.get(key, [])),
            }
        )
    return output_rows


def build_taxonomy(alias_rows: list[dict[str, Any]], item_plan: list[dict[str, Any]]) -> dict[str, Any]:
    canonical_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    for row in item_plan:
        canonical_counter.update(split_tags(row["recommended_tags"]))
        source_counter.update(split_tags(row["source_tags"]))
    namespace_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_by_canonical: dict[str, Counter[str]] = defaultdict(Counter)
    for row in alias_rows:
        canonical = row.get("canonical_tag")
        if canonical:
            source_by_canonical[canonical].update({row["original_tag"]: int(row["item_count"])})
    for canonical, count in canonical_counter.most_common():
        namespace = canonical.split("/", 1)[0].lstrip("#")
        namespace_groups[namespace].append(
            {
                "tag": canonical,
                "item_count": count,
                "source_tag_count": len(source_by_canonical[canonical]),
                "top_source_tags": source_by_canonical[canonical].most_common(12),
            }
        )
    return {
        "generated_at": utc_now(),
        "policy": {
            "write_to_zotero": False,
            "collection_role": "research direction and item placement",
            "tag_role": "cross-cutting facets for filtering and compact display",
            "parameter_quantifiability_gate": "A #Parameter tag is kept only when it is a measurable, computable, or comparable variable/metric in QUANTIFIABLE_PARAMETER_TAGS.",
            "namespace_limits_per_item": NAMESPACE_LIMITS,
        },
        "summary": {
            "source_unique_tags": len(source_counter),
            "recommended_unique_tags": len(canonical_counter),
            "source_tag_assignments": sum(source_counter.values()),
            "recommended_tag_assignments": sum(canonical_counter.values()),
        },
        "namespaces": namespace_groups,
    }


def build_peripheral_rows(alias_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in alias_rows:
        original = str(row.get("original_tag", ""))
        if row.get("namespace") != "Status" or "peripheral" not in compact_token(original):
            continue
        rows.append(
            {
                "original_tag": original,
                "item_count": row.get("item_count", 0),
                "top_levels": row.get("top_levels", ""),
                "recommended_action": "move_signal_to_collection_or_drop_tag",
                "suggested_collection_review": "review source item collections; do not keep as #Status tag",
            }
        )
    return sorted(rows, key=lambda item: (-int(item["item_count"]), item["original_tag"]))


def build_parameter_rows(alias_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in alias_rows:
        if row.get("namespace") != "Parameter":
            continue
        canonical = str(row.get("canonical_tag", ""))
        if canonical.startswith("#Parameter/"):
            gate = "pass_quantifiable_parameter"
            review_hint = "keep as quantifiable parameter facet"
        elif canonical:
            gate = "redirect_non_parameter_concept"
            review_hint = "redirected outside #Parameter because it is a field, object, method, or topic"
        else:
            gate = "drop_not_quantifiable_or_too_broad"
            review_hint = "drop unless a future pass can define a measurable canonical parameter"
        rows.append(
            {
                "original_tag": row.get("original_tag", ""),
                "canonical_tag": canonical,
                "action": row.get("action", ""),
                "quantifiability_gate": gate,
                "item_count": row.get("item_count", 0),
                "top_level_entropy": row.get("top_level_entropy", ""),
                "top_level_count": row.get("top_level_count", ""),
                "top_levels": row.get("top_levels", ""),
                "review_hint": review_hint,
            }
        )
    return sorted(rows, key=lambda item: (item["action"] != "keep", -int(item["item_count"]), item["original_tag"]))


def render_report(
    alias_rows: list[dict[str, Any]],
    item_plan: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    alias_map_path: Path,
    item_plan_path: Path,
    taxonomy_path: Path,
    peripheral_tags_path: Path,
    parameter_tags_path: Path,
) -> str:
    summary = taxonomy["summary"]
    namespace_counts: dict[str, int] = {}
    namespace_assignments: dict[str, int] = {}
    for namespace, rows in taxonomy["namespaces"].items():
        namespace_counts[namespace] = len(rows)
        namespace_assignments[namespace] = sum(int(row["item_count"]) for row in rows)
    action_counts = Counter(row["action"] for row in alias_rows)
    tag_count_distribution = Counter(int(row["recommended_tag_count"]) for row in item_plan)
    long_tail_items = sum(1 for row in item_plan if int(row["dropped_long_tail_tag_count"]) > 0)
    suppressed_field_items = sum(1 for row in item_plan if row.get("suppressed_collection_duplicate_fields"))
    suppressed_field_counter: Counter[str] = Counter()
    for row in item_plan:
        suppressed_field_counter.update(split_tags(row.get("suppressed_collection_duplicate_fields", "")))

    lines: list[str] = []
    lines.append("# Zotero #tags 聚合与互补显示方案")
    lines.append("")
    lines.append("## 1. 目标与边界")
    lines.append("")
    lines.append("- 本方案只生成 dry-run 输出，不写入 Zotero。")
    lines.append("- Collection 承担“研究方向/归属位置”；#tags 承担“跨 collection 的筛选维度”。")
    lines.append("- 标签聚合目标是减少一条文献上过多、过细、一次性标签，保留方法、对象、具体参数、治理动作、类型等高信息密度维度。")
    lines.append("")
    lines.append("## 2. 方法")
    lines.append("")
    lines.append("1. 按命名空间解析 `#Field`、`#Method`、`#Object`、`#Parameter`、`#Status`、`#Type`。")
    lines.append("2. 统计每个 tag 的频次和跨一级 collection 的分布熵，区分横向筛选标签和一次性长尾标签。")
    lines.append("3. 使用可审计关键词规则把同义、近义、过细标签映射到 canonical tags。")
    lines.append("4. 对 `#Parameter/` 增加量化门槛：只有可观测、可计算或可比较的变量/指标进入参数白名单；主题、对象、方法、策略、布局和宽泛 performance 概念不放入 Parameter。")
    lines.append("5. 对每个 item 设置显示上限：最多 2 个 Field、2 个 Method、2 个 Object、3 个 Parameter、4 个 Governance、1 个 Type。")
    lines.append("6. 将 collection 计划中的治理复核 tag 合并到 item tag plan，但仍只作为建议。")
    lines.append("")
    lines.append("## 3. 聚合结果")
    lines.append("")
    lines.append(f"- 原始 unique tags：{summary['source_unique_tags']}。")
    lines.append(f"- 建议 canonical tags：{summary['recommended_unique_tags']}。")
    lines.append(f"- 原始 tag assignments：{summary['source_tag_assignments']}。")
    lines.append(f"- 建议 tag assignments：{summary['recommended_tag_assignments']}。")
    lines.append(f"- 有长尾 tag 被丢弃或合并的 item：{long_tail_items}。")
    lines.append(f"- 因 collection 已表达而移除重复 `#Field` 的 item：{suppressed_field_items}。")
    lines.append("")
    lines.append("### Alias 动作")
    lines.append("")
    lines.append("| action | count |")
    lines.append("|---|---:|")
    for action, count in action_counts.most_common():
        lines.append(f"| `{action}` | {count} |")
    lines.append("")
    lines.append("### Namespace 规模")
    lines.append("")
    lines.append("| namespace | canonical tags | assignments |")
    lines.append("|---|---:|---:|")
    for namespace in ("Field", "Method", "Object", "Parameter", "Governance", "Type"):
        lines.append(f"| `{namespace}` | {namespace_counts.get(namespace, 0)} | {namespace_assignments.get(namespace, 0)} |")
    lines.append("")
    lines.append("### 每条 item 推荐 tag 数")
    lines.append("")
    lines.append("| recommended_tag_count | items |")
    lines.append("|---:|---:|")
    for tag_count, items in sorted(tag_count_distribution.items()):
        lines.append(f"| {tag_count} | {items} |")
    lines.append("")
    lines.append("### 被 Collection 吸收的重复 Field")
    lines.append("")
    lines.append("| suppressed field | items |")
    lines.append("|---|---:|")
    for field, count in suppressed_field_counter.most_common(20):
        lines.append(f"| `{field}` | {count} |")
    lines.append("")
    lines.append("## 4. 建议保留的标签角色")
    lines.append("")
    lines.append("- `#Field/`：只保留跨 collection 的研究焦点，例如 `#Field/RadiantSystems`、`#Field/IndoorThermalComfort`、`#Field/HeatTransferModeling`。不要重复 collection 名称的完整层级。")
    lines.append("- `#Method/`：优先用于方法筛选，例如实验、现场测量、CFD、EnergyPlus/TRNSYS、MPC、机器学习、优化、综述。")
    lines.append("- `#Object/`：记录对象类型，例如建筑类型、系统、材料、家具、红外测量对象。")
    lines.append("- `#Parameter/`：只记录具体可观测、可计算、可比较的变量/指标，例如 `AirTemperature`、`EnergyConsumption`、`SolarIrradiance`、`Illuminance`、`Emissivity`、`CO2Concentration`。不能量化的主题词、对象词、策略词和宽泛 `Performance` 词不放在这里。")
    lines.append("- 状态类信息进入 `#Governance/` 或 `#Type/`，`Peripheral*` 进入 collection 归位复核表。")
    lines.append("- `#Governance/`：单独承载治理动作，例如 `NeedsManualReview`、`MissingMetadata`、`NonLiteratureItem`、`DoNotModify`、`PotentialDuplicate`。")
    lines.append("- `#Type/`：文献类型和研究类型，保留一个最能表达用途的标签。")
    lines.append("- `Peripheral*`：进入 collection 归位复核，不作为推荐 tag。")
    lines.append("")
    lines.append("## 5. 输出文件")
    lines.append("")
    lines.append(f"- 原始 tag 到 canonical tag 映射：`{alias_map_path}`")
    lines.append(f"- item 级推荐 tags：`{item_plan_path}`")
    lines.append(f"- JSON taxonomy：`{taxonomy_path}`")
    lines.append(f"- Peripheral tags 归位复核表：`{peripheral_tags_path}`")
    lines.append(f"- Parameter tags 参数审阅表：`{parameter_tags_path}`")
    lines.append("")
    lines.append("## 6. 使用建议")
    lines.append("")
    lines.append("- Zotero 左侧 collection 用于“在哪个方向”；tag 面板用于“用什么方法、研究什么对象、看什么指标、是否需复核”。")
    lines.append("- 后续如果执行写入，应先人工抽查 alias map 中 `drop_long_tail` 和 `map_to_canonical` 的高频项，再进入 Zotero write gate。")
    lines.append("- 不建议把所有原始细粒度 `#Field/...` 原样写回 Zotero；它们会淹没真正有筛选价值的 tags。")
    lines.append("")
    return "\n".join(lines)


def command_build(args: argparse.Namespace) -> int:
    item_rows = read_csv(Path(args.item_matrix))
    collection_rows = read_csv(Path(args.collection_assignments))
    top_levels_by_item = item_top_levels(collection_rows)
    counts, top_counts, item_tags = collect_tag_stats(item_rows, top_levels_by_item)
    alias_rows, mapping = build_alias_map(counts, top_counts)
    item_plan = build_item_tag_plan(item_rows, item_tags, mapping, collection_rows)
    taxonomy = build_taxonomy(alias_rows, item_plan)
    peripheral_rows = build_peripheral_rows(alias_rows)
    parameter_rows = build_parameter_rows(alias_rows)

    write_csv(
        Path(args.alias_map),
        alias_rows,
        [
            "namespace",
            "original_tag",
            "canonical_tag",
            "action",
            "item_count",
            "top_level_entropy",
            "top_level_count",
            "top_levels",
            "reason",
        ],
    )
    write_csv(
        Path(args.item_tag_plan),
        item_plan,
        [
            "item_key",
            "zotero_link",
            "title",
            "year",
            "item_type",
            "collections",
            "recommended_tags",
            "recommended_tag_count",
            "dropped_long_tail_tag_count",
            "suppressed_collection_duplicate_fields",
            "source_tags",
        ],
    )
    write_json(Path(args.taxonomy_json), taxonomy)
    write_csv(
        Path(args.peripheral_tags),
        peripheral_rows,
        [
            "original_tag",
            "item_count",
            "top_levels",
            "recommended_action",
            "suggested_collection_review",
        ],
    )
    write_csv(
        Path(args.parameter_tags),
        parameter_rows,
        [
            "original_tag",
            "canonical_tag",
            "action",
            "quantifiability_gate",
            "item_count",
            "top_level_entropy",
            "top_level_count",
            "top_levels",
            "review_hint",
        ],
    )
    report = render_report(
        alias_rows,
        item_plan,
        taxonomy,
        Path(args.alias_map),
        Path(args.item_tag_plan),
        Path(args.taxonomy_json),
        Path(args.peripheral_tags),
        Path(args.parameter_tags),
    )
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(report, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "items_total": len(item_rows),
                "source_unique_tags": taxonomy["summary"]["source_unique_tags"],
                "recommended_unique_tags": taxonomy["summary"]["recommended_unique_tags"],
                "alias_map": str(args.alias_map),
                "item_tag_plan": str(args.item_tag_plan),
                "taxonomy_json": str(args.taxonomy_json),
                "peripheral_tags": str(args.peripheral_tags),
                "parameter_tags": str(args.parameter_tags),
                "report_md": str(args.report_md),
            },
            ensure_ascii=False,
        )
    )
    return 0
