from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.zotero.write import publish_reading_card_note as publisher
from tools.zotero.write.publish_reading_card_note import (
    existing_generated_notes,
    markdown_to_zotero_html,
    note_content_hash,
    note_marker,
    note_postcondition_errors,
    repair_noop_mapping,
    safe_children_snapshot,
    validate_approved_plan,
)


class PublishReadingCardNoteTests(unittest.TestCase):
    def test_renderer_adds_stable_marker_and_readable_links(self) -> None:
        body = """---
card_id: RC-001
zotero_key: ITEM1234
---
# [Paper](zotero://select/library/items/ITEM1234)

## <span style=\"color:red\">1. 创新摘要</span>

- **Finding:** useful
"""
        rendered = markdown_to_zotero_html(body, "RC-001")
        self.assertIn("ResearchOS 读书卡｜RC-001", rendered)
        self.assertIn('href="zotero://select/library/items/ITEM1234"', rendered)
        self.assertIn("1. 创新摘要", rendered)
        self.assertNotIn("style=", rendered)

    def test_renderer_preserves_multi_parameter_zotero_links(self) -> None:
        body = "[定位](zotero://open-pdf/library/items/PDF12345?page=2&annotation=ANN12345)"
        rendered = markdown_to_zotero_html(body, "RC-001")
        self.assertIn(
            'href="zotero://open-pdf/library/items/PDF12345?page=2&amp;annotation=ANN12345"',
            rendered,
        )
        self.assertNotIn("&amp;amp;", rendered)

    def test_only_matching_generated_note_is_selected(self) -> None:
        children = [
            {"key": "NOTE1234", "data": {"itemType": "note", "note": f"<h1>{note_marker('RC-001')}</h1>"}},
            {"key": "NOTE5678", "data": {"itemType": "note", "note": "<p>Human note</p>"}},
            {"key": "PDF12345", "data": {"itemType": "attachment"}},
        ]
        matches = existing_generated_notes(children, "RC-001")
        self.assertEqual([row["key"] for row in matches], ["NOTE1234"])

    def test_children_snapshot_hashes_note_bodies(self) -> None:
        children = [
            {"key": "NOTE1234", "version": 3, "data": {"itemType": "note", "note": "private human note"}},
        ]
        snapshot = safe_children_snapshot(children, "RC-001")
        self.assertNotIn("private human note", str(snapshot))
        self.assertEqual(snapshot[0]["itemType"], "note")
        self.assertEqual(len(snapshot[0]["note_hash"]), 64)

    def test_content_hash_ignores_zotero_html_normalization(self) -> None:
        published = (
            '<h1>ResearchOS 读书卡｜RC-001</h1>\n'
            '<blockquote>引用内容</blockquote><ul><li>列表</li><p></p></ul>\n'
            '<pre><code>metadata</code></pre>\n'
            '<p><a href="zotero://open-pdf/library/items/PDF1?page=1&amp;annotation=ANN1">定位</a></p>\n'
            '<p><small>ResearchOS card id: RC-001</small></p>'
        )
        normalized = (
            '<div data-schema-version="9"><h1>ResearchOS 读书卡｜RC-001</h1>\n'
            '<blockquote><p>引用内容</p></blockquote><ul><li>列表</li><li></li></ul>\n'
            '<pre>metadata</pre>\n'
            '<p><a href="zotero://open-pdf/library/items/PDF1?page=1&amp;annotation=ANN1" '
            'rel="noopener noreferrer nofollow">定位</a></p>\n'
            '<p>ResearchOS card id: RC-001</p></div>'
        )
        self.assertEqual(note_content_hash(published), note_content_hash(normalized))

    def test_content_hash_detects_text_or_link_target_changes(self) -> None:
        baseline = '<p><a href="zotero://open-pdf/library/items/PDF1?page=1">原文</a></p>'
        changed_text = '<p><a href="zotero://open-pdf/library/items/PDF1?page=1">人工改写</a></p>'
        changed_target = '<p><a href="zotero://open-pdf/library/items/PDF1?page=2">原文</a></p>'
        self.assertNotEqual(note_content_hash(baseline), note_content_hash(changed_text))
        self.assertNotEqual(note_content_hash(baseline), note_content_hash(changed_target))

    def test_content_hash_detects_manual_structure_or_format_changes(self) -> None:
        paragraph = "<p>同一文字</p>"
        heading = "<h2>同一文字</h2>"
        bold = "<p><strong>同一文字</strong></p>"
        self.assertNotEqual(note_content_hash(paragraph), note_content_hash(heading))
        self.assertNotEqual(note_content_hash(paragraph), note_content_hash(bold))

    def valid_update_plan(self):
        digest = "a" * 64
        return {
            "schema_version": 1,
            "mode": "zotero_reading_card_note_canary",
            "generated_at": "2026-07-14T00:00:00+00:00",
            "plan_dir": ".researchos/outputs/machine/M-005-reading-card-annotation-sync/plan",
            "card_id": "RC-001",
            "card_path": "corpus/reading-cards/cards/RC-001.md",
            "item_key": "ITEM1234",
            "action": "update",
            "source_hash": digest,
            "note_html_hash": digest,
            "note_content_hash": digest,
            "existing_note_key": "NOTE1234",
            "existing_note_version": 3,
            "existing_note_hash": digest,
            "blocking_conditions": [],
            "policy": {
                "one_parent_item": True,
                "one_generated_note": True,
                "never_write_annotations": True,
                "never_delete_automatically": True,
                "require_version_match": True,
                "require_explicit_approved_plan": True,
            },
        }

    def test_approved_plan_rejects_unsafe_or_incomplete_provenance(self) -> None:
        plan = self.valid_update_plan()
        self.assertIs(validate_approved_plan(plan), plan)
        unsafe_path = {**plan, "card_path": "../outside.md"}
        with self.assertRaisesRegex(SystemExit, "safe relative path"):
            validate_approved_plan(unsafe_path)
        missing_hash = {**plan, "note_content_hash": ""}
        with self.assertRaisesRegex(SystemExit, "invalid note_content_hash"):
            validate_approved_plan(missing_hash)

    def test_postcondition_verifies_identity_parent_tag_content_and_version(self) -> None:
        plan = self.valid_update_plan()
        html = '<h1>ResearchOS 读书卡｜RC-001</h1><p>正文</p>'
        note = {
            "key": "NOTE1234",
            "version": 4,
            "data": {
                "itemType": "note",
                "parentItem": "ITEM1234",
                "note": html,
                "tags": [{"tag": "rs:reading-card"}],
            },
        }
        self.assertEqual(note_postcondition_errors(plan, "NOTE1234", note, html), [])
        broken = {**note, "data": {**note["data"], "parentItem": "OTHER123", "tags": [], "note": "changed"}}
        errors = note_postcondition_errors(plan, "NOTE1234", broken, html)
        self.assertIn("parent_item_mismatch", errors)
        self.assertIn("reading_card_tag_missing", errors)
        self.assertIn("note_content_mismatch", errors)
        missing = note_postcondition_errors(plan, "NOTE1234", {}, html)
        self.assertIn("note_key_mismatch", missing)
        self.assertIn("note_version_missing", missing)

    def test_noop_mapping_repair_updates_only_local_verified_state(self) -> None:
        note_html = '<div data-schema-version="9"><p>ResearchOS 读书卡｜RC-001</p></div>'
        plan = {
            "card_id": "RC-001",
            "action": "noop",
            "source_hash": "new-source",
            "note_content_hash": note_content_hash(note_html),
            "existing_note_content_hash": note_content_hash(note_html),
            "generated_at": "planned",
        }

        class FakeConnection:
            def __init__(self) -> None:
                self.params = None
                self.committed = False

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, _query, params):
                self.params = params

            def commit(self):
                self.committed = True

        connection = FakeConnection()
        with (
            patch.object(publisher, "mapped_note_state", return_value={"note_key": "NOTE1"}),
            patch.object(publisher.sqlite3, "connect", return_value=connection),
        ):
            repair_noop_mapping(
                publisher.RESEARCHOS_ROOT / "unused.sqlite",
                plan,
                {"key": "NOTE1", "version": 4, "data": {"note": note_html}},
                "card.md",
            )
        self.assertTrue(connection.committed)
        self.assertEqual(
            connection.params,
            ("card.md", 4, "new-source", note_content_hash(note_html), "planned", "RC-001", "NOTE1"),
        )


if __name__ == "__main__":
    unittest.main()
