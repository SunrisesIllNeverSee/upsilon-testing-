# Development Chain Study v2 — Freeze Record

**Frozen at**: commit fb0862d, tag `chain-study-v2-development`
**Frozen at UTC**: 2026-08-31T17:33:11+00:00 (run timestamp from results JSON)

## Frozen Artifacts

| File | SHA-256 |
|------|---------|
| chain_study_v2_report.md | 16166d494041529f4c930bc57789fcce1e44555ec0baf90c39de4ea9f30f64dc |
| chain_study_v2_results.json | 7d6f50bf7cde5ed72edd206619599b101ca5011ed146ce156235cf05c1351886 |

## Frozen System

- Parser v0.4.1 (frozen)
- Semantic Mapper v0.1 (frozen)
- S0 Commitment Extractor v0.1
- Authoritative GT Extractor v0.1
- Shared extraction engine (commitment_extractor.py)

## Frozen Results

- 25 real EDGAR chains (3 existing manual + 22 new automated)
- S0 extraction: 12/22 new chains (54.5% success, 40.3% avg coverage)
- GT extraction: 2/5 CMP chains (40.0% success, 25.0% avg coverage)
- Reconstruction: 40.0% chain-level exact (5 chains with GT)
- False authoritative promotions: 0 (PASS)

## Do Not Modify

These results are the development baseline. v0.2 changes will be measured
against this frozen reference. Do not rewrite, re-run, or modify these
files after the freeze.
