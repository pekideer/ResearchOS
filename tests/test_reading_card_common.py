from __future__ import annotations

import unittest
from pathlib import Path

from tools.reading_cards.card_common import (
    format_publication_tags,
    parse_metadata,
    parse_frontmatter,
    raw_item_key,
    reading_card_identity,
    reading_card_project_links,
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

    def test_reading_card_identity_prefers_frontmatter(self) -> None:
        body = """---
card_id: RC-099
zotero_key: ABCD1234
---
# Card
"""
        self.assertEqual(parse_frontmatter(body)["card_id"], "RC-099")
        self.assertEqual(reading_card_identity(body, Path("ignored.md")), ("RC-099", "ABCD1234"))

    def test_project_links_support_multiple_projects_and_legacy_cards(self) -> None:
        body = '''---
project_links: [{"project_id":"p-2","project_name":"项目二","association_order":2},{"project_id":"p-1","project_name":"项目一","association_order":1}]
---
'''
        self.assertEqual(
            reading_card_project_links(body),
            [
                {"project_id": "p-1", "project_name": "项目一", "association_order": 1},
                {"project_id": "p-2", "project_name": "项目二", "association_order": 2},
            ],
        )
        legacy = "---\nproject_id: legacy-project\n---\n"
        self.assertEqual(
            reading_card_project_links(legacy),
            [{"project_id": "legacy-project", "project_name": "", "association_order": 1}],
        )


if __name__ == "__main__":
    unittest.main()
