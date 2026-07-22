"""Shared path conventions for ResearchOS framework assets.

Project-specific workflows keep their existing numbered project directories
(`corpus/reading-cards/cards`, `03-文献矩阵`, `.research`, etc.). This module is
for ResearchOS root framework assets that should be synchronized across
terminals or kept as machine run outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DOCS_ROOT = Path("docs")
CORPUS_ROOT = Path("corpus")
OUTPUTS_ROOT = Path(".researchos") / "outputs"

REPORTS_ROOT = DOCS_ROOT / "reports"
GOVERNANCE_DOCS_ROOT = DOCS_ROOT / "governance"

CORPUS_ZOTERO_ROOT = CORPUS_ROOT / "zotero"
CORPUS_FULLTEXT_ROOT = CORPUS_ROOT / "fulltext"
CORPUS_READING_CARDS_ROOT = CORPUS_ROOT / "reading-cards"

MACHINE_ROOT = OUTPUTS_ROOT / "machine"
ARCHIVE_ROOT = OUTPUTS_ROOT / "archive"

M002_LIBRARY_GOVERNANCE = MACHINE_ROOT / "M-002-library-governance"
M004_ZOTERO_NEW_ITEM_MONITOR = MACHINE_ROOT / "M-004-zotero-new-item-monitor"
M005_READING_CARD_ANNOTATION_SYNC = MACHINE_ROOT / "M-005-reading-card-annotation-sync"
M006_ZOTERO_INGESTION_PIPELINE = MACHINE_ROOT / "M-006-zotero-ingestion-pipeline"

A001_LIBRARY_GOVERNANCE = ARCHIVE_ROOT / "A-001-library-governance"
A003_READING_CARD_NOTE_PUBLISH = ARCHIVE_ROOT / "A-003-reading-card-note-publish"
A004_CORPUS_PUBLICATION = ARCHIVE_ROOT / "A-004-corpus-publication"

DOCS_LIBRARY_GOVERNANCE = REPORTS_ROOT / "library-governance"
DOCS_RULE_AUDITS = REPORTS_ROOT / "rule-audits"
DOCS_ZOTERO_NEW_ITEM_MONITOR = REPORTS_ROOT / "zotero-new-item-monitor"
DOCS_RESEARCHOS_GOVERNANCE_RESTRUCTURE = GOVERNANCE_DOCS_ROOT / "researchos-governance-restructure"

CORPUS_M001_ZOTERO_LIBRARY = CORPUS_ZOTERO_ROOT / "M-001-zotero-library"
CORPUS_ZOTERO_LIBRARY_DB = CORPUS_M001_ZOTERO_LIBRARY / "zotero_library.sqlite"
CORPUS_ZOTERO_FULLTEXT = CORPUS_FULLTEXT_ROOT / "zotero-library"
CORPUS_ZOTERO_FULLTEXT_NORMALIZED = CORPUS_FULLTEXT_ROOT / "zotero-library-normalized"


def find_researchos_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "tools").is_dir():
            return candidate
    raise FileNotFoundError("无法定位 ResearchOS 根目录。请在 00_ResearchOS 内运行。")


def ensure_output_dirs(root: Path) -> None:
    for path in [
        root / REPORTS_ROOT,
        root / GOVERNANCE_DOCS_ROOT,
        root / CORPUS_ZOTERO_ROOT,
        root / CORPUS_FULLTEXT_ROOT,
        root / CORPUS_READING_CARDS_ROOT,
        root / MACHINE_ROOT,
        root / ARCHIVE_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
