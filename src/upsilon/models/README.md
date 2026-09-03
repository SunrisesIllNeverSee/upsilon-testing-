# src/upsilon/models/ — Shared Data Models (Layer 0)

**STATUS: TARGET_ACTIVE**

## PURPOSE

Defines the canonical value objects that all semantic subdomains operate over. This is Layer 0 — no layer-specific logic lives here. Models are designed for compatibility with the legacy `models.CommitmentState` so migration can proceed without breaking the legacy test suite.

## OWNS

- `CommitmentIdentity` — persistent agreement-local identity
- `CommitmentKernel` — canonical commitment state object (C_{t-1} and C_t)
- `KernelVersion` — immutable version stamp for lineage tracing
- `LineageEdge` — append-only lineage record
- `SemanticTransformationProof` — proof record
- `AuthorizedTransformation` — the delta object (Δ_t)
- `AuthorityDecision` — authority gate decision enum
- Supporting types: `AddressBinding`, `AffectedField`, `EdgeClass`, `NodeClass`, `ValidationStatus`, `EvidenceLevel`, `EvidenceStatus`, `UncertaintyStatus`, `ProofCompleteness`, `ProofValidity`, `CheckResult`, `ConservationChecks`, `ValidatorResults`, `TargetSignal`, `TargetIdentityEvidence`, `ExecutionResultSummary`, `TransformationFamily`, `IdentityProvenance`, `IdentityEvent`

## DOES NOT OWN

- Layer-specific logic (identity resolution, transformation interpretation, validation, proof assembly, authority decisions)
- Runtime behavior of any kind

## ALLOWED INPUTS

- None (models are passive data structures)

## ALLOWED OUTPUTS

- Pydantic model instances

## ALLOWED DEPENDENCIES

- `pydantic` (third-party)
- Python standard library (`datetime`, `enum`, `typing`)

## FORBIDDEN DEPENDENCIES

- Any other `upsilon.*` subdomain (models is Layer 0; no layer-specific imports)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `models.py` (root) — `CommitmentState` and shared data models; CLEAN; migration target: `src/upsilon/models/`; many dependents (HIGH risk)

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — re-exports all model types
- `authority.py` — `AuthorityDecision` enum
- `identity.py` — `CommitmentIdentity`, `AddressBinding`, `IdentityProvenance`, `IdentityEvent`
- `kernel.py` — `CommitmentKernel`, `KernelVersion`
- `lineage.py` — `LineageEdge`, `NodeClass`, `EdgeClass`, `ValidationStatus`
- `proof.py` — `SemanticTransformationProof`, `CheckResult`, `ConservationChecks`, `ValidatorResults`, `TargetSignal`, `TargetIdentityEvidence`, `ExecutionResultSummary`, evidence/proof/uncertainty enums
- `transformation.py` — `AuthorizedTransformation`, `AffectedField`, `TransformationFamily`

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass.

## MIGRATION PRECONDITIONS

- Legacy `models.py` `CommitmentState` must be reconciled with `upsilon.models.CommitmentKernel`. A compatibility layer or direct migration is required before legacy modules can be retired.
