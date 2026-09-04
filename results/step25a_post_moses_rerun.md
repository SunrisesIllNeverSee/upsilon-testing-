# Step 25A — Post-MO§ES Re-Run of the Step 19B Corpus

**LABEL: POST-MO§ES RE-RUN / FIXED REGRESSION CORPUS (Step 25B RECONCILED)**

This is NOT a new held-out confirmatory result. The corpus was previously inspected and its failures influenced subsequent development.

**JSON artifact SHA-256:** `2801288ca304c5739c94a6b2ee81fd32f7a07e6ce650c19c608fb0d774d1f329`
**Baseline JSON SHA-256:** `9be51d60fa439d3deef3dcdfc07dd64b8928adf4b7cb31ff9c2735ccdb5bfe0f`
**Baseline Markdown SHA-256:** `dafdba102ba87f3afbfb5f19d02feb22fb5d2c91293dac36d20bd26eb2a233ba`

## 1. Run identity

- **Branch:** `main`
- **Commit:** `a16c9ae8db58cb412846e190eabffbd487f45465`
- **Corpus manifest SHA-256:** `2ef28f4e496b5d4dbe9d05b5dc1f993c8b562031f744787ddec67de646d00611`
- **Frozen GT manifest SHA-256:** `8fa3994a23a5ef8ec131b82ba1269eb261f19b9dbffbfa21e38f813b256a8316`
- **Timestamp:** `2026-09-04T02:08:49.684392+00:00`
- **Pipeline:** `run_semantic_pipeline_v2`

## 2. Corpus

| Metric | Value |
|---|---:|
| Chains attempted | 25 |
| Chains completed | 25 |
| Amendments | 152 |
| Documents | 180 |
| CMP/composite validation documents | 3 |

## 3. Step 19B baseline

| Metric | Step 19B value |
|---|---:|
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

## 4. Current results (reconciled)

### 4.1 S0 extraction

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| S0 extraction success | 25 | 25 | 100.00% |
| Total S0 commitments extracted | 44 | — | — |
| Avg S0 extraction coverage | — | — | 44.34% |

### 4.2 GT extraction

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| GT extraction success | 2 | 3 | 66.67% |
| Total GT commitments extracted | 3 | — | — |
| Avg GT extraction coverage | — | — | 27.78% |

### 4.3 Parser

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Total parser instructions | 306 | — | — |
| Amendments with ≥1 instruction | 81 | 152 | 53.29% |

### 4.4 Semantic interpretation (mapped ≠ accepted ≠ applied ≠ promoted)

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Mapped (total) | 30 | 306 | — |
| Mapped from parser | 3 | 306 | 0.98% |
| Mapped from extraction | 27 | — | — |
| Unresolved | 303 | 306 | 99.02% |

### 4.5 MOSES spine

| Outcome | Count |
|---|---:|
| Promoted | 0 |
| Rejected | 3 |
| Routed away | 27 |

### 4.6 Safety (CORRECTED: actual applied, not mapped)

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Mapped count | 30 | — | — |
| Accepted count | 30 | — | — |
| Applied mutation count | 0 | — | — |
| Authoritative promotion count | 0 | — | — |
| Incorrect applied mutations | 0 | 0 | N/A |
| False authoritative promotions | 0 | 25 | 0.00% |

> **Note:** 0 mutations were actually applied. Incorrect-accepted rate is N/A (no denominator). The 3 spine rejections prevented the incorrect mutations that Step 19B applied.

### 4.7 Precision (CORRECTED: only independently scorable)

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Mapped predictions | 30 | — | — |
| Independently scorable | 0 | — | — |
| Verified correct | 0 | — | — |
| Verified incorrect | 0 | — | — |
| Unscored | 30 | — | — |
| Overall precision | — | — | N/A |
| Parser-derived precision | — | — | N/A |
| Extraction-derived precision | — | — | N/A |

### 4.8 Reconstruction (CORRECTED: separate from GT coverage)

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| All-chains exact reconstruction | 1 | 25 | 4.00% |
| GT-scorable chains | 2 | 25 | 8.00% |
| GT exact reconstruction | 1 | 2 | 50.00% |
| GT unavailable chains | 23 | — | — |
| Supported-field GT agreement | 1 | 2 | 50.00% |

### 4.9 Lineage

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---|
| Lineage complete | 18 | 25 | 72.00% |
| Lineage incomplete | 7 | — | — |

## 5. Step 19B vs current comparison

| Metric | Step 19B | Current | Absolute change | Relative change |
|---|---:|---:|---:|---:|
| S0 extraction success | 28.00% | 100.00% | +72.00% | — |
| S0 avg coverage | 16.31% | 44.34% | +28.03% | — |
| GT extraction success | 66.67% | 66.67% | +0.00% | — |
| Amendments with parser instructions | 12.03% | 53.29% | +41.26% | — |
| Semantic mapping coverage | 0.96% | 0.98% | +0.02% | — |
| Mapping precision | 0.00% | N/A | NOT DIRECTLY COMPARABLE | — |
| Incorrect accepted mutation rate | 100.00% | N/A | NOT DIRECTLY COMPARABLE | — |
| Unresolved rate | 99.04% | 99.02% | +-0.02% | — |
| Supported-field GT agreement | 50.00% | 50.00% | — | — |
| Exact GT-chain reconstruction | 50.00% | 50.00% | — | — |
| Exact reconstruction overall | 4.00% | 4.00% | +0.00% | — |
| Lineage completeness | 88.00% | 72.00% | +-16.00% | — |
| False authoritative promotion rate | 0.00% | 0.00% | +0.00% | — |

## 6. Candidate ledger reconciliation

Total candidates: 30
Sum of terminal dispositions: 30
Conservation holds: True

Terminal dispositions:

| Disposition | Count |
|---|---:|
| REJECTED | 3 |
| ROUTED+LEGACY_UNRESOLVED | 27 |

### Row-by-row reconciliation: 3 parser + 57 extraction = 60 mapped

Parser-derived: 3 candidates
Extraction-derived: 27 candidates
Total: 30

Parser-derived candidates (all 3):

| ID | Chain | Amend | Family | Target | MOSES | Legacy | Mutated | Correct |
|---|---|---|---|---|---|---|---|---|
| CAND-0002 | HELD-009 | 2 | SCALAR_REPLACEMENT | facility.credit_agreement | rejected | not_attempted | False | not_scorable |
| CAND-0003 | HELD-012 | 10 | SCALAR_REPLACEMENT | facility.credit_agreement | rejected | not_attempted | False | not_scorable |
| CAND-0009 | HELD-016 | 9 | SCALAR_REPLACEMENT | facility.credit_agreement | rejected | not_attempted | False | not_scorable |

## 7. Chain reconstruction funnel

| Stage | Count | % of 25 |
|---|---:|---:|
| Total Chains | 25 | 100.0% |
| S0 Established | 25 | 100.0% |
| Instructions Available | 20 | 80.0% |
| At Least One Target Resolved | 10 | 40.0% |
| Executable Transformation Available | 0 | 0.0% |
| Successful State Transition | 0 | 0.0% |
| Complete Lineage | 18 | 72.0% |
| Independently Gt Scorable | 2 | 8.0% |
| Exact Reconstruction | 1 | 4.0% |

## 8. Instruction/transformation funnel

### Parser path

| Stage | Count |
|---|---:|
| Parser Instructions | 306 |
| Parser Derived Mappings | 3 |
| Moses Candidates | 3 |
| Moses Promoted | 0 |
| Moses Rejected | 3 |
| Moses Routed | 0 |
| Applied | 0 |
| Authoritative | 0 |
| Independently Scorable | 0 |

### Extraction path

| Stage | Count |
|---|---:|
| Extraction Derived Candidates | 27 |
| Classified | 27 |
| Target Resolved | 27 |
| Moses Candidate | 27 |
| Moses Promoted | 0 |
| Moses Rejected | 0 |
| Moses Routed | 27 |
| Legacy Attempted | 27 |
| Legacy Applied | 0 |
| Legacy Unresolved | 27 |
| Authoritative | 0 |
| Independently Scorable | 0 |

## 9. Transformation-family inventory

| Family | Total | Parser | Extract | MOSES_cand | Prom | Rej | Routed | Legacy_att | Legacy_appl | Legacy_unres | GT_scor | Correct | Incorrect |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CREATE | 27 | 0 | 27 | 27 | 0 | 0 | 27 | 27 | 0 | 27 | 0 | 0 | 0 |
| SCALAR_REPLACEMENT | 3 | 3 | 0 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 10. Lineage reconciliation

| Chain | Amend | S0 | Instr | Mapped | MOSES_cand | Prom | Rej | Routed | Legacy_appl | Unres | Lineage | GT | Exact | First failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| HELD-001 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | True | False | False | INSTRUCTION_DETECTION |
| HELD-002 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | True | True | True | INSTRUCTION_DETECTION |
| HELD-003 | 2 | 1 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | True | False | False | TARGET_RESOLUTION |
| HELD-004 | 2 | 2 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | False | True | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-005 | 2 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | True | False | False | TARGET_RESOLUTION |
| HELD-006 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | True | False | False | INSTRUCTION_DETECTION |
| HELD-007 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | True | False | False | INSTRUCTION_DETECTION |
| HELD-008 | 2 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | True | False | False | TARGET_RESOLUTION |
| HELD-009 | 2 | 1 | 4 | 1 | 1 | 0 | 1 | 0 | 0 | 3 | True | False | False | CONSERVATION_VALIDATION |
| HELD-010 | 14 | 2 | 82 | 0 | 0 | 0 | 0 | 0 | 0 | 82 | True | False | False | TARGET_RESOLUTION |
| HELD-011 | 13 | 2 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | True | False | False | TARGET_RESOLUTION |
| HELD-012 | 11 | 3 | 9 | 1 | 1 | 0 | 1 | 0 | 0 | 8 | True | False | False | CONSERVATION_VALIDATION |
| HELD-013 | 11 | 3 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | True | False | False | TARGET_RESOLUTION |
| HELD-014 | 11 | 2 | 24 | 5 | 5 | 0 | 0 | 5 | 0 | 24 | False | False | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-015 | 10 | 3 | 42 | 0 | 0 | 0 | 0 | 0 | 0 | 42 | True | False | False | TARGET_RESOLUTION |
| HELD-016 | 10 | 2 | 15 | 1 | 1 | 0 | 1 | 0 | 0 | 14 | True | False | False | CONSERVATION_VALIDATION |
| HELD-017 | 9 | 4 | 9 | 5 | 5 | 0 | 0 | 5 | 0 | 9 | False | False | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-020 | 9 | 1 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | True | False | False | TARGET_RESOLUTION |
| HELD-021 | 6 | 2 | 2 | 10 | 10 | 0 | 0 | 10 | 0 | 2 | False | False | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-022 | 8 | 1 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | True | False | False | TARGET_RESOLUTION |
| HELD-023 | 2 | 1 | 0 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | False | False | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-024 | 7 | 2 | 5 | 3 | 3 | 0 | 0 | 3 | 0 | 5 | False | False | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-025 | 4 | 1 | 8 | 1 | 1 | 0 | 0 | 1 | 0 | 8 | False | False | False | TRANSFORMATION_FAMILY_EXECUTION |
| HELD-R01 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | True | False | False | INSTRUCTION_DETECTION |
| HELD-R02 | 5 | 3 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 14 | True | False | False | TARGET_RESOLUTION |

Lineage complete: 18/25 = 72.00%

### Step 19B → current lineage change: 88% → 60%

The lineage completeness decrease is caused by:
- The v2 pipeline marks steps with UNRESOLVED execution status when
  the legacy executor cannot process routed-away candidates
- The v1 pipeline marked these steps as COMPLETE because it applied
  mutations (including incorrect ones) without conservation validation
- The definition is the same (all steps COMPLETE + origin state)
- The change is a REAL regression in the metric, caused by the spine
  correctly rejecting bad mutations and the legacy executor correctly
  refusing to process unsupported transformation families

## 11. Chain-level bottleneck ranking

| Failure Stage | Chains | Denominator | % |
|---|---:|---:|---:|
| TARGET_RESOLUTION | 10 | 25 | 40.0% |
| TRANSFORMATION_FAMILY_EXECUTION | 7 | 25 | 28.0% |
| INSTRUCTION_DETECTION | 5 | 25 | 20.0% |
| CONSERVATION_VALIDATION | 3 | 25 | 12.0% |

## 12. Recoverable engineering-opportunity ranking

| Family | Blocked | Denom | Affected chains | Scorable | Recoverable | Evidence level | Next blocker |
|---|---:|---:|---:|---:|---:|---|---|
| TRANSFORMATION_FAMILY_EXECUTION | 27 | 30 | 7 | 1 | 0 | BOUNDED_UPPER_LIMIT | VALUE_EXTRACTION and CONSERVATION_VALIDATION — routed candidates have not been evaluated through the MOSES spine, so their conservation and value correctness are unknown. |
| GROUND_TRUTH_COVERAGE | 23 | 25 | 23 | 0 | 0 | BOUNDED_UPPER_LIMIT | N/A (observability, not runtime) |
| TARGET_RESOLUTION | 10 | 25 | 10 | 0 | 0 | BOUNDED_UPPER_LIMIT | VALUE_EXTRACTION |
| INSTRUCTION_DETECTION | 5 | 25 | 5 | 1 | 0 | BOUNDED_UPPER_LIMIT | TARGET_RESOLUTION |
| S0_EXTRACTION | 0 | 25 | 0 | 0 | 0 | BOUNDED_UPPER_LIMIT | TARGET_RESOLUTION (for chains with instructions) or INSTRUCTION_DETECTION (for chains without) |

## 13. Evaluation observability / GT coverage

| Metric | Value |
|---|---|
| Total chains | 25 |
| GT-scorable chains | 2 |
| GT unavailable chains | 23 |
| GT coverage | 8.00% |

GT availability is NOT a runtime failure. Chains without GT executed
successfully but cannot be scored for reconstruction correctness.

## 14. Determinism proof

Determinism gate: 64 matched, 0 mismatched. ALL METRICS MATCH — deterministic.

## 15. Tests

See verification section in the final report.

## 16. Next target

See final report.
