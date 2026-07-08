"""Resolve machine-specific ResearchOS paths.

The ResearchOS folder may live under different OneDrive parent paths on
different machines. This module keeps scripts from hard-coding those paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_ENV_VAR = "RESEARCHOS_MACHINE_CONFIG"
HOME_CONFIG = Path.home() / ".researchos" / "machine_config.json"
LOCAL_CONFIG_RELATIVE = Path(".local") / "machine_config.json"
CONFIGS_CONFIG_RELATIVE = Path("configs") / "machine_config.json"


def find_researchos_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (
            (candidate / "AGENTS.md").exists()
            and (candidate / ".agents" / "skills").is_dir()
            and (candidate / "templates").is_dir()
        ):
            return candidate

    raise FileNotFoundError(
        "无法定位 ResearchOS 根目录。请在 00_ResearchOS 内运行脚本，或设置 "
        f"{CONFIG_ENV_VAR} 指向 machine_config.json。"
    )


def config_candidates(researchos_root: Path) -> list[Path]:
    candidates: list[Path] = []
    env_path = os.getenv(CONFIG_ENV_VAR)
    if env_path:
        candidates.append(Path(env_path).expanduser())

    # Prefer a home-directory config because it is machine-local and will not
    # move with OneDrive.
    candidates.append(HOME_CONFIG)
    candidates.append(researchos_root / LOCAL_CONFIG_RELATIVE)
    candidates.append(researchos_root / CONFIGS_CONFIG_RELATIVE)
    return candidates


def load_machine_config(researchos_root: Path) -> tuple[dict[str, Any], Path | None]:
    for path in config_candidates(researchos_root):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"machine config 必须是 JSON object：{path}")
        return data, path
    return {}, None


def get_projects_root(researchos_root: Path, config: dict[str, Any]) -> tuple[Path, str]:
    configured = config.get("projects_root")
    if configured:
        return Path(str(configured)).expanduser(), "machine_config.projects_root"

    return researchos_root.parent, "default: researchos_root.parent"


def resolve_project_root(
    *,
    explicit_root: str | None,
    project_name: str | None,
    start: Path | None = None,
) -> tuple[Path, str, Path, Path | None]:
    researchos_root = find_researchos_root(start)

    if explicit_root and project_name:
        raise ValueError("请只传入 --root 或 --project-name 其中一个。")

    if explicit_root:
        return Path(explicit_root).expanduser(), "--root", researchos_root, None

    if not project_name:
        raise ValueError("必须传入 --root 或 --project-name。")

    config, config_path = load_machine_config(researchos_root)
    projects_root, source = get_projects_root(researchos_root, config)
    return projects_root / project_name, source, researchos_root, config_path
