from __future__ import annotations

import unittest

from tools.zotero.write import execute_zotero_additive_write_plan as additive
from tools.zotero.write import execute_zotero_deleted_collection_cleanup as cleanup
from tools.zotero.write import execute_project_collection_overlay_write as overlay
from tools.zotero.write import publish_reading_card_note as reading_card_note
from tools.zotero.write.zotero_web_api import fetch_web_api_paged
from tools.researchos_outputs import (
    A001_LIBRARY_GOVERNANCE,
    A003_READING_CARD_NOTE_PUBLISH,
    M002_LIBRARY_GOVERNANCE,
    M005_READING_CARD_ANNOTATION_SYNC,
)


class ZoteroWriteOutputPathTests(unittest.TestCase):
    def test_moved_modules_resolve_same_researchos_root(self) -> None:
        self.assertEqual(additive.RESEARCHOS_ROOT, cleanup.RESEARCHOS_ROOT)
        self.assertEqual(additive.RESEARCHOS_ROOT, overlay.RESEARCHOS_ROOT)
        self.assertEqual(additive.RESEARCHOS_ROOT, reading_card_note.RESEARCHOS_ROOT)
        self.assertTrue((additive.RESEARCHOS_ROOT / "AGENTS.md").is_file())

    def test_shared_pagination_helper_imports_from_new_package(self) -> None:
        self.assertTrue(callable(fetch_web_api_paged))

    def test_additive_plan_input_stays_machine_output(self) -> None:
        self.assertEqual(
            additive.DEFAULT_PLAN.parent,
            M002_LIBRARY_GOVERNANCE,
        )

    def test_additive_run_evidence_goes_to_archive(self) -> None:
        self.assertEqual(
            additive.RUNS_DIR,
            A001_LIBRARY_GOVERNANCE / "zotero-unfiled-write-runs",
        )

    def test_cleanup_plan_input_stays_machine_output(self) -> None:
        self.assertEqual(
            cleanup.DEFAULT_PLAN.parent,
            M002_LIBRARY_GOVERNANCE,
        )

    def test_cleanup_run_evidence_goes_to_archive(self) -> None:
        self.assertEqual(
            cleanup.RUNS_DIR,
            A001_LIBRARY_GOVERNANCE / "zotero-deleted-collection-cleanup-runs",
        )

    def test_reading_card_note_plan_and_run_outputs_are_separated(self) -> None:
        self.assertEqual(reading_card_note.M005_READING_CARD_ANNOTATION_SYNC, M005_READING_CARD_ANNOTATION_SYNC)
        self.assertEqual(reading_card_note.A003_READING_CARD_NOTE_PUBLISH, A003_READING_CARD_NOTE_PUBLISH)


if __name__ == "__main__":
    unittest.main()
