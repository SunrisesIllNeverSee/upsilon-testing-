# Semantic Proof Record

**Step 23M design document — Component 5: Semantic Transformation
Proof Record.**

This document specifies the schema for the compact machine-readable
proof record that every accepted transformation must produce.  No
runtime code is modified.

---

## 1. Purpose

Every accepted semantic transformation must produce a
`SemanticTransformationProof` record.  The proof record is a runtime
evidence object showing why the transformation was allowed.

**The proof record is NOT philosophical proof.**  It is not a claim
of mathematical certainty.  It is a structured record of:

- what evidence was available;
- what target identity was established;
- what transformation was authorized;
- what conservation checks passed;
- what the execution result was;
- what lineage edge was created.

---

## 2. Semantic proof precedes execution (Constraint #5)

The `SemanticTransformationProof` is NOT a post-hoc explanation of
executor behavior.  It is the **precondition** that justifies
allowing a transformation to execute.

The conceptual ordering is:

```
Evidence
  → Target Identity
  → Predecessor State
  → Authorized Transformation
  → Semantic Proof
  → Conservation Validation
  → EXECUTION
  → Lineage
  → Authority
```

The proof record is assembled BEFORE execution.  It carries the
evidence, target identity, transformation, and conservation
validation results.  Execution is permitted only when the proof is
COMPLETE and all conservation checks PASS.

After execution, the proof record is updated with the execution
result and lineage reference.  This completes the record.

---

## 3. Current state

The current runtime does not produce structured semantic proof
records (`CONFORMANCE_CONTRACT.md` invariant #10).  The `proof/`
domain is a target architectural home with no current implementation.

The current authority determination (`semantic_pipeline_v2.py:247-251`)
reduces to:

```
execution complete + nothing unresolved = authoritative
```

This is what allowed the 1 false authoritative promotion in HELD-017:
the incorrect mutation was accepted, execution completed, and
authority was granted without any semantic proof.

---

## 4. Proof schema

```python
class SemanticTransformationProof:
    # --- Identity ---
    proof_id: str               # unique identifier for this proof
    agreement_id: str           # agreement this proof belongs to
    commitment_id: str          # commitment this transformation affects

    # --- Versions ---
    predecessor_version: int    # version number of C_{t-1}
    successor_version: int      # version number of C_t

    # --- Source evidence ---
    source_document: str        # document from which evidence was extracted
    source_span: str            # text span in the source document
    source_authority: str       # authority source (amendment ID, section)

    # --- Transformation ---
    transformation_type: str    # one of the 13 transformation families
    target_identity_evidence: TargetIdentityEvidence

    # --- Field-level changes ---
    affected_fields: list[str]
    predecessor_values: dict[str, Any]
    successor_values: dict[str, Any]
    preserved_fields: list[str]

    # --- Dependencies ---
    defined_term_dependencies: list[str]
    temporal_dependencies: list[TemporalDependency]

    # --- Conservation ---
    conservation_checks: dict[str, CheckResult]
    validator_results: ValidatorResults

    # --- Status ---
    evidence_status: EvidenceStatus
    uncertainty_status: UncertaintyStatus

    # --- Execution ---
    execution_result: ExecutionResultSummary
    lineage_reference: str      # proof_id of the lineage edge
```

---

## 5. Field responsibilities

### Identity fields

| Field | Responsibility |
|-------|---------------|
| `proof_id` | Unique identifier.  Links to the lineage edge. |
| `agreement_id` | The agreement this transformation belongs to. |
| `commitment_id` | The persistent commitment identity (see `COMMITMENT_IDENTITY.md`). |

### Version fields

| Field | Responsibility |
|-------|---------------|
| `predecessor_version` | Version number of `C_{t-1}`.  Links to the predecessor kernel version. |
| `successor_version` | Version number of `C_t`.  The new kernel version produced by this transformation. |

### Source evidence fields

| Field | Responsibility |
|-------|---------------|
| `source_document` | The document (amendment, restated agreement) from which evidence was extracted. |
| `source_span` | The text span in the source document that provides the transformation evidence. |
| `source_authority` | The legal authority for the transformation (e.g., "Amendment No. 3, Aug 24, 2023, Section 2"). |

### Transformation fields

| Field | Responsibility |
|-------|---------------|
| `transformation_type` | One of the 13 transformation families (see `TRANSFORMATION_ALGEBRA.md`). |
| `target_identity_evidence` | The evidence that establishes the amendment targets this commitment (see §6 below). |

### Field-level change fields

| Field | Responsibility |
|-------|---------------|
| `affected_fields` | List of fields changed by this transformation. |
| `predecessor_values` | Values of affected fields in `C_{t-1}`. |
| `successor_values` | Values of affected fields in `C_t`. |
| `preserved_fields` | List of fields NOT changed.  These must satisfy `C_t[f] == C_{t-1}[f]`. |

### Dependency fields

| Field | Responsibility |
|-------|---------------|
| `defined_term_dependencies` | Defined terms referenced by this transformation.  If a defined term is later redefined, this proof is flagged for re-validation. |
| `temporal_dependencies` | Temporal constraints (effective dates, waiver periods, step schedule references). |

### Conservation fields

| Field | Responsibility |
|-------|---------------|
| `conservation_checks` | Per-invariant pass/fail results (see `CONSERVATION_INVARIANTS.md`). |
| `validator_results` | Detailed validator output, including failure reasons for any failed checks. |

### Status fields

| Field | Responsibility |
|-------|---------------|
| `evidence_status` | SUFFICIENT / CORROBORATED / WEAK / INSUFFICIENT (see target evidence levels in `CONSERVATION_INVARIANTS.md` §2.6). |
| `uncertainty_status` | NONE / LOW / MEDIUM / HIGH.  High uncertainty routes to VALIDATION_REQUIRED, not auto-promotion. |
| `proof_completeness` | COMPLETE / INCOMPLETE — structural: all required fields populated. |
| `proof_validity` | VALID / INVALID / INDETERMINATE — semantic: the evidence actually supports the transformation.  A COMPLETE proof can be INVALID. |

### Execution fields

| Field | Responsibility |
|-------|---------------|
| `execution_result` | Summary of execution: applied/unresolved, state change. |
| `lineage_reference` | ID of the lineage edge created by this transformation. |

---

## 6. TargetIdentityEvidence

```python
class TargetIdentityEvidence:
    # The evidence signals used to establish target identity
    signals: list[TargetSignal]

    # The confidence level established
    confidence: float           # [0.0, 1.0]

    # The evidence level: SUFFICIENT / CORROBORATED / WEAK / INSUFFICIENT
    evidence_level: str

    # Whether predecessor state was used as context
    predecessor_state_used: bool

    # The agreement-local address used for resolution
    local_address: str | None
```

```python
class TargetSignal:
    signal_type: str            # "section_ref", "alias_match", "text_match",
                                # "defined_term", "predecessor_bias", "model_assisted"
    signal_value: str           # the matched value
    signal_weight: float        # weight of this signal [0.0, 1.0]
    corroboration: bool         # whether this signal is corroborated by others
```

This structure makes explicit what evidence was used to establish
target identity.  It prevents the tautological old-value problem
(Constraint #3): the target identity evidence must come from
amendment evidence + predecessor context, NOT from copying
`old_value = predecessor[field]`.

---

## 7. Proof completeness and validity

### Completeness (structural)

A proof is COMPLETE when:

1. `target_identity_evidence.evidence_level` is SUFFICIENT or
   CORROBORATED;
2. All `affected_fields` have both `predecessor_values` and
   `successor_values`;
3. All `conservation_checks` have been run (pass or fail);
4. `evidence_status` is not INSUFFICIENT;
5. `transformation_type` is one of the 13 families;
6. `defined_term_dependencies` and `temporal_dependencies` are
   populated (or explicitly empty).

An INCOMPLETE proof does not proceed to execution.  An incomplete
proof produces an UNRESOLVED instruction.

### Validity (semantic)

A proof is VALID when the populated evidence actually supports the
transformation that was proposed:

1. The `target_identity_evidence` signals corroborate the target
   commitment (not just a reference);
2. The `predecessor_values` match the actual predecessor state;
3. The `successor_values` are supported by amendment evidence;
4. The `conservation_checks` that pass are genuinely passing (not
   tautological `x = x` checks);
5. The `transformation_type` is consistent with the amendment
   operation and evidence.

A COMPLETE proof that is INVALID blocks execution.  A COMPLETE proof
that is INDETERMINATE (validity cannot be confirmed) routes to
VALIDATION_REQUIRED.

---

## 8. Proof record and authority

The authority gate (`SEMANTIC_AUTHORITY_GATE.md`) consumes the proof
record.  Authority is granted only when:

```
proof_completeness == COMPLETE
AND proof_validity == VALID
AND all conservation_checks PASS
AND execution succeeds
AND no inherited unresolved state blocks promotion
```

The proof record must NOT depend on `ground_truth_correct = true` or
any equivalent answer-key information (Constraint #4).  Production
runtime establishes validity using operational evidence and MOSES
invariants alone.

---

## 9. Proof record and lineage

The proof record links to the lineage edge via `lineage_reference`.
The lineage edge (`COMMITMENT_LINEAGE_SCHEMA.md`, addendum §3) carries:

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

The `proof_id` in the lineage edge links back to the proof record.
This bidirectional link makes the transformation traceable from both
the lineage graph and the proof record.

---

## 10. Layer contract

Semantic proof is Layer E from `MOSES_RUNTIME_CONTRACT.md`.

| | |
|---|---|
| **Inputs** | Authorized transformation `Δ_t`, validation results (from Layer D), evidence objects, predecessor/successor versions |
| **Outputs** | `SemanticTransformationProof` record |
| **May do** | Assemble the proof record with all required fields; record evidence status and uncertainty status |
| **Must not do** | Invent semantic interpretation; perform validation; execute; grant authority |
| **Failure behavior** | If required proof fields cannot be populated, the proof is INCOMPLETE.  An incomplete proof does not proceed to execution. |

---

## 11. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q4, Final Output F
  — false authoritative promotion (no proof record existed)
- `CONFORMANCE_CONTRACT.md` invariant #10 — semantic proof
  completeness (NOT YET ENFORCED)
- `COMMITMENT_LINEAGE_SCHEMA.md` — lineage edge schema
- `MOSES_RUNTIME_CONTRACT.md` — layer contracts
- `CONSERVATION_INVARIANTS.md` — invariant checks
- `SEMANTIC_AUTHORITY_GATE.md` — authority gate consuming proof records
