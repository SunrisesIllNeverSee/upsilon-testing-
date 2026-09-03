# src/upsilon/transformations/ — Authorized Transformation Engine

**STATUS: TARGET_ACTIVE**

## PURPOSE

Owns operations over commitment state that consume evidence. The `AuthorizedTransformationEngine` produces authorized semantic transformations (Δ_t) from predecessor state, amendment evidence, and authority context. The `apply_transformation` function produces the successor kernel from the predecessor and an authorized delta.

## Governing equation

```
(C_{t-1}, E_t, A_t) → Δ_t

C_t = Apply(C_{t-1}, Δ_t)
```

## OWNS

- `AuthorizedTransformationEngine` — produces `AuthorizedTransformation` (Δ_t) from evidence + predecessor state
- `apply_transformation` — pure functional application producing successor kernel
- `AmendmentEvidence` — evidence extracted from an amendment (Layer A output)
- `AuthorityContext` — predecessor state and chain context
- `TransformationResult` — authorized or rejected result

## DOES NOT OWN

- Raw document parsing (parsing domain)
- Authority decisions (authority domain)
- Conservation validation (conservation domain)
- Kernel state storage (commitments domain)
- Execution side-effects (execution domain)

## ALLOWED INPUTS

- `AmendmentEvidence` (from Layer A parsing)
- `AuthorityContext` (predecessor kernel, predecessor commitment IDs, chain position)
- `CommitmentKernel` (predecessor state, for apply)

## ALLOWED OUTPUTS

- `AuthorizedTransformation` (the delta)
- `CommitmentKernel` (the successor, from apply)

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)
- `upsilon.commitments.identity` (for `IdentityResolver` and `IdentityResolutionResult`)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (transformations may not grant authority)
- `upsilon.conservation` (conservation validates transformations; transformations do not depend on conservation)
- `upsilon.proof` (proof assembles transformation records; transformations do not depend on proof)
- `upsilon.execution` (execution applies transformations)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `semantic_resolver_v2.py` (root) — re-extracts values from source text, discarding parser-provided old/new values; BOUNDARY_VIOLATION; migration precondition: new identity/evidence/transformation interfaces exist first
- `semantic_mapper.py` (root) — resolves commitment identity via section-number heuristics; BOUNDARY_VIOLATION; migration target: `src/upsilon/transformations/`
- `v02_change_spec.py` (root) — change specification logic; migration candidate

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — exports `AuthorizedTransformationEngine`, `AmendmentEvidence`, `AuthorityContext`, `TransformationResult`, `apply_transformation`
- `authorized_change.py` — `AuthorizedTransformationEngine` implementing the 6-step process from `docs/moses/TRANSFORMATION_ALGEBRA.md` §4
- `apply.py` — `apply_transformation` implementing `C_t = Apply(C_{t-1}, Δ_t)`

## CONFORMANCE INVARIANTS TOUCHED

- Old-value consistency (CONSERVATION_INVARIANTS.md §2.2): declared_old_value == C_{t-1}[field]
- Transformation completeness (§2.10): all affected fields must be extracted
- Target reference separation (§2.6): target identity from evidence, not from copying old_value

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass, not yet wired into the legacy pipeline.

## MIGRATION PRECONDITIONS

- Legacy `semantic_resolver_v2.py` must be retired after the new engine is wired into the pipeline.
- Legacy `semantic_mapper.py` section-heuristic identity resolution must be replaced by `IdentityResolver` (commitments domain).
- The 13 transformation families must remain frozen unless explicitly authorized.
