"""Conservation validator.

Implements the Layer D component specified in
``docs/moses/CONSERVATION_INVARIANTS.md`` §5.

| Inputs  | Candidate successor C_t, predecessor C_{t-1}, authorized Delta_t |
| Outputs | Validation results: pass/fail per invariant, with failure reasons |
| May do  | Check all 10 invariant families; report which passed and which failed |
| Must not | Perform raw EDGAR parsing; construct transformations; grant authority; execute |
| Failure | If any invariant fails, the candidate is rejected.  Rejection prevents execution. |

Validation runs AFTER the AuthorizedTransformationEngine produces
Delta_t and BEFORE execution.  It is a precondition for execution,
not a post-hoc check.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from upsilon.models import (
    AuthorizedTransformation,
    CheckResult,
    CommitmentKernel,
    ConservationChecks,
    ValidatorResults,
)

from .invariants import (
    InvariantNames,
    applicable_invariants,
)


@dataclass
class ValidationResult:
    """Result of conservation validation."""

    passed: bool
    checks: ConservationChecks = field(default_factory=ConservationChecks)
    validator_results: ValidatorResults = field(default_factory=ValidatorResults)
    failed_invariants: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.passed


class ConservationValidator:
    """Validates a candidate successor against all applicable conservation invariants.

    This is Layer D.  It runs after the AuthorizedTransformationEngine
    (Layer B) produces Delta_t and before execution (Layer F).
    """

    def validate(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> ValidationResult:
        """Validate a candidate transformation against all applicable invariants."""
        invariants = applicable_invariants(delta.transformation_type)

        check_results: list[CheckResult] = []
        checks = ConservationChecks()
        failed: list[str] = []

        for invariant in invariants:
            result = invariant.check(predecessor, successor, delta)
            check_results.append(result)
            if not result.passed:
                failed.append(result.invariant_name)

            # Store in the ConservationChecks structure
            name = invariant.name
            if name == InvariantNames.IDENTITY_PERSISTENCE:
                checks.identity_persistence = result
            elif name == InvariantNames.OLD_VALUE_CONSISTENCY:
                checks.old_value_consistency = result
            elif name == InvariantNames.UNCHANGED_FIELD_PRESERVATION:
                checks.unchanged_field_preservation = result
            elif name == InvariantNames.NO_UNSUPPORTED_SEMANTIC_GAIN:
                checks.no_unsupported_semantic_gain = result
            elif name == InvariantNames.NO_SILENT_SEMANTIC_LOSS:
                checks.no_silent_semantic_loss = result
            elif name == InvariantNames.TARGET_REFERENCE_SEPARATION:
                checks.target_reference_separation = result
            elif name == InvariantNames.LINEAGE_CONTINUITY:
                checks.lineage_continuity = result
            elif name == InvariantNames.TEMPORAL_VALIDITY:
                checks.temporal_validity = result
            elif name == InvariantNames.OUT_OF_SCOPE_ISOLATION:
                checks.out_of_scope_isolation = result
            elif name == InvariantNames.TRANSFORMATION_COMPLETENESS:
                checks.transformation_completeness = result

        validator_results = ValidatorResults(
            checks=check_results,
            summary=f"{len(check_results)} checks, {len(failed)} failed",
        )

        return ValidationResult(
            passed=len(failed) == 0,
            checks=checks,
            validator_results=validator_results,
            failed_invariants=failed,
        )
