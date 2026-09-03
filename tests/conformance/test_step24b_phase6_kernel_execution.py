"""Step 24B Phase 6 conformance tests — Kernel Execution Path.

These tests enforce that:
1. KernelStore.advance() commits the candidate successor as a new
   immutable version.
2. The new version has the correct version_number, proof_id, and
   predecessor_version.
3. The current authoritative state is updated to the new version.
4. Unaffected commitments remain at their previous version.
5. Violation: advance() without proof_id raises.
6. Violation: advance() for a non-existent commitment raises.
7. Violation: advance() when proof says may NOT proceed should be
   blocked by the caller (the spine must check the proof first).
8. Designated real EDGAR case: Ameresco A1 Section 7.10(a).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from upsilon.models import (
    CommitmentKernel,
    KernelVersion,
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
from upsilon.commitments.identity import IdentityResolver
from upsilon.commitments.kernel import KernelStore
from upsilon.evidence.evidence_extractor import instruction_to_evidence
from upsilon.transformations.authorized_change import (
    AuthorityContext,
    AuthorizedTransformationEngine,
)
from upsilon.transformations.apply import apply_transformation
from upsilon.conservation.validator import ConservationValidator
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


def _setup_and_execute():
    """Set up the full Phase 1-5 path, execute via advance, return all."""
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

    assert proof.may_proceed_to_execution()

    # Phase 6: Execute via KernelStore.advance
    new_version = store.advance(
        "financial_covenant.leverage_ratio",
        candidate,
        proof_id=proof.proof_id,
    )

    return store, predecessor, candidate, proof, new_version


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestKernelExecution:
    """Test KernelStore.advance as the execution step."""

    def test_advance_produces_kernel_version(self):
        """Positive: advance produces a KernelVersion."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        assert isinstance(new_version, KernelVersion)

    def test_advance_produces_version_1(self):
        """Positive: advance produces version 1 (after origin v0)."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        assert new_version.version_number == 1

    def test_advance_carries_proof_id(self):
        """Positive: the new version carries the proof_id."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        assert new_version.produced_by_proof_id == proof.proof_id

    def test_advance_carries_predecessor_version(self):
        """Positive: the new version carries predecessor_version=0."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        assert new_version.predecessor_version == 0

    def test_current_authoritative_state_updated(self):
        """Positive: the current authoritative state is the candidate."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        current = store.get_predecessor("financial_covenant.leverage_ratio")
        # The current state should be the candidate (new applicability)
        assert current.applicability != pred.applicability
        assert len(current.applicability["step_down_schedule"]) == 2
        # Preserved fields should still be the same
        assert current.threshold == pred.threshold
        assert current.operator == pred.operator

    def test_version_history_shows_two_versions(self):
        """Positive: version history shows v0 (origin) and v1 (proof)."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        history = store.get_version_history("financial_covenant.leverage_ratio")
        assert len(history) == 2
        assert history[0].version_number == 0
        assert history[0].produced_by_proof_id == "ORIGIN"
        assert history[1].version_number == 1
        assert history[1].produced_by_proof_id == proof.proof_id

    def test_unaffected_commitment_remains_at_v0(self):
        """Positive: debt_service_coverage remains at version 0."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        dsc_history = store.get_version_history(
            "financial_covenant.debt_service_coverage"
        )
        assert len(dsc_history) == 1
        assert dsc_history[0].version_number == 0

    def test_executed_state_preserves_unaffected_fields(self):
        """Positive: the executed state preserves all unaffected fields."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        current = store.get_predecessor("financial_covenant.leverage_ratio")
        # All preserved fields must match predecessor
        assert current.threshold == pred.threshold
        assert current.operator == pred.operator
        assert current.unit == pred.unit
        assert current.frequency == pred.frequency
        assert current.party == pred.party
        assert current.action == pred.action
        assert current.subject == pred.subject


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestKernelExecutionViolations:
    """Test that kernel execution violations are detected."""

    def test_advance_without_proof_id_raises(self):
        """Violation: advance without proof_id raises ValueError."""
        original = _ameresco_original_state()
        store, address_map, _ = establish_authoritative_kernel(
            original, _AMERESCO_AGREEMENT, _SECTION_REFS
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )

        # Create a candidate without going through the proof path
        from upsilon.models import CommitmentIdentity, AddressBinding
        identity = CommitmentIdentity(
            commitment_id="financial_covenant.leverage_ratio",
            agreement_identity=_AMERESCO_AGREEMENT,
            canonical_key="financial_covenant.leverage_ratio",
            local_address=AddressBinding(
                section_ref="Section 7.10(a)",
                established_at_version="S0",
            ),
        )
        candidate = CommitmentKernel(identity=identity, threshold=3.50)

        with pytest.raises((ValueError, TypeError)):
            store.advance(
                "financial_covenant.leverage_ratio",
                candidate,
                proof_id=None,
            )

    def test_advance_nonexistent_commitment_raises(self):
        """Violation: advance for non-existent commitment raises."""
        store = KernelStore(agreement_identity=_AMERESCO_AGREEMENT)

        from upsilon.models import CommitmentIdentity, AddressBinding
        identity = CommitmentIdentity(
            commitment_id="nonexistent",
            agreement_identity=_AMERESCO_AGREEMENT,
            canonical_key="nonexistent",
            local_address=AddressBinding(
                section_ref="Section 1",
                established_at_version="S0",
            ),
        )
        candidate = CommitmentKernel(identity=identity)

        with pytest.raises(ValueError, match="not in kernel store"):
            store.advance("nonexistent", candidate, proof_id="PRF-test")

    def test_stale_predecessor_version_raises(self):
        """Violation: advance with stale predecessor version raises.

        If the candidate was computed against predecessor version 0
        but the current authoritative version is 1, the advance must
        fail closed.  This prevents stale-version execution.
        """
        original = _ameresco_original_state()
        store, address_map, _ = establish_authoritative_kernel(
            original, _AMERESCO_AGREEMENT, _SECTION_REFS
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )

        # First advance to version 1
        from upsilon.models import CommitmentIdentity, AddressBinding
        identity = CommitmentIdentity(
            commitment_id="financial_covenant.leverage_ratio",
            agreement_identity=_AMERESCO_AGREEMENT,
            canonical_key="financial_covenant.leverage_ratio",
            local_address=AddressBinding(
                section_ref="Section 7.10(a)",
                established_at_version="S0",
            ),
        )
        candidate_v1 = CommitmentKernel(identity=identity, threshold=3.50)
        store.advance(
            "financial_covenant.leverage_ratio",
            candidate_v1,
            proof_id="PRF-first",
        )

        # Now try to advance with expected_predecessor_version=0
        # (stale — current is version 1)
        candidate_v2 = CommitmentKernel(identity=identity, threshold=3.25)
        with pytest.raises(ValueError, match="Predecessor version mismatch"):
            store.advance(
                "financial_covenant.leverage_ratio",
                candidate_v2,
                proof_id="PRF-stale",
                expected_predecessor_version=0,
            )

    def test_rollback_restores_predecessor(self):
        """Positive: rollback restores the predecessor as current.

        After advance + rollback, the authoritative current state
        must be the predecessor, and the version history must not
        contain the rolled-back version.
        """
        original = _ameresco_original_state()
        store, address_map, _ = establish_authoritative_kernel(
            original, _AMERESCO_AGREEMENT, _SECTION_REFS
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        pred_threshold = predecessor.threshold

        from upsilon.models import CommitmentIdentity, AddressBinding
        identity = CommitmentIdentity(
            commitment_id="financial_covenant.leverage_ratio",
            agreement_identity=_AMERESCO_AGREEMENT,
            canonical_key="financial_covenant.leverage_ratio",
            local_address=AddressBinding(
                section_ref="Section 7.10(a)",
                established_at_version="S0",
            ),
        )
        candidate = CommitmentKernel(identity=identity, threshold=99.99)
        store.advance(
            "financial_covenant.leverage_ratio",
            candidate,
            proof_id="PRF-test",
        )

        # Verify the candidate is current
        current = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        assert current.threshold == 99.99

        # Roll back
        store.rollback(
            "financial_covenant.leverage_ratio", predecessor,
        )

        # The authoritative current state must be the predecessor
        current = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        assert current.threshold == pred_threshold
        assert current.threshold != 99.99

        # Version history must not contain the rolled-back version
        history = store.get_version_history(
            "financial_covenant.leverage_ratio"
        )
        assert len(history) == 1
        assert history[0].version_number == 0

    def test_execution_failure_leaves_state_unchanged(self):
        """Violation: if advance raises, the state must be unchanged.

        Execution atomicity: if KernelStore.advance fails (e.g.,
        stale predecessor version), the authoritative current state
        must remain the predecessor.  No partial mutation.
        """
        original = _ameresco_original_state()
        store, address_map, _ = establish_authoritative_kernel(
            original, _AMERESCO_AGREEMENT, _SECTION_REFS
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        pred_applicability = predecessor.applicability

        from upsilon.models import CommitmentIdentity, AddressBinding
        identity = CommitmentIdentity(
            commitment_id="financial_covenant.leverage_ratio",
            agreement_identity=_AMERESCO_AGREEMENT,
            canonical_key="financial_covenant.leverage_ratio",
            local_address=AddressBinding(
                section_ref="Section 7.10(a)",
                established_at_version="S0",
            ),
        )
        candidate = CommitmentKernel(
            identity=identity, threshold=99.99,
            applicability={"steady_state_threshold": 99.99},
        )

        # Attempt advance with a stale predecessor version — must raise
        with pytest.raises(ValueError, match="Predecessor version mismatch"):
            store.advance(
                "financial_covenant.leverage_ratio",
                candidate,
                proof_id="PRF-stale",
                expected_predecessor_version=99,  # stale
            )

        # The state must be unchanged
        current = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        assert current.threshold == predecessor.threshold
        assert current.applicability == pred_applicability

        # Version history must still have only the origin version
        history = store.get_version_history(
            "financial_covenant.leverage_ratio"
        )
        assert len(history) == 1
        assert history[0].version_number == 0


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1KernelExecution:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_full_execution(self):
        """Positive: Ameresco A1 executes through the full Phase 1-6 path.

        This is the end-to-end test:
        S0 kernel → evidence → engine → candidate → conservation →
        proof → advance → version 1
        """
        store, pred, cand, proof, new_version = _setup_and_execute()

        # Version 1 created with proof
        assert new_version.version_number == 1
        assert new_version.produced_by_proof_id == proof.proof_id
        assert new_version.predecessor_version == 0

        # Current state is the candidate
        current = store.get_predecessor("financial_covenant.leverage_ratio")
        assert current.threshold == 3.50
        assert len(current.applicability["step_down_schedule"]) == 2
        assert current.applicability["steady_state_threshold"] == 3.50

    def test_ameresco_a1_threshold_preserved_after_execution(self):
        """Positive: threshold=3.50 is preserved after execution."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        current = store.get_predecessor("financial_covenant.leverage_ratio")
        assert current.threshold == 3.50
        assert current.operator == "<="
        assert current.unit == "ratio"

    def test_ameresco_a1_dsc_unaffected_after_execution(self):
        """Positive: debt_service_coverage is unaffected by A1 execution."""
        store, pred, cand, proof, new_version = _setup_and_execute()

        dsc = store.get_predecessor("financial_covenant.debt_service_coverage")
        assert dsc.threshold == 1.50
        assert dsc.operator == ">="
        dsc_history = store.get_version_history(
            "financial_covenant.debt_service_coverage"
        )
        assert len(dsc_history) == 1


# ---------------------------------------------------------------------------
# Phase 5: Staging / promotion separation
# ---------------------------------------------------------------------------


class TestStagingPromotionSeparation:
    """Phase 5: provisional execution must be separable from authority
    promotion.

    stage() stages a successor WITHOUT changing authoritative current.
    promote() is the ONLY mechanism that changes authoritative current.
    discard() removes a staged successor without promoting it.
    """

    def test_stage_does_not_change_authoritative_current(self):
        """stage() places the successor in a staging area but
        authoritative _current remains the predecessor."""
        store, pred, cand, proof, _ = _setup_and_execute()
        # Reset: re-establish predecessor as current
        store.rollback("financial_covenant.leverage_ratio", pred)

        # Stage the candidate
        staged_version = store.stage(
            "financial_covenant.leverage_ratio", cand, proof.proof_id,
        )
        assert staged_version.version_number == 1

        # Authoritative current must still be the predecessor
        current = store.get_predecessor("financial_covenant.leverage_ratio")
        assert current.threshold == 3.50
        assert len(current.applicability["step_down_schedule"]) == 4

        # The staged successor is accessible via get_staged
        staged = store.get_staged("financial_covenant.leverage_ratio")
        assert staged is not None
        assert len(staged.applicability["step_down_schedule"]) == 2

    def test_promote_changes_authoritative_current(self):
        """promote() moves the staged successor to authoritative
        current."""
        store, pred, cand, proof, _ = _setup_and_execute()
        store.rollback("financial_covenant.leverage_ratio", pred)

        store.stage("financial_covenant.leverage_ratio", cand, proof.proof_id)
        version = store.promote("financial_covenant.leverage_ratio")

        assert version is not None
        assert version.version_number == 1

        # Authoritative current is now the successor
        current = store.get_predecessor("financial_covenant.leverage_ratio")
        assert len(current.applicability["step_down_schedule"]) == 2

        # Staging area is empty
        assert store.get_staged("financial_covenant.leverage_ratio") is None

    def test_discard_keeps_predecessor(self):
        """discard() removes the staged successor without changing
        authoritative current."""
        store, pred, cand, proof, _ = _setup_and_execute()
        store.rollback("financial_covenant.leverage_ratio", pred)

        store.stage("financial_covenant.leverage_ratio", cand, proof.proof_id)
        store.discard("financial_covenant.leverage_ratio")

        # Authoritative current is still the predecessor
        current = store.get_predecessor("financial_covenant.leverage_ratio")
        assert current.threshold == 3.50
        assert len(current.applicability["step_down_schedule"]) == 4

        # Staging area is empty
        assert store.get_staged("financial_covenant.leverage_ratio") is None

        # Version history has only the origin
        history = store.get_version_history("financial_covenant.leverage_ratio")
        assert len(history) == 1
        assert history[0].version_number == 0

    def test_stale_version_stage_fails_closed(self):
        """stage() with a stale expected_predecessor_version fails."""
        store, pred, cand, proof, _ = _setup_and_execute()
        store.rollback("financial_covenant.leverage_ratio", pred)

        # Expected version 99 but actual is 0
        with pytest.raises(ValueError, match="Predecessor version mismatch"):
            store.stage(
                "financial_covenant.leverage_ratio",
                cand,
                proof.proof_id,
                expected_predecessor_version=99,
            )


# ---------------------------------------------------------------------------
# Phase 6: Proof lifecycle
# ---------------------------------------------------------------------------


class TestProofLifecycle:
    """Phase 6: proof lifecycle must be completed after execution and
    lineage.

    The proof must:
    1. Gate execution (pre-execution precondition).
    2. Be updated after execution with execution_result and
       lineage_reference.
    3. The completed proof must be used in authority evaluation.
    """

    def test_update_post_execution_attaches_execution_and_lineage(self):
        """update_post_execution attaches execution_result and
        lineage_reference to the proof."""
        from upsilon.proof.transformation_proof import ProofAssembler
        from upsilon.authority.promotion_gate import ExecutionResultSummary
        from upsilon.conservation.validator import ValidationResult
        from upsilon.models import (
            ConservationChecks,
            CheckResult,
            CommitmentIdentity,
            AddressBinding,
            IdentityProvenance,
            AuthorizedTransformation,
            AffectedField,
            ValidatorResults,
        )
        from upsilon.commitments.identity import IdentityResolutionResult

        store, pred, cand, proof, _ = _setup_and_execute()

        # Create a minimal identity result for the proof assembler
        identity_result = IdentityResolutionResult(
            identity=CommitmentIdentity(
                commitment_id="financial_covenant.leverage_ratio",
                agreement_identity="test",
                canonical_key="financial_covenant.leverage_ratio",
                local_address=AddressBinding(
                    section_ref="Section 7.10(a)",
                    established_at_version="S0",
                ),
                provenance=IdentityProvenance.S0_ORIGIN,
                confidence=0.9,
            ),
            confidence=0.9,
            evidence_level="SUFFICIENT",
            signals=["address_map"],
        )

        assembler = ProofAssembler()
        check_result = CheckResult(
            invariant_name="identity_persistence",
            passed=True,
            failure_reason="",
        )
        validation = ValidationResult(
            passed=True,
            checks=ConservationChecks(
                identity_persistence=check_result,
            ),
            validator_results=ValidatorResults(
                checks=[check_result],
                summary="1 check, 0 failed",
            ),
            failed_invariants=[],
        )

        # Create a minimal delta for the proof assembler
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            commitment_id="financial_covenant.leverage_ratio",
            agreement_identity="test",
            affected_fields=[
                AffectedField(
                    field_name="applicability",
                    old_value={"steady_state_threshold": 3.50},
                    new_value={"steady_state_threshold": 4.00},
                ),
            ],
            preserved_fields=["threshold", "operator", "unit"],
            source_authority="Amendment No. 3",
            old_value_consistency_verified=True,
        )

        pre_proof = assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity_result,
            validation=validation,
            predecessor_version=0,
            successor_version=1,
        )

        # Pre-execution proof must gate execution
        assert pre_proof.may_proceed_to_execution()

        # Update post-execution
        exec_summary = ExecutionResultSummary(
            applied=True, status="COMPLETE", state_changed=True,
        )
        completed = assembler.update_post_execution(
            proof=pre_proof,
            execution_result=exec_summary,
            lineage_reference="LE-test123",
        )

        # The completed proof must have execution result and lineage
        assert completed.execution_result is not None
        assert completed.lineage_reference == "LE-test123"
        assert completed.proof_completeness == ProofCompleteness.COMPLETE
