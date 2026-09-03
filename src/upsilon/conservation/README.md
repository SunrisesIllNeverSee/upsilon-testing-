# src/upsilon/conservation/ — Conservation Validation

**STATUS: TARGET_ACTIVE**

## PURPOSE

Validates candidate transformations against conservation invariants. Runs AFTER the AuthorizedTransformationEngine produces Δ_t and BEFORE execution. Conservation does NOT mean preventing legitimate amendments — it means no unauthorized semantic change, no unexplained semantic loss, and no unsupported semantic gain.

## OWNS

- 10 conservation invariant families (CONSERVATION_INVARIANTS.md §2)
- `ConservationValidator` — runs all applicable invariants against (predecessor, successor, delta)
- `LossDetector` — detailed field-by-field semantic loss detection

## DOES NOT OWN

- Transformation interpretation (transformations domain)
- Authority decisions (authority domain)
- Raw text parsing (parsing domain)
- Execution (execution domain)

## ALLOWED INPUTS

- `CommitmentKernel` (predecessor and successor)
- `AuthorizedTransformation` (the delta being validated)

## ALLOWED OUTPUTS

- `ValidationResult` with per-invariant `CheckResult` entries
- `LossDetectionResult` with field-level loss details

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)
- `upsilon.transformations` (for `TransformationFamily` enum — invariant applicability)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (conservation is a precondition for authority, not a consumer of it)
- `upsilon.execution` (conservation runs before execution)
- `upsilon.proof` (proof assembles conservation results; conservation does not depend on proof)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- No direct legacy equivalent. Conservation validation was implicit in the legacy pipeline's authority determination. The `moses_safety.py` root module contains safety enforcement logic that partially overlaps.

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — exports `ConservationValidator`, `ValidationResult`, `LossDetector`, `ConservationInvariant`, `InvariantNames`
- `invariants.py` — 10 invariant classes: `IdentityPersistence`, `OldValueConsistency`, `UnchangedFieldPreservation`, `NoUnsupportedSemanticGain`, `NoSilentSemanticLoss`, `TargetReferenceSeparation`, `LineageContinuity`, `TemporalValidity`, `OutOfScopeIsolation`, `TransformationCompleteness`
- `validator.py` — `ConservationValidator` running applicable invariants
- `loss_detection.py` — `LossDetector` for detailed field-level loss reporting

## CONFORMANCE INVARIANTS TOUCHED

All 10 invariant families (CONSERVATION_INVARIANTS.md §2.1–§2.10):
1. Identity persistence
2. Old-value consistency
3. Unchanged field preservation
4. No unsupported semantic gain
5. No silent semantic loss
6. Target reference separation
7. Lineage continuity
8. Temporal validity
9. Out-of-scope isolation
10. Transformation completeness

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass, not yet wired into the legacy pipeline.

## MIGRATION PRECONDITIONS

- Legacy `moses_safety.py` safety enforcement must be reconciled with these invariants.
- Conformance tests for each invariant must be added under `tests/conservation/`.
