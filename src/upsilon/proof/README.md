# src/upsilon/proof/ — Semantic Transformation Proof Records

**STATUS: TARGET_ACTIVE**

## PURPOSE

Assembles semantic transformation proof records. The proof record is NOT philosophical proof — it is a structured record of what evidence was available, what target identity was established, what transformation was authorized, what conservation checks passed, and what the execution result was. The proof is assembled BEFORE execution and updated AFTER execution.

## OWNS

- `ProofBuilder` — assembles `SemanticTransformationProof` from transformation components
- `ProofAssembler` — assembles pre-execution and updates post-execution

## DOES NOT OWN

- Semantic interpretation (transformations domain)
- Conservation validation (conservation domain)
- Authority decisions (authority domain)
- Execution (execution domain)

## ALLOWED INPUTS

- `AuthorizedTransformation` (the delta)
- `IdentityResolutionResult` (target identity evidence)
- `ValidationResult` (conservation check results)
- Predecessor and successor version numbers

## ALLOWED OUTPUTS

- `SemanticTransformationProof` records

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)
- `upsilon.commitments.identity` (for `IdentityResolutionResult` type)
- `upsilon.conservation.validator` (for `ValidationResult` type)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (proof is a precondition for authority, not a consumer)
- `upsilon.execution` (proof is assembled before execution)
- `upsilon.transformations` (transformation interpretation)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- No direct legacy equivalent. Proof records were implicit in the legacy pipeline.

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — exports `ProofBuilder`, `ProofAssembler`
- `transformation_proof.py` — `ProofBuilder` and `ProofAssembler` implementing `docs/moses/SEMANTIC_PROOF_RECORD.md` §10

## CONFORMANCE INVARIANTS TOUCHED

- Proof completeness and validity (SEMANTIC_PROOF_RECORD.md §7)
- Authority preconditions (proof must be COMPLETE and VALID for authority to be granted)

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass, not yet wired into the legacy pipeline.

## MIGRATION PRECONDITIONS

- Legacy pipeline must be wired to produce proof records for every transformation.
- Conformance tests for proof completeness/validity must be added.
