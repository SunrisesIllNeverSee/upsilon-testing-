# src/upsilon/execution/ — Transformation Execution

**STATUS: TARGET_SCAFFOLD**

## PURPOSE

Applies already-validated structured transformations to commitment state. Execution produces the successor state and records the execution result. It must NOT contain EDGAR lexical heuristics or text-based semantic interpretation.

## OWNS

- Application of validated transformations to produce successor state
- Execution result reporting (applied, status, state_changed)

## DOES NOT OWN

- Transformation interpretation (transformations domain)
- Authority decisions (authority domain)
- Conservation validation (conservation domain)
- Raw text parsing (parsing domain)

## ALLOWED INPUTS

- `CommitmentKernel` (predecessor)
- `AuthorizedTransformation` (validated delta)

## ALLOWED OUTPUTS

- `CommitmentKernel` (successor)
- `ExecutionResultSummary`

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)
- `upsilon.transformations` (for `AuthorizedTransformation` type and `apply_transformation`)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (execution produces the result; authority consumes it)
- `upsilon.conservation` (conservation is a precondition for execution)
- `upsilon.proof` (proof is assembled before execution)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `executor.py` (root) — applies structured mutations to commitment state; CLEAN; migration target: `src/upsilon/execution/`
- `chain_reconstruction.py` (root) — execution state advancement entangled with lineage and authority; BOUNDARY_VIOLATION; execution logic extracts to this domain

## CURRENT IMPLEMENTED TARGET MODULES

None (`.gitkeep` only). Note: `upsilon.transformations.apply` contains a pure-functional `apply_transformation` that produces the successor kernel, but the full execution layer (with side-effects, result reporting, and lineage edge creation) is not yet implemented here.

## OPERATING STATUS

TARGET_SCAFFOLD — no runtime code yet. The pure-functional apply lives in `transformations/apply.py`; the execution layer with side-effects is future work.

## MIGRATION PRECONDITIONS

- Legacy `executor.py` can move once its dependents are updated.
- Legacy `chain_reconstruction.py` must be decomposed first: execution → `execution/`, lineage → `lineage/`, authority → `authority/`.
