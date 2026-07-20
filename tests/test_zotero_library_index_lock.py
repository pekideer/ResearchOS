from __future__ import annotations

import unittest
from pathlib import Path

from tools.zotero.zotero_library_index import DEFAULT_WRITER_LOCK_DIR, writer_lock_path


class ZoteroLibraryIndexLockTests(unittest.TestCase):
    def test_default_writer_lock_is_machine_local_not_db_sibling(self) -> None:
        db = Path.cwd() / ".researchos" / "tmp" / "sync-root" / "zotero_library.sqlite"
        lock = writer_lock_path(db)
        self.assertEqual(lock.parent, DEFAULT_WRITER_LOCK_DIR)
        self.assertNotEqual(lock.parent, db.parent)

    def test_explicit_writer_lock_dir_uses_hashed_db_name(self) -> None:
        root = Path.cwd() / ".researchos" / "tmp" / "unit-test-fixture"
        lock = writer_lock_path(root / "corpus" / "zotero_library.sqlite", root / "locks")
        self.assertEqual(lock.parent, root / "locks")
        self.assertRegex(lock.name, r"^zotero_library\.sqlite\.[0-9a-f]{12}\.writer\.lock$")


if __name__ == "__main__":
    unittest.main()
