# Parser-Development Sample Census — v0.3.1 Baseline

**Parser:** v0.3.1 (deterministic_baseline_v0.3) (tag: dev-baseline-v0.3.1)
**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)
**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain
corpus (original + multiple amendments per issuer) that the reconstruction
study ultimately requires.
**Gold annotations:** data/development/gold_annotations.json (77 total)
**Methodology:** TP/FP/FN computed from explicit gold annotations.
Precision = TP / (TP + FP), Recall = TP / (TP + FN), F1 = 2PR / (P + R).
**Metric type:** Instruction DETECTION. Matching uses span overlap +
instruction_type (with key-based fallback for gold without spans). Does
NOT verify extracted old_value, new_value, amount, exception, or actual
semantic mutation correctness. Full reconstruction accuracy is a separate
measurement.

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

## Table 2 — Instruction-detection performance by format

| Format | Precision | Recall | F1 | Unresolved | Docs |
|--------|-----------|--------|----|------------|------|
| Inline | 0.538 | 0.096 | 0.163 | 0 | 20 |
| Composite | N/A | N/A | N/A | 0 | 0 |
| Restated | N/A | N/A | N/A | 0 | 0 |
| Referential | N/A | N/A | N/A | 0 | 0 |
| Waiver | 1.000 | 1.000 | 1.000 | 0 | 1 |
| Mixed | 1.000 | 0.000 | 0.000 | 0 | 4 |
| **All amendment documents** | **0.538** | **0.091** | **0.156** | **0** | **25** |

## Pooled summary

| Metric | Value |
|--------|-------|
| Gold annotations | 77 |
| Detected | 13 |
| True positives | 7 |
| False positives | 6 |
| False negatives | 70 |
| Precision | 0.538 |
| Recall | 0.091 |
| F1 | 0.156 |
| Unresolved | 0 |

