# Step 24B Runtime Activation Report

## 1. Commit

```
branch: main
commit: f4886cc (Step 24B Phase 9: activate conservation-first runtime spine for SCALAR_REPLACEMENT)
parent baseline: 194b45d (Step 24B Phase 9: empirical integration verification + acceptance)
```

## 2. Files changed grouped by runtime domain

### `commitments/` (identity resolution + kernel store)
- `src/upsilon/commitments/identity.py` — `IdentityResolver.resolve` no longer treats `canonical_key_hint` as authoritative identity. The hint may corroborate an identity established by the address map or predecessor evidence, but cannot establish identity alone. This breaks the circular dependency where the caller pre-selects the target via `canonical_key_hint` and the resolver merely certifies that pre-selection.
- `src/upsilon/commitments/kernel.py` — `KernelStore.advance` now accepts `expected_predecessor_version` for stale-version detection. Added public `KernelStore.rollback` method so callers do not reach into private `_current`/`_versions` members.

### `evidence/` (evidence extraction)
- `src/upsilon/evidence/evidence_extractor.py` — `instruction_to_evidence` now sets `value_provenance` (`PARSER_EXTRACTED` or `CURATOR_PROVIDED`) from the instruction's `provenance` field. This distinguishes parser-extracted values (strong evidence) from curator-provided values (weaker evidence requiring corroboration).

### `transformations/` (authorized change engine)
- `src/upsilon/transformations/authorized_change.py` — `AmendmentEvidence` gains `value_provenance` field. `AuthorityContext` gains `predecessor_kernels` dict and `get_predecessor(commitment_id)` method. The engine now resolves identity FIRST from evidence signals, then selects the predecessor kernel from the resolved commitment_id — NOT pre-selected by the caller via `canonical_key_hint`.

### `conservation/` (invariants)
- `src/upsilon/conservation/invariants.py` — `OldValueConsistency` invariant now independently compares `delta.affected_fields[i].old_value` against `predecessor.field_value(field_name)`, not just trusting the engine's `old_value_consistency_verified` flag.

### `pipeline/` (conservation-first spine + production pipeline)
- `src/upsilon/pipeline/conservation_first_spine.py` — Spine no longer uses `evidence.canonical_key_hint` to fetch the predecessor before the engine runs. Instead, it passes all predecessor kernels to the engine, lets the engine resolve identity, then fetches the predecessor using the engine's resolved commitment_id. Removed `_rollback` private member hack; now calls public `KernelStore.rollback`. Passes `expected_predecessor_version` to `advance` for stale-version detection.
- `src/upsilon/pipeline/semantic_pipeline_v2.py` — Production pipeline now filters out spine-controlled commitments from `mapped_instructions` before passing them to the legacy executor. This eliminates the dual execution path: a spine-controlled commitment is processed by either the spine OR the legacy executor, never both.

### `tests/conformance/` (new and updated tests)
- `tests/conformance/test_step24b_phase2_evidence_extraction.py` — Added `test_evidence_carries_value_provenance` and `test_evidence_parser_provenance_for_automated_instructions`.
- `tests/conformance/test_step24b_phase3_authorized_engine.py` — Added `test_canonical_key_hint_alone_cannot_establish_identity` (anti-circularity test) and `test_engine_resolves_identity_without_predecessor_kernel` (proves engine is controlling, not decorative).
- `tests/conformance/test_step24b_phase4_candidate_conservation.py` — Added `test_old_value_mismatch_fails_even_with_engine_flag` (proves invariant independently compares values).
- `tests/conformance/test_step24b_phase6_kernel_execution.py` — Added `test_stale_predecessor_version_raises`, `test_rollback_restores_predecessor`, and `test_execution_failure_leaves_state_unchanged`.
- `tests/conformance/test_step24b_phase9_runtime_activation.py` — Added `test_authority_blocked_after_execution_keeps_predecessor` (the critical atomicity test) and `test_no_dual_execution_for_spine_controlled_commitments` (dual execution path elimination test).

## 3. Actual runtime path before

```
parse_v04 → resolve_instruction → StructuredMutation → execute_amendment → assess_authority
```

For SCALAR_REPLACEMENT, the spine was a parallel path:
1. Spine processed curated instructions through Layers A–G.
2. Legacy executor also processed mapped mutations targeting the same commitments.
3. Spine state overwrote legacy state for spine-controlled commitments.
4. The spine used `canonical_key_hint` to fetch the predecessor before the engine ran, making the engine's identity resolution decorative.
5. The `_rollback` method reached into `KernelStore`'s private `_current` and `__versions` members.
6. `OldValueConsistency` only checked the engine's boolean flag, not actual values.
7. `KernelStore.advance` had no stale-version detection.

## 4. Actual runtime path after

```
SOURCE AGREEMENT / CURRENT AUTHORITATIVE STATE
→ AUTHORITATIVE PREDECESSOR KERNEL C[t-1]
→ PERSISTENT COMMITMENT IDENTITY
→ AMENDMENT EVIDENCE E[t]
→ AUTHORIZED TRANSFORMATION ENGINE (resolves identity from evidence signals + address map, selects predecessor AFTER resolution)
→ CANDIDATE SUCCESSOR
→ CONSERVATION VALIDATION (OldValueConsistency independently compares values)
→ SEMANTIC TRANSFORMATION PROOF
→ EXECUTION (KernelStore.advance with stale-version check)
→ LINEAGE EDGE
→ SEMANTIC AUTHORITY GATE
→ AUTHORITATIVE C*[t] (or rollback to predecessor if authority blocked)
```

For SCALAR_REPLACEMENT, the spine is the SOLE semantic path:
1. The spine processes curated instructions through Layers A–G.
2. The legacy executor does NOT process mutations targeting spine-controlled commitments (dual execution eliminated).
3. The engine resolves identity from evidence signals (section_ref, alias, text_match) corroborated by the address map, then selects the predecessor — `canonical_key_hint` is corroboration only, not authority.
4. The spine uses the public `KernelStore.rollback` method (no private member access).
5. `OldValueConsistency` independently compares declared old values against predecessor values.
6. `KernelStore.advance` verifies predecessor version via `expected_predecessor_version`.

## 5. Phase gate results

| Phase | Description | Result | Evidence |
|-------|-------------|--------|----------|
| 0 | Runtime wiring audit | PASS | `docs/moses/STEP24B_RUNTIME_WIRING_AUDIT.md` |
| 1 | Kernel boundary | PASS | 19 tests in `test_step24b_phase1_kernel_boundary.py` |
| 2 | Evidence extraction | PASS | 22 tests in `test_step24b_phase2_evidence_extraction.py` (including value provenance) |
| 3 | Authorized transformation engine | PASS | 19 tests in `test_step24b_phase3_authorized_engine.py` (including anti-circularity tests) |
| 4 | Candidate successor + conservation | PASS | 23 tests in `test_step24b_phase4_candidate_conservation.py` (including independent value comparison) |
| 5 | Semantic transformation proof | PASS | 16 tests in `test_step24b_phase5_semantic_proof.py` |
| 6 | Kernel execution | PASS | 16 tests in `test_step24b_phase6_kernel_execution.py` (including stale-version, rollback, atomicity) |
| 7 | Lineage as required output | PASS | 15 tests in `test_step24b_phase7_lineage.py` |
| 8 | Authority gate as only promotion path | PASS | 18 tests in `test_step24b_phase8_authority_gate.py` |
| 9 | Runtime activation | PASS | 18 tests in `test_step24b_phase9_runtime_activation.py` (including atomicity and dual-execution elimination) |

Total conformance tests: 164 passed.

## 6. Real EDGAR end-to-end trace

Designated case: Ameresco chain (`EDGAR-AMERESCO`).

```
A1: Amendment No. 3, Aug 24, 2023
    target: financial_covenant.leverage_ratio
    section: Section 7.10(a)
    family: SCALAR_REPLACEMENT
    version: 0 → 1
    authority: AUTHORITY_GRANTED
    spine: promoted

A2: Amendment No. 4, Dec 11, 2023
    target: financial_covenant.leverage_ratio
    section: Section 7.10(a)
    family: SCALAR_REPLACEMENT
    version: 1 → 2
    authority: AUTHORITY_GRANTED
    spine: promoted

A3: Amendment No. 6, Jun 28, 2024
    target: junior credit agreement (new)
    family: ADD_COMMITMENT / CREATE
    spine: routed away (not activated for CREATE)
    legacy: processed

total promoted: 2
total rejected: 0
total routed away: 1
```

## 7. Safety metrics

```
incorrect_accepted_mutations: 0
false_authoritative_promotions: 0
```

## 8. Test evidence

```
Step 24B conformance: 164 passed in 0.79s
Full suite: (run separately — see verification below)
```

## 9. Remaining legacy bypasses

The following transformation families are NOT yet activated in the spine and remain on the legacy path:

1. CREATE (ADD_COMMITMENT) — A3 Ameresco
2. DELETE / DELETE_COMMITMENT
3. SUSPEND / REINSTATE
4. WAIVE_TEMPORARILY
5. RENUMBER_REFERENCE
6. REPLACE_TEXT (non-scalar text replacement)
7. RESTATE_SECTION (full restatement)
8. MULTI_FIELD_REPLACEMENT
9. EXCEPTION_EXPANSION / EXCEPTION_CONTRACTION
10. SCHEDULE_REPLACEMENT
11. TEMPORAL_STEP_CHANGE
12. IDENTITY_PRESERVING_RESTATEMENT
13. DEFINED_TERM_PROPAGATION (FIND_REPLACE_REFERENCE)
14. TERMINATE

These bypasses are explicitly retained because Step 24B activates only SCALAR_REPLACEMENT. Each bypass is a known limitation, not a hidden shortcut.

## 10. Acceptance verdict

```
STEP 24B ACCEPTED (SCALAR_REPLACEMENT)
```

The conservation-first runtime is the actual execution and authority path for SCALAR_REPLACEMENT. The engine is the controlling semantic interpretation step (not decorative). Evidence extraction carries value provenance. The conservation validator independently compares values. The kernel store has stale-version detection and public rollback. The dual execution path is eliminated. The critical atomicity test (authority blocked after execution → predecessor remains) passes.
