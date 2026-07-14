"""Render mirrored Zotero annotations into a controlled reading-card section.

The default mode writes only a dry-run preview. Use ``--write-cards`` to update
the generated section while leaving every other reading-card section untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.reading_cards.card_common import content_sha256, reading_card_identity
from tools.researchos_outputs import (
    CORPUS_READING_CARDS_ROOT,
    CORPUS_ZOTERO_LIBRARY_DB,
    M005_READING_CARD_ANNOTATION_SYNC,
    ensure_output_dirs,
    write_json,
)


START_MARKER = "<!-- researchos:zotero-annotations:start -->"
END_MARKER = "<!-- researchos:zotero-annotations:end -->"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def evidence_role(row: sqlite3.Row | dict[str, Any]) -> str:
    text = str(row["annotation_text"] or "").strip()
    comment = str(row["annotation_comment"] or "").strip()
    if text and comment:
        return "原文摘录＋人工判断"
    if text:
        return "原文摘录"
    if comment:
        return "人工判断"
    return "定位线索"


def optional_value(row: sqlite3.Row | dict[str, Any], key: str, default: Any = "") -> Any:
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def physical_page(row: sqlite3.Row | dict[str, Any]) -> int | None:
    try:
        position = json.loads(str(row["annotation_position_json"] or "{}"))
        if isinstance(position, str):
            position = json.loads(position)
        if not isinstance(position, dict):
            return None
        page_index = int(position.get("pageIndex"))
    except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
        return None
    return page_index + 1


def annotation_link(row: sqlite3.Row | dict[str, Any]) -> str:
    attachment_key = str(row["attachment_key"] or "")
    params: dict[str, Any] = {}
    page = physical_page(row)
    if page is not None:
        params["page"] = page
    annotation_key = str(row["annotation_key"] or "")
    if annotation_key:
        params["annotation"] = annotation_key
    suffix = "?" + urlencode(params) if params else ""
    return f"zotero://open-pdf/library/items/{attachment_key}{suffix}"


def quote_lines(value: str) -> list[str]:
    lines = [line.strip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return [f"> {line}" if line else ">" for line in lines]


def comment_lines(value: str) -> list[str]:
    """Render every comment line below the list item, never as a control line."""
    lines = [line.strip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return [f"  > {line}" if line else "  >" for line in lines]


def render_annotation(row: sqlite3.Row | dict[str, Any], index: int) -> str:
    text = str(row["annotation_text"] or "").strip()
    comment = str(row["annotation_comment"] or "").strip()
    page_label = str(row["annotation_page_label"] or "").strip()
    page = physical_page(row)
    try:
        pages_total = int(optional_value(row, "pdf_pages_total", 0) or 0)
    except (TypeError, ValueError):
        pages_total = 0
    color = str(row["annotation_color"] or "").strip()
    annotation_type = str(row["annotation_type"] or "").strip() or "annotation"
    lines = [f"#### 标注 {index}"]
    if text:
        lines.extend(["", *quote_lines(text)])
    if comment:
        lines.extend(["", "- **人工批注：**", *comment_lines(comment)])
    if page is not None:
        pdf_position = f"PDF 第 {page}/{pages_total} 页" if pages_total else f"PDF 第 {page} 页"
        location = f"[{pdf_position}]({annotation_link(row)})"
    else:
        location = f"[PDF 标注位置]({annotation_link(row)})"
    if page_label and page_label != str(page):
        location += f"；文献印刷页码 `{page_label}`"
    lines.extend(
        [
            f"- **位置：** {location}",
            f"- **标注类型：** `{annotation_type}`" + (f"；颜色 `{color}`" if color else ""),
            f"- **证据角色：** {evidence_role(row)}",
            "- **处理状态：** 待核查",
        ]
    )
    return "\n".join(lines)


def render_block(rows: list[sqlite3.Row | dict[str, Any]], synced_at: str | None = None) -> str:
    synced_at = synced_at or utc_now()
    lines = [
        START_MARKER,
        "### 6.99 人工阅读标注（Zotero 同步）",
        "",
        "> 本区由 ResearchOS 从 Zotero 原生标注生成。原文摘录、人工判断和定位线索不得混同；正式改写读书卡正文前仍需人工或模型核查。",
        "",
    ]
    if rows:
        for index, row in enumerate(rows, start=1):
            if index > 1:
                lines.extend(["", "---", ""])
            lines.append(render_annotation(row, index))
    else:
        lines.append("当前未发现活动标注；历史删除状态仍保留在 ResearchOS 父文档中。")
    lines.extend(["", f"- **最近同步：** {synced_at}", END_MARKER])
    return "\n".join(lines)


def replace_generated_block(body: str, block: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    starts = [index for index, line in enumerate(lines) if line == START_MARKER]
    ends = [index for index, line in enumerate(lines) if line == END_MARKER]
    if starts or ends:
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            raise ValueError("Reading card has duplicate, unbalanced, or reversed Zotero annotation markers")
    marker_pattern = re.compile(
        rf"(?ms)^{re.escape(START_MARKER)}\s*\n.*?^{re.escape(END_MARKER)}\s*\n?"
    )
    replacement = block.rstrip() + "\n\n"
    if marker_pattern.search(body):
        return marker_pattern.sub(replacement, body, count=1).rstrip() + "\n"
    metadata = re.search(r"(?m)^##\s+7\.\s+元数据（折叠）\s*$", body)
    if metadata:
        return (body[: metadata.start()].rstrip() + "\n\n" + replacement + body[metadata.start() :].lstrip()).rstrip() + "\n"
    return body.rstrip() + "\n\n" + block.rstrip() + "\n"


def active_annotations(conn: sqlite3.Connection, item_key: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT a.annotation_key, a.attachment_key, a.annotation_type, a.annotation_text,
               a.annotation_comment, a.annotation_color, a.annotation_page_label,
               a.annotation_sort_index, a.annotation_position_json, a.date_modified,
               COALESCE(p.pages_total, 0) AS pdf_pages_total
        FROM annotations AS a
        LEFT JOIN pdf_texts AS p ON p.attachment_key = a.attachment_key
        WHERE a.parent_item_key = ? AND COALESCE(a.zotero_deleted, 0) = 0
        ORDER BY a.attachment_key, a.annotation_sort_index, a.annotation_key
        """,
        (item_key,),
    ).fetchall()


def select_cards(cards_root: Path, item_keys: set[str]) -> list[tuple[Path, str, str, str]]:
    selected: list[tuple[Path, str, str, str]] = []
    for path in sorted(cards_root.glob("*.md")):
        body = path.read_text(encoding="utf-8-sig")
        card_id, item_key = reading_card_identity(body, path)
        if not item_key or (item_keys and item_key not in item_keys):
            continue
        selected.append((path, body, card_id, item_key))
    return selected


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else RESEARCHOS_ROOT
    ensure_output_dirs(root)
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = root / db_path
    cards_root = Path(args.cards_root)
    if not cards_root.is_absolute():
        cards_root = root / cards_root
    item_keys = {str(value).strip().upper() for value in (args.item_key or [])}
    invalid_item_keys = sorted(key for key in item_keys if not re.fullmatch(r"[A-Z0-9]{8}", key))
    if invalid_item_keys:
        raise SystemExit(f"Invalid Zotero item key(s): {', '.join(invalid_item_keys)}")
    if args.write_cards and not item_keys:
        raise SystemExit("--write-cards requires at least one explicit --item-key")
    if not db_path.exists():
        raise SystemExit(f"ResearchOS parent document not found: {db_path}")
    cards = select_cards(cards_root, item_keys)
    if not cards:
        raise SystemExit("No centralized reading cards matched the selected item keys")

    output_dir = root / M005_READING_CARD_ANNOTATION_SYNC / f"{safe_timestamp()}-card-{'write' if args.write_cards else 'dry-run'}"
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_rows: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        for path, body, card_id, item_key in cards:
            rows = active_annotations(conn, item_key)
            block = render_block(rows)
            updated = replace_generated_block(body, block)
            changed = updated != body
            relative_path = str(path.relative_to(root)).replace("\\", "/") if path.is_relative_to(root) else path.name
            plan_rows.append(
                {
                    "card_id": card_id,
                    "item_key": item_key,
                    "card_path": relative_path,
                    "annotations": len(rows),
                    "changed": changed,
                    "before_hash": content_sha256(body),
                    "after_hash": content_sha256(updated),
                }
            )
            (output_dir / f"{card_id or path.stem}-annotation-section.md").write_text(block + "\n", encoding="utf-8")
            if args.write_cards and changed:
                path.write_text(updated, encoding="utf-8")

    summary = {
        "generated_at": utc_now(),
        "mode": "write_cards" if args.write_cards else "dry_run",
        "cards_selected": len(plan_rows),
        "cards_changed": sum(1 for row in plan_rows if row["changed"]),
        "annotations_rendered": sum(int(row["annotations"]) for row in plan_rows),
        "output_dir": str(output_dir.relative_to(root)).replace("\\", "/"),
    }
    write_json(output_dir / "card-update-plan.json", {"summary": summary, "cards": plan_rows})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--db", default=str(CORPUS_ZOTERO_LIBRARY_DB))
    parser.add_argument("--cards-root", default=str(CORPUS_READING_CARDS_ROOT / "cards"))
    parser.add_argument("--item-key", action="append")
    parser.add_argument("--write-cards", action="store_true")
    return parser


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
