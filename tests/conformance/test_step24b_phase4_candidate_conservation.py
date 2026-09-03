"""Step 24B Phase 4 conformance tests — Candidate Successor + Conservation.

These tests enforce that:
1. apply_transformation produces a candidate successor from
   predecessor + Δ.
2. Unchanged fields are preserved (C_t[f] == C_{t-1}[f] for all f
   not in affected(Delta_t)).
3. Only the affected field is modified.
4. Identity persists (ID(C_t) == ID(C_{t-1}) for SCALAR_REPLACEMENT).
5. ConservationValidator validates all applicable invariants.
6. All invariants PASS for a correct transformation.
7. Violation: a corrupted successor (changed preserved field) fails
   unchanged_field_preservation.
8. Violation: a successor with changed identity fails
   identity_persistence.
9. Designated real EDGAR case: Ameresco A1 Section 7.10(a).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from upsilon.models import (
    AuthorizedTransformation,
    AffectedField,
    CommitmentKernel,
    TransformationFamily,
)
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    DomainEffect,
    InstructionProvenance,
    InstructionType,
)
from upsilon.commitments.kernel_bridge import establish_authoritative_kernel
from upsilon.commitments.identity import IdentityResolver
from upsilon.evidence.evidence_extractor import instruction_to_evidence
from upsilon.transformations.authorized_change import (
    AuthorityContext,
    AuthorizedTransformationEngine,
)
from upsilon.transformations.apply import apply_transformation
from upsilon.conservation.validator import ConservationValidator, ValidationResult


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


_AMERESCO_AGREEMENT = "ameresco-fifth-ar-2022"


def _ameresco_original_state() -> dict[str, CommitmentState]:
    return {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="core_leverage_ratio",
            operator="<=",
            threshold=3.50,
            unit="ratio",
            frequency="quarterly",
            applicability={
                "step_down_schedule": [
                    {"period_end": "2022-03-31", "threshold": 4.50},
                    {"period_end": "2022-06-30", "threshold": 4.25},
                    {"period_end": "2022-09-30", "threshold": 4.00},
                    {"period_end": "2022-12-31", "threshold": 4.00},
                ],
                "steady_state_threshold": 3.50,
            },
        ),
        "financial_covenant.debt_service_coverage": CommitmentState(
            canonical_key="financial_covenant.debt_service_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="debt_service_coverage_ratio",
            operator=">=",
            threshold=1.50,
            unit="ratio",
            frequency="quarterly",
        ),
    }


_SECTION_REFS = {
    "financial_covenant.leverage_ratio": "Section 7.10(a)",
    "financial_covenant.debt_service_coverage": "Section 7.10(b)",
}


def _ameresco_a1_instruction() -> AmendmentInstruction:
    return AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_key="financial_covenant.leverage_ratio",
        target_section_ref="Section 7.10(a)",
        field="applicability",
        old_value=_ameresco_original_state()[
            "financial_covenant.leverage_ratio"
        ].applicability,
        new_value={
            "step_down_schedule": [
                {"period_end": "2023-06-30", "threshold": 4.00},
                {"period_end": "2023-09-30", "threshold": 4.25},
            ],
            "steady_state_threshold": 3.50,
        },
        effective_start=datetime(2023, 8, 24),
        source_text=(
            "Section 7.10 of the Credit Agreement is hereby amended "
            "by deleting paragraph (a) in its entirety and replacing "
            "it with the following: (a) Total Funded Debt to EBITDA "
            "Ratio. The Loan Parties shall not permit the Core "
            "Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on June 30, 2023 to exceed 4.00 to 1.00, "
            "(ii) ending on September 30, 2023 to exceed 4.25 to "
            "1.00, and (ii) for any quarter ending thereafter, to "
            "exceed 3.50 to 1.00."
        ),
        domain_effect=DomainEffect.COVENANT_THRESHOLD_CHANGE,
        provenance=InstructionProvenance.MANUAL_FALLBACK,
        citation_document="Amendment No. 3, Aug 24, 2023",
        citation_section="Section 7.10(a)",
    )


def _setup_and_authorize():
    """Set up the full Phase 1-3 path and return (predecessor, delta, candidate)."""
    original = _ameresco_original_state()
    store, address_map, _ = establish_authoritative_kernel(
        original, _AMERESCO_AGREEMENT, _SECTION_REFS
    )
    ins = _ameresco_a1_instruction()
    evidence = instruction_to_evidence(
        ins, citation_document="Amendment No. 3, Aug 24, 2023"
    )
    predecessor = store.get_predecessor(
        "financial_covenant.leverage_ratio"
    )
    resolver = IdentityResolver(address_map)
    engine = AuthorizedTransformationEngine(resolver)
    authority = AuthorityContext(
        predecessor_kernel=predecessor,
        predecessor_commitment_ids=list(store.get_all_current().keys()),
        amendment_number=1,
        chain_position=1,
    )
    result = engine.authorize(evidence, authority)
    assert result.authorized, f"Engine rejected: {result.rejection_reason}"
    return store, predecessor, result.transformation


# ---------------------------------------------------------------------------
# Positive-path tests: apply_transformation
# ---------------------------------------------------------------------------


class TestApplyTransformation:
    """Test that apply_transformation produces a correct candidate successor."""

    def test_apply_produces_kernel(self):
        """Positive: apply_transformation produces a CommitmentKernel."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert isinstance(candidate, CommitmentKernel)

    def test_apply_preserves_threshold(self):
        """Positive: threshold (3.50) is preserved from predecessor."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert candidate.threshold == predecessor.threshold
        assert candidate.threshold == 3.50

    def test_apply_preserves_operator(self):
        """Positive: operator (<=) is preserved from predecessor."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert candidate.operator == predecessor.operator
        assert candidate.operator == "<="

    def test_apply_preserves_unit(self):
        """Positive: unit (ratio) is preserved from predecessor."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert candidate.unit == predecessor.unit
        assert candidate.unit == "ratio"

    def test_apply_preserves_frequency(self):
        """Positive: frequency (quarterly) is preserved from predecessor."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert candidate.frequency == predecessor.frequency
        assert candidate.frequency == "quarterly"

    def test_apply_preserves_party(self):
        """Positive: party (['borrower']) is preserved from predecessor."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert candidate.party == predecessor.party
        assert candidate.party == ["borrower"]

    def test_apply_modifies_only_affected_field(self):
        """Positive: only the affected field (applicability) is modified."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # applicability should be the new value
        assert candidate.applicability != predecessor.applicability
        assert len(candidate.applicability["step_down_schedule"]) == 2
        assert candidate.applicability["steady_state_threshold"] == 3.50

    def test_apply_preserves_identity(self):
        """Positive: identity persists (ID(C_t) == ID(C_{t-1}))."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        assert candidate.commitment_id == predecessor.commitment_id
        assert candidate.agreement_identity == predecessor.agreement_identity


# ---------------------------------------------------------------------------
# Positive-path tests: ConservationValidator
# ---------------------------------------------------------------------------


class TestConservationValidation:
    """Test that ConservationValidator validates all applicable invariants."""

    def test_validation_produces_result(self):
        """Positive: validation produces a ValidationResult."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert isinstance(result, ValidationResult)

    def test_validation_passes_for_correct_transformation(self):
        """Positive: all invariants PASS for a correct transformation."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert result.passed
        assert result.failed_invariants == []

    def test_identity_persistence_passes(self):
        """Positive: identity_persistence invariant passes."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert result.checks.identity_persistence is not None
        assert result.checks.identity_persistence.passed

    def test_unchanged_field_preservation_passes(self):
        """Positive: unchanged_field_preservation invariant passes."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert result.checks.unchanged_field_preservation is not None
        assert result.checks.unchanged_field_preservation.passed

    def test_old_value_consistency_passes(self):
        """Positive: old_value_consistency invariant passes."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert result.checks.old_value_consistency is not None
        assert result.checks.old_value_consistency.passed

    def test_lineage_continuity_passes(self):
        """Positive: lineage_continuity invariant passes."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert result.checks.lineage_continuity is not None
        assert result.checks.lineage_continuity.passed

    def test_all_eight_invariants_run(self):
        """Positive: all 8 applicable invariants for SCALAR_REPLACEMENT run."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        # SCALAR_REPLACEMENT has 8 applicable invariants
        # (transformation_completeness is not applicable to SCALAR_REPLACEMENT)
        checks_run = result.validator_results.checks
        assert len(checks_run) == 8


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestConservationViolations:
    """Test that conservation violations are detected."""

    def test_corrupted_preserved_field_fails_unchanged_field_preservation(self):
        """Violation: a successor with a corrupted preserved field fails
        unchanged_field_preservation."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # Corrupt a preserved field (threshold should be 3.50, change to 99.99)
        candidate.threshold = 99.99

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert not result.passed
        assert "unchanged_field_preservation" in result.failed_invariants

    def test_corrupted_identity_fails_identity_persistence(self):
        """Violation: a successor with changed identity fails
        identity_persistence."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # Corrupt the identity (change commitment_id)
        from upsilon.models import CommitmentIdentity, AddressBinding
        candidate.identity = CommitmentIdentity(
            commitment_id="wrong_commitment",
            agreement_identity=predecessor.agreement_identity,
            canonical_key="wrong_commitment",
            local_address=AddressBinding(
                section_ref="Section 1",
                established_at_version="S0",
            ),
        )

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert not result.passed
        assert "identity_persistence" in result.failed_invariants

    def test_unverified_old_value_fails_old_value_consistency(self):
        """Violation: a Δ with unverified old-value consistency fails
        old_value_consistency."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # Mark old-value consistency as not verified
        delta.old_value_consistency_verified = False

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert not result.passed
        assert "old_value_consistency" in result.failed_invariants

    def test_old_value_mismatch_fails_even_with_engine_flag(self):
        """Violation: the invariant independently compares values.

        Even if the engine's ``old_value_consistency_verified`` flag
        is True, the invariant must independently detect a mismatch
        between the declared old_value and the predecessor's actual
        value.  This proves the invariant does NOT trust the engine
        flag alone.
        """
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # Corrupt the old_value in the affected field — set it to
        # a value that does NOT match the predecessor.
        delta.affected_fields[0].old_value = {"steady_state_threshold": 99.99}
        # Leave the engine flag set to True (the engine "verified" it)
        delta.old_value_consistency_verified = True

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        # The invariant must independently detect the mismatch
        assert not result.passed
        assert "old_value_consistency" in result.failed_invariants

    def test_missing_source_authority_fails_lineage_continuity(self):
        """Violation: a Δ with no source_authority fails lineage_continuity."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # Remove source authority
        delta.source_authority = ""

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert not result.passed
        assert "lineage_continuity" in result.failed_invariants


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1CandidateConservation:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_candidate_preserves_all_unaffected_fields(self):
        """Positive: Ameresco A1 candidate preserves all unaffected fields.

        The A1 amendment changes only the applicability (step-down
        schedule).  All other semantic fields must be preserved from
        the S0 predecessor.
        """
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # Affected field: applicability (changed)
        assert candidate.applicability != predecessor.applicability

        # All preserved fields must be equal
        for field_name in delta.preserved_fields:
            pred_val = predecessor.field_value(field_name)
            succ_val = candidate.field_value(field_name)
            assert pred_val == succ_val, (
                f"Preserved field '{field_name}' changed: "
                f"{pred_val} -> {succ_val}"
            )

    def test_ameresco_a1_conservation_all_pass(self):
        """Positive: Ameresco A1 passes all conservation invariants."""
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        validator = ConservationValidator()
        result = validator.validate(predecessor, candidate, delta)

        assert result.passed
        assert result.failed_invariants == []

    def test_ameresco_a1_threshold_3_50_preserved(self):
        """Positive: the steady-state threshold (3.50) is preserved.

        The A1 amendment changes the step-down schedule but the
        steady_state_threshold remains 3.50 in both old and new
        applicability values.
        """
        store, predecessor, delta = _setup_and_authorize()
        candidate = apply_transformation(predecessor, delta)

        # The threshold field (separate from applicability) is preserved
        assert candidate.threshold == 3.50
        # The steady_state_threshold within applicability is also 3.50
        assert candidate.applicability["steady_state_threshold"] == 3.50
