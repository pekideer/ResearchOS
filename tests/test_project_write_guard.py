import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.runtime.project_write_guard import (
    assert_project_targets,
    refuse_direct_shared_corpus_write,
    require_project_write_access,
)


class ProjectWriteGuardTests(unittest.TestCase):
    def test_rejects_target_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            with self.assertRaises(ValueError):
                assert_project_targets(root, [root.parent / "outside.md"])

    def test_calls_handoff_check_before_returning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "report.md"
            with patch("tools.runtime.project_write_guard.check_write", return_value={"allowed": True}) as guarded:
                result = require_project_write_access(
                    root,
                    agent_root=root,
                    corpus_root=root / "corpus",
                    role_config=root / "role.json",
                    targets=[target],
                )
            self.assertTrue(result["allowed"])
            guarded.assert_called_once()

    def test_direct_shared_corpus_write_is_reserved_for_publisher(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                refuse_direct_shared_corpus_write(root, [root / "corpus" / "reading-cards" / "cards"])
            refuse_direct_shared_corpus_write(root, [root / ".researchos" / "staging" / "cards"])


if __name__ == "__main__":
    unittest.main()
