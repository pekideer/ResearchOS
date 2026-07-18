from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.reading_cards.zotero_library_pipeline import (
    canonicalize_affiliation,
    enrich_existing_card,
    journal_display,
    machine_network_env,
    page_one_affiliation_candidate,
    relative_link_path,
    render_card,
    rollback_file_writes,
    semantic_result_record,
    strict_audit_failures,
)
from tools.reading_cards.card_common import reading_card_project_links, yaml_scalar
from tools.reading_cards.sync_journal_rankings import normalize_project_links_frontmatter


class ZoteroLibraryPipelineTests(unittest.TestCase):
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

    def test_page_one_affiliation_ignores_title_before_author_block(self) -> None:
        text = """===== Page 1 =====
Hybrid Approach for Digital Twins in the Built Environment Yu-Wen Lin yuwen.lin@example.edu University of California, Berkeley Berkeley, CA, USA ABSTRACT details
===== Page 2 =====
2. Laboratory experiment University wording in the body
"""
        self.assertEqual(page_one_affiliation_candidate(text), "University of California, Berkeley")

    def test_missing_rank_has_explicit_status_instead_of_question_mark(self) -> None:
        self.assertEqual(journal_display("no_match", ""), "未收录")
        self.assertEqual(journal_display("unqueried", ""), "待查询")

    def test_existing_card_only_fills_missing_visible_fields(self) -> None:
        card = "- **单位：** ?\n- **期刊等级：** ？\n"
        updated = enrich_existing_card(
            card,
            {
                "display": "Hunan University",
                "status": "heuristic_candidate",
                "raw": "Hunan University",
                "normalized": "hunanuniversity",
                "source": "test",
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
            "display": "Test University",
            "status": "heuristic_candidate",
            "raw": "Test University",
            "normalized": "testuniversity",
            "source": "test",
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
        self.assertIn("first_author_affiliation_candidate", card)
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
