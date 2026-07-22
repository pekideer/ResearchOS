from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.runtime.corpus_snapshot import DEFAULT_ZONES, compute_snapshot


def make_corpus(root: Path) -> None:
    for zone in DEFAULT_ZONES:
        target = root / zone
        target.mkdir(parents=True)
        (target / "sample.txt").write_text(zone, encoding="utf-8")


class CorpusSnapshotTests(unittest.TestCase):
    def test_snapshot_is_stable_and_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_corpus(root)
            first = compute_snapshot(root)
            second = compute_snapshot(root)
            self.assertEqual(first["snapshot_id"], second["snapshot_id"])
            (root / "zotero" / "sample.txt").write_text("changed", encoding="utf-8")
            changed = compute_snapshot(root)
            self.assertNotEqual(first["snapshot_id"], changed["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
