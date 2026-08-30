"""System smoke test: end-to-end amendment-chain reconstruction.

This is the first true system smoke test for the Financial Commitment
Integrity tester. It exercises the full pipeline:

    S0 → A1 → reconstruct S1 → A2 → reconstruct S2 → ...
    → compare reconstructed current state against ground truth

on 2-3 complete issuer chains (synthetic fixtures that model real
amendment-chain structure; real EDGAR chain acquisition is the next
phase).

The four questions the smoke test must answer:
  Q1: Can Upsilon preserve authoritative state across multiple amendments?
  Q2: Can it maintain complete lineage from origin to current state?
  Q3: Does any unresolved instruction block authoritative promotion correctly?
  Q4: Does reconstructed state exactly match an independent authoritative
      document where one exists?

These tests use the REAL executor and persistence planner — no mocks.
"""
from __future__ import annotations

from chain_reconstruction import (
    ChainReconstructionResult,
    ComparisonResult,
    IssuerChain,
    StepResult,
    compare_to_ground_truth,
    reconstruct_chain,
)
from models import CommitmentState, ExecutionStatus, InstructionType
from synthetic_chains import all_chains, chain_acme, chain_beta, chain_gamma


# ---------------------------------------------------------------------------
# Per-chain reconstruction tests
# ---------------------------------------------------------------------------


def test_chain_acme_reconstructs_cleanly():
    """Chain ACME: 3 clean amendments, all COMPLETE, final state matches A&R."""
    result = reconstruct_chain(chain_acme())
    assert result.chain_id == "CHAIN-ACME"
    assert len(result.steps) == 3

    # Every step is authoritative (COMPLETE, no unresolved).
    for step in result.steps:
        assert step.is_authoritative is True
        assert step.execution_result.status == ExecutionStatus.COMPLETE
        assert len(step.execution_result.unresolved) == 0

    # Final state has all 4 commitments (3 original + 1 added in A2).
    assert len(result.final_state) == 4
    assert "financial_covenant.debt_service_coverage" in result.final_state

    # Leverage was relaxed to 4.5 in A1, then tightened back to 4.0 in A3.
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.0
    # Revolver increased 50M → 75M in A2.
    assert result.final_state["facility.revolver.amount"].threshold == 75_000_000.0
    # Permitted_acquisition exception added in A3.
    assert "permitted_acquisition" in result.final_state[
        "financial_covenant.total_leverage_ratio"
    ].exceptions


def test_chain_beta_unresolved_blocks_promotion():
    """Chain BETA: A1 has RESTATE_SECTION (unresolved) → PARTIAL, not authoritative.
    A2 is clean → COMPLETE, authoritative. Final state matches composite."""
    result = reconstruct_chain(chain_beta())
    assert len(result.steps) == 2

    a1, a2 = result.steps

    # A1: one applied (REPLACE), one unresolved (RESTATE_SECTION).
    assert a1.execution_result.status == ExecutionStatus.PARTIAL
    assert a1.is_authoritative is False
    assert len(a1.execution_result.applied) == 1
    assert len(a1.execution_result.unresolved) == 1
    assert a1.execution_result.unresolved[0].instruction_type == InstructionType.RESTATE_SECTION

    # A2: clean, authoritative.
    assert a2.execution_result.status == ExecutionStatus.COMPLETE
    assert a2.is_authoritative is True
    assert len(a2.execution_result.unresolved) == 0

    # Final leverage is 4.25 (A2 applied on top of A1's provisional 4.0).
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.25


def test_chain_gamma_waiver_then_threshold_change():
    """Chain GAMMA: A1 waives leverage for Q1-Q2 2026, A2 tightens to 4.5.
    Persistence plan for A1 must produce a WAIVED state + restore_state."""
    result = reconstruct_chain(chain_gamma())
    assert len(result.steps) == 2

    a1, a2 = result.steps

    # A1: waiver applied, authoritative (COMPLETE — waiver is a valid
    # authoritative state change, just bounded in time).
    assert a1.execution_result.status == ExecutionStatus.COMPLETE
    assert a1.is_authoritative is True
    assert len(a1.execution_result.applied) == 1

    # Persistence plan for A1 must have a waiver mutation with restore_state.
    assert len(a1.persistence_plan["mutations"]) == 1
    waiver_mutation = a1.persistence_plan["mutations"][0]
    assert waiver_mutation["state"].status == "WAIVED"
    assert waiver_mutation["restore_state"] is not None
    assert waiver_mutation["restore_state"].status == "ACTIVE"
    assert waiver_mutation["restore_state"].threshold == 5.0  # post-A1 terms

    # A2: clean threshold change 5.0 → 4.5.
    assert a2.execution_result.status == ExecutionStatus.COMPLETE
    assert a2.is_authoritative is True
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.5


# ---------------------------------------------------------------------------
# Q1: Can Upsilon preserve authoritative state across multiple amendments?
# ---------------------------------------------------------------------------


def test_q1_state_preservation_all_chains():
    """Q1: No commitment is silently lost; statuses are COMPLETE or PARTIAL."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        q1 = result.questions["Q1_state_preservation"]
        assert q1["pass"] is True, (
            f"{chain.chain_id} Q1 failed: {q1['evidence']}"
        )
        # No silent commitment losses.
        assert q1["evidence"]["silent_commitment_losses"] == []


def test_q1_acme_all_steps_authoritative():
    """ACME: all 3 steps are authoritative (no unresolved)."""
    result = reconstruct_chain(chain_acme())
    q1 = result.questions["Q1_state_preservation"]
    assert q1["evidence"]["authoritative_steps"] == 3
    assert q1["evidence"]["provisional_steps"] == 0


def test_q1_beta_has_one_provisional_step():
    """BETA: A1 is provisional (PARTIAL), A2 is authoritative."""
    result = reconstruct_chain(chain_beta())
    q1 = result.questions["Q1_state_preservation"]
    assert q1["evidence"]["authoritative_steps"] == 1
    assert q1["evidence"]["provisional_steps"] == 1


# ---------------------------------------------------------------------------
# Q2: Can it maintain complete lineage from origin to current state?
# ---------------------------------------------------------------------------


def test_q2_lineage_completeness_all_chains():
    """Q2: Every state-changing step has a persistence plan with mutations
    and valid_from anchors. No lineage gaps."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        q2 = result.questions["Q2_lineage_completeness"]
        assert q2["pass"] is True, (
            f"{chain.chain_id} Q2 failed: {q2['evidence']['lineage_gaps']}"
        )
        assert q2["evidence"]["lineage_gaps"] == []


def test_q2_acme_produces_mutations_every_step():
    """ACME: each of 3 steps produces at least one mutation."""
    result = reconstruct_chain(chain_acme())
    q2 = result.questions["Q2_lineage_completeness"]
    # A1: 1 mutation (leverage). A2: 2 mutations (new covenant + revolver).
    # A3: 1 mutation (leverage, since exception add groups with threshold
    # change on the same target).
    assert q2["evidence"]["step_mutation_counts"] == [1, 2, 1]


def test_q2_gamma_waiver_produces_restore_lineage():
    """GAMMA: A1 waiver produces a mutation with restore_state (REINSTATES
    lineage edge in the persistence plan)."""
    result = reconstruct_chain(chain_gamma())
    a1 = result.steps[0]
    mutation = a1.persistence_plan["mutations"][0]
    assert mutation["restore_state"] is not None
    # The restore_state must have a valid_from = waiver end.
    assert mutation["restore_state"].valid_from is not None


# ---------------------------------------------------------------------------
# Q3: Does any unresolved instruction block authoritative promotion?
# ---------------------------------------------------------------------------


def test_q3_unresolved_blocks_promotion_all_chains():
    """Q3: Every step with unresolved instructions has is_authoritative=False
    and status PARTIAL/UNRESOLVED. Steps without unresolved are authoritative."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        q3 = result.questions["Q3_unresolved_blocks_promotion"]
        assert q3["pass"] is True, (
            f"{chain.chain_id} Q3 failed: {q3['evidence']}"
        )


def test_q3_beta_a1_unresolved_blocks_promotion():
    """BETA A1: RESTATE_SECTION is unresolved → PARTIAL → not authoritative."""
    result = reconstruct_chain(chain_beta())
    a1 = result.steps[0]
    assert a1.execution_result.unresolved
    assert a1.is_authoritative is False
    assert a1.execution_result.status == ExecutionStatus.PARTIAL


def test_q3_beta_a2_clean_is_authoritative():
    """BETA A2: no unresolved → COMPLETE → authoritative."""
    result = reconstruct_chain(chain_beta())
    a2 = result.steps[1]
    assert not a2.execution_result.unresolved
    assert a2.is_authoritative is True
    assert a2.execution_result.status == ExecutionStatus.COMPLETE


# ---------------------------------------------------------------------------
# Q4: Does reconstructed state exactly match ground truth?
# ---------------------------------------------------------------------------


def test_q4_ground_truth_match_all_chains():
    """Q4: Reconstructed final state exactly matches the independent
    ground-truth composite/A&R for all three chains."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        q4 = result.questions["Q4_ground_truth_match"]
        assert q4["evidence"]["ground_truth_available"] is True
        assert q4["pass"] is True, (
            f"{chain.chain_id} Q4 failed: {q4['evidence']}"
        )


def test_q4_acme_exact_match():
    """ACME: exact match on all 4 commitments, zero field mismatches."""
    result = reconstruct_chain(chain_acme())
    comp = result.comparison
    assert comp is not None
    assert comp.exact_match is True
    assert comp.matched_commitments == 4
    assert comp.missing_commitments == []
    assert comp.extra_commitments == []
    assert comp.field_mismatches == []


def test_q4_beta_exact_match():
    """BETA: exact match on both commitments (leverage 4.25, interest 2.5)."""
    result = reconstruct_chain(chain_beta())
    comp = result.comparison
    assert comp is not None
    assert comp.exact_match is True
    assert comp.matched_commitments == 2
    assert comp.field_mismatches == []


def test_q4_gamma_exact_match():
    """GAMMA: exact match — leverage 4.5 ACTIVE, interest 2.0."""
    result = reconstruct_chain(chain_gamma())
    comp = result.comparison
    assert comp is not None
    assert comp.exact_match is True
    assert comp.matched_commitments == 2
    # Final state leverage is ACTIVE (post-waiver, post-A2 threshold change).
    assert result.final_state["financial_covenant.total_leverage_ratio"].status == "ACTIVE"
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.5


# ---------------------------------------------------------------------------
# Comparison engine unit tests
# ---------------------------------------------------------------------------


def test_compare_exact_match():
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="ACTIVE",
        ),
    }
    gt = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="ACTIVE",
        ),
    }
    result = compare_to_ground_truth(state, gt)
    assert result.exact_match is True
    assert result.matched_commitments == 1


def test_compare_threshold_mismatch_detected():
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.5,
        ),
    }
    gt = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
        ),
    }
    result = compare_to_ground_truth(state, gt)
    assert result.exact_match is False
    assert len(result.field_mismatches) == 1
    assert result.field_mismatches[0].field == "threshold"
    assert result.field_mismatches[0].reconstructed == 4.5
    assert result.field_mismatches[0].ground_truth == 4.0


def test_compare_missing_commitment_detected():
    state = {}
    gt = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
        ),
    }
    result = compare_to_ground_truth(state, gt)
    assert result.exact_match is False
    assert result.missing_commitments == ["covenant.x"]


def test_compare_deleted_in_reconstructed_not_counted_as_extra():
    """A commitment that was DELETED in reconstructed and is absent from
    ground truth is not an error — it was intentionally removed."""
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="DELETED",
        ),
    }
    gt = {}
    result = compare_to_ground_truth(state, gt)
    assert result.exact_match is True
    assert result.extra_commitments == []
    assert result.deleted_in_reconstructed == ["covenant.x"]


def test_compare_active_in_reconstructed_but_absent_from_gt_is_extra():
    """A commitment that is ACTIVE in reconstructed but absent from ground
    truth is an error (extra commitment)."""
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="ACTIVE",
        ),
    }
    gt = {}
    result = compare_to_ground_truth(state, gt)
    assert result.exact_match is False
    assert result.extra_commitments == ["covenant.x"]


def test_compare_status_mismatch_when_reconstructed_deleted_gt_active():
    """If reconstructed is DELETED but ground truth is ACTIVE, that's a
    status mismatch (the deletion was wrong), not a clean removal."""
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="DELETED",
        ),
    }
    gt = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="ACTIVE",
        ),
    }
    result = compare_to_ground_truth(state, gt)
    assert result.exact_match is False
    assert any(m.field == "status" for m in result.field_mismatches)


# ---------------------------------------------------------------------------
# Aggregate smoke-test verdict
# ---------------------------------------------------------------------------


def test_all_four_questions_pass_all_three_chains():
    """The complete system smoke test: all four questions pass on all
    three chains. This is the gate for proceeding to the 25-issuer
    chain study."""
    results = [reconstruct_chain(c) for c in all_chains()]
    assert len(results) == 3

    question_keys = [
        "Q1_state_preservation",
        "Q2_lineage_completeness",
        "Q3_unresolved_blocks_promotion",
        "Q4_ground_truth_match",
    ]
    for result in results:
        for qk in question_keys:
            q = result.questions[qk]
            assert q["pass"] is True, (
                f"{result.chain_id} {qk} failed: {q['summary']} | {q['evidence']}"
            )
