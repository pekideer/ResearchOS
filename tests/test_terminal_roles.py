from __future__ import annotations

import unittest

from tools.runtime.terminal_roles import TerminalRoleError, check_action, status


def role_config(**updates):
    config = {
        "schema_version": 1,
        "terminal_name": "TEST-TERMINAL",
        "framework_role": "follower",
        "corpus_role": "reader",
        "zotero_role": "reader",
        "project_writer_mode": "transferable",
        "configured_at": "2026-01-01T00:00:00+00:00",
    }
    config.update(updates)
    return config


class TerminalRoleTests(unittest.TestCase):
    def test_follower_can_pull_but_cannot_push(self) -> None:
        config = role_config()
        self.assertTrue(check_action(config, "framework-pull", actual_terminal="TEST-TERMINAL")["allowed"])
        with self.assertRaises(TerminalRoleError):
            check_action(config, "framework-push", actual_terminal="TEST-TERMINAL")

    def test_maintainer_publisher_writer_actions_are_separate(self) -> None:
        config = role_config(framework_role="maintainer", corpus_role="publisher", zotero_role="writer")
        self.assertTrue(check_action(config, "framework-push", actual_terminal="TEST-TERMINAL")["allowed"])
        self.assertTrue(check_action(config, "corpus-write", actual_terminal="TEST-TERMINAL")["allowed"])
        zotero = check_action(config, "zotero-write", actual_terminal="TEST-TERMINAL")
        self.assertTrue(zotero["separate_user_approval_still_required"])

    def test_configuration_for_another_terminal_is_rejected(self) -> None:
        with self.assertRaises(TerminalRoleError):
            status(role_config(terminal_name="OTHER-TERMINAL"))

    def test_project_writer_mode_must_remain_transferable(self) -> None:
        with self.assertRaises(TerminalRoleError):
            check_action(
                role_config(project_writer_mode="fixed"),
                "framework-pull",
                actual_terminal="TEST-TERMINAL",
            )


if __name__ == "__main__":
    unittest.main()
