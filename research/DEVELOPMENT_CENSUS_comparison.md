# Parser-Development Sample Census — v0.3.1 vs v0.4 Comparison

**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)
**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain
corpus that the reconstruction study ultimately requires.
**Gold annotations:** 77 total
**Metric type:** Instruction DETECTION. Matching uses span overlap +
instruction_type (with key-based fallback for gold without spans). Does NOT
verify extracted old_value, new_value, amount, exception, or actual semantic
mutation correctness.

## Pooled instruction-detection metrics comparison

| Metric | v0.3.1 | v0.4 |
|--------|--------|------|
| Gold annotations | 77 | 77 |
| Detected | 13 | 44 |
| True positives | 13 | 41 |
| False positives | 0 | 3 |
| False negatives | 64 | 36 |
| Precision | 1.000 | 0.932 |
| Recall | 0.169 | 0.532 |
| F1 | 0.289 | 0.678 |
| Unresolved | 0 | 0 |

## Key findings

- Recall improved from 0.169 to 0.532 (+0.364)
- Precision changed from 1.000 to 0.932 (-0.068)
- F1 improved from 0.289 to 0.678
- False positives: 0 → 3
- False negatives: 64 → 36
