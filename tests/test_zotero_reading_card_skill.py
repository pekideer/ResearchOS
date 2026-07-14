from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "zotero-reading-card-annotation-sync"


class ZoteroReadingCardSkillTests(unittest.TestCase):
    def test_skill_frontmatter_and_ui_metadata(self) -> None:
        body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        parts = body.split("---", 2)
        self.assertEqual(parts[0].strip(), "")
        self.assertEqual(len(parts), 3)
        frontmatter = parts[1]
        name = re.search(r"(?m)^name:\s*(.+)$", frontmatter)
        description = re.search(r"(?m)^description:\s*(.+)$", frontmatter)
        self.assertIsNotNone(name)
        self.assertIsNotNone(description)
        skill_name = name.group(1).strip()
        self.assertEqual(skill_name, SKILL_DIR.name)
        self.assertRegex(skill_name, r"^[a-z0-9-]{1,64}$")
        self.assertLessEqual(len(description.group(1).strip()), 1024)

        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        short_description = re.search(r'(?m)^\s*short_description:\s*"([^"]+)"', metadata)
        default_prompt = re.search(r'(?m)^\s*default_prompt:\s*"([^"]+)"', metadata)
        self.assertIsNotNone(short_description)
        self.assertIsNotNone(default_prompt)
        self.assertGreaterEqual(len(short_description.group(1)), 25)
        self.assertLessEqual(len(short_description.group(1)), 64)
        self.assertIn(f"${skill_name}", default_prompt.group(1))


if __name__ == "__main__":
    unittest.main()
