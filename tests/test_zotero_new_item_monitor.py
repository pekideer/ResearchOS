from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from tools import zotero_new_item_monitor as monitor


def zotero_item(
    key: str,
    added: str,
    title: str = "Model predictive control for HVAC",
    item_type: str = "journalArticle",
    doi: str = "10.1234/example",
    abstract: str = "A review of model predictive control for HVAC systems.",
) -> dict[str, Any]:
    return {
        "key": key,
        "version": 1,
        "data": {
            "key": key,
            "version": 1,
            "itemType": item_type,
            "title": title,
            "creators": [{"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}],
            "date": added[:4],
            "publicationTitle": "Energy and Buildings",
            "DOI": doi,
            "url": "https://example.test/article",
            "abstractNote": abstract,
            "dateAdded": added,
            "dateModified": added,
            "collections": ["COLL1"],
            "tags": [{"tag": "MPC"}],
        },
    }


class ZoteroNewItemMonitorTests(unittest.TestCase):
    def watermark(self, key: str, added: str) -> monitor.Watermark:
        parsed = monitor.parse_zotero_time(added)
        assert parsed is not None
        return monitor.Watermark(added, parsed, {key})

    def test_fetch_new_items_stops_at_parent_watermark(self) -> None:
        calls: list[tuple[str, dict[str, Any] | None]] = []

        def fake_fetcher(url: str, params: dict[str, Any] | None, timeout: int) -> Any:
            calls.append((url, params))
            return [
                zotero_item("NEWKEY01", "2026-06-02T00:00:00Z"),
                zotero_item("OLDKEY01", "2026-06-01T00:00:00Z"),
                zotero_item("OLDER001", "2026-05-01T00:00:00Z"),
            ]

        rows, diagnostics = monitor.fetch_new_items(
            Path("unused.sqlite"),
            fetcher=fake_fetcher,
            batch_size=50,
            max_records=50,
            watermark_override=self.watermark("OLDKEY01", "2026-06-01T00:00:00Z"),
        )
        self.assertEqual([row["item_key"] for row in rows], ["NEWKEY01"])
        self.assertTrue(diagnostics["stopped_at_watermark"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].endswith("/items/top"))
        self.assertNotIn("children", calls[0][0])
        self.assertNotIn("file", calls[0][0])

    def test_same_timestamp_uses_item_key_to_avoid_missing_new_item(self) -> None:
        def fake_fetcher(url: str, params: dict[str, Any] | None, timeout: int) -> Any:
            return [
                zotero_item("NEWSTAMP", "2026-06-01T00:00:00Z"),
                zotero_item("KNOWN001", "2026-06-01T00:00:00Z"),
            ]

        rows, _diagnostics = monitor.fetch_new_items(
            Path("unused.sqlite"),
            fetcher=fake_fetcher,
            watermark_override=self.watermark("KNOWN001", "2026-06-01T00:00:00Z"),
        )
        self.assertEqual([row["item_key"] for row in rows], ["NEWSTAMP"])

    def test_excludes_non_literature_top_level_types(self) -> None:
        def fake_fetcher(url: str, params: dict[str, Any] | None, timeout: int) -> Any:
            return [
                zotero_item("ATTACH01", "2026-06-02T00:00:00Z", item_type="attachment"),
                zotero_item("NOTE0001", "2026-06-02T00:00:00Z", item_type="note"),
                zotero_item("REAL0001", "2026-06-02T00:00:00Z"),
                zotero_item("OLDKEY01", "2026-06-01T00:00:00Z"),
            ]

        rows, _diagnostics = monitor.fetch_new_items(
            Path("unused.sqlite"),
            fetcher=fake_fetcher,
            watermark_override=self.watermark("OLDKEY01", "2026-06-01T00:00:00Z"),
        )
        self.assertEqual([row["item_key"] for row in rows], ["REAL0001"])

    def test_classification_handles_missing_doi_author_and_abstract(self) -> None:
        row = monitor.compact_item_record(
            zotero_item(
                "NOMETA01",
                "2026-06-02T00:00:00Z",
                title="Radiative cooling coating experiment",
                doi="",
                abstract="",
            ),
            "2026-07-05T00:00:00+00:00",
        )
        row["creators"] = ""
        rules = {
            "research_directions": [{"name": "Spectrally Selective Materials", "keywords": ["radiative cooling"]}],
            "research_methods": [{"name": "Experiment", "keywords": ["experiment"]}],
            "research_objects": [],
        }
        classified = monitor.classify_row(row, rules, "00.09-watchlist-待补读与跟踪")
        self.assertEqual(classified["review_required"], "no")
        self.assertIn("rs:topic/spectrally-selective-materials", classified["recommended_tags"])
        self.assertEqual(classified["classification_basis"], "metadata_only")

    def test_write_plan_is_dry_run_only(self) -> None:
        plan = monitor.build_write_plan(
            [
                {
                    "item_key": "ITEM0001",
                    "title": "Example",
                    "suggested_collections": "00.09-watchlist-待补读与跟踪",
                    "recommended_tags": "rs:read/todo",
                    "reason": "test",
                    "review_required": "no",
                }
            ],
            Path("classification.csv"),
        )
        self.assertEqual(plan["mode"], "dry_run_only")
        self.assertIn("requires explicit user approval", plan["write_policy"])
        self.assertEqual(plan["pdf_access_policy"], "forbidden; this plan was built from item metadata only")


if __name__ == "__main__":
    unittest.main()
