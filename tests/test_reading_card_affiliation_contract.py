from __future__ import annotations

import unittest

from tools.reading_cards.card_common import (
    affiliation_publish_blockers,
    normalized_affiliation_status,
)


class ReadingCardAffiliationContractTests(unittest.TestCase):
    def test_heuristic_candidate_is_never_publishable(self) -> None:
        blockers = affiliation_publish_blockers({
            "first_author_affiliation": "Example University",
            "first_author_affiliation_status": "heuristic_candidate",
            "first_author_affiliation_source": "first-page regex",
        })
        self.assertEqual(blockers, ["affiliation_semantic_review_incomplete:heuristic_candidate"])

    def test_semantic_confirmed_requires_raw_evidence_and_page_source(self) -> None:
        blockers = affiliation_publish_blockers({
            "first_author_affiliation": "Example University, China",
            "first_author_affiliation_status": "semantic_confirmed",
            "first_author_affiliation_source": "semantic extraction",
        })
        self.assertIn("affiliation_semantic_confirmed_without_raw_evidence", blockers)
        self.assertIn("affiliation_semantic_confirmed_without_page_source", blockers)

    def test_semantic_confirmed_with_provenance_is_publishable(self) -> None:
        blockers = affiliation_publish_blockers({
            "first_author_affiliation": "Example University, China",
            "first_author_affiliation_raw": "School, Example University, China",
            "first_author_affiliation_source": "PDF 第 1 页作者区语义识别",
            "first_author_affiliation_status": "semantic_confirmed",
        })
        self.assertEqual(blockers, [])

    def test_legacy_ok_is_only_compatible_with_explicit_semantic_provenance(self) -> None:
        confirmed = {
            "first_author_affiliation_status": "ok",
            "first_author_affiliation_raw": "Example University",
            "first_author_affiliation_source": "PDF page 1 semantic extraction",
        }
        self.assertEqual(normalized_affiliation_status(confirmed), "semantic_confirmed")
        self.assertEqual(normalized_affiliation_status({"first_author_affiliation_status": "ok"}), "ok")

    def test_old_not_found_remains_pending(self) -> None:
        blockers = affiliation_publish_blockers({"first_author_affiliation_status": "not_found"})
        self.assertEqual(blockers, ["affiliation_semantic_review_incomplete:not_found"])


if __name__ == "__main__":
    unittest.main()
