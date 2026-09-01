# Upsilon Financial Commitment Integrity v1 — Frozen Operational Build

**Frozen at UTC**: 2026-09-01T05:48:44.147775+00:00
**Git commit**: `9771fe5db5f672c3d653ef2a9ba1fc54ffd08900`
**Git tag**: `v1.0-frozen-operational-build`
**Branch**: feature/semantic-mapper-v0.1
**Working tree**: clean

## Frozen Artifacts

| File | SHA-256 |
|------|---------|
| CAPABILITY_STATEMENT.md | `abc5bd9a98d729a4e5a645c0655d629d6a793de0191f7f99c6b613972845cba9` |
| FINAL_DEVELOPMENT_REPORT.md | `17fca4e7e4bdf22a9ebdd2fe6e224fd0fffc55d38de2e2a6b882c51e6cfc6555` |
| REPRODUCIBILITY.md | `60a077baa9119d36fbe7d02c468d81c73764cddfe1a6a9fffbebd2b4974de15d` |
| ci_status.json | `eb5f914f957e5ecb8fee76f3ac217847bddcc64e38facc96706ce0fd94a35071` |
| code_hashes.json | `8a1a434fbc58942a45b4bbae0a9d14b2996e0e2312e7c8d629fc3d1d88402eb5` |
| defect_diagnosis.json | `f351af31dfedd1279870339e7ebb03102770acf7f1558739858e0f7e7d3665fe` |
| failure_matrix.json | `6779d961a854ab0d86a661f288879e615506e38beaaaae3914541c83437425bc` |
| false_authoritative_promotion.json | `c17c8f9f0a5f8f209268d32aa4d990673ac2bd7a7d0088061af83efa09de5591` |
| final_report_sha256.txt | `65a20cf1cd3b13b05f5516a919e3596e67bda7c63dd606961da81216a4b74a48` |
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
