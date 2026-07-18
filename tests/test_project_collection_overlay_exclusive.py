from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.zotero.write import execute_project_collection_overlay_write as overlay


class ProjectCollectionOverlayExclusiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.triage_path = "00.科研项目/01-项目/00-待分配-triage"
        self.review_path = "00.科研项目/01-项目/02-综述-review"
        self.method_path = "00.科研项目/01-项目/04-方法-method"
        self.path_by_key = {
            "OTHER001": "主题/建筑环境",
            "TRIAGE01": self.triage_path,
            "REVIEW01": self.review_path,
            "METHOD01": self.method_path,
        }
        self.key_by_path = {value: key for key, value in self.path_by_key.items()}

    def item(self, version: int, collections: list[str]) -> dict:
        return {"key": "ITEM0001", "version": version, "data": {"collections": collections}}

    def test_preview_adds_targets_then_removes_only_project_triage(self) -> None:
        preview = overlay.exclusive_preview(
            self.item(3, ["OTHER001", "TRIAGE01"]),
            ["REVIEW01", "METHOD01"],
            [self.review_path, self.method_path],
            self.path_by_key,
            self.key_by_path,
        )
        self.assertEqual(
            preview["add_phase_collection_keys"],
            ["OTHER001", "TRIAGE01", "REVIEW01", "METHOD01"],
        )
        self.assertEqual(preview["after_collection_keys"], ["OTHER001", "REVIEW01", "METHOD01"])

    def test_mixed_triage_and_stable_targets_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot both"):
            overlay.collection_assignment_policy(
                [self.triage_path, self.review_path],
                self.key_by_path,
            )

    def test_patch_verifies_add_before_removing_triage(self) -> None:
        before = self.item(3, ["OTHER001", "TRIAGE01"])
        after_add = self.item(4, ["OTHER001", "TRIAGE01", "REVIEW01"])
        final = self.item(5, ["OTHER001", "REVIEW01"])
        responses = [
            (200, {}, before),
            (204, {}, None),
            (200, {}, after_add),
            (204, {}, None),
            (200, {}, final),
        ]
        with (
            patch.object(overlay, "zotero_request", side_effect=responses) as request,
            patch.object(overlay.time, "sleep", return_value=None),
        ):
            item_before, item_after, preview, status = overlay.patch_item_collections(
                {},
                "ITEM0001",
                ["REVIEW01"],
                [self.review_path],
                self.path_by_key,
                self.key_by_path,
            )
        self.assertEqual(item_before, before)
        self.assertEqual(item_after, final)
        self.assertEqual(status, 204)
        self.assertEqual(overlay.collection_postcondition_errors(final, preview), [])
        self.assertEqual(request.call_args_list[1].args[3]["collections"], ["OTHER001", "TRIAGE01", "REVIEW01"])
        self.assertEqual(request.call_args_list[3].args[3]["collections"], ["OTHER001", "REVIEW01"])

    def test_add_phase_postcondition_failure_stops_before_removal(self) -> None:
        before = self.item(3, ["TRIAGE01"])
        missing_target = self.item(4, ["TRIAGE01"])
        responses = [(200, {}, before), (204, {}, None), (200, {}, missing_target)]
        with (
            patch.object(overlay, "zotero_request", side_effect=responses) as request,
            patch.object(overlay.time, "sleep", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "Add-phase postcondition failed"):
                overlay.patch_item_collections(
                    {},
                    "ITEM0001",
                    ["REVIEW01"],
                    [self.review_path],
                    self.path_by_key,
                    self.key_by_path,
                )
        self.assertEqual(request.call_count, 3)


if __name__ == "__main__":
    unittest.main()
