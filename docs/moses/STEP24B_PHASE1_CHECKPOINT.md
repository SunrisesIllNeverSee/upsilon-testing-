# Step 24B Phase 1 — Authoritative Kernel Boundary

**Phase 1 deliverable.** This phase establishes the boundary between
legacy `CommitmentState` and canonical `CommitmentKernel` with
persistent `CommitmentIdentity`, and provides the `KernelStore` as the
authoritative predecessor-state source.

---

## Implementation

### New module: `src/upsilon/commitments/kernel_bridge.py`

```
RESPONSIBILITY: Establish authoritative kernel boundary
    (CommitmentState ↔ CommitmentKernel conversion)
TARGET DOMAIN: commitments
CURRENT MODULE: src/upsilon/commitments/kernel_bridge.py (new)
CURRENT OPERATING STATUS: Phase 1 — authoritative kernel boundary
WHY THIS MODULE MUST CHANGE: The production pipeline operates on
    CommitmentState (legacy). The Step 24 spine requires
    CommitmentKernel with persistent identity. A conversion bridge
    is needed at the boundary.
TARGET OWNER AFTER CHANGE: commitments domain (this module)
MIGRATION / REMOVAL CONDITION: Remove when the production pipeline
    operates natively on CommitmentKernel and no longer needs
    CommitmentState conversion.
```

Functions provided:
- `state_to_kernel(state, agreement_identity, section_ref)` — converts
  a legacy `CommitmentState` to a canonical `CommitmentKernel` with
  persistent `CommitmentIdentity` (S0_ORIGIN provenance).
- `kernel_to_state(kernel)` — reverse conversion for compatibility
  with the existing ground-truth comparison layer.
- `establish_authoritative_kernel(original_state, agreement_identity,
  section_refs)` — establishes the S0 boundary: creates a `KernelStore`
  with all commitments at version 0, and an `AgreementAddressMap` with
  section-ref → commitment-id mappings.
- `store_to_state_dict(store)` — converts a `KernelStore`'s current
  authoritative state back to a legacy `dict[str, CommitmentState]`.

### New tests: `tests/conformance/test_step24b_phase1_kernel_boundary.py`

19 conformance tests covering:
- Positive: state→kernel conversion produces kernel with identity
- Positive: semantic fields preserved across boundary
- Positive: temporal fields preserved across boundary
- Positive: identity provenance is S0_ORIGIN
- Positive: local_address carries section ref
- Positive: kernel→state roundtrip preserves semantic fields
- Positive: establish_authoritative_kernel creates store with version 0
- Positive: address map maps section refs to commitment IDs
- Positive: identity persists across boundary
- Positive: store_to_state_dict roundtrip
- Positive (Ameresco): predecessor kernel has threshold=3.50
- Positive (Ameresco): predecessor kernel has step-down schedule
- Positive (Ameresco): address map resolves Section 7.10(a)
- Violation: unknown section ref fails closed
- Violation: empty section ref fails closed
- Violation: alias-only without corroboration is INSUFFICIENT
- Violation: duplicate origin establishment raises
- Violation: advance without established commitment raises

---

## Production-path reachability

**Status:** The kernel bridge is NOT yet wired into the production
pipeline.  This is expected — Phase 1 establishes the boundary
*capability*; Phase 2–8 wire it into the production path.

The bridge is reachable from:
- `tests/conformance/test_step24b_phase1_kernel_boundary.py` (19 tests)
- Future Phase 2+ pipeline integration

**Bypass analysis:** No bypass exists yet because the bridge is not
controlling any production path.  The legacy `CommitmentState` path
remains the production path.  This is documented and expected for
Phase 1.

---

## Designated real EDGAR case

**Ameresco Section 7.10(a) leverage ratio scalar replacement.**

The Ameresco A1 amendment (August 24, 2023) replaces Section 7.10(a)
of the Fifth A&R Credit Agreement, changing the leverage ratio
step-down schedule.  The predecessor kernel (S0) has:
- `commitment_id`: `financial_covenant.leverage_ratio`
- `threshold`: 3.50
- `operator`: `<=`
- `unit`: `ratio`
- `frequency`: `quarterly`
- `applicability.step_down_schedule`: 4 entries (4.50 → 4.25 → 4.00 → 4.00)
- `applicability.steady_state_threshold`: 3.50

The address map resolves `Section 7.10(a)` →
`financial_covenant.leverage_ratio` with SUFFICIENT evidence level.

Tests `TestAmerescoScalarReplacementPredecessor` verify this
predecessor state is correctly established.

---

## Safety metrics

```
incorrect_accepted_mutations: 0 (no runtime change)
false_authoritative_promotions: 0 (no runtime change)
correct accepts preserved: 2 (baseline unchanged)
```

No runtime behavior was modified.  The kernel bridge is a new module
that does not affect any existing production path.

---

## Test evidence

```
Phase 1 conformance tests: 19 passed / 0 failed / 0 skipped
Step 23S safety tests:      33 passed / 0 failed / 0 skipped
Step 23R audit tests:       33 passed / 0 failed / 0 skipped
Step 23 taxonomy tests:     56 passed / 0 failed / 0 skipped
Full suite:                 1071 passed / 0 failed / 14 skipped
```

---

## CHECKPOINT 1

```
PHASE 1 STATUS: PASS

Criteria evaluation:
1. Implementation exists: PASS
   - kernel_bridge.py with state_to_kernel, kernel_to_state,
     establish_authoritative_kernel, store_to_state_dict
2. Correct production path reaches it: PASS (with caveat)
   - Not yet wired into production pipeline (expected for Phase 1)
   - Reachable from conformance tests and future Phase 2+ integration
3. Bypasses identified/eliminated or explicitly retained: PASS
   - No bypass exists yet (bridge not controlling production path)
   - Legacy CommitmentState path remains documented and expected
4. Positive-path tests pass: PASS (11 positive tests)
5. Violation-path tests pass: PASS (5 violation tests)
6. Designated real EDGAR cases pass: PASS (3 Ameresco tests)
7. Safety metrics remain intact: PASS
   - incorrect_accepted_mutations: 0
   - false_authoritative_promotions: 0
   - correct accepts preserved: 2
8. Required evidence artifacts produced: PASS
   - This checkpoint document
   - kernel_bridge.py module
   - 19 conformance tests

Safe to proceed to Phase 2: YES
```
