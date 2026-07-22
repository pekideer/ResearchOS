"""Initialize, audit, and safely clean the local ResearchOS runtime area."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
RUNTIME_KIND = "researchos_local_runtime"
RUNTIME_DIRNAME = ".researchos"
MARKER_NAME = "runtime.json"
PLAN_NAME = "cleanup-plan.json"
MANAGED_DIRS = ("tmp", "cache", "logs", "failed-runs", "audit-staging")
DEFAULT_POLICY = {
    "schema_version": 1,
    "retention_days": {
        "tmp": 7,
        "cache": 30,
        "logs": 14,
        "failed-runs": 30,
        "audit-staging": 30,
    },
    "protected_scopes": {
        "failed-runs": {"marker": "cleanup-state.json", "required_true": ["issue_closed"]},
        "audit-staging": {
            "marker": "cleanup-state.json",
            "required_true": ["task_closed", "promoted"],
        },
    },
}


class LocalRuntimeError(RuntimeError):
    """Raised when a local runtime safety contract is violated."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def root_fingerprint(root: Path) -> str:
    normalized = os.path.normcase(str(root.resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalRuntimeError(f"Cannot read valid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise LocalRuntimeError(f"JSON root must be an object: {path.name}")
    return value


def validate_researchos_root(root: Path) -> Path:
    resolved = root.resolve()
    if not (resolved / "AGENTS.md").is_file() or not (resolved / ".gitignore").is_file():
        raise LocalRuntimeError("Target is not a ResearchOS Agent Core root")
    return resolved


def runtime_path(root: Path) -> Path:
    return root / RUNTIME_DIRNAME


def is_linklike(path: Path) -> bool:
    """Treat both symbolic links and Windows junctions as external boundaries."""
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise LocalRuntimeError("Unsupported local runtime policy schema")
    retention = policy.get("retention_days")
    if not isinstance(retention, dict) or set(retention) != set(MANAGED_DIRS):
        raise LocalRuntimeError("Retention policy must cover every managed directory")
    for name, days in retention.items():
        if not isinstance(days, int) or isinstance(days, bool) or days < 1:
            raise LocalRuntimeError(f"Invalid retention days for {name}")
    protected = policy.get("protected_scopes")
    if not isinstance(protected, dict) or set(protected) != {"failed-runs", "audit-staging"}:
        raise LocalRuntimeError("Protected scope policy is incomplete")
    return policy


def read_policy(path: Path | None) -> dict[str, Any]:
    if path is None:
        return json.loads(json.dumps(DEFAULT_POLICY))
    return validate_policy(load_json(path.resolve()))


def validate_marker(root: Path) -> dict[str, Any]:
    marker_path = runtime_path(root) / MARKER_NAME
    marker = load_json(marker_path)
    if (
        marker.get("schema_version") != SCHEMA_VERSION
        or marker.get("kind") != RUNTIME_KIND
        or marker.get("root_fingerprint") != root_fingerprint(root)
    ):
        raise LocalRuntimeError("Local runtime marker does not match this Agent Core")
    return marker


def initialize(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    root = validate_researchos_root(root)
    runtime = runtime_path(root)
    if runtime.exists() and (is_linklike(runtime) or not runtime.is_dir()):
        raise LocalRuntimeError(".researchos must be a real local directory")
    runtime.mkdir(exist_ok=True)
    created: list[str] = []
    for name in MANAGED_DIRS:
        target = runtime / name
        if target.exists() and (is_linklike(target) or not target.is_dir()):
            raise LocalRuntimeError(f"Managed runtime path is not a real directory: {name}")
        if not target.exists():
            target.mkdir()
            created.append(name)
    marker_path = runtime / MARKER_NAME
    if marker_path.exists():
        marker = validate_marker(root)
    else:
        marker = {
            "schema_version": SCHEMA_VERSION,
            "kind": RUNTIME_KIND,
            "root_fingerprint": root_fingerprint(root),
            "terminal_name": socket.gethostname(),
            "created_at": iso_utc(utc_now()),
            "policy": policy,
        }
        write_json_atomic(marker_path, marker)
        created.append(MARKER_NAME)
    return {
        "initialized": True,
        "runtime": RUNTIME_DIRNAME,
        "created": created,
        "marker_valid": True,
    }


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def has_symlink_component(path: Path, stop: Path) -> bool:
    current = path
    while current != stop:
        if is_linklike(current):
            return True
        current = current.parent
    return is_linklike(stop)


def iter_regular_files(directory: Path) -> Iterable[Path]:
    if not directory.exists() or is_linklike(directory):
        return
    for current, dirnames, filenames in os.walk(directory, followlinks=False):
        current_path = Path(current)
        dirnames[:] = [name for name in dirnames if not is_linklike(current_path / name)]
        for name in filenames:
            path = current_path / name
            if not is_linklike(path) and path.is_file():
                yield path


def parse_closed_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def candidate_record(path: Path, runtime: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.relative_to(runtime).as_posix(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def build_cleanup_plan(root: Path, now: datetime | None = None) -> dict[str, Any]:
    root = validate_researchos_root(root)
    marker = validate_marker(root)
    policy = validate_policy(marker.get("policy") or {})
    runtime = runtime_path(root)
    current_time = (now or utc_now()).astimezone(timezone.utc)
    candidates: list[dict[str, Any]] = []
    protected: list[dict[str, str]] = []

    for name in ("tmp", "cache", "logs"):
        cutoff = current_time - timedelta(days=policy["retention_days"][name])
        for path in iter_regular_files(runtime / name):
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified <= cutoff:
                candidates.append(candidate_record(path, runtime))

    for name in ("failed-runs", "audit-staging"):
        base = runtime / name
        scope_policy = policy["protected_scopes"][name]
        if not base.exists() or is_linklike(base):
            continue
        for scope in sorted(base.iterdir(), key=lambda item: item.name):
            if not scope.is_dir() or is_linklike(scope):
                protected.append({"path": scope.relative_to(runtime).as_posix(), "reason": "invalid_scope"})
                continue
            state_path = scope / scope_policy["marker"]
            if not state_path.is_file() or is_linklike(state_path):
                protected.append({"path": scope.relative_to(runtime).as_posix(), "reason": "closure_marker_missing"})
                continue
            try:
                state = load_json(state_path)
            except LocalRuntimeError:
                protected.append({"path": scope.relative_to(runtime).as_posix(), "reason": "closure_marker_invalid"})
                continue
            if not all(state.get(field) is True for field in scope_policy["required_true"]):
                protected.append({"path": scope.relative_to(runtime).as_posix(), "reason": "scope_not_closed_or_promoted"})
                continue
            closed_at = parse_closed_at(state.get("closed_at"))
            if closed_at is None:
                protected.append({"path": scope.relative_to(runtime).as_posix(), "reason": "closed_at_invalid"})
                continue
            if current_time - closed_at < timedelta(days=policy["retention_days"][name]):
                protected.append({"path": scope.relative_to(runtime).as_posix(), "reason": "retention_not_elapsed"})
                continue
            candidates.extend(candidate_record(path, runtime) for path in iter_regular_files(scope))

    candidates.sort(key=lambda row: row["path"])
    managed_names = set(MANAGED_DIRS) | {MARKER_NAME, PLAN_NAME}
    unmanaged = sorted(item.name for item in runtime.iterdir() if item.name not in managed_names)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "researchos_local_runtime_cleanup_plan",
        "created_at": iso_utc(current_time),
        "root_fingerprint": root_fingerprint(root),
        "policy": policy,
        "candidate_count": len(candidates),
        "candidate_bytes": sum(row["size"] for row in candidates),
        "candidates": candidates,
        "protected_scopes": protected,
        "unmanaged_top_level": unmanaged,
        "apply_requires_explicit_plan": True,
    }


def audit(root: Path) -> dict[str, Any]:
    root = validate_researchos_root(root)
    marker = validate_marker(root)
    runtime = runtime_path(root)
    plan = build_cleanup_plan(root)
    directories: dict[str, dict[str, Any]] = {}
    for name in MANAGED_DIRS:
        target = runtime / name
        files = list(iter_regular_files(target))
        directories[name] = {
            "exists": target.is_dir() and not is_linklike(target),
            "file_count": len(files),
            "bytes": sum(path.stat().st_size for path in files),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "researchos_local_runtime_audit",
        "marker_valid": marker.get("kind") == RUNTIME_KIND,
        "directories": directories,
        "cleanup_candidate_count": plan["candidate_count"],
        "cleanup_candidate_bytes": plan["candidate_bytes"],
        "protected_scope_count": len(plan["protected_scopes"]),
        "unmanaged_top_level": plan["unmanaged_top_level"],
    }


def validate_candidate(root: Path, runtime: Path, row: dict[str, Any]) -> Path:
    relative = Path(str(row.get("path") or ""))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise LocalRuntimeError("Cleanup plan contains an unsafe relative path")
    if relative.parts[0] not in MANAGED_DIRS:
        raise LocalRuntimeError("Cleanup plan targets an unmanaged directory")
    path = runtime / relative
    resolved = path.resolve(strict=True)
    if not is_within(resolved, runtime.resolve()) or has_symlink_component(path, runtime):
        raise LocalRuntimeError("Cleanup plan crosses the local runtime boundary")
    stat = path.stat()
    if not path.is_file() or is_linklike(path):
        raise LocalRuntimeError("Cleanup target is not a regular file")
    if stat.st_size != row.get("size") or stat.st_mtime_ns != row.get("mtime_ns"):
        raise LocalRuntimeError("Cleanup target changed after plan generation")
    return path


def apply_cleanup_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    root = validate_researchos_root(root)
    validate_marker(root)
    runtime = runtime_path(root)
    plan_path = plan_path.resolve(strict=True)
    if not is_within(plan_path, runtime.resolve()) or is_linklike(plan_path):
        raise LocalRuntimeError("Cleanup plan must be a real file inside .researchos")
    plan = load_json(plan_path)
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("kind") != "researchos_local_runtime_cleanup_plan"
        or plan.get("root_fingerprint") != root_fingerprint(root)
    ):
        raise LocalRuntimeError("Cleanup plan does not belong to this Agent Core")
    rows = plan.get("candidates")
    if not isinstance(rows, list):
        raise LocalRuntimeError("Cleanup plan candidates are invalid")
    targets = [validate_candidate(root, runtime, row) for row in rows]
    deleted_bytes = sum(path.stat().st_size for path in targets)
    for path in targets:
        path.unlink()
    for name in MANAGED_DIRS:
        base = runtime / name
        for current, _dirnames, _filenames in os.walk(base, topdown=False, followlinks=False):
            current_path = Path(current)
            if current_path != base and not is_linklike(current_path):
                try:
                    current_path.rmdir()
                except OSError:
                    pass
    return {
        "applied": True,
        "deleted_count": len(targets),
        "deleted_bytes": deleted_bytes,
        "plan": plan_path.relative_to(runtime).as_posix(),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="ResearchOS Agent Core root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="Create and mark the local runtime")
    init_parser.add_argument("--policy", help="Optional JSON policy")
    subparsers.add_parser("audit", help="Audit the local runtime without deleting")
    cleanup_parser = subparsers.add_parser("cleanup", help="Create or explicitly apply a cleanup plan")
    cleanup_parser.add_argument("--output", help="Plan output path; defaults inside .researchos")
    cleanup_parser.add_argument("--apply", metavar="PLAN", help="Explicitly apply an existing cleanup plan")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "init":
            result = initialize(root, read_policy(Path(args.policy) if args.policy else None))
        elif args.command == "audit":
            result = audit(root)
        elif args.apply:
            result = apply_cleanup_plan(root, Path(args.apply))
        else:
            resolved_root = validate_researchos_root(root)
            result = build_cleanup_plan(resolved_root)
            requested_output = Path(args.output) if args.output else Path(PLAN_NAME)
            output = requested_output.resolve() if requested_output.is_absolute() else (runtime_path(resolved_root) / requested_output).resolve()
            if not is_within(output, runtime_path(resolved_root).resolve()):
                raise LocalRuntimeError("Cleanup plan output must stay inside .researchos")
            write_json_atomic(output, result)
            result = {**result, "plan_written": output.relative_to(runtime_path(resolved_root)).as_posix()}
    except LocalRuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
