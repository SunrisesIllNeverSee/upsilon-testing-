# Conformance Matrix

**Step 23M design document — Component 7: MOSES Conformance Harness.**

This document defines the conformance test matrix and the Conformance
Promotion Rule.  No runtime code is modified.

---

## 1. Conformance Promotion Rule (Constraint #6)

This is a permanent governance rule:

```
ENFORCED(I)
iff
RuntimeGuard(I)
AND PositiveTest(I)
AND ViolationTest(I)
```

An invariant `I` may not be marked `ENFORCED` because documentation
says it exists or because ordinary tests happen to pass.

### Required before promotion to ENFORCED

1. **Explicit runtime enforcement** — a runtime guard (code) that
   checks the invariant and blocks violations.
2. **Valid-case test** — a test that confirms the guard allows
   legitimate transformations.
3. **Violation/failure-path test** — a test that confirms the guard
   blocks the prohibited behavior.

### Promotion levels

| Level | Meaning |
|-------|---------|
| `ENFORCED` | All three requirements met: runtime guard + positive test + violation test |
| `PARTIALLY ENFORCED` | Runtime guard exists in some paths but not all, OR positive test exists but violation test does not |
| `NOT YET ENFORCED` | No runtime guard, or guard exists but no tests prove it works |
| `DOCUMENTED` | Invariant is specified in documentation but has no runtime guard and no tests |

An invariant may not skip levels.  `DOCUMENTED` → `NOT YET ENFORCED`
→ `PARTIALLY ENFORCED` → `ENFORCED` requires the corresponding
evidence at each step.

### CI behavior

A failed MOSES conformance invariant must be capable of failing CI
**even if hundreds of ordinary unit tests pass**.  Conformance tests
are not advisory.  They are gating.

---

## 2. Conformance test matrix

The following 18 conformance tests are required.  Each maps to one or
more invariant families from `CONSERVATION_INVARIANTS.md` and
`CONFORMANCE_CONTRACT.md`.

### 2.1 identity_persists_across_amendment

| | |
|---|---|
| **Invariant** | Identity persistence (§2.1) |
| **Test type** | CONFORMANCE |
| **Positive case** | A commitment amended by SCALAR_REPLACEMENT retains its `commitment_id` |
| **Violation case** | A transformation that changes `commitment_id` without a CREATE/TERMINATE/SPLIT/MERGE/REDEFINE/RENUMBER event is blocked |
| **Current status** | NOT YET ENFORCED |

### 2.2 section_address_is_agreement_local

| | |
|---|---|
| **Invariant** | Identity persistence (§2.1), target/reference separation (§2.6) |
| **Test type** | CONFORMANCE |
| **Positive case** | Section 7.10 in Agreement A resolves to a different commitment than Section 7.10 in Agreement B |
| **Violation case** | A global section map that maps Section 7.10 to `leverage_ratio` for all agreements is rejected |
| **Current status** | NOT YET ENFORCED |

### 2.3 reference_is_not_target

| | |
|---|---|
| **Invariant** | Target/reference separation (§2.6) |
| **Test type** | CONFORMANCE |
| **Positive case** | A provision mentioning "Revolving Loans" in a debt-incurrence context does not produce a mutation on `facility.revolving_facility` |
| **Violation case** | A resolver that matches "Revolving Loans" alias and constructs a mutation without target identity evidence is blocked |
| **Current status** | ENFORCED (Step 23S) — `moses_safety.check_section_alias_consistency` + `check_cross_type_evidence` enforce target-vs-reference separation. Tests: `test_reference_is_not_target`, `test_section_contradicts_alias_blocks_resolver`, `test_facility_target_with_ratio_evidence_blocked` |

### 2.4 old_value_matches_predecessor

| | |
|---|---|
| **Invariant** | Old-value consistency (§2.2) |
| **Test type** | CONFORMANCE |
| **Positive case** | A SCALAR_REPLACEMENT with `declared_old_value == C_{t-1}[field]` is accepted |
| **Violation case** | A SCALAR_REPLACEMENT with `declared_old_value != C_{t-1}[field]` is blocked |
| **Current status** | ENFORCED (Step 23S) — `moses_safety.check_old_value_consistency` enforces old-value consistency from amendment evidence only (no tautological predecessor-derived check). Tests: `test_old_value_matches_predecessor`, `test_wrong_old_value_blocks_transform`, `test_no_old_value_is_not_applicable`, `test_wrong_old_value_blocks_resolver` |

### 2.5 wrong_old_value_blocks_transform

| | |
|---|---|
| **Invariant** | Old-value consistency (§2.2) |
| **Test type** | CONFORMANCE (violation path) |
| **Positive case** | N/A (this is the violation test for 2.4) |
| **Violation case** | A transformation where the declared old value does not match the predecessor state is blocked BEFORE execution |
| **Current status** | ENFORCED (Step 23S) — `moses_safety.check_old_value_consistency` returns FAIL when the amendment-declared old value does not match the predecessor. Test: `test_wrong_old_value_blocks_transform`, `test_wrong_old_value_blocks_resolver` |

### 2.6 unchanged_fields_are_conserved

| | |
|---|---|
| **Invariant** | Unchanged-field preservation (§2.3) |
| **Test type** | CONFORMANCE |
| **Positive case** | After a SCALAR_REPLACEMENT on `threshold`, all other fields (`exceptions`, `scope`, `operator`, etc.) are unchanged |
| **Violation case** | A transformation that silently drops `exceptions` when only `threshold` was targeted is blocked |
| **Current status** | PARTIALLY ENFORCED (deep-copy preserves fields, but ADD with dict payload can drop them) |

### 2.7 unsupported_semantics_do_not_alias_into_frozen_class

| | |
|---|---|
| **Invariant** | No unsupported semantic gain (§2.4), alias policy (§4) |
| **Test type** | CONFORMANCE |
| **Positive case** | "Consolidated Leverage Ratio" aliases to `leverage_ratio` (spelling equivalence) |
| **Violation case** | "Asset Coverage Ratio" aliased to `debt_service_coverage` is rejected (non-equivalent); "Minimum Working Capital" aliased to `current_ratio` is rejected |
| **Current status** | PARTIALLY ENFORCED (Step 23S) — `moses_safety.check_section_alias_consistency` catches non-equivalent alias claims when the section reference contradicts the alias-resolved class. The value-extraction compatibility check (`check_value_extraction_compatibility`) also catches cross-type alias mismatches (e.g., a ratio value extracted for a facility target). However, the alias registry itself still contains aliases that may not represent genuine semantic equivalence; full alias-equivalence auditing is a Step 24 task. Tests: `test_non_equivalent_alias_is_blocked_by_value_mismatch`, `test_non_equivalent_alias_blocks_resolver` |

### 2.8 restatement_derives_correct_delta

| | |
|---|---|
| **Invariant** | Transformation completeness (§2.10), identity-preserving restatement (`TRANSFORMATION_ALGEBRA.md` §3) |
| **Test type** | CONFORMANCE |
| **Positive case** | A restated section produces a delta with exactly the changed fields |
| **Violation case** | A restated section that produces a full replacement (destroying unchanged fields) is blocked |
| **Current status** | NOT YET ENFORCED (RESTATE_SECTION currently rejected by executor) |

### 2.9 restatement_preserves_identity

| | |
|---|---|
| **Invariant** | Identity persistence (§2.1) |
| **Test type** | CONFORMANCE |
| **Positive case** | A restated section preserves `commitment_id` |
| **Violation case** | A restatement that creates a new `commitment_id` without evidence of identity change is blocked |
| **Current status** | NOT YET ENFORCED |

### 2.10 multi_field_change_cannot_partially_disappear

| | |
|---|---|
| **Invariant** | Transformation completeness (§2.10) |
| **Test type** | CONFORMANCE |
| **Positive case** | A MULTI_FIELD_REPLACEMENT that changes 3 fields extracts all 3 |
| **Violation case** | A MULTI_FIELD_REPLACEMENT that extracts only 2 of 3 fields is blocked (no partial subset applied) |
| **Current status** | NOT YET ENFORCED |

### 2.11 out_of_scope_instruction_cannot_mutate_state

| | |
|---|---|
| **Invariant** | OUT_OF_SCOPE isolation (§2.9) |
| **Test type** | CONFORMANCE |
| **Positive case** | An OUT_OF_SCOPE instruction produces no mutation |
| **Violation case** | An OUT_OF_SCOPE instruction that produces a mutation (the HELD-017 pattern) is blocked |
| **Current status** | ENFORCED (Step 23S) — `moses_safety.check_section_corroboration` enforces that structural amendments (ADD on list fields) require section corroboration. The target-vs-reference separation (I1) and cross-type evidence check (I3) also block OUT_OF_SCOPE mutations. No lexical rejection heuristics are used. Tests: `test_out_of_scope_instruction_cannot_mutate_state`, `test_section_contradicts_alias_blocks_resolver` |

### 2.12 incorrect_semantic_delta_cannot_be_authoritative

| | |
|---|---|
| **Invariant** | Authority gate (`SEMANTIC_AUTHORITY_GATE.md`) |
| **Test type** | CONFORMANCE |
| **Positive case** | A step with a valid proof record and passing conservation checks is promoted to authoritative |
| **Violation case** | A step with a failed conservation check (e.g., old-value mismatch) is NOT promoted to authoritative |
| **Current status** | ENFORCED (Step 23S) — `semantic_pipeline_v2.assess_authority` implements the semantic authority gate: an INVALID or INCOMPLETE proof blocks authority promotion even when execution is COMPLETE. Tests: `test_invalid_proof_blocks_authority`, `test_insufficient_evidence_blocks_authority`, `test_incomplete_proof_blocks_authority`, `test_inherited_unresolved_blocks_authority`, `test_valid_proof_grants_authority` |

### 2.13 renumbering_preserves_identity

| | |
|---|---|
| **Invariant** | Identity persistence (§2.1) |
| **Test type** | CONFORMANCE |
| **Positive case** | A RENUMBER transformation changes the address but not the `commitment_id` |
| **Violation case** | A renumbering that changes `commitment_id` is blocked |
| **Current status** | NOT YET ENFORCED |

### 2.14 waiver_preserves_and_restores_state

| | |
|---|---|
| **Invariant** | Temporal validity (§2.8), unchanged-field preservation (§2.3) |
| **Test type** | CONFORMANCE |
| **Positive case** | A WAIVER preserves all semantic fields; a REINSTATEMENT restores them to pre-waiver values |
| **Violation case** | A waiver that modifies `threshold` or `exceptions` is blocked; a reinstatement that does not restore pre-waiver values is blocked |
| **Current status** | PARTIALLY ENFORCED (7 temporal transition tests exist but are not comprehensive) |

### 2.15 temporal_schedule_changes_at_correct_time

| | |
|---|---|
| **Invariant** | Temporal validity (§2.8) |
| **Test type** | CONFORMANCE |
| **Positive case** | A step schedule change takes effect at the correct date |
| **Violation case** | A step schedule with overlapping or backward dates is blocked |
| **Current status** | PARTIALLY ENFORCED |

### 2.16 defined_term_dependency_is_traceable

| | |
|---|---|
| **Invariant** | Lineage continuity (§2.7) |
| **Test type** | CONFORMANCE |
| **Positive case** | A DEFINED_TERM_PROPAGATION updates all referencing commitments and records the dependency |
| **Violation case** | A defined-term change that does not propagate to all referencing commitments is blocked |
| **Current status** | NOT YET ENFORCED |

### 2.17 proof_record_is_complete

| | |
|---|---|
| **Invariant** | Semantic proof completeness (`SEMANTIC_PROOF_RECORD.md` §7) |
| **Test type** | CONFORMANCE |
| **Positive case** | An accepted transformation produces a COMPLETE proof record |
| **Violation case** | A transformation with an INCOMPLETE proof record is blocked before execution |
| **Current status** | ENFORCED (Step 23S) — `moses_safety._is_structurally_complete` + `build_semantic_proof` produce a real INCOMPLETE status when required structural components (canonical_id, field_name, new_value, source_text) are missing. An INCOMPLETE proof cannot execute (`is_executable` requires COMPLETE+VALID) and blocks authority. Tests: `test_proof_record_is_complete`, `test_missing_new_value_produces_incomplete_proof`, `test_missing_source_text_produces_incomplete_proof`, `test_missing_canonical_id_produces_incomplete_proof`, `test_incomplete_proof_blocks_authority` |

### 2.18 authority_requires_valid_semantic_proof

| | |
|---|---|
| **Invariant** | Authority gate (`SEMANTIC_AUTHORITY_GATE.md`) |
| **Test type** | CONFORMANCE |
| **Positive case** | Authority is granted only with a COMPLETE proof record and passing conservation checks |
| **Violation case** | Authority granted with no proof record (the current behavior) is blocked |
| **Current status** | ENFORCED (Step 23S) — `semantic_pipeline_v2.assess_authority` requires COMPLETE+VALID proof records for authority promotion. An INVALID, INCOMPLETE, or INSUFFICIENT-evidence proof blocks authority. The authority gate is wired into `run_semantic_pipeline_v2` (Step 6). Tests: `test_authority_requires_valid_semantic_proof`, `test_invalid_semantic_proof_cannot_execute`, `test_invalid_proof_blocks_authority`, `test_valid_proof_grants_authority`, `test_no_op_step_grants_authority_without_proofs` |

---

## 3. Test type distinction

| Type | Purpose | Location | CI gating |
|------|---------|----------|-----------|
| **UNIT TEST** | Tests individual functions in isolation | `tests/unit/` | Yes |
| **INTEGRATION TEST** | Tests multiple components together | `tests/integration/` | Yes |
| **CONFORMANCE TEST** | Tests MOSES invariants against the real runtime | `tests/conformance/` | Yes — a failed conformance test fails CI regardless of unit test results |
| **REAL-EDGAR REGRESSION** | Tests against real EDGAR chain data | `tests/regression/` | Yes |

### Conformance tests are not unit tests

A conformance test asserts that a MOSES invariant holds against the
real runtime, not against a mock.  If the current system does not
satisfy an invariant, the test must fail (or be skipped with a
documented reason), not pass vacuously.

A conformance test that passes vacuously (e.g., because the invariant
is not exercised) is a defect.  The Conformance Promotion Rule
(§1) requires a violation-path test that proves the guard blocks the
prohibited behavior.

---

## 4. Current enforcement status summary

After Step 23S, 7 of 18 conformance tests are ENFORCED, 4 are
PARTIALLY ENFORCED, and 7 remain NOT YET ENFORCED.  The ENFORCED
invariants cover the safety-critical baseline: target/reference
separation, old-value consistency, OUT_OF_SCOPE isolation, proof
completeness, and the semantic authority gate.

| Test | Current status | Promotion blocker |
|------|---------------|-------------------|
| identity_persists_across_amendment | NOT YET ENFORCED | No runtime guard |
| section_address_is_agreement_local | NOT YET ENFORCED | Global section map still in use |
| reference_is_not_target | ENFORCED (Step 23S) | — |
| old_value_matches_predecessor | ENFORCED (Step 23S) | — |
| wrong_old_value_blocks_transform | ENFORCED (Step 23S) | — |
| unchanged_fields_are_conserved | PARTIALLY ENFORCED | ADD with dict payload can drop fields |
| unsupported_semantics_do_not_alias_into_frozen_class | PARTIALLY ENFORCED (Step 23S) | Alias registry still contains potentially non-equivalent aliases; full alias-equivalence audit is Step 24 |
| restatement_derives_correct_delta | NOT YET ENFORCED | RESTATE_SECTION rejected by executor |
| restatement_preserves_identity | NOT YET ENFORCED | No restatement implementation |
| multi_field_change_cannot_partially_disappear | NOT YET ENFORCED | No completeness check |
| out_of_scope_instruction_cannot_mutate_state | ENFORCED (Step 23S) | — |
| incorrect_semantic_delta_cannot_be_authoritative | ENFORCED (Step 23S) | — |
| renumbering_preserves_identity | NOT YET ENFORCED | No renumbering handling |
| waiver_preserves_and_restores_state | PARTIALLY ENFORCED | Not comprehensive |
| temporal_schedule_changes_at_correct_time | PARTIALLY ENFORCED | Not comprehensive |
| defined_term_dependency_is_traceable | NOT YET ENFORCED | No defined-term propagation |
| proof_record_is_complete | ENFORCED (Step 23S) | — |
| authority_requires_valid_semantic_proof | ENFORCED (Step 23S) | — |

---

## 5. References

- `CONFORMANCE_CONTRACT.md` — existing 13 invariant families + L1–L7
  lineage invariants
- `CONSERVATION_INVARIANTS.md` — invariant specifications
- `SEMANTIC_AUTHORITY_GATE.md` — authority gate contract
- `SEMANTIC_PROOF_RECORD.md` — proof record schema
- `.devin/prompts/STEP_23M_CONSTRAINTS.md` — Constraint #6
  (Conformance Promotion Rule)
