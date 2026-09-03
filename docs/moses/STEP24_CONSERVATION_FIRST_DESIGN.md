# Step 24 Conservation-First Design

**Step 23M design document — Step 23S repair mapping and Step 24
implementation boundary.**

This document identifies how the 10 incorrect accepts + 1 false
promotion should be repaired under the MOSES invariants (Step 23S),
and states exactly what Step 24 should implement after Step 23S
restores safety.  No runtime code is modified.

---

## 1. Sequence

```
Step 23M (this document)
  → define semantic contracts
  → review contracts

Step 23S (safety restoration)
  → implement runtime enforcement for safety invariants
  → verify: incorrect_accepted = 0, false_authoritative_promotions = 0
  → verify: conformance tests for safety invariants pass

Step 24 (coverage)
  → implement transformation families for coverage
  → migrate responsibilities into target modules (only after
    contracts are reviewed and enforcement is implemented)
```

No runtime modules are moved during Step 23M.  Migration is authorized
only after the contracts in this package are reviewed and runtime
enforcement is implemented (Constraint #1).

---

## 2. Step 23S — Safety repair mapping

Step 23S restores safety by implementing the runtime enforcement for
the invariants that block the 10 incorrect accepted mutations and the
1 false authoritative promotion.

**Do NOT implement the repair in Step 23M.**  This section only
identifies which invariant family each repair belongs to.

### 2.1 The 6 IN_SCOPE incorrect accepted mutations

| ID | Root cause | Repair invariant family | How |
|----|-----------|------------------------|-----|
| EDGAR-AMERESCO:A1:I5 | Section heuristic + wrong paragraph | **Old-value consistency** (§2.2) + **target/reference separation** (§2.6) | The `AuthorizedTransformationEngine` establishes target identity from evidence + predecessor state, then checks `declared_old_value == C_{t-1}[field]`.  The wrong paragraph (3.5 vs 4.00) fails the old-value check. |
| EDGAR-AMERESCO:A2:I4 | Same as A1:I5 | **Old-value consistency** (§2.2) | Same: 3.5 vs 3.75 fails the old-value check. |
| STUDY-007:A2:I2 | Wrong paragraph span | **Old-value consistency** (§2.2) | $10M vs 7.00 fails the old-value check. |
| STUDY-016:A2:I1 | Definitions section | **Target/reference separation** (§2.6) | The definitions section is a reference, not a target.  Target identity evidence is INSUFFICIENT → fail closed. |
| STUDY-016:A2:I2 | Section heuristic overrode text | **Target/reference separation** (§2.6) + **semantic equivalence** (alias policy) | Text says "current ratio", section heuristic says "leverage".  Agreement-local address map resolves correctly; global section heuristic is not authoritative. |
| HELD-010:A11:I6 | Alias priority wrong | **Target/reference separation** (§2.6) + **semantic equivalence** (alias policy) | "Revolving Credit" (facility) vs "Leverage Ratio" (covenant) — these are different commitments.  Target identity must disambiguate using predecessor state, not alias priority. |

### 2.2 The 4 OUT_OF_SCOPE incorrect accepted mutations

| ID | Root cause | Repair invariant family | How |
|----|-----------|------------------------|-----|
| HELD-017:A1:I1 | "Revolving Loans" in debt incurrence | **OUT_OF_SCOPE isolation** (§2.9) + **target/reference separation** (§2.6) | Source text contains debt-incurrence signals AND target is a facility class → fail closed.  This is a reference, not a target. |
| HELD-017:A4:I1 | Same | **OUT_OF_SCOPE isolation** (§2.9) | Same. |
| HELD-017:A4:I2 | Same | **OUT_OF_SCOPE isolation** (§2.9) | Same. |
| HELD-017:A4:I3 | Same | **OUT_OF_SCOPE isolation** (§2.9) | Same. |

### 2.3 The 1 false authoritative promotion

| ID | Root cause | Repair invariant family | How |
|----|-----------|------------------------|-----|
| HELD-017 A1 (step-level) | Authority is completeness-only | **Semantic authority** (`SEMANTIC_AUTHORITY_GATE.md`) | The authority gate requires a COMPLETE proof record with passing conservation checks.  The incorrect mutation on A1:I1 fails conservation → AUTHORITY_BLOCKED → no false promotion. |

### 2.4 Repair summary by invariant family

| Invariant family | Incorrect accepts blocked | False promotions blocked |
|---|---:|---:|
| Old-value consistency | 3 | 1 (indirect) |
| Target/reference separation | 3 | 0 |
| Semantic equivalence (alias policy) | 2 | 0 |
| OUT_OF_SCOPE isolation | 4 | 1 (direct) |
| Semantic authority | 0 | 1 (direct) |
| **Total** | **10** | **1** |

### 2.5 No lexical patches

The repairs are NOT lexical patches.  The prohibited approach is:

```
ADD + long text + exception + debt words = reject
```

The required approach is:

```
Establish target identity from evidence + predecessor state
→ Verify the amendment targets the conserved commitment
→ Verify old-value consistency (if applicable)
→ Check OUT_OF_SCOPE isolation
→ Require a COMPLETE proof record for authority
```

This is semantic reasoning, not regex heuristics.

### 2.6 Step 23S verification

Step 23S is complete when:

```
incorrect_accepted_mutations = 0
false_authoritative_promotions = 0
```

and the conformance tests for the safety invariants (old-value
consistency, target/reference separation, OUT_OF_SCOPE isolation,
semantic authority) pass with both positive and violation-path tests
per the Conformance Promotion Rule.

---

## 3. Step 24 — Implementation boundary

Step 24 implements coverage after Step 23S restores safety.  The
build sequence is reframed under the new architecture.

### 3.1 Step 24 Phase 1 — AuthorizedTransformationEngine (safety layer)

**Implement:** The `AuthorizedTransformationEngine` (Layer B from
`MOSES_RUNTIME_CONTRACT.md`).

- Contract: `(C_{t-1}, E_t, A_t) → Δ_t`
- Establish target identity from evidence + predecessor state
- Determine transformation type and affected fields
- **Activate predecessor-state consistency validation.**  Where
  amendment evidence independently declares an old value, require that
  value to match the authoritative predecessor.  Where no old value
  is independently declared, do NOT fabricate one solely to satisfy
  the executor guard — mark the conservation check `NOT_APPLICABLE`.
- The proper sequence is:
  ```
  independently establish target
    → identify proposed field/transformation
    → extract amendment-side old value when explicitly present
    → compare amendment-side old value with predecessor
  ```
- Predecessor state constrains interpretation but does not
  manufacture independent evidence.

**Effect:** Blocks 6 IN_SCOPE incorrect accepts + 1 false promotion.

**Conformance tests:** old_value_matches_predecessor,
wrong_old_value_blocks_transform, reference_is_not_target,
predecessor_state_alone_does_not_prove_target.

### 3.2 Step 24 Phase 2 — Target-vs-Reference enforcement

**Implement:** General target-vs-reference enforcement in the
`AuthorizedTransformationEngine`.

A proposed mutation is executable only if there is affirmative
evidence that the instruction transforms the commitment.  Relevant
evidence may include:

- direct replacement/add/delete syntax scoped to the commitment;
- agreement-local section identity;
- predecessor section-to-commitment mapping;
- structural amendment target;
- semantic delta compatible with the identified commitment.

Mere mention, cross-reference, exception dependency, defined-term
use, or downstream effect is insufficient.

OUT_OF_SCOPE isolation falls out of the stronger semantic rule
instead of becoming a specialized heuristic.  **Do NOT implement a
debt-incurrence lexical blacklist.**  The HELD-017 failures are
solved because the amendment mentions Revolving Loans while changing
a debt-incurrence/acquisition-financing provision — the engine needs
target evidence, not a word filter.

**Effect:** Blocks 4 OUT_OF_SCOPE incorrect accepts.

**Conformance tests:** out_of_scope_instruction_cannot_mutate_state,
reference_is_not_target.

### 3.3 Step 24 Phase 3 — Authority correctness gate

**Implement:** The semantic authority gate (Layer G from
`MOSES_RUNTIME_CONTRACT.md`).

- Require a COMPLETE **and VALID** proof record for AUTHORITY_GRANTED
- Completeness is structural (all fields populated); validity is
  semantic (the evidence actually supports the transformation)
- Block authority on failed conservation checks
- Block authority on INVALID proof (a completely populated wrong
  proof is still wrong)
- Consume existing chain-aware authority from `chain_reconstruction.py`

**Effect:** Prevents false authoritative promotions (defense in
depth).

**Conformance tests:** incorrect_semantic_delta_cannot_be_authoritative,
authority_requires_valid_semantic_proof, proof_record_is_complete,
invalid_semantic_proof_cannot_execute.

### 3.4 Step 24 Phase 4 — TARGET_IDENTIFICATION with predecessor bias

**Implement:** Predecessor-state-biased target identification.

- Before text-based resolution, check if any commitment in
  `current_state` has a threshold/field consistent with the amendment
- Prefer existing commitments over text-only matches
- Use agreement-local address maps, not global section heuristics

**Effect:** Recovers up to 16 TARGET_IDENTIFICATION failures.

**Conformance tests:** identity_persists_across_amendment,
section_address_is_agreement_local.

### 3.5 Step 24 Phase 5 — RESTATE_SECTION decomposition

**Implement:** The `IDENTITY_PRESERVING_RESTATEMENT` transformation
family.

- Compare restated section text against predecessor state
- Derive `Δ = semantic_difference(C_prev, C_next_candidate)`
- Validate the delta against conservation invariants
- Preserve identity unless contrary evidence exists

**Effect:** Recovers up to 41 MULTI_FIELD_DECOMPOSITION failures.

**Conformance tests:** restatement_derives_correct_delta,
restatement_preserves_identity,
multi_field_change_cannot_partially_disappear.

### 3.6 Ordering constraint

Phases 1–3 (safety) must be completed and verified
(`incorrect_accepted = 0`, `false_authoritative_promotions = 0`)
before Phase 4 (coverage) begins.  Phase 5 requires the
`AuthorizedTransformationEngine` from Phase 1 and the conservation
validators from Phase 3.

---

## 4. Migration boundary

Step 24 implements runtime enforcement for the contracts defined in
this package.  Migration of responsibilities into the target
`src/upsilon/` package layout is authorized only after:

1. The contracts in `MOSES_RUNTIME_CONTRACT.md` and the component
   documents are reviewed.
2. Runtime enforcement is implemented (Step 24 Phases 1–3).
3. Conformance tests pass with both positive and violation-path tests
   per the Conformance Promotion Rule.

The prohibited sequence is:

```
move files → fix imports → green tests
```

The required sequence is:

```
define contracts → review contracts → implement enforcement →
  verify conformance → migrate responsibilities
```

---

## 5. Architectural interpretation (addendum §8)

> Does the forensic evidence indicate that Upsilon abandoned an
> adequate original MOSES architecture, or that the original
> architecture itself was insufficient?

**Answer: Upsilon abandoned an adequate original MOSES architecture.**

Evidence:

1. **The recovered original framework** (`ARCHITECTURE_INDEX.md`
   lines 12–22, `DEPENDENCY_DIRECTION.md` lines 12–22) describes:
   ```
   EDGAR → Agreement Chain → Parser → Commitment Extractor →
     Authoritative / validated Kernel → Amendment Parser →
     Authorized Change Engine → Commitment Lineage Graph →
     Current Authoritative Kernel
   ```
   This architecture has an `Authorized Change Engine` and a
   `Commitment Lineage Graph` as first-class components.  The current
   runtime has neither.

2. **Step 23R evidence** shows that the failure modes are
   interpretation failures and implementation gaps, not protocol
   insufficiencies (see `FAILURE_RECLASSIFICATION.md`): 0 of 84
   non-correct cases are true protocol insufficiency.

3. **Representability of predecessor/successor states:**
   `CommitmentState` (`models.py:97-123`) has the fields to represent
   both `C_{t-1}` and `C_t`.  The predecessor state is available at
   resolver entry but is passed as a dead parameter
   (`forensic_qa/001_moses_commitment_theory_audit.md` Q6, Q7).

4. **Representability of authorized transformations:** The
   transformation algebra (see `TRANSFORMATION_ALGEBRA.md`) defines 13
   families that cover the observed EDGAR behaviors.  All 58
   previously alleged protocol-insufficiency cases are representable
   under these families.

The original MOSES architecture is adequate.  The current runtime did
not implement it.  Step 23M is architectural restoration, not theory
extension.

---

## 6. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q3, Q4, Q29, Q30,
  Final Output E, F, I, J — incorrect accepted root causes, false
  promotion, leverage analysis, build sequence
- `docs/architecture/ARCHITECTURE_INDEX.md` — original architectural
  anchor
- `docs/architecture/DEPENDENCY_DIRECTION.md` — original pipeline
- `MOSES_RUNTIME_CONTRACT.md` — layer contracts
- `TRANSFORMATION_ALGEBRA.md` — transformation families
- `CONSERVATION_INVARIANTS.md` — invariant families
- `SEMANTIC_AUTHORITY_GATE.md` — authority gate
- `CONFORMANCE_MATRIX.md` — Conformance Promotion Rule
- `FAILURE_RECLASSIFICATION.md` — revised census
