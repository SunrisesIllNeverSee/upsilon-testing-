# Transformation Algebra

**Step 23M design document — Component 3: Transformation Algebra.**

This document specifies the legal transformation families over
commitment state and the `AuthorizedTransformationEngine` contract.
No runtime code is modified.

---

## 1. Governing formula

```
C_t = T(C_{t-1}, E_t)
```

or equivalently, from the addendum:

```
C_t = C_{t-1} ⊕ Δ_t_authorized
```

where:

```
C_{t-1} = authoritative predecessor commitment
E_t     = amendment evidence
A_t     = authority / lineage context
Δ_t     = authorized semantic transformation
```

The `AuthorizedTransformationEngine` contract is:

```
(C_{t-1}, E_t, A_t) → Δ_t
```

Then:

```
C_t = Apply(C_{t-1}, Δ_t)
```

This component is distinct from evidence extraction (Layer A) and from
execution (Layer F).  It owns transformation interpretation and
authorization reasoning, not raw document parsing.

---

## 2. Transformation families

The 13 transformation families cover evidence-supported real EDGAR
behavior.  **These are NOT new commitment classes.**  The 13 frozen
commitment classes (`commitment_registry.py:67-86`) are unchanged.
Transformation richness and ontology breadth are different questions.

### 2.1 SCALAR_REPLACEMENT

Replace a single scalar field value.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with the target field populated |
| **Required evidence** | Amendment text specifying the new value; target identity evidence; old-value evidence (the amendment may state "from X to Y" or just "to Y") |
| **Affected fields** | One scalar field (e.g., `threshold`, `rate`, `deadline`) |
| **Preserved fields** | All fields except the affected one |
| **Valid successor conditions** | `C_t[field] = new_value`; `C_t[f] = C_{t-1}[f]` for all other f; `ID(C_t) = ID(C_{t-1})` |
| **Failure conditions** | Target identity not established; field not identified; new value not extractable; old-value mismatch (if old value stated in amendment) |

**Old-value consistency (Constraint #3):** The engine must first
establish (1) the amendment targets the commitment, (2) the amendment
targets the field, (3) the transformation is authorized.  Only then
may it verify `declared_old_value == C_{t-1}[field]` as a conservation
check.  It must NOT simply copy `old_value = C_{t-1}[field]` and
treat `old_value == C_{t-1}[field]` as evidence of correct
interpretation — that proves only `x = x`.

### 2.2 MULTI_FIELD_REPLACEMENT

Replace multiple fields in a single transformation.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with the target fields populated |
| **Required evidence** | Amendment text specifying multiple new values; target identity evidence |
| **Affected fields** | Two or more fields (e.g., `threshold` + `operator`, or `threshold` + `unit`) |
| **Preserved fields** | All fields except the affected ones |
| **Valid successor conditions** | All affected fields have new values; all preserved fields unchanged; identity persists |
| **Failure conditions** | Target identity not established; any affected field's new value not extractable; partial extraction (only some fields extracted) — fail closed, do NOT apply a partial subset |

**Transformation completeness:** A partially understood multi-field
transformation may not silently apply only the convenient subset and
claim authority.  If the amendment changes 3 fields and only 2 can be
extracted, the transformation fails.  This is the
`transformation_completeness` conservation invariant (see
`CONSERVATION_INVARIANTS.md`).

### 2.3 EXCEPTION_EXPANSION

Add one or more exceptions to a commitment.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with an `exceptions` list |
| **Required evidence** | Amendment text adding an exception; target identity evidence; the exception text |
| **Affected fields** | `exceptions` (append) |
| **Preserved fields** | All fields except `exceptions` |
| **Valid successor conditions** | `C_t.exceptions = C_{t-1}.exceptions + [new_exception]`; all other fields unchanged |
| **Failure conditions** | Target identity not established; exception text not extractable; the amendment does not actually target this commitment's exceptions |

**OUT_OF_SCOPE isolation:** If the source text is a debt-incurrence
provision (containing "Indebtedness", "Acquisition", "prepay",
"defease") and the target is a facility class, this is likely a
reference, not a target.  The transformation must fail closed.  See
`CONSERVATION_INVARIANTS.md` §OUT_OF_SCOPE isolation.  This addresses
the 4 `HELD-017` incorrect accepted mutations.

### 2.4 EXCEPTION_CONTRACTION

Remove one or more exceptions from a commitment.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with an `exceptions` list containing the exception(s) to remove |
| **Required evidence** | Amendment text removing an exception; target identity evidence |
| **Affected fields** | `exceptions` (remove) |
| **Preserved fields** | All fields except `exceptions` |
| **Valid successor conditions** | `C_t.exceptions = C_{t-1}.exceptions - [removed_exception]`; all other fields unchanged |
| **Failure conditions** | Target identity not established; the exception to remove is not in `C_{t-1}.exceptions` |

### 2.5 SCHEDULE_REPLACEMENT

Replace a schedule or table associated with a commitment.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with a schedule reference |
| **Required evidence** | Amendment text providing a replacement schedule; target identity evidence |
| **Affected fields** | Schedule-related fields (e.g., `applicability` with step schedule) |
| **Preserved fields** | All non-schedule fields |
| **Valid successor conditions** | Schedule is replaced; identity persists; non-schedule fields unchanged |
| **Failure conditions** | Target identity not established; schedule cannot be parsed; schedule does not correspond to the predecessor schedule |

### 2.6 TEMPORAL_STEP_CHANGE

Change a temporal step schedule (e.g., a leverage ratio that steps
down over time).

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with a temporal step schedule |
| **Required evidence** | Amendment text modifying the step schedule; target identity evidence |
| **Affected fields** | `applicability` (step schedule), `valid_from`/`valid_to` for affected steps |
| **Preserved fields** | Non-temporal fields |
| **Valid successor conditions** | Step schedule is valid (dates are monotonic, no overlaps); identity persists |
| **Failure conditions** | Target identity not established; step schedule invalid; temporal validity violated |

### 2.7 WAIVER

Temporarily suspend a commitment.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with `status = ACTIVE` |
| **Required evidence** | Amendment text granting a waiver; waiver period |
| **Affected fields** | `status` (→ WAIVED), `valid_from`/`valid_to` (waiver period), `applicability` |
| **Preserved fields** | All semantic fields (threshold, operator, exceptions, etc.) |
| **Valid successor conditions** | `status = WAIVED`; waiver period is valid; all semantic fields unchanged |
| **Failure conditions** | Waiver period invalid; predecessor not ACTIVE |

A waiver preserves the commitment's semantic state.  The commitment is
suspended, not terminated.  See `REINSTATEMENT` for restoration.

### 2.8 REINSTATEMENT

Restore a previously waived commitment.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with `status = WAIVED` |
| **Required evidence** | Amendment text reinstating the commitment; or waiver period expiry |
| **Affected fields** | `status` (→ ACTIVE), `valid_from`/`valid_to` |
| **Preserved fields** | All semantic fields (must match the pre-waiver state) |
| **Valid successor conditions** | `status = ACTIVE`; semantic fields match pre-waiver values |
| **Failure conditions** | Predecessor not WAIVED; semantic fields changed during waiver (conservation violation) |

### 2.9 IDENTITY_PRESERVING_RESTATEMENT

Restate a section while preserving commitment identity.

This is the `RESTATE_SECTION` operation, redesigned as a conservation
operation.  See §3 below for the full specification.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with the target commitment |
| **Required evidence** | Restated section text sufficient to derive `C_next_candidate` |
| **Affected fields** | Only the fields that differ between `C_{t-1}` and `C_next_candidate` |
| **Preserved fields** | All fields that are unchanged or implicitly conserved |
| **Valid successor conditions** | `Δ = semantic_difference(C_{t-1}, C_next_candidate)` is valid; identity persists |
| **Failure conditions** | Restated text cannot be parsed; delta cannot be derived; delta includes unsupported changes |

### 2.10 DEFINED_TERM_PROPAGATION

Propagate a defined-term change to all commitments that reference the
term.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` for each affected commitment |
| **Required evidence** | Amendment text redefining a defined term; list of commitments referencing the term |
| **Affected fields** | Fields that reference the redefined term (may be `scope`, `exceptions`, `threshold` semantics) |
| **Preserved fields** | Fields not referencing the term |
| **Valid successor conditions** | All referencing commitments updated; non-referencing commitments unchanged; identity persists for all |
| **Failure conditions** | Defined term change not established; referencing commitments cannot be enumerated; propagation incomplete |

### 2.11 RENUMBER

Renumber a section reference without changing commitment identity.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with an `AddressBinding` |
| **Required evidence** | Amendment text renumbering the section |
| **Affected fields** | `AddressBinding.section_ref`, `AddressBinding.renumbered_from` |
| **Preserved fields** | All semantic fields; `commitment_id` |
| **Valid successor conditions** | `commitment_id` unchanged; both old and new addresses resolve to the same identity |
| **Failure conditions** | Renumbering evidence insufficient |

### 2.12 TERMINATE

Terminate a commitment.

| | |
|---|---|
| **Required predecessor state** | `C_{t-1}` with `status = ACTIVE` (or WAIVED) |
| **Required evidence** | Amendment text terminating the commitment |
| **Affected fields** | `status` (→ TERMINATED), `valid_to` |
| **Preserved fields** | All semantic fields (the commitment's semantics are preserved in the lineage; only the status changes) |
| **Valid successor conditions** | `status = TERMINATED`; `valid_to` set; identity lineage records the termination |
| **Failure conditions** | Termination evidence insufficient; predecessor not ACTIVE/WAIVED |

### 2.13 CREATE

Create a new commitment.

| | |
|---|---|
| **Required predecessor state** | None (this is a new identity) |
| **Required evidence** | Amendment text creating a new obligation; the new commitment's fields |
| **Affected fields** | All fields of the new commitment |
| **Preserved fields** | N/A (no predecessor) |
| **Valid successor conditions** | New `commitment_id` assigned; all required fields populated; identity lineage records the creation |
| **Failure conditions** | Creation evidence insufficient; required fields cannot be populated |

---

## 3. RESTATE_SECTION as conservation operation

`RESTATE_SECTION` is redesigned around predecessor/successor semantic
differencing.  This is the highest-leverage transformation: 41 of 78
failed IN_SCOPE instructions fall into the `MULTI_FIELD_DECOMPOSITION`
failure family (`forensic_qa/001_moses_commitment_theory_audit.md`
Final Output D).

### Current behavior

The current runtime rejects all `RESTATE_SECTION` operations
(`executor.py:174-177` raises `UnresolvedInstruction`).  This was
classified as `MOSES_PROTOCOL_INSUFFICIENCY` in the forensic audit.
The reclassification in `FAILURE_RECLASSIFICATION.md` reassesses
whether this is a true protocol insufficiency or an implementation
gap.

### Target behavior

Given:

```
C_prev = C_{t-1}
```

and replacement section evidence sufficient to derive:

```
C_next_candidate
```

derive:

```
Δ = semantic_difference(C_prev, C_next_candidate)
```

Then validate `Δ`.

### Identity preservation

Do NOT assume a full restatement means destroy identity and recreate
everything.  Identity should normally persist unless contrary evidence
exists.  The restatement is an `IDENTITY_PRESERVING_RESTATEMENT` by
default; it becomes a `CREATE` + `TERMINATE` only if the semantic
difference is so large that the obligation is no longer recognizably
the same.

### Field handling

| Field state in restated text | Handling |
|------------------------------|----------|
| **Changed fields** | Included in `Δ`; old/new values recorded |
| **Unchanged fields** | Conserved: `C_t[f] = C_{t-1}[f]` |
| **Omitted but implicitly conserved** | Conserved: if the restated text omits a field that was present in `C_{t-1}`, the field is presumed conserved unless the restatement explicitly removes it |
| **Removed exceptions** | Included in `Δ` as `EXCEPTION_CONTRACTION` |
| **New exceptions** | Included in `Δ` as `EXCEPTION_EXPANSION` |
| **Ambiguous omissions** | Fail closed: if it is unclear whether a field was intentionally removed or merely omitted, the transformation is UNRESOLVED |
| **Multi-field changes** | All changed fields must be extracted; partial extraction fails (transformation completeness) |

### Delta validation

The derived `Δ` must pass all applicable conservation invariants (see
`CONSERVATION_INVARIANTS.md`):

- Identity persistence (unless evidence establishes identity change)
- Unchanged-field preservation
- No unsupported semantic gain
- No silent semantic loss
- Transformation completeness

---

## 4. AuthorizedTransformationEngine contract

The engine is the Layer B component from `MOSES_RUNTIME_CONTRACT.md`.

### Inputs

```
C_{t-1}    — authoritative predecessor commitment
E_t        — amendment evidence (from Layer A)
A_t        — authority / lineage context
```

### Outputs

```
Δ_t        — authorized semantic transformation (or rejection)
```

### Process

```
1. Establish target identity
   - Resolve target commitment from evidence + predecessor state
   - Use agreement-local address map (not global section heuristics)
   - Predecessor state biases resolution but does not determine it
   - If target identity cannot be established: REJECT (fail closed)

2. Determine transformation type
   - From amendment operation + evidence + predecessor state
   - If transformation type cannot be determined: REJECT

3. Determine affected fields
   - From transformation type + evidence
   - If affected fields cannot be fully determined: REJECT
     (transformation completeness — no partial subsets)

4. Determine old/new values
   - New values from evidence
   - Old values from predecessor state (C_{t-1}[field])
   - If old values stated in amendment, verify consistency
   - If any value cannot be determined: REJECT

5. Verify old-value consistency (Constraint #3)
   - This is a CONSERVATION CHECK, not interpretation evidence
   - It runs AFTER target/transformation evidence is established
   - declared_old_value == C_{t-1}[field]
   - If mismatch: REJECT (the amendment may target a different
     commitment or a different field)

6. Produce Δ_t
   - The authorized semantic transformation
   - Carries: transformation_type, affected_fields, old_values,
     new_values, preserved_fields, evidence references
```

### Must not do

- Raw document parsing (that is Layer A)
- Mutate commitment state (that is Layer F)
- Grant authority (that is Layer G)
- Execute the transformation (that is Layer F)
- Copy `old_value = predecessor[field]` and treat
  `old_value == predecessor[field]` as interpretation evidence
  (Constraint #3)

---

## 5. Transformation families do NOT expand the 13 classes

The 13 frozen commitment classes are unchanged.  A
`SCALAR_REPLACEMENT` on a `financial_covenant.leverage_ratio` does not
create a new class.  A `MULTI_FIELD_REPLACEMENT` that changes both
threshold and operator on a `financial_covenant.current_ratio` does
not create a new class.  A `CREATE` may create a new commitment
instance, but its `canonical_key` must be one of the 13 frozen
classes (or the instruction is UNSUPPORTED).

Transformation richness is about how commitments change; ontology
breadth is about what commitment types exist.  These are different
questions.

---

## 6. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q19, Final Output
  D, I, J — multi-field/restatement semantics, failure census,
  leverage analysis, build sequence
- `executor.py:174-177` — current RESTATE_SECTION rejection
- `semantic_resolver_v2.py:650-745` — current value extraction (dead
  `current_commitment` parameter)
- `.devin/rules.md` — prohibited action #6 (broadening frozen
  ontology)
- `MOSES_RUNTIME_CONTRACT.md` — layer contracts
- `CONSERVATION_INVARIANTS.md` — invariant checks per family
