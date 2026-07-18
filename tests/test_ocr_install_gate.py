from __future__ import annotations

import unittest

from tools.runtime.ensure_ocr_needed import parse_args


class OcrInstallGateTests(unittest.TestCase):
    def test_installation_is_disabled_by_default(self) -> None:
        self.assertFalse(parse_args([]).install)

    def test_installation_requires_explicit_flag(self) -> None:
        self.assertTrue(parse_args(["--install"]).install)

    def test_legacy_no_install_flag_remains_safe(self) -> None:
        self.assertFalse(parse_args(["--no-install"]).install)


if __name__ == "__main__":
    unittest.main()
