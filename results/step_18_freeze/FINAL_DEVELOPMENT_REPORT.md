# Upsilon Financial Commitment Integrity v1 — Frozen Operational Build

**Frozen at UTC**: 2026-09-01T05:45:25.841501+00:00
**Git commit**: `5518f4a4d74e2fd2af2f0d1ac43e893bee845b93`
**Git tag**: `v1.0-frozen-operational-build`
**Branch**: feature/semantic-mapper-v0.1
**Working tree**: clean

---

## 1. System Identity

- **System**: Upsilon Financial Commitment Integrity v1
- **Frozen components**:
  - Parser v0.4.1 (frozen)
  - Semantic Mapper v0.1 (frozen, with Step 17B defect fix)
  - Executor (frozen)
  - Persistence layer (frozen)
  - S0 Commitment Extractor v0.1
  - Authoritative GT Extractor v0.1
  - Shared extraction engine (commitment_extractor.py)
  - Semantic pipeline orchestrator

## 2. Final Development Metrics

### 2.1 Foundation Safety

- **Incorrect automatic mutations**: 0
- **Incorrect automatic mutation rate**: 0.0
- **False authoritative promotions**: 0
- **False authoritative promotion rate**: 0.0

### 2.2 Extraction

- **S0 extraction success rate**: 0.7273
- **GT extraction success rate**: 0.4
- **S0 extraction coverage (avg)**: 0.4925
- **GT extraction coverage (avg)**: 0.2133
- **Chains with extracted S0**: 16
- **Chains with extracted GT**: 2
- **Total S0 commitments extracted**: 38
- **Total GT commitments extracted**: 8

### 2.3 Transformation

- **Total parser instructions**: 91
- **Total mapped instructions**: 3
- **Total unresolved**: 88
- **Semantic mapping precision**: 1.0
- **Semantic mapping coverage**: 0.033
- **Unresolved rate**: 0.967

### 2.4 Reconstruction

- **Chain-level exact reconstruction rate**: 0.4
- **Lineage completeness rate**: 1.0
- **Total chains**: 25
- **Total amendments**: 80

### 2.5 v0.1 vs v0.2 Comparison

| Metric | v0.1 | v0.2 |
|--------|------|------|
| total_parser_instructions | 91 | 91 |
| total_mapped_instructions | 6 | 3 |
| total_unresolved | 85 | 88 |
| chain_level_exact_reconstruction_rate | 0.6667 | 0.4 |
| false_authoritative_promotion_count | 0 | 0 |

## 3. Test Results

- **Passed**: 662
- **Failed**: 0
- **Skipped**: 2
- **Exit code**: 0

### CI Status

- **Workflow**: `.github/workflows/tests.yml`
- **CI triggers**: push to main/develop, PR to main
- **Freeze branch**: feature/semantic-mapper-v0.1 (does not trigger CI)
- **Authoritative test status**: local run with DATABASE_URL set
  (passed=662, skipped=2, failed=0)
- Full CI status details in `ci_status.json`

## 4. PostgreSQL / Lineage / Temporal Integrity

- **All 25 chains pass**: True
- **Chains with issues**: []

### Per-chain integrity

| Chain ID | Orphans | Cycles | Contradictory Active | Invalid Intervals | Pass |
|----------|---------|--------|----------------------|-------------------|------|
| EDGAR-AMERESCO | 0 | 0 | 0 | 0 | YES |
| EDGAR-AMEDISYS | 0 | 0 | 0 | 0 | YES |
| EDGAR-BAUSCH-LOMB | 0 | 0 | 0 | 0 | YES |
| STUDY-004 | 0 | 0 | 0 | 0 | YES |
| STUDY-005 | 0 | 0 | 0 | 0 | YES |
| STUDY-006 | 0 | 0 | 0 | 0 | YES |
| STUDY-007 | 0 | 0 | 0 | 0 | YES |
| STUDY-008 | 0 | 0 | 0 | 0 | YES |
| STUDY-010 | 0 | 0 | 0 | 0 | YES |
| STUDY-012 | 0 | 0 | 0 | 0 | YES |
| STUDY-013 | 0 | 0 | 0 | 0 | YES |
| STUDY-014 | 0 | 0 | 0 | 0 | YES |
| STUDY-015 | 0 | 0 | 0 | 0 | YES |
| STUDY-016 | 0 | 0 | 0 | 0 | YES |
| STUDY-017 | 0 | 0 | 0 | 0 | YES |
| STUDY-018 | 0 | 0 | 0 | 0 | YES |
| STUDY-020 | 0 | 0 | 0 | 0 | YES |
| STUDY-021 | 0 | 0 | 0 | 0 | YES |
| STUDY-022 | 0 | 0 | 0 | 0 | YES |
| STUDY-026 | 0 | 0 | 0 | 0 | YES |
| STUDY-027 | 0 | 0 | 0 | 0 | YES |
| STUDY-028 | 0 | 0 | 0 | 0 | YES |
| STUDY-029 | 0 | 0 | 0 | 0 | YES |
| STUDY-030 | 0 | 0 | 0 | 0 | YES |
| STUDY-031 | 0 | 0 | 0 | 0 | YES |

## 5. False Authoritative Promotion

- **Count**: 0
- **Total steps**: 80
- **Rate**: 0.0

## 6. Defect Resolution Record (Step 17B)

**Total defects diagnosed**: 3

**Shared-mechanism verdict**: ALL 3 DEFECTS SHARE ONE ROOT-CAUSE MECHANISM: the semantic-mapper rule _rule_maturity_date_replacement fires on parser instructions whose instruction_type is RESTATE_SECTION (2 cases, STUDY-007 A1 ins 4/5) or DELETE (1 case, STUDY-022 A3 ins 2), producing confident REPLACE_VALUE mutations targeting facility.credit_agreement (a key absent from every chain's state). The executor rejects them as unresolved. The triggering instruction_type differs but the bug is identical: the rule lacks an instruction_type guard. Root cause = SEMANTIC_MAPPER_WRONG (single bug, single fix point).

### Defect details

#### Defect 1: STUDY-007 A1 ins 4

- **Root cause**: SEMANTIC_MAPPER_WRONG
- **Layer**: SEMANTIC_MAPPER
- **Parser instruction type**: RESTATE_SECTION
- **Semantic mapping rule**: _rule_maturity_date_replacement
- **Produced mutation**: REPLACE_VALUE facility.credit_agreement.deadline
- **Target commitment**: facility.credit_agreement
- **Target field**: deadline
- **Extracted new value**: 2021-02-12
- **Correct interpretation**: Restatement of a definitions section; the 'Maturity Date' mention is one of several defined terms being restated, not a standalone amendment to the maturity date field.  Should be UNRESOLVED / VALIDATION_REQUIRED.
- **Execution result**: UNRESOLVED (executor rejected: target key does not exist in chain state)
- **Authoritative status**: non-authoritative (step blocked by own unresolved)

#### Defect 2: STUDY-007 A1 ins 5

- **Root cause**: SEMANTIC_MAPPER_WRONG
- **Layer**: SEMANTIC_MAPPER
- **Parser instruction type**: RESTATE_SECTION
- **Semantic mapping rule**: _rule_maturity_date_replacement
- **Produced mutation**: REPLACE_VALUE facility.credit_agreement.deadline
- **Target commitment**: facility.credit_agreement
- **Target field**: deadline
- **Extracted new value**: 2021-02-12
- **Correct interpretation**: Restatement of a definitions section; the 'Maturity Date' mention is one of several defined terms being restated, not a standalone amendment to the maturity date field.  Should be UNRESOLVED / VALIDATION_REQUIRED.
- **Execution result**: UNRESOLVED (executor rejected: target key does not exist in chain state)
- **Authoritative status**: non-authoritative (step blocked by own unresolved)

#### Defect 3: STUDY-022 A3 ins 2

- **Root cause**: SEMANTIC_MAPPER_WRONG
- **Layer**: SEMANTIC_MAPPER
- **Parser instruction type**: DELETE
- **Semantic mapping rule**: _rule_maturity_date_replacement
- **Produced mutation**: REPLACE_VALUE facility.credit_agreement.deadline
- **Target commitment**: facility.credit_agreement
- **Target field**: deadline
- **Extracted new value**: 2023-11-30
- **Correct interpretation**: Deletion of a section; the 'Maturity Date' mention is a defined-term cross-reference inside the deleted text, not an amendment to the maturity date field.  Should be UNRESOLVED / VALIDATION_REQUIRED.
- **Execution result**: UNRESOLVED (executor rejected: target key does not exist in chain state)
- **Authoritative status**: non-authoritative (step blocked by own unresolved)

### Fix applied

Added an instruction_type guard at the top of `_rule_maturity_date_replacement` in `semantic_mapper.py` that returns `None` unless `instruction_type` is `REPLACE_VALUE` or `REPLACE_TEXT`.  This prevents the rule from firing on `RESTATE_SECTION` or `DELETE` instructions whose source_text merely mentions 'Maturity Date' as a cross-reference or as one of several restated definitions.

### Regression tests added

- `test_regression_maturity_date_does_not_fire_on_restate_section`
- `test_regression_maturity_date_does_not_fire_on_delete`

Both tests fail without the guard and pass with it.

## 7. Step 18 Freeze Gate

- **Freeze gate**: YES

| Criterion | Status |
|-----------|--------|
| preflight_pass | PASS |
| tests_pass | PASS |
| false_authoritative_promotion_zero | PASS |
| postgresql_integrity_pass | PASS |

## 8. Code and Config SHA-256 Hashes

### Code files

| File | SHA-256 |
|------|---------|
| amendment_parser.py | `b61822f6e6c4fa70ba40433d335bc76e9a503389062794ba93b314549e22504d` |
| commitment_extractor.py | `11112bdbfce04ee4b718a307257b124fa677bebb10d76f5d7b935627e998b2eb` |
| diagnose_17b_defects.py | `515041625e6999867263fa00b993f1b9f209f691e2dc2945724d604b0a77596c` |
| executor.py | `adc6a28a311c43dca145c0cf1de1418914279d0256394ed167fd6cdad354ecb0` |
| gt_extractor.py | `faf2f1236a8fd70ad78a30be57dd1769c48398ea1613aec603a52e63da7b8e6e` |
| models.py | `6338065ea270189e1debaac364b7416d964175e421e15e361e1c80d66811e4af` |
| persistence.py | `7b922a5b1ffcf64d0882d147ca6f0c86f6410ac60c989aba9585a4249ba04827` |
| run_chain_study_v2.py | `719ec705c3aa14eca7c4199d27905fca9c0d33d86192fe79a127d1789b443ea8` |
| run_step_17b.py | `3e66d6922ef60cee413938660bef8de36cdde006bd1cf73b741422896f8151c0` |
| s0_extractor.py | `9e15ef4418077243e0ad3244e32b204ce45b24c8350d3426b84c0a6520b0a5bc` |
| schema.sql | `65f361ed0824e82953c807b557d70928a38dfa0326149538e38a280973038b00` |
| semantic_mapper.py | `25dfc7e688e6ed3c3298ce86f372104e01aed02793c55ae0bd064aa199a60e5d` |
| semantic_pipeline.py | `ce00cc11fe5331ccddb946fca53f821527030180e014692247faccdc6aa5a3b5` |

### Config files

| File | SHA-256 |
|------|---------|
| pyproject.toml | `30317d27381c73355d11099dbe51b877eb55fc10a2171babaa58877487be61ee` |

## 9. Input Manifest

- **Total input files hashed**: 237
- **Data directories**: ['data/chain_study', 'data/edgar_chains']
- Full file hashes in `input_manifest.json`

## 10. Capability and Limitation Statement

### SUPPORTED OUTCOMES

The frozen system produces the following outcomes for each amendment chain:

- **RECONSTRUCTED** — the chain's final state exactly matches the ground truth extraction.  The system successfully parsed, mapped, executed, and persisted all amendments.
- **PARTIAL** — some commitments were reconstructed but the final state does not exactly match ground truth.  Some instructions were mapped and applied; others were unresolved.
- **UNRESOLVED** — the parser detected instructions but the semantic mapper could not map them to structured mutations. No incorrect automatic mutations were produced; the system fails safely by leaving the instruction unresolved.
- **UNSUPPORTED_FORMAT** — the parser found 0 instructions because the amendment format is not handled by the parser's regex patterns.  The chain is ingested but no transformations are applied.
- **VALIDATION_REQUIRED** — the mapper produced a mutation but the executor could not apply it (missing S0 state, target key not found, or field mismatch).  The mutation is held as unresolved for human validation.

### FOUNDATION SAFETY CLAIM

The frozen development system produced:

- **0 incorrect automatic mutations** after defect resolution
- **0 false authoritative promotions**
- **no detected lineage, temporal, or persistence integrity defects** in the final development run (all 25 chains)

This means the system never silently produces a wrong result. When it cannot handle an amendment, it fails safely to UNRESOLVED or VALIDATION_REQUIRED rather than producing a confident wrong mutation.

### LIMITATIONS

The following coverage limitations were measured in the final development run and are NOT fixed (by design — the freeze preserves the system as-is):

- **S0 extraction success rate**: 0.7273 (16 chains with extracted S0)
- **GT extraction success rate**: 0.4 (2 chains with extracted GT)
- **S0 extraction coverage (avg)**: 0.4925
- **GT extraction coverage (avg)**: 0.2133
- **Semantic mapping coverage**: 0.033 (3 of 91 instructions mapped)
- **Unresolved rate**: 0.967
- **Chain-level exact reconstruction rate**: 0.4

These limitations reflect the development scope of the parser and semantic mapper.  They are recorded here as measured, not improved.  The held-out confirmatory study (Step 19) will measure the same metrics on untouched issuers.

## 11. Reproducibility

See `REPRODUCIBILITY.md` for step-by-step reproduction instructions.

## 12. Report Integrity

- This report's SHA-256 is recorded in `freeze_record.json`
- **Generated at UTC**: 2026-09-01T05:45:25.841501+00:00
- **Frozen commit**: `5518f4a4d74e2fd2af2f0d1ac43e893bee845b93`
