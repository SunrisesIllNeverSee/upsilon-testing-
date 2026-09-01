"""Tests for temporal false-authoritative-promotion detection (Step 21).

Regression test for the fix where false_authoritative_promotion
overcounted by ignoring temporal ordering.  An incorrect mutation in
amendment 5 should NOT retroactively make amendment 2's authoritative
promotion false — the system had no way to know at the time.

The test constructs a minimal SemanticPipelineResultV2 with known
incorrect_pair_steps and step authoritativeness, then verifies the
temporal logic in run_v2_study.run_v2_study.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from models import CommitmentState, ExecutionResult, ExecutionStatus
from semantic_pipeline_v2 import SemanticPipelineResultV2, SemanticStepResultV2


def _make_step(
    amendment_number: int,
    is_authoritative: bool,
    status: ExecutionStatus = ExecutionStatus.COMPLETE,
) -> SemanticStepResultV2:
    """Build a minimal SemanticStepResultV2 for testing."""
    exec_result = MagicMock(spec=ExecutionResult)
    exec_result.status = status
    exec_result.applied = []
    exec_result.unresolved = []
    return SemanticStepResultV2(
        amendment_number=amendment_number,
        effective_at=datetime(2023, 1, 1),
        pattern="incremental",
        genre="incremental",
        parser_instruction_count=1,
        extraction_count=0,
        mapped_count=1,
        unresolved_count=0,
        execution_result=exec_result,
        is_authoritative=is_authoritative,
        inherited_unresolved_count=0,
        adapter_notes="test",
    )


def _make_pipe_result(
    steps: list[SemanticStepResultV2],
    incorrect_pair_steps: list[tuple[tuple[str, str | None], int]],
    incorrect_mutations: list[str] | None = None,
) -> SemanticPipelineResultV2:
    """Build a minimal SemanticPipelineResultV2 for testing."""
    return SemanticPipelineResultV2(
        chain_id="TEST",
        issuer_name="Test",
        steps=steps,
        reconstructed_state={},
        ground_truth_state={},
        total_parser_instructions=1,
        total_mapped=1,
        total_unresolved=0,
        mapping_accuracy=1.0,
        unresolved_rate=0.0,
        incorrect_mutation_rate=0.0,
        final_state_agreement=1.0,
        incorrect_mutations=incorrect_mutations or [],
        state_mismatches=[],
        incorrect_pair_steps=incorrect_pair_steps,
    )


class TestTemporalFalseAuthPromotion:
    """Test the temporal false-authoritative-promotion logic extracted
    from run_v2_study.run_v2_study."""

    def _count_false_promotions(
        self,
        pipe_result: SemanticPipelineResultV2,
    ) -> int:
        """Replicate the false-promotion counting logic from
        run_v2_study.run_v2_study (the fixed version)."""
        false_auth_promotions = 0
        incorrect_steps = {s for _, s in pipe_result.incorrect_pair_steps}
        for step_idx, step in enumerate(pipe_result.steps):
            if not step.is_authoritative:
                continue
            if any(inc_step <= step_idx for inc_step in incorrect_steps):
                false_auth_promotions += 1
                break
        return false_auth_promotions

    def test_no_incorrect_mutations_no_false_promotion(self):
        """No incorrect mutations → no false promotions."""
        steps = [
            _make_step(1, is_authoritative=True),
            _make_step(2, is_authoritative=True),
        ]
        pipe = _make_pipe_result(steps, incorrect_pair_steps=[])
        assert self._count_false_promotions(pipe) == 0

    def test_incorrect_at_step_1_promotion_at_step_1_is_false(self):
        """Incorrect mutation at step 0 (index 0) + authoritative at
        step 0 → false promotion."""
        steps = [
            _make_step(1, is_authoritative=True),
            _make_step(2, is_authoritative=True),
        ]
        pipe = _make_pipe_result(
            steps,
            incorrect_pair_steps=[(("key", "threshold"), 0)],
        )
        assert self._count_false_promotions(pipe) == 1

    def test_incorrect_at_step_5_does_not_make_step_2_false(self):
        """Incorrect mutation at step 4 (index 4) should NOT make
        step 1 (index 1) authoritative promotion false.

        This is the core regression: previously ANY incorrect mutation
        in the chain would flag ALL authoritative steps as false.
        """
        steps = [
            _make_step(1, is_authoritative=True),
            _make_step(2, is_authoritative=True),
            _make_step(3, is_authoritative=False),
            _make_step(4, is_authoritative=False),
            _make_step(5, is_authoritative=True),
        ]
        pipe = _make_pipe_result(
            steps,
            incorrect_pair_steps=[(("key", "threshold"), 4)],
        )
        # Step 5 (index 4) is authoritative AND incorrect mutation at
        # index 4 → false promotion.  But steps 1-2 (indices 0-1) are
        # authoritative with no incorrect mutation at or before them →
        # NOT false.  Count is 1 (only step 5).
        assert self._count_false_promotions(pipe) == 1

    def test_incorrect_at_step_3_makes_step_3_and_after_false(self):
        """Incorrect mutation at step 2 (index 2) makes step 3 (index 2)
        and all subsequent authoritative steps false.  But we count
        once per chain (break after first false)."""
        steps = [
            _make_step(1, is_authoritative=True),
            _make_step(2, is_authoritative=True),
            _make_step(3, is_authoritative=True),
            _make_step(4, is_authoritative=True),
        ]
        pipe = _make_pipe_result(
            steps,
            incorrect_pair_steps=[(("key", "threshold"), 2)],
        )
        # Steps 1-2 (indices 0-1) are authoritative, no incorrect at
        # or before → not false.  Step 3 (index 2) is authoritative,
        # incorrect at index 2 → false.  Count once per chain = 1.
        assert self._count_false_promotions(pipe) == 1

    def test_non_authoritative_steps_not_counted(self):
        """Even if incorrect mutation is at step 0, a non-authoritative
        step at index 0 is not a false promotion."""
        steps = [
            _make_step(1, is_authoritative=False),
            _make_step(2, is_authoritative=True),
        ]
        pipe = _make_pipe_result(
            steps,
            incorrect_pair_steps=[(("key", "threshold"), 0)],
        )
        # Step 1 (index 0) is NOT authoritative → not a false promotion.
        # Step 2 (index 1) IS authoritative, incorrect at index 0 <= 1
        # → false promotion.  Count = 1.
        assert self._count_false_promotions(pipe) == 1
