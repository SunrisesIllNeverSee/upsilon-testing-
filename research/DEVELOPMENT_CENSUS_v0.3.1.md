# Parser-Development Sample Census — v0.3.1 Baseline

**Parser:** v0.3.1 (tag: dev-baseline-v0.3.1)
**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)
**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain
corpus (original + multiple amendments per issuer) that the reconstruction
study ultimately requires.
**Date:** 2026-08-30

## Table 1 — Corpus structure

| Format | Documents | % |
|--------|----------|---|
| Inline amendment | 20 | 80.0% |
| Composite | 0 | 0.0% |
| Amended/restated | 0 | 0.0% |
| Redline | 0 | 0.0% |
| Referential | 0 | 0.0% |
| Waiver | 1 | 4.0% |
| Mixed | 4 | 16.0% |
| **Total** | **25** | **100.0%** |

## Table 2 — v0.3 performance by format

| Format | Precision | Recall | Unresolved | Docs |
|--------|-----------|--------|------------|------|
| Inline | 1.000 | 0.138 | 0 | 20 |
| Composite | N/A | N/A | 0 | 0 |
| Restated | N/A | N/A | 0 | 0 |
| Referential | N/A | N/A | 0 | 0 |
| Waiver | N/A | N/A | 0 | 1 |
| Mixed | N/A | N/A | 0 | 4 |
| **All amendment documents** | **1.000** | **0.138** | **0** | **25** |

## Detail: False negative patterns

| Pattern | Expected | Detected | Missed |
|---------|----------|----------|--------|
| amended_by | 32 | 6 | 26 |
| amended_to | 9 | 0 | 9 |
| amended_as_follows | 7 | 0 | 7 |
| deleting_inserting | 33 | 0 | 33 |
| is_hereby_waived | 0 | 0 | 0 |
| restated_entirety | 10 | 6 | 4 |
| deleted_from_section | 1 | 0 | 1 |

