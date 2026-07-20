import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.runtime.project_write_guard import add_project_write_guard_args, require_from_args


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def read_docx(path: Path) -> str:
    paragraphs = []
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    for paragraph in root.findall(".//w:p", WORD_NS):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{{{WORD_NS['w']}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{WORD_NS['w']}}}tab":
                parts.append("\t")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def read_pdf(path: Path, max_pages: int | None) -> tuple[str, int | None]:
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover
        return f"[PDF_TEXT_EXTRACTION_FAILED] pdfplumber unavailable: {exc}", None

    pages_text = []
    page_count = None
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for index, page in enumerate(pages, start=1):
            text = page.extract_text() or ""
            pages_text.append(f"\n\n[page {index}]\n{text.strip()}")
    return "\n".join(pages_text).strip(), page_count


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def safe_cache_name(rel: Path) -> str:
    stem = "__".join(rel.with_suffix("").parts)
    stem = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", stem).strip("._")
    return stem or "material"


def portable_child_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return "{LOCAL_PATH}/" + path.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-pdf-pages", type=int, default=80)
    parser.add_argument("--fulltext-cache-dir", help="Defaults to <project-root>/02-证据材料/全文缓存/materials.")
    parser.add_argument("--refresh-cache", action="store_true")
    add_project_write_guard_args(parser)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    output_dir = Path(args.output_dir)
    fulltext_cache_dir = Path(args.fulltext_cache_dir) if args.fulltext_cache_dir else project_root / "02-证据材料" / "全文缓存" / "materials"
    text_dir = output_dir / "material_text"
    require_from_args(args, [output_dir, fulltext_cache_dir])
    text_dir.mkdir(parents=True, exist_ok=True)

    records = []
    exts = {".docx", ".pdf", ".md", ".txt"}
    for path in sorted(project_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        if any(part.startswith(".") for part in path.relative_to(project_root).parts):
            continue

        rel = path.relative_to(project_root)
        stem = "__".join(rel.with_suffix("").parts)
        out_path = text_dir / f"{stem}.txt"
        page_count = None
        try:
            if path.suffix.lower() == ".docx":
                text = read_docx(path)
                source_type = "docx"
            elif path.suffix.lower() == ".pdf":
                cache_path = fulltext_cache_dir / f"{safe_cache_name(rel)}.txt"
                if cache_path.exists() and not args.refresh_cache:
                    text = read_text(cache_path)
                    source_type = "pdf_cached"
                else:
                    text, page_count = read_pdf(path, args.max_pdf_pages)
                    source_type = "pdf"
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(text, encoding="utf-8")
            else:
                text = read_text(path)
                source_type = path.suffix.lower().lstrip(".")
        except Exception as exc:
            text = f"[EXTRACTION_FAILED] {type(exc).__name__}: {exc}"
            source_type = path.suffix.lower().lstrip(".")

        out_path.write_text(text, encoding="utf-8")
        records.append(
            {
                "path": str(rel).replace("\\", "/"),
                "relative_path": str(rel).replace("\\", "/"),
                "source_type": source_type,
                "bytes": path.stat().st_size,
                "page_count": page_count,
                "chars_extracted": len(text),
                "text_output": portable_child_path(out_path, output_dir),
            }
        )

    (output_dir / "material_index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_lines = [
        "# 项目材料索引",
        "",
        "| 文件 | 类型 | 页数 | 抽取字符数 | 文本输出 |",
        "|---|---:|---:|---:|---|",
    ]
    for r in records:
        md_lines.append(
            f"| {r['relative_path']} | {r['source_type']} | {r['page_count'] or ''} | "
            f"{r['chars_extracted']} | {Path(r['text_output']).name} |"
        )
    (output_dir / "material_index.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "output_dir": str(output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
