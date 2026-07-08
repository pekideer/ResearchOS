from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools import create_project_workspace as workspace


class CreateProjectWorkspaceAuditTests(unittest.TestCase):
    def test_audit_flags_old_local_reading_cards_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "01-reading-cards").mkdir()
            manifest = root / ".research" / "project_manifest.yml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '\n'.join(
                    [
                        "outputs:",
                        '  reading_cards_mode: "centralized_links"',
                        '  centralized_reading_cards_dir: "00_ResearchOS/corpus/reading-cards/cards/"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()) as output:
                code = workspace.audit_workspace(
                    root,
                    "centralized:00_ResearchOS/corpus/reading-cards/cards/",
                )

            self.assertEqual(code, 4)
            self.assertIn("发现旧英文目录", output.getvalue())

    def test_audit_accepts_centralized_reading_cards_without_local_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / ".research" / "project_manifest.yml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '\n'.join(
                    [
                        "outputs:",
                        '  reading_cards_mode: "centralized_links"',
                        '  centralized_reading_cards_dir: "00_ResearchOS/corpus/reading-cards/cards/"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()) as output:
                code = workspace.audit_workspace(
                    root,
                    "centralized:00_ResearchOS/corpus/reading-cards/cards/",
                )

            self.assertEqual(code, 0)
            self.assertIn("OK: 项目登记、manifest 与中文目录规则一致", output.getvalue())


if __name__ == "__main__":
    unittest.main()
