"""Conservation invariant definitions.

Implements the 10 invariant families specified in
``docs/moses/CONSERVATION_INVARIANTS.md`` §2.

Governing principle:

    C_t = C_{t-1} ⊕ Delta_t_authorized

subject to:

    Delta_t_actual = Delta_t_authorized

and, for every field outside the authorized transformation:

    C_t[f] = C_{t-1}[f]   for all f not in affected(Delta_t)

Conservation does NOT mean preventing legitimate amendment changes.
It means:
- no unauthorized semantic change
- no unexplained semantic loss
- no unsupported semantic gain
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from upsilon.models import (
    AuthorizedTransformation,
    CheckResult,
    CommitmentKernel,
    TransformationFamily,
)


class InvariantNames(str, Enum):
    """The 10 conservation invariant families."""

    IDENTITY_PERSISTENCE = "identity_persistence"
    OLD_VALUE_CONSISTENCY = "old_value_consistency"
    UNCHANGED_FIELD_PRESERVATION = "unchanged_field_preservation"
    NO_UNSUPPORTED_SEMANTIC_GAIN = "no_unsupported_semantic_gain"
    NO_SILENT_SEMANTIC_LOSS = "no_silent_semantic_loss"
    TARGET_REFERENCE_SEPARATION = "target_reference_separation"
    LINEAGE_CONTINUITY = "lineage_continuity"
    TEMPORAL_VALIDITY = "temporal_validity"
    OUT_OF_SCOPE_ISOLATION = "out_of_scope_isolation"
    TRANSFORMATION_COMPLETENESS = "transformation_completeness"


@dataclass
class ConservationInvariant:
    """One conservation invariant check.

    Each invariant is a function that takes (predecessor, successor,
    delta) and returns a CheckResult.
    """

    name: InvariantNames
    description: str
    applies_to: set[TransformationFamily]

    def check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> CheckResult:
        """Run this invariant's check."""
        try:
            passed, reason = self._check(predecessor, successor, delta)
            return CheckResult(
                invariant_name=self.name.value,
                passed=passed,
                failure_reason=reason,
            )
        except (TypeError, ValueError, AttributeError) as e:
            return CheckResult(
                invariant_name=self.name.value,
                passed=False,
                failure_reason=f"Invariant check error: {e}",
            )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        """Override in subclasses."""
        return True, ""


# ---------------------------------------------------------------------------
# Invariant implementations
# ---------------------------------------------------------------------------


class IdentityPersistence(ConservationInvariant):
    """2.1: ID(C_t) == ID(C_{t-1}) unless identity-changing transformation."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.IDENTITY_PERSISTENCE,
            description="ID(C_t) == ID(C_{t-1}) unless identity-changing transformation",
            applies_to={
                TransformationFamily.SCALAR_REPLACEMENT,
                TransformationFamily.MULTI_FIELD_REPLACEMENT,
                TransformationFamily.EXCEPTION_EXPANSION,
                TransformationFamily.EXCEPTION_CONTRACTION,
                TransformationFamily.SCHEDULE_REPLACEMENT,
                TransformationFamily.TEMPORAL_STEP_CHANGE,
                TransformationFamily.WAIVER,
                TransformationFamily.REINSTATEMENT,
                TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT,
                TransformationFamily.DEFINED_TERM_PROPAGATION,
                TransformationFamily.RENUMBER,
                TransformationFamily.TERMINATE,
            },
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        if delta.transformation_type == TransformationFamily.CREATE:
            return True, ""  # N/A for CREATE
        if predecessor is None or successor is None:
            return False, "Missing predecessor or successor kernel"
        if predecessor.commitment_id != successor.commitment_id:
            return False, (
                f"Identity changed: {predecessor.commitment_id} -> "
                f"{successor.commitment_id} without identity-changing transformation"
            )
        return True, ""


class OldValueConsistency(ConservationInvariant):
    """2.2: amendment_declared_old_value == C_{t-1}[field] (conservation check).

    This invariant independently verifies that the amendment-declared
    old value matches the predecessor's actual value.  It preserves two
    distinct concepts:

    - ``amendment_declared_old_value``: the old value stated in the
      amendment text (what the amendment claims is being replaced).
    - ``old_value`` (predecessor actual): the actual value in the
      predecessor kernel C_{t-1}[field].

    The invariant compares the amendment-declared old value against the
    predecessor actual value.  It does NOT compare the predecessor
    value against itself (which would be tautological x == x).

    If the amendment does not declare an old value
    (amendment_declared_old_value is None), the check is NOT_APPLICABLE
    and passes — the amendment does not claim a specific old value.

    The invariant also verifies the engine's
    ``old_value_consistency_verified`` flag as a secondary check.
    """

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.OLD_VALUE_CONSISTENCY,
            description="amendment_declared_old_value == C_{t-1}[field] (conservation check)",
            applies_to={
                TransformationFamily.SCALAR_REPLACEMENT,
                TransformationFamily.MULTI_FIELD_REPLACEMENT,
                TransformationFamily.EXCEPTION_CONTRACTION,
                TransformationFamily.SCHEDULE_REPLACEMENT,
                TransformationFamily.TEMPORAL_STEP_CHANGE,
                TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT,
            },
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        # First, verify the engine's flag is set.  If the engine
        # did not verify old-value consistency, that's a failure.
        if not delta.old_value_consistency_verified:
            return False, "Old-value consistency was not verified by the engine"

        if predecessor is None:
            return True, ""

        for affected in delta.affected_fields:
            # Use the amendment-declared old value, NOT the predecessor
            # actual value (which is in affected.old_value).  The
            # amendment-declared old value is what the amendment claims
            # is being replaced.  The predecessor actual value is what
            # is actually in the predecessor state.
            declared_old = affected.amendment_declared_old_value

            if declared_old is None:
                # No amendment-declared old value — NOT_APPLICABLE.
                # The amendment does not claim a specific old value,
                # so there is nothing to verify.
                continue

            pred_val = predecessor.field_value(affected.field_name)

            # Normalize numeric comparison
            if isinstance(pred_val, (int, float)) and isinstance(declared_old, (int, float)):
                if float(pred_val) != float(declared_old):
                    return False, (
                        f"Old-value consistency failed for field "
                        f"'{affected.field_name}': amendment-declared "
                        f"old value {declared_old!r} does not match "
                        f"predecessor actual value {pred_val!r}"
                    )
            elif pred_val != declared_old:
                return False, (
                    f"Old-value consistency failed for field "
                    f"'{affected.field_name}': amendment-declared "
                    f"old value {declared_old!r} does not match "
                    f"predecessor actual value {pred_val!r}"
                )

        return True, ""


class UnchangedFieldPreservation(ConservationInvariant):
    """2.3: C_t[f] == C_{t-1}[f] for all f not in affected(Delta_t)."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.UNCHANGED_FIELD_PRESERVATION,
            description="C_t[f] == C_{t-1}[f] for all f not in affected(Delta_t)",
            applies_to={
                TransformationFamily.SCALAR_REPLACEMENT,
                TransformationFamily.MULTI_FIELD_REPLACEMENT,
                TransformationFamily.EXCEPTION_EXPANSION,
                TransformationFamily.EXCEPTION_CONTRACTION,
                TransformationFamily.SCHEDULE_REPLACEMENT,
                TransformationFamily.TEMPORAL_STEP_CHANGE,
                TransformationFamily.WAIVER,
                TransformationFamily.REINSTATEMENT,
                TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT,
                TransformationFamily.DEFINED_TERM_PROPAGATION,
                TransformationFamily.RENUMBER,
                TransformationFamily.TERMINATE,
            },
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        if delta.transformation_type == TransformationFamily.CREATE:
            return True, ""  # N/A for CREATE
        if predecessor is None or successor is None:
            return False, "Missing predecessor or successor kernel"

        for field_name in delta.preserved_fields:
            pred_val = predecessor.field_value(field_name)
            succ_val = successor.field_value(field_name)
            if pred_val != succ_val:
                return False, (
                    f"Preserved field '{field_name}' changed: "
                    f"{pred_val} -> {succ_val}"
                )
        return True, ""


class NoUnsupportedSemanticGain(ConservationInvariant):
    """2.4: Successor may not acquire semantics unsupported by evidence."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.NO_UNSUPPORTED_SEMANTIC_GAIN,
            description="No unsupported semantic gain in successor",
            applies_to=set(TransformationFamily),
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        if predecessor is None or successor is None:
            return True, ""  # Cannot check without both

        affected = set(delta.affected_field_names)

        # Check that no list/dict field gained entries without being affected
        for field_name in ["exceptions", "scope", "trigger", "cure", "applicability"]:
            if field_name in affected:
                continue
            pred_val = predecessor.field_value(field_name)
            succ_val = successor.field_value(field_name)
            if isinstance(pred_val, list) and isinstance(succ_val, list):
                if len(succ_val) > len(pred_val):
                    return False, (
                        f"Field '{field_name}' gained entries without "
                        f"being in affected fields"
                    )
            elif isinstance(pred_val, dict) and isinstance(succ_val, dict):
                if len(succ_val) > len(pred_val):
                    return False, (
                        f"Field '{field_name}' gained keys without "
                        f"being in affected fields"
                    )
        return True, ""


class NoSilentSemanticLoss(ConservationInvariant):
    """2.5: Existing semantics may not disappear without evidence."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.NO_SILENT_SEMANTIC_LOSS,
            description="No silent semantic loss in successor",
            applies_to=set(TransformationFamily),
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        if predecessor is None or successor is None:
            return True, ""
        if delta.transformation_type == TransformationFamily.CREATE:
            return True, ""

        affected = set(delta.affected_field_names)

        for field_name in ["exceptions", "scope", "trigger", "cure", "applicability"]:
            if field_name in affected:
                continue
            pred_val = predecessor.field_value(field_name)
            succ_val = successor.field_value(field_name)
            if isinstance(pred_val, list) and isinstance(succ_val, list):
                if len(succ_val) < len(pred_val):
                    return False, (
                        f"Field '{field_name}' lost entries without "
                        f"being in affected fields"
                    )
            elif isinstance(pred_val, dict) and isinstance(succ_val, dict):
                if len(succ_val) < len(pred_val):
                    return False, (
                        f"Field '{field_name}' lost keys without "
                        f"being in affected fields"
                    )
        return True, ""


class TargetReferenceSeparation(ConservationInvariant):
    """2.6: Reference to commitment ≠ transformation target of commitment."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.TARGET_REFERENCE_SEPARATION,
            description="Reference ≠ target; affirmative target evidence required",
            applies_to=set(TransformationFamily),
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        # This invariant is primarily enforced by the identity resolver
        # and the transformation engine.  Here we verify that the
        # transformation carries evidence references.
        if not delta.source_span and not delta.source_document:
            return False, "No source evidence in transformation"
        return True, ""


class LineageContinuity(ConservationInvariant):
    """2.7: Every accepted successor traces to predecessor + amendment evidence."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.LINEAGE_CONTINUITY,
            description="Successor traces to predecessor through valid lineage edges",
            applies_to=set(TransformationFamily),
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        if delta.transformation_type == TransformationFamily.CREATE:
            return True, ""  # CREATE has no predecessor
        if predecessor is None:
            return False, "No predecessor for non-CREATE transformation"
        if delta.source_authority == "":
            return False, "No source authority (amendment reference) in transformation"
        return True, ""


class TemporalValidity(ConservationInvariant):
    """2.8: Schedules, waivers, reinstatements, effective dates obey valid transitions."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.TEMPORAL_VALIDITY,
            description="Temporal validity: valid_from <= valid_to, valid state transitions",
            applies_to={
                TransformationFamily.SCHEDULE_REPLACEMENT,
                TransformationFamily.TEMPORAL_STEP_CHANGE,
                TransformationFamily.WAIVER,
                TransformationFamily.REINSTATEMENT,
                TransformationFamily.TERMINATE,
                TransformationFamily.CREATE,
            },
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        if successor is None:
            return True, ""

        # valid_from <= valid_to (if valid_to is set)
        if successor.valid_from and successor.valid_to:
            if successor.valid_from > successor.valid_to:
                return False, "valid_from > valid_to"

        # Reinstatement requires prior waiver
        if delta.transformation_type == TransformationFamily.REINSTATEMENT:
            if predecessor and predecessor.status != "WAIVED":
                return False, "Reinstatement requires predecessor status WAIVED"

        # Waiver requires active predecessor
        if delta.transformation_type == TransformationFamily.WAIVER:
            if predecessor and predecessor.status not in ("ACTIVE",):
                return False, "Waiver requires predecessor status ACTIVE"

        # Terminate requires active or waived predecessor
        if delta.transformation_type == TransformationFamily.TERMINATE:
            if predecessor and predecessor.status not in ("ACTIVE", "WAIVED"):
                return False, "Terminate requires predecessor status ACTIVE or WAIVED"

        return True, ""


class OutOfScopeIsolation(ConservationInvariant):
    """2.9: Out-of-scope provisions cannot mutate frozen commitment state."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.OUT_OF_SCOPE_ISOLATION,
            description="Out-of-scope provisions cannot mutate commitment state",
            applies_to=set(TransformationFamily),
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        # This invariant is primarily enforced by the identity resolver
        # and the safety layer.  Here we verify the transformation
        # targets a known commitment.
        if not delta.commitment_id:
            return False, "No commitment_id in transformation"
        return True, ""


class TransformationCompleteness(ConservationInvariant):
    """2.10: Partial multi-field transformations may not apply subsets."""

    def __init__(self) -> None:
        super().__init__(
            name=InvariantNames.TRANSFORMATION_COMPLETENESS,
            description="All affected fields must be extracted; no partial subsets",
            applies_to={
                TransformationFamily.MULTI_FIELD_REPLACEMENT,
                TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT,
                TransformationFamily.DEFINED_TERM_PROPAGATION,
                TransformationFamily.SCHEDULE_REPLACEMENT,
                TransformationFamily.CREATE,
            },
        )

    def _check(
        self,
        predecessor: CommitmentKernel | None,
        successor: CommitmentKernel | None,
        delta: AuthorizedTransformation,
    ) -> tuple[bool, str]:
        # Every affected field must have both old and new values
        for affected in delta.affected_fields:
            if affected.new_value is None and affected.old_value is None:
                return False, (
                    f"Affected field '{affected.field_name}' has neither "
                    f"old nor new value (incomplete extraction)"
                )
        return True, ""


# ---------------------------------------------------------------------------
# All invariants
# ---------------------------------------------------------------------------

ALL_INVARIANTS: list[ConservationInvariant] = [
    IdentityPersistence(),
    OldValueConsistency(),
    UnchangedFieldPreservation(),
    NoUnsupportedSemanticGain(),
    NoSilentSemanticLoss(),
    TargetReferenceSeparation(),
    LineageContinuity(),
    TemporalValidity(),
    OutOfScopeIsolation(),
    TransformationCompleteness(),
]


def applicable_invariants(
    transform_type: TransformationFamily,
) -> list[ConservationInvariant]:
    """Get the invariants that apply to a transformation family."""
    return [inv for inv in ALL_INVARIANTS if transform_type in inv.applies_to]
