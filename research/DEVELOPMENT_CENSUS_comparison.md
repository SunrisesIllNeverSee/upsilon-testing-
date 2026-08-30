# Parser-Development Sample Census — v0.3.1 vs v0.4 Comparison

**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)
**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain
corpus that the reconstruction study ultimately requires.
**Gold annotations:** 77 total

## Pooled metrics comparison

| Metric | v0.3.1 | v0.4 |
|--------|--------|------|
| Gold annotations | 77 | 77 |
| Detected | 13 | 46 |
| True positives | 11 | 38 |
| False positives | 2 | 8 |
| False negatives | 66 | 39 |
| Precision | 0.846 | 0.826 |
| Recall | 0.143 | 0.494 |
| F1 | 0.244 | 0.618 |
| Unresolved | 0 | 0 |

## Key findings

- Recall improved from 0.143 to 0.494 (+0.351)
- Precision changed from 0.846 to 0.826 (-0.020)
- F1 improved from 0.244 to 0.618
- False positives: 2 → 8
- False negatives: 66 → 39
