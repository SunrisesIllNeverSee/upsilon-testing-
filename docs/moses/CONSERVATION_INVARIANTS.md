# Conservation Invariants

**Step 23M design document — Component 4: Conservation Validators.**

This document defines the explicit invariant checks that every
transformation must pass before execution.  No runtime code is
modified.

---

## 1. Governing principle

```
C_t = C_{t-1} ⊕ Δ_t_authorized
```

subject to:

```
Δ_t_actual = Δ_t_authorized
```

and, for every field outside the authorized transformation:

```
C_t[f] = C_{t-1}[f]   for all f not in affected(Δ_t)
```

Conservation does NOT mean preventing legitimate amendment changes.
It means:

- no unauthorized semantic change;
- no unexplained semantic loss;
- no unsupported semantic gain.

---

## 2. Invariant families

### 2.1 Identity persistence

```
ID(C_t) == ID(C_{t-1})
```

unless a validated identity-changing transformation (CREATE,
TERMINATE, SPLIT, MERGE, REDEFINE, RENUMBER) has been applied with
sufficient evidence.

**Applies to:** All transformation families except CREATE (which
assigns a new ID) and TERMINATE (which preserves ID but changes
status).

**Current status:** NOT YET ENFORCED.  The runtime does not persist
commitment identity across amendments (`forensic_qa/001_moses_commitment_theory_audit.md`
Q15).

### 2.2 Old-value consistency

Where the amendment states an old value:

```
declared_old_value == C_{t-1}[field]
```

**This is a conservation check, NOT interpretation evidence
(Constraint #3).**

The engine must NOT simply copy `old_value = predecessor[field]` and
then treat an executor check that `old_value == predecessor[field]`
as evidence that the semantic interpretation was correct.  That only
proves `x = x`.  It does not prove:

- the amendment targets the commitment;
- the amendment targets the field;
- the extracted transformation is authorized.

Old-value consistency is checked AFTER target/transformation evidence
has been established.  The sequence is:

```
1. Establish target identity (the amendment targets this commitment)
2. Establish field identity (the amendment targets this field)
3. Establish transformation authorization (the transformation is legal)
4. THEN check old-value consistency (conservation guard)
```

If the declared old value does not match the predecessor state, the
transformation is rejected.  The mismatch may indicate that the
amendment targets a different commitment, a different field, or that
the predecessor state is stale.

**Applies to:** SCALAR_REPLACEMENT, MULTI_FIELD_REPLACEMENT,
EXCEPTION_CONTRACTION, SCHEDULE_REPLACEMENT, TEMPORAL_STEP_CHANGE.

**Current status:** NOT YET ENFORCED.  The executor has an old-value
guard (`executor.py:119-122`) but the resolver never supplies
`old_value` (`semantic_resolver_v2.py:650-745`), so the guard never
fires.  This is the highest-leverage safety gap: activating it
prevents 6 of 10 incorrect accepted mutations and the 1 false
authoritative promotion.

### 2.3 Unchanged-field preservation

For every field outside the validated delta:

```
C_t[f] == C_{t-1}[f]
```

**Applies to:** All transformation families.  Every transformation
specifies its affected fields; all other fields must be preserved.

**Current status:** PARTIALLY ENFORCED.  The executor deep-copies
state before mutation (`executor.py:186`), so untargeted fields
normally survive.  However, `ADD`/`ADD_COMMITMENT` with a dict payload
constructs a new `CommitmentState` where missing fields get defaults,
silently dropping exceptions, scope, or other fields.  This is the
"no silent semantic loss" gap.

### 2.4 No unsupported semantic gain

Successor state may not acquire semantics unsupported by
evidence/transformation.

**Applies to:** All transformation families.  If the amendment does
not mention a new exception, the successor may not gain one.  If the
amendment does not change the scope, the successor may not broaden it.

**Current status:** NOT YET ENFORCED.  The 4 OUT_OF_SCOPE accepted
mutations from HELD-017 demonstrate this gap: the resolver generated
facility exception additions from acquisition/debt-incurrence
language that independent eligibility correctly classifies as
ancillary (`forensic_qa/001_moses_commitment_theory_audit.md` Q20).

### 2.5 No silent semantic loss

Existing semantics may not disappear without evidence of
removal/change.

**Applies to:** All transformation families.  If the predecessor has
exceptions, the successor must either preserve them, expand them, or
explicitly contract them with evidence.  An amendment that does not
mention exceptions may not silently drop them.

**Current status:** NOT YET ENFORCED.  When `ADD` creates a new
commitment to represent a legal successor, omitted fields receive
model defaults rather than being inherited from the predecessor
(`forensic_qa/001_moses_commitment_theory_audit.md` Q6).

### 2.6 Target/reference separation

```
REFERENCE TO COMMITMENT ≠ TRANSFORMATION TARGET OF COMMITMENT
```

A provision mentioning "Revolving Loans", "Term Facility", or
"Leverage Ratio" does not by itself prove that entity is being
modified.  A mutation may only be constructed after evidence
establishes the amendment provision actually targets the conserved
commitment.

**This is a controlling invariant.**  It addresses the root cause of
the 4 HELD-017 incorrect accepted mutations and 3 of the 6 IN_SCOPE
incorrect accepted mutations.

**Do NOT propose another lexical patch** such as `ADD + long text +
exception + debt words = reject`.  Solve this at semantic target
identity.  See `COMMITMENT_IDENTITY.md` §9 and the
`AuthorizedTransformationEngine` contract in
`TRANSFORMATION_ALGEBRA.md` §4.

### Target evidence levels

| Level | Evidence | Action |
|-------|----------|--------|
| **SUFFICIENT** | Amendment text explicitly targets the commitment (e.g., "Section 7.10 is hereby amended to...") | Proceed to transformation |
| **CORROBORATED** | Multiple evidence signals agree (section ref + alias + predecessor state consistency) | Proceed with proof record |
| **WEAK** | Single signal, no corroboration | Route to VALIDATION_REQUIRED; do not auto-promote |
| **INSUFFICIENT** | No target evidence, or contradictory evidence | Fail closed (UNRESOLVED) |

Insufficient target evidence must fail closed.  No path may construct
a mutation from a reference alone.

**Applies to:** All transformation families.  Target identity must be
established before any transformation is constructed.

**Current status:** NOT YET ENFORCED.  The current resolver does not
distinguish target from reference (`forensic_qa/001_moses_commitment_theory_audit.md`
Q12, `CONFORMANCE_CONTRACT.md` invariant #2).

### 2.7 Lineage continuity

Every accepted successor traces to predecessor + amendment evidence.

```
C_t → lineage_edge → C_{t-1} → lineage_edge → ... → C_0
```

**Applies to:** All transformation families.  Every accepted
transformation produces a lineage edge (see
`COMMITMENT_LINEAGE_SCHEMA.md` and the addendum §3).

**Lineage edge schema:**

```
predecessor_commitment_id
successor_commitment_id
amendment_id
authority_source
transformation_type
affected_fields
old_values
new_values
effective_date
source_span
proof_id
validation_status
```

**Current status:** NOT YET ENFORCED.  The lineage domain has no
current runtime implementation (`CONFORMANCE_CONTRACT.md` L1–L7).

### 2.8 Temporal validity

Schedules, waivers, reinstatements, and effective dates obey valid
state transitions.

**Rules:**

- `valid_from <= valid_to` (if `valid_to` is set)
- Waiver period must be within the commitment's active period
- Reinstatement requires a prior waiver
- Step schedules must be monotonic (no overlapping or backward steps)
- Amendment effective dates must be consistent with chain order

**Applies to:** WAIVER, REINSTATEMENT, TEMPORAL_STEP_CHANGE,
SCHEDULE_REPLACEMENT, CREATE, TERMINATE.

**Current status:** PARTIALLY ENFORCED.  There are 7 temporal
transition tests, but they do not comprehensively cover all temporal
validity constraints (`CONFORMANCE_CONTRACT.md` invariant #8).

### 2.9 OUT_OF_SCOPE isolation

Unsupported/out-of-scope provisions cannot mutate the frozen
commitment state.

**Rules:**

- If an instruction is classified as OUT_OF_SCOPE, no mutation is
  produced.
- If source text contains debt-incurrence signals ("Indebtedness",
  "Acquisition", "prepay", "defease") AND the target is a facility
  class, the transformation is likely a reference, not a target.  Fail
  closed.
- If a concept does not match any frozen class (e.g., "Asset Coverage
  Ratio" ≠ DSCR, "Minimum Working Capital" ≠ current ratio), classify
  as OUT_OF_SCOPE, UNSUPPORTED, or AMBIGUOUS — do not force into a
  frozen class.

**Applies to:** All transformation families.  OUT_OF_SCOPE isolation
is a precondition check before any transformation is constructed.

**Current status:** NOT YET ENFORCED.  The 4 OUT_OF_SCOPE accepted
mutations from HELD-017 demonstrate this gap
(`forensic_qa/001_moses_commitment_theory_audit.md` Q20).

### 2.10 Transformation completeness

A partially understood multi-field transformation may not silently
apply only the convenient subset and claim authority.

**Rules:**

- If a transformation affects N fields and only M < N can be
  extracted, the transformation FAILS.  No partial subset is applied.
- The proof record must list all affected fields.  If any is missing,
  the proof is INCOMPLETE.
- An incomplete proof does not proceed to execution.

**Applies to:** MULTI_FIELD_REPLACEMENT,
IDENTITY_PRESERVING_RESTATEMENT, DEFINED_TERM_PROPAGATION,
SCHEDULE_REPLACEMENT.

**Current status:** NOT YET ENFORCED.  41 of 78 failed IN_SCOPE
instructions fall into `MULTI_FIELD_DECOMPOSITION`
(`forensic_qa/001_moses_commitment_theory_audit.md` Final Output D).

---

## 3. Invariant-to-transformation matrix

| Invariant | SCALAR | MULTI | EXC_EXP | EXC_CON | SCHED | TEMP | WAIVER | REINSTATE | RESTATE | DEF_TERM | RENUMBER | TERMINATE | CREATE |
|-----------|--------|-------|---------|---------|-------|------|--------|-----------|---------|----------|----------|-----------|--------|
| Identity persistence | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | N/A |
| Old-value consistency | ✓ | ✓ | — | ✓ | ✓ | ✓ | — | — | ✓ | — | — | — | N/A |
| Unchanged-field preservation | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | N/A |
| No unsupported semantic gain | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| No silent semantic loss | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | N/A |
| Target/reference separation | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Lineage continuity | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Temporal validity | — | — | — | — | ✓ | ✓ | ✓ | ✓ | — | — | — | ✓ | ✓ |
| OUT_OF_SCOPE isolation | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Transformation completeness | — | ✓ | — | — | ✓ | ✓ | — | — | ✓ | ✓ | — | — | ✓ |

---

## 4. Alias policy

Aliases may only express genuine semantic equivalence.

### Suspicious/non-equivalent aliases identified

The forensic audit (`forensic_qa/001_moses_commitment_theory_audit.md`
Q11) identified three aliases asserting semantic equivalence rather
than spelling equivalence:

| Alias | Mapped to | Problem |
|-------|-----------|---------|
| Asset Coverage Ratio | `debt_service_coverage` | Asset coverage is a BDC-specific concept, not DSCR |
| Minimum Working Capital | `current_ratio` | Working capital is a dollar amount, current ratio is a ratio |
| Minimum Liquidity | `interest_coverage` | Liquidity is not interest coverage |

### Required behavior when concept ≠ frozen class

```
OUT_OF_SCOPE    — the provision is outside the commitment ontology
UNSUPPORTED     — the concept is real but not in the frozen 13 classes
AMBIGUOUS       — the concept might match but evidence is insufficient
```

Do not force non-equivalent concepts into frozen classes merely for
coverage.

### Distinct mechanisms

| Mechanism | Definition | May establish identity? |
|-----------|------------|------------------------|
| **alias** | Genuine semantic equivalence (spelling variant of the same concept) | Yes, as evidence |
| **related concept** | Semantically related but not equivalent | No — route to UNSUPPORTED |
| **defined-term expansion** | Expanding a defined term to its definition text | Yes, as evidence |
| **section address** | Agreement-local section reference | Yes, as evidence (through address map) |
| **semantic equivalence** | Two concepts are the same legal obligation | Yes, but requires proof |

Aliases are spelling equivalence (`"Consolidated Leverage Ratio"` →
`leverage_ratio`).  They are NOT semantic equivalence assertions
(`"Asset Coverage Ratio"` → `debt_service_coverage` is wrong).

---

## 5. Conservation validation layer contract

Conservation validation is Layer D from `MOSES_RUNTIME_CONTRACT.md`.

| | |
|---|---|
| **Inputs** | Candidate successor `C_t_candidate`, predecessor `C_{t-1}`, authorized transformation `Δ_t` |
| **Outputs** | Validation results: pass/fail per invariant, with failure reasons |
| **May do** | Check all 10 invariant families; report which passed and which failed |
| **Must not do** | Perform raw EDGAR parsing; construct transformations; grant authority; execute |
| **Failure behavior** | If any invariant fails, the candidate is rejected.  Rejection prevents execution.  The failure is recorded in the proof record. |

Validation runs AFTER the `AuthorizedTransformationEngine` produces
`Δ_t` and BEFORE execution.  It is a precondition for execution, not
a post-hoc check.

---

## 6. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q11, Q16, Q20 —
  alias audit, old-value audit, OUT_OF_SCOPE audit
- `executor.py:119-122` — existing old-value guard (never activated)
- `executor.py:186` — deep-copy for unchanged-field preservation
- `CONFORMANCE_CONTRACT.md` — existing 13 invariant families
- `COMMITMENT_LINEAGE_SCHEMA.md` — lineage edge schema
- `MOSES_RUNTIME_CONTRACT.md` — layer contracts
- `TRANSFORMATION_ALGEBRA.md` — transformation families
