"""Build first-author affiliation semantic-review packets from fulltext cache.

This tool does not call Zotero, does not read PDFs, and does not write reading
cards. It prepares compact page-1/page-2 evidence for an agent or human to
semantically extract authors and first-author affiliation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from card_common import known, parse_metadata, raw_item_key
from tools.runtime.project_write_guard import add_project_write_guard_args, require_from_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--researchos-root",
        default=str(Path(__file__).resolve().parent.parent.parent),
        help="ResearchOS root. Used to locate corpus/reading-cards/cards when --cards-root is omitted.",
    )
    parser.add_argument("--cards-root")
    parser.add_argument("--fulltext-cache-root")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-chars-per-card", type=int, default=4500)
    parser.add_argument("--output")
    parser.add_argument("--jsonl-output")
    add_project_write_guard_args(parser)
    return parser


def default_cards_root(researchos_root: Path) -> Path:
    return researchos_root / "corpus" / "reading-cards" / "cards"


def default_cache_roots(project_root: Path, cards_root: Path) -> list[Path]:
    return [
        project_root / "02-证据材料" / "全文缓存",
        project_root / ".research" / "fulltext_cache",  # legacy read-only compatibility
    ]


def find_cache_file(cache_roots: list[Path], item_key: str) -> Path | None:
    if not item_key:
        return None
    for root in cache_roots:
        candidate = root / f"{item_key}.txt"
        if candidate.exists():
            return candidate
    return None


def portable_path(path: Path | None, project_root: Path, researchos_root: Path) -> str:
    if not path:
        return ""
    resolved = path.resolve()
    try:
        return "{PROJECT_ROOT}/" + str(resolved.relative_to(project_root.resolve())).replace("\\", "/")
    except ValueError:
        pass
    try:
        return "{RESEARCHOS_ROOT}/" + str(resolved.relative_to(researchos_root.resolve())).replace("\\", "/")
    except ValueError:
        return "{LOCAL_PATH}/" + path.name


def extract_marked_pages(text: str, max_pages: int) -> str:
    marker = re.compile(r"(?m)^===== Page (\d+) =====\s*$")
    matches = list(marker.finditer(text))
    if not matches:
        return text
    chunks: list[str] = []
    for index, match in enumerate(matches):
        page = int(match.group(1))
        if page > max_pages:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunks.append(text[match.start() : end].strip())
    return "\n\n".join(chunks) if chunks else text[:0]


def compact_text(text: str, max_chars: int) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text[:max_chars].rstrip()


def find_cards(cards_root: Path) -> list[Path]:
    return sorted(
        path
        for path in cards_root.rglob("*.md")
        if path.is_file() and not path.name.startswith("_") and path.name.lower() != "readme.md"
    )


def build_record(
    card: Path,
    cache_roots: list[Path],
    project_root: Path,
    researchos_root: Path,
    max_pages: int,
    max_chars: int,
) -> dict[str, Any]:
    text = card.read_text(encoding="utf-8-sig")
    metadata = parse_metadata(text)
    item_key = raw_item_key(metadata.get("item_key"))
    cache_file = find_cache_file(cache_roots, item_key)
    front_text = ""
    cache_status = "missing"
    if cache_file:
        raw = cache_file.read_text(encoding="utf-8-sig", errors="replace")
        front_text = compact_text(extract_marked_pages(raw, max_pages), max_chars)
        cache_status = "ok" if front_text else "empty"
    return {
        "card": portable_path(card, project_root, researchos_root),
        "manual_ref_id": metadata.get("manual_ref_id", ""),
        "item_key": item_key,
        "title": metadata.get("title", ""),
        "authors_current": metadata.get("authors", ""),
        "first_author_affiliation_current": metadata.get("first_author_affiliation", ""),
        "first_author_affiliation_status_current": metadata.get("first_author_affiliation_status", ""),
        "cache_status": cache_status,
        "cache_path": portable_path(cache_file, project_root, researchos_root),
        "text_scope": f"fulltext_cache pages 1-{max_pages}",
        "front_text": front_text,
    }


def markdown_packet(records: list[dict[str, Any]], cache_roots: list[Path], project_root: Path, researchos_root: Path) -> str:
    lines = [
        "# First-Author Affiliation Semantic Packet",
        "",
        "Purpose: use only the cached first pages below to semantically extract authors and first-author affiliation.",
        "",
        "Rules:",
        "- Output `first_author_affiliation` as `一级单位, 国家`.",
        "- Preserve supporting evidence in `first_author_affiliation_raw`.",
        "- Use `semantic_confirmed`, `semantic_needs_check`, `semantic_not_found`, or `source_unavailable` for status.",
        "- Do not infer missing country or institution from general knowledge.",
        "- Do not read Zotero or PDFs before checking this packet/cache.",
        "",
        "Cache roots checked:",
        *[f"- `{portable_path(root, project_root, researchos_root)}`" for root in cache_roots],
        "",
    ]
    for record in records:
        ref = record.get("manual_ref_id") or "?"
        key = record.get("item_key") or "?"
        lines.extend(
            [
                f"## {ref} / {key}",
                "",
                f"- Title: {record.get('title') or '?'}",
                f"- Current authors: {record.get('authors_current') or '?'}",
                f"- Current affiliation: {record.get('first_author_affiliation_current') or '?'}",
                f"- Current status: {record.get('first_author_affiliation_status_current') or '?'}",
                f"- Cache status: {record.get('cache_status')}",
                f"- Cache path: `{record.get('cache_path') or '?'}`",
                "",
                "```text",
                record.get("front_text") or "[NO CACHED FRONT TEXT]",
                "```",
                "",
                "Expected extraction:",
                "",
                "```yaml",
                'authors: "..."',
                'first_author_affiliation: "一级单位, 国家"',
                'first_author_affiliation_raw: "..."',
                'first_author_affiliation_source: "fulltext_cache pages 1-2 semantic extraction"',
                'first_author_affiliation_status: "semantic_confirmed|semantic_needs_check|semantic_not_found|source_unavailable"',
                'pages_checked: [1, 2]',
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(args.project_root).resolve()
    researchos_root = Path(args.researchos_root).resolve()
    cards_root = Path(args.cards_root).resolve() if args.cards_root else default_cards_root(researchos_root)
    cache_roots = [Path(args.fulltext_cache_root).resolve()] if args.fulltext_cache_root else default_cache_roots(project_root, cards_root)
    output = (
        Path(args.output).resolve()
        if args.output
        else project_root / "02-证据材料" / "语料包" / "first-author-affiliation-semantic-packet.md"
    )
    jsonl_output = Path(args.jsonl_output).resolve() if args.jsonl_output else output.with_suffix(".jsonl")
    require_from_args(args, [output, jsonl_output])

    records = [
        build_record(card, cache_roots, project_root, researchos_root, args.max_pages, args.max_chars_per_card)
        for card in find_cards(cards_root)
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_packet(records, cache_roots, project_root, researchos_root), encoding="utf-8")
    jsonl_output.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    print("ResearchOS affiliation semantic packet")
    print(f"cards_seen: {len(records)}")
    print(f"cache_ok: {sum(1 for record in records if record['cache_status'] == 'ok')}")
    print(f"cache_missing: {sum(1 for record in records if record['cache_status'] == 'missing')}")
    print(f"output: {output}")
    print(f"jsonl_output: {jsonl_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
