from __future__ import annotations

import json
import io
import sqlite3
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from tools.zotero import zotero_ai_governance as governance
from tools.zotero.governance.contracts import TaskKind, result_schema, validate_result
from tools.zotero.governance.evidence import build_agent_packet, build_records
from tests.test_support import workspace_temp_dir


class LlmFirstGovernanceTests(unittest.TestCase):
    def test_legacy_and_model_api_commands_are_not_exposed(self) -> None:
        parser = governance.build_parser()
        for command in ("recover-keywords", "build-batch-file", "submit-batch", "aggregate-directions", "build-tag-plan"):
            with self.subTest(command=command), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args([command])

    def test_task_defaults_use_separate_output_paths(self) -> None:
        content = governance.default_path(TaskKind.CONTENT_TAGS, "corpus", "jsonl")
        library = governance.default_path(TaskKind.LIBRARY_STRUCTURE, "corpus", "jsonl")
        self.assertNotEqual(content, library)

    def test_content_packet_physically_excludes_operational_context(self) -> None:
        with workspace_temp_dir() as root:
            corpus = root / "corpus.jsonl"
            packet = root / "packet.jsonl"
            instructions = root / "instructions.md"
            corpus.write_text(json.dumps({
                "item_key": "ITEM0001",
                "semantic_scope": "document_content_only",
                "selection_is_not_evidence": True,
                "semantic_evidence": {"title": "Example"},
                "evidence_hash": "a" * 64,
            }) + "\n", encoding="utf-8")
            self.assertEqual(build_agent_packet(corpus, packet, instructions, TaskKind.CONTENT_TAGS), 1)
            record = json.loads(packet.read_text(encoding="utf-8").strip())
            self.assertNotIn("current_state", record)
            self.assertNotIn("keywords_for_ai", json.dumps(record))
            self.assertTrue(record["selection_is_not_evidence"])
            text = instructions.read_text(encoding="utf-8")
            self.assertIn("collection or project that selected an item is never semantic evidence", text)
            self.assertNotIn("collection_candidates", result_schema(TaskKind.CONTENT_TAGS)["properties"])

    def test_content_packet_rejects_operational_context(self) -> None:
        with workspace_temp_dir() as root:
            corpus = root / "corpus.jsonl"
            corpus.write_text(json.dumps({
                "item_key": "ITEM0001", "semantic_scope": "document_content_only",
                "semantic_evidence": {"title": "Example"}, "current_state": {"tags": ["project"]},
            }) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "operational context"):
                build_agent_packet(corpus, root / "packet.jsonl", root / "instructions.md", TaskKind.CONTENT_TAGS)

    def test_task_specific_result_validation(self) -> None:
        content = {
            "item_key": "ITEM0001", "evidence_hash": "a" * 64, "type_tag": "#Type/Study", "status_tags": [],
            "method_tags": ["#Method/Optimization"], "object_tags": [], "parameter_tags": [],
            "field_tags": [], "needs_manual_review": False, "evidence": "title and abstract",
        }
        item_key, parsed, error = validate_result(TaskKind.CONTENT_TAGS, content)
        self.assertEqual((item_key, parsed, error), ("ITEM0001", content, ""))
        content["collection_candidates"] = []
        _key, parsed, error = validate_result(TaskKind.CONTENT_TAGS, content)
        self.assertIsNone(parsed)
        self.assertIn("unexpected fields", error)

    def test_content_evidence_is_invariant_to_tags_and_collections(self) -> None:
        with workspace_temp_dir() as root:
            db_path = root / "library.sqlite"
            with sqlite3.connect(db_path) as connection:
                connection.executescript("""
                    CREATE TABLE items (
                        item_key TEXT, item_type TEXT, title TEXT, year TEXT, date TEXT,
                        publication TEXT, journal_abbreviation TEXT, doi TEXT, isbn TEXT,
                        url TEXT, language TEXT, abstract_note TEXT, tags_json TEXT,
                        collection_paths_json TEXT, zotero_deleted INTEGER
                    );
                    CREATE TABLE pdf_texts (
                        item_key TEXT, attachment_key TEXT, status TEXT, text_chars INTEGER,
                        text_normalized_cache_path TEXT
                    );
                """)
                connection.execute(
                    "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("ITEM0001", "journalArticle", "Stable content", "2025", "", "Journal", "", "", "", "", "en",
                     "Same abstract", '["project-tag"]', '["00.科研项目/项目甲"]', 0),
                )
            first = build_records(db_path, root, root, TaskKind.CONTENT_TAGS)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "UPDATE items SET tags_json=?, collection_paths_json=? WHERE item_key=?",
                    ('["another-tag"]', '["00.科研项目/项目乙"]', "ITEM0001"),
                )
            second = build_records(db_path, root, root, TaskKind.CONTENT_TAGS)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
