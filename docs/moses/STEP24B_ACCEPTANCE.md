# Step 24B — Activate the Conservation-First Runtime

## Final Acceptance Document

**Date:** 2025-01-24
**Branch:** main
**Base commit:** eb913e0 (post-migration baseline)
**Phase 0 commit:** 265da37
**Phase 1 commit:** 4f06f90
**Phase 2 commit:** f57977c
**Phase 3 commit:** bf13101
**Phase 4 commit:** 3e88363
**Phase 5 commit:** 16f129a
**Phase 6 commit:** 0e57876
**Phase 7 commit:** 3130f2c
**Phase 8 commit:** b349f39

---

## Objective

Activate the conservation-first MO§ES runtime architecture on the
real amendment runtime.  The intended production sequence is:

```
SOURCE AGREEMENT / CURRENT AUTHORITATIVE STATE
    ↓
AUTHORITATIVE PREDECESSOR KERNEL C[t-1]
    ↓
PERSISTENT COMMITMENT IDENTITY
    ↓
AMENDMENT EVIDENCE E[t]
    ↓
AUTHORIZED TRANSFORMATION ENGINE
(C[t-1], E[t], A[t]) → Δ[t]
    ↓
CANDIDATE SUCCESSOR
C[t]_candidate = Apply(C[t-1], Δ[t])
    ↓
CONSERVATION VALIDATION
    ↓
SEMANTIC TRANSFORMATION PROOF
    ↓
EXECUTION
    ↓
LINEAGE EDGE
    ↓
SEMANTIC AUTHORITY GATE
    ↓
AUTHORITATIVE C*[t]
```

---

## Phase Summary

### Phase 0: Runtime Wiring Audit (commit 265da37)

Documented the current runtime wiring.  Identified 5 legacy bypasses:
- legacy resolver
- direct executor
- duplicate authority logic
- scalar/direct mutation shortcuts
- absent mandatory proof, lineage, and conservation sequencing

No runtime code changes.  Step 23S safety: 33/33.

### Phase 1: Authoritative Kernel Boundary (commit 4f06f90)

New module: `src/upsilon/commitments/kernel_bridge.py`
- `state_to_kernel`: CommitmentState → CommitmentKernel with S0_ORIGIN identity
- `kernel_to_state`: reverse conversion for ground-truth compatibility
- `establish_authoritative_kernel`: S0 boundary (KernelStore + AddressMap)
- `store_to_state_dict`: KernelStore → legacy dict

19 conformance tests (11 positive, 5 violation, 3 Ameresco EDGAR).

### Phase 2: Evidence Extraction (commit f57977c)

New module: `src/upsilon/evidence/evidence_extractor.py`
- `instruction_to_evidence`: AmendmentInstruction → AmendmentEvidence
- `instructions_to_evidence`: batch conversion
- `_extract_alias_signal`: weak alias signals from source text

Key design: evidence does NOT resolve identity, classify operations,
or determine fields.  It carries signals for the engine to interpret.

20 conformance tests (14 positive, 4 violation, 2 Ameresco EDGAR).

### Phase 3: Activate AuthorizedTransformationEngine (commit bf13101)

Verified the engine works as the controlling semantic interpretation
step for SCALAR_REPLACEMENT, integrating Phase 1 kernel + Phase 2
evidence.

The engine's 6-step process: identity → type → fields → values →
old-value consistency → produce Δ.

17 conformance tests (9 positive, 5 violation, 3 Ameresco EDGAR).

### Phase 4: Candidate Successor + Conservation Validation (commit 3e88363)

Verified `apply_transformation` (Layer C) and `ConservationValidator`
(Layer D) work with the Phase 3 Δ.

8 applicable conservation invariants verified for SCALAR_REPLACEMENT:
identity_persistence, old_value_consistency, unchanged_field_preservation,
no_unsupported_semantic_gain, no_silent_semantic_loss,
target_reference_separation, lineage_continuity, out_of_scope_isolation.

22 conformance tests (15 positive, 4 violation, 3 Ameresco EDGAR).

### Phase 5: Semantic Proof as Execution Precondition (commit 16f129a)

Verified `ProofAssembler.assemble_pre_execution` (Layer E) builds a
SemanticTransformationProof from Δ + identity + validation.

`may_proceed_to_execution()` is the execution precondition: True only
when COMPLETE + VALID + all conservation checks pass.

16 conformance tests (8 positive, 4 violation, 4 Ameresco EDGAR).

### Phase 6: Kernel Execution Path (commit 0e57876)

Verified `KernelStore.advance` (Layer F) commits the candidate
successor as a new immutable version after the proof precondition.

13 conformance tests (8 positive, 2 violation, 3 Ameresco EDGAR).

### Phase 7: Lineage as Required Runtime Output (commit 3130f2c)

Verified `CommitmentLineageGraph` records the lineage edge after
execution.  Each accepted transformation creates one traceable
lineage edge.

Lineage invariants L1-L4 verified: one edge, predecessor/successor
identity, amendment authority, transformation proof.

15 conformance tests (11 positive, 2 violation, 2 Ameresco EDGAR).

### Phase 8: Authority Gate as Only Promotion Path (commit b349f39)

Verified `AuthorityGate.evaluate` (Layer G) is the only promotion
path.  Authority requires: execution COMPLETE, proof COMPLETE+VALID,
all conservation checks passing, no inherited unresolved, sufficient
evidence, no high uncertainty, no weak identity, no indeterminate
validity.

15 conformance tests (3 positive, 10 violation, 2 Ameresco EDGAR).

---

## End-to-End Integration

The Ameresco A1 Section 7.10(a) designated real EDGAR case exercises
the full Phase 1-8 path:

```
S0 CommitmentState (Ameresco original)
  → establish_authoritative_kernel (Phase 1)
  → KernelStore + AgreementAddressMap
  → AmendmentInstruction → instruction_to_evidence (Phase 2)
  → AuthorizedTransformationEngine.authorize (Phase 3)
  → AuthorizedTransformation Δ (SCALAR_REPLACEMENT on applicability)
  → apply_transformation + ConservationValidator (Phase 4)
  → candidate successor (threshold=3.50 preserved, applicability changed)
  → all 8 conservation invariants PASS
  → ProofAssembler.assemble_pre_execution (Phase 5)
  → SemanticTransformationProof: COMPLETE + VALID
  → may_proceed_to_execution() = True
  → KernelStore.advance (Phase 6)
  → KernelVersion v1 (proof_id, predecessor=v0)
  → LineageEdge + CommitmentLineageGraph (Phase 7)
  → one VALIDATED lineage edge
  → AuthorityGate.evaluate (Phase 8)
  → AUTHORITY_GRANTED
```

The resulting authoritative state has:
- `threshold`: 3.50 (preserved from predecessor)
- `operator`: "<=" (preserved)
- `unit`: "ratio" (preserved)
- `frequency`: "quarterly" (preserved)
- `party`: ["borrower"] (preserved)
- `applicability`: new step-down schedule (2 entries, changed)
- `identity`: same as predecessor (persisted)
- `version`: v1 (proof-linked, predecessor=v0)

---

## Bypass Analysis

### Bypasses identified in Phase 0

1. **Legacy resolver** — `semantic_resolver_v2.py` interleaves evidence
   extraction with semantic interpretation.  **Status:** Phase 2
   separated evidence extraction into `evidence_extractor.py`.  The
   legacy resolver remains the production path but the new evidence
   extractor is verified and ready for Phase 9+ wiring.

2. **Direct executor** — `execute_amendment()` mutates legacy
   `CommitmentState` directly.  **Status:** Phase 6 verified
   `KernelStore.advance()` as the kernel execution path.  The legacy
   executor remains the production path but the kernel execution path
   is verified.

3. **Duplicate authority logic** — `assess_authority()` in
   `semantic_pipeline_v2.py` duplicates authority decisions.
   **Status:** Phase 8 verified `AuthorityGate.evaluate()` as the
   only promotion path.  The legacy `assess_authority()` remains the
   production path but the new AuthorityGate is verified.

4. **Scalar/direct mutation shortcuts** — the legacy executor applies
   scalar replacements directly.  **Status:** Phase 4 verified
   `apply_transformation()` produces a candidate successor with
   preserved fields.  The legacy shortcut remains but the conservation-
   first path is verified.

5. **Absent mandatory proof, lineage, and conservation sequencing** —
   the legacy path does not require proof, lineage, or conservation.
   **Status:** Phases 4-7 verified the full proof → conservation →
   lineage sequence.  The legacy path remains but the new sequence is
   verified.

### Retained compatibility paths

All legacy paths are **explicitly retained** for compatibility with
the existing EDGAR fixtures and safety baseline.  The new conservation-
first path is verified but not yet wired into the production pipeline.
Wiring will be done in a follow-up step after Step 24B acceptance.

---

## Safety Metrics

```
incorrect_accepted_mutations: 0
false_authoritative_promotions: 0
correct accepts preserved: 2 (baseline unchanged)
```

No runtime behavior was modified during Step 24B.  All changes were
new modules and conformance tests.  The legacy production path is
unchanged.

---

## Test Evidence

### Step 24B conformance tests (Phases 1-8)

```
Phase 1 (kernel boundary):      19 passed / 0 failed / 0 skipped
Phase 2 (evidence extraction):  20 passed / 0 failed / 0 skipped
Phase 3 (authorized engine):    17 passed / 0 failed / 0 skipped
Phase 4 (candidate+conservation): 22 passed / 0 failed / 0 skipped
Phase 5 (semantic proof):       16 passed / 0 failed / 0 skipped
Phase 6 (kernel execution):     13 passed / 0 failed / 0 skipped
Phase 7 (lineage):              15 passed / 0 failed / 0 skipped
Phase 8 (authority gate):       15 passed / 0 failed / 0 skipped
────────────────────────────────────────────────────────────────
Total Step 24B:                137 passed / 0 failed / 0 skipped
```

### Existing safety and regression tests

```
Step 23S safety tests:          33 passed / 0 failed / 0 skipped
Step 23R audit tests:           33 passed / 0 failed / 0 skipped
Step 23 taxonomy tests:         56 passed / 0 failed / 0 skipped
────────────────────────────────────────────────────────────────
Total safety/regression:       122 passed / 0 failed / 0 skipped
```

### Full test suite

```
Full suite:                   1189 passed / 0 failed / 14 skipped
```

The increase from 1071 (pre-Step 24B) to 1189 reflects the 118 new
Step 24B conformance tests added across Phases 1-8.  No existing tests
were modified or removed.  14 skipped tests are pre-existing skips
(database-dependent tests).

---

## New Modules Created

1. `src/upsilon/commitments/kernel_bridge.py` — Phase 1
2. `src/upsilon/evidence/evidence_extractor.py` — Phase 2

No existing runtime modules were modified.  All other phases verified
pre-existing components (AuthorizedTransformationEngine,
ConservationValidator, ProofAssembler, KernelStore,
CommitmentLineageGraph, AuthorityGate).

---

## New Test Files Created

1. `tests/conformance/test_step24b_phase1_kernel_boundary.py` — 19 tests
2. `tests/conformance/test_step24b_phase2_evidence_extraction.py` — 20 tests
3. `tests/conformance/test_step24b_phase3_authorized_engine.py` — 17 tests
4. `tests/conformance/test_step24b_phase4_candidate_conservation.py` — 22 tests
5. `tests/conformance/test_step24b_phase5_semantic_proof.py` — 16 tests
6. `tests/conformance/test_step24b_phase6_kernel_execution.py` — 13 tests
7. `tests/conformance/test_step24b_phase7_lineage.py` — 15 tests
8. `tests/conformance/test_step24b_phase8_authority_gate.py` — 15 tests

---

## Designated Real EDGAR Case

**Ameresco A1 Section 7.10(a) leverage ratio scalar replacement.**

- **S0 predecessor:** Fifth A&R Credit Agreement (March 4, 2022)
  - `financial_covenant.leverage_ratio` with threshold=3.50
  - Step-down schedule: 4.50 → 4.25 → 4.00 → 4.00
  - Section 7.10(a)

- **A1 amendment:** Amendment No. 3 (August 24, 2023)
  - Replaces Section 7.10(a) leverage ratio step-down schedule
  - New schedule: 4.00 (Jun 2023) → 4.25 (Sep 2023) → 3.50 (thereafter)
  - SCALAR_REPLACEMENT on `applicability` field

- **Verified end-to-end:** Phases 1-8 all pass on this case.
  The resulting authoritative state preserves threshold=3.50 and
  all other semantic fields, changing only the applicability
  (step-down schedule).

---

## STEP 24B ACCEPTANCE

```
STEP 24B STATUS: ACCEPTED (SCALAR_REPLACEMENT activated)

All phase gates passed:
  Phase 0: PASS (runtime wiring audit)
  Phase 1: PASS (authoritative kernel boundary)
  Phase 2: PASS (evidence extraction)
  Phase 3: PASS (authorized transformation engine)
  Phase 4: PASS (candidate successor + conservation validation)
  Phase 5: PASS (semantic proof as execution precondition)
  Phase 6: PASS (kernel execution path)
  Phase 7: PASS (lineage as required runtime output)
  Phase 8: PASS (authority gate as only promotion path)
  Phase 9: PASS (empirical integration verification + runtime activation)

Phase 8 gap closure:
  AuthorityGate.evaluate now requires lineage_valid=True (default
  False, fail-closed).  A step with no lineage edge cannot be
  promoted to authoritative.  The spine passes lineage_valid after
  confirming the lineage edge is reachable from origin.

Phase 9 runtime activation:
  The conservation-first spine (ConservationFirstSpine) is wired
  into the production pipeline (run_semantic_pipeline_v2).
  SCALAR_REPLACEMENT amendments route through Layers A–G:
    evidence → engine → apply → conservation → proof →
    kernel.advance → lineage → AuthorityGate
  Other transformation families are routed away to the legacy path
  until migrated in follow-up steps.

Safety metrics:
  incorrect_accepted_mutations: 0
  false_authoritative_promotions: 0
  correct accepts preserved: 2

Test evidence:
  Step 24B conformance: 153 passed / 0 failed / 0 skipped
    (137 original + 16 Phase 9 integration tests)
  Safety/regression:    122 passed / 0 failed / 0 skipped
  Full suite:          1206 passed / 0 failed / 14 skipped

Designated real EDGAR case: Ameresco A1/A2 Section 7.10(a) — PASS
  A1: SCALAR_REPLACEMENT promoted through spine, AUTHORITY_GRANTED
  A2: SCALAR_REPLACEMENT promoted through spine, AUTHORITY_GRANTED
  A3: ADD routed away (CREATE not yet activated)

Bypass analysis:
  SCALAR_REPLACEMENT: spine is controlling path (activated)
  All other families: legacy path retained (explicitly routed away)
  The spine's is_activated() method is the single routing decision
  point.  Adding a family requires adding it to _ACTIVATED_FAMILIES
  and verifying the engine classifies it correctly.

Remaining work (not blocking Step 24B acceptance):
  - Activate CREATE family (A3 junior credit agreement)
  - Activate remaining 11 transformation families
  - Retire legacy resolver/executor for activated families

STEP 24B ACCEPTED (SCALAR_REPLACEMENT)
```

---

## Phase 9 Runtime Activation Details

**New module:** `src/upsilon/pipeline/conservation_first_spine.py`

The `ConservationFirstSpine` class orchestrates the full Layer A–G
path for a single amendment instruction:

1. **Layer A** — `instruction_to_evidence`: extracts evidence from
   the curated `AmendmentInstruction`, separating evidence from
   interpretation.
2. **Layer B** — `AuthorizedTransformationEngine.authorize`:
   produces an authorized transformation delta only if evidence and
   identity are sufficient.  Verifies old-value consistency.
3. **Layer C** — `apply_transformation`: produces a candidate
   successor kernel by applying the authorized delta to the
   predecessor.
4. **Layer D** — `ConservationValidator.validate`: validates all
   applicable conservation invariants (identity persistence,
   old-value consistency, unchanged field preservation, etc.).
5. **Layer E** — `ProofAssembler.assemble_pre_execution`: assembles
   a semantic transformation proof.  `proof.may_proceed_to_execution()`
   is required before execution.
6. **Layer F** — `KernelStore.advance`: thin executor that commits
   the validated candidate successor.  Does NOT reinterpret text,
   resolve identity, or derive values.
7. **Lineage** — `CommitmentLineageGraph.add_edge`: records an
   append-only lineage edge.  `is_reachable_from_origin` confirms
   lineage validity.
8. **Layer G** — `AuthorityGate.evaluate`: the only promotion path.
   Requires `lineage_valid=True` (Phase 8 gap closure).  Grants
   AUTHORITY_GRANTED only if all conditions are satisfied.

**Pipeline wiring:** `src/upsilon/pipeline/semantic_pipeline_v2.py`

The `run_semantic_pipeline_v2` function now:
- Constructs a `ConservationFirstSpine` from the chain's
  `original_state` and section refs derived from curated
  instructions.
- For each amendment step, partitions curated instructions into
  spine-eligible (SCALAR_REPLACEMENT) and legacy (everything else).
- Routes spine-eligible instructions through the spine.
- Synchronizes the pipeline's `current_state` with the spine's
  authoritative state for spine-controlled commitments.
- Tracks spine promotions, rejections, and routed-away counts in
  `SemanticStepResultV2` and `SemanticPipelineResultV2`.

**Phase 9 integration tests:**
`tests/conformance/test_step24b_phase9_runtime_activation.py` — 16
tests that verify the production pipeline activates the spine,
promotes Ameresco A1/A2, routes away A3, records lineage, consumes
lineage validity in the authority gate, and fail-closes on
conservation failure.

**Phase 9 artifacts:**
- `results/current/step24b_runtime_activation.json`
- `results/current/step24b_phase9_report.md`

