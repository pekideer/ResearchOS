"""Read-only Zotero Local API maintenance CLI for ResearchOS.

Ordinary reading, literature matrix, and library governance should use the
ResearchOS SQLite parent document and normalized fulltext cache first. This CLI
is only for parent-document maintenance, path troubleshooting, and last-resort
PDF text extraction.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RESEARCHOS_ROOT = Path(__file__).resolve().parents[1]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import CORPUS_FULLTEXT_ROOT, find_researchos_root
from tools.zotero_local_api import (
    creators_to_text,
    fetch_children,
    fetch_json,
    load_config,
    resolve_pdf_file_url,
    year_from_date,
)

TIMEOUT_SECONDS = 8
SKIP_ITEM_TYPES = {"attachment", "note", "annotation"}
LOCAL_API_GUARD_MESSAGE = (
    "ERROR: Zotero Local API is only for parent-document maintenance or path "
    "troubleshooting. Ordinary reading, literature matrix, and library "
    "governance must use tools/build_zotero_library_context_packet.py against "
    "the SQLite parent document and normalized text. Pass --allow-local-api "
    "only when the parent document is missing, stale, or path resolution is broken."
)


def require_local_api(args: argparse.Namespace) -> bool:
    if getattr(args, "allow_local_api", False):
        return True
    print(LOCAL_API_GUARD_MESSAGE)
    return False


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    return {
        "key": item.get("key") or data.get("key"),
        "title": data.get("title", ""),
        "itemType": data.get("itemType", ""),
        "creators": creators_to_text(data.get("creators", [])),
        "year": year_from_date(data.get("date")),
        "DOI": data.get("DOI", ""),
        "url": data.get("url", ""),
    }


def child_summary(child: dict[str, Any]) -> dict[str, Any]:
    data = child.get("data", {})
    content_type = data.get("contentType", "")
    return {
        "key": child.get("key") or data.get("key"),
        "itemType": data.get("itemType", ""),
        "title": data.get("title", ""),
        "contentType": content_type,
        "linkMode": data.get("linkMode", ""),
        "filename": data.get("filename", ""),
        "isPdfAttachment": content_type.lower() == "application/pdf",
    }


def print_search_results(items: list[dict[str, Any]]) -> None:
    if not items:
        print("未找到 top-level 文献条目。")
        return
    for index, item in enumerate(items, start=1):
        print(f"[{index}] {item['title'] or '(无标题)'}")
        print(f"    key: {item['key']}")
        print(f"    type: {item['itemType']}")
        if item["creators"]:
            print(f"    authors: {item['creators']}")
        if item["year"]:
            print(f"    year: {item['year']}")
        if item["DOI"]:
            print(f"    DOI: {item['DOI']}")
        if item["url"]:
            print(f"    URL: {item['url']}")


def print_item(item: dict[str, Any], children: list[dict[str, Any]]) -> None:
    data = item.get("data", {})
    print("母条目")
    print(f"  title: {data.get('title', '')}")
    print(f"  key: {item.get('key') or data.get('key')}")
    print(f"  type: {data.get('itemType', '')}")
    print(f"  authors: {creators_to_text(data.get('creators', []))}")
    print(f"  date: {data.get('date', '')}")
    print(f"  DOI: {data.get('DOI', '')}")
    print(f"  URL: {data.get('url', '')}")
    print(f"  publication: {data.get('publicationTitle') or data.get('conferenceName') or ''}")
    print("\nChildren")
    if not children:
        print("  未发现 children。")
        return
    for index, child in enumerate(children, start=1):
        summary = child_summary(child)
        marker = " [PDF attachment key]" if summary["isPdfAttachment"] else ""
        print(f"  [{index}] {summary['title'] or '(无标题)'}{marker}")
        print(f"      key: {summary['key']}")
        print(f"      type: {summary['itemType']}")
        if summary["contentType"]:
            print(f"      contentType: {summary['contentType']}")
        if summary["filename"]:
            print(f"      filename: {summary['filename']}")
        if summary["linkMode"]:
            print(f"      linkMode: {summary['linkMode']}")


def find_pdf_attachment(children: list[dict[str, Any]]) -> dict[str, Any] | None:
    for child in children:
        data = child.get("data", {})
        if data.get("itemType") == "attachment" and str(data.get("contentType", "")).lower() == "application/pdf":
            return child
    return None


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._")
    return stem or "pdf_text"


def default_output_path(pdf_path: Path) -> Path:
    root = find_researchos_root()
    return root / CORPUS_FULLTEXT_ROOT / "manual-extracts" / f"{safe_stem(pdf_path)}.txt"


def cache_output_path(project_root: Path, item_key: str, cache_subdir: str) -> Path:
    return project_root / ".research" / "fulltext_cache" / cache_subdir / f"{item_key.upper()}.txt"


def extract_text(pdf_path: Path, max_pages: int | None) -> tuple[str, int, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少依赖 pypdf。请先安装 tools/requirements/base.txt。") from exc

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    page_limit = min(max_pages, total_pages) if max_pages else total_pages
    chunks: list[str] = []
    non_empty_pages = 0
    for index in range(page_limit):
        text = reader.pages[index].extract_text() or ""
        if text.strip():
            non_empty_pages += 1
        chunks.append(f"\n\n===== Page {index + 1} =====\n\n{text.strip()}")
    return "".join(chunks).strip() + "\n", page_limit, non_empty_pages


def command_ping(args: argparse.Namespace) -> int:
    if not require_local_api(args):
        return 2
    api_base, _user_id = load_config()
    url = api_base + "/"
    print(f"Checking Zotero Local API: {url}")
    try:
        request = Request(url, headers={"Zotero-API-Version": "3"})
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code == 403:
            print("ERROR: Zotero Local API 返回 403。请在 Zotero 设置中启用 Local API。")
            return 3
        print(f"ERROR: Zotero Local API 返回异常状态：HTTP {exc.code}")
        print(exc.read().decode("utf-8", errors="replace")[:500])
        return 1
    except URLError as exc:
        print("ERROR: 无法连接 Zotero Local API。请打开 Zotero 桌面端并启用 Local API。")
        print(f"底层错误：{exc.reason}")
        return 2
    if 200 <= status < 300:
        print("OK: Zotero Local API 可访问。")
        print(f"HTTP {status}")
        return 0
    print(f"ERROR: Zotero Local API 返回异常状态：HTTP {status}")
    print(body[:500])
    return 1


def command_search(args: argparse.Namespace) -> int:
    if not require_local_api(args):
        return 2
    api_base, user_id = load_config()
    url = f"{api_base}/users/{user_id}/items"
    params = {
        "q": args.query,
        "format": "json",
        "include": "data,bib",
        "limit": max(args.limit, 1),
        "itemType": "-attachment || -note",
    }
    try:
        raw_items = fetch_json(url, params)
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        print(f"ERROR: Zotero 搜索失败：{exc}")
        return 2
    normalized = [
        normalize_item(item)
        for item in raw_items
        if item.get("data", {}).get("itemType") not in SKIP_ITEM_TYPES
    ][: args.limit]
    if args.json:
        print(json.dumps(normalized, ensure_ascii=False, indent=2))
    else:
        print_search_results(normalized)
    return 0


def command_get_item(args: argparse.Namespace) -> int:
    if not require_local_api(args):
        return 2
    api_base, user_id = load_config()
    try:
        params = {"format": "json", "include": "data,bib"}
        item = fetch_json(f"{api_base}/users/{user_id}/items/{args.key}", params)
        children = fetch_json(f"{api_base}/users/{user_id}/items/{args.key}/children", params)
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        print(f"ERROR: 读取 Zotero item 失败：{exc}")
        return 2
    if args.json:
        print(json.dumps({"item": item, "children": children}, ensure_ascii=False, indent=2))
    else:
        print_item(item, children)
    return 0


def command_get_pdf(args: argparse.Namespace) -> int:
    if not require_local_api(args):
        return 2
    api_base, user_id = load_config()
    try:
        children = fetch_children(api_base, user_id, args.key)
        pdf_attachment = find_pdf_attachment(children)
        if pdf_attachment is None:
            print(f"ERROR: 条目 {args.key} 未发现 PDF attachment。")
            return 4
        attachment_key = pdf_attachment.get("key") or pdf_attachment.get("data", {}).get("key")
        file_url, path = resolve_pdf_file_url(api_base, user_id, str(attachment_key))
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        print(f"ERROR: 获取 PDF 路径失败：{exc}")
        return 2
    if path is None:
        print("ERROR: Zotero Local API 未返回可解析的 file URL。")
        return 5
    result = {
        "topLevelItemKey": args.key,
        "attachmentKey": attachment_key,
        "fileUrl": file_url,
        "pdfPath": str(path),
        "exists": path.exists(),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"PDF attachment key: {attachment_key}")
        print(f"file URL: {file_url}")
        print(f"PDF path: {path}")
        print(f"exists: {path.exists()}")
    return 0 if path.exists() else 6


def command_extract_pdf(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"ERROR: PDF 文件不存在或不是文件：{pdf_path}")
        return 2
    cache_path = None
    if args.project_root and args.item_key:
        cache_path = cache_output_path(Path(args.project_root).resolve(), args.item_key, args.cache_subdir)
    output_path = Path(args.output) if args.output else (cache_path if cache_path else default_output_path(pdf_path))
    if output_path.exists() and not args.overwrite:
        if cache_path and output_path.resolve() == cache_path.resolve() and not args.refresh_cache:
            text = cache_path.read_text(encoding="utf-8-sig", errors="replace")
            print("OK: 使用已有 fulltext cache，未重新读取 PDF。")
            print(f"cache: {cache_path}")
            print(f"chars: {len(text)}")
            return 0
        print(f"ERROR: 输出文件已存在：{output_path}")
        print("如需覆盖，请显式传入 --overwrite。")
        return 3
    if cache_path and cache_path.exists() and not args.refresh_cache:
        text = cache_path.read_text(encoding="utf-8-sig", errors="replace")
        if args.output:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8")
        print("OK: 使用已有 fulltext cache，未重新读取 PDF。")
        print(f"cache: {cache_path}")
        print(f"output: {output_path}")
        print(f"chars: {len(text)}")
        return 0
    try:
        text, extracted_pages, non_empty_pages = extract_text(pdf_path, args.max_pages)
    except Exception as exc:
        print(f"ERROR: PDF 文本抽取失败：{exc}")
        return 4
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    if cache_path and output_path.resolve() != cache_path.resolve():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    print("OK: 已抽取 PDF 文本。")
    print(f"PDF: {pdf_path}")
    print(f"pages extracted: {extracted_pages}")
    print(f"pages with text: {non_empty_pages}")
    print(f"output: {output_path}")
    if cache_path:
        print(f"cache: {cache_path}")
    if non_empty_pages == 0 or len(text.strip()) < 100:
        print("WARNING: 抽取文本很少，可能是扫描版 PDF。可能需要 OCR，本命令未做 OCR。")
    return 0


def add_local_api_guard(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-local-api",
        action="store_true",
        help="Explicitly allow Zotero Local API reads for parent-document maintenance/troubleshooting.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ping_parser = subparsers.add_parser("ping", help="Check Zotero Local API availability.")
    add_local_api_guard(ping_parser)
    ping_parser.set_defaults(func=command_ping)

    search_parser = subparsers.add_parser("search", help="Search top-level Zotero items.")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true")
    add_local_api_guard(search_parser)
    search_parser.set_defaults(func=command_search)

    item_parser = subparsers.add_parser("get-item", help="Read Zotero item metadata and children.")
    item_parser.add_argument("--key", required=True)
    item_parser.add_argument("--json", action="store_true")
    add_local_api_guard(item_parser)
    item_parser.set_defaults(func=command_get_item)

    pdf_parser = subparsers.add_parser("get-pdf", help="Resolve a Zotero item's PDF attachment path.")
    pdf_parser.add_argument("--key", required=True)
    pdf_parser.add_argument("--json", action="store_true")
    add_local_api_guard(pdf_parser)
    pdf_parser.set_defaults(func=command_get_pdf)

    extract_parser = subparsers.add_parser("extract-pdf", help="Extract text from a local PDF with pypdf.")
    extract_parser.add_argument("--pdf", required=True)
    extract_parser.add_argument("--max-pages", type=int, default=None)
    extract_parser.add_argument("--output")
    extract_parser.add_argument("--project-root")
    extract_parser.add_argument("--item-key")
    extract_parser.add_argument("--cache-subdir", default="reading-cards")
    extract_parser.add_argument("--refresh-cache", action="store_true")
    extract_parser.add_argument("--overwrite", action="store_true")
    extract_parser.set_defaults(func=command_extract_pdf)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
