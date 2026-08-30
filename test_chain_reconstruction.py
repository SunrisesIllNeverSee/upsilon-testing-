"""Synthetic system smoke test: end-to-end amendment-chain reconstruction.

This is the synthetic system smoke test for the Financial Commitment
Integrity tester. It exercises the full pipeline:

    S0 → A1 → reconstruct S1 → A2 → reconstruct S2 → ...
    → compare reconstructed current state against oracle ground truth

on 5 complete issuer chains (synthetic oracle fixtures that model real
amendment-chain structure; real EDGAR chain acquisition is the next
phase).

The four questions the smoke test must answer:
  Q1: Can Upsilon preserve authoritative state across multiple amendments?
  Q2: Can it maintain complete lineage from origin to current state?
  Q3: Does any unresolved instruction block authoritative promotion correctly?
  Q4: Does reconstructed state exactly match an independent authoritative
      document where one exists?

These tests use the REAL executor and persistence planner — no mocks.

Authority model (chain-aware, tested by Q3):
  A step is authoritative iff (a) its own execution is COMPLETE and
  (b) no inherited unresolved uncertainty from ancestor amendments
  remains. A later clean amendment does NOT automatically erase
  uncertainty inherited from an earlier PARTIAL/UNRESOLVED amendment.
  The inherited unresolved must be explicitly addressed by a later
  amendment's applied instructions targeting the same commitment.
"""
from __future__ import annotations

from chain_reconstruction import (
    ChainReconstructionResult,
    ComparisonResult,
    IssuerChain,
    LineageGraph,
    PendingRestore,
    StepResult,
    VersionNode,
    _apply_due_restores,
    _is_resolved_by,
    compare_to_ground_truth,
    reconstruct_chain,
)
from models import AmendmentInstruction, CommitmentState, ExecutionStatus, InstructionType
from synthetic_chains import (
    all_chains,
    chain_acme,
    chain_beta,
    chain_delta,
    chain_epsilon,
    chain_gamma,
)


# ---------------------------------------------------------------------------
# Per-chain reconstruction tests
# ---------------------------------------------------------------------------


def test_chain_acme_reconstructs_cleanly():
    """Chain ACME: 3 clean amendments, all COMPLETE, final state matches A&R."""
    result = reconstruct_chain(chain_acme())
    assert result.chain_id == "CHAIN-ACME"
    assert len(result.steps) == 3

    # Every step is authoritative (COMPLETE, no unresolved, no inherited).
    for step in result.steps:
        assert step.is_authoritative is True
        assert step.execution_result.status == ExecutionStatus.COMPLETE
        assert len(step.execution_result.unresolved) == 0
        assert len(step.inherited_unresolved) == 0

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
    """Chain BETA: A1 has RESTATE_SECTION (unresolved) → PARTIAL, not
    authoritative. A2 is clean but targets a DIFFERENT commitment, so it
    does NOT resolve A1's inherited unresolved → A2 is also NOT
    authoritative (chain-aware authority). Final state still matches oracle."""
    result = reconstruct_chain(chain_beta())
    assert len(result.steps) == 2

    a1, a2 = result.steps

    # A1: one applied (REPLACE), one unresolved (RESTATE_SECTION).
    assert a1.execution_result.status == ExecutionStatus.PARTIAL
    assert a1.is_authoritative is False
    assert len(a1.execution_result.applied) == 1
    assert len(a1.execution_result.unresolved) == 1
    assert a1.execution_result.unresolved[0].instruction_type == InstructionType.RESTATE_SECTION
    # A1's inherited unresolved (for the next step) includes its own.
    assert len(a1.inherited_unresolved) == 1
    assert a1.inherited_unresolved[0].target_key == "financial_covenant.interest_coverage"

    # A2: clean execution (COMPLETE), but NOT authoritative because A1's
    # inherited unresolved (RESTATE_SECTION on interest_coverage) was NOT
    # resolved — A2 targets total_leverage_ratio, not interest_coverage.
    assert a2.execution_result.status == ExecutionStatus.COMPLETE
    assert a2.is_authoritative is False  # KEY CHANGE: chain-aware authority
    assert len(a2.execution_result.unresolved) == 0
    # A2 still carries A1's inherited unresolved.
    assert len(a2.inherited_unresolved) == 1
    assert a2.inherited_unresolved[0].target_key == "financial_covenant.interest_coverage"

    # Final leverage is 4.25 (A2 applied on top of A1's provisional 4.0).
    # State reconstruction is independent of authority.
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


def test_chain_delta_waiver_across_intervening_amendment():
    """Chain DELTA: A1 waives leverage Jan→Jul, A2 is UNRELATED (March),
    A3 tightens leverage in August. The A1 July restore must NOT be lost
    just because A2 (the immediately preceding amendment) didn't touch
    the waived covenant. Regression test for chain-wide pending queue."""
    result = reconstruct_chain(chain_delta())
    assert len(result.steps) == 3

    a1, a2, a3 = result.steps

    # A1: waiver applied, authoritative.
    assert a1.execution_result.status == ExecutionStatus.COMPLETE
    assert a1.is_authoritative is True
    assert a1.persistence_plan["mutations"][0]["restore_state"] is not None

    # A2: unrelated amendment on interest_coverage. At A2's effective_at
    # (Mar 1), the waiver (expires Jul 1) has NOT expired, so leverage
    # is still WAIVED in A2's reconstructed state.
    assert a2.execution_result.status == ExecutionStatus.COMPLETE
    assert a2.is_authoritative is True
    assert a2.reconstructed_state["financial_covenant.total_leverage_ratio"].status == "WAIVED"
    # A2 changed interest_coverage, not leverage.
    assert a2.reconstructed_state["financial_covenant.interest_coverage"].threshold == 2.5

    # A3: at A3's effective_at (Aug 1), the waiver (expired Jul 1) MUST
    # have been restored BEFORE A3 executes. The chain-wide pending queue
    # applies the A1 restore (leverage → ACTIVE, threshold 5.0) at the
    # start of A3. A3 then changes threshold 5.0 → 4.5.
    assert a3.execution_result.status == ExecutionStatus.COMPLETE
    assert a3.is_authoritative is True
    # A3's REPLACE_VALUE specifies old_value=5.0, which only succeeds if
    # the restore was applied (otherwise the state would be WAIVED with
    # threshold 5.0 but the old_value check would still pass on threshold).
    # The real proof is the final state: leverage ACTIVE, threshold 4.5.
    assert result.final_state["financial_covenant.total_leverage_ratio"].status == "ACTIVE"
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.5
    # Interest_coverage carries A2's change.
    assert result.final_state["financial_covenant.interest_coverage"].threshold == 2.5


def test_chain_epsilon_inherited_unresolved_resolved_by_a3():
    """Chain EPSILON: A1 has unresolved RESTATE_SECTION on interest_coverage,
    A2 targets a different commitment (does NOT resolve), A3 targets
    interest_coverage (DOES resolve) → A3 becomes authoritative.
    Regression test for chain-aware authority resolution."""
    result = reconstruct_chain(chain_epsilon())
    assert len(result.steps) == 3

    a1, a2, a3 = result.steps

    # A1: PARTIAL (one applied, one unresolved), not authoritative.
    assert a1.execution_result.status == ExecutionStatus.PARTIAL
    assert a1.is_authoritative is False
    assert len(a1.execution_result.unresolved) == 1
    assert a1.inherited_unresolved[0].target_key == "financial_covenant.interest_coverage"

    # A2: COMPLETE but NOT authoritative — targets total_leverage_ratio,
    # not interest_coverage, so A1's inherited unresolved persists.
    assert a2.execution_result.status == ExecutionStatus.COMPLETE
    assert a2.is_authoritative is False
    assert len(a2.execution_result.unresolved) == 0
    assert len(a2.inherited_unresolved) == 1
    assert a2.inherited_unresolved[0].target_key == "financial_covenant.interest_coverage"

    # A3: COMPLETE AND authoritative — targets interest_coverage, which
    # resolves A1's inherited RESTATE_SECTION per the conservative
    # resolution policy.
    assert a3.execution_result.status == ExecutionStatus.COMPLETE
    assert a3.is_authoritative is True
    assert len(a3.execution_result.unresolved) == 0
    assert len(a3.inherited_unresolved) == 0  # resolved!

    # Final state matches oracle.
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.25
    assert result.final_state["financial_covenant.interest_coverage"].threshold == 3.0


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
    """ACME: all 3 steps are authoritative (no unresolved, no inherited)."""
    result = reconstruct_chain(chain_acme())
    q1 = result.questions["Q1_state_preservation"]
    assert q1["evidence"]["authoritative_steps"] == 3
    assert q1["evidence"]["provisional_steps"] == 0


def test_q1_beta_both_steps_provisional():
    """BETA: A1 is provisional (own unresolved), A2 is provisional
    (inherited unresolved). Zero authoritative steps."""
    result = reconstruct_chain(chain_beta())
    q1 = result.questions["Q1_state_preservation"]
    assert q1["evidence"]["authoritative_steps"] == 0
    assert q1["evidence"]["provisional_steps"] == 2


def test_q1_epsilon_a1_a2_provisional_a3_authoritative():
    """EPSILON: A1 and A2 provisional, A3 authoritative (resolves inherited)."""
    result = reconstruct_chain(chain_epsilon())
    q1 = result.questions["Q1_state_preservation"]
    assert q1["evidence"]["authoritative_steps"] == 1
    assert q1["evidence"]["provisional_steps"] == 2


# ---------------------------------------------------------------------------
# Q2: Can it maintain complete lineage from origin to current state?
# ---------------------------------------------------------------------------


def test_q2_lineage_completeness_all_chains():
    """Q2: Every version is reachable from origin, no orphans, no broken
    reinstatement edges, every mutation has valid_from. No lineage gaps."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        q2 = result.questions["Q2_lineage_completeness"]
        assert q2["pass"] is True, (
            f"{chain.chain_id} Q2 failed: {q2['evidence']['lineage_gaps']}"
        )
        assert q2["evidence"]["lineage_gaps"] == []
        assert q2["evidence"]["orphans"] == []
        assert q2["evidence"]["unreachable_versions"] == []
        assert q2["evidence"]["broken_reinstatements"] == []
        assert q2["evidence"]["authority_mismatches"] == []


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


def test_q2_lineage_graph_origin_to_current_reachable():
    """Q2 lineage graph: every target's current version is reachable from
    its origin by following parent_id chain backwards."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        graph = result.lineage_graph
        for target in sorted(result.final_state.keys()):
            current = graph.current_version_for(target)
            assert current is not None, f"{chain.chain_id}: no current version for {target}"
            path = graph.reach_origin(current.version_id)
            assert path is not None, (
                f"{chain.chain_id}: current version {current.version_id} "
                f"for {target} not reachable from origin"
            )
            # Path starts at current and ends at origin.
            origin = graph.nodes[path[-1]]
            assert origin.kind == "origin", (
                f"{chain.chain_id}: path for {target} ends at non-origin {origin.version_id}"
            )


def test_q2_lineage_graph_waiver_reinstate_edge():
    """Q2 lineage graph: GAMMA's waiver produces a restore node whose
    parent is the WAIVES state node (REINSTATES edge)."""
    result = reconstruct_chain(chain_gamma())
    graph = result.lineage_graph
    # Find the restore node for total_leverage_ratio.
    restore_nodes = [
        n for n in graph.nodes.values()
        if n.target == "financial_covenant.total_leverage_ratio" and n.kind == "restore"
    ]
    assert len(restore_nodes) == 1
    restore = restore_nodes[0]
    assert restore.edge_type == "REINSTATES"
    parent = graph.nodes[restore.parent_id]
    assert parent.kind == "state"
    assert parent.edge_type == "WAIVES"


def test_q2_lineage_graph_no_orphans_all_chains():
    """Q2 lineage graph: no orphan versions (parent_id references
    non-existent node) in any chain."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        assert result.lineage_graph.orphans() == [], (
            f"{chain.chain_id}: orphan versions {result.lineage_graph.orphans()}"
        )


# ---------------------------------------------------------------------------
# Q3: Does any unresolved instruction block authoritative promotion?
# ---------------------------------------------------------------------------


def test_q3_unresolved_blocks_promotion_all_chains():
    """Q3: Every step with own or inherited unresolved has
    is_authoritative=False. Steps with no unresolved and COMPLETE are
    authoritative. Chain-aware authority."""
    for chain in all_chains():
        result = reconstruct_chain(chain)
        q3 = result.questions["Q3_unresolved_blocks_promotion"]
        assert q3["pass"] is True, (
            f"{chain.chain_id} Q3 failed: {q3['evidence']}"
        )


def test_q3_beta_a1_own_unresolved_blocks_promotion():
    """BETA A1: RESTATE_SECTION is own unresolved → PARTIAL → not authoritative."""
    result = reconstruct_chain(chain_beta())
    a1 = result.steps[0]
    assert a1.execution_result.unresolved
    assert a1.is_authoritative is False
    assert a1.execution_result.status == ExecutionStatus.PARTIAL


def test_q3_beta_a2_inherited_unresolved_blocks_promotion():
    """BETA A2: no own unresolved, COMPLETE, but INHERITED unresolved from
    A1 → NOT authoritative. This is the key chain-aware authority test."""
    result = reconstruct_chain(chain_beta())
    a2 = result.steps[1]
    assert not a2.execution_result.unresolved  # no own unresolved
    assert a2.execution_result.status == ExecutionStatus.COMPLETE  # clean execution
    assert a2.is_authoritative is False  # but inherited unresolved blocks
    assert len(a2.inherited_unresolved) == 1


def test_q3_epsilon_a3_resolves_inherited_and_promotes():
    """EPSILON A3: targets the same commitment as A1's inherited unresolved
    → resolves it → A3 IS authoritative. Chain-aware authority has a
    resolution mechanism, not just blocking."""
    result = reconstruct_chain(chain_epsilon())
    a3 = result.steps[2]
    assert a3.execution_result.status == ExecutionStatus.COMPLETE
    assert len(a3.inherited_unresolved) == 0  # resolved
    assert a3.is_authoritative is True  # promoted after resolution


# ---------------------------------------------------------------------------
# Q4: Does reconstructed state exactly match ground truth?
# ---------------------------------------------------------------------------


def test_q4_ground_truth_match_all_chains():
    """Q4: Reconstructed final state exactly matches the oracle
    ground-truth for all five chains."""
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
    """BETA: exact match on both commitments (leverage 4.25, interest 2.5).
    State matches even though the chain is not authoritative."""
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


def test_q4_delta_exact_match():
    """DELTA: exact match — leverage 4.5 ACTIVE, interest 2.5. The
    intervening-amendment waiver restore works correctly."""
    result = reconstruct_chain(chain_delta())
    comp = result.comparison
    assert comp is not None
    assert comp.exact_match is True
    assert comp.matched_commitments == 2
    assert result.final_state["financial_covenant.total_leverage_ratio"].status == "ACTIVE"
    assert result.final_state["financial_covenant.total_leverage_ratio"].threshold == 4.5
    assert result.final_state["financial_covenant.interest_coverage"].threshold == 2.5


def test_q4_epsilon_exact_match():
    """EPSILON: exact match — leverage 4.25, interest 3.0."""
    result = reconstruct_chain(chain_epsilon())
    comp = result.comparison
    assert comp is not None
    assert comp.exact_match is True
    assert comp.matched_commitments == 2
    assert result.final_state["financial_covenant.interest_coverage"].threshold == 3.0


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
# Chain-aware authority unit tests
# ---------------------------------------------------------------------------


def test_is_resolved_by_same_target_resolves():
    """An inherited unresolved is resolved by an applied constructive
    instruction on the same target_key."""
    unresolved = AmendmentInstruction(
        order=2,
        instruction_type=InstructionType.RESTATE_SECTION,
        target_key="financial_covenant.interest_coverage",
    )
    applied = [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.interest_coverage",
            field="threshold",
            old_value=2.5,
            new_value=3.0,
        ),
    ]
    assert _is_resolved_by(unresolved, applied) is True


def test_is_resolved_by_different_target_does_not_resolve():
    """An inherited unresolved is NOT resolved by an applied instruction
    on a DIFFERENT target_key."""
    unresolved = AmendmentInstruction(
        order=2,
        instruction_type=InstructionType.RESTATE_SECTION,
        target_key="financial_covenant.interest_coverage",
    )
    applied = [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=4.25,
        ),
    ]
    assert _is_resolved_by(unresolved, applied) is False


def test_is_resolved_by_reference_change_does_not_resolve():
    """A RENUMBER_REFERENCE (non-constructive) does not resolve inherited
    unresolved even if it targets the same commitment."""
    unresolved = AmendmentInstruction(
        order=2,
        instruction_type=InstructionType.RESTATE_SECTION,
        target_key="financial_covenant.interest_coverage",
    )
    applied = [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RENUMBER_REFERENCE,
            target_key="financial_covenant.interest_coverage",
            old_value="Section 6.07",
            new_value="Section 6.08",
        ),
    ]
    assert _is_resolved_by(unresolved, applied) is False


# ---------------------------------------------------------------------------
# Chain-wide pending-restoration queue unit tests
# ---------------------------------------------------------------------------


def test_apply_due_restores_applies_expired_only():
    """_apply_due_restores applies restores whose valid_from <= at_time
    and keeps the rest in pending."""
    from datetime import datetime, timezone
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x",
            commitment_type="financial_covenant",
            threshold=4.0,
            status="WAIVED",
        ),
    }
    restore = CommitmentState(
        canonical_key="covenant.x",
        commitment_type="financial_covenant",
        threshold=4.0,
        status="ACTIVE",
        valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    pending = [
        PendingRestore(
            valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
            target="covenant.x",
            restore_state=restore,
        ),
    ]
    # Before July 1 → not due.
    out, still = _apply_due_restores(state, pending, datetime(2026, 3, 1, tzinfo=timezone.utc))
    assert out["covenant.x"].status == "WAIVED"
    assert len(still) == 1
    # At July 1 → due.
    out, still = _apply_due_restores(state, pending, datetime(2026, 7, 1, tzinfo=timezone.utc))
    assert out["covenant.x"].status == "ACTIVE"
    assert len(still) == 0


def test_apply_due_restores_chain_wide_multiple_pending():
    """_apply_due_restores handles multiple pending restores from different
    prior amendments — the chain-wide queue, not just the immediately
    preceding plan."""
    from datetime import datetime, timezone
    state = {
        "covenant.x": CommitmentState(
            canonical_key="covenant.x", commitment_type="financial_covenant",
            threshold=4.0, status="WAIVED",
        ),
        "covenant.y": CommitmentState(
            canonical_key="covenant.y", commitment_type="financial_covenant",
            threshold=3.0, status="WAIVED",
        ),
    }
    pending = [
        PendingRestore(
            valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
            target="covenant.x",
            restore_state=CommitmentState(
                canonical_key="covenant.x", commitment_type="financial_covenant",
                threshold=4.0, status="ACTIVE",
                valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
        ),
        PendingRestore(
            valid_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
            target="covenant.y",
            restore_state=CommitmentState(
                canonical_key="covenant.y", commitment_type="financial_covenant",
                threshold=3.0, status="ACTIVE",
                valid_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ),
        ),
    ]
    # At Aug 1: x's restore (Jul 1) is due, y's (Sep 1) is not.
    out, still = _apply_due_restores(state, pending, datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert out["covenant.x"].status == "ACTIVE"
    assert out["covenant.y"].status == "WAIVED"
    assert len(still) == 1
    assert still[0].target == "covenant.y"


# ---------------------------------------------------------------------------
# Lineage graph unit tests
# ---------------------------------------------------------------------------


def test_lineage_graph_reach_origin_simple_chain():
    """A simple origin → state chain is reachable from origin."""
    graph = LineageGraph()
    graph.add(VersionNode(
        version_id="S0:x", target="x", amendment_number=0, kind="origin",
        state=CommitmentState(canonical_key="x", commitment_type="c", threshold=1.0),
        parent_id=None, authority_amendment_number=0, edge_type="ORIGIN",
    ))
    graph.add(VersionNode(
        version_id="A1:x:state", target="x", amendment_number=1, kind="state",
        state=CommitmentState(canonical_key="x", commitment_type="c", threshold=2.0),
        parent_id="S0:x", authority_amendment_number=1, edge_type="MODIFIES",
    ))
    path = graph.reach_origin("A1:x:state")
    assert path == ["A1:x:state", "S0:x"]


def test_lineage_graph_broken_parent_detected():
    """A version whose parent doesn't exist is unreachable (returns None)."""
    graph = LineageGraph()
    graph.add(VersionNode(
        version_id="A1:x:state", target="x", amendment_number=1, kind="state",
        state=CommitmentState(canonical_key="x", commitment_type="c", threshold=2.0),
        parent_id="S0:x",  # doesn't exist
        authority_amendment_number=1, edge_type="MODIFIES",
    ))
    assert graph.reach_origin("A1:x:state") is None
    assert graph.orphans() == ["A1:x:state"]


def test_lineage_graph_cycle_detected():
    """A cycle in parent_id chain is detected (returns None)."""
    graph = LineageGraph()
    graph.add(VersionNode(
        version_id="A", target="x", amendment_number=1, kind="state",
        state=CommitmentState(canonical_key="x", commitment_type="c", threshold=2.0),
        parent_id="B", authority_amendment_number=1, edge_type="MODIFIES",
    ))
    graph.add(VersionNode(
        version_id="B", target="x", amendment_number=2, kind="state",
        state=CommitmentState(canonical_key="x", commitment_type="c", threshold=3.0),
        parent_id="A", authority_amendment_number=2, edge_type="MODIFIES",
    ))
    assert graph.reach_origin("A") is None  # cycle, no origin


# ---------------------------------------------------------------------------
# Aggregate smoke-test verdict
# ---------------------------------------------------------------------------


def test_all_four_questions_pass_all_five_chains():
    """The complete system smoke test: all four questions pass on all
    five chains. This is the gate for proceeding to the 25-issuer
    chain study."""
    results = [reconstruct_chain(c) for c in all_chains()]
    assert len(results) == 5

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
