# Step 24B — Runtime Wiring Audit

**Phase 0 deliverable.** This document maps the actual empirical EDGAR
amendment pipeline against the target Step 24 conservation-first
architecture.  No runtime behavior was changed during this phase.

---

## A. Current call graph

The actual production runtime path for EDGAR amendment processing is:

```
IssuerChain (edgar_chains.py)
  ↓
run_semantic_pipeline_v2(chain)               [semantic_pipeline_v2.py]
  ↓ for each AmendmentStep:
  ↓
  process_amendment_by_genre(text, state)      [genre_adapters.py]
    ↓ INCREMENTAL genre:
    ↓
    parse_v04(text)                            [amendment_parser.py]
      → list[AmendmentInstruction] (parser rows)
    ↓
    for each instruction:
      resolve_instruction(ins, current_state)  [semantic_resolver_v2.py]
        ↓ Step 1: resolve_commitment_from_text [commitment_registry.py]
        ↓         (alias patterns + _SECTION_MAP global heuristics)
        ↓ Step 2: resolve_commitment_from_state[commitment_registry.py]
        ↓ Step 3: _identify_field              [semantic_resolver_v2.py]
        ↓ Step 4: _extract_values              [semantic_resolver_v2.py]
        ↓ Step 5: _normalize_value             [semantic_resolver_v2.py]
        ↓ Step 6: _identify_operation          [semantic_resolver_v2.py]
        ↓ Step 7: StructuredMutation candidate [semantic_mapper.py]
        ↓ Step 8: _validate_candidate          [semantic_resolver_v2.py]
        ↓ Step 8b: validate_safety             [moses_safety.py]
        ↓ Step 9:  return MappingResult (mapped | unresolved)
    ↓
    candidates: list[StructuredMutation]
  ↓
  for mapped mutation:
    mut.to_amendment_instruction(order=i)      [semantic_mapper.py]
      → AmendmentInstruction
  ↓
  execute_amendment(current_state, instructions)[executor.py]
    → ExecutionResult (state, applied, unresolved, status)
  ↓
  assess_authority(execution_status, proofs,   [semantic_pipeline_v2.py]
                   inherited, own_unresolved)
    → AuthorityDecision
  ↓
  is_authoritative = (decision == AUTHORITY_GRANTED)
  ↓
  current_state = execution_result.state       (carried forward)
```

### Key modules in the current path

| Module | Role | Location |
|--------|------|----------|
| `semantic_pipeline_v2.py` | Pipeline orchestration + authority assessment | `src/upsilon/pipeline/` |
| `genre_adapters.py` | Genre routing + incremental adapter | `src/upsilon/parsing/` |
| `amendment_parser.py` | Lexical parsing (parse_v04) | `src/upsilon/parsing/` |
| `semantic_resolver_v2.py` | 10-step resolver: identity + field + value + validation + safety | `src/upsilon/transformations/` |
| `commitment_registry.py` | Alias matching + section-to-commitment heuristics | `src/upsilon/commitments/` |
| `semantic_mapper.py` | StructuredMutation dataclass + to_amendment_instruction | `src/upsilon/transformations/` |
| `moses_safety.py` | Step 23S safety proof (validate_safety) | `src/upsilon/conservation/` |
| `executor.py` | Legacy executor (execute_amendment) | `src/upsilon/execution/` |
| `legacy_models.py` | CommitmentState, AmendmentInstruction, ExecutionResult | `src/upsilon/models/` |
| `chain_reconstruction.py` | Synthetic chain harness (separate from v2 pipeline) | `src/upsilon/lineage/` |

---

## B. Target call graph

The required Step 24 conservation-first runtime:

```
IssuerChain
  ↓
pipeline orchestration
  ↓ for each amendment:
  ↓
  Layer A: Evidence Extraction
    parse_v04(text) → parser instructions
    extract AmendmentEvidence from each instruction
  ↓
  Layer B: AuthorizedTransformationEngine.authorize(evidence, authority)
    inputs: AmendmentEvidence, AuthorityContext(predecessor_kernel)
    uses: IdentityResolver + AgreementAddressMap (agreement-local)
    outputs: AuthorizedTransformation Δ (or rejection)
  ↓
  Layer C: apply_transformation(predecessor_kernel, Δ)
    outputs: candidate successor CommitmentKernel
  ↓
  Layer D: ConservationValidator.validate(predecessor, candidate, Δ)
    outputs: ValidationResult (per-invariant pass/fail)
  ↓
  Layer E: ProofAssembler.assemble_pre_execution(Δ, identity, validation)
    outputs: SemanticTransformationProof
    precondition: proof.may_proceed_to_execution() == True
  ↓
  Layer F: Kernel execution (thin executor)
    inputs: predecessor, Δ, candidate, proof, expected version
    outputs: executed successor (or fail-closed)
    MUST NOT reinterpret text, resolve identity, or derive values
  ↓
  Layer G: AuthorityGate.evaluate(execution_result, proof, inherited)
    inputs: execution status, proof, conservation, lineage validity
    outputs: AUTHORITY_GRANTED | AUTHORITY_BLOCKED | ...
  ↓
  Lineage: CommitmentLineageGraph.add_edge(...)
    append-only edge: predecessor → successor
  ↓
  if AUTHORITY_GRANTED:
    KernelStore.advance(commitment_id, successor, proof_id)
    authoritative_current = successor
  else:
    authoritative_current remains predecessor
```

---

## C. Gap matrix

| Layer | Target owner | Current owner | Production path reaches target owner? | Bypass? | Required change |
|-------|-------------|---------------|---------------------------------------|---------|-----------------|
| A. Evidence extraction | `AmendmentEvidence` (authorized_change.py) | `semantic_resolver_v2.py` (interleaved with interpretation) | NO — evidence is not separated into `AmendmentEvidence` objects | YES | Extract `AmendmentEvidence` from parser instructions before the engine; resolver becomes evidence producer, not final authority |
| B. Semantic interpretation | `AuthorizedTransformationEngine` (authorized_change.py) | `semantic_resolver_v2.py` 10-step resolver | NO — engine exists but is never called by the pipeline | YES | Wire `AuthorizedTransformationEngine.authorize()` as the controlling interpretation step for SCALAR_REPLACEMENT |
| C. Commitment transformation | `apply_transformation()` (apply.py) | `semantic_resolver_v2.py` candidate construction + `executor.py` | NO — `apply_transformation` exists but is never called | YES | Use `apply_transformation(predecessor_kernel, Δ)` to produce candidate successor |
| D. Conservation validation | `ConservationValidator` (validator.py) | `semantic_resolver_v2._validate_candidate` (hasattr check only) + `moses_safety.validate_safety` | NO — `ConservationValidator` exists but is never called by the pipeline | YES | Wire `ConservationValidator.validate(predecessor, candidate, Δ)` before execution |
| E. Semantic proof | `ProofBuilder`/`ProofAssembler` (transformation_proof.py) | `moses_safety.validate_safety` produces a `SemanticProof` (different type) | NO — `ProofAssembler` exists but is never called | YES | Use `ProofAssembler.assemble_pre_execution()` to build the proof; require `proof.may_proceed_to_execution()` before execution |
| F. Execution | Thin kernel executor (new) | `executor.py` (legacy, reinterprets via domain_effect) | NO — legacy executor applies `AmendmentInstruction`, not validated Δ | YES | Implement thin execution path that commits the validated candidate successor without reinterpreting text |
| G. Authority promotion | `AuthorityGate` (promotion_gate.py) | `assess_authority()` in semantic_pipeline_v2.py | NO — `AuthorityGate` exists but pipeline uses `assess_authority()` instead | YES | Wire `AuthorityGate.evaluate()` as the sole promotion path; add lineage validity consumption |
| Lineage | `CommitmentLineageGraph` (graph.py) | `LineageGraph` in chain_reconstruction.py (separate harness) | NO — `CommitmentLineageGraph` exists but is never used by the v2 pipeline | YES | Wire `CommitmentLineageGraph.add_edge()` as a required runtime output of execution |

---

## D. State-model boundary

### Current runtime: `CommitmentState` (legacy)

The production pipeline operates exclusively on `CommitmentState` objects
(`src/upsilon/models/legacy_models.py`):

- `chain.original_state: dict[str, CommitmentState]`
- `current_state: dict[str, CommitmentState]` (carried forward through steps)
- `execution_result.state: dict[str, CommitmentState]`
- `executor.execute_amendment(state, instructions)` mutates `CommitmentState` fields directly

`CommitmentState` is a flat pydantic model with semantic fields
(threshold, rate, deadline, party, exceptions, etc.) and temporal fields
(valid_from, valid_to, status).  It has no persistent identity object,
no version tracking, and no kernel/version semantics.

### Target runtime: `CommitmentKernel` (Step 24)

`CommitmentKernel` (`src/upsilon/models/kernel.py`) is the canonical state
object that transformations operate over:

- Combines `CommitmentIdentity` (persistent agreement-local identity) with mutable semantic state
- Has `KernelVersion` (immutable version stamp for lineage tracing)
- Has `field_value()` and `semantic_fields()` methods for conservation checks
- Has `lineage_reference`, `authority_status`, `proof_reference` evidentiary fields

### Boundary location

The boundary between `CommitmentState` and `CommitmentKernel` is currently
**nowhere** — the production pipeline never creates or operates on
`CommitmentKernel` objects.  The `KernelStore` and `OriginKernelBuilder`
exist but are only exercised by unit tests (`tests/unit/test_upsilonsrc.py`).

The conversion point must be established at S0 kernel initialization
(Phase 1): `CommitmentState` objects from the chain's `original_state` must
be converted to `CommitmentKernel` objects with persistent identity and
registered in a `KernelStore` before amendment processing begins.

---

## E. Authority boundary

### Locations capable of advancing current state

1. **`semantic_pipeline_v2.py:427-431`** — `current_state = execution_result.state`
   This carries state forward after every step regardless of authority
   decision.  The `is_authoritative` flag is computed but does NOT gate
   state advancement — the provisional state always replaces the
   predecessor state in the `current_state` dict.

2. **`chain_reconstruction.py:617-623`** — `current_state = reconstructed`
   Same pattern in the synthetic chain harness: state is carried forward
   regardless of `is_authoritative`.

3. **`executor.py:186-231`** — `execute_amendment()` mutates a deep copy
   of `current_state` and returns the mutated state.  The executor itself
   advances state by applying instructions.

### Locations capable of declaring a step authoritative

1. **`semantic_pipeline_v2.py:388-399`** — `assess_authority()` returns
   `AuthorityDecision`; `is_authoritative` is set to
   `(decision == AUTHORITY_GRANTED)`.

2. **`chain_reconstruction.py:590-593`** — `is_authoritative` is set to
   `(execution_result.status == COMPLETE and not inherited_unresolved)`.
   This is the old chain-aware model without semantic proof preconditions.

### Gap

Neither location consumes lineage validity.  The `AuthorityGate` in
`promotion_gate.py` exists and has the correct decision logic, but it
does NOT check lineage validity (the prompt's Phase 8 identifies this
as an existing gap to close).  The `assess_authority()` function in the
pipeline does not use `AuthorityGate` at all — it reimplements a subset
of the logic inline.

---

## F. Legacy bypass inventory

### Bypass 1: StructuredMutation → AmendmentInstruction → legacy executor

**Path:**
```
semantic_resolver_v2.resolve_instruction()
  → StructuredMutation (semantic_mapper.py)
  → StructuredMutation.to_amendment_instruction()
  → AmendmentInstruction (legacy_models.py)
  → executor.execute_amendment(state, [AmendmentInstruction])
  → CommitmentState mutated directly
```

**Status:** CONTROLLING for all transformation families, including
SCALAR_REPLACEMENT.  The resolver determines target + field + values +
operation, converts to `AmendmentInstruction`, and the legacy executor
applies it.  The `AuthorizedTransformationEngine` is never invoked.

**Impact:** The Step 24 spine (engine → apply → validate → proof →
execute → lineage → authority) is entirely bypassed.  The executor
re-derives the field from `domain_effect` (lines 99-112) and applies
the mutation directly to `CommitmentState`.

### Bypass 2: Global section heuristics as identity authority

**Path:**
```
commitment_registry.resolve_commitment_from_text()
  → _ALIASES pattern matching (global)
  → _SECTION_MAP regex matching (global section → commitment_id)
  → returns canonical_id with confidence 0.60-0.95
```

**Status:** CONTROLLING.  The `AgreementAddressMap` and `IdentityResolver`
in `commitments/identity.py` exist but are never used by the production
pipeline.  Section numbers resolve through global `_SECTION_MAP` patterns,
not agreement-local address maps.

**Impact:** Section heuristics can establish commitment identity without
agreement-local context.  This is the root cause of the target/reference
separation failures documented in Step 23S.

### Bypass 3: moses_safety proof ≠ SemanticTransformationProof

**Path:**
```
semantic_resolver_v2.py:656
  → moses_safety.validate_safety(...)
  → returns (moses_safety.SemanticProof, is_safe: bool)
  → proof attached to StructuredMutation.semantic_proof
  → consumed by assess_authority() via getattr() duck-typing
```

**Status:** CONTROLLING.  The `ProofBuilder`/`ProofAssembler` in
`transformation_proof.py` exist but are never used.  The pipeline uses
a different proof type (`moses_safety.SemanticProof`) with a different
schema.  The `SemanticTransformationProof` model (with
`may_proceed_to_execution()`) is never constructed by the pipeline.

**Impact:** The proof precondition for execution is not enforced through
the canonical `SemanticTransformationProof.may_proceed_to_execution()`
check.  The safety proof is a gate inside the resolver (Step 8b), not a
precondition on the execution path.

### Bypass 4: assess_authority() ≠ AuthorityGate

**Path:**
```
semantic_pipeline_v2.py:388
  → assess_authority(execution_status, proofs, inherited, own)
  → returns AuthorityDecision (inline logic)
```

**Status:** CONTROLLING.  The `AuthorityGate` in `promotion_gate.py`
exists with the full decision logic (including conservation checks and
evidence status) but is never instantiated or called by the pipeline.
`assess_authority()` reimplements a subset of the logic.

**Impact:** The authority gate does not consume lineage validity, does
not use the canonical `SemanticTransformationProof`, and does not
enforce conservation check results (it only checks proof completeness
and validity via duck-typing).

### Bypass 5: No CommitmentLineageGraph in production

**Path:**
```
semantic_pipeline_v2.py — no lineage graph construction
chain_reconstruction.py — uses its own LineageGraph (different type)
```

**Status:** The `CommitmentLineageGraph` in `lineage/graph.py` exists
but is never used by either pipeline.  The synthetic chain harness
builds its own `LineageGraph` with `VersionNode` objects, which is a
different data structure entirely.

**Impact:** No append-only lineage edges are created from actual
execution results in the v2 pipeline.  Lineage is not a runtime output.

---

## CHECKPOINT 0

```
PHASE 0 STATUS: PASS

Evidence:
- Actual production call graph identified (Section A)
- Every Layer A–G owner mapped against target (Section C gap matrix)
- Every existing Step 24 component classified:
    AuthorizedTransformationEngine:  EXISTS, NOT WIRED (bypassed)
    ConservationValidator:           EXISTS, NOT WIRED (bypassed)
    ProofBuilder/ProofAssembler:     EXISTS, NOT WIRED (bypassed)
    AuthorityGate:                   EXISTS, NOT WIRED (bypassed by assess_authority)
    CommitmentKernel/KernelStore:    EXISTS, NOT WIRED (pipeline uses CommitmentState)
    AgreementAddressMap/IdentityResolver: EXISTS, NOT WIRED (bypassed by commitment_registry)
    apply_transformation:            EXISTS, NOT WIRED (bypassed by executor)
    CommitmentLineageGraph:          EXISTS, NOT WIRED (no lineage in v2 pipeline)
- State-advancement locations identified (Section E):
    semantic_pipeline_v2.py:427-431 (current_state = execution_result.state)
    chain_reconstruction.py:617-623 (current_state = reconstructed)
    executor.py:186-231 (execute_amendment mutates state)
- Authority-decision locations identified (Section E):
    semantic_pipeline_v2.py:388-399 (assess_authority)
    chain_reconstruction.py:590-593 (is_authoritative inline)
- Legacy semantic bypasses identified (Section F):
    Bypass 1: StructuredMutation → AmendmentInstruction → legacy executor (CONTROLLING)
    Bypass 2: Global section heuristics as identity authority (CONTROLLING)
    Bypass 3: moses_safety proof ≠ SemanticTransformationProof (CONTROLLING)
    Bypass 4: assess_authority() ≠ AuthorityGate (CONTROLLING)
    Bypass 5: No CommitmentLineageGraph in production (ABSENT)
- No runtime behavior changed during this phase
- Existing safety baseline remains unchanged (no code modified)

Unresolved gaps:
- All 5 bypasses must be closed for the SCALAR_REPLACEMENT family in Phases 1–8
- CommitmentState → CommitmentKernel conversion must be established (Phase 1)
- Thin kernel executor must be implemented (Phase 6)
- Lineage validity must be added to AuthorityGate (Phase 8)

Safe to proceed to Phase 1: YES
```
