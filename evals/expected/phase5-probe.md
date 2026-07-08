# Phase 5 Probe Eval Expected Behavior

- `evals/run_phase5_probe.py` creates a temporary mini project under the ResearchOS root and deletes it before exit.
- The eval must not call Zotero and must not use a real API key.
- Fulltext and affiliation packets must report cache hits and include the probe evidence line.
- Reading summary Markdown/HTML must expose the Zotero item key as a clickable `zotero://select/library/items/ABCD1234` link.
- EasyScholar ranking dry-run must use the local ranking table with `api_requests: 0`.
- First-author affiliation dry-run must use fulltext cache with `pdf_reads: 0`.
