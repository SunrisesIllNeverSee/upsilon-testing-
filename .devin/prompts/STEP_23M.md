# PHASE VI — STEP 23M
# MOSES SEMANTIC CONTROL ARCHITECTURE PACKAGE

> **Archived prompt.** This is the authoritative Step 23M design prompt,
> preserved here so future agents have the full specification without
> relying on session context.  Do not modify without explicit user
> authorization.  If the user supplies a revised prompt, archive the
> revision as a new file (e.g. `STEP_23M_v2.md`) rather than overwriting.

## Objective

Convert the recent forensic findings into one authoritative implementation design for the MOSES semantic control layer inside Upsilon.

This is a DESIGN / SPECIFICATION step.

Do NOT modify runtime behavior.

Do NOT implement Step 23S.

Do NOT implement Step 24.

Do NOT optimize coverage.

We need to settle what MOSES means operationally before additional semantic code is written.

---

# 1. CONTROLLING FINDING

The forensic evidence indicates that current Upsilon behaves approximately as:

```text
C_t = Execute(Extract(Text_t))
```

when the intended conservation-first runtime is:

```text
C_t = T_t(C_{t-1}, E_t)
```

where:

```text
C_{t-1} = authoritative predecessor commitment state
E_t     = amendment evidence
T_t     = validated semantic transformation
C_t     = successor commitment state
```

The central design objective is therefore:

> Make predecessor commitment state and conserved commitment identity primary semantic inputs to amendment interpretation.

---

# 2. CORRECT THE PROTOCOL-INSUFFICIENCY CLASSIFICATION

Do NOT classify an observed failure as:

```text
MOSES_PROTOCOL_INSUFFICIENCY
```

merely because the current Upsilon implementation does not support the operation.

For every alleged protocol-insufficiency case ask:

1. Can `C_{t-1}` be represented?
2. Can the correct `C_t` be represented?
3. Can the semantic difference/transformation between them be represented conceptually within the commitment-state model?

If all three are YES, classify:

```text
MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP
```

not protocol insufficiency.

Genuine protocol insufficiency requires evidence that the correct state or transformation cannot be represented by MOSES even in principle.

Reassess specifically:

```text
RESTATE_SECTION
DELETE / TERMINATION
TABLE / SCHEDULE
DEFINED_TERM propagation
MULTI_FIELD transformations
temporal schedules
waivers / reinstatements
```

Do not modify code during reassessment.

---

# 3. REQUIRED RUNTIME ARCHITECTURE

The target semantic path is:

```text
SOURCE EVIDENCE
      |
TRANSFORMATION TARGET IDENTITY
      |
CONSERVED PREDECESSOR COMMITMENT
      |
TRANSFORMATION INTERPRETATION
      |
SEMANTIC DELTA
      |
CONSERVATION VALIDATION
      |
SEMANTIC PROOF RECORD
      |
EXECUTION
      |
SUCCESSOR COMMITMENT
      |
SEMANTIC AUTHORITY GATE
```

Current evidence extraction mechanisms such as:

```text
text matching
aliases
section references
regex
model-assisted candidates
defined-term lookup
```

remain useful.

But they become subordinate evidence sources.

They may not independently establish semantic authority.

---

# 4. COMPONENT 1 - PERSISTENT COMMITMENT IDENTITY

Design an explicit agreement-local commitment identity layer.

Core invariant:

```text
ID(C_t) = ID(C_{t-1})
```

unless affirmative evidence establishes:

```text
CREATE
TERMINATE
SPLIT
MERGE
REDEFINE
RENUMBER / READDRESS
```

Section references are agreement-local addresses.

Design around:

```text
(agreement_identity, section/address, time)
    -> commitment_identity
```

NOT:

```text
Section 7.10 -> leverage_ratio globally
```

Global section mappings may remain weak discovery evidence only.

Once S0 establishes commitment identity, later amendments should inherit it unless evidence establishes a legitimate identity transformation.

Document:

- identity data structure;
- agreement-local address map;
- identity lineage;
- renumbering behavior;
- identity confidence/provenance;
- rules for creation/termination.

---

# 5. COMPONENT 2 - CANONICAL COMMITMENT KERNEL

Specify the semantic commitment object that MOSES actually governs.

Distinguish fields into categories such as:

## Identity-bearing

What makes this the same commitment over time?

## Mutable semantic state

Examples:

```text
threshold
operator
frequency
scope
exceptions
trigger
cure
applicability
```

## Temporal state

Examples:

```text
effective_from
effective_until
waiver periods
step schedules
```

## Evidentiary / provenance state

Examples:

```text
source document
source span
defined-term support
lineage
authority
```

Do not blindly activate every dormant dataclass field.

Determine which fields have explicit semantic responsibility.

Define:

```text
CommitmentKernel
```

as the state object transformations operate over.

---

# 6. COMPONENT 3 - TRANSFORMATION ALGEBRA

Specify explicit legal transformation families over commitment state.

Conceptually:

```text
C_t = T(C_{t-1}, E_t)
```

Transformation types should cover evidence-supported real EDGAR behavior, potentially including:

```text
SCALAR_REPLACEMENT
MULTI_FIELD_REPLACEMENT
EXCEPTION_EXPANSION
EXCEPTION_CONTRACTION
SCHEDULE_REPLACEMENT
TEMPORAL_STEP_CHANGE
WAIVER
REINSTATEMENT
IDENTITY_PRESERVING_RESTATEMENT
DEFINED_TERM_PROPAGATION
RENUMBER
TERMINATE
CREATE
```

Do not expand the frozen 13 commitment classes.

Transformation richness and ontology breadth are different questions.

For each operator specify:

```text
required predecessor state
required evidence
affected fields
preserved fields
valid successor conditions
failure conditions
```

---

# 7. RESTATEMENT AS CONSERVATION OPERATION

Design `RESTATE_SECTION` around predecessor/successor semantic differencing.

Given:

```text
C_prev
```

and replacement section evidence sufficient to derive:

```text
C_next_candidate
```

derive:

```text
delta = semantic_difference(C_prev, C_next_candidate)
```

Then validate that delta.

Do not assume a full restatement means destroy identity and recreate everything.

Identity should normally persist unless contrary evidence exists.

Document handling of:

- changed fields;
- unchanged fields;
- omitted but implicitly conserved fields;
- removed exceptions;
- new exceptions;
- ambiguous omissions;
- multi-field changes.

---

# 8. TARGET != REFERENCE

This becomes a controlling invariant:

```text
REFERENCE TO COMMITMENT != TRANSFORMATION TARGET OF COMMITMENT
```

Design an explicit target-establishment contract.

A provision mentioning:

```text
Revolving Loans
Term Facility
Leverage Ratio
```

does not by itself prove that entity is being modified.

A mutation may only be constructed after evidence establishes the amendment provision actually targets the conserved commitment.

Do NOT propose another lexical patch such as:

```text
ADD + long text + exception + debt words = reject
```

Solve this at semantic target identity.

Specify target evidence levels and failure behavior.

Insufficient target evidence must fail closed.

---

# 9. COMPONENT 4 - CONSERVATION VALIDATORS

Define explicit invariant checks.

At minimum:

## Identity persistence

```text
ID(C_t) == ID(C_{t-1})
```

unless validated identity-changing transformation.

## Old-value consistency

Where applicable:

```text
declared_old_value == C_{t-1}[field]
```

## Unchanged-field preservation

For every field outside the validated delta:

```text
C_t[f] == C_{t-1}[f]
```

## No unsupported semantic gain

Successor state may not acquire semantics unsupported by evidence/transformation.

## No silent semantic loss

Existing semantics may not disappear without evidence of removal/change.

## Target/reference separation

Mention does not satisfy target identity.

## Lineage continuity

Every accepted successor traces to predecessor + amendment evidence.

## Temporal validity

Schedules, waivers, reinstatements, and effective dates obey valid state transitions.

## OUT_OF_SCOPE isolation

Unsupported/out-of-scope provisions cannot mutate the frozen commitment state.

## Transformation completeness

A partially understood multi-field transformation may not silently apply only the convenient subset and claim authority.

Specify which invariants apply to each transformation family.

---

# 10. COMPONENT 5 - SEMANTIC TRANSFORMATION PROOF RECORD

Every accepted semantic transformation must produce a compact machine-readable proof record.

Design a schema containing at minimum:

```text
proof_id
agreement_id
commitment_id

predecessor_version
successor_version

source_document
source_span
source_authority

transformation_type
target_identity_evidence

affected_fields
predecessor_values
successor_values
preserved_fields

defined_term_dependencies
temporal_dependencies

conservation_checks
validator_results

evidence_status
uncertainty_status

execution_result
lineage_reference
```

The proof record is not philosophical proof.

It is a runtime evidence object showing why the transformation was allowed.

---

# 11. COMPONENT 6 - SEMANTIC AUTHORITY GATE

Authority must no longer be reducible solely to:

```text
execution complete
+
nothing unresolved
```

Design semantic authority as requiring:

```text
valid transformation proof
AND
required conservation invariants pass
AND
execution succeeds
AND
no inherited unresolved semantic state blocks promotion
```

Specify:

```text
AUTHORITY_GRANTED
AUTHORITY_BLOCKED
VALIDATION_REQUIRED
PARTIAL
UNRESOLVED
```

Do not redesign existing lineage/temporal architecture unnecessarily.

The authority gate should consume those systems, not replace them.

---

# 12. COMPONENT 7 - MOSES CONFORMANCE HARNESS

Define a dedicated conformance test matrix.

At minimum:

```text
identity_persists_across_amendment
section_address_is_agreement_local
reference_is_not_target
old_value_matches_predecessor
wrong_old_value_blocks_transform
unchanged_fields_are_conserved
unsupported_semantics_do_not_alias_into_frozen_class
restatement_derives_correct_delta
restatement_preserves_identity
multi_field_change_cannot_partially_disappear
out_of_scope_instruction_cannot_mutate_state
incorrect_semantic_delta_cannot_be_authoritative
renumbering_preserves_identity
waiver_preserves_and_restores_state
temporal_schedule_changes_at_correct_time
defined_term_dependency_is_traceable
proof_record_is_complete
authority_requires_valid_semantic_proof
```

Distinguish:

```text
UNIT TEST
INTEGRATION TEST
CONFORMANCE TEST
REAL-EDGAR REGRESSION
```

A failed MOSES conformance invariant must be capable of failing CI even if hundreds of ordinary unit tests pass.

---

# 13. ALIAS POLICY

Audit and specify alias semantics.

Aliases may only express genuine semantic equivalence.

Examples previously identified as suspicious/non-equivalent include concepts such as:

```text
Asset Coverage Ratio
Minimum Working Capital
Minimum Liquidity
```

Do not force non-equivalent concepts into frozen classes merely for coverage.

Required behavior when concept != frozen class:

```text
OUT_OF_SCOPE
UNSUPPORTED
AMBIGUOUS
```

as evidence warrants.

Define:

```text
alias
related concept
defined-term expansion
section address
semantic equivalence
```

as distinct mechanisms.

---

# 14. RECLASSIFY THE FAILURE CENSUS

Revisit the previously alleged protocol-insufficiency cases.

Produce:

```text
MOSES_TRUE_PROTOCOL_INSUFFICIENCY
MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP
UPSILON_INTERPRETATION_FAILURE
AMBIGUOUS
```

For every case or failure family explain why.

Specifically report revised counts for:

```text
MULTI_FIELD_DECOMPOSITION
RESTATE_SECTION
DELETE / TERMINATION
TABLE / SCHEDULE
DEFINED_TERM
TEMPORAL / APPLICABILITY
```

Do NOT manipulate categories to improve projected coverage.

---

# 15. EXPECTED RECOVERY LEVERAGE

Using the independently adjudicated Step 23R diagnostic set, estimate by transformation family:

```text
affected eligible failures
representable under existing commitment theory?
current implementation missing?
downstream dependencies
maximum directly addressable cases
```

This is engineering leverage analysis, not a forecast.

Do not claim that implementing a transformation guarantees successful end-to-end mappings.

---

# 16. LAYER CONTRACTS

Explicitly separate:

```text
A. Evidence extraction
B. Semantic interpretation
C. Commitment transformation
D. Conservation validation
E. Semantic proof
F. Execution
G. Authority promotion
```

For each specify:

```text
inputs
outputs
may do
must not do
failure behavior
```

These responsibilities must not collapse into a single resolver.

---

# 17. REQUIRED DOCUMENT PACKAGE

Create an authoritative design package under the MOSES docs area.

At minimum:

```text
docs/moses/MOSES_RUNTIME_CONTRACT.md
docs/moses/COMMITMENT_IDENTITY.md
docs/moses/COMMITMENT_KERNEL.md
docs/moses/TRANSFORMATION_ALGEBRA.md
docs/moses/CONSERVATION_INVARIANTS.md
docs/moses/SEMANTIC_PROOF_RECORD.md
docs/moses/SEMANTIC_AUTHORITY_GATE.md
docs/moses/CONFORMANCE_MATRIX.md
docs/moses/FAILURE_RECLASSIFICATION.md
docs/moses/STEP24_CONSERVATION_FIRST_DESIGN.md
```

Add them to the architecture index created in Step 23G.

Do not modify runtime code.

---

# 18. FINAL RESPONSE

Return:

## A. Revised conceptual diagnosis

Is current Upsilon predominantly:

```text
MOSES theory/schema insufficient
```

or:

```text
MOSES EDGAR engine incompletely implemented
```

Support with counts/evidence.

## B. Seven-component architecture

Summarize:

```text
Persistent Identity
Commitment Kernel
Transformation Algebra
Conservation Validators
Semantic Proof
Semantic Authority
Conformance Harness
```

## C. Failure reclassification

Exact counts.

## D. Runtime sequence

Exact proposed runtime sequence.

## E. Invariant list

Complete list.

## F. Transformation families

Complete list.

## G. Proof schema

Fields and responsibilities.

## H. Step 23S implications

Identify how the 10 incorrect accepts + 1 false promotion should be repaired under these invariants.

Do NOT implement the repair.

Specifically identify whether the repair belongs to:

```text
target identity
semantic equivalence
transformation validation
conservation validation
semantic authority
```

rather than proposing lexical patches.

## I. Step 24 implementation boundary

State exactly what Step 24 should implement after Step 23S restores safety.

## J. Verdict

Choose:

```text
STEP 23M PASS - MOSES runtime control architecture sufficiently specified for implementation
```

or:

```text
STEP 23M BLOCKED - material semantic-control questions remain unresolved
```

---

# NON-NEGOTIABLES

- Do not implement code.
- Do not expand the 13 commitment classes.
- Do not confuse unsupported implementation with theory insufficiency.
- Do not use global section numbers as semantic authority.
- Do not force non-equivalent aliases into the ontology.
- Do not replace semantic reasoning with another lexical heuristic.
- Do not weaken fail-closed behavior.
- Do not change frozen experimental evidence.

The purpose is to turn MOSES from a conceptual influence around Upsilon into an explicit runtime control contract:

> **Evidence -> Conserved Identity -> Prior State -> Transformation -> Conservation Proof -> Execution -> Authority**
