"""Shared fail-closed guard for every write into a ResearchOS project root."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

from tools.runtime.project_handoff import check_write
from tools.runtime.terminal_roles import default_config_path


def add_project_write_guard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent-root", type=Path, help="ResearchOS Agent Core root used for handoff validation.")
    parser.add_argument("--corpus-root", type=Path, help="Shared corpus root used for handoff validation.")
    parser.add_argument("--role-config", type=Path, help="Private terminal role configuration.")


def assert_project_targets(project_root: Path, targets: Iterable[Path]) -> list[Path]:
    root = project_root.resolve()
    checked: list[Path] = []
    for target in targets:
        candidate = target if target.is_absolute() else root / target
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Project write target escapes project root: {target}") from exc
        checked.append(resolved)
    return checked


def require_project_write_access(
    project_root: Path,
    *,
    agent_root: Path | None = None,
    corpus_root: Path | None = None,
    role_config: Path | None = None,
    targets: Iterable[Path] = (),
) -> dict[str, object]:
    root = project_root.resolve()
    agent = (agent_root or Path(__file__).resolve().parents[2]).resolve()
    corpus = (corpus_root or (agent / "corpus")).resolve()
    config = (role_config or default_config_path()).resolve()
    checked = assert_project_targets(root, targets)
    result = check_write(root, agent, corpus, config)
    return {**result, "targets": [str(path) for path in checked]}


def require_from_args(args: argparse.Namespace, targets: Iterable[Path]) -> dict[str, object]:
    return require_project_write_access(
        Path(args.project_root),
        agent_root=getattr(args, "agent_root", None),
        corpus_root=getattr(args, "corpus_root", None),
        role_config=getattr(args, "role_config", None),
        targets=targets,
    )


def discover_project_root(targets: Iterable[Path]) -> Path | None:
    roots: set[Path] = set()
    for target in targets:
        candidate = target.resolve(strict=False)
        for parent in [candidate if candidate.is_dir() else candidate.parent, *candidate.parents]:
            if (parent / ".research" / "project_manifest.yml").is_file():
                roots.add(parent.resolve())
                break
    if len(roots) > 1:
        raise ValueError("One write operation cannot span multiple project roots")
    return next(iter(roots), None)


def require_discovered_project_write(
    targets: Iterable[Path],
    *,
    agent_root: Path | None = None,
    corpus_root: Path | None = None,
    role_config: Path | None = None,
) -> dict[str, object] | None:
    target_list = list(targets)
    root = discover_project_root(target_list)
    if root is None:
        return None
    return require_project_write_access(
        root,
        agent_root=agent_root,
        corpus_root=corpus_root,
        role_config=role_config,
        targets=target_list,
    )


def refuse_direct_shared_corpus_write(agent_root: Path, targets: Iterable[Path]) -> None:
    """Reserve shared corpus mutations for publish_corpus.py.

    Uses lexical absolute paths so Windows Junction targets remain identifiable
    by their stable ``corpus/`` entry path.
    """
    corpus = Path(os.path.abspath(agent_root / "corpus"))
    for target in targets:
        candidate = Path(os.path.abspath(target))
        try:
            candidate.relative_to(corpus)
        except ValueError:
            continue
        raise ValueError(
            f"Direct shared corpus write is forbidden: {target}. "
            "Write machine-local staging and publish through tools/runtime/publish_corpus.py."
        )
