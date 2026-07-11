from __future__ import annotations

import unittest

from tools.zotero.write import execute_zotero_additive_write_plan as additive
from tools.zotero.write import execute_zotero_deleted_collection_cleanup as cleanup
from tools.zotero.write import execute_project_collection_overlay_write as overlay
from tools.zotero.write.zotero_web_api import fetch_web_api_paged
from tools.researchos_outputs import A001_LIBRARY_GOVERNANCE, M002_LIBRARY_GOVERNANCE


class ZoteroWriteOutputPathTests(unittest.TestCase):
    def test_moved_modules_resolve_same_researchos_root(self) -> None:
        self.assertEqual(additive.RESEARCHOS_ROOT, cleanup.RESEARCHOS_ROOT)
        self.assertEqual(additive.RESEARCHOS_ROOT, overlay.RESEARCHOS_ROOT)
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


if __name__ == "__main__":
    unittest.main()
