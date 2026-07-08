"""Create numbered ResearchOS output folders under a user-specified project root.

This script only creates directories. It does not move, copy, rename, or delete
files, and it does not write to Zotero.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


STANDARD_DIRS = [
    ".research",
    "annotations",
    "annotations/processed",
    "annotations/.internal",
    "01-reading-cards",
    "01-reading-cards/priority-cards",
    "02-literature-matrix",
    "02-literature-matrix/.internal",
    "02-literature-matrix/prisma",
    "02-literature-matrix/reading-summary-tables",
    "03-manuscript",
    "04-reviewer-response",
    "05-ai-code-workspace",
    "05-ai-code-workspace/configs",
    "05-ai-code-workspace/data/raw",
    "05-ai-code-workspace/data/processed",
    "05-ai-code-workspace/notebooks",
    "05-ai-code-workspace/outputs/figures",
    "05-ai-code-workspace/outputs/tables",
    "05-ai-code-workspace/src",
    "05-ai-code-workspace/tests",
    "05-ai-code-workspace/logs",
]


def load_path_resolver() -> Any:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        resolver_path = candidate / ".agents" / "utils" / "path_resolver.py"
        if resolver_path.exists():
            spec = importlib.util.spec_from_file_location("researchos_path_resolver", resolver_path)
            if spec is None or spec.loader is None:
                break
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("无法加载 .agents/utils/path_resolver.py。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create numbered ResearchOS output folders in a project directory."
    )
    parser.add_argument(
        "--root",
        help="Research project root directory where output folders should be created.",
    )
    parser.add_argument(
        "--project-name",
        help=(
            "Project directory name under projects_root. This is preferred for "
            "cross-device use because projects_root can come from machine config."
        ),
    )
    parser.add_argument(
        "--create-root",
        action="store_true",
        help="Create the root directory if it does not already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview directories without creating them.",
    )
    parser.add_argument(
        "--topic-direction",
        action="append",
        default=[],
        help=(
            "Project topic direction, repeatable. Use CODE=LABEL, for example "
            "--topic-direction T1=研究方向一. If CODE is omitted, T1/T2/... is assigned."
        ),
    )
    return parser


def parse_topic_directions(values: list[str]) -> list[dict[str, str]]:
    directions: list[dict[str, str]] = []
    for index, value in enumerate(values, start=1):
        raw = repair_mojibake(value.strip())
        if not raw:
            continue
        if "=" in raw:
            code, label = raw.split("=", 1)
            code = code.strip() or f"T{index}"
            label = label.strip()
        else:
            code = f"T{index}"
            label = raw
        if not label:
            continue
        full_label = label if label.startswith(f"{code}_") else f"{code}_{label}"
        directions.append(
            {
                "code": code,
                "label": full_label,
                "display": full_label.split("_", 1)[1] if "_" in full_label else full_label,
                "relevance_default": "待判定",
            }
        )
    return directions


def repair_mojibake(value: str) -> str:
    try:
        repaired = value.encode("gbk").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def write_text_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return True


def project_manifest_text(root: Path, directions: list[dict[str, str]]) -> str:
    topic_lines: list[str] = ["topic_directions:"]
    if directions:
        for direction in directions:
            topic_lines.extend(
                [
                    f"  - code: {direction['code']}",
                    f"    label: \"{direction['label']}\"",
                    f"    display: \"{direction['display']}\"",
                    f"    relevance_default: \"{direction['relevance_default']}\"",
                ]
            )
    else:
        topic_lines.extend(
            [
                "  - code: T1",
                "    label: \"T1_方向名称\"",
                "    display: \"方向名称\"",
                "    relevance_default: \"待判定\"",
            ]
        )
    topic_block = "\n".join(topic_lines)
    return f"""
project:
  project_name: "{root.name}"
  short_name: "{root.name}"
  stage: "initialized"
  owner: "?"
  last_updated: "?"

research_focus:
  background: "?"
  research_questions: []
  hypotheses: []
  gap_ids: []

{topic_block}

sources:
  literature_matrix: []
  reading_cards: []
  zotero_item_links: []
  datasets: []
  manuscripts: []

outputs:
  reading_cards_dir: "01-reading-cards/"
  annotations_dir: "annotations/"
  literature_matrix_dir: "02-literature-matrix/"
  prisma_dir: "02-literature-matrix/prisma/"
  manuscript_dir: "03-manuscript/"
  reviewer_response_dir: "04-reviewer-response/"
  code_workspace_dir: "05-ai-code-workspace/"

status:
  current_stage: "initialized"
  last_completed_step: "project workspace created"
  pending_user_approval: []
  blocked_reasons: []
  next_actions: []

safety:
  api_keys_stored_here: false
  zotero_write_allowed: false
  notes: "不要在 .research/ 中保存 API key、Zotero 数据库或 PDF 文件；.research/fulltext_cache/ 可保存项目内部文本缓存，kit export 必须剔除。"
"""


def reading_cards_readme_text() -> str:
    return """
# Reading Cards

本目录保存课题读书卡。

新读书卡统一使用 ResearchOS 全局模板：

`00_ResearchOS/templates/paper-reading-card.md`

治理规则见：

`00_ResearchOS/RUNBOOKS/reading-card-governance.md`
"""


def annotation_inbox_text() -> str:
    return """
# Human Annotation Inbox

这个文件用于记录你阅读本课题文档时的想法、意见、疑问和修改建议。它只保留待处理或需确认条目；已处理条目会进入 `processed/`。

使用原则：

- 优先把本课题的批注写在这里；跨项目或暂时不知道归属时才写 ResearchOS 全局 `.researchos/human-annotation-inbox/inbox.md`。
- `target_document` 尽量写相对课题根目录的路径，例如 `01-reading-cards/xxx.md`、`02-literature-matrix/xxx.md`、`03-manuscript/xxx.md`。
- 不确定的事实、数据、文献结论直接写“待核查”。

## 待处理条目

在此标题下方追加新的 `## ANNO-...` 条目。
"""


def annotation_review_log_text() -> str:
    return """
# Human Annotation Review Log

本文件由 agent 在处理本课题 `annotations/inbox.md` 后追加记录。保留既有记录，便于回溯处理过程。
"""


def scaffold_files(root: Path, directions: list[dict[str, str]], dry_run: bool) -> list[Path]:
    files = {
        root / ".research" / "project_manifest.yml": project_manifest_text(root, directions),
        root / "annotations" / "inbox.md": annotation_inbox_text(),
        root / "annotations" / "review-log.md": annotation_review_log_text(),
        root / "01-reading-cards" / "README.md": reading_cards_readme_text(),
        root / "02-literature-matrix" / "LM-001_search-map.md": "# Search Map\n\n待填写。\n",
        root / "02-literature-matrix" / "LM-002_reading-plan.md": "# Reading Plan\n\n待填写。\n",
        root / "02-literature-matrix" / "LM-006_gap-analysis-and-technical-route.md": "# Gap Analysis And Technical Route\n\n待填写。\n",
        root / "02-literature-matrix" / "LM-007_team-tracking.md": "# Team Tracking\n\n待填写。\n",
        root / "05-ai-code-workspace" / "README.md": "# AI Code Workspace\n\n用于保存本课题可复现分析脚本、配置、图表和日志；不要保存 API key、Zotero 数据库或 PDF 文件。长文本请优先复用 `.research/fulltext_cache/`。\n",
    }
    planned_or_created: list[Path] = []
    for path, text in files.items():
        if path.exists():
            continue
        planned_or_created.append(path)
        if not dry_run:
            write_text_if_missing(path, text)
    return planned_or_created


def main() -> int:
    args = build_parser().parse_args()
    path_resolver = load_path_resolver()
    topic_directions = parse_topic_directions(args.topic_direction)

    try:
        root, root_source, researchos_root, config_path = path_resolver.resolve_project_root(
            explicit_root=args.root,
            project_name=args.project_name,
            start=Path(__file__),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    root = root.expanduser()

    if root.exists() and not root.is_dir():
        print(f"ERROR: 指定路径已存在，但不是目录：{root}")
        return 2

    if not root.exists():
        if args.dry_run:
            print(f"DRY RUN: 课题根目录当前不存在：{root}")
            print("DRY RUN: 实际创建时请先手动创建根目录，或显式传入 --create-root。")
        elif not args.create_root:
            print(f"ERROR: 课题根目录不存在：{root}")
            print("如需创建根目录，请显式传入 --create-root。")
            return 2
        else:
            root.mkdir(parents=True, exist_ok=True)
            print(f"created root: {root}")

    created: list[Path] = []
    existing: list[Path] = []
    planned: list[Path] = []

    for dirname in STANDARD_DIRS:
        target = root / dirname
        if target.exists():
            if target.is_dir():
                existing.append(target)
                continue
            print(f"ERROR: 目标路径已存在但不是目录：{target}")
            return 3

        if args.dry_run:
            print(f"DRY RUN: 将创建目录：{target}")
            planned.append(target)
        else:
            target.mkdir(parents=True, exist_ok=True)
            created.append(target)

    scaffolded = scaffold_files(root, topic_directions, args.dry_run)

    print("\nResearchOS 课题输出目录")
    print(f"researchos_root: {researchos_root}")
    print(f"config: {config_path if config_path else '(未使用配置文件，采用默认路径规则)'}")
    print(f"root_source: {root_source}")
    print(f"root: {root}")

    if created:
        print("\ncreated:")
        for path in created:
            print(f"  {path}")

    if existing:
        print("\nexisting:")
        for path in existing:
            print(f"  {path}")

    if planned:
        print("\nplanned:")
        for path in planned:
            print(f"  {path}")

    if scaffolded:
        print("\nscaffold files:")
        for path in scaffolded:
            prefix = "DRY RUN: " if args.dry_run else ""
            print(f"  {prefix}{path}")

    print("\n建议用途：")
    print("  annotations           人工阅读批注收件箱、处理记录和已处理条目")
    print("  01-reading-cards      单篇文献读书卡和 PDF 抽取文本")
    print("  02-literature-matrix  文献综述矩阵、gap 分析、选题建议")
    print("  02-literature-matrix/prisma  PRISMA 检索、筛选、阅读状态和 Zotero tag mirror plan")
    print("  03-manuscript         论文大纲、方法审查、图表叙事、润色稿")
    print("  04-reviewer-response  审稿意见拆解、回复信、返修清单")
    print("  05-ai-code-workspace   本课题脚本、配置、图表和可复现分析")
    print("\n课题方向：")
    if topic_directions:
        for direction in topic_directions:
            print(f"  {direction['code']}: {direction['display']}")
    else:
        print("  未指定；已在 manifest 中写入占位方向，请人工修改。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
