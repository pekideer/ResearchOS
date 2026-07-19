"""Configure and verify per-terminal ResearchOS write roles."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CONFIG_NAME = "terminal_role.json"
VALID_FRAMEWORK_ROLES = {"maintainer", "follower"}
VALID_CORPUS_ROLES = {"publisher", "reader"}
VALID_ZOTERO_ROLES = {"writer", "reader"}
ACTION_REQUIREMENTS = {
    "framework-pull": None,
    "framework-write": ("framework_role", "maintainer"),
    "framework-push": ("framework_role", "maintainer"),
    "corpus-write": ("corpus_role", "publisher"),
    "zotero-write": ("zotero_role", "writer"),
}


class TerminalRoleError(RuntimeError):
    """Raised when terminal identity or role configuration is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_config_path() -> Path:
    return Path.home() / ".researchos" / CONFIG_NAME


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise TerminalRoleError("Terminal role configuration is missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise TerminalRoleError("Terminal role configuration is invalid") from exc
    if not isinstance(value, dict):
        raise TerminalRoleError("Terminal role configuration must be a JSON object")
    validate_config(value)
    return value


def validate_config(config: dict[str, Any], actual_terminal: str | None = None) -> None:
    if config.get("schema_version") != SCHEMA_VERSION:
        raise TerminalRoleError("Unsupported terminal role schema")
    terminal_name = str(config.get("terminal_name") or "").strip()
    if not terminal_name:
        raise TerminalRoleError("terminal_name is required")
    if config.get("framework_role") not in VALID_FRAMEWORK_ROLES:
        raise TerminalRoleError("framework_role is invalid")
    if config.get("corpus_role") not in VALID_CORPUS_ROLES:
        raise TerminalRoleError("corpus_role is invalid")
    if config.get("zotero_role") not in VALID_ZOTERO_ROLES:
        raise TerminalRoleError("zotero_role is invalid")
    if config.get("project_writer_mode") != "transferable":
        raise TerminalRoleError("project_writer_mode must be transferable")
    observed = actual_terminal or socket.gethostname()
    if terminal_name.casefold() != observed.casefold():
        raise TerminalRoleError("Terminal role configuration belongs to another terminal")


def configure(
    path: Path,
    terminal_name: str,
    framework_role: str,
    corpus_role: str,
    zotero_role: str,
) -> dict[str, Any]:
    config = {
        "schema_version": SCHEMA_VERSION,
        "terminal_name": terminal_name,
        "framework_role": framework_role,
        "corpus_role": corpus_role,
        "zotero_role": zotero_role,
        "project_writer_mode": "transferable",
        "configured_at": utc_now(),
    }
    validate_config(config)
    if path.exists():
        existing = load_config(path)
        stable_fields = ("terminal_name", "framework_role", "corpus_role", "zotero_role", "project_writer_mode")
        if any(existing.get(field) != config.get(field) for field in stable_fields):
            raise TerminalRoleError("Refusing to overwrite a different terminal role configuration")
        return existing
    write_json_atomic(path, config)
    return config


def check_action(config: dict[str, Any], action: str, actual_terminal: str | None = None) -> dict[str, Any]:
    validate_config(config, actual_terminal=actual_terminal)
    requirement = ACTION_REQUIREMENTS[action]
    allowed = requirement is None or config.get(requirement[0]) == requirement[1]
    result = {
        "action": action,
        "allowed": allowed,
        "terminal_name": config["terminal_name"],
        "framework_role": config["framework_role"],
        "corpus_role": config["corpus_role"],
        "zotero_role": config["zotero_role"],
    }
    if action == "zotero-write":
        result["separate_user_approval_still_required"] = True
    if not allowed:
        required = f"{requirement[0]}={requirement[1]}" if requirement else "configured terminal"
        raise TerminalRoleError(f"Action denied; required role: {required}")
    return result


def status(config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    return {
        "configured": True,
        "terminal_name": config["terminal_name"],
        "framework_role": config["framework_role"],
        "corpus_role": config["corpus_role"],
        "zotero_role": config["zotero_role"],
        "project_writer_mode": config["project_writer_mode"],
    }


def validate_researchos_root(root: Path) -> Path:
    resolved = root.resolve()
    if not (resolved / "AGENTS.md").is_file() or not (resolved / ".git").exists():
        raise TerminalRoleError("Target is not a ResearchOS Agent Core Git root")
    return resolved


def install_git_guard(root: Path) -> dict[str, Any]:
    root = validate_researchos_root(root)
    hook = root / ".githooks" / "pre-push"
    if not hook.is_file():
        raise TerminalRoleError("Tracked pre-push guard is missing")
    completed = subprocess.run(
        ["git", "config", "--local", "core.hooksPath", ".githooks"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise TerminalRoleError("Could not install the local Git push guard")
    return {"installed": True, "core_hooks_path": ".githooks"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Private terminal role JSON path")
    parser.add_argument("--root", default=".", help="ResearchOS Agent Core root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure_parser = subparsers.add_parser("configure")
    configure_parser.add_argument("--terminal-name", required=True)
    configure_parser.add_argument("--framework-role", required=True, choices=sorted(VALID_FRAMEWORK_ROLES))
    configure_parser.add_argument("--corpus-role", required=True, choices=sorted(VALID_CORPUS_ROLES))
    configure_parser.add_argument("--zotero-role", required=True, choices=sorted(VALID_ZOTERO_ROLES))

    subparsers.add_parser("status")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--action", required=True, choices=sorted(ACTION_REQUIREMENTS))
    subparsers.add_parser("install-git-guard")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).resolve() if args.config else default_config_path()
    try:
        if args.command == "configure":
            result = configure(
                config_path,
                args.terminal_name,
                args.framework_role,
                args.corpus_role,
                args.zotero_role,
            )
            result = status(result)
        elif args.command == "status":
            result = status(load_config(config_path))
        elif args.command == "check":
            result = check_action(load_config(config_path), args.action)
        else:
            check_action(load_config(config_path), "framework-write")
            result = install_git_guard(Path(args.root))
    except TerminalRoleError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
