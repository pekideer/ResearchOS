"""Create numbered ResearchOS output folders under a user-specified project root.

This script only creates directories. It does not move, copy, rename, or delete
files, and it does not write to Zotero.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


CENTRALIZED_READING_CARDS = "centralized-links"
BASE_STANDARD_DIRS = [
    ".research",
    "01-课题入口",
    "02-证据材料",
    "03-文献矩阵",
    "03-文献矩阵/01-检索路线与候选文献",
    "03-文献矩阵/02-阅读计划",
    "03-文献矩阵/03-文献管理元数据",
    "03-文献矩阵/04-阅读总表",
    "03-文献矩阵/04-阅读总表/分主题阅读总表",
    "03-文献矩阵/05-读书卡审计与证据",
    "03-文献矩阵/06-矩阵缺口与技术路线",
    "03-文献矩阵/07-团队追踪",
    "03-文献矩阵/08-项目文献集覆盖层",
    "03-文献矩阵/08-项目文献集覆盖层/01-计划与条目分配",
    "03-文献矩阵/08-项目文献集覆盖层/02-文献集创建审计",
    "03-文献矩阵/08-项目文献集覆盖层/03-条目金丝雀审计",
    "03-文献矩阵/08-项目文献集覆盖层/04-条目批量写入审计",
    "03-文献矩阵/09-治理记录",
    "04-决策记录",
    "05-论文稿件",
    "06-报告材料",
    "07-审稿回复",
    "08-写作材料",
    "09-计算工作区",
    "10-批注",
    "10-批注/processed",
]
FORBIDDEN_OLD_DIRS = [
    "01-reading-cards",
    "02-literature-matrix",
    "03-manuscript",
    "04-reviewer-response",
    "05-ai-code-workspace",
    "annotations",
    "03-decisions",
    "04-reports",
]


def standard_dirs(reading_cards_mode: str) -> list[str]:
    if reading_cards_mode != CENTRALIZED_READING_CARDS:
        raise ValueError("只允许集中读书卡模式；项目目录不得生成旧本地读书卡目录。")
    return BASE_STANDARD_DIRS


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
    parser.add_argument(
        "--reading-cards-mode",
        choices=[CENTRALIZED_READING_CARDS],
        default=CENTRALIZED_READING_CARDS,
        help=(
            "Only centralized-links is allowed. Reading cards live in "
            "corpus/reading-cards/cards; project directories only keep pointers, "
            "summary tables, and tracking reports."
        ),
    )
    parser.add_argument(
        "--centralized-reading-cards-dir",
        default="00_ResearchOS/corpus/reading-cards/cards/",
        help="Human-readable pointer used in manifest when --reading-cards-mode centralized-links.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Read-only audit of project workspace and reading-card path consistency.",
    )
    parser.add_argument(
        "--registry-reading-cards",
        help=(
            "Optional reading_cards value from project registry, for example "
            "centralized:00_ResearchOS/corpus/reading-cards/cards/."
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


def project_manifest_text(
    root: Path,
    directions: list[dict[str, str]],
    reading_cards_mode: str,
    centralized_reading_cards_dir: str,
) -> str:
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
    if reading_cards_mode != CENTRALIZED_READING_CARDS:
        raise ValueError("只允许集中读书卡模式。")
    reading_card_output = f"""  reading_cards_mode: "centralized_links"
  centralized_reading_cards_dir: "{centralized_reading_cards_dir}"
  reading_card_project_links: []
"""

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
{reading_card_output.rstrip()}
  entry_dir: "01-课题入口/"
  evidence_dir: "02-证据材料/"
  literature_matrix_dir: "03-文献矩阵/"
  reading_plan_dir: "03-文献矩阵/02-阅读计划/"
  reading_summary_dir: "03-文献矩阵/04-阅读总表/"
  decisions_dir: "04-决策记录/"
  manuscript_dir: "05-论文稿件/"
  reports_dir: "06-报告材料/"
  reviewer_response_dir: "07-审稿回复/"
  writing_dir: "08-写作材料/"
  computation_workspace_dir: "09-计算工作区/"
  annotations_dir: "10-批注/"

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


def annotation_inbox_text() -> str:
    return """
# Human Annotation Inbox

这个文件用于记录你阅读本课题文档时的想法、意见、疑问和修改建议。它只保留待处理或需确认条目；已处理条目会进入 `processed/`。

使用原则：

- 优先把本课题的批注写在这里；跨项目或暂时不知道归属时才写 ResearchOS 全局 `.researchos/human-annotation-inbox/inbox.md`。
- `target_document` 尽量写相对课题根目录的路径，例如 `03-文献矩阵/04-阅读总表/xxx.md`、`05-论文稿件/xxx.md`、`07-审稿回复/xxx.md`。
- 不确定的事实、数据、文献结论直接写“待核查”。

## 待处理条目

在此标题下方追加新的 `## ANNO-...` 条目。
"""


def annotation_review_log_text() -> str:
    return """
# Human Annotation Review Log

本文件由 agent 在处理本课题 `10-批注/inbox.md` 后追加记录。保留既有记录，便于回溯处理过程。
"""


def scaffold_files(
    root: Path,
    directions: list[dict[str, str]],
    dry_run: bool,
    reading_cards_mode: str,
    centralized_reading_cards_dir: str,
) -> list[Path]:
    files = {
        root / ".research" / "project_manifest.yml": project_manifest_text(
            root,
            directions,
            reading_cards_mode,
            centralized_reading_cards_dir,
        ),
        root / "10-批注" / "inbox.md": annotation_inbox_text(),
        root / "10-批注" / "review-log.md": annotation_review_log_text(),
        root / "03-文献矩阵" / "01-检索路线与候选文献" / "LM-001_search-map.md": "# 检索路线\n\n待填写。\n",
        root / "03-文献矩阵" / "02-阅读计划" / "LM-002_reading-plan.md": "# 阅读计划\n\n待填写。\n",
        root / "03-文献矩阵" / "06-矩阵缺口与技术路线" / "LM-006_gap-analysis-and-technical-route.md": "# 矩阵缺口与技术路线\n\n待填写。\n",
        root / "03-文献矩阵" / "07-团队追踪" / "LM-007_team-tracking.md": "# 团队追踪\n\n待填写。\n",
        root / "09-计算工作区" / "README.md": "# 计算工作区\n\n用于保存本课题可复现分析脚本、配置、图表和日志；不要保存 API key、Zotero 数据库或 PDF 文件。长文本请优先复用 `.research/fulltext_cache/`。\n",
    }

    planned_or_created: list[Path] = []
    for path, text in files.items():
        if path.exists():
            continue
        planned_or_created.append(path)
        if not dry_run:
            write_text_if_missing(path, text)
    return planned_or_created


def audit_workspace(root: Path, registry_reading_cards: str | None) -> int:
    issues: list[str] = []
    manifest = root / ".research" / "project_manifest.yml"
    if not root.exists() or not root.is_dir():
        print(f"ERROR: 课题根目录不存在或不是目录：{root}")
        return 2

    for dirname in FORBIDDEN_OLD_DIRS:
        if (root / dirname).exists():
            issues.append(f"发现旧英文目录，必须迁移或删除空目录：{dirname}")

    if not manifest.exists():
        issues.append("缺少 .research/project_manifest.yml，无法确认读书卡落点。")
        manifest_text = ""
    else:
        manifest_text = manifest.read_text(encoding="utf-8")

    registry_uses_centralized = bool(
        registry_reading_cards and registry_reading_cards.strip().startswith("centralized:")
    )
    manifest_uses_centralized = (
        'reading_cards_mode: "centralized_links"' in manifest_text
        or "reading_cards_mode: centralized_links" in manifest_text
        or "centralized_reading_cards_dir:" in manifest_text
    )
    manifest_declares_old_path = any(marker in manifest_text for marker in FORBIDDEN_OLD_DIRS) or bool(
        re.search(r"(?m)^\s*reading_cards_dir\s*:", manifest_text)
    )

    if manifest_declares_old_path:
        issues.append("manifest 仍包含旧英文目录或本地读书卡路径。")
    if registry_reading_cards and not registry_uses_centralized:
        issues.append("项目登记的 reading_cards 不是集中读书卡模式。")
    if manifest.exists() and not manifest_uses_centralized:
        issues.append('manifest 未声明 reading_cards_mode: "centralized_links"。')

    print("ResearchOS 项目工作区审计")
    print(f"root: {root}")
    print(f"manifest: {manifest if manifest.exists() else '(missing)'}")
    print(f"registry_reading_cards: {registry_reading_cards if registry_reading_cards else '(未提供)'}")
    print(
        "reading_cards_mode: "
        + (
            "centralized-links"
            if registry_uses_centralized or manifest_uses_centralized
            else "project-local"
        )
    )

    if issues:
        print("\nissues:")
        for issue in issues:
            print(f"  - {issue}")
        return 4

    print("\nOK: 项目登记、manifest 与中文目录规则一致。")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.audit and args.root:
        return audit_workspace(Path(args.root).expanduser(), args.registry_reading_cards)

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

    if args.audit:
        return audit_workspace(root, args.registry_reading_cards)

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

    for dirname in standard_dirs(args.reading_cards_mode):
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

    scaffolded = scaffold_files(
        root,
        topic_directions,
        args.dry_run,
        args.reading_cards_mode,
        args.centralized_reading_cards_dir,
    )

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
    print("  01-课题入口           入口、索引、项目说明和指针页")
    print("  02-证据材料           来源记录、证据地图和材料索引")
    print("  03-文献矩阵           阅读计划、阅读总表、团队追踪和缺口分析")
    print("  05-论文稿件           论文大纲、方法审查、图表叙事、润色稿")
    print("  07-审稿回复           审稿意见拆解、回复信、返修清单")
    print("  09-计算工作区         本课题脚本、配置、图表和可复现分析")
    print("  10-批注               人工阅读批注收件箱、处理记录和已处理条目")
    print("  集中读书卡            主卡位于 corpus/reading-cards/cards/，项目目录不生成本地读书卡目录")
    print("\n课题方向：")
    if topic_directions:
        for direction in topic_directions:
            print(f"  {direction['code']}: {direction['display']}")
    else:
        print("  未指定；已在 manifest 中写入占位方向，请人工修改。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
