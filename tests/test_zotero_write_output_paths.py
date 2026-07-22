from __future__ import annotations

import unittest

from tools.zotero.write import execute_zotero_deleted_collection_cleanup as cleanup
from tools.zotero.write import execute_project_collection_overlay_write as overlay
from tools.zotero.write import execute_zotero_item_mutation_plan as mutation
from tools.zotero.write import publish_reading_card_note as reading_card_note
from tools.zotero.write.zotero_web_api import fetch_web_api_paged
from tools.researchos_outputs import A001_LIBRARY_GOVERNANCE, A003_READING_CARD_NOTE_PUBLISH


class ZoteroWriteOutputPathTests(unittest.TestCase):
    def test_modules_resolve_same_researchos_root(self) -> None:
        self.assertEqual(mutation.RESEARCHOS_ROOT, cleanup.RESEARCHOS_ROOT)
        self.assertEqual(mutation.RESEARCHOS_ROOT, overlay.RESEARCHOS_ROOT)
        self.assertEqual(mutation.RESEARCHOS_ROOT, reading_card_note.RESEARCHOS_ROOT)
        self.assertTrue((mutation.RESEARCHOS_ROOT / "AGENTS.md").is_file())

    def test_shared_pagination_helper_imports_from_new_package(self) -> None:
        self.assertTrue(callable(fetch_web_api_paged))

    def test_mutation_run_evidence_goes_to_archive(self) -> None:
        self.assertEqual(mutation.RUNS_DIR, A001_LIBRARY_GOVERNANCE / "zotero-item-mutation-runs")

    def test_cleanup_run_evidence_goes_to_archive(self) -> None:
        self.assertEqual(cleanup.RUNS_DIR, A001_LIBRARY_GOVERNANCE / "zotero-deleted-collection-cleanup-runs")

    def test_reading_card_note_run_output_is_separate(self) -> None:
        self.assertEqual(reading_card_note.A003_READING_CARD_NOTE_PUBLISH, A003_READING_CARD_NOTE_PUBLISH)


if __name__ == "__main__":
    unittest.main()
