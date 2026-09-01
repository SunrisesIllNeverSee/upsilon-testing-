# Upsilon Financial Commitment Integrity v1 — Frozen Operational Build

**Frozen at UTC**: 2026-09-01T05:45:25.841501+00:00
**Git commit**: `5518f4a4d74e2fd2af2f0d1ac43e893bee845b93`
**Git tag**: `v1.0-frozen-operational-build`
**Branch**: feature/semantic-mapper-v0.1
**Working tree**: clean

## Frozen Artifacts

| File | SHA-256 |
|------|---------|
| CAPABILITY_STATEMENT.md | `d648d650fe0634bc250c4688a508438fae07a78a32cbca61a91165d236ecc781` |
| FINAL_DEVELOPMENT_REPORT.md | `baed5ea7e0ce0bdb21d681e29b9d497a41caf2eaa52f34c46b886f726fc4ffc4` |
| REPRODUCIBILITY.md | `e7799ff681b13c32eae2d01a303ffca24dc845eb786f84b878a05d5d47cbd2ae` |
| ci_status.json | `9ab2321dd9bbfe70d4c192250999f42e2fd753d3689c2b84e35ffb4ff6bb0ed2` |
| code_hashes.json | `8a1a434fbc58942a45b4bbae0a9d14b2996e0e2312e7c8d629fc3d1d88402eb5` |
| defect_diagnosis.json | `f351af31dfedd1279870339e7ebb03102770acf7f1558739858e0f7e7d3665fe` |
| failure_matrix.json | `6779d961a854ab0d86a661f288879e615506e38beaaaae3914541c83437425bc` |
| false_authoritative_promotion.json | `c17c8f9f0a5f8f209268d32aa4d990673ac2bd7a7d0088061af83efa09de5591` |
| final_report_sha256.txt | `eea4a8e45e6efe6f6a218c78684389e8191e0be4366b540103127be20923a260` |
| input_manifest.json | `d0407ef2623476753a57572c64c80bec1978095a8b700cf9cb410530d6748072` |
| postgresql_integrity.json | `2a7a21969e2c339955a81a9fe161b42891f4b69a7c10ef53123d10379cbc0213` |
| step_17b_results.json | `b0e706c11e28e03736eeaa7aeba7ed852bbaaf6dc80a24f82a7aaf2f255bba09` |
| test_results.json | `f2dc6577985a7723e0c43a2f1a9c55f14cf25c8cc7cba76fa271e923bb418b74` |
| v01_vs_v02_comparison.json | `8f6884c5335aa85104657eaab1cd6174d1a4aed31614dca1afd60ec5bae47c43` |

## Frozen System

- Parser v0.4.1 (frozen)
- Semantic Mapper v0.1 (frozen, with Step 17B defect fix)
- Executor (frozen)
- Persistence layer (frozen)
- S0 Commitment Extractor v0.1
- Authoritative GT Extractor v0.1
- Shared extraction engine (commitment_extractor.py)

## Foundation Safety Claim

- 0 incorrect automatic mutations after defect resolution
- 0 false authoritative promotions
- no detected lineage, temporal, or persistence integrity defects

## Do Not Modify

These artifacts are the frozen operational baseline. The held-out
confirmatory study (Step 19) will measure the same metrics on
untouched issuers. Do not rewrite, re-run, or modify these files
after the freeze.
