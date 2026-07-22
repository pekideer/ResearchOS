"""Build task-scoped Zotero governance evidence and validate agent results.

Research semantics remain the responsibility of the active ChatGPT/Codex agent. This
CLI only prepares evidence, validates structured results, and writes read-only plans.
It never writes Zotero or calls a language-model API.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
    DOCS_LIBRARY_GOVERNANCE,
    M002_LIBRARY_GOVERNANCE,
)
from tools.zotero.governance.contracts import TaskKind, result_schema, validate_result
from tools.zotero.governance.evidence import (
    build_agent_packet,
    build_records,
    write_jsonl,
    write_preparation_report,
    write_preview,
)
from tools.zotero.governance.plans import build_plan, write_plan_outputs


def default_path(task: TaskKind, name: str, suffix: str, human: bool = False) -> Path:
    root = DOCS_LIBRARY_GOVERNANCE if human else M002_LIBRARY_GOVERNANCE
    return root / f"zotero-{task.value}-{name}.{suffix}"


def resolved(value: str | None, fallback: Path) -> Path:
    return Path(value) if value else fallback


def _task(value: str) -> TaskKind:
    try:
        return TaskKind.parse(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def command_prepare(args: argparse.Namespace) -> int:
    records = build_records(
        db_path=Path(args.db),
        normalized_root=Path(args.normalized_root),
        root=RESEARCHOS_ROOT,
        task=args.task,
        max_first_page_chars=args.max_first_page_chars,
        item_keys=args.item_key,
        query=args.query,
        limit=args.limit,
    )
    output_jsonl = resolved(args.output_jsonl, default_path(args.task, "corpus", "jsonl"))
    preview_csv = resolved(args.preview_csv, default_path(args.task, "corpus-preview", "csv"))
    report = resolved(args.report, default_path(args.task, "preparation-report", "md", human=True))
    write_jsonl(output_jsonl, records)
    write_preview(preview_csv, records)
    write_preparation_report(report, args.task, records, output_jsonl)
    print(json.dumps({
        "task": args.task.value,
        "records": len(records),
        "jsonl": str(output_jsonl),
        "preview_csv": str(preview_csv),
        "report": str(report),
    }, ensure_ascii=False))
    return 0


def command_packet(args: argparse.Namespace) -> int:
    corpus_jsonl = resolved(args.corpus_jsonl, default_path(args.task, "corpus", "jsonl"))
    output_jsonl = resolved(args.output_jsonl, default_path(args.task, "agent-packet", "jsonl"))
    instructions_md = resolved(args.instructions_md, default_path(args.task, "agent-instructions", "md"))
    count = build_agent_packet(corpus_jsonl, output_jsonl, instructions_md, args.task, args.limit)
    print(json.dumps({
        "task": args.task.value,
        "items": count,
        "agent_packet": str(output_jsonl),
        "instructions": str(instructions_md),
    }, ensure_ascii=False))
    return 0


def command_plan(args: argparse.Namespace) -> int:
    plan = build_plan(args.task, Path(args.results_jsonl))
    output_json = resolved(args.output_json, default_path(args.task, "semantic-plan", "json"))
    output_csv = resolved(args.output_csv, default_path(args.task, "semantic-plan", "csv"))
    report = resolved(args.report, default_path(args.task, "semantic-plan-report", "md", human=True))
    write_plan_outputs(plan, output_json, output_csv, report)
    print(json.dumps({
        "task": args.task.value,
        "items": len(plan["items"]),
        "errors": len(plan["errors"]),
        "output_json": str(output_json),
        "output_csv": str(output_csv),
        "report": str(report),
    }, ensure_ascii=False))
    return 0 if not plan["errors"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-corpus", help="Build task-scoped evidence from the read-only Zotero parent document.")
    prepare.add_argument("--task", type=_task, required=True, metavar="{content-tags,library-structure}")
    prepare.add_argument("--db", default=str(CORPUS_ZOTERO_LIBRARY_DB))
    prepare.add_argument("--normalized-root", default=str(CORPUS_ZOTERO_FULLTEXT_NORMALIZED))
    prepare.add_argument("--max-first-page-chars", type=int, default=4000)
    prepare.add_argument("--item-key", action="append")
    prepare.add_argument("--query")
    prepare.add_argument("--limit", type=int)
    prepare.add_argument("--output-jsonl")
    prepare.add_argument("--preview-csv")
    prepare.add_argument("--report")
    prepare.set_defaults(func=command_prepare)

    packet = subparsers.add_parser("build-agent-packet", help="Build a bounded packet and task-specific result schema.")
    packet.add_argument("--task", type=_task, required=True, metavar="{content-tags,library-structure}")
    packet.add_argument("--corpus-jsonl")
    packet.add_argument("--output-jsonl")
    packet.add_argument("--instructions-md")
    packet.add_argument("--limit", type=int)
    packet.set_defaults(func=command_packet)

    plan = subparsers.add_parser("build-plan", help="Validate task-specific agent results and build a read-only semantic plan.")
    plan.add_argument("--task", type=_task, required=True, metavar="{content-tags,library-structure}")
    plan.add_argument("--results-jsonl", required=True)
    plan.add_argument("--output-json")
    plan.add_argument("--output-csv")
    plan.add_argument("--report")
    plan.set_defaults(func=command_plan)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["TaskKind", "build_parser", "result_schema", "validate_result"]
