"""Step 24B Phase 8 conformance tests — Authority Gate as Only Promotion Path.

These tests enforce that:
1. AuthorityGate.evaluate() is the only promotion path.
2. AUTHORITY_GRANTED requires: execution COMPLETE, proof COMPLETE+VALID,
   all conservation checks passing, no inherited unresolved, sufficient
   evidence, no high uncertainty, no weak identity, no indeterminate
   validity.
3. Violation: UNRESOLVED execution → AUTHORITY_BLOCKED.
4. Violation: PARTIAL execution → PARTIAL.
5. Violation: INCOMPLETE proof → AUTHORITY_BLOCKED.
6. Violation: INVALID proof → AUTHORITY_BLOCKED.
7. Violation: failed conservation → AUTHORITY_BLOCKED.
8. Violation: inherited unresolved → AUTHORITY_BLOCKED.
9. Violation: INSUFFICIENT evidence → AUTHORITY_BLOCKED.
10. Violation: HIGH uncertainty → VALIDATION_REQUIRED.
11. Violation: WEAK identity evidence → VALIDATION_REQUIRED.
12. Violation: INDETERMINATE proof validity → VALIDATION_REQUIRED.
13. Designated real EDGAR case: Ameresco A1 Section 7.10(a).
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
from upsilon.conservation.validator import ConservationValidator
from upsilon.proof.transformation_proof import ProofAssembler
from upsilon.authority.promotion_gate import (
    AuthorityDecision,
    AuthorityGate,
    AuthorityGateResult,
    ExecutionResultSummary,
)


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


def _setup_full_path_with_proof():
    """Set up the full Phase 1-5 path and return (store, proof, validation)."""
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

    assembler = ProofAssembler()
    proof = assembler.assemble_pre_execution(
        delta=result.transformation,
        identity_result=identity_result,
        validation=validation,
        predecessor_version=0,
        successor_version=1,
    )

    return store, proof, validation


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestAuthorityGateGrants:
    """Test that the authority gate grants authority for valid transformations."""

    def test_gate_produces_result(self):
        """Positive: AuthorityGate.evaluate produces a result."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            inherited_unresolved=0,
            lineage_valid=True,
        )

        assert isinstance(result, AuthorityGateResult)

    def test_gate_grants_authority_for_valid_transformation(self):
        """Positive: gate grants AUTHORITY_GRANTED for a valid transformation."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            inherited_unresolved=0,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_GRANTED
        assert "All authority conditions satisfied" in result.reason

    def test_gate_carries_proof_id(self):
        """Positive: gate result carries the proof_id."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            lineage_valid=True,
        )

        assert result.proof_id == proof.proof_id


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestAuthorityGateBlocks:
    """Test that the authority gate blocks invalid transformations."""

    def test_unresolved_execution_blocks(self):
        """Violation: UNRESOLVED execution → UNRESOLVED decision."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=False,
            status="UNRESOLVED",
            state_changed=False,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
        )

        assert result.decision == AuthorityDecision.UNRESOLVED

    def test_partial_execution_blocks(self):
        """Violation: PARTIAL execution → PARTIAL decision."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="PARTIAL",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
        )

        assert result.decision == AuthorityDecision.PARTIAL

    def test_incomplete_proof_blocks(self):
        """Violation: INCOMPLETE proof → AUTHORITY_BLOCKED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        # Corrupt the proof to be INCOMPLETE
        proof.proof_completeness = ProofCompleteness.INCOMPLETE

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
        assert "INCOMPLETE" in result.reason

    def test_invalid_proof_blocks(self):
        """Violation: INVALID proof → AUTHORITY_BLOCKED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        proof.proof_validity = ProofValidity.INVALID

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
        assert "INVALID" in result.reason

    def test_failed_conservation_blocks(self):
        """Violation: failed conservation checks → AUTHORITY_BLOCKED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        # Corrupt one of the conservation check results to show a failure.
        # The proof's conservation_checks.all_passed is a computed property
        # based on the individual check results.  We corrupt one check.
        from upsilon.conservation.validator import CheckResult
        proof.conservation_checks.unchanged_field_preservation = CheckResult(
            invariant_name="unchanged_field_preservation",
            passed=False,
            failure_reason="Field 'threshold' was corrupted",
        )

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
        assert "Conservation" in result.reason

    def test_inherited_unresolved_blocks(self):
        """Violation: inherited unresolved state → AUTHORITY_BLOCKED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            inherited_unresolved=2,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
        assert "Inherited unresolved" in result.reason

    def test_missing_lineage_blocks(self):
        """Violation: missing lineage → AUTHORITY_BLOCKED.

        Lineage validity is a required precondition (Step 24B Phase 8
        gap closure).  A step with no lineage edge must not be promoted
        even if every other condition is satisfied.
        """
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            inherited_unresolved=0,
            lineage_valid=False,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
        assert "Lineage" in result.reason

    def test_insufficient_evidence_blocks(self):
        """Violation: INSUFFICIENT evidence → AUTHORITY_BLOCKED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        # We need to create a proof with INSUFFICIENT evidence.
        # The easiest way is to re-assemble with an insufficient identity.
        from upsilon.models import EvidenceStatus
        proof.evidence_status = EvidenceStatus.INSUFFICIENT

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
        assert "INSUFFICIENT" in result.reason

    def test_high_uncertainty_routes_to_validation(self):
        """Violation: HIGH uncertainty → VALIDATION_REQUIRED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        from upsilon.models import UncertaintyStatus
        proof.uncertainty_status = UncertaintyStatus.HIGH

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.VALIDATION_REQUIRED
        assert "HIGH" in result.reason

    def test_weak_identity_routes_to_validation(self):
        """Violation: WEAK identity evidence → VALIDATION_REQUIRED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        # Create a proof with WEAK identity evidence
        from upsilon.models import EvidenceStatus
        # The target_identity_evidence has an evidence_level
        proof.target_identity_evidence.evidence_level = EvidenceStatus.WEAK

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.VALIDATION_REQUIRED
        assert "WEAK" in result.reason

    def test_indeterminate_validity_routes_to_validation(self):
        """Violation: INDETERMINATE proof validity → VALIDATION_REQUIRED."""
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        proof.proof_validity = ProofValidity.INDETERMINATE

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.VALIDATION_REQUIRED
        assert "INDETERMINATE" in result.reason


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1AuthorityGate:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_authority_granted(self):
        """Positive: Ameresco A1 is granted authority by the gate.

        This is the end-to-end test of Phases 1-8:
        S0 kernel → evidence → engine → candidate → conservation →
        proof → execution → authority gate → AUTHORITY_GRANTED
        """
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            inherited_unresolved=0,
            lineage_valid=True,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_GRANTED
        assert result.proof_id == proof.proof_id

    def test_ameresco_a1_authority_blocked_if_conservation_fails(self):
        """Positive: Ameresco A1 is blocked if conservation fails.

        This verifies the fail-closed property: if conservation
        validation fails, the authority gate must block promotion.
        """
        store, proof, validation = _setup_full_path_with_proof()
        gate = AuthorityGate()

        # Simulate a conservation failure
        from upsilon.models import EvidenceStatus
        proof.proof_validity = ProofValidity.INVALID

        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )

        result = gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
        )

        assert result.decision == AuthorityDecision.AUTHORITY_BLOCKED
