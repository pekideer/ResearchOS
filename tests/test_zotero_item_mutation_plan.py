from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.zotero.write.mutation_contract import ItemSnapshot, load_plan, snapshot_drift
from tools.zotero.write.mutation_executor import execute_plan, select_actions
from tests.test_support import workspace_temp_dir


def plan_payload(version: int = 10) -> dict:
    return {
        "schema_version": 1,
        "plan_id": "plan-001",
        "plan_kind": "content_tags",
        "source_packet_hash": "a" * 64,
        "approval_status": "approved",
        "actions": [{
            "item_key": "ITEM0001",
            "expected_before": {"version": version, "tags": ["old"], "collection_keys": ["COLL0001"]},
            "mutation": {
                "add_tags": ["#Method/Test"], "remove_tags": ["old"],
                "add_collection_paths": [], "remove_collection_paths": [],
            },
            "expected_after": {"tags": ["#Method/Test"], "collection_keys": ["COLL0001"]},
            "evidence_refs": ["packet.jsonl#ITEM0001"],
        }],
    }


class MutationContractTests(unittest.TestCase):
    def test_snapshot_comparison_ignores_tag_and_collection_order(self) -> None:
        expected = ItemSnapshot(10, ("a", "b"), ("c1", "c2"))
        live = ItemSnapshot(10, ("b", "a"), ("c2", "c1"))
        self.assertEqual(snapshot_drift(expected, live), [])

    def test_snapshot_comparison_reports_each_drift_dimension(self) -> None:
        expected = ItemSnapshot(10, ("a",), ("c1",))
        live = ItemSnapshot(11, ("b",), ("c2",))
        self.assertEqual(snapshot_drift(expected, live), ["version", "tags", "collections"])

    def test_plan_requires_structured_arrays(self) -> None:
        with workspace_temp_dir() as root:
            path = root / "plan.json"
            payload = plan_payload()
            payload["actions"][0]["mutation"]["add_tags"] = "#Method/Test"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "array"):
                load_plan(path)

    def test_any_drift_blocks_entire_batch_before_patch(self) -> None:
        with workspace_temp_dir() as root:
            path = root / "plan.json"
            path.write_text(json.dumps(plan_payload(version=9)), encoding="utf-8")
            plan = load_plan(path)
            calls: list[tuple[str, str]] = []

            def request(method, endpoint, body, headers):
                calls.append((method, endpoint))
                return 200, {}, {
                    "key": "ITEM0001", "version": 10,
                    "data": {"tags": [{"tag": "old"}], "collections": ["COLL0001"]},
                }

            collections = [{"key": "COLL0001", "data": {"name": "Collection", "parentCollection": False}}]
            summary = execute_plan(plan, select_actions(plan, None, None), collections, request, root / "run", True, {})
            self.assertEqual(summary["blocked_rows"], 1)
            self.assertEqual(summary["writes_performed"], 0)
            self.assertFalse(any(method == "PATCH" for method, _endpoint in calls))
            before = json.loads((root / "run" / "before_items.json").read_text(encoding="utf-8"))
            self.assertEqual(before[0]["key"], "ITEM0001")

    def test_drift_in_second_item_blocks_first_item_too(self) -> None:
        with workspace_temp_dir() as root:
            payload = plan_payload()
            second = json.loads(json.dumps(payload["actions"][0]))
            second["item_key"] = "ITEM0002"
            second["expected_before"]["version"] = 9
            payload["actions"].append(second)
            path = root / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            plan = load_plan(path)
            calls = []

            def request(method, endpoint, body, headers):
                calls.append((method, endpoint))
                return 200, {}, {
                    "key": endpoint.rsplit("/", 1)[-1], "version": 10,
                    "data": {"tags": [{"tag": "old"}], "collections": ["COLL0001"]},
                }

            collections = [{"key": "COLL0001", "data": {"name": "Collection", "parentCollection": False}}]
            summary = execute_plan(plan, list(plan.actions), collections, request, root / "run", True, {})
            self.assertEqual(summary["writes_performed"], 0)
            self.assertEqual(summary["blocked_rows"], 1)
            self.assertFalse(any(method == "PATCH" for method, _endpoint in calls))

    def test_unapproved_plan_is_audited_as_global_block(self) -> None:
        with workspace_temp_dir() as root:
            payload = plan_payload()
            payload["approval_status"] = "pending"
            path = root / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            plan = load_plan(path)

            def request(method, endpoint, body, headers):
                return 200, {}, {
                    "key": "ITEM0001", "version": 10,
                    "data": {"tags": [{"tag": "old"}], "collections": ["COLL0001"]},
                }

            collections = [{"key": "COLL0001", "data": {"name": "Collection", "parentCollection": False}}]
            summary = execute_plan(plan, list(plan.actions), collections, request, root / "run", True, {})
            blocks = json.loads((root / "run" / "preflight_blocks.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["writes_performed"], 0)
            self.assertEqual(blocks[-1]["blocking_conditions"], ["plan_not_approved"])

    def test_readback_failure_preserves_rollback_for_completed_patch(self) -> None:
        with workspace_temp_dir() as root:
            path = root / "plan.json"
            path.write_text(json.dumps(plan_payload()), encoding="utf-8")
            plan = load_plan(path)
            get_count = 0

            def request(method, endpoint, body, headers):
                nonlocal get_count
                if method == "PATCH":
                    return 204, {}, None
                get_count += 1
                if get_count == 1:
                    return 200, {}, {
                        "key": "ITEM0001", "version": 10,
                        "data": {"tags": [{"tag": "old"}], "collections": ["COLL0001"]},
                    }
                return 200, {}, {
                    "key": "ITEM0001", "version": 11,
                    "data": {"tags": [{"tag": "wrong"}], "collections": ["COLL0001"]},
                }

            collections = [{"key": "COLL0001", "data": {"name": "Collection", "parentCollection": False}}]
            summary = execute_plan(plan, list(plan.actions), collections, request, root / "run", True, {})
            rollback = json.loads((root / "run" / "rollback_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["writes_performed"], 1)
            self.assertEqual(summary["blocked_rows"], 1)
            self.assertEqual(rollback["rollback_items"][0]["item_key"], "ITEM0001")


if __name__ == "__main__":
    unittest.main()
