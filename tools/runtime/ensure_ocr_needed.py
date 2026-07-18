"""Ensure local OCR dependencies and process Zotero PDFs marked needs_ocr.

This machine-level helper is intended to be safe from any ResearchOS terminal:

1. Check the local ResearchOS SQLite index for pdf_texts.status = 'needs_ocr'.
2. If none exist, exit without installing anything.
3. Ensure Python OCR packages are installed into the Python interpreter running
   this script.
4. Ensure a local Tesseract executable and tessdata are available.
5. Call zotero_library_index.py ocr-needed so OCR output is written to the
   standard fulltext cache root as ITEMKEY__ATTACHMENTKEY.txt.

It does not write to Zotero, does not read zotero.sqlite, and does not move or
copy Zotero PDF files.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import (
    CORPUS_ZOTERO_FULLTEXT,
    CORPUS_ZOTERO_FULLTEXT_NORMALIZED,
    CORPUS_ZOTERO_LIBRARY_DB,
)


DEFAULT_DB = CORPUS_ZOTERO_LIBRARY_DB
DEFAULT_FULLTEXT_CACHE_ROOT = CORPUS_ZOTERO_FULLTEXT
DEFAULT_NORMALIZED_CACHE_ROOT = CORPUS_ZOTERO_FULLTEXT_NORMALIZED
DEFAULT_OCR_LANGUAGE = "eng+chi_sim"
DEFAULT_OCR_DPI = 220
DEFAULT_OCR_MAX_SOURCE_PAGES = 80
DEFAULT_OCR_SKIP_ITEM_TYPES = ("book", "thesis")
REQUIRED_PYTHON_MODULES = {
    "fitz": "PyMuPDF",
    "PIL": "Pillow",
    "pytesseract": "pytesseract",
}
TESSDATA_BASE = "https://raw.githubusercontent.com/tesseract-ocr/tessdata/main"
DEFAULT_LANGUAGES = ("eng", "chi_sim")


def local_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ResearchOS"
    return Path.home() / ".researchos"


def default_tesseract_root() -> Path:
    return local_root() / "tesseract"


def common_tesseract_paths() -> list[Path]:
    paths = []
    program_files = os.environ.get("ProgramFiles")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if program_files:
        paths.append(Path(program_files) / "Tesseract-OCR" / "tesseract.exe")
    if local_app_data:
        paths.append(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    paths.append(default_tesseract_root() / "bin" / "tesseract.exe")
    return paths


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True, env=env)


def parse_skip_item_types(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def ocr_candidate_counts(db: Path, skip_item_types: set[str], max_source_pages: int | None) -> tuple[int, int]:
    if not db.exists():
        raise SystemExit(f"ERROR: database not found: {db}")
    clauses = ["t.status = 'needs_ocr'", "a.content_type = 'application/pdf'"]
    params: list[Any] = []
    if skip_item_types:
        placeholders = ",".join("?" for _ in skip_item_types)
        clauses.append(f"COALESCE(i.item_type, '') NOT IN ({placeholders})")
        params.extend(sorted(skip_item_types))
    if max_source_pages is not None:
        clauses.append("(COALESCE(t.pages_total, 0) = 0 OR t.pages_total <= ?)")
        params.append(max_source_pages)
    where_sql = " AND ".join(clauses)
    with sqlite3.connect(db) as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM pdf_texts WHERE status = 'needs_ocr'").fetchone()[0] or 0)
        eligible = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM pdf_texts AS t
                JOIN attachments AS a ON a.attachment_key = t.attachment_key
                JOIN items AS i ON i.item_key = t.item_key
                WHERE {where_sql}
                """,
                params,
            ).fetchone()[0]
            or 0
        )
    return total, eligible


def missing_python_modules() -> list[str]:
    missing = []
    for module_name, package_name in REQUIRED_PYTHON_MODULES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def ensure_python_ocr_packages(install: bool, dry_run: bool) -> None:
    missing = missing_python_modules()
    if not missing:
        print("python_ocr_packages: ok")
        return
    print("python_ocr_packages_missing: " + ", ".join(missing))
    if not install:
        raise SystemExit("ERROR: Python OCR packages are missing. Re-run without --no-install or install tools/requirements/ocr.txt manually.")
    requirements = RESEARCHOS_ROOT / "tools" / "requirements" / "ocr.txt"
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements),
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--no-cache-dir",
    ]
    if dry_run:
        print("DRY-RUN: " + " ".join(command))
        return
    run(command)
    still_missing = missing_python_modules()
    if still_missing:
        raise SystemExit("ERROR: Python OCR packages are still missing after install: " + ", ".join(still_missing))


def resolve_tesseract() -> Path | None:
    for env_name in ("RESEARCHOS_TESSERACT_CMD", "TESSERACT_CMD"):
        value = os.environ.get(env_name)
        if value and Path(value).exists():
            return Path(value)
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    for path in common_tesseract_paths():
        if path.exists():
            return path
    return None


def install_tesseract_with_winget(dry_run: bool) -> None:
    winget = shutil.which("winget")
    if not winget:
        raise SystemExit("ERROR: tesseract.exe not found and winget is unavailable. Install Tesseract manually, then re-run.")
    command = [
        winget,
        "install",
        "--id",
        "UB-Mannheim.TesseractOCR",
        "-e",
        "--silent",
        "--disable-interactivity",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    if dry_run:
        print("DRY-RUN: " + " ".join(command))
        return
    run(command)


def normalize_proxy(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if "://" not in value:
        return "http://" + value
    return value


def download_file(url: str, output: Path, proxy: str | None, dry_run: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 0:
        print(f"exists: {output}")
        return
    print(f"download: {url} -> {output}")
    if dry_run:
        return
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
        with opener.open(url, timeout=120) as response:
            output.write_bytes(response.read())
    else:
        urllib.request.urlretrieve(url, output)
    if output.stat().st_size <= 0:
        raise SystemExit(f"ERROR: downloaded file is empty: {output}")


def ensure_tessdata(languages: list[str], proxy: str | None, dry_run: bool) -> Path:
    tessdata_dir = default_tesseract_root() / "share" / "tessdata"
    for language in languages:
        download_file(
            f"{TESSDATA_BASE}/{language}.traineddata",
            tessdata_dir / f"{language}.traineddata",
            proxy,
            dry_run,
        )
    return tessdata_dir


def write_env_helper(tesseract_exe: Path, tessdata_dir: Path, dry_run: bool) -> Path:
    install_root = default_tesseract_root()
    install_root.mkdir(parents=True, exist_ok=True)
    env_path = install_root / "env.ps1"
    bin_dir = tesseract_exe.parent
    content = "\n".join(
        [
            f"$env:RESEARCHOS_TESSERACT_CMD = '{tesseract_exe}'",
            f"$env:TESSERACT_CMD = '{tesseract_exe}'",
            f"$env:TESSDATA_PREFIX = '{tessdata_dir}'",
            f"$env:PATH = '{bin_dir};' + $env:PATH",
            "",
        ]
    )
    if dry_run:
        print(f"DRY-RUN: write {env_path}")
        return env_path
    env_path.write_text(content, encoding="utf-8")
    return env_path


def ensure_tesseract(install: bool, languages: list[str], proxy: str | None, dry_run: bool) -> tuple[Path, Path, Path]:
    tesseract = resolve_tesseract()
    if tesseract is None:
        print("tesseract: missing")
        if not install:
            raise SystemExit("ERROR: tesseract.exe is missing. Re-run without --no-install or install Tesseract manually.")
        install_tesseract_with_winget(dry_run)
        tesseract = resolve_tesseract()
    if tesseract is None:
        raise SystemExit("ERROR: tesseract.exe still not found after install. Open a new terminal or check winget output.")
    print(f"tesseract: {tesseract}")
    tessdata_dir = ensure_tessdata(languages, proxy, dry_run)
    env_path = write_env_helper(tesseract, tessdata_dir, dry_run)
    os.environ["RESEARCHOS_TESSERACT_CMD"] = str(tesseract)
    os.environ["TESSERACT_CMD"] = str(tesseract)
    os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
    os.environ["PATH"] = str(tesseract.parent) + os.pathsep + os.environ.get("PATH", "")
    print(f"env_helper: {env_path}")
    return tesseract, tessdata_dir, env_path


def run_ocr_needed(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        str(RESEARCHOS_ROOT / "tools" / "zotero" / "zotero_library_index.py"),
        "--db",
        str(args.db),
        "ocr-needed",
        "--fulltext-cache-root",
        str(args.fulltext_cache_root),
        "--normalized-cache-root",
        str(args.normalized_cache_root),
        "--pdf-timeout",
        str(args.pdf_timeout),
        "--ocr-language",
        args.ocr_language,
        "--ocr-dpi",
        str(args.ocr_dpi),
        "--max-source-pages",
        str(args.max_source_pages or 0),
        "--skip-item-types",
        args.skip_item_types,
    ]
    if args.max_pages is not None:
        command.extend(["--max-pages", str(args.max_pages)])
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])
    if args.force_lock:
        command.append("--force-lock")
    command.extend(["--lock-stale-after", str(args.lock_stale_after)])
    if args.dry_run:
        print("DRY-RUN: " + " ".join(command))
        return
    run(command)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--fulltext-cache-root", type=Path, default=DEFAULT_FULLTEXT_CACHE_ROOT)
    parser.add_argument("--normalized-cache-root", type=Path, default=DEFAULT_NORMALIZED_CACHE_ROOT)
    parser.add_argument("--limit", type=int, default=None, help="Optional number of needs_ocr PDFs to process.")
    parser.add_argument("--max-source-pages", type=int, default=DEFAULT_OCR_MAX_SOURCE_PAGES, help="Skip needs_ocr PDFs whose known source page count is above this threshold; use 0 to disable.")
    parser.add_argument("--skip-item-types", default=",".join(DEFAULT_OCR_SKIP_ITEM_TYPES), help="Comma-separated Zotero item types to skip for OCR, default book,thesis.")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional OCR page limit per PDF.")
    parser.add_argument("--pdf-timeout", type=int, default=300, help="Per-PDF OCR timeout in seconds.")
    parser.add_argument("--ocr-language", default=DEFAULT_OCR_LANGUAGE)
    parser.add_argument("--ocr-dpi", type=int, default=DEFAULT_OCR_DPI)
    parser.add_argument("--language", action="append", dest="languages", default=None, help="Tessdata language to ensure; default eng and chi_sim.")
    parser.add_argument("--proxy", default=normalize_proxy(os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")), help="Optional proxy for tessdata downloads, e.g. http://127.0.0.1:7888.")
    parser.add_argument("--no-install", action="store_true", help="Fail instead of installing missing Python packages or Tesseract.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned actions without installing or running OCR.")
    parser.add_argument("--lock-stale-after", type=int, default=1800)
    parser.add_argument("--force-lock", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise SystemExit("ERROR: --limit must be >= 1")
    if args.max_pages is not None and args.max_pages < 1:
        raise SystemExit("ERROR: --max-pages must be >= 1")
    if args.max_source_pages == 0:
        args.max_source_pages = None
    if args.max_source_pages is not None and args.max_source_pages < 0:
        raise SystemExit("ERROR: --max-source-pages must be >= 0")
    if args.pdf_timeout < 1:
        raise SystemExit("ERROR: --pdf-timeout must be >= 1")
    if args.ocr_dpi < 72:
        raise SystemExit("ERROR: --ocr-dpi must be >= 72")

    skip_item_types = parse_skip_item_types(args.skip_item_types)
    needs_ocr, eligible_needs_ocr = ocr_candidate_counts(args.db, skip_item_types, args.max_source_pages)
    print(f"needs_ocr_total: {needs_ocr}")
    print(f"eligible_after_skip_rules: {eligible_needs_ocr}")
    print(f"skipped_by_type_or_length: {needs_ocr - eligible_needs_ocr}")
    if eligible_needs_ocr == 0:
        print("OK: no eligible OCR work needed.")
        return 0

    install = not args.no_install
    ensure_python_ocr_packages(install, args.dry_run)
    languages = args.languages or list(DEFAULT_LANGUAGES)
    ensure_tesseract(install, languages, args.proxy, args.dry_run)
    run_ocr_needed(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
