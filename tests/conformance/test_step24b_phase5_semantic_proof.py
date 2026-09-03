"""Step 24B Phase 5 conformance tests — Semantic Proof as Execution Precondition.

These tests enforce that:
1. ProofAssembler.assemble_pre_execution produces a
   SemanticTransformationProof from Δ + identity + validation.
2. The proof is COMPLETE when all structural fields are populated.
3. The proof is VALID when all conservation checks pass.
4. may_proceed_to_execution() is True only when COMPLETE + VALID +
   all conservation checks pass.
5. Violation: a proof with failed conservation is INVALID and may
   NOT proceed to execution.
6. Violation: a proof with INSUFFICIENT evidence is INCOMPLETE and
   may NOT proceed to execution.
7. Violation: a proof with unverified old-value consistency is
   INDETERMINATE and may NOT proceed to execution.
8. Designated real EDGAR case: Ameresco A1 Section 7.10(a).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from upsilon.models import (
    CommitmentKernel,
    ProofCompleteness,
    ProofValidity,
    SemanticTransformationProof,
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
from upsilon.commitments.identity import IdentityResolver, IdentityResolutionResult
from upsilon.evidence.evidence_extractor import instruction_to_evidence
from upsilon.transformations.authorized_change import (
    AuthorityContext,
    AuthorizedTransformationEngine,
)
from upsilon.transformations.apply import apply_transformation
from upsilon.conservation.validator import ConservationValidator, ValidationResult
from upsilon.proof.transformation_proof import ProofAssembler


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


def _setup_full_path():
    """Set up the full Phase 1-4 path and return all components."""
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
    assert result.authorized

    # Get identity result for proof assembly
    identity_result = resolver.resolve(
        section_ref=evidence.source_section_ref,
        alias_match=evidence.alias_match,
        text_match=evidence.text_match,
        predecessor_commitment_ids=list(store.get_all_current().keys()),
        canonical_key_hint=evidence.canonical_key_hint,
    )

    candidate = apply_transformation(predecessor, result.transformation)
    validator = ConservationValidator()
    validation = validator.validate(predecessor, candidate, result.transformation)

    return store, predecessor, result.transformation, identity_result, validation


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestProofAssembly:
    """Test ProofAssembler.assemble_pre_execution."""

    def test_assembly_produces_proof(self):
        """Positive: assembly produces a SemanticTransformationProof."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
            predecessor_version=0,
            successor_version=1,
        )

        assert isinstance(proof, SemanticTransformationProof)

    def test_proof_is_complete(self):
        """Positive: proof is COMPLETE when all structural fields populated."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.proof_completeness == ProofCompleteness.COMPLETE

    def test_proof_is_valid(self):
        """Positive: proof is VALID when all conservation checks pass."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.proof_validity == ProofValidity.VALID

    def test_proof_carries_identity_evidence(self):
        """Positive: proof carries target identity evidence."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.target_identity_evidence is not None
        assert proof.commitment_id == "financial_covenant.leverage_ratio"

    def test_proof_carries_conservation_checks(self):
        """Positive: proof carries conservation check results."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.conservation_checks is not None
        assert proof.conservation_checks.all_passed

    def test_proof_carries_transformation_fields(self):
        """Positive: proof carries affected fields and values."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.affected_fields == ["applicability"]
        assert "applicability" in proof.predecessor_values
        assert "applicability" in proof.successor_values

    def test_may_proceed_to_execution_true(self):
        """Positive: may_proceed_to_execution() is True for a valid proof."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.may_proceed_to_execution()

    def test_is_complete_and_valid_true(self):
        """Positive: is_complete_and_valid() is True for a valid proof."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.is_complete_and_valid()


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestProofViolations:
    """Test that proof violations prevent execution."""

    def test_failed_conservation_makes_proof_invalid(self):
        """Violation: failed conservation checks make proof INVALID,
        and may_proceed_to_execution() is False."""
        store, pred, delta, identity, validation = _setup_full_path()

        # Corrupt the validation to simulate a failed conservation check
        validation.passed = False
        validation.failed_invariants = ["unchanged_field_preservation"]

        assembler = ProofAssembler()
        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.proof_validity == ProofValidity.INVALID
        assert not proof.may_proceed_to_execution()

    def test_insufficient_evidence_makes_proof_incomplete(self):
        """Violation: INSUFFICIENT evidence makes proof INCOMPLETE,
        and may_proceed_to_execution() is False."""
        store, pred, delta, identity, validation = _setup_full_path()

        # Create an identity result with INSUFFICIENT evidence
        insufficient_identity = IdentityResolutionResult(
            identity=None,
            confidence=0.2,
            evidence_level="INSUFFICIENT",
            signals=[],
            fail_closed=True,
            failure_reason="Insufficient evidence",
        )

        assembler = ProofAssembler()
        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=insufficient_identity,
            validation=validation,
        )

        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE
        assert not proof.may_proceed_to_execution()

    def test_unverified_old_value_makes_proof_indeterminate(self):
        """Violation: unverified old-value consistency makes proof
        INDETERMINATE, and may_proceed_to_execution() is False."""
        store, pred, delta, identity, validation = _setup_full_path()

        # Mark old-value consistency as not verified
        delta.old_value_consistency_verified = False

        assembler = ProofAssembler()
        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.proof_validity == ProofValidity.INDETERMINATE
        assert not proof.may_proceed_to_execution()

    def test_weak_evidence_makes_proof_incomplete(self):
        """Violation: WEAK evidence makes proof INCOMPLETE."""
        store, pred, delta, identity, validation = _setup_full_path()

        # Create an identity result with WEAK evidence
        weak_identity = IdentityResolutionResult(
            identity=identity.identity,
            confidence=0.5,
            evidence_level="WEAK",
            signals=identity.signals,
        )

        assembler = ProofAssembler()
        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=weak_identity,
            validation=validation,
        )

        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE
        assert not proof.may_proceed_to_execution()


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1Proof:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_proof_complete_and_valid(self):
        """Positive: Ameresco A1 proof is COMPLETE + VALID.

        The proof is assembled from:
        - Δ (SCALAR_REPLACEMENT on applicability)
        - Identity (SUFFICIENT, via address map)
        - Conservation (all 8 invariants PASS)
        """
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
            predecessor_version=0,
            successor_version=1,
        )

        assert proof.proof_completeness == ProofCompleteness.COMPLETE
        assert proof.proof_validity == ProofValidity.VALID
        assert proof.may_proceed_to_execution()

    def test_ameresco_a1_proof_carries_correct_fields(self):
        """Positive: Ameresco A1 proof carries the correct transformation fields."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.commitment_id == "financial_covenant.leverage_ratio"
        assert proof.transformation_type == TransformationFamily.SCALAR_REPLACEMENT
        assert proof.affected_fields == ["applicability"]
        assert "threshold" in proof.preserved_fields
        assert "operator" in proof.preserved_fields

    def test_ameresco_a1_proof_evidence_sufficient(self):
        """Positive: Ameresco A1 proof has SUFFICIENT evidence status."""
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        assert proof.evidence_status.value == "SUFFICIENT"

    def test_ameresco_a1_proof_precondition_enforced(self):
        """Positive: Ameresco A1 proof enforces the execution precondition.

        may_proceed_to_execution() is the gate: execution is permitted
        only when the proof is COMPLETE + VALID + all conservation
        checks pass.
        """
        store, pred, delta, identity, validation = _setup_full_path()
        assembler = ProofAssembler()

        proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )

        # The precondition is satisfied for the Ameresco A1 case
        assert proof.may_proceed_to_execution()

        # If we corrupt the conservation, the precondition fails
        validation.passed = False
        proof_corrupted = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity,
            validation=validation,
        )
        assert not proof_corrupted.may_proceed_to_execution()
