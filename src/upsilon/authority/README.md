# src/upsilon/authority/ — Authority Promotion Gate

**STATUS: TARGET_ACTIVE**

## PURPOSE

Determines whether a transformation step may be promoted to authoritative. Consumes execution results, proof records, and conservation status to make the authority decision. Does NOT inspect raw EDGAR text to infer meaning.

## OWNS

- Authority gate decision logic (AUTHORITY_GRANTED, AUTHORITY_BLOCKED, VALIDATION_REQUIRED, PARTIAL, UNRESOLVED)
- Promotion preconditions: proof completeness, proof validity, conservation checks, inherited unresolved state, evidence status, uncertainty routing

## DOES NOT OWN

- Semantic interpretation of amendment text
- Execution of transformations
- Conservation validation
- Proof assembly
- Raw EDGAR parsing

## ALLOWED INPUTS

- `ExecutionResultSummary` (from execution layer)
- `SemanticTransformationProof` (from proof layer)
- `inherited_unresolved` count (from chain/lineage context)

## ALLOWED OUTPUTS

- `AuthorityGateResult` containing `AuthorityDecision` + reason + proof_id

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)
- `upsilon.proof` (proof record types)

## FORBIDDEN DEPENDENCIES

- `upsilon.ingestion`, `upsilon.parsing` (raw text processing)
- `upsilon.execution` (execution applies transformations; authority consumes the result)
- `upsilon.transformations` (transformation interpretation)
- Any root-level legacy module
- `audits/`, `research/`, `results/` (runtime may not import audit/research)

## CURRENT LEGACY SOURCES

- `semantic_pipeline_v2.py` (root) — contains authority determination logic entangled with pipeline orchestration; BOUNDARY_VIOLATION; migration precondition: authority logic extracted first

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — exports `AuthorityGate`, `AuthorityGateResult`
- `promotion_gate.py` — `AuthorityGate` implementing the decision logic from `docs/moses/SEMANTIC_AUTHORITY_GATE.md` §5

## CONFORMANCE INVARIANTS TOUCHED

- Authority gate preconditions (SEMANTIC_AUTHORITY_GATE.md §5)

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass, not yet wired into the legacy pipeline.

## MIGRATION PRECONDITIONS

- Legacy `semantic_pipeline_v2.py` authority logic must be extracted and replaced with calls to this gate.
- Conformance tests for authority decisions must be added under `tests/authority/`.
