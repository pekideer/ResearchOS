"""Extract heuristic first-author affiliation candidates for reading cards.

This script is heuristic. It checks project fulltext cache first, then an
explicit affiliation cache when provided, then Zotero/PDF only as fallback. It never writes to
Zotero, never reads zotero.sqlite, and never changes PDFs. Semantic extraction
during reading-card generation is the authoritative source.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

try:
    from .card_common import known, metadata_heading_pattern, parse_metadata, raw_item_key, yaml_scalar
except ImportError:  # Direct script execution keeps the script directory on sys.path.
    from card_common import known, metadata_heading_pattern, parse_metadata, raw_item_key, yaml_scalar
from tools.zotero.zotero_local_api import fetch_json as fetch_zotero_json, resolve_pdf_file_url


API_BASE = "http://127.0.0.1:23119/api"
USER_ID = "0"
AUTHORITATIVE_AFFILIATION_SOURCES = ("semantic extraction", "manual", "人工确认", "人工核查")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--researchos-root",
        default=str(Path(__file__).resolve().parent.parent.parent),
        help="ResearchOS root. Used to locate corpus/reading-cards/cards and corpus/indexes.",
    )
    parser.add_argument("--cards-root")
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--user-id", default=USER_ID)
    parser.add_argument(
        "--fulltext-cache-root",
        help="Defaults to <project-root>/.research/fulltext_cache.",
    )
    parser.add_argument("--skip-fulltext-cache", action="store_true", help="Do not read project fulltext cache before Zotero/PDF fallback.")
    parser.add_argument("--max-cache-pages", type=int, default=2, help="Number of marked fulltext-cache pages to inspect.")
    parser.add_argument("--refresh-cache", action="store_true", help="Re-read Zotero/PDF even when cache exists.")
    parser.add_argument(
        "--cache-dir",
        help="Optional explicit cache directory. No project-local affiliation cache is used by default.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def set_metadata(body: str, metadata: dict[str, Any]) -> str:
    metadata.pop("extra", None)
    preferred = [
        "item_key",
        "manual_ref_id",
        "title",
        "title_zh",
        "authors",
        "first_author_affiliation",
        "first_author_affiliation_raw",
        "first_author_affiliation_source",
        "first_author_affiliation_status",
        "year",
        "venue",
        "journal_abbrev",
        "publication_tags",
        "journal_ranking_source",
        "journal_ranking_status",
    ]
    ordered = [key for key in preferred if key in metadata and known(metadata.get(key))]
    ordered.extend(sorted(key for key in metadata if key not in ordered and known(metadata.get(key))))
    yaml_body = "\n".join(f"{key}: {yaml_scalar(metadata[key])}" for key in ordered)
    section = (
        "## 7. 元数据（折叠）\n\n"
        "<details>\n"
        "<summary>Reading card metadata</summary>\n\n"
        "```yaml\n"
        f"{yaml_body}\n"
        "```\n\n"
        "</details>"
    )
    pattern = re.compile(rf"(?ms)\n*{metadata_heading_pattern()}.*?```(?:yaml|yml)\s*\n.*?\n```\s*</details>\s*")
    return pattern.sub("\n\n" + section, body).rstrip() if pattern.search(body) else body.rstrip() + "\n\n" + section


def fetch_local_api_json(api_base: str, user_id: str, path: str) -> Any:
    url = f"{api_base.rstrip('/')}/users/{user_id}/{path.lstrip('/')}"
    return fetch_zotero_json(url)


def response_to_file_url(headers: Any, body: str) -> str | None:
    location = headers.get("Location")
    if location:
        return location
    text = body.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return text
    if isinstance(payload, dict):
        return str(payload.get("url") or payload.get("file") or payload.get("path") or "")
    return text


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def resolve_pdf_path(api_base: str, user_id: str, attachment_key: str) -> Path | None:
    _file_url, path = resolve_pdf_file_url(api_base.rstrip("/"), user_id, attachment_key)
    return path if path.exists() else None


def pdf_attachment_key(api_base: str, user_id: str, item_key: str) -> str:
    children = fetch_local_api_json(api_base, user_id, f"items/{item_key}/children")
    for child in children if isinstance(children, list) else []:
        data = child.get("data", {})
        if data.get("itemType") == "attachment" and str(data.get("contentType", "")).lower() == "application/pdf":
            return str(child.get("key") or data.get("key") or "")
    return ""


def extract_first_pages(pdf_path: Path, pages: int = 2) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    chunks = []
    for index in range(min(pages, len(reader.pages))):
        chunks.append(reader.pages[index].extract_text() or "")
    return "\n".join(chunks)


def default_fulltext_cache_roots(project_root: Path, cards_root: Path) -> list[Path]:
    base = project_root / ".research" / "fulltext_cache"
    return [base]


def fulltext_cache_roots(args: argparse.Namespace, project_root: Path, cards_root: Path) -> list[Path]:
    if args.skip_fulltext_cache:
        return []
    if args.fulltext_cache_root:
        return [Path(args.fulltext_cache_root).resolve()]
    return default_fulltext_cache_roots(project_root, cards_root)


def find_fulltext_cache_file(cache_roots: list[Path], item_key: str) -> Path | None:
    if not item_key:
        return None
    for root in cache_roots:
        candidate = root / f"{item_key}.txt"
        if candidate.exists():
            return candidate
    return None


def extract_marked_cache_pages(path: Path, max_pages: int) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    marker = re.compile(r"(?m)^===== Page (\d+) =====\s*$")
    matches = list(marker.finditer(text))
    if not matches:
        return text[:12000]
    chunks: list[str] = []
    for index, match in enumerate(matches):
        page = int(match.group(1))
        if page > max_pages:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunks.append(text[match.start() : end].strip())
    return "\n\n".join(chunks)[:12000]


def cache_path(cache_dir: Path, attachment_key: str) -> Path:
    safe = re.sub(r"[^A-Z0-9_-]+", "_", attachment_key.upper()).strip("_")
    return cache_dir / f"{safe}.json"


def load_cached_affiliation(cache_dir: Path, attachment_key: str) -> dict[str, Any] | None:
    path = cache_path(cache_dir, attachment_key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def save_cached_affiliation(
    cache_dir: Path,
    attachment_key: str,
    item_key: str,
    affiliation: str,
    status: str,
    source: str,
    first_pages_text: str,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Keep enough local evidence for deterministic re-use, without sending PDF
    # text to the model or storing full-paper text.
    snippet = first_pages_text[:12000]
    payload = {
        "attachment_key": attachment_key,
        "item_key": item_key,
        "status": status,
        "affiliation": affiliation,
        "source": source,
        "text_scope": "PDF pages 1-2",
        "first_pages_text": snippet,
    }
    cache_path(cache_dir, attachment_key).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


BAD_LINE = re.compile(
    r"(?i)(abstract|keywords|doi|received|accepted|available online|copyright|journal homepage|contents lists|"
    r"corresponding author|e-mail|email|tel\.|fax|science ?direct|elsevier|springer|wiley|article history|"
    r"摘要|关键词|收稿|作者简介|通讯作者)"
)
BAD_AFFILIATION_LINE = re.compile(
    r"(?i)(evaluation on|energy savings|experimental study|numerical and experimental|review|state of the art|"
    r"thesis submitted|submitted to|in partial fulfillment|requirements for|supervisor|dissertation)"
)

AFFILIATION_KEYWORDS = re.compile(
    r"(大学|学院|研究院|研究所|实验室|重点实验室|中心|公司|\bUniversity\b|\bDepartment\b|\bSchool\b|\bInstitute\b|\bLaboratory\b|"
    r"\bLab\b|\bCentre\b|\bCenter\b|\bFaculty\b|\bCollege\b|\bAcademy\b|\bCorporation\b|\bGmbH\b|\bInc\.|\bChina\b|\bUSA\b|\bUnited States\b|\bJapan\b|"
    r"Germany|Denmark|Italy|Korea|Australia|Canada|Netherlands|Singapore|Switzerland|École|Ecole|UK|Kingdom)",
    re.I,
)


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"^[a-zA-Z0-9,*†‡§\s]{0,5}(?=(Department|School|Institute|University|College|Faculty|Center|Centre|大学|学院|研究院|研究所|实验室))", "", line)
    return line.strip(" ;,")


def trim_to_first_affiliation(value: str) -> str:
    text = value.strip(" ,;")
    # When several affiliation addresses are extracted as one line, keep only
    # the first address after a country/city boundary.
    country_boundary = re.search(
        r"(?i)\b(USA|China|Japan|Germany|Denmark|Italy|Australia|Canada|Netherlands|Singapore|Switzerland|UK)\b,\s+(?=(?:[a-z]\s+)?(?:Department|School|Institute|University|College|Faculty|Center|Centre|Laboratory|École|Ecole)\b)",
        text,
    )
    if country_boundary:
        text = text[: country_boundary.end(1)]
    marker_split = re.split(
        r"(?i)\s+[bcdefgh]\s+(?=(?:Department|School|Institute|University|College|Faculty|Center|Centre|Laboratory)\b)",
        text,
        maxsplit=1,
    )
    if marker_split:
        text = marker_split[0]
    return text.strip(" ,;")


def candidate_affiliation(text: str) -> str:
    lines = [clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if len(line) >= 12]
    for idx, line in enumerate(lines[:120]):
        if BAD_LINE.search(line):
            continue
        if BAD_AFFILIATION_LINE.search(line):
            continue
        if not AFFILIATION_KEYWORDS.search(line):
            continue
        combined = line
        for next_line in lines[idx + 1 : idx + 3]:
            if BAD_LINE.search(next_line):
                break
            if BAD_AFFILIATION_LINE.search(next_line):
                break
            if len(combined) > 240:
                break
            if AFFILIATION_KEYWORDS.search(next_line) or re.search(r"\b\d{4,6}\b|China|USA|Japan|Germany|Denmark", next_line, re.I):
                combined += ", " + next_line
        combined = re.sub(r"\s*,\s*,+", ", ", combined).strip(" ,;")
        combined = trim_to_first_affiliation(combined)
        if not combined or BAD_AFFILIATION_LINE.search(combined):
            continue
        return combined[:300]
    return ""


def find_cards(cards_root: Path) -> list[Path]:
    return sorted(
        path
        for path in cards_root.rglob("*.md")
        if path.is_file() and not path.name.startswith("_") and path.name.lower() != "readme.md"
    )


def has_authoritative_affiliation(metadata: dict[str, str]) -> bool:
    affiliation = str(metadata.get("first_author_affiliation", "")).strip().strip("'\"")
    if not known(affiliation):
        return False
    source = str(metadata.get("first_author_affiliation_source", "")).strip().strip("'\"").lower()
    status = str(metadata.get("first_author_affiliation_status", "")).strip().strip("'\"").lower()
    return any(marker in source for marker in AUTHORITATIVE_AFFILIATION_SOURCES) or status in {"ok", "manual_confirmed"}


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(args.project_root).resolve()
    researchos_root = Path(args.researchos_root).resolve()
    cards_root = Path(args.cards_root).resolve() if args.cards_root else researchos_root / "corpus" / "reading-cards" / "cards"
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else None
    text_cache_roots = fulltext_cache_roots(args, project_root, cards_root)
    rows: list[dict[str, str]] = []
    changed = 0
    fulltext_cache_hits = 0
    cache_hits = 0
    pdf_reads = 0
    for card in find_cards(cards_root):
        text = card.read_text(encoding="utf-8-sig")
        metadata = parse_metadata(text)
        item_key = raw_item_key(metadata.get("item_key"))
        status = "no_item_key"
        affiliation = ""
        source = ""
        error = ""
        try:
            fulltext_cache_file = find_fulltext_cache_file(text_cache_roots, item_key)
            if fulltext_cache_file is not None:
                first_pages = extract_marked_cache_pages(fulltext_cache_file, args.max_cache_pages)
                fulltext_cache_hits += 1
                affiliation = candidate_affiliation(first_pages)
                status = "ok" if affiliation else "no_match"
                source = f"fulltext_cache {fulltext_cache_file.name}, pages 1-{args.max_cache_pages}, heuristic"
            else:
                attachment_key = str(metadata.get("pdf_attachment_key") or "")
                if not attachment_key and item_key:
                    attachment_key = pdf_attachment_key(args.api_base, args.user_id, item_key)
                if not attachment_key:
                    status = "no_pdf"
                else:
                    cached = None if (args.refresh_cache or cache_dir is None) else load_cached_affiliation(cache_dir, attachment_key)
                    if cached is not None:
                        cache_hits += 1
                        affiliation = str(cached.get("affiliation", "") or "")
                        status = str(cached.get("status", "") or ("ok" if affiliation else "no_match"))
                        source = str(cached.get("source", "") or f"PDF {attachment_key}, pages 1-2, cached heuristic")
                    else:
                        pdf_path = resolve_pdf_path(args.api_base, args.user_id, attachment_key)
                        if not pdf_path:
                            status = "pdf_not_found"
                        else:
                            first_pages = extract_first_pages(pdf_path, pages=2)
                            pdf_reads += 1
                            affiliation = candidate_affiliation(first_pages)
                            status = "ok" if affiliation else "no_match"
                            source = f"PDF {attachment_key}, pages 1-2, heuristic"
                            if not args.dry_run and cache_dir is not None:
                                save_cached_affiliation(cache_dir, attachment_key, item_key, affiliation, status, source, first_pages)
        except (HTTPError, URLError, OSError, RuntimeError, Exception) as exc:  # noqa: BLE001
            status = "error"
            error = str(exc)
        if affiliation:
            current_affiliation = str(metadata.get("first_author_affiliation", "")).strip().strip("'\"")
            current_source = str(metadata.get("first_author_affiliation_source", "")).strip().strip("'\"")
            if has_authoritative_affiliation(metadata):
                status = "skipped_authoritative"
                rows.append({"card": str(card), "item_key": item_key, "status": status, "affiliation": affiliation, "source": source, "error": error})
                continue
            if current_affiliation != affiliation or current_source != source:
                metadata["first_author_affiliation"] = affiliation
                metadata["first_author_affiliation_source"] = source
                metadata["first_author_affiliation_status"] = "heuristic_candidate"
                updated = set_metadata(text, metadata).rstrip() + "\n"
                if updated != text:
                    changed += 1
                    if not args.dry_run:
                        card.write_text(updated, encoding="utf-8")
        elif "heuristic" in str(metadata.get("first_author_affiliation_source", "")).lower():
            metadata.pop("first_author_affiliation", None)
            metadata.pop("first_author_affiliation_raw", None)
            metadata.pop("first_author_affiliation_source", None)
            metadata.pop("first_author_affiliation_status", None)
            updated = set_metadata(text, metadata).rstrip() + "\n"
            if updated != text:
                changed += 1
                if not args.dry_run:
                    card.write_text(updated, encoding="utf-8")
        rows.append({"card": str(card), "item_key": item_key, "status": status, "affiliation": affiliation, "source": source, "error": error})

    report = researchos_root / "corpus" / "indexes" / "first-author-affiliation-sync-report.csv"
    if not args.dry_run:
        report.parent.mkdir(parents=True, exist_ok=True)
        import csv

        with report.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["card", "item_key", "status", "affiliation", "source", "error"])
            writer.writeheader()
            writer.writerows(rows)
    print("ResearchOS first-author affiliation sync")
    print(f"cards_seen: {len(rows)}")
    print(f"cards_changed: {changed}")
    print(f"fulltext_cache_hits: {fulltext_cache_hits}")
    print(f"cache_hits: {cache_hits}")
    print(f"pdf_reads: {pdf_reads}")
    for status, count in sorted(Counter(row["status"] for row in rows).items()):
        print(f"{status}: {count}")
    print(f"dry_run: {args.dry_run}")
    if not args.dry_run:
        print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
