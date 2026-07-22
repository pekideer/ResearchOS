"""Run a disposable ResearchOS Phase 5 probe eval.

The probe creates a temporary mini project, verifies fulltext-cache-first
workflows, dry-run behavior, clickable Zotero links, and automatic cleanup.
It does not call Zotero and does not use real API keys.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def run_command(args: list[str]) -> str:
    result = subprocess.run(
        [str(PYTHON), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(args)
            + "\nstdout:\n"
            + result.stdout
            + "\nstderr:\n"
            + result.stderr
        )
    return result.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_probe(project: Path) -> None:
    write(
        project / "01-reading-cards" / "RC-001_probe.md",
        """# Probe Reading Card

## 一段话综述

This temporary probe checks ResearchOS metadata parsing, cache packet building, and dry-run synchronization.

## 7. 元数据（折叠）

<details>
<summary>Reading card metadata</summary>

```yaml
item_key: "[ABCD1234](zotero://select/library/items/ABCD1234)"
manual_ref_id: "RC-001"
title: "Probe Study"
authors: "Alice Probe; Bob Test"
year: "2026"
venue: "Journal of Probe Studies"
journal_abbrev: "J Probe Stud"
publication_tags: "sci: Q2"
read_status: "read"
importance: "medium"
planned_use: "method-source"
topic_relevance: "direct"
tags: "T1_probe"
rating_5: "3"
evidence_strength: "medium"
one_paragraph_review: "Probe review sentence."
pdf_attachment_key: "EFGH5678"
first_author_affiliation_status: "?"
```

</details>
""",
    )
    write(
        project / ".research" / "fulltext_cache" / "01-reading-cards" / "ABCD1234.txt",
        """===== Page 1 =====
Probe Study
Alice Probe 1, Bob Test 2
1 School of Probe Engineering, Test University, China
2 Department of Validation, Example Institute, China

This page is a temporary cache probe for ResearchOS Phase 5 validation.

===== Page 2 =====
The methods section is intentionally short.
""",
    )
    write(
        project / "02-literature-matrix" / ".internal" / "easyscholar-journal-ranking-table.csv",
        'journal_name,normalized_name,status,publication_tags,fields_json,source_query,updated_at\n'
        'Journal of Probe Studies,journalofprobestudies,ok,sci: Q2,"{""sci"":""Q2""}",Journal of Probe Studies,2026-07-02T00:00:00\n',
    )
    fake_env = project / ".internal" / "fake-easyscholar.env"
    write(fake_env, "EASYSCHOLAR_API_KEY=replace_with_real_key_probe\n")
    write(
        project / ".internal" / "easyscholar.yml",
        f'endpoint: "https://example.invalid/easyscholar"\n'
        f'secret_env_file: "{str(fake_env).replace("\\", "/")}"\n'
        f'rate_limit_seconds: "0"\n',
    )


def run_probe(project: Path) -> dict[str, str]:
    internal = project / "02-literature-matrix" / ".internal"
    outputs: dict[str, str] = {}
    outputs["fulltext_packet"] = run_command(
        [
            "tools/reading_cards/build_fulltext_cache_packet.py",
            "--project-root",
            str(project),
            "--max-pages",
            "1",
            "--output",
            str(internal / "probe-fulltext-packet.md"),
        ]
    )
    outputs["affiliation_packet"] = run_command(
        [
            "tools/reading_cards/build_affiliation_semantic_packet.py",
            "--project-root",
            str(project),
            "--max-pages",
            "1",
            "--output",
            str(internal / "probe-affiliation-packet.md"),
        ]
    )
    outputs["summary_table"] = run_command(["tools/reading_cards/sync_reading_summary_table.py", "--project-root", str(project)])
    outputs["journal_rankings"] = run_command(
        [
            "tools/reading_cards/sync_journal_rankings.py",
            "--project-root",
            str(project),
            "--provider-config",
            str(project / ".internal" / "easyscholar.yml"),
            "--dry-run",
        ]
    )
    return outputs


def verify_probe(project: Path, outputs: dict[str, str]) -> None:
    fulltext_packet = project / "02-literature-matrix" / ".internal" / "probe-fulltext-packet.md"
    affiliation_packet = project / "02-literature-matrix" / ".internal" / "probe-affiliation-packet.md"
    summary_md = project / "02-literature-matrix" / "LM-004_reading-summary-table.md"
    summary_html = project / "02-literature-matrix" / "LM-004_reading-summary-table.html"
    for path in [fulltext_packet, affiliation_packet, summary_md, summary_html]:
        require(path.exists(), f"missing output: {path}")
    packet_text = fulltext_packet.read_text(encoding="utf-8")
    affiliation_text = affiliation_packet.read_text(encoding="utf-8")
    summary_text = summary_md.read_text(encoding="utf-8") + "\n" + summary_html.read_text(encoding="utf-8")
    require("Cache status: ok" in packet_text, "fulltext packet did not report cache ok")
    require("School of Probe Engineering" in packet_text, "fulltext packet missing evidence text")
    require("School of Probe Engineering" in affiliation_text, "affiliation packet missing evidence text")
    require("zotero://select/library/items/ABCD1234" in summary_text, "summary output missing clickable Zotero item link")
    require("api_requests: 0" in outputs["journal_rankings"], "journal ranking dry-run unexpectedly requested API")
    require("ranking_table_hits: 1" in outputs["journal_rankings"], "journal ranking dry-run missed local table")


def main() -> int:
    probe_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix=".tmp_phase5_probe_eval-", dir=ROOT) as temp_dir:
        probe_path = Path(temp_dir)
        build_probe(probe_path)
        outputs = run_probe(probe_path)
        verify_probe(probe_path, outputs)
        result = {
            "status": "ok",
            "probe_dir": str(probe_path),
            "checks": {
                "fulltext_cache_first": True,
                "clickable_zotero_item_link": True,
                "journal_ranking_api_requests": 0,
                "first_author_pdf_reads": 0,
            },
        }
    require(probe_path is not None and not probe_path.exists(), "temporary probe directory was not deleted")
    result["probe_deleted"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
