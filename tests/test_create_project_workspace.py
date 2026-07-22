from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools.project import create_project_workspace as workspace


class CreateProjectWorkspaceAuditTests(unittest.TestCase):
    def make_context_chain(self, root: Path) -> None:
        research = root / ".research"
        research.mkdir(parents=True, exist_ok=True)
        (research / "run_state.json").write_text(
            '{"schema_version": 1, "project_id": "test"}\n', encoding="utf-8"
        )
        (research / "run-log.jsonl").write_text("", encoding="utf-8")

    def test_audit_flags_old_local_reading_cards_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.make_context_chain(root)
            (root / "01-reading-cards").mkdir()
            manifest = root / ".research" / "project_manifest.yml"
            manifest.parent.mkdir(parents=True, exist_ok=True)
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
            self.make_context_chain(root)
            manifest = root / ".research" / "project_manifest.yml"
            manifest.parent.mkdir(parents=True, exist_ok=True)
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

    def test_scaffold_includes_context_recovery_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            files = workspace.scaffold_files(
                root,
                [],
                True,
                workspace.CENTRALIZED_READING_CARDS,
                "00_ResearchOS/corpus/reading-cards/cards/",
            )

            relative = {path.relative_to(root).as_posix() for path in files}
            self.assertIn(".research/project_manifest.yml", relative)
            self.assertIn(".research/run_state.json", relative)
            self.assertIn(".research/run-log.jsonl", relative)

    def test_audit_rejects_missing_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            research = root / ".research"
            research.mkdir(parents=True)
            (research / "project_manifest.yml").write_text(
                'outputs:\n  reading_cards_mode: "centralized_links"\n', encoding="utf-8"
            )
            (research / "run-log.jsonl").write_text("", encoding="utf-8")

            with redirect_stdout(io.StringIO()) as output:
                code = workspace.audit_workspace(root, None)

            self.assertEqual(code, 4)
            self.assertIn("缺少 .research/run_state.json", output.getvalue())


if __name__ == "__main__":
    unittest.main()
