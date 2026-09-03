# src/upsilon/propagation/ — Downstream Propagation and Comparison

**STATUS: TARGET_SCAFFOLD**

## PURPOSE

Owns the third integrity domain: Propagation Integrity. Verifies that downstream representations match the current authoritative kernel. A downstream state cannot become canonical merely by differing from the current kernel.

This domain is documented as a first-class architectural responsibility in:
- `docs/architecture/DEPENDENCY_DIRECTION.md` (line 50: "DOWNSTREAM PROPAGATION / COMPARISON")
- `docs/architecture/ARCHITECTURE_INDEX.md` (line 107: "Propagation Integrity — Not yet addressed")
- `docs/moses/CONFORMANCE_CONTRACT.md` (L7: "downstream state cannot become canonical merely by differing from current kernel")

## OWNS

- Downstream representation comparison
- Propagation integrity validation
- Canonical-vs-downstream drift detection

## DOES NOT OWN

- Transformation interpretation (transformations domain)
- Authority decisions (authority domain)
- Kernel state storage (commitments domain)

## ALLOWED INPUTS

- `CommitmentKernel` (current authoritative kernel)
- Downstream representation state

## ALLOWED OUTPUTS

- Propagation validation results
- Drift detection reports

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)
- `upsilon.lineage` (for authoritative state queries)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (propagation verifies downstream; authority promotes upstream)
- `upsilon.transformations` (transformation interpretation)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

None. No legacy module currently addresses propagation integrity.

## CURRENT IMPLEMENTED TARGET MODULES

None (`.gitkeep` only). No runtime behavior is implemented in this step.

## CONFORMANCE INVARIANTS TOUCHED

- L7 (CONFORMANCE_CONTRACT.md): downstream state cannot become canonical merely by differing from current kernel

## OPERATING STATUS

TARGET_SCAFFOLD — newly created in Step 23G-R. No runtime code. Placeholder for future implementation of the third integrity domain.

## MIGRATION PRECONDITIONS

- Propagation runtime behavior must NOT be implemented until the transformation and lineage layers are wired into the active pipeline.
- Conformance tests for L7 must be added under `tests/conformance/`.
