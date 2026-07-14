from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tools.zotero.zotero_annotation_sync import (
    annotation_hash,
    normalize_annotation,
    scan_item,
    soft_delete_missing,
    upsert_annotation,
)
from tools.zotero.zotero_library_index import init_db


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def fetch_paged(self, endpoint, params=None, max_records=None):
        self.calls.append(endpoint)
        return self.responses.get(endpoint, [])


class ZoteroAnnotationSyncTests(unittest.TestCase):
    def annotation_row(self, key: str = "ANN12345", text: str = "quoted text"):
        return {
            "key": key,
            "version": 7,
            "data": {
                "itemType": "annotation",
                "annotationType": "highlight",
                "annotationText": text,
                "annotationComment": "my interpretation",
                "annotationColor": "#ffd400",
                "annotationPageLabel": "12",
                "annotationSortIndex": "00011|000001|00000",
                "annotationPosition": {"pageIndex": 11, "rects": [[1, 2, 3, 4]]},
                "tags": [{"tag": "method"}],
            },
        }

    def test_annotation_hash_changes_with_comment(self) -> None:
        data = self.annotation_row()["data"]
        before = annotation_hash(data)
        data["annotationComment"] = "changed"
        self.assertNotEqual(before, annotation_hash(data))

    def test_normalize_annotation_decodes_stringified_position(self) -> None:
        row = self.annotation_row()
        row["data"]["annotationPosition"] = '{"pageIndex":0,"rects":[]}'
        record = normalize_annotation(row, "ITEM1234", "PDF12345", "2026-07-14T00:00:00+00:00")
        self.assertEqual(record["annotation_position_json"], '{"pageIndex":0,"rects":[]}')

    def test_scan_item_filters_global_annotations_by_attachment_parent(self) -> None:
        attachment = {
            "key": "PDF12345",
            "data": {"itemType": "attachment", "contentType": "application/pdf", "title": "paper.pdf"},
        }
        unrelated = self.annotation_row(key="ANN99999", text="unrelated")
        unrelated["data"]["parentItem"] = "OTHERPDF"
        target = self.annotation_row()
        target["data"]["parentItem"] = "PDF12345"
        client = FakeClient(
            {
                "items/ITEM1234/children": [attachment],
                "items": [unrelated, target],
            }
        )
        records, scans = scan_item(client, "ITEM1234")
        self.assertEqual(client.calls, ["items/ITEM1234/children", "items"])
        self.assertEqual(records[0]["parent_item_key"], "ITEM1234")
        self.assertEqual([row["annotation_key"] for row in records], ["ANN12345"])
        self.assertEqual(scans[0]["annotation_keys"], ["ANN12345"])

    def test_upsert_and_soft_delete_preserve_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "test.sqlite"
            with closing(sqlite3.connect(db)) as conn:
                init_db(conn)
                record = normalize_annotation(self.annotation_row(), "ITEM1234", "PDF12345", "2026-07-14T00:00:00+00:00")
                upsert_annotation(conn, record)
                conn.commit()
                deleted = soft_delete_missing(conn, "PDF12345", set(), "2026-07-14T01:00:00+00:00")
                conn.commit()
                row = conn.execute(
                    "SELECT annotation_text, zotero_deleted FROM annotations WHERE annotation_key = 'ANN12345'"
                ).fetchone()
            self.assertEqual(deleted, 1)
            self.assertEqual(row, ("quoted text", 1))


if __name__ == "__main__":
    unittest.main()
