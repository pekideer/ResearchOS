"""Plan, apply, and verify transferable project write ownership."""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.runtime.corpus_snapshot import compute_snapshot
from tools.runtime.terminal_roles import default_config_path, load_config, validate_config


SCHEMA_VERSION = 1
HANDOFF_NAME = "handoff.yml"
VALID_STATUSES = {"active", "ready_for_transfer"}


class ProjectHandoffError(RuntimeError):
    """Raised when project ownership cannot be changed safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def project_identity(project_root: Path) -> tuple[Path, str]:
    root = project_root.resolve()
    manifest = root / ".research" / "project_manifest.yml"
    if not manifest.is_file():
        raise ProjectHandoffError("Project manifest is missing")
    match = re.search(r"(?m)^project_id:\s*[\"']?([^\"'\s]+)", manifest.read_text(encoding="utf-8-sig"))
    if not match:
        raise ProjectHandoffError("project_id is missing from project manifest")
    return root, match.group(1)


def current_framework_commit(agent_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=agent_root.resolve(),
        check=False,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ProjectHandoffError("Could not determine current Agent Core commit")
    return commit


def load_handoff(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ProjectHandoffError("Project handoff file is missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectHandoffError("Project handoff file is invalid") from exc
    if not isinstance(value, dict):
        raise ProjectHandoffError("Project handoff must be a JSON-compatible YAML object")
    validate_handoff(value)
    return value


def validate_handoff(value: dict[str, Any]) -> None:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ProjectHandoffError("Unsupported project handoff schema")
    if not str(value.get("project_id") or ""):
        raise ProjectHandoffError("handoff project_id is missing")
    if not isinstance(value.get("state_revision"), int) or value["state_revision"] < 1:
        raise ProjectHandoffError("handoff state_revision is invalid")
    if value.get("status") not in VALID_STATUSES:
        raise ProjectHandoffError("handoff status is invalid")
    active_writer = value.get("active_writer_terminal")
    if value["status"] == "active" and not str(active_writer or ""):
        raise ProjectHandoffError("active handoff requires an active writer")
    if value["status"] == "ready_for_transfer" and active_writer is not None:
        raise ProjectHandoffError("released handoff cannot retain an active writer")
    if not re.fullmatch(r"[0-9a-f]{40}", str(value.get("framework_commit") or "")):
        raise ProjectHandoffError("handoff framework_commit is invalid")
    if not str(value.get("corpus_snapshot_id") or "").startswith("corpus-"):
        raise ProjectHandoffError("handoff corpus_snapshot_id is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(value.get("corpus_content_hash") or "")):
        raise ProjectHandoffError("handoff corpus_content_hash is invalid")
    if not str(value.get("last_completed") or "").strip():
        raise ProjectHandoffError("handoff last_completed is missing")
    if not str(value.get("next_action") or "").strip():
        raise ProjectHandoffError("handoff next_action is missing")


def terminal_config(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    validate_config(config, actual_terminal=socket.gethostname())
    if config.get("project_writer_mode") != "transferable":
        raise ProjectHandoffError("Terminal does not permit transferable project ownership")
    return config


def live_anchors(agent_root: Path, corpus_root: Path) -> tuple[str, dict[str, object]]:
    return current_framework_commit(agent_root), compute_snapshot(corpus_root)


def anchor_mismatches(
    handoff: dict[str, Any],
    framework_commit: str,
    corpus_snapshot: dict[str, object],
) -> list[str]:
    mismatches: list[str] = []
    if handoff["framework_commit"] != framework_commit:
        mismatches.append("framework_commit")
    if handoff["corpus_snapshot_id"] != corpus_snapshot.get("snapshot_id"):
        mismatches.append("corpus_snapshot_id")
    if handoff["corpus_content_hash"] != corpus_snapshot.get("content_hash"):
        mismatches.append("corpus_content_hash")
    return mismatches


def bootstrap_plan(
    project_root: Path,
    agent_root: Path,
    corpus_root: Path,
    config_path: Path,
    last_completed: str,
    next_action: str,
) -> dict[str, Any]:
    root, project_id = project_identity(project_root)
    handoff_path = root / ".research" / HANDOFF_NAME
    if handoff_path.exists():
        raise ProjectHandoffError("Project handoff already exists; bootstrap is not allowed")
    config = terminal_config(config_path)
    commit, corpus = live_anchors(agent_root, corpus_root)
    desired = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "state_revision": 1,
        "status": "active",
        "active_writer_terminal": config["terminal_name"],
        "released_by_terminal": None,
        "target_terminal": None,
        "framework_commit": commit,
        "corpus_snapshot_id": corpus["snapshot_id"],
        "corpus_content_hash": corpus["content_hash"],
        "last_completed": last_completed,
        "next_action": next_action,
        "updated_at": utc_now(),
    }
    validate_handoff(desired)
    return {"action": "bootstrap", "project_id": project_id, "desired": desired, "apply_required": True}


def transition_plan(
    action: str,
    project_root: Path,
    agent_root: Path,
    corpus_root: Path,
    config_path: Path,
    target_terminal: str | None = None,
    last_completed: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    root, project_id = project_identity(project_root)
    handoff_path = root / ".research" / HANDOFF_NAME
    current = load_handoff(handoff_path)
    if current["project_id"] != project_id:
        raise ProjectHandoffError("Handoff project identity does not match manifest")
    config = terminal_config(config_path)
    terminal = config["terminal_name"]
    commit, corpus = live_anchors(agent_root, corpus_root)
    if action == "release":
        if current["status"] != "active" or str(current["active_writer_terminal"]).casefold() != terminal.casefold():
            raise ProjectHandoffError("Only the active project writer can release this project")
        if not str(last_completed or "").strip() or not str(next_action or "").strip():
            raise ProjectHandoffError("Release requires last_completed and next_action")
        desired = dict(current)
        desired["state_revision"] += 1
        desired["framework_commit"] = commit
        desired["corpus_snapshot_id"] = corpus["snapshot_id"]
        desired["corpus_content_hash"] = corpus["content_hash"]
        desired["last_completed"] = str(last_completed).strip()
        desired["next_action"] = str(next_action).strip()
        desired["updated_at"] = utc_now()
        desired["status"] = "ready_for_transfer"
        desired["active_writer_terminal"] = None
        desired["released_by_terminal"] = terminal
        desired["target_terminal"] = target_terminal
    elif action == "claim":
        if current["status"] != "ready_for_transfer":
            raise ProjectHandoffError("Project is not ready for transfer")
        target = str(current.get("target_terminal") or "")
        if target and target.casefold() != terminal.casefold():
            raise ProjectHandoffError("Project was released to another terminal")
        mismatches = anchor_mismatches(current, commit, corpus)
        if mismatches:
            raise ProjectHandoffError(
                "Current Agent Core or shared corpus does not match the released handoff: "
                + ", ".join(mismatches)
            )
        desired = dict(current)
        desired["state_revision"] += 1
        desired["updated_at"] = utc_now()
        desired["status"] = "active"
        desired["active_writer_terminal"] = terminal
        desired["target_terminal"] = None
    else:
        raise ProjectHandoffError("Unsupported project handoff action")
    validate_handoff(desired)
    return {"action": action, "project_id": project_id, "before": current, "desired": desired, "apply_required": True}


def apply_plan(project_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    root, project_id = project_identity(project_root)
    if plan.get("project_id") != project_id:
        raise ProjectHandoffError("Plan does not belong to this project")
    handoff_path = root / ".research" / HANDOFF_NAME
    action = plan.get("action")
    if action == "bootstrap":
        if handoff_path.exists():
            raise ProjectHandoffError("Live state changed: handoff now exists")
    else:
        current = load_handoff(handoff_path)
        if current != plan.get("before"):
            raise ProjectHandoffError("Live handoff changed after plan generation")
    desired = plan.get("desired")
    if not isinstance(desired, dict):
        raise ProjectHandoffError("Plan desired state is invalid")
    validate_handoff(desired)
    write_json_atomic(handoff_path, desired)
    return {
        "applied": True,
        "action": action,
        "project_id": project_id,
        "state_revision": desired["state_revision"],
        "status": desired["status"],
        "active_writer_terminal": desired["active_writer_terminal"],
    }


def check_write(
    project_root: Path,
    agent_root: Path,
    corpus_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    root, project_id = project_identity(project_root)
    handoff = load_handoff(root / ".research" / HANDOFF_NAME)
    config = terminal_config(config_path)
    allowed = (
        handoff["project_id"] == project_id
        and handoff["status"] == "active"
        and str(handoff["active_writer_terminal"]).casefold() == str(config["terminal_name"]).casefold()
    )
    if not allowed:
        raise ProjectHandoffError("Current terminal does not hold project write ownership")
    commit, corpus = live_anchors(agent_root, corpus_root)
    mismatches = anchor_mismatches(handoff, commit, corpus)
    if mismatches:
        raise ProjectHandoffError(
            "Project write ownership is stale relative to the current Agent Core or shared corpus: "
            + ", ".join(mismatches)
        )
    return {
        "allowed": True,
        "project_id": project_id,
        "terminal_name": config["terminal_name"],
        "state_revision": handoff["state_revision"],
        "framework_commit": commit,
        "corpus_snapshot_id": corpus["snapshot_id"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--agent-root", default=".")
    parser.add_argument("--corpus-root", default="corpus")
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="command", required=True)
    bootstrap = subparsers.add_parser("bootstrap")
    bootstrap.add_argument("--last-completed", required=True)
    bootstrap.add_argument("--next-action", required=True)
    bootstrap.add_argument("--apply", action="store_true")
    release = subparsers.add_parser("release")
    release.add_argument("--target-terminal")
    release.add_argument("--last-completed", required=True)
    release.add_argument("--next-action", required=True)
    release.add_argument("--apply", action="store_true")
    claim = subparsers.add_parser("claim")
    claim.add_argument("--apply", action="store_true")
    subparsers.add_parser("status")
    subparsers.add_parser("check-write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root)
    agent_root = Path(args.agent_root)
    corpus_root = Path(args.corpus_root)
    config_path = Path(args.config).resolve() if args.config else default_config_path()
    try:
        if args.command == "bootstrap":
            plan = bootstrap_plan(
                project_root,
                agent_root,
                corpus_root,
                config_path,
                args.last_completed,
                args.next_action,
            )
            result = apply_plan(project_root, plan) if args.apply else plan
        elif args.command in {"release", "claim"}:
            plan = transition_plan(
                args.command,
                project_root,
                agent_root,
                corpus_root,
                config_path,
                getattr(args, "target_terminal", None),
                getattr(args, "last_completed", None),
                getattr(args, "next_action", None),
            )
            result = apply_plan(project_root, plan) if args.apply else plan
        elif args.command == "check-write":
            result = check_write(project_root, agent_root, corpus_root, config_path)
        else:
            root, project_id = project_identity(project_root)
            result = load_handoff(root / ".research" / HANDOFF_NAME)
            if result["project_id"] != project_id:
                raise ProjectHandoffError("Handoff project identity does not match manifest")
    except (ProjectHandoffError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
