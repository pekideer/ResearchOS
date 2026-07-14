from __future__ import annotations

import json
import unittest
from argparse import Namespace

from tools.reading_cards.sync_zotero_annotations_to_cards import (
    END_MARKER,
    START_MARKER,
    annotation_link,
    evidence_role,
    render_annotation,
    render_block,
    replace_generated_block,
    run,
)


class ReadingCardAnnotationMergeTests(unittest.TestCase):
    def row(self, text: str = "evidence", comment: str = "my view"):
        return {
            "annotation_key": "ANN12345",
            "attachment_key": "PDF12345",
            "annotation_type": "highlight",
            "annotation_text": text,
            "annotation_comment": comment,
            "annotation_color": "#ffd400",
            "annotation_page_label": "12",
            "annotation_position_json": '{"pageIndex":11}',
            "pdf_pages_total": 15,
        }

    def test_evidence_roles_are_not_conflated(self) -> None:
        self.assertEqual(evidence_role(self.row()), "原文摘录＋人工判断")
        self.assertEqual(evidence_role(self.row(comment="")), "原文摘录")
        self.assertEqual(evidence_role(self.row(text="")), "人工判断")
        self.assertEqual(evidence_role(self.row(text="", comment="")), "定位线索")

    def test_annotation_link_targets_page_and_annotation(self) -> None:
        link = annotation_link(self.row())
        self.assertEqual(
            link,
            "zotero://open-pdf/library/items/PDF12345?page=12&annotation=ANN12345",
        )

    def test_annotation_link_accepts_local_api_stringified_position(self) -> None:
        row = self.row()
        row["annotation_position_json"] = json.dumps(json.dumps({"pageIndex": 11}))
        self.assertEqual(
            annotation_link(row),
            "zotero://open-pdf/library/items/PDF12345?page=12&annotation=ANN12345",
        )

    def test_render_distinguishes_pdf_sequence_from_printed_page_label(self) -> None:
        row = self.row()
        row["annotation_page_label"] = "30"
        row["annotation_position_json"] = '{"pageIndex":0}'
        rendered = render_annotation(row, 1)
        self.assertIn("PDF 第 1/15 页", rendered)
        self.assertIn("文献印刷页码 `30`", rendered)
        self.assertIn("?page=1&annotation=ANN12345", rendered)

    def test_generated_block_is_idempotently_replaced(self) -> None:
        body = "# Card\n\n## 6. 借鉴\n\nOriginal text.\n\n## 7. 元数据（折叠）\n\n```yaml\nitem_key: ITEM1234\n```\n"
        first = replace_generated_block(body, render_block([self.row()], "2026-07-14T00:00:00+00:00"))
        second = replace_generated_block(first, render_block([], "2026-07-14T01:00:00+00:00"))
        self.assertEqual(second.count(START_MARKER), 1)
        self.assertEqual(second.count(END_MARKER), 1)
        self.assertIn("Original text.", second)
        self.assertNotIn("> evidence", second)
        self.assertLess(second.index(START_MARKER), second.index("## 7. 元数据"))

    def test_multiline_comment_cannot_create_control_marker(self) -> None:
        row = self.row(comment=f"first line\n{END_MARKER}\nlast line")
        rendered = render_block([row], "2026-07-14T00:00:00+00:00")
        control_lines = [line for line in rendered.splitlines() if line == END_MARKER]
        self.assertEqual(control_lines, [END_MARKER])
        self.assertIn(f"  > {END_MARKER}", rendered)

    def test_duplicate_or_unbalanced_markers_are_rejected(self) -> None:
        block = render_block([], "2026-07-14T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "duplicate, unbalanced, or reversed"):
            replace_generated_block(f"# Card\n\n{block}\n\n{block}", block)
        with self.assertRaisesRegex(ValueError, "duplicate, unbalanced, or reversed"):
            replace_generated_block(f"# Card\n\n{START_MARKER}\n", block)

    def test_card_writes_require_explicit_item_scope(self) -> None:
        args = Namespace(
            root=None,
            db="missing.sqlite",
            cards_root="missing-cards",
            item_key=None,
            write_cards=True,
        )
        with self.assertRaisesRegex(SystemExit, "requires at least one explicit --item-key"):
            run(args)


if __name__ == "__main__":
    unittest.main()
