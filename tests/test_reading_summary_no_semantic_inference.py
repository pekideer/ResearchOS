from __future__ import annotations

import unittest

from tools.reading_cards.sync_reading_summary_table import html_link, normalize_relevance_degree


class ReadingSummaryNoSemanticInferenceTests(unittest.TestCase):
    def test_missing_relevance_remains_unset(self) -> None:
        self.assertEqual(normalize_relevance_degree(""), "")
        self.assertEqual(normalize_relevance_degree("?"), "")

    def test_explicit_agent_or_human_relevance_is_preserved(self) -> None:
        self.assertEqual(normalize_relevance_degree("直接相关：核心方法"), "直接相关")
        self.assertEqual(normalize_relevance_degree("相邻相关"), "待复核")

    def test_html_links_do_not_depend_on_local_open_service(self) -> None:
        anchor = html_link("卡", "../corpus/card.md")
        self.assertEqual(anchor, '<a href="../corpus/card.md">卡</a>')
        self.assertNotIn("__researchos_open", anchor)
        self.assertNotIn("onclick", anchor)


if __name__ == "__main__":
    unittest.main()
