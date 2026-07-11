from __future__ import annotations

import unittest

from tools.reading_cards.card_common import (
    format_publication_tags,
    parse_metadata,
    raw_item_key,
    zotero_item_markdown_link,
)


class ReadingCardCommonTests(unittest.TestCase):
    def test_parse_folded_metadata(self) -> None:
        body = """## 7. 元数据（折叠）

```yaml
item_key: "ABCD1234"
title: "Example"
```
"""
        self.assertEqual(parse_metadata(body)["title"], "Example")

    def test_normalize_zotero_item_key(self) -> None:
        value = "[ABCD1234](zotero://select/library/items/ABCD1234)"
        self.assertEqual(raw_item_key(value), "ABCD1234")
        self.assertEqual(zotero_item_markdown_link(value), value)

    def test_format_publication_tags(self) -> None:
        text, ranks = format_publication_tags({"sciif": "7.5", "eii": "EI检索"})
        self.assertEqual(ranks["sciif"], "7.5")
        self.assertIn("sciif: 7.5", text)
        self.assertIn("eii: EI", text)


if __name__ == "__main__":
    unittest.main()
