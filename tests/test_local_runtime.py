from __future__ import annotations

import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.runtime.local_runtime import (
    LocalRuntimeError,
    apply_cleanup_plan,
    audit,
    build_cleanup_plan,
    initialize,
    write_json_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = ROOT / ".researchos" / "tmp"


@contextmanager
def temporary_directory():
    TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TEMP_ROOT / f"local-runtime-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_root(path: Path) -> None:
    (path / "AGENTS.md").write_text("# test\n", encoding="utf-8")
    (path / ".gitignore").write_text(".researchos/\n", encoding="utf-8")


class LocalRuntimeTests(unittest.TestCase):
    def test_init_creates_marker_and_managed_directories(self) -> None:
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            make_root(root)

            result = initialize(root, {
                "schema_version": 1,
                "retention_days": {"tmp": 7, "cache": 30, "logs": 14, "failed-runs": 30, "audit-staging": 30},
                "protected_scopes": {
                    "failed-runs": {"marker": "cleanup-state.json", "required_true": ["issue_closed"]},
                    "audit-staging": {"marker": "cleanup-state.json", "required_true": ["task_closed", "promoted"]},
                },
            })

            self.assertTrue(result["marker_valid"])
            self.assertTrue((root / ".researchos" / "runtime.json").is_file())
            for name in ("tmp", "cache", "logs", "failed-runs", "audit-staging"):
                self.assertTrue((root / ".researchos" / name).is_dir())

    def test_plan_selects_old_tmp_but_protects_unpromoted_audit(self) -> None:
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            make_root(root)
            from tools.runtime.local_runtime import DEFAULT_POLICY
            initialize(root, DEFAULT_POLICY)
            old_tmp = root / ".researchos" / "tmp" / "old.txt"
            old_tmp.write_text("old", encoding="utf-8")
            old_time = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
            os.utime(old_tmp, (old_time, old_time))
            audit_scope = root / ".researchos" / "audit-staging" / "pending"
            audit_scope.mkdir()
            (audit_scope / "receipt.json").write_text("{}", encoding="utf-8")

            plan = build_cleanup_plan(root)

            self.assertEqual([row["path"] for row in plan["candidates"]], ["tmp/old.txt"])
            self.assertEqual(plan["protected_scopes"][0]["reason"], "closure_marker_missing")

    def test_apply_requires_unchanged_explicit_plan(self) -> None:
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            make_root(root)
            from tools.runtime.local_runtime import DEFAULT_POLICY
            initialize(root, DEFAULT_POLICY)
            old_tmp = root / ".researchos" / "tmp" / "old.txt"
            fresh_tmp = root / ".researchos" / "tmp" / "fresh.txt"
            old_tmp.write_text("old", encoding="utf-8")
            fresh_tmp.write_text("fresh", encoding="utf-8")
            old_time = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
            os.utime(old_tmp, (old_time, old_time))
            plan_path = root / ".researchos" / "cleanup-plan.json"
            write_json_atomic(plan_path, build_cleanup_plan(root))

            result = apply_cleanup_plan(root, plan_path)

            self.assertEqual(result["deleted_count"], 1)
            self.assertFalse(old_tmp.exists())
            self.assertTrue(fresh_tmp.exists())

    def test_audit_reports_unmanaged_legacy_directory(self) -> None:
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            make_root(root)
            from tools.runtime.local_runtime import DEFAULT_POLICY
            initialize(root, DEFAULT_POLICY)
            (root / ".researchos" / "outputs").mkdir()

            report = audit(root)

            self.assertEqual(report["unmanaged_top_level"], ["outputs"])

    def test_missing_marker_refuses_cleanup_plan(self) -> None:
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            make_root(root)
            (root / ".researchos").mkdir()

            with self.assertRaises(LocalRuntimeError):
                build_cleanup_plan(root)


if __name__ == "__main__":
    unittest.main()
