"""Build a compact evidence packet from project fulltext cache.

Use this before asking an agent to read long materials. For compatibility the
tool can read legacy `.research/fulltext_cache` text files, but new packets are
written under `02-证据材料/语料包` by default. It does not call Zotero or read PDFs.
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

from card_common import parse_metadata, raw_item_key
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
    parser.add_argument("--item-key", action="append", help="Limit to one or more Zotero item keys.")
    parser.add_argument("--max-pages", type=int, default=None, help="Keep marked pages 1..N when page markers exist.")
    parser.add_argument("--max-chars-per-item", type=int, default=12000)
    parser.add_argument("--output")
    parser.add_argument("--jsonl-output")
    add_project_write_guard_args(parser)
    return parser


def default_cards_root(researchos_root: Path) -> Path:
    return researchos_root / "corpus" / "reading-cards" / "cards"


def default_cache_roots(project_root: Path, cards_root: Path | None) -> list[Path]:
    return [
        project_root / "02-证据材料" / "全文缓存",
        project_root / ".research" / "fulltext_cache",  # legacy read-only compatibility
    ]


def find_cache_file(cache_roots: list[Path], item_key: str) -> Path | None:
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


def extract_marked_pages(text: str, max_pages: int | None) -> str:
    if not max_pages:
        return text
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
    return "\n\n".join(chunks) if chunks else ""


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


def card_records(cards_root: Path, item_keys: set[str] | None) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for card in find_cards(cards_root):
        metadata = parse_metadata(card.read_text(encoding="utf-8-sig"))
        item_key = raw_item_key(metadata.get("item_key"))
        if not item_key or (item_keys is not None and item_key not in item_keys):
            continue
        records.append(
            {
                "manual_ref_id": metadata.get("manual_ref_id", ""),
                "item_key": item_key,
                "title": metadata.get("title", ""),
                "card": str(card),
            }
        )
    return records


def direct_key_records(item_keys: set[str]) -> list[dict[str, str]]:
    return [{"manual_ref_id": "", "item_key": key, "title": "", "card": ""} for key in sorted(item_keys)]


def build_records(
    seed_records: list[dict[str, str]],
    cache_roots: list[Path],
    project_root: Path,
    researchos_root: Path,
    max_pages: int | None,
    max_chars: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for seed in seed_records:
        item_key = seed["item_key"]
        cache_file = find_cache_file(cache_roots, item_key)
        cache_status = "missing"
        packet_text = ""
        if cache_file:
            raw = cache_file.read_text(encoding="utf-8-sig", errors="replace")
            packet_text = compact_text(extract_marked_pages(raw, max_pages), max_chars)
            cache_status = "ok" if packet_text else "empty"
        records.append(
            {
                **seed,
                "card": portable_path(Path(seed["card"]), project_root, researchos_root) if seed.get("card") else "",
                "cache_status": cache_status,
                "cache_path": portable_path(cache_file, project_root, researchos_root),
                "text_scope": f"fulltext_cache pages 1-{max_pages}" if max_pages else "fulltext_cache full text truncated",
                "packet_text": packet_text,
            }
        )
    return records


def markdown_packet(records: list[dict[str, Any]], cache_roots: list[Path], project_root: Path, researchos_root: Path) -> str:
    lines = [
        "# Fulltext Cache Packet",
        "",
        "Purpose: use cached text as the source for long-reading tasks. Do not read Zotero/PDF before checking this packet/cache.",
        "",
        "Cache roots checked:",
        *[f"- `{portable_path(root, project_root, researchos_root)}`" for root in cache_roots],
        "",
    ]
    for record in records:
        label = record.get("manual_ref_id") or record.get("item_key") or "item"
        lines.extend(
            [
                f"## {label} / {record.get('item_key') or '?'}",
                "",
                f"- Title: {record.get('title') or '?'}",
                f"- Cache status: {record.get('cache_status')}",
                f"- Cache path: `{record.get('cache_path') or '?'}`",
                f"- Text scope: {record.get('text_scope')}",
                "",
                "```text",
                record.get("packet_text") or "[NO CACHED TEXT]",
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
    item_keys = {key.upper() for key in args.item_key} if args.item_key else None
    if cards_root.exists():
        seed_records = card_records(cards_root, item_keys)
    elif item_keys is not None:
        seed_records = direct_key_records(item_keys)
    else:
        seed_records = []
    output = Path(args.output).resolve() if args.output else project_root / "02-证据材料" / "语料包" / "fulltext-cache-packet.md"
    jsonl_output = Path(args.jsonl_output).resolve() if args.jsonl_output else output.with_suffix(".jsonl")
    require_from_args(args, [output, jsonl_output])

    records = build_records(seed_records, cache_roots, project_root, researchos_root, args.max_pages, args.max_chars_per_item)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_packet(records, cache_roots, project_root, researchos_root), encoding="utf-8")
    jsonl_output.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )

    print("ResearchOS fulltext cache packet")
    print(f"records: {len(records)}")
    print(f"cache_ok: {sum(1 for record in records if record['cache_status'] == 'ok')}")
    print(f"cache_missing: {sum(1 for record in records if record['cache_status'] == 'missing')}")
    print(f"output: {output}")
    print(f"jsonl_output: {jsonl_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
