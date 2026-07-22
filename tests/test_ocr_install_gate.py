from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tools.runtime.ensure_ocr_needed import parse_args, run_ocr_needed


class OcrInstallGateTests(unittest.TestCase):
    def test_installation_is_disabled_by_default(self) -> None:
        self.assertFalse(parse_args([]).install)

    def test_installation_requires_explicit_flag(self) -> None:
        self.assertTrue(parse_args(["--install"]).install)

    def test_legacy_no_install_flag_remains_safe(self) -> None:
        self.assertFalse(parse_args(["--no-install"]).install)

    def test_ocr_needed_forwards_lock_dir_to_library_index(self) -> None:
        args = parse_args(["--db", "library.sqlite", "--lock-dir", "local-locks", "--dry-run"])
        with patch("builtins.print") as printer:
            run_ocr_needed(args)
        dry_run_line = printer.call_args[0][0]
        self.assertIn("--lock-dir", dry_run_line)
        self.assertIn(str(Path("local-locks")), dry_run_line)


if __name__ == "__main__":
    unittest.main()
