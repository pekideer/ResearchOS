from __future__ import annotations

import unittest
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tools.reading_cards.zotero_library_pipeline import (
    canonicalize_affiliation,
    compare_top_item_snapshots,
    curation_local_failures,
    enrich_existing_card,
    journal_display,
    local_parent_note_counts,
    machine_network_env,
    relative_link_path,
    render_card,
    resolve_paths,
    rollback_file_writes,
    run_pipeline,
    seed_work_cards,
    semantic_result_record,
    strict_audit_failures,
    top_item_snapshot_payload,
)
from tools.reading_cards.card_common import reading_card_project_links, yaml_scalar
from tools.reading_cards.sync_journal_rankings import normalize_project_links_frontmatter


class ZoteroLibraryPipelineTests(unittest.TestCase):
    def test_snapshot_comparison_detects_key_and_version_changes(self) -> None:
        before = top_item_snapshot_payload([
            {"key": "AAAA1111", "version": 1},
            {"key": "BBBB2222", "version": 2},
        ])
        after = top_item_snapshot_payload([
            {"key": "AAAA1111", "version": 3},
            {"key": "CCCC3333", "version": 1},
        ])
        comparison = compare_top_item_snapshots(before, after)
        self.assertEqual(comparison["added"], ["CCCC3333"])
        self.assertEqual(comparison["removed"], ["BBBB2222"])
        self.assertEqual(comparison["version_changed"], ["AAAA1111"])
        self.assertFalse(comparison["stable"])

    def test_curation_gate_detects_duplicate_identity_and_incomplete_deep_card(self) -> None:
        records = [
            {
                "item_key": "ACTIVE01",
                "frontmatter": {"generation_mode": "auto_initial_screening", "fulltext_status": "full_text_available_needs_review"},
                "metadata": {
                    "first_author_affiliation": "Example University, China",
                    "first_author_affiliation_status": "semantic_confirmed",
                },
            },
            {"item_key": "ACTIVE01", "frontmatter": {}, "metadata": {}},
            {"item_key": "DELETED1", "frontmatter": {}, "metadata": {}},
        ]
        failures = curation_local_failures(
            {"ACTIVE01"},
            {"ACTIVE01"},
            {"ACTIVE01": "10.1/test", "DELETED1": "10.1/test"},
            {"DELETED1"},
            {"ACTIVE01": "ok"},
            records,
        )
        self.assertEqual(failures["duplicate_cards_by_item_key"], 1)
        self.assertEqual(failures["deleted_card_doi_conflicts"], 1)
        self.assertEqual(failures["fulltext_available_but_not_deep_read"], 1)
        self.assertEqual(failures["confirmed_affiliation_not_chinese_form"], 1)

    def test_curation_gate_scopes_duplicate_cards_but_keeps_related_doi_conflicts(self) -> None:
        records = [
            {"item_key": "TARGET01", "frontmatter": {}, "metadata": {}},
            {"item_key": "RELATED", "frontmatter": {}, "metadata": {}},
            {"item_key": "OTHER001", "frontmatter": {}, "metadata": {}},
            {"item_key": "OTHER001", "frontmatter": {}, "metadata": {}},
        ]
        failures = curation_local_failures(
            {"TARGET01"},
            {"TARGET01", "RELATED", "OTHER001"},
            {"TARGET01": "10.1/target", "RELATED": "10.1/target", "OTHER001": "10.1/other"},
            set(),
            {},
            records,
        )
        self.assertEqual(failures["duplicate_cards_by_item_key"], 0)
        self.assertEqual(failures["active_doi_with_multiple_cards"], 1)

    def test_parent_note_counts_fetches_notes_once_and_groups_by_parent(self) -> None:
        notes = [
            {
                "data": {
                    "itemType": "note",
                    "parentItem": "ITEM0001",
                    "tags": [{"tag": "rs:reading-card"}],
                    "note": "",
                },
            },
            {
                "data": {
                    "itemType": "note",
                    "parentItem": "ITEM0001",
                    "tags": [],
                    "note": "ResearchOS card id: RC-002",
                },
            },
            {
                "data": {
                    "itemType": "note",
                    "parentItem": "ITEM0002",
                    "tags": [],
                    "note": "ordinary note",
                },
            },
        ]
        with patch("tools.reading_cards.zotero_library_pipeline.ZoteroClient") as client_class:
            client_class.return_value.fetch_paged.return_value = notes
            counts = local_parent_note_counts({"ITEM0001", "ITEM0002"})
        self.assertEqual(counts, {"ITEM0001": 2, "ITEM0002": 0})
        client_class.return_value.fetch_paged.assert_called_once_with(
            "items",
            {"itemType": "note", "sort": "dateModified", "direction": "desc"},
        )
    def test_legacy_project_links_unescape_once_then_stay_stable(self) -> None:
        links = '[{"project_id":"project-a","association_order":1}]'
        parsed_value = links
        repeatedly_escaped = ""
        for _ in range(4):
            repeatedly_escaped = yaml_scalar(parsed_value)
            parsed_value = repeatedly_escaped.strip("'\"")
        card = f"---\nproject_links: {repeatedly_escaped}\n---\n\n# Card\n"
        normalized = normalize_project_links_frontmatter(card)
        self.assertEqual(normalized, normalize_project_links_frontmatter(normalized))
        self.assertEqual(reading_card_project_links(normalized)[0]["project_id"], "project-a")

    def test_master_index_links_from_sibling_index_directory(self) -> None:
        self.assertEqual(
            relative_link_path(Path(r"D:\ResearchOS\corpus\reading-cards\cards\RC-080.md"), Path(r"D:\ResearchOS\corpus\reading-cards\indexes")),
            "../cards/RC-080.md",
        )

    def test_network_env_always_bypasses_proxy_for_local_api(self) -> None:
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://machine-specific:9999"}, clear=True):
            env, source = machine_network_env(Path("does-not-exist"))
        self.assertEqual(source, "environment")
        self.assertEqual(env["HTTPS_PROXY"], "http://machine-specific:9999")
        self.assertIn("127.0.0.1", env["NO_PROXY"])
        self.assertIn("localhost", env["NO_PROXY"])

    def test_run_pipeline_passes_db_and_local_lock_dir_to_writer_steps(self) -> None:
        root = Path.cwd() / ".researchos" / "tmp" / "pipeline-fixture"
        db = root / ".researchos" / "staging" / "zotero" / "library.sqlite"
        cards_root = root / ".researchos" / "staging" / "reading-cards" / "cards"
        index_path = root / ".researchos" / "staging" / "reading-cards" / "indexes" / "reading-card-master-index.md"
        lock_dir = root / ".researchos" / "locks"
        args = Namespace(
            researchos_root=root,
            db=db,
            work_db=None,
            cards_root=cards_root,
            index_path=index_path,
            work_cards_root=None,
            work_index_path=None,
            lock_dir=lock_dir,
            scope="new",
            item_key=[],
            no_journal_api=True,
            skip_sync=False,
            limit=None,
        )
        calls: list[list[str]] = []

        def fake_run_step(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
            calls.append(command)

        with patch("tools.reading_cards.zotero_library_pipeline.run_step", fake_run_step), patch(
            "tools.reading_cards.zotero_library_pipeline.reconcile_soft_deleted_items",
            return_value=(0, 0),
        ) as reconcile:
            self.assertEqual(run_pipeline(args), 0)

        db_arg = str(db.resolve())
        lock_arg = str(lock_dir.resolve())
        self.assertIn(["--db", db_arg], [calls[0][i : i + 2] for i in range(len(calls[0]) - 1)])
        self.assertIn(["--lock-dir", lock_arg], [calls[0][i : i + 2] for i in range(len(calls[0]) - 1)])
        self.assertIn(["--db", db_arg], [calls[1][i : i + 2] for i in range(len(calls[1]) - 1)])
        self.assertIn(["--lock-dir", lock_arg], [calls[1][i : i + 2] for i in range(len(calls[1]) - 1)])
        self.assertIn(["--db", db_arg], [calls[2][i : i + 2] for i in range(len(calls[2]) - 1)])
        self.assertIn(["--lock-dir", lock_arg], [calls[2][i : i + 2] for i in range(len(calls[2]) - 1)])
        self.assertIn(["--journal-rankings-db", db_arg], [calls[3][i : i + 2] for i in range(len(calls[3]) - 1)])
        self.assertIn(["--cards-root", str(cards_root.absolute())], [calls[3][i : i + 2] for i in range(len(calls[3]) - 1)])
        self.assertIn(["--db", db_arg], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        self.assertIn(["--cards-root", str(cards_root.absolute())], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        self.assertIn(["--index-path", str(index_path.absolute())], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        self.assertIn(["--lock-dir", lock_arg], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        reconcile.assert_called_once_with(db.absolute(), lock_dir.absolute())

    def test_run_pipeline_defaults_to_machine_local_work_db(self) -> None:
        root = Path.cwd() / ".researchos" / "tmp" / "pipeline-fixture"
        work_db = root / ".researchos" / "staging" / "zotero_library.sqlite"
        work_cards_root = root / ".researchos" / "staging" / "reading-cards" / "cards"
        work_index_path = root / ".researchos" / "staging" / "reading-cards" / "indexes" / "reading-card-master-index.md"
        lock_dir = root / ".researchos" / "locks"
        args = Namespace(
            researchos_root=root,
            db=None,
            work_db=work_db,
            cards_root=None,
            index_path=None,
            work_cards_root=work_cards_root,
            work_index_path=work_index_path,
            lock_dir=lock_dir,
            scope="new",
            item_key=[],
            no_journal_api=True,
            skip_sync=False,
            limit=None,
        )
        calls: list[list[str]] = []

        def fake_run_step(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
            calls.append(command)

        with patch("tools.reading_cards.zotero_library_pipeline.run_step", fake_run_step), patch(
            "tools.reading_cards.zotero_library_pipeline.reconcile_soft_deleted_items",
            return_value=(0, 0),
        ) as reconcile:
            self.assertEqual(run_pipeline(args), 0)

        work_db_arg = str(work_db.absolute())
        self.assertIn(["--db", work_db_arg], [calls[0][i : i + 2] for i in range(len(calls[0]) - 1)])
        self.assertIn(["--db", work_db_arg], [calls[1][i : i + 2] for i in range(len(calls[1]) - 1)])
        self.assertIn(["--db", work_db_arg], [calls[2][i : i + 2] for i in range(len(calls[2]) - 1)])
        self.assertIn(["--journal-rankings-db", work_db_arg], [calls[3][i : i + 2] for i in range(len(calls[3]) - 1)])
        self.assertIn(["--cards-root", str(work_cards_root.absolute())], [calls[3][i : i + 2] for i in range(len(calls[3]) - 1)])
        self.assertIn(["--db", work_db_arg], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        self.assertIn(["--cards-root", str(work_cards_root.absolute())], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        self.assertIn(["--index-path", str(work_index_path.absolute())], [calls[4][i : i + 2] for i in range(len(calls[4]) - 1)])
        reconcile.assert_called_once_with(work_db.absolute(), lock_dir.absolute())

    def test_run_pipeline_rejects_direct_shared_corpus_targets(self) -> None:
        root = Path.cwd() / ".researchos" / "tmp" / "pipeline-direct-corpus-fixture"
        args = Namespace(
            researchos_root=root,
            db=root / "corpus" / "zotero" / "library.sqlite",
            work_db=None,
            cards_root=root / "corpus" / "reading-cards" / "cards",
            index_path=root / "corpus" / "reading-cards" / "indexes" / "master.md",
            work_cards_root=None,
            work_index_path=None,
            lock_dir=root / ".researchos" / "locks",
            scope="new",
            item_key=[],
            no_journal_api=True,
            skip_sync=True,
            limit=None,
        )
        with self.assertRaises(ValueError):
            run_pipeline(args)

    def test_follow_up_commands_reuse_existing_default_staging(self) -> None:
        root = Path.cwd() / ".researchos" / "tmp" / "active-staging-fixture"
        staged_db = root / ".researchos" / "outputs" / "machine" / "M-006-zotero-ingestion-pipeline" / "staging" / "zotero_library.sqlite"
        staged_cards = staged_db.parent / "reading-cards" / "cards"
        staged_index = staged_db.parent / "reading-cards" / "indexes" / "reading-card-master-index.md"
        with patch("tools.reading_cards.zotero_library_pipeline.default_work_db", return_value=staged_db), patch(
            "tools.reading_cards.zotero_library_pipeline.default_work_cards_root", return_value=staged_cards
        ), patch("tools.reading_cards.zotero_library_pipeline.default_work_index_path", return_value=staged_index), patch.object(
            type(staged_db), "exists", return_value=True
        ):
            args = Namespace(researchos_root=root, db=None, cards_root=None, index_path=None)
            _root, db, cards, index = resolve_paths(args)
        self.assertEqual(db, staged_db)
        self.assertEqual(cards, staged_cards)
        self.assertEqual(index, staged_index)

    def test_follow_up_commands_reject_incomplete_default_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            staged_db = root / "staging" / "zotero_library.sqlite"
            staged_cards = root / "staging" / "reading-cards" / "cards"
            staged_index = root / "staging" / "reading-cards" / "indexes" / "reading-card-master-index.md"
            staged_db.parent.mkdir(parents=True)
            staged_db.write_bytes(b"")
            with patch("tools.reading_cards.zotero_library_pipeline.default_work_db", return_value=staged_db), patch(
                "tools.reading_cards.zotero_library_pipeline.default_work_cards_root", return_value=staged_cards
            ), patch("tools.reading_cards.zotero_library_pipeline.default_work_index_path", return_value=staged_index):
                args = Namespace(researchos_root=root, db=None, cards_root=None, index_path=None)
                with self.assertRaises(RuntimeError):
                    resolve_paths(args)

    def test_staging_seed_does_not_duplicate_an_existing_item_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            staging = root / "staging"
            source.mkdir()
            staging.mkdir()
            (staging / "RC-001_EXISTING.md").write_text("---\nzotero_key: ITEM0001\n---\n", encoding="utf-8")
            (source / "RC-099_RENAMED.md").write_text("---\nzotero_key: ITEM0001\n---\n", encoding="utf-8")
            (source / "RC-002_NEW.md").write_text("---\nzotero_key: ITEM0002\n---\n", encoding="utf-8")
            self.assertTrue(seed_work_cards(source, staging))
            self.assertFalse((staging / "RC-099_RENAMED.md").exists())
            self.assertTrue((staging / "RC-002_NEW.md").exists())

    def test_strict_audit_uses_active_key_sets_not_total_row_counts(self) -> None:
        failures = strict_audit_failures(
            {"ACTIVE01", "ACTIVE02"},
            {"ACTIVE01", "HISTORY1"},
            {"ACTIVE01": "semantic_confirmed", "HISTORY1": "semantic_confirmed"},
            {"ACTIVE01", "ACTIVE02", "HISTORY1"},
        )
        self.assertEqual(failures["missing_pipeline_state"], 1)
        self.assertEqual(failures["missing_affiliation_state"], 1)
        self.assertEqual(failures["missing_cards"], 0)

    def test_local_file_transaction_restores_existing_and_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "existing.md"
            created = root / "created.md"
            existing.write_text("before", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                with rollback_file_writes() as rollback:
                    rollback.write_text(existing, "after")
                    rollback.write_text(created, "new")
                    raise RuntimeError("injected failure")
            self.assertEqual(existing.read_text(encoding="utf-8"), "before")
            self.assertFalse(created.exists())

    def test_affiliation_canonicalization_groups_department_variant(self) -> None:
        canonical, normalized = canonicalize_affiliation(
            "Department of Civil Engineering, Hunan University, Changsha, China"
        )
        self.assertEqual(canonical, "Hunan University")
        self.assertEqual(normalized, "hunanuniversity")

    def test_missing_rank_has_explicit_status_instead_of_question_mark(self) -> None:
        self.assertEqual(journal_display("no_match", ""), "未收录")
        self.assertEqual(journal_display("unqueried", ""), "待查询")

    def test_existing_card_only_fills_missing_visible_fields(self) -> None:
        card = "- **单位：** ?\n- **期刊等级：** ？\n"
        updated = enrich_existing_card(
            card,
            {
                "display": "",
                "status": "not_processed",
                "raw": "",
                "normalized": "",
                "source": "semantic review required",
                "evidence_path": "test.txt",
            },
            "no_match",
            "",
        )
        self.assertIn("单位：** 待语义识别", updated)
        self.assertNotIn("Hunan University", updated)
        self.assertIn("期刊等级：** 未收录", updated)
        self.assertNotIn("** ?", updated)
        self.assertNotIn("** ？", updated)

    def test_generated_screening_card_omits_project_borrowing_section(self) -> None:
        item = {
            "item_key": "ABCD1234",
            "title": "A test paper",
            "creators_json": '[{"firstName":"Ada","lastName":"Lovelace"}]',
            "abstract_note": "Abstract evidence.",
            "year": "2026",
            "publication": "Test Journal",
            "doi": "10.1/test",
            "item_type": "journalArticle",
            "version": 7,
        }
        affiliation = {
            "display": "",
            "status": "not_processed",
            "raw": "",
            "normalized": "",
            "source": "semantic review required",
            "evidence_path": "test.txt",
        }
        evidence = {
            "status": "ok",
            "pages_total": 10,
            "pages_extracted": 10,
            "pages_with_text": 10,
            "text_chars": 1000,
            "path": "corpus/fulltext/test.txt",
            "attachment_key": "EFGH5678",
        }
        card = render_card(item, "RC-080", affiliation, "unqueried", "", evidence, "2026-07-14T12:00:00+08:00")
        self.assertNotIn("## 6.", card)
        self.assertIn("本卡不生成第 6 章", card)
        self.assertNotIn("**期刊等级：** ?", card)
        self.assertIn("单位：** 待语义识别", card)
        self.assertNotIn("first_author_affiliation_candidate", card)
        self.assertNotIn("单位：** Test University", card)

    def test_semantic_result_preserves_country_in_display(self) -> None:
        result = {
            "first_author_affiliation": "浙江大学, 中国",
            "first_author_affiliation_raw": "浙江大学建筑系，杭州 310058",
            "first_author_affiliation_source": "规范化 PDF 第 1 页作者区语义识别",
            "first_author_affiliation_status": "semantic_confirmed",
            "pages_checked": [1],
        }
        record = semantic_result_record(result, {"text_status": "ok", "front_text": "evidence", "text_path": "page.txt"})
        self.assertEqual(record["display"], "浙江大学, 中国")
        self.assertEqual(record["normalized"], "浙江大学")

    def test_source_unavailable_rejected_when_text_exists(self) -> None:
        result = {
            "first_author_affiliation": "",
            "first_author_affiliation_raw": "",
            "first_author_affiliation_source": "missing PDF",
            "first_author_affiliation_status": "source_unavailable",
            "pages_checked": [],
        }
        with self.assertRaisesRegex(ValueError, "conflicts with available"):
            semantic_result_record(result, {"text_status": "ok", "front_text": "evidence", "text_path": "page.txt"})


if __name__ == "__main__":
    unittest.main()
