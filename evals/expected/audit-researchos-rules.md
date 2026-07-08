# audit_researchos_rules expected behavior

- `naked-zotero-key-sample.md` is intentionally invalid and should appear under `eval_fixture_naked_zotero_keys`.
- `clickable-zotero-key-sample.md` should not be reported as a naked key violation.
- `legacy-journal-level-card-fragment.md` should appear in old EasyScholar field scans.
- The fixture violations must not be counted as real human-document violations in `naked_zotero_keys`.
