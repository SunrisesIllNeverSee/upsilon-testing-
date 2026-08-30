# Parser-Development Sample Census — v0.3.1 vs v0.4 Comparison

**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)
**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain
corpus that the reconstruction study ultimately requires.
**Gold annotations:** 77 total
**Metric type:** Instruction DETECTION. Matching is by (normalized target_ref,
instruction_type) only. Does NOT verify extracted old_value, new_value, amount,
exception, or actual semantic mutation correctness.

## Pooled instruction-detection metrics comparison

| Metric | v0.3.1 | v0.4 |
|--------|--------|------|
| Gold annotations | 77 | 77 |
| Detected | 13 | 44 |
| True positives | 11 | 36 |
| False positives | 2 | 8 |
| False negatives | 66 | 41 |
| Precision | 0.846 | 0.818 |
| Recall | 0.143 | 0.468 |
| F1 | 0.244 | 0.595 |
| Unresolved | 0 | 0 |

## Key findings

- Recall improved from 0.143 to 0.468 (+0.325)
- Precision changed from 0.846 to 0.818 (-0.028)
- F1 improved from 0.244 to 0.595
- False positives: 2 → 8
- False negatives: 66 → 41
