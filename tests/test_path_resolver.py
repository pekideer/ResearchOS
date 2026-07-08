from __future__ import annotations

import os
import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "path_resolver",
    ROOT / ".agents" / "utils" / "path_resolver.py",
)
assert SPEC is not None and SPEC.loader is not None
path_resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(path_resolver)


def make_researchos_root(root: Path) -> None:
    (root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
    (root / ".agents" / "skills").mkdir(parents=True)
    (root / "templates").mkdir()


class PathResolverTests(unittest.TestCase):
    def test_load_machine_config_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_researchos_root(root)
            config = root / "machine_config.json"
            config.write_text('\ufeff{"projects_root": "D:/Projects"}\n', encoding="utf-8")

            with patch.dict(os.environ, {path_resolver.CONFIG_ENV_VAR: str(config)}):
                data, path = path_resolver.load_machine_config(root)

            self.assertEqual(data["projects_root"], "D:/Projects")
            self.assertEqual(path, config)

    def test_explicit_root_does_not_read_machine_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_researchos_root(root)
            bad_config = root / "bad-machine-config.json"
            bad_config.write_text("{not-json", encoding="utf-8")
            explicit = root / "Project"

            with patch.dict(os.environ, {path_resolver.CONFIG_ENV_VAR: str(bad_config)}):
                resolved, source, researchos_root, config_path = path_resolver.resolve_project_root(
                    explicit_root=str(explicit),
                    project_name=None,
                    start=root,
                )

            self.assertEqual(resolved, explicit)
            self.assertEqual(source, "--root")
            self.assertEqual(researchos_root, root)
            self.assertIsNone(config_path)


if __name__ == "__main__":
    unittest.main()
