# Target Runtime Inventory — Step 23G-R

**Date:** 2026-09-02
**Baseline commit:** `035daeb`

This inventory documents every runtime `.py` file under `src/upsilon/` that contains real implementation (not `.gitkeep` or empty `__init__.py` re-exports).

Step 24 (`035daeb`) added 26 runtime files implementing the conservation-first commitment architecture. This inventory confirms that Step 23S/24 has **already begun implementing architecture** — the target is not merely a scaffold.

---

## authority/

### `authority/promotion_gate.py`
- **Responsibility:** Authority gate — determines whether a transformation step may be promoted to authoritative
- **Imports:** `upsilon.models` (AuthorityDecision, ExecutionResultSummary, ProofCompleteness, ProofValidity, SemanticTransformationProof)
- **Dependents:** `authority/__init__.py`
- **Implementation status:** COMPLETE — implements `docs/moses/SEMANTIC_AUTHORITY_GATE.md` §5 decision logic
- **Test coverage:** 8 tests in `tests/unit/test_upsilonsrc.py::TestAuthorityGate`
- **Legacy equivalent:** `semantic_pipeline_v2.py` authority determination (entangled)
- **Conformance invariants touched:** Authority gate preconditions
- **Operating status:** TARGET_ACTIVE

---

## commitments/

### `commitments/identity.py`
- **Responsibility:** Agreement-local address map and identity resolution from amendment evidence + predecessor state
- **Imports:** `upsilon.models` (AddressBinding, CommitmentIdentity, IdentityProvenance)
- **Dependents:** `commitments/__init__.py`, `commitments/kernel.py`, `conservation/invariants.py`, `conservation/validator.py`, `lineage/graph.py`, `proof/transformation_proof.py`, `transformations/authorized_change.py`
- **Implementation status:** COMPLETE — `AgreementAddressMap`, `IdentityResolver`, `IdentityResolutionResult`
- **Test coverage:** 7 tests in `TestAgreementAddressMap` + `TestIdentityResolver`
- **Legacy equivalent:** `commitment_registry.py` (identity entangled with evidence alias matching)
- **Conformance invariants touched:** Identity persistence (§2.1), Target reference separation (§2.6)
- **Operating status:** TARGET_ACTIVE

### `commitments/kernel.py`
- **Responsibility:** Kernel store with version tracking and origin kernel builder
- **Imports:** `upsilon.models` (CommitmentIdentity, CommitmentKernel, KernelVersion)
- **Dependents:** `commitments/__init__.py`, `conservation/invariants.py`, `conservation/loss_detection.py`, `lineage/graph.py`, `proof/transformation_proof.py`, `transformations/apply.py`, `transformations/authorized_change.py`
- **Implementation status:** COMPLETE — `KernelStore`, `OriginKernelBuilder`
- **Test coverage:** 5 tests in `TestKernelStore`
- **Legacy equivalent:** `persistence.py` (state storage), `models.py` (CommitmentState)
- **Conformance invariants touched:** Kernel version immutability, temporal authority rule K(A,T)
- **Operating status:** TARGET_ACTIVE

---

## conservation/

### `conservation/invariants.py`
- **Responsibility:** 10 conservation invariant families
- **Imports:** `upsilon.models` (AuthorizedTransformation, CheckResult, CommitmentKernel, TransformationFamily)
- **Dependents:** `conservation/__init__.py`, `conservation/validator.py`, `authority/promotion_gate.py`
- **Implementation status:** COMPLETE — all 10 invariant classes: IdentityPersistence, OldValueConsistency, UnchangedFieldPreservation, NoUnsupportedSemanticGain, NoSilentSemanticLoss, TargetReferenceSeparation, LineageContinuity, TemporalValidity, OutOfScopeIsolation, TransformationCompleteness
- **Test coverage:** 6 tests in `TestConservationValidator`
- **Legacy equivalent:** `moses_safety.py` (partial overlap)
- **Conformance invariants touched:** All 10 (§2.1–§2.10)
- **Operating status:** TARGET_ACTIVE

### `conservation/loss_detection.py`
- **Responsibility:** Detailed field-by-field semantic loss detection
- **Imports:** `upsilon.models` (AuthorizedTransformation, CommitmentKernel, TransformationFamily)
- **Dependents:** `conservation/__init__.py`
- **Implementation status:** COMPLETE — `LossDetector` with list/dict/scalar field loss detection
- **Test coverage:** 2 tests in `TestLossDetector`
- **Legacy equivalent:** None
- **Conformance invariants touched:** No silent semantic loss (§2.5)
- **Operating status:** TARGET_ACTIVE

### `conservation/validator.py`
- **Responsibility:** Conservation validator — runs all applicable invariants against (predecessor, successor, delta)
- **Imports:** `upsilon.models` (AuthorizedTransformation, CheckResult, CommitmentKernel, ConservationChecks, ValidatorResults), `.invariants` (InvariantNames, applicable_invariants)
- **Dependents:** `conservation/__init__.py`, `proof/transformation_proof.py`
- **Implementation status:** COMPLETE — `ConservationValidator`, `ValidationResult`
- **Test coverage:** 6 tests in `TestConservationValidator`
- **Legacy equivalent:** None
- **Conformance invariants touched:** All 10 (orchestrates them)
- **Operating status:** TARGET_ACTIVE

---

## lineage/

### `lineage/graph.py`
- **Responsibility:** Append-only commitment lineage graph
- **Imports:** `upsilon.models` (EdgeClass, LineageEdge, TransformationFamily, ValidationStatus)
- **Dependents:** `lineage/__init__.py`, `lineage/queries.py`
- **Implementation status:** COMPLETE — `CommitmentLineageGraph` with add_edge, validate/reject, trace_to_origin, is_reachable_from_origin
- **Test coverage:** 10 tests in `TestCommitmentLineageGraph`
- **Legacy equivalent:** `chain_reconstruction.py` (lineage entangled with execution and authority)
- **Conformance invariants touched:** Lineage continuity (§2.7), L1–L7
- **Operating status:** TARGET_ACTIVE

### `lineage/queries.py`
- **Responsibility:** Query interface over the lineage graph
- **Imports:** `upsilon.models` (LineageEdge, TransformationFamily, ValidationStatus), `.graph` (CommitmentLineageGraph)
- **Dependents:** `lineage/__init__.py`
- **Implementation status:** COMPLETE — `LineageQueries` with history, transformations_by_type, amendments_affecting, validated_history, has_unvalidated_edges, affected_fields_history
- **Test coverage:** 3 tests in `TestLineageQueries`
- **Legacy equivalent:** None
- **Conformance invariants touched:** L1–L7 (query support)
- **Operating status:** TARGET_ACTIVE

---

## models/

### `models/authority.py`
- **Responsibility:** AuthorityDecision enum
- **Imports:** (none — stdlib only)
- **Dependents:** `authority/promotion_gate.py`, all modules via `models/__init__.py`
- **Implementation status:** COMPLETE
- **Test coverage:** Indirect via authority tests
- **Legacy equivalent:** None
- **Operating status:** TARGET_ACTIVE

### `models/identity.py`
- **Responsibility:** CommitmentIdentity, AddressBinding, IdentityProvenance, IdentityEvent
- **Imports:** (none — stdlib + pydantic)
- **Dependents:** all modules via `models/__init__.py`
- **Implementation status:** COMPLETE
- **Test coverage:** 3 tests in `TestCommitmentIdentity`
- **Legacy equivalent:** `models.py` CommitmentState (partial)
- **Operating status:** TARGET_ACTIVE

### `models/kernel.py`
- **Responsibility:** CommitmentKernel, KernelVersion
- **Imports:** `.identity` (CommitmentIdentity)
- **Dependents:** all modules via `models/__init__.py`
- **Implementation status:** COMPLETE — 20 semantic fields, version tracking, field_value, semantic_fields
- **Test coverage:** 2 tests in `TestCommitmentKernel`
- **Legacy equivalent:** `models.py` CommitmentState
- **Operating status:** TARGET_ACTIVE

### `models/lineage.py`
- **Responsibility:** LineageEdge, NodeClass, EdgeClass, ValidationStatus
- **Imports:** `.transformation` (TransformationFamily)
- **Dependents:** all modules via `models/__init__.py`
- **Implementation status:** COMPLETE — 12-field LineageEdge schema
- **Test coverage:** 2 tests in `TestCommitmentLineageGraph` (edge properties)
- **Legacy equivalent:** None
- **Operating status:** TARGET_ACTIVE

### `models/proof.py`
- **Responsibility:** SemanticTransformationProof and supporting types (CheckResult, ConservationChecks, ValidatorResults, TargetSignal, TargetIdentityEvidence, ExecutionResultSummary, evidence/proof/uncertainty enums)
- **Imports:** `.transformation` (TransformationFamily)
- **Dependents:** `authority/promotion_gate.py`, `proof/transformation_proof.py`
- **Implementation status:** COMPLETE — full proof record schema with completeness/validity checks
- **Test coverage:** 4 tests in `TestProofAssembly`
- **Legacy equivalent:** None
- **Operating status:** TARGET_ACTIVE

### `models/transformation.py`
- **Responsibility:** AuthorizedTransformation, AffectedField, TransformationFamily (13 families)
- **Imports:** (none — stdlib + pydantic)
- **Dependents:** all modules via `models/__init__.py`
- **Implementation status:** COMPLETE — 13 transformation families, affected field tracking, old/new value accessors
- **Test coverage:** 1 test in `TestTransformationFamily`
- **Legacy equivalent:** None
- **Operating status:** TARGET_ACTIVE

---

## proof/

### `proof/transformation_proof.py`
- **Responsibility:** Proof builder and assembler
- **Imports:** `upsilon.commitments.identity` (IdentityResolutionResult), `upsilon.conservation.validator` (ValidationResult), `upsilon.models` (multiple)
- **Dependents:** `proof/__init__.py`
- **Implementation status:** COMPLETE — `ProofBuilder` and `ProofAssembler` implementing `docs/moses/SEMANTIC_PROOF_RECORD.md` §10
- **Test coverage:** 4 tests in `TestProofAssembly`
- **Legacy equivalent:** None
- **Conformance invariants touched:** Proof completeness and validity (§7)
- **Operating status:** TARGET_ACTIVE

---

## transformations/

### `transformations/apply.py`
- **Responsibility:** Pure-functional transformation application: C_t = Apply(C_{t-1}, Δ_t)
- **Imports:** `upsilon.models` (AuthorizedTransformation, CommitmentKernel, TransformationFamily)
- **Dependents:** `transformations/__init__.py`
- **Implementation status:** COMPLETE — handles scalar replacement, exception expansion/contraction, status transitions, identity preservation
- **Test coverage:** 5 tests in `TestApplyTransformation`
- **Legacy equivalent:** `executor.py` (applies mutations, but with side-effects)
- **Conformance invariants touched:** Unchanged field preservation (§2.3)
- **Operating status:** TARGET_ACTIVE

### `transformations/authorized_change.py`
- **Responsibility:** AuthorizedTransformationEngine — (C_{t-1}, E_t, A_t) → Δ_t
- **Imports:** `upsilon.commitments.identity` (IdentityResolutionResult, IdentityResolver), `upsilon.models` (AffectedField, AuthorizedTransformation, CommitmentKernel, TransformationFamily)
- **Dependents:** `transformations/__init__.py`
- **Implementation status:** COMPLETE — 6-step process: establish identity, determine type, determine affected fields, determine values, verify old-value consistency, produce delta
- **Test coverage:** 9 tests in `TestAuthorizedTransformationEngine`
- **Legacy equivalent:** `semantic_resolver_v2.py` (re-extracts values, discards parser output), `semantic_mapper.py` (section heuristics)
- **Conformance invariants touched:** Old-value consistency (§2.2), Transformation completeness (§2.10), Target reference separation (§2.6)
- **Operating status:** TARGET_ACTIVE

---

## Summary

| Metric | Value |
|--------|-------|
| Target runtime files | 26 (including `__init__.py` re-exports) |
| Files with real implementation | 17 (excluding `__init__.py`) |
| Total tests in target test suite | 72 |
| Domains TARGET_ACTIVE | 7 (authority, commitments, conservation, lineage, models, proof, transformations) |
| Domains TARGET_SCAFFOLD | 6 (evidence, execution, ingestion, parsing, pipeline, propagation) |
| Legacy equivalents being replaced | 5 (semantic_resolver_v2, semantic_mapper, commitment_registry, chain_reconstruction, moses_safety) |
| Wired into legacy pipeline | NO — target runtime exists but is not yet connected to the legacy pipeline |
