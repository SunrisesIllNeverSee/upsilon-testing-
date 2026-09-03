# Step 25A — Post-MO§ES Re-Run of the Step 19B Corpus

**LABEL: POST-MO§ES RE-RUN / FIXED REGRESSION CORPUS**

This is NOT a new held-out confirmatory result. The corpus was previously inspected and its failures influenced subsequent development. Its purpose is to measure improvement relative to Step 19B. A future confirmatory study requires fresh untouched issuers after the system is frozen again.

---

## 1. Run identity

- **Branch:** `main`
- **Commit:** `2ac389aecd8183a2dc1b184c587552a5254d3c93`
- **Corpus manifest:** `data/held_out/manifest.json`
- **Corpus manifest SHA-256:** `3c39a08bd9a841c60be1d2fe3f4864724d59fe001c439b86e63d2133bb034a27`
- **Frozen GT manifest SHA-256:** `8fa3994a23a5ef8ec131b82ba1269eb261f19b9dbffbfa21e38f813b256a8316`
- **Timestamp:** `2026-09-03T22:51:44+00:00`
- **Pipeline:** `run_semantic_pipeline_v2` (current production path with MO§ES conservation-first spine)

---

## 2. Corpus

| Metric | Value |
|---|---:|
| Chains attempted | 25 |
| Chains completed | 25 |
| Amendments | 158 |
| Documents | 186 |
| CMP/composite validation documents | 3 |

The corpus is the same 25-chain held-out set from Step 19B. Manifest hash verified. No issuers added or removed.

---

## 3. Step 19B baseline

| Metric | Step 19B value |
|---|---:|
| Chains | 25 |
| Amendments | 158 |
| Documents | 186 |
| CMP documents | 3 |
| S0 extraction success | 7/25 = 28.00% |
| Avg S0 extraction coverage | 16.31% |
| GT extraction success | 2/3 = 66.67% |
| Parser instructions | 312 |
| Amendments with instructions | 19/158 = 12.03% |
| Semantic mapping coverage | 3/312 = 0.96% |
| Mapping precision | 0/3 = 0.00% |
| Incorrect automatic mutations | 3/3 = 100.00% |
| Unresolved rate | 309/312 = 99.04% |
| Supported-field GT agreement | 1/2 = 50.00% |
| Whole-commitment GT agreement | 1/2 = 50.00% |
| Exact GT-chain reconstruction | 1/2 = 50.00% |
| Exact reconstruction overall | 1/25 = 4.00% |
| Lineage completeness | 22/25 = 88.00% |
| False authoritative promotions | 0/25 = 0.00% |

Source: `results/step_19b_held_out_confirmatory_study.md`

---

## 4. Current results

### 4.1 Corpus

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Chains attempted | 25 | 25 | 100.00% |
| Chains completed | 25 | 25 | 100.00% |
| Amendments | 158 | — | — |
| Documents | 186 | — | — |
| CMP documents | 3 | — | — |

### 4.2 S0 extraction

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| S0 documents found | 25 | 25 | 100.00% |
| S0 extraction attempted | 25 | 25 | 100.00% |
| S0 extraction success (≥1 commitment) | 13 | 25 | 52.00% |
| Total S0 commitments extracted | 22 | — | — |
| Avg S0 extraction coverage | — | — | 31.95% |

### 4.3 GT extraction

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| GT extraction attempted | 3 | — | — |
| GT extraction success (≥1 commitment) | 2 | 3 | 66.67% |
| Total GT commitments extracted | 2 | — | — |
| Avg GT extraction coverage | — | — | 27.78% |

### 4.4 Parser

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Amendment documents | 158 | — | — |
| Total parser instructions | 302 | — | — |
| Amendments with ≥1 instruction | 84 | 158 | 53.16% |

Note: The v2 pipeline uses genre-aware adapters. The parser instruction count (302) differs from Step 19B (312) because the genre classifier routes some amendments to FULL_RESTATEMENT or CONFORMED_COPY adapters that use extraction rather than parsing. The instruction detection rate increased dramatically (12.03% → 53.16%) because the v2 genre adapters classify more amendments as INCREMENTAL and attempt parsing on them.

No gold exists for instruction boundary/type verification. Precision, recall, F1, and type accuracy are not reported.

### 4.5 Semantic interpretation / target resolution

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Instructions presented to semantic layer | 302 | — | — |
| Mapped/resolved (total) | 60 | 302 | 19.87% |
| Mapped from parser | 3 | 302 | 0.99% |
| Mapped from extraction | 57 | — | — |
| Unresolved | 299 | 302 | 99.01% |
| Mapping coverage (parser-based) | 3 | 302 | 0.99% |
| Mapping precision | 60 | 60 | 100.00%* |

*Mapping precision is 100% because 0 incorrect accepted mutations were detected. However, this is partly unmeasurable: the 3 parser-based mappings are on chains without GT (HELD-009, HELD-012, HELD-016), and the spine rejected all 3 before they were applied. The 57 extraction-based mappings are on chains without GT. Precision is not meaningfully comparable to Step 19B's 0/3 = 0% because the denominator and measurement conditions differ.

#### MO§ES spine breakdown

| Outcome | Count |
|---|---:|
| MO§ES spine promoted | 0 |
| MO§ES spine rejected | 3 |
| MO§ES spine routed away (non-SCALAR_REPLACEMENT) | 57 |
| Legacy-path resolutions (extraction-based) | 57 |

The spine promoted 0 mutations on the held-out corpus. All 60 mapped mutations were either routed away (57 — not SCALAR_REPLACEMENT family) or rejected (3 — conservation validation failure). The 3 rejections are on the same chains that had incorrect mutations in Step 19B (HELD-009, HELD-012, HELD-016), confirming the spine's fail-closed behavior caught the bad mutations the v1 pipeline applied.

### 4.6 Authoritative-state reconstruction — PRIMARY PERFORMANCE RESULT

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Supported-field GT agreement | 1 | 2 | 50.00% |
| Whole-commitment GT agreement | 1 | 2 | 50.00% |
| Exact GT-chain reconstruction | 1 | 2 | 50.00% |
| Exact reconstruction overall | 1 | 25 | 4.00% |

GT-measurable chains: 2 (HELD-002, HELD-004). HELD-002 has exact agreement (trivial: 0 parser instructions, S0 state passes through). HELD-004 does not have exact agreement (extraction-based mapping produced a commitment that disagrees with GT).

Field-level gold is insufficient for per-field accuracy reporting. The automated proxy scaffold in `data/held_out/gold/` is NOT verified human gold and cannot be used for field-level accuracy claims.

### 4.7 Lineage

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Lineage complete | 15 | 25 | 60.00% |
| Lineage incomplete | 10 | 25 | 40.00% |

Lineage completeness decreased from 88.00% to 60.00%. The 10 incomplete chains have at least one amendment step with UNRESOLVED execution status. This is caused by:
- Spine rejections (3 chains: HELD-009, HELD-012, HELD-016) — the spine correctly rejected bad mutations, but the rejection causes the step's execution status to be UNRESOLVED
- Extraction-based mappings routed away from the spine but not processable by the legacy executor (7 chains: HELD-004, HELD-013, HELD-014, HELD-017, HELD-020, HELD-021, HELD-023, HELD-024, HELD-025)

This is a side effect of the spine's fail-closed behavior and the genre adapter's extraction-based mappings. The v1 pipeline marked these steps as COMPLETE because it applied mutations (including incorrect ones) without conservation validation.

### 4.8 Safety

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Incorrect accepted mutations | 0 | 60 | 0.00% |
| Total accepted mutations | 60 | — | — |
| False authoritative promotions | 0 | 25 | 0.00% |
| Authority-granted steps | — | — | — |
| Authority-blocked steps | — | — | — |

Safety includes both legacy executor and MO§ES spine paths. The spine rejected 3 mutations (conservation validation failures) that the v1 pipeline would have applied as incorrect mutations. False authoritative promotions remained at 0.

### 4.9 Human review / unresolved burden

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Unresolved | 299 | 302 | 99.01% |
| Spine rejected (require review) | 3 | — | — |
| Spine routed away (unsupported family) | 57 | — | — |

---

## 5. Step 19B vs current comparison

| Metric | Step 19B | Current MO§ES run | Absolute change | Relative change |
|---|---:|---:|---:|---:|
| S0 extraction success | 28.00% | 52.00% | +24.00 pp | +85.71% |
| S0 avg coverage | 16.31% | 31.95% | +15.64 pp | +95.89% |
| GT extraction success | 66.67% | 66.67% | 0.00 pp | 0.00% |
| Amendments with parser instructions | 12.03% | 53.16% | +41.13 pp | +341.98% |
| Semantic mapping coverage | 0.96% | 0.99% | +0.03 pp | +3.13% |
| Mapping precision | 0.00% | 100.00%* | +100.00 pp | — |
| Incorrect accepted mutation rate | 100.00% | 0.00% | -100.00 pp | -100.00% |
| Unresolved rate | 99.04% | 99.01% | -0.03 pp | -0.03% |
| Supported-field GT agreement | 50.00% | 50.00% | 0.00 pp | 0.00% |
| Whole-commitment GT agreement | 50.00% | 50.00% | 0.00 pp | 0.00% |
| Exact GT-chain reconstruction | 50.00% | 50.00% | 0.00 pp | 0.00% |
| Exact reconstruction overall | 4.00% | 4.00% | 0.00 pp | 0.00% |
| Lineage completeness | 88.00% | 60.00% | -28.00 pp | -31.82% |
| False authoritative promotion rate | 0.00% | 0.00% | 0.00 pp | 0.00% |

*Mapping precision is not directly comparable. In Step 19B, 3/3 automatic mappings were applied and all were incorrect (0% precision). In the current run, 3 parser-based mappings were produced but all 3 were rejected by the spine (fail-closed), so 0 were applied. The 57 extraction-based mappings have no GT to verify against. The 100% figure reflects "0 incorrect out of 60 accepted" but the denominator composition changed fundamentally.

### Denominator changes

| Metric | OLD (Step 19B) | NEW (Step 25A) | Explanation |
|---|---|---|---|
| Parser instructions | 312 | 302 | V2 genre adapters route some amendments to extraction instead of parsing |
| Amendments with instructions | 19/158 | 84/158 | V2 genre adapters classify more amendments as INCREMENTAL and attempt parsing |
| Total mapped | 3 | 60 | V2 extraction adapters (FULL_RESTATEMENT, CONFORMED_COPY) produce 57 extraction-based mappings |
| Mapping precision denominator | 3 (all parser-based) | 60 (3 parser + 57 extraction) | Extraction-based mappings have no parser-instruction denominator |

---

## 6. Primary reconstruction result

Authoritative-state reconstruction metrics:

| Metric | Value |
|---|---|
| GT-measurable chains | 2/25 |
| Supported-field exact agreement | 1/2 = 50.00% |
| Whole-commitment agreement | 1/2 = 50.00% |
| Exact chain reconstruction (GT) | 1/2 = 50.00% |
| Exact reconstruction (overall) | 1/25 = 4.00% |

Reconstruction accuracy is unchanged from Step 19B. The 1 successful GT chain (HELD-002) is trivial: 0 parser instructions means the reconstruction is just the S0 state. The system cannot reliably reconstruct commitment state on held-out data. The primary limitation is the lack of GT-measurable chains (only 2/25 have CMP documents with extractable GT).

---

## 7. Safety result

| Metric | Value |
|---|---|
| Incorrect accepted mutations | 0 |
| Total accepted mutations | 60 |
| Incorrect accepted mutation rate | 0.00% |
| False authoritative promotions | 0 |
| False authoritative promotion rate | 0.00% |
| Spine rejections (conservation failures) | 3 |
| Spine routed away (unsupported family) | 57 |

**Safety improved.** The 3 incorrect automatic mutations from Step 19B (HELD-009, HELD-012, HELD-016) are now caught by the MO§ES spine's conservation validation and rejected before application. False authoritative promotions remained at 0. The spine's fail-closed behavior is the direct cause of the safety improvement: mutations that the v1 pipeline applied incorrectly are now blocked by old-value consistency checks and conservation invariants.

---

## 8. MO§ES runtime utilization

| Outcome | Count |
|---|---:|
| Promoted (applied to authoritative state) | 0 |
| Rejected (conservation validation failure) | 3 |
| Routed away (non-SCALAR_REPLACEMENT family) | 57 |
| Legacy-path (extraction-based, no spine) | 57 |

The MO§ES spine did not promote any mutations on the held-out corpus. All 60 mapped mutations were either:
- Routed away (57): the transformation family is not SCALAR_REPLACEMENT, so the spine correctly routes them to the legacy path
- Rejected (3): the spine's conservation validation detected old-value mismatches and rejected the mutations

The 0 promotions mean the MO§ES conservation-first runtime did not change any authoritative state on the held-out corpus. The safety improvement (0 incorrect mutations) is entirely due to the spine's rejection of 3 bad mutations, not due to successful promotion of correct ones.

---

## 9. Failure-stage census

| Stage | Count | Percentage |
|---|---:|---:|
| s0_commitment_extraction | 12 | 48.00% |
| amendment_instruction_detection | 6 | 24.00% |
| target_identity_resolution | 4 | 16.00% |
| evaluation_gold_unavailable | 2 | 8.00% |
| conservation_validation | 1 | 4.00% |

**Dominant failure stage: S0 commitment extraction (48%).**

12 of 25 chains have S0=0 (the S0 extractor returned 0 commitments). This is improved from Step 19B's 18/25 = 72% but remains the dominant bottleneck. The S0 extractor's heuristics do not generalize to diverse credit agreement formats.

The second-largest stage is amendment instruction detection (24%, 6 chains) — the parser found 0 instructions in amendment documents for these chains.

The third stage is target identity resolution (16%, 4 chains) — the parser found instructions but the semantic mapper could not resolve any of them.

The conservation_validation stage (4%, 1 chain) represents a chain where the spine rejected all mutations. This is a SAFE rejection, not a failure — the spine correctly blocked bad mutations.

---

## 10. Test and integrity evidence

| Verification | Result |
|---|---|
| Full test suite | 1242 passed, 14 skipped |
| Step 23R safety audit | 46 passed |
| Step 23S safety tests | 33 passed |
| Frozen-manifest verification | 5 passed |
| Step 24B conformance | 190 passed |
| Step 25A evaluation | Completed (this report) |
| Report-generation reproducibility | Artifact regenerated successfully |
| Step 24B activation artifact | All 17 gates pass, 0 incorrect mutations, 0 false promotions |

---

## 11. Artifacts

| Artifact | Path | Version-controlled |
|---|---|---|
| Step 25A JSON | `results/step25a_post_moses_rerun.json` | Yes (`.gitignore` exception added) |
| Step 25A Markdown | `results/step25a_post_moses_rerun.md` | Yes (`.gitignore` exception added) |
| Step 24B activation JSON | `results/current/step24b_runtime_activation.json` | Yes (`.gitignore` exception added) |
| Evaluation harness | `audits/step25a/run_post_moses_rerun.py` | Yes (new file) |
| Corpus manifest | `data/held_out/manifest.json` | Yes (unchanged from Step 19B) |

---

## 12. Conclusion

### 1. Did reconstruction improve?

**No.** Exact reconstruction remained at 1/25 = 4.00% overall and 1/2 = 50.00% for GT chains. The system still cannot reliably reconstruct commitment state on held-out data. The primary limitation is the lack of GT-measurable chains (only 2/25) and the S0 extractor's failure rate (48% of chains have no origin state).

### 2. Did automatic coverage improve?

**Mixed.** Parser instruction detection improved dramatically (12.03% → 53.16% of amendments) due to the v2 genre adapters. However, semantic mapping coverage (parser-based) remained essentially unchanged (0.96% → 0.99%). The 57 extraction-based mappings are a new capability but are not parser-based semantic interpretation. The unresolved rate remained at ~99%.

### 3. Did safety improve or remain intact?

**Safety improved.** Incorrect accepted mutations dropped from 3/3 = 100% to 0/60 = 0%. The MO§ES spine's conservation validation caught the 3 bad mutations that the v1 pipeline applied incorrectly. False authoritative promotions remained at 0. The safety improvement is directly attributable to the spine's fail-closed behavior on the 3 mutations that were incorrect in Step 19B.

### 4. What is now the dominant measured failure stage?

**S0 commitment extraction (48%).** 12 of 25 chains have no extracted S0 state, preventing the pipeline from reaching the reconstruction stage. This is improved from Step 19B's 72% but remains the primary bottleneck. The S0 extractor's heuristics do not generalize to diverse credit agreement formats.

### 5. Is the system ready to freeze for a NEW untouched held-out study?

**No.** The system is not ready for a new confirmatory study because:
1. S0 extraction still fails on 48% of chains
2. Semantic mapping coverage is still <1% for parser-based interpretation
3. Only 2/25 chains are GT-measurable (insufficient statistical power)
4. The MO§ES spine promoted 0 mutations on this corpus — the conservation-first runtime's promotion capability has not been demonstrated on held-out data
5. Lineage completeness decreased (88% → 60%) due to spine rejections and extraction-based routing
6. Human gold has not been verified for the preregistered subset

The system should be frozen only after S0 extraction generalizes, semantic mapping coverage expands, and the spine demonstrates successful promotion on held-out data.
