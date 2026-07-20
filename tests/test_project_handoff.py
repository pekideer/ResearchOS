from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.runtime.project_handoff import (
    ProjectHandoffError,
    apply_plan,
    bootstrap_plan,
    check_write,
    transition_plan,
)


COMMIT = "a" * 40
SNAPSHOT = {
    "snapshot_id": "corpus-1234567890abcdef",
    "content_hash": "b" * 64,
}


def setup_project(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    research = project / ".research"
    research.mkdir(parents=True)
    (research / "project_manifest.yml").write_text("project_id: test-project\n", encoding="utf-8")
    agent = root / "agent"
    agent.mkdir()
    corpus = root / "corpus"
    corpus.mkdir()
    config = root / "terminal_role.json"
    config.write_text(json.dumps({
        "schema_version": 1,
        "terminal_name": "TEST-TERMINAL",
        "framework_role": "follower",
        "corpus_role": "reader",
        "zotero_role": "reader",
        "project_writer_mode": "transferable",
        "configured_at": "2026-01-01T00:00:00+00:00",
    }), encoding="utf-8")
    return project, agent, corpus, config


class ProjectHandoffTests(unittest.TestCase):
    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors", return_value=(COMMIT, SNAPSHOT))
    def test_bootstrap_apply_and_write_check(self, _anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            plan = bootstrap_plan(project, agent, corpus, config, "done", "next")
            result = apply_plan(project, plan)
            allowed = check_write(project, agent, corpus, config)
            self.assertEqual(result["status"], "active")
            self.assertTrue(allowed["allowed"])

    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors", return_value=(COMMIT, SNAPSHOT))
    def test_release_removes_active_writer(self, _anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            apply_plan(project, bootstrap_plan(project, agent, corpus, config, "done", "next"))
            plan = transition_plan("release", project, agent, corpus, config, "TARGET", "released", "claim on target")
            result = apply_plan(project, plan)
            self.assertEqual(result["status"], "ready_for_transfer")
            self.assertIsNone(result["active_writer_terminal"])

    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors", return_value=(COMMIT, SNAPSHOT))
    def test_claim_rejects_wrong_target(self, _anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            apply_plan(project, bootstrap_plan(project, agent, corpus, config, "done", "next"))
            apply_plan(project, transition_plan("release", project, agent, corpus, config, "OTHER", "released", "claim on other"))
            with self.assertRaises(ProjectHandoffError):
                transition_plan("claim", project, agent, corpus, config)

    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors", return_value=(COMMIT, SNAPSHOT))
    def test_stale_plan_is_rejected_before_write(self, _anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            apply_plan(project, bootstrap_plan(project, agent, corpus, config, "done", "next"))
            plan = transition_plan("release", project, agent, corpus, config, None, "released", "claim next")
            handoff = project / ".research" / "handoff.yml"
            live = json.loads(handoff.read_text(encoding="utf-8"))
            live["next_action"] = "changed"
            handoff.write_text(json.dumps(live), encoding="utf-8")
            with self.assertRaises(ProjectHandoffError):
                apply_plan(project, plan)

    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors")
    def test_claim_rejects_framework_or_corpus_drift(self, anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            anchors.return_value = (COMMIT, SNAPSHOT)
            apply_plan(project, bootstrap_plan(project, agent, corpus, config, "done", "next"))
            apply_plan(project, transition_plan("release", project, agent, corpus, config, "TEST-TERMINAL", "released", "claim"))
            anchors.return_value = ("c" * 40, {"snapshot_id": "corpus-drifted000000", "content_hash": "d" * 64})
            with self.assertRaises(ProjectHandoffError):
                transition_plan("claim", project, agent, corpus, config)

    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors")
    def test_check_write_rejects_stale_live_anchors(self, anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            anchors.return_value = (COMMIT, SNAPSHOT)
            apply_plan(project, bootstrap_plan(project, agent, corpus, config, "done", "next"))
            anchors.return_value = (COMMIT, {"snapshot_id": "corpus-drifted000000", "content_hash": "d" * 64})
            with self.assertRaises(ProjectHandoffError):
                check_write(project, agent, corpus, config)

    @patch("tools.runtime.project_handoff.socket.gethostname", return_value="TEST-TERMINAL")
    @patch("tools.runtime.project_handoff.live_anchors", return_value=(COMMIT, SNAPSHOT))
    def test_release_requires_current_progress_fields(self, _anchors, _hostname) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, agent, corpus, config = setup_project(Path(tmpdir))
            apply_plan(project, bootstrap_plan(project, agent, corpus, config, "done", "next"))
            with self.assertRaises(ProjectHandoffError):
                transition_plan("release", project, agent, corpus, config)


if __name__ == "__main__":
    unittest.main()
