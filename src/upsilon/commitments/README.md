# src/upsilon/commitments/ — Commitment Identity and Canonical State

**STATUS: TARGET_ACTIVE**

## PURPOSE

Owns persistent agreement-local commitment identity and the canonical commitment kernel (origin kernel C₀ and authoritative current kernel C*t). Identity survives across amendments unless an identity-changing transformation (CREATE, TERMINATE, RENUMBER) explicitly establishes otherwise.

## OWNS

- `CommitmentIdentity` — stable semantic identifier (commitment_id + agreement_identity)
- `AgreementAddressMap` — agreement-local section-ref → commitment_id resolution
- `IdentityResolver` — resolves target identity from amendment evidence + predecessor state
- `KernelStore` — in-memory store for commitment kernels with version tracking
- `OriginKernelBuilder` — builds the origin kernel C₀ from source agreement extraction

## DOES NOT OWN

- Transformation interpretation (transformations domain)
- Authority decisions (authority domain)
- Raw text parsing (parsing domain)
- Evidence extraction from amendment text (evidence domain)

## ALLOWED INPUTS

- Amendment evidence signals (section refs, aliases, text matches, predecessor IDs)
- Source agreement extraction output (for origin kernel building)
- Canonical key hints (from the 13 frozen classes)

## ALLOWED OUTPUTS

- `CommitmentIdentity` (resolved identity)
- `CommitmentKernel` (canonical state)
- `KernelVersion` (version stamps)
- `IdentityResolutionResult` (with confidence and evidence level)

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (commitments may not depend on authority)
- `upsilon.transformations` (commitments provide state; transformations operate over it)
- `upsilon.conservation`, `upsilon.proof`, `upsilon.execution`
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `commitment_registry.py` (root) — combines commitment identity with evidence alias matching; BOUNDARY_VIOLATION; migration precondition: identity and evidence layers separated
- `persistence.py` (root) — commitment state storage; CLEAN; migration target: `src/upsilon/commitments/`
- `models.py` (root) — `CommitmentState` shared data model; CLEAN; migration target: `src/upsilon/models/`

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — exports `AgreementAddressMap`, `IdentityResolver`, `IdentityResolutionResult`, `KernelStore`, `OriginKernelBuilder`
- `identity.py` — `AgreementAddressMap`, `IdentityResolver`, `IdentityResolutionResult`
- `kernel.py` — `KernelStore`, `OriginKernelBuilder`

## CONFORMANCE INVARIANTS TOUCHED

- Identity persistence (CONSERVATION_INVARIANTS.md §2.1): ID(C_t) == ID(C_{t-1}) unless identity-changing transformation
- Target reference separation (§2.6): reference ≠ target

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass, not yet wired into the legacy pipeline.

## MIGRATION PRECONDITIONS

- Legacy `commitment_registry.py` must be decomposed: identity logic → `src/upsilon/commitments/identity.py`; evidence alias matching → `src/upsilon/evidence/`.
- Legacy `models.py` `CommitmentState` must be reconciled with `upsilon.models.CommitmentKernel` (compatibility layer or migration).
