import json
import socket
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tools.runtime.publish_corpus import (
    CorpusPublicationError,
    apply_plan,
    apply_rollback,
    build_plan,
    validate_plan_state,
    verify_manifest,
)


def role_config(path: Path, corpus_role: str = "publisher") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "terminal_name": socket.gethostname(),
                "framework_role": "maintainer",
                "corpus_role": corpus_role,
                "zotero_role": "reader",
                "project_writer_mode": "transferable",
                "configured_at": "2026-07-20T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    return path


class CorpusPublicationTests(unittest.TestCase):
    def test_manifest_committed_apply_verify_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            corpus = root / "corpus"
            database = staging / "zotero_library.sqlite"
            database.parent.mkdir(parents=True)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("CREATE TABLE items(value TEXT)")
                connection.execute("INSERT INTO items VALUES('new')")
                connection.commit()
            card = staging / "reading-cards" / "cards" / "RC-001.md"
            card.parent.mkdir(parents=True)
            card.write_text("new card\n", encoding="utf-8")
            old_card = corpus / "reading-cards" / "cards" / "RC-001.md"
            old_card.parent.mkdir(parents=True)
            old_card.write_text("old card\n", encoding="utf-8")

            plan = build_plan(staging, corpus)
            self.assertEqual(len(plan["files"]), 2)
            result = apply_plan(plan, role_config(root / "role.json"), root / "archive")
            self.assertTrue(result["applied"])
            self.assertEqual(old_card.read_text(encoding="utf-8"), "new card\n")
            self.assertTrue(verify_manifest(corpus)["valid"])

            rollback_path = Path(result["archive"]) / "rollback-plan.json"
            rollback = json.loads(rollback_path.read_text(encoding="utf-8"))
            rolled_back = apply_rollback(rollback, root / "role.json")
            self.assertTrue(rolled_back["rolled_back"])
            self.assertEqual(old_card.read_text(encoding="utf-8"), "old card\n")
            self.assertFalse((corpus / "zotero" / "M-001-zotero-library" / "zotero_library.sqlite").exists())

    def test_reader_role_cannot_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging" / "reading-cards" / "cards"
            staging.mkdir(parents=True)
            (staging / "RC-001.md").write_text("card\n", encoding="utf-8")
            plan = build_plan(root / "staging", root / "corpus")
            with self.assertRaises(Exception):
                apply_plan(plan, role_config(root / "role.json", "reader"), root / "archive")

    def test_plan_rejects_unmapped_staging_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            staging.mkdir()
            (staging / "unexpected.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(CorpusPublicationError):
                build_plan(staging, root / "corpus")

    def test_plan_validation_rejects_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            card = root / "staging" / "reading-cards" / "cards" / "RC-001.md"
            card.parent.mkdir(parents=True)
            card.write_text("planned\n", encoding="utf-8")
            plan = build_plan(root / "staging", root / "corpus")
            card.write_text("changed\n", encoding="utf-8")
            with self.assertRaises(CorpusPublicationError):
                validate_plan_state(plan)


if __name__ == "__main__":
    unittest.main()
