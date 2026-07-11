from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tools.zotero.write.zotero_web_api import env_config


class ZoteroWebApiHelperTests(unittest.TestCase):
    def test_env_config_requires_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                env_config()

    def test_env_config_returns_values_without_logging(self) -> None:
        values = {
            "ZOTERO_API_KEY": "secret-value",
            "ZOTERO_USER_ID": "123",
            "ZOTERO_API_BASE": "https://example.invalid/",
        }
        with patch.dict(os.environ, values, clear=True):
            config = env_config()
        self.assertEqual(config["api_key"], "secret-value")
        self.assertEqual(config["user_id"], "123")
        self.assertEqual(config["api_base"], "https://example.invalid")


if __name__ == "__main__":
    unittest.main()
