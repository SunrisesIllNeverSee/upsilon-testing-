# Semantic Authority Gate

**Step 23M design document — Component 6: Semantic Authority Gate.**

This document specifies the authority promotion contract.  No runtime
code is modified.

---

## 1. Current behavior (forensic finding)

The current authority determination
(`semantic_pipeline_v2.py:247-251`) reduces to:

```
execution complete
+
nothing unresolved
=
authoritative
```

This is a **completeness-only check**.  It does not verify that the
applied mutation is semantically correct.  The incorrect-mutation
detection runs post-hoc (after the full chain) by comparing to ground
truth — it is not available at authority-determination time.

### The false authoritative promotion

The forensic audit (`forensic_qa/001_moses_commitment_theory_audit.md`
Q4, Final Output F) documented the single false authoritative
promotion:

- **Chain:** HELD-017, Amendment A1
- **Path:** Source text (IDHC Acquisition financing) → parser (ADD,
  Article III) → resolver ("Revolving Loans" alias matched
  `facility.revolving_facility`) → mapper
  (`_rule_exception_add_remove` found "Notwithstanding") → candidate
  (ADD exceptions, confidence 0.85) → validator (`hasattr` check
  passed) → executor (`c.exceptions.append()` applied) → authority
  (COMPLETE + 0 unresolved + 0 inherited = **authoritative**)
- **Missing invariant:** "A step shall not be promoted to
  authoritative if any mutation applied at or before that step is
  semantically incorrect."  This invariant is NOT IMPLEMENTED at
  runtime.

---

## 2. Target authority contract

Authority must no longer be reducible to `execution complete + nothing
unresolved`.  Semantic authority requires:

```
AUTHORITY_GRANTED
iff
proof_completeness == COMPLETE
AND proof_validity == VALID
AND required conservation invariants pass
AND execution succeeds
AND lineage is valid
AND no blocking inherited/own unresolved state
```

### Proof completeness vs. proof validity

**Completeness** is a structural property: all required proof fields
are populated.

**Validity** is a semantic property: the populated evidence actually
supports the transformation that was executed.

A completely populated wrong proof is still wrong.  For example:

```
target = leverage_ratio
old = 4.0
new = 15.0
evidence = populated
checks = populated
```

could be syntactically COMPLETE while semantically INVALID (the
amendment may not actually target the leverage ratio, or the old
value may not match the predecessor).

The proof record carries two distinct status fields:

```
proof_completeness: COMPLETE / INCOMPLETE
proof_validity:     VALID / INVALID / INDETERMINATE
```

Authority requires both `COMPLETE` and `VALID`.  Ground-truth labels
must never participate in production authority decisions — they
remain audit/evaluation data only.

---

## 3. Authority states

```
AUTHORITY_GRANTED
```
The step is promoted to authoritative.  The successor kernel `C_t`
becomes the current authoritative kernel `C*t`.  The lineage edge is
confirmed.

```
AUTHORITY_BLOCKED
```
The step is NOT promoted.  A conservation invariant failed, or the
proof record is INCOMPLETE, or execution failed.  The predecessor
kernel `C_{t-1}` remains the current authoritative kernel.  The
failure is recorded.

```
VALIDATION_REQUIRED
```
The step is provisionally accepted but requires validation before
promotion.  This is used when target identity evidence is
CORROBORATED but not SUFFICIENT, or when uncertainty is MEDIUM.  The
step does NOT become authoritative until validation completes.

```
PARTIAL
```
Some instructions in the step were applied, some were unresolved.  The
resulting state is provisional and must NOT be promoted to
authoritative.  This is equivalent to the current `PARTIAL` execution
status, but with the added requirement that partial results cannot
become authoritative even if no unresolved instructions remain in the
current step (because inherited unresolved state may block).

```
UNRESOLVED
```
No instructions were applied (all failed).  No state change.  The
predecessor kernel remains authoritative.

---

## 4. Authority gate inputs

| Input | Source | Required for |
|-------|--------|-------------|
| Execution result | Layer F (execution) | All states |
| Proof record | Layer E (semantic proof) | AUTHORITY_GRANTED |
| Conservation validation results | Layer D (conservation) | AUTHORITY_GRANTED |
| Inherited unresolved state | Chain context | AUTHORITY_GRANTED |
| Lineage edge | Layer F (execution) | AUTHORITY_GRANTED |

---

## 5. Authority gate decision logic

```
IF execution_result.status == UNRESOLVED:
    → UNRESOLVED

IF execution_result.status == PARTIAL:
    → PARTIAL

IF execution_result.status == COMPLETE:
    IF proof_record.completeness == INCOMPLETE:
        → AUTHORITY_BLOCKED
    IF proof_record.validity == INVALID:
        → AUTHORITY_BLOCKED
    IF any conservation_check FAILED:
        → AUTHORITY_BLOCKED
    IF inherited_unresolved > 0:
        → AUTHORITY_BLOCKED
    IF proof_record.evidence_status == INSUFFICIENT:
        → AUTHORITY_BLOCKED
    IF proof_record.uncertainty_status == HIGH:
        → VALIDATION_REQUIRED
    IF proof_record.target_identity_evidence.evidence_level == WEAK:
        → VALIDATION_REQUIRED
    IF proof_record.validity == INDETERMINATE:
        → VALIDATION_REQUIRED
    ELSE:
        → AUTHORITY_GRANTED
```

### Key differences from current behavior

1. **Proof record is required.**  The current runtime has no proof
   record.  The gate cannot grant authority without one.
2. **Completeness is not validity.**  A COMPLETE proof that is INVALID
   blocks authority.  A COMPLETE proof that is INDETERMINATE routes to
   VALIDATION_REQUIRED.
3. **Conservation checks are required.**  The current runtime has no
   conservation validation (the `_validate_candidate` `hasattr` check
   is not conservation validation).
4. **Evidence status matters.**  INSUFFICIENT evidence blocks
   authority.  WEAK evidence routes to VALIDATION_REQUIRED.
5. **Uncertainty matters.**  HIGH uncertainty routes to
   VALIDATION_REQUIRED, not auto-promotion.

---

## 6. Evaluation truth must never become production logic (Constraint #4)

The authority gate must NOT depend on:

```
ground_truth_correct = true
```

or any equivalent answer-key information.  The Step 23R independently
adjudicated labels are test/diagnostic oracles, not production lookup
data.

Production runtime establishes validity using:

- operational evidence (amendment text, source spans, defined terms);
- MOSES invariants (conservation checks, identity persistence,
  target/reference separation);
- proof records (structured evidence objects).

The authority gate consumes these operational artifacts.  It does NOT
consume ground-truth labels, expected values, or independent
eligibility classifications from the audit.

---

## 7. Consume existing systems, do not replace them

The authority gate should consume existing lineage/temporal
architecture, not replace it.  Specifically:

- **`chain_reconstruction.py`** chain-aware authority model: a step is
  authoritative iff execution is COMPLETE, no inherited unresolved
  uncertainty remains, and own unresolved is zero.  The authority
  gate extends this with the proof-record and conservation-check
  requirements.
- **`executor.py`** execution result: the gate consumes the
  `ExecutionResult` (applied/unresolved lists, state).
- **`COMMITMENT_LINEAGE_SCHEMA.md`** temporal authority rule `K(A,T)`:
  the gate confirms that the successor kernel satisfies the temporal
  authority rule before promotion.

The gate does NOT redesign these systems.  It adds the semantic-proof
and conservation-validation preconditions that the current authority
determination lacks.

---

## 8. Authority and the 10 incorrect accepts

The 10 incorrect accepted mutations and the 1 false promotion would
be blocked by the authority gate as follows:

| ID | Root cause | Authority gate action |
|----|-----------|----------------------|
| EDGAR-AMERESCO:A1:I5 | Section heuristic + wrong paragraph | Old-value consistency check FAILS (3.5 ≠ 4.00 in predecessor) → AUTHORITY_BLOCKED |
| EDGAR-AMERESCO:A2:I4 | Same as A1:I5 | Old-value consistency FAILS (3.5 ≠ 3.75) → AUTHORITY_BLOCKED |
| STUDY-007:A2:I2 | Wrong paragraph span | Old-value consistency FAILS ($10M ≠ 7.00) → AUTHORITY_BLOCKED |
| STUDY-016:A2:I1 | Definitions section | Target identity INSUFFICIENT → AUTHORITY_BLOCKED |
| STUDY-016:A2:I2 | Section heuristic overrode text | Target identity INSUFFICIENT (text says "current ratio", section says "leverage") → AUTHORITY_BLOCKED |
| HELD-010:A11:I6 | Alias priority wrong | Target identity WEAK (alias conflict) → VALIDATION_REQUIRED (not auto-promoted) |
| HELD-017:A1:I1 | OUT_OF_SCOPE unauthorized | OUT_OF_SCOPE isolation FAILS → AUTHORITY_BLOCKED |
| HELD-017:A4:I1 | Same | OUT_OF_SCOPE isolation FAILS → AUTHORITY_BLOCKED |
| HELD-017:A4:I2 | Same | OUT_OF_SCOPE isolation FAILS → AUTHORITY_BLOCKED |
| HELD-017:A4:I3 | Same | OUT_OF_SCOPE isolation FAILS → AUTHORITY_BLOCKED |

The 1 false promotion (HELD-017 A1) is blocked because
AUTHORITY_BLOCKED on A1:I1 prevents the step from becoming
authoritative.

**This is design analysis, not implementation.**  Step 23S implements
the safety repairs; Step 23M only specifies the contract.

---

## 9. Layer contract

Authority promotion is Layer G from `MOSES_RUNTIME_CONTRACT.md`.

| | |
|---|---|
| **Inputs** | Execution result, proof record, conservation validation results, inherited unresolved state |
| **Outputs** | Authority decision: AUTHORITY_GRANTED / AUTHORITY_BLOCKED / VALIDATION_REQUIRED / PARTIAL / UNRESOLVED |
| **May do** | Consume execution + proof + conservation + lineage status; determine if the step may be promoted to authoritative |
| **Must not do** | Inspect raw EDGAR text to infer meaning; perform validation; construct transformations; execute |
| **Failure behavior** | If any required input is missing or failed, authority is BLOCKED.  No path may promote a step with a failed proof record or failed conservation validation. |

---

## 10. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q4, Final Output F
  — false authoritative promotion
- `semantic_pipeline_v2.py:247-251` — current authority
  determination (completeness-only)
- `chain_reconstruction.py` — chain-aware authority model
- `COMMITMENT_LINEAGE_SCHEMA.md` — temporal authority rule `K(A,T)`
- `MOSES_RUNTIME_CONTRACT.md` — layer contracts
- `SEMANTIC_PROOF_RECORD.md` — proof record schema
- `CONSERVATION_INVARIANTS.md` — conservation checks
