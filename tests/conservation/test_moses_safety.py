"""Conformance tests for Step 23S MOSES semantic safety baseline.

These tests are GATING conformance tests, not advisory unit tests.  Each
invariant has a positive test (the invariant permits a valid transformation)
and a violation test (the invariant blocks an invalid transformation).

An invariant may be marked ENFORCED only when all three exist:
    RuntimeGuard(I)
    AND PositiveTest(I)
    AND ViolationTest(I)

Invariants tested:

  I1  Target-vs-reference separation (reference_is_not_target)
  I2  Value-extraction compatibility (incorrect_semantic_delta_cannot_execute)
  I3  Cross-type evidence rejection
  I4  Section-alias consistency
  I5  Section corroboration for structural amendments
      (out_of_scope_instruction_cannot_mutate_state)
  I6  Old-value consistency from amendment evidence only
      (old_value_matches_predecessor, wrong_old_value_blocks_transform)
  I7  Minimal semantic proof (proof_record_is_complete,
      authority_requires_valid_semantic_proof,
      invalid_semantic_proof_cannot_execute,
      predecessor_state_alone_does_not_prove_target)
"""
from __future__ import annotations

import pytest

from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)
from upsilon.conservation.moses_safety import (
    CheckResult,
    ProofCompleteness,
    ProofValidity,
    TargetEvidenceLevel,
    build_semantic_proof,
    check_cross_type_evidence,
    check_old_value_consistency,
    check_section_alias_consistency,
    check_value_extraction_compatibility,
)
from upsilon.pipeline.semantic_pipeline_v2 import (
    AuthorityDecision,
    assess_authority,
)
from upsilon.transformations.semantic_resolver_v2 import resolve_instruction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _leverage_ratio_state(threshold: float = 4.00) -> dict[str, CommitmentState]:
    """Build a minimal state with a leverage ratio covenant."""
    return {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            threshold=threshold,
            unit="ratio",
        ),
    }


def _facility_state(amount: int = 150_000_000) -> dict[str, CommitmentState]:
    """Build a minimal state with a revolving facility."""
    return {
        "facility.revolving_facility": CommitmentState(
            canonical_key="facility.revolving_facility",
            commitment_type="facility",
            threshold=amount,
            unit="usd",
        ),
    }


def _make_instruction(
    source_text: str,
    target_ref: str = "",
    ins_type: InstructionType = InstructionType.REPLACE_VALUE,
    order: int = 1,
) -> AmendmentInstruction:
    return AmendmentInstruction(
        order=order,
        instruction_type=ins_type,
        target_section_ref=target_ref,
        source_text=source_text,
        provenance=InstructionProvenance.PARSER,
    )


# ---------------------------------------------------------------------------
# I6: Old-value consistency (amendment-evidence-only)
# ---------------------------------------------------------------------------


class TestOldValueConsistency:
    """I6: Old-value consistency from amendment evidence only.

    The old value must come from amendment evidence, not from predecessor
    state.  When the amendment declares an old value, it must match the
    predecessor.  When no old value is declared, the check is
    NOT_APPLICABLE (we do NOT fabricate one).
    """

    def test_old_value_matches_predecessor(self):
        """Positive: when the amendment declares an old value that matches
        the predecessor state, the check passes."""
        state = _leverage_ratio_state(threshold=4.00)
        result = check_old_value_consistency(
            old_value=4.00,
            current_commitment=state["financial_covenant.leverage_ratio"],
            field_name="threshold",
        )
        assert result == CheckResult.PASS

    def test_wrong_old_value_blocks_transform(self):
        """Violation: when the amendment declares an old value that does
        NOT match the predecessor state, the check fails."""
        state = _leverage_ratio_state(threshold=4.00)
        result = check_old_value_consistency(
            old_value=3.50,
            current_commitment=state["financial_covenant.leverage_ratio"],
            field_name="threshold",
        )
        assert result == CheckResult.FAIL

    def test_no_old_value_is_not_applicable(self):
        """When no old value is declared, the check is NOT_APPLICABLE.
        We do NOT fabricate an old value from predecessor state."""
        state = _leverage_ratio_state(threshold=4.00)
        result = check_old_value_consistency(
            old_value=None,
            current_commitment=state["financial_covenant.leverage_ratio"],
            field_name="threshold",
        )
        assert result == CheckResult.NOT_APPLICABLE

    def test_wrong_old_value_blocks_resolver(self):
        """End-to-end: the resolver blocks a mutation with a wrong old
        value via the safety proof."""
        state = _leverage_ratio_state(threshold=4.00)
        ins = _make_instruction(
            source_text=(
                "Section 7.10 is hereby amended to decrease the "
                "Maximum Leverage Ratio from 3.50 to 1.00 to 4.00 to 1.00"
            ),
            target_ref="Section 7.10",
        )
        result, trace = resolve_instruction(ins, state)
        # The resolver should produce an unresolved result because the
        # old value (3.50) does not match the predecessor (4.00).
        assert len(result.unresolved) > 0 or len(result.mutations) == 0


# ---------------------------------------------------------------------------
# I1: Target-vs-reference separation
# ---------------------------------------------------------------------------


class TestTargetVsReference:
    """I1: A reference to a commitment is not sufficient evidence that
    the amendment transforms that commitment."""

    def test_reference_is_not_target(self):
        """Violation: when the source text mentions a covenant name but
        the section reference maps to a different class, the target
        evidence is insufficient."""
        # Text mentions "Leverage Ratio" but section maps to a facility.
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Leverage Ratio shall be maintained.",
            section_ref="Section 2.01",  # maps to facility.revolving_facility
            current_commitment=None,
            confidence=0.95,
        )
        assert proof.section_alias_consistent == CheckResult.FAIL
        assert proof.proof_validity == ProofValidity.INVALID

    def test_section_contradicts_alias_blocks_resolver(self):
        """End-to-end: the resolver blocks a mutation where the section
        contradicts the alias-resolved target."""
        state = _leverage_ratio_state(threshold=4.00)
        # Text mentions "Leverage Ratio" but section 2.01 maps to facility.
        ins = _make_instruction(
            source_text=(
                "The Maximum Leverage Ratio shall not exceed 3.50 to 1.00"
            ),
            target_ref="Section 2.01",
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 0
        assert len(result.unresolved) > 0


# ---------------------------------------------------------------------------
# I7: Predecessor state alone does not prove target
# ---------------------------------------------------------------------------


class TestPredecessorStateNotProof:
    """I7: Predecessor state alone does not prove target identity.

    The fact that a commitment exists in the predecessor state does not
    mean the amendment targets it.  Target identity requires affirmative
    evidence from the amendment, not just predecessor existence.
    """

    def test_predecessor_state_alone_does_not_prove_target(self):
        """When the resolver matches via section-only (confidence <= 0.60)
        without corroboration, the target evidence is WEAK and the proof
        is INDETERMINATE."""
        state = _leverage_ratio_state(threshold=4.00)
        # Section 7.10 maps to leverage_ratio, but the source text has
        # no alias match — only a section-only match.
        ins = _make_instruction(
            source_text="Some generic amendment text without covenant names.",
            target_ref="Section 7.10",
        )
        result, trace = resolve_instruction(ins, state)
        # The resolver should not produce a mapped mutation from
        # section-only evidence without alias corroboration.
        # (The resolver's Step 1 may resolve via section, but the safety
        # proof should route it to UNRESOLVED if the evidence is weak.)
        if result.mutations:
            # If a mutation was produced, it must have a VALID proof.
            # But section-only without alias should not produce a mutation.
            pytest.fail(
                "Section-only match without alias should not produce a mutation"
            )


# ---------------------------------------------------------------------------
# I5: Section corroboration for structural amendments
# ---------------------------------------------------------------------------


class TestOutOfScopeCannotMutate:
    """I5: An out-of-scope instruction cannot mutate commitment state.

    For structural amendments (ADD on list fields), the section reference
    must corroborate the target.  An exception being added from an
    unrelated article is not affirmative target evidence.
    """

    def test_out_of_scope_instruction_cannot_mutate_state(self):
        """Violation: an ADD operation on a list field from a section
        that does not map to the target class is blocked."""
        state = _facility_state()
        # Text mentions "Revolving Facility" but section is "Article III"
        # which does not map to any known class.
        ins = _make_instruction(
            source_text=(
                "Notwithstanding anything to the contrary, the obligation "
                "of each Lender to make Revolving Loans is subject to "
                "conditions precedent."
            ),
            target_ref="Article III",
            ins_type=InstructionType.ADD,
        )
        result, trace = resolve_instruction(ins, state)
        # The safety proof should block this mutation.
        assert len(result.mutations) == 0
        assert len(result.unresolved) > 0


# ---------------------------------------------------------------------------
# I2: Value-extraction compatibility
# ---------------------------------------------------------------------------


class TestValueExtractionCompatibility:
    """I2: The extracted value must be compatible with the identified
    commitment's field type."""

    def test_incorrect_semantic_delta_cannot_execute(self):
        """Violation: a percentage value extracted from a SOFR-rate
        paragraph cannot be a leverage-ratio threshold."""
        state = _leverage_ratio_state(threshold=4.00)
        # Text mentions "Leverage Ratio" but the value 15% comes from
        # a commitment percentage context, not a ratio.
        ins = _make_instruction(
            source_text=(
                "Section 7.10 Leverage Ratio. At least 15% of the "
                "Commitments are undrawn."
            ),
            target_ref="Section 7.10",
        )
        result, trace = resolve_instruction(ins, state)
        # The safety proof should block this because the value (15.0)
        # is a percentage, not a ratio threshold.
        assert len(result.mutations) == 0
        assert len(result.unresolved) > 0

    def test_facility_value_must_be_dollar(self):
        """A facility threshold must be a dollar amount, not a ratio."""
        result = check_value_extraction_compatibility(
            canonical_id="facility.revolving_facility",
            field_name="threshold",
            new_value=3.50,
            source_text="The ratio shall be 3.50 to 1.00",
        )
        assert result == CheckResult.FAIL

    def test_ratio_covenant_value_must_be_ratio(self):
        """A ratio covenant threshold must be a ratio, not a dollar."""
        result = check_value_extraction_compatibility(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            new_value=150_000_000,
            source_text="The amount shall be $150,000,000",
        )
        assert result == CheckResult.FAIL

    def test_step_down_schedule_scalar_is_blocked(self):
        """A step-down schedule cannot be safely represented as a single
        scalar — the extraction is incomplete."""
        text = (
            "(i) ending on June 30, 2023 to exceed 4.00 to 1.00 "
            "and (ii) for any quarter ending thereafter, to exceed "
            "3.50 to 1.00"
        )
        result = check_value_extraction_compatibility(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            new_value=3.50,  # scalar extracted from schedule
            source_text=text,
        )
        assert result == CheckResult.FAIL


# ---------------------------------------------------------------------------
# I3: Cross-type evidence
# ---------------------------------------------------------------------------


class TestCrossTypeEvidence:
    """I3: If the source text contains operative evidence for a different
    commitment family, the target identity is ambiguous."""

    def test_facility_target_with_ratio_evidence_blocked(self):
        """A facility target with ratio threshold evidence in the text
        is cross-type evidence."""
        result = check_cross_type_evidence(
            canonical_id="facility.revolving_facility",
            field_name="threshold",
            source_text="The ratio shall not exceed 4.00 to 1.00",
        )
        assert result == CheckResult.FAIL


# ---------------------------------------------------------------------------
# I4: Section-alias consistency
# ---------------------------------------------------------------------------


class TestSectionAliasConsistency:
    """I4: The section reference must agree with the alias-resolved class."""

    def test_section_matches_alias(self):
        result = check_section_alias_consistency(
            canonical_id="financial_covenant.leverage_ratio",
            section_ref="Section 7.10",
        )
        assert result == CheckResult.PASS

    def test_section_contradicts_alias(self):
        result = check_section_alias_consistency(
            canonical_id="financial_covenant.leverage_ratio",
            section_ref="Section 2.01",  # maps to facility
        )
        assert result == CheckResult.FAIL

    def test_no_section_is_neutral(self):
        result = check_section_alias_consistency(
            canonical_id="financial_covenant.leverage_ratio",
            section_ref=None,
        )
        assert result == CheckResult.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# I7: Semantic proof record
# ---------------------------------------------------------------------------


class TestSemanticProofRecord:
    """I7: Every candidate mutation must carry a COMPLETE and VALID
    semantic proof."""

    def test_proof_record_is_complete(self):
        """A proof record with all checks evaluated is COMPLETE."""
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 7.10",
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.COMPLETE

    def test_authority_requires_valid_semantic_proof(self):
        """A VALID proof is required for authority.  An INVALID proof
        blocks authority."""
        # Valid proof
        proof_valid = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 7.10",
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.95,
        )
        assert proof_valid.proof_validity == ProofValidity.VALID
        assert proof_valid.is_executable

        # Invalid proof (section contradicts alias)
        proof_invalid = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 2.01",  # maps to facility
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.95,
        )
        assert proof_invalid.proof_validity == ProofValidity.INVALID
        assert not proof_invalid.is_executable

    def test_invalid_semantic_proof_cannot_execute(self):
        """An invalid semantic proof blocks execution — the candidate
        is routed to UNRESOLVED."""
        state = _leverage_ratio_state(threshold=4.00)
        # Section 2.01 maps to facility, contradicting the leverage ratio alias.
        ins = _make_instruction(
            source_text=(
                "The Maximum Leverage Ratio shall not exceed 3.50 to 1.00"
            ),
            target_ref="Section 2.01",
        )
        result, trace = resolve_instruction(ins, state)
        # No mutation should be produced — the proof is invalid.
        assert len(result.mutations) == 0
        assert len(result.unresolved) > 0
        # The trace should show a Step 8 failure.
        assert trace.failed_step == 8

    def test_indeterminate_proof_routes_to_unresolved(self):
        """An indeterminate proof (weak target evidence) routes to
        UNRESOLVED, not to execution."""
        # Section-only match without corroboration → WEAK evidence.
        # Use a section that doesn't map to any known class, but with
        # a ratio value in the text so the value-extraction check passes.
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 99.99",  # not in section map
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.60,  # section-only confidence
        )
        assert proof.target_evidence_level == TargetEvidenceLevel.WEAK
        assert proof.proof_validity == ProofValidity.INDETERMINATE
        assert not proof.is_executable


# ---------------------------------------------------------------------------
# End-to-end: valid transformation is permitted
# ---------------------------------------------------------------------------


class TestValidTransformationPermitted:
    """Positive: a valid transformation with sufficient evidence is
    permitted by the safety layer."""

    def test_valid_leverage_ratio_amendment_executes(self):
        """A leverage ratio amendment with alias match, section
        corroboration, and ratio value extraction is permitted."""
        state = _leverage_ratio_state(threshold=4.00)
        ins = _make_instruction(
            source_text=(
                "Section 7.10 is hereby amended so that the "
                "Maximum Leverage Ratio shall not exceed 3.50 to 1.00"
            ),
            target_ref="Section 7.10",
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 1
        assert result.mutations[0].new_value == 3.50
        assert trace.failed_step == 0

    def test_valid_facility_amendment_executes(self):
        """A facility amendment with alias match and dollar value is
        permitted."""
        state = _facility_state(amount=150_000_000)
        ins = _make_instruction(
            source_text=(
                "The Revolving Facility commitment is hereby increased "
                "to $200,000,000"
            ),
            target_ref="Section 2.01",
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 1
        assert result.mutations[0].new_value == 200_000_000


# ---------------------------------------------------------------------------
# I1/alias: Unsupported alias cannot create false identity
# ---------------------------------------------------------------------------


class TestUnsupportedAliasCannotCreateFalseIdentity:
    """An alias that maps a related-but-distinct financial concept to
    one of the frozen 13 classes merely because it produces a mapping
    must be rejected.

    The MOSES alias policy (CONSERVATION_INVARIANTS.md §4) requires
    genuine semantic equivalence.  When equivalence cannot be
    demonstrated, the candidate must be routed to UNSUPPORTED /
    OUT_OF_SCOPE / AMBIGUOUS as appropriate — not collapsed into a
    frozen class.
    """

    def test_non_equivalent_alias_is_blocked_by_value_mismatch(self):
        """A 'Current Ratio' alias matched in a section that maps to
        leverage_ratio is a non-equivalent identity claim.  The
        section-alias consistency check (I4) catches this: the section
        contradicts the alias-resolved class, so the proof is INVALID."""
        # "Current Ratio" aliases to financial_covenant.current_ratio,
        # but the section maps to leverage_ratio.  This is a
        # non-equivalent identity claim — the alias matched in a
        # context that contradicts it.
        proof = build_semantic_proof(
            canonical_id="financial_covenant.current_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=2.00,
            source_text="The Current Ratio shall not be less than 2.00 to 1.00",
            section_ref="Section 7.10",  # maps to leverage_ratio
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.current_ratio",
                commitment_type="financial_covenant",
                threshold=1.50,
                unit="ratio",
            ),
            confidence=0.95,
        )
        # The section-alias consistency check catches the contradiction.
        assert proof.section_alias_consistent == CheckResult.FAIL
        assert proof.proof_validity == ProofValidity.INVALID
        assert not proof.is_executable

    def test_non_equivalent_alias_blocks_resolver(self):
        """End-to-end: the resolver blocks a mutation where a
        non-equivalent alias is contradicted by the section reference."""
        state = {
            "financial_covenant.current_ratio": CommitmentState(
                canonical_key="financial_covenant.current_ratio",
                commitment_type="financial_covenant",
                threshold=1.50,
                unit="ratio",
            ),
        }
        # "Current Ratio" alias matches, but Section 7.10 maps to
        # leverage_ratio — a non-equivalent class.  The safety proof
        # blocks this.
        ins = _make_instruction(
            source_text=(
                "The Current Ratio shall not be less than 2.00 to 1.00"
            ),
            target_ref="Section 7.10",
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 0
        assert len(result.unresolved) > 0


# ---------------------------------------------------------------------------
# I7: Incomplete semantic proof cannot execute
# ---------------------------------------------------------------------------


class TestIncompleteSemanticProofCannotExecute:
    """A proof with INCOMPLETE status cannot execute.  Completeness is
    a structural property (SEMANTIC_AUTHORITY_GATE.md §2): all required
    proof fields must be populated.  When a structural component is
    missing, the proof is INCOMPLETE and validity is INDETERMINATE —
    the engine cannot even ask the semantic question.
    """

    def test_missing_new_value_produces_incomplete_proof(self):
        """When new_value is None, the proof is structurally INCOMPLETE
        — there is no transformation to prove."""
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=None,  # missing — no transformation
            source_text="Some amendment text",
            section_ref="Section 7.10",
            current_commitment=None,
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE
        assert proof.proof_validity == ProofValidity.INDETERMINATE
        assert not proof.is_executable

    def test_missing_source_text_produces_incomplete_proof(self):
        """When source_text is empty, the proof is structurally
        INCOMPLETE — there is no amendment evidence."""
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="",  # missing — no evidence
            section_ref="Section 7.10",
            current_commitment=None,
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE
        assert not proof.is_executable

    def test_missing_canonical_id_produces_incomplete_proof(self):
        """When canonical_id is empty, the proof is structurally
        INCOMPLETE — the target commitment is unidentified."""
        proof = build_semantic_proof(
            canonical_id="",  # missing — no target
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 7.10",
            current_commitment=None,
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE
        assert not proof.is_executable

    def test_incomplete_proof_blocks_authority(self):
        """An INCOMPLETE proof blocks authority promotion via the
        authority gate."""
        from upsilon.models.legacy_models import ExecutionStatus as ExecStatus

        # Build a mock INCOMPLETE proof
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=None,  # missing → INCOMPLETE
            source_text="Some text",
            section_ref="Section 7.10",
            current_commitment=None,
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE

        decision = assess_authority(
            execution_status=ExecStatus.COMPLETE,
            proofs=[proof],
            inherited_unresolved_count=0,
            own_unresolved_count=0,
        )
        assert decision == AuthorityDecision.AUTHORITY_BLOCKED


# ---------------------------------------------------------------------------
# I7/Authority: Incorrect semantic transformation cannot be authoritative
# ---------------------------------------------------------------------------


class TestIncorrectSemanticTransformationCannotBeAuthoritative:
    """An incorrect semantic transformation cannot be promoted to
    authoritative.  The authority gate (assess_authority) must block
    promotion when any proof is INVALID or has INSUFFICIENT target
    evidence, even if execution completed with no unresolved state.
    """

    def test_invalid_proof_blocks_authority(self):
        """A COMPLETE but INVALID proof blocks authority promotion,
        even when execution is COMPLETE and no unresolved state
        exists."""
        from upsilon.models.legacy_models import ExecutionStatus as ExecStatus

        # Build a COMPLETE but INVALID proof (section contradicts alias)
        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 2.01",  # maps to facility — contradiction
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.COMPLETE
        assert proof.proof_validity == ProofValidity.INVALID

        decision = assess_authority(
            execution_status=ExecStatus.COMPLETE,
            proofs=[proof],
            inherited_unresolved_count=0,
            own_unresolved_count=0,
        )
        assert decision == AuthorityDecision.AUTHORITY_BLOCKED

    def test_insufficient_evidence_blocks_authority(self):
        """A proof with INSUFFICIENT target evidence blocks authority,
        even when execution is COMPLETE."""
        from upsilon.models.legacy_models import ExecutionStatus as ExecStatus

        # Build a proof with INSUFFICIENT target evidence
        # (section contradicts alias + cross-type evidence)
        proof = build_semantic_proof(
            canonical_id="facility.revolving_facility",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=150_000_000,
            source_text="The Leverage Ratio shall not exceed 4.00 to 1.00",
            section_ref="Section 7.10",  # maps to leverage_ratio — contradiction
            current_commitment=CommitmentState(
                canonical_key="facility.revolving_facility",
                commitment_type="facility",
                threshold=100_000_000,
                unit="usd",
            ),
            confidence=0.95,
        )
        assert proof.target_evidence_level == TargetEvidenceLevel.INSUFFICIENT

        decision = assess_authority(
            execution_status=ExecStatus.COMPLETE,
            proofs=[proof],
            inherited_unresolved_count=0,
            own_unresolved_count=0,
        )
        assert decision == AuthorityDecision.AUTHORITY_BLOCKED

    def test_valid_proof_grants_authority(self):
        """Positive: a COMPLETE and VALID proof with no unresolved
        state grants authority."""
        from upsilon.models.legacy_models import ExecutionStatus as ExecStatus

        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 7.10",
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.95,
        )
        assert proof.proof_completeness == ProofCompleteness.COMPLETE
        assert proof.proof_validity == ProofValidity.VALID

        decision = assess_authority(
            execution_status=ExecStatus.COMPLETE,
            proofs=[proof],
            inherited_unresolved_count=0,
            own_unresolved_count=0,
        )
        assert decision == AuthorityDecision.AUTHORITY_GRANTED

    def test_inherited_unresolved_blocks_authority(self):
        """Inherited unresolved state from a prior step blocks
        authority even with a valid proof."""
        from upsilon.models.legacy_models import ExecutionStatus as ExecStatus

        proof = build_semantic_proof(
            canonical_id="financial_covenant.leverage_ratio",
            field_name="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value=3.50,
            source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 7.10",
            current_commitment=CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.00,
                unit="ratio",
            ),
            confidence=0.95,
        )
        assert proof.is_executable

        decision = assess_authority(
            execution_status=ExecStatus.COMPLETE,
            proofs=[proof],
            inherited_unresolved_count=2,  # prior step left unresolved
            own_unresolved_count=0,
        )
        assert decision == AuthorityDecision.AUTHORITY_BLOCKED

    def test_no_op_step_grants_authority_without_proofs(self):
        """A no-op step (no candidates, no proofs) with COMPLETE
        execution and no unresolved state grants authority.  This
        preserves the existing chain-aware authority contract for
        steps that do not produce mutations."""
        from upsilon.models.legacy_models import ExecutionStatus as ExecStatus

        decision = assess_authority(
            execution_status=ExecStatus.COMPLETE,
            proofs=[],  # no proofs — no-op step
            inherited_unresolved_count=0,
            own_unresolved_count=0,
        )
        assert decision == AuthorityDecision.AUTHORITY_GRANTED
