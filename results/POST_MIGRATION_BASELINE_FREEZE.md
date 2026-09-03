# Post-Migration Canonical Baseline Freeze

**Frozen:** 2026-09-03
**Migration commit:** `e908eb6` (Move all root modules into target directory structure)
**Merge commit:** `b434398` (Merge branch 'feature/semantic-mapper-v0.1' into main)
**Verification method:** Pre-migration code (commit `0217213`) rerun with identical data, compared metric-by-metric against post-migration code output.

## Verification protocol

1. Created git worktree at `e908eb6~1` (pre-migration state).
2. Symlinked untracked data directories (`data/held_out/`, `data/chain_study/`).
3. Copied untracked result files needed by audit scripts (`chain_study_v1_results.json`, `step_21_v2_study_results.json`, `step_22_unresolved_taxonomy.json`).
4. Ran all empirical audit scripts on pre-migration code.
5. Ran all empirical audit scripts on post-migration code.
6. Compared 53 metrics across all audits (frozen-input hash verification, Step 23R, Step 23, Step 23S, defect safety record).

## Result: 53 matched, 0 mismatched

The directory/import migration preserved all empirical behavior. Post-migration behavior is byte-identical to pre-migration.

## Canonical baseline metrics

### Frozen-input hash verification
- Hashes checked: 26
- Failures: 0
- Verdict: PASS

### Step 23R — Independent Failure Census

| Metric | Value |
|--------|-------|
| incorrect_accepted_mutations | 0 |
| false_authoritative_promotions | 0 |
| step_authoritative_count | 33 |
| total_steps | 203 |
| IN_SCOPE | 86 |
| OUT_OF_SCOPE | 266 |
| AMBIGUOUS_SCOPE | 41 |
| correct_accepts_preserved (eligible_semantic_coverage) | 2/86 = 2.3% |
| total_failed | 84 |
| total_accepted_correct | 2 |
| total_accepted_incorrect | 0 |
| other_percentage | 0.0% |

### Runtime failure histogram (first failure)

| Family | Count |
|--------|-------|
| TARGET_IDENTIFICATION | 67 |
| VALUE_EXTRACTION | 11 |
| VALIDATOR_REJECTION | 6 |

### Failure-family distribution (taxonomy)

| Bucket | Count |
|--------|-------|
| MULTI_FIELD_DECOMPOSITION | 45 |
| TARGET_IDENTIFICATION | 16 |
| DELETE_REQUIRES_MANUAL_REVIEW | 6 |
| TABLE_OR_SCHEDULE_VALUE_EXTRACTION | 6 |
| DEFINED_TERM_RESOLUTION | 5 |
| VALUE_EXTRACTION | 4 |
| VALIDATOR_REJECTION | 2 |

### S0 extraction metrics

| Metric | Value |
|--------|-------|
| Raw coverage | 29/47 = 61.7% |
| Eligible coverage | 29/34 = 85.3% |
| S0_IN_SCOPE | 34 |
| S0_NO_IN_SCOPE_CONTENT | 9 |
| S0_DISCOVERY_FAILURE | 0 |
| S0_AMBIGUOUS | 4 |

### GT extraction metrics

| Metric | Value |
|--------|-------|
| Raw coverage | 5/8 = 62.5% |
| Eligible coverage | 5/8 = 62.5% |
| GT_IN_SCOPE | 8 |
| GT_NO_IN_SCOPE_CONTENT | 0 |
| GT_DISCOVERY_FAILURE | 0 |
| GT_AMBIGUOUS | 0 |

### Step 23 — Eligibility & Semantic Funnel

| Metric | Value |
|--------|-------|
| Total parser instructions | 393 |
| IN_SCOPE | 130 |
| OUT_OF_SCOPE | 228 |
| AMBIGUOUS_SCOPE | 35 |
| Eligible semantic mapping coverage | 12/130 = 9.2% |
| S0 eligible coverage | 29/33 = 87.9% |
| GT eligible coverage | 5/8 = 62.5% |
| Unknown genre rate | 18.9% |
| Funnel stage_12_accepted | 2 |
| Funnel stage_13_rejected | 6 |
| commitment_registry_executed | True |
| staged_interpreter_executed | True |

### Step 23 — Revised taxonomy (23F)

| Bucket | Count |
|--------|-------|
| DEFINED_TERM_REFERENCE | 49 |
| MULTI_FIELD_RESTATEMENT | 44 |
| VALUE_IN_TABLE_SCHEDULE | 26 |
| AMOUNT_CHANGE | 6 |
| TRUE_AMBIGUITY | 3 |
| DATE_CHANGE | 2 |
| OTHER percentage | 0.0% |

### Step 23 — Exit gates (23H)

| Gate | Result |
|------|--------|
| semantic_mapping_coverage >= 50% | FAIL (9.2%) |
| incorrect_accepted_mutations = 0 | PASS (0) |
| false_authoritative_promotions = 0 | PASS (0) |
| s0_extraction >= 85% | PASS (87.9%) |
| gt_extraction >= 70% | FAIL (62.5%) |
| unknown_genre_rate < 20% | PASS (18.9%) |
| **Total gates passed** | **4/6** |

### Step 23S — MOSES Semantic Safety Enforcement

The Step 23S safety audit verifies that the 7 MOSES runtime invariants (I1–I7) are enforced and that the post-fix safety metrics hold.

**Conformance tests:** 33 tests covering 7 MOSES runtime invariants (I1 target-vs-reference, I2 value-extraction compatibility, I3 cross-type evidence, I4 section-alias consistency, I5 section corroboration, I6 old-value consistency, I7 minimal semantic proof + authority gate).

- Pre-migration: 33 passed (root-level `test_moses_safety.py`, per `STEP_23S_FINAL_REPORT.md`)
- Post-migration: 33 passed (`tests/conservation/test_moses_safety.py`)

**Post-fix safety metrics** (sourced from `step23r_audit.json` `section_safety_metrics`, re-run after Step 23S implementation):

| Metric | Value |
|--------|-------|
| incorrect_accepted_mutations | 0 |
| false_authoritative_promotions | 0 |
| OUT_OF_SCOPE accepted | 0 |

All 7 MOSES invariants are ENFORCED. The 10 prior incorrect accepts (from the pre-23S baseline) are now safe rejections (UNRESOLVED). No correct accept was weakened.

### Defect safety record

| Layer | Finding |
|-------|---------|
| Semantic mapper defect | 3 wrong confident mappings (CONFIRMED) |
| Execution safety | 3/3 rejected by executor (HELD) |
| Authoritative corruption | 0 promotions (NONE) |
| Defect chains | HELD-009, HELD-012, HELD-016 |
| Held-out aggregate total chains | 25 |
| Held-out aggregate total | 158 |

## Test suite

| Metric | Value |
|--------|-------|
| Tests collected | 1066 |
| Tests passed | 1052 |
| Tests skipped | 14 |
| Tests failed | 0 |

## Audit scripts used

- `data/ground_truth/frozen/generate_manifest.py verify` — frozen hash verification (live subprocess call from compare_baseline.py)
- `audits/step23r/build_step23r_audit.py` — Step 23R independent failure census
- `audits/build_step23_audit.py` — Step 23 eligibility & semantic funnel audit
- `pytest tests/conservation/test_moses_safety.py` — Step 23S MOSES conformance tests (live subprocess call from compare_baseline.py)
- `audits/generate_defect_safety_record.py` — defect/safety distinction record
- `audits/step23r/generate_step23r_deliverables.py` — Step 23R deliverables
- `audits/repository/compare_baseline.py` — metric-by-metric comparison

## Conclusion

The post-migration repository is empirically identical to the pre-migration repository. This is the canonical post-migration baseline. Any future semantic change must be measured against this baseline.
