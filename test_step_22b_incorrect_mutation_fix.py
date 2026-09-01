"""Step 22B regression: incorrect mutation detection must not fire
on chains with no ground truth.

When a chain's ground_truth_state is None or empty, every reconstructed
commitment would appear as "Extra" — a false positive that inflates
the incorrect mutation count.  Chains without ground truth cannot
have measurable incorrect mutations.

Reproduces the 5 false-positive incorrect mutations from Step 21B:
  STUDY-007 (1), STUDY-016 (2), HELD-010 (1), HELD-017 (1)

All 5 occurred because the pipeline compared the reconstructed state
against an empty/None ground truth, making every applied ADD mutation
appear as an "Extra" commitment.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from chain_reconstruction import AmendmentStep, IssuerChain
from models import AmendmentInstruction, CommitmentState
from semantic_pipeline_v2 import run_semantic_pipeline_v2


def _make_chain_with_no_gt(chain_id: str) -> IssuerChain:
    """Build a minimal chain with amendments but no ground truth."""
    original_state = {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            threshold=4.0,
            unit="ratio",
            status="ACTIVE",
        ),
    }
    amendments = [
        AmendmentStep(
            amendment_number=1,
            effective_at=datetime.now(UTC),
            instructions=[],
            source_document_path=None,
            description="Test amendment",
            pattern="incremental",
        ),
    ]
    return IssuerChain(
        chain_id=chain_id,
        issuer_name="Test Issuer",
        original_state=original_state,
        ground_truth_state=None,  # No ground truth
        amendments=amendments,
        comparison_at=datetime.now(UTC),
    )


def _make_chain_with_empty_gt(chain_id: str) -> IssuerChain:
    """Build a minimal chain with an empty dict ground truth."""
    original_state = {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            threshold=4.0,
            unit="ratio",
            status="ACTIVE",
        ),
    }
    amendments = [
        AmendmentStep(
            amendment_number=1,
            effective_at=datetime.now(UTC),
            instructions=[],
            source_document_path=None,
            description="Test amendment",
            pattern="incremental",
        ),
    ]
    return IssuerChain(
        chain_id=chain_id,
        issuer_name="Test Issuer",
        original_state=original_state,
        ground_truth_state={},  # Empty dict, not None
        amendments=amendments,
        comparison_at=datetime.now(UTC),
    )


def test_no_incorrect_mutations_when_gt_is_none():
    """Chains with None ground truth must report 0 incorrect mutations."""
    chain = _make_chain_with_no_gt("TEST-NO-GT")
    result = run_semantic_pipeline_v2(chain)
    assert len(result.incorrect_mutations) == 0, (
        f"Expected 0 incorrect mutations with None GT, got "
        f"{len(result.incorrect_mutations)}: {result.incorrect_mutations}"
    )


def test_no_incorrect_mutations_when_gt_is_empty():
    """Chains with empty dict ground truth must report 0 incorrect mutations.

    This reproduces the STUDY-016 pattern: ground_truth_state is an
    empty dict (not None), which caused all reconstructed commitments
    to appear as "Extra" false positives.
    """
    chain = _make_chain_with_empty_gt("TEST-EMPTY-GT")
    result = run_semantic_pipeline_v2(chain)
    assert len(result.incorrect_mutations) == 0, (
        f"Expected 0 incorrect mutations with empty GT, got "
        f"{len(result.incorrect_mutations)}: {result.incorrect_mutations}"
    )


def test_no_state_mismatches_when_gt_is_none():
    """Chains with None ground truth must report no state mismatches."""
    chain = _make_chain_with_no_gt("TEST-NO-GT-MISMATCH")
    result = run_semantic_pipeline_v2(chain)
    assert len(result.state_mismatches) == 0, (
        f"Expected 0 state mismatches with None GT, got "
        f"{len(result.state_mismatches)}: {result.state_mismatches}"
    )


def test_no_state_mismatches_when_gt_is_empty():
    """Chains with empty dict ground truth must report no state mismatches."""
    chain = _make_chain_with_empty_gt("TEST-EMPTY-GT-MISMATCH")
    result = run_semantic_pipeline_v2(chain)
    assert len(result.state_mismatches) == 0, (
        f"Expected 0 state mismatches with empty GT, got "
        f"{len(result.state_mismatches)}: {result.state_mismatches}"
    )
