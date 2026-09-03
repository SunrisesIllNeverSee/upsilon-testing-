# Commitment Kernel

**Step 23M design document — Component 2: Canonical Commitment
Kernel.**

This document specifies the semantic commitment object that MOSES
governs.  No runtime code is modified.

---

## 1. Purpose

The `CommitmentKernel` is the state object that transformations
operate over.  It is the canonical representation of a commitment at
a point in time.  The governing state model is:

```
C_t = C_{t-1} ⊕ Δ_t_authorized
```

The kernel is `C_{t-1}` (predecessor) and `C_t` (successor).
Transformations produce deltas; the kernel is what the delta applies
to.

---

## 2. Current state: CommitmentState

The current runtime object is `CommitmentState`
(`models.py:97-123`), a 22-field dataclass.  The forensic audit
(`forensic_qa/001_moses_commitment_theory_audit.md` Q5) found:

**Active fields** (read/written by resolver/executor at runtime):

| Field | Read by | Written by |
|-------|---------|------------|
| `canonical_key` | state dict key | executor |
| `threshold` | resolver | executor |
| `rate` | resolver | executor |
| `deadline` | resolver | executor |
| `exceptions` | resolver | executor |
| `party` | resolver | executor |
| `status` | executor | executor |
| `valid_from`, `valid_to` | — | executor (WAIVE) |
| `applicability` | — | executor (WAIVE) |

**Dormant fields** (defined but never read/written at runtime):

```
commitment_type, modality, action, subject, operator, unit,
frequency, scope, trigger, grace_period, cure, application_order
```

14 of 22 fields are dormant.  The kernel design must determine which
dormant fields get explicit semantic responsibility.

---

## 3. Kernel field categories

### Identity-bearing

What makes this the same commitment over time?

| Field | Responsibility | Current status |
|-------|---------------|----------------|
| `commitment_id` | Stable semantic identifier within the agreement | NEW (replaces `canonical_key` as the identity carrier; see `COMMITMENT_IDENTITY.md`) |
| `canonical_key` | Frozen 13-class experimental family identifier | ACTIVE — remains as the commitment family classification |
| `commitment_type` | The type of commitment (financial_covenant, facility, etc.) | DORMANT — activate as identity metadata |
| `agreement_identity` | The agreement this commitment belongs to | NEW |
| `identity_provenance` | How identity was established | NEW (see `COMMITMENT_IDENTITY.md`) |

The `commitment_id` is the persistent identity.  The `canonical_key`
is the frozen 13-class family.  These are distinct: the family is
experimental scope; the identity is the stable semantic handle.

### Mutable semantic state

Fields that transformations may modify:

| Field | Responsibility | Current status |
|-------|---------------|----------------|
| `threshold` | Numeric threshold value | ACTIVE |
| `operator` | Comparison operator (≥, ≤, =, >, <) | DORMANT — activate |
| `unit` | Unit of measurement (ratio, dollars, percent) | DORMANT — activate |
| `frequency` | Testing frequency (quarterly, continuous, annual) | DORMANT — activate |
| `scope` | Scope of application (entities, transactions covered) | DORMANT — activate |
| `exceptions` | Carve-outs and exceptions | ACTIVE |
| `trigger` | Conditions that trigger the commitment | DORMANT — activate |
| `cure` | Cure/grace period semantics | DORMANT — activate |
| `applicability` | Conditional applicability predicates | ACTIVE (WAIVE only) — expand |
| `rate` | Interest rate or similar rate value | ACTIVE |
| `deadline` | Deadline or date constraint | ACTIVE |
| `party` | Parties bound by the commitment | ACTIVE |
| `action` | The action required or prohibited | DORMANT — activate |
| `subject` | The subject matter of the commitment | DORMANT — activate |
| `modality` | Modality (obligation, prohibition, permission) | DORMANT — activate |

### Temporal state

| Field | Responsibility | Current status |
|-------|---------------|----------------|
| `valid_from` | When this version becomes effective | ACTIVE |
| `valid_to` | When this version ceases to be effective | ACTIVE |
| `status` | ACTIVE / WAIVED / SUSPENDED / TERMINATED | ACTIVE |
| `grace_period` | Grace period before enforcement | DORMANT — activate |
| `application_order` | Order of application relative to other commitments | DORMANT — activate |

### Evidentiary / provenance state

| Field | Responsibility | Current status |
|-------|---------------|----------------|
| `source_document` | Document from which this version was extracted | NEW |
| `source_span` | Text span in the source document | NEW |
| `defined_term_support` | Defined terms referenced by this commitment | NEW |
| `lineage_reference` | Reference to the lineage edge that produced this version | NEW |
| `authority_status` | Authority decision for this version | NEW (see `SEMANTIC_AUTHORITY_GATE.md`) |
| `proof_reference` | Reference to the semantic proof record | NEW (see `SEMANTIC_PROOF_RECORD.md`) |

---

## 4. The 13 frozen classes vs. the kernel

Per the Step 23M addendum §4:

> Do NOT broaden the 13-class experimental scope.  However, do NOT
> treat the 13 classes as the complete semantic content of a
> commitment.  Treat them as experimental canonical commitment
> families while the Commitment Kernel carries richer legal semantics.

The 13 classes (`commitment_registry.py:67-86`) are:

```
facility.revolving_facility
facility.term_loan
facility.letter_of_credit
financial_covenant.leverage_ratio
financial_covenant.interest_coverage
financial_covenant.debt_service_coverage
financial_covenant.current_ratio
financial_covenant.tangible_net_worth
financial_covenant.fixed_charge_coverage
financial_covenant.minimum_net_worth
financial_covenant.restricted_payments
financial_covenant.default
financial_covenant.guarantor
```

These are the `canonical_key` values — the experimental commitment
families.  The kernel carries richer semantics (party, action,
subject, operator, threshold, unit, frequency, exceptions, scope,
trigger, effective dates, status, cure/grace, source section/span,
parent identity, provenance).

**Transformation richness does not require expanding commitment-family
scope.**  A `SCALAR_REPLACEMENT` that changes a threshold from 4.00 to
3.75 does not create a new commitment class.  A
`MULTI_FIELD_REPLACEMENT` that changes both threshold and operator
does not create a new commitment class.  The 13 classes are frozen;
the transformation algebra is not.

---

## 5. Origin Kernel vs. Current Kernel

Per the Step 23M addendum §5, the architecture explicitly
distinguishes:

```
C0  = AUTHORITATIVE ORIGIN KERNEL
C*t = AUTHORITATIVE CURRENT KERNEL
D_t = DOWNSTREAM REPRESENTATION
```

### C0 — Origin Kernel

The origin kernel is the set of commitments extracted from the source
agreement (S0).  It is established by the commitment extractor from
the original credit agreement.  It is the starting point for all
amendment transformations.

The origin kernel is **human-validated / independently established**
(addendum §6).  The amendment interpreter begins with an authoritative
predecessor object whenever one is available.  It does not rediscover
the complete commitment from amendment text at every step.

### C*t — Current Authoritative Kernel

The current authoritative kernel is the set of commitments that
results from applying all authorized transformations from C0 through
the current amendment.  It is computed as:

```
C*t = Apply(C*t-1, Δ_t)
```

where each `Δ_t` has a valid proof record and has passed conservation
validation.

### D_t — Downstream Representation

Downstream representations are projections of the authoritative
kernel: risk models, covenant trackers, credit memos, policy systems,
AI-generated summaries.  Propagation Integrity (a future phase) checks
that `D_t` matches `C*t`.

### Three integrity questions

| Domain | Question |
|--------|----------|
| Transformation Integrity | Did `Δ_t` produce the correct `C_t` from `C_{t-1}`? |
| Lineage Integrity | Is `C*t` reachable from `C0` through valid lineage edges? |
| Propagation Integrity | Does `D_t` match `C*t`? |

These must not be collapsed.  Current Step 23/24 work is primarily
Transformation Integrity.

---

## 6. Kernel versioning

Each transformation produces a new **version** of the kernel.  The
version is identified by:

```python
class KernelVersion:
    commitment_id: str
    version_number: int      # monotonic within a chain
    valid_from: datetime
    valid_to: datetime | None
    produced_by_proof_id: str
    predecessor_version: int | None
```

The version is immutable once produced.  A new transformation produces
a new version; it does not mutate the existing one.  This supports
lineage tracing and temporal queries (`COMMITMENT_LINEAGE_SCHEMA.md`
temporal authority rule `K(A,T)`).

---

## 7. Do not blindly activate every dormant field

The forensic audit found 14 dormant fields.  The kernel design
activates fields that have **explicit semantic responsibility** for
the transformation algebra and conservation invariants.

### Activation criteria

A field is activated if and only if:

1. At least one transformation family reads or writes it, OR
2. At least one conservation invariant checks it, OR
3. It is required for the proof record.

Fields that do not meet these criteria remain dormant.  They are not
activated for coverage's sake.

### Activation plan

| Field | Activated by | Reason |
|-------|-------------|--------|
| `operator` | SCALAR_REPLACEMENT, conservation (old-value consistency) | The operator determines what "old value" means |
| `unit` | SCALAR_REPLACEMENT, conservation (no unsupported semantic gain) | Unit changes are semantic changes |
| `frequency` | TEMPORAL_STEP_CHANGE, conservation (temporal validity) | Frequency changes are temporal transformations |
| `scope` | EXCEPTION_EXPANSION/CONTRACTION, conservation (no silent semantic loss) | Scope changes affect what's conserved |
| `trigger` | WAIVER, REINSTATEMENT, conservation (temporal validity) | Triggers determine when commitments apply |
| `cure` | WAIVER, REINSTATEMENT, conservation (temporal validity) | Cure periods affect temporal state |
| `action` | All transformation families | The action is part of the commitment's semantic identity |
| `subject` | All transformation families | The subject is part of the commitment's semantic identity |
| `modality` | All transformation families | Modality (obligation/prohibition/permission) affects conservation |
| `application_order` | Conservation (transformation completeness) | Order matters for multi-commitment interactions |
| `commitment_type` | Identity (identity-bearing metadata) | Part of the kernel's identity metadata |

Fields not in this table remain dormant until a future step
explicitly activates them.

---

## 8. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q5, Q11 —
  CommitmentState audit, 13-class audit
- `models.py:97-123` — current `CommitmentState` dataclass
- `commitment_registry.py:67-86` — 13 frozen canonical classes
- `COMMITMENT_LINEAGE_SCHEMA.md` — temporal authority rule `K(A,T)`
- `.devin/rules.md` — prohibited action #6 (broadening frozen ontology)
