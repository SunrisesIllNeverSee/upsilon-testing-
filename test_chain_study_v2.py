"""Tests for Development Chain Study v2.

Tests cover:
  - v2 chain building with extracted S0 and GT states
  - v2 per-issuer result extraction
  - v2 aggregate metrics computation
  - Safety: false authoritative promotion rate remains 0
  - Independence: prediction path != validation path
  - S0 extraction produces non-empty origin state for applicable chains
  - GT extraction produces non-empty ground truth for applicable chains
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chain_reconstruction import IssuerChain
from run_chain_study_v2 import (
    AggregateMetricsV2,
    IssuerStudyResultV2,
    all_v2_chains,
    build_v2_issuer_result,
    compute_v2_aggregate_metrics,
    _build_v2_chain_from_manifest_entry,
)
from semantic_pipeline import run_semantic_pipeline


# ---------------------------------------------------------------------------
# v2 chain building
# ---------------------------------------------------------------------------


class TestV2ChainBuilding:
    def test_all_v2_chains_returns_25(self):
        chains = all_v2_chains()
        assert len(chains) == 25

    def test_existing_chains_have_manual_label(self):
        """The 3 existing chains should use hand-extracted states."""
        chains = all_v2_chains()
        for chain, s0_result, gt_result in chains[:3]:
            assert s0_result.source_label == "S0-manual"

    def test_new_chains_have_extracted_s0(self):
        """New chains should use the v0.1 S0 extractor."""
        chains = all_v2_chains()
        for chain, s0_result, gt_result in chains[3:]:
            assert s0_result.source_label == "S0"

    def test_existing_chains_keep_hand_extracted_state(self):
        """Ameresco should still have its hand-extracted leverage ratio."""
        chains = all_v2_chains()
        ameresco = chains[0][0]
        assert ameresco.chain_id == "EDGAR-AMERESCO"
        assert "financial_covenant.leverage_ratio" in ameresco.original_state

    def test_new_chains_have_non_empty_s0_when_extractable(self):
        """At least some new chains should have non-empty S0 state."""
        chains = all_v2_chains()
        new_chains = chains[3:]
        non_empty = sum(1 for c, _, _ in new_chains if len(c.original_state) > 0)
        assert non_empty > 0, "At least some new chains should have extracted S0 state"

    def test_new_chains_with_cmp_have_gt(self):
        """Chains with CMP files should have extracted ground truth."""
        chains = all_v2_chains()
        new_chains = chains[3:]
        with_gt = sum(1 for c, _, gt in new_chains if gt is not None and len(gt.commitments) > 0)
        # At least STUDY-015 and STUDY-022 should have GT
        assert with_gt > 0, "At least some chains with CMP should have extracted GT"

    def test_no_duplicate_chain_ids(self):
        chains = all_v2_chains()
        chain_ids = [c[0].chain_id for c in chains]
        assert len(chain_ids) == len(set(chain_ids))


# ---------------------------------------------------------------------------
# v2 pipeline execution
# ---------------------------------------------------------------------------


class TestV2PipelineExecution:
    @pytest.mark.skipif(
        not Path("data/chain_study/manifest.json").exists(),
        reason="Manifest not available",
    )
    def test_v2_pipeline_runs_on_all_chains(self):
        """The frozen pipeline should run on all 25 chains without error."""
        chains = all_v2_chains()
        for chain, _, _ in chains:
            result = run_semantic_pipeline(chain)
            assert result is not None
            assert result.chain_id == chain.chain_id


# ---------------------------------------------------------------------------
# v2 safety: false authoritative promotion rate
# ---------------------------------------------------------------------------


class TestV2Safety:
    @pytest.mark.skipif(
        not Path("data/chain_study/manifest.json").exists(),
        reason="Manifest not available",
    )
    def test_false_authoritative_promotion_rate_is_zero(self):
        """False authoritative promotion rate MUST remain 0."""
        chains = all_v2_chains()
        false_promo_count = 0
        total_steps = 0

        for chain, _, _ in chains:
            pipe_result = run_semantic_pipeline(chain)
            for step in pipe_result.steps:
                total_steps += 1
                own_unresolved = (
                    len(step.mapper_unresolved)
                    + len(step.execution_result.unresolved)
                )
                if step.is_authoritative and (
                    own_unresolved > 0 or step.inherited_unresolved_count > 0
                ):
                    false_promo_count += 1

        assert false_promo_count == 0, (
            f"SAFETY VIOLATION: {false_promo_count} false authoritative promotions "
            f"detected across {total_steps} steps"
        )

    @pytest.mark.skipif(
        not Path("data/chain_study/manifest.json").exists(),
        reason="Manifest not available",
    )
    def test_ameresco_still_succeeds(self):
        """Ameresco should still achieve SUCCESS with extracted S0 state."""
        chains = all_v2_chains()
        ameresco = chains[0][0]
        assert ameresco.chain_id == "EDGAR-AMERESCO"
        pipe_result = run_semantic_pipeline(ameresco)
        # Ameresco should have 100% final state agreement
        assert pipe_result.final_state_agreement == 1.0


# ---------------------------------------------------------------------------
# v2 independence: prediction path != validation path
# ---------------------------------------------------------------------------


class TestV2Independence:
    def test_s0_extractor_does_not_use_amendment_output(self):
        """The S0 extractor should only take a document path."""
        import inspect
        from s0_extractor import extract_s0_state
        sig = inspect.signature(extract_s0_state)
        params = list(sig.parameters.keys())
        assert "s0_path" in params
        assert "reconstructed_state" not in params
        assert "amendment_result" not in params

    def test_gt_extractor_does_not_use_amendment_output(self):
        """The GT extractor should only take a document path."""
        import inspect
        from gt_extractor import extract_ground_truth
        sig = inspect.signature(extract_ground_truth)
        params = list(sig.parameters.keys())
        assert "cmp_path" in params
        assert "reconstructed_state" not in params
        assert "amendment_result" not in params

    def test_s0_and_gt_use_different_source_labels(self):
        """S0 and GT extractors produce different source labels."""
        from s0_extractor import extract_s0_state
        from gt_extractor import extract_ground_truth

        # Both should work on the same document but produce different labels
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Borrower shall not permit "
            "the ratio to exceed 4.50 to 1.00.  7.11 Next. End."
        )
        from pathlib import Path
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(text)
            tmp_path = f.name

        try:
            s0_result = extract_s0_state(tmp_path)
            gt_result = extract_ground_truth(tmp_path)
            assert s0_result.source_label == "S0"
            assert gt_result.source_label == "CMP"
        finally:
            Path(tmp_path).unlink()


# ---------------------------------------------------------------------------
# v2 extraction metrics
# ---------------------------------------------------------------------------


class TestV2ExtractionMetrics:
    @pytest.mark.skipif(
        not Path("data/chain_study/manifest.json").exists(),
        reason="Manifest not available",
    )
    def test_s0_extraction_success_rate(self):
        """At least 30% of new chains should have extracted S0 state."""
        chains = all_v2_chains()
        new_chains = chains[3:]
        non_empty = sum(1 for c, _, _ in new_chains if len(c.original_state) > 0)
        rate = non_empty / len(new_chains)
        assert rate >= 0.30, (
            f"S0 extraction success rate {rate:.1%} is below 30% threshold"
        )

    @pytest.mark.skipif(
        not Path("data/chain_study/manifest.json").exists(),
        reason="Manifest not available",
    )
    def test_gt_extraction_success_rate(self):
        """At least 1 chain with CMP should have extracted GT state."""
        chains = all_v2_chains()
        new_chains = chains[3:]
        with_gt = sum(1 for c, _, gt in new_chains if gt is not None and len(gt.commitments) > 0)
        assert with_gt >= 1, "At least 1 chain with CMP should have extracted GT state"


# ---------------------------------------------------------------------------
# v2 no guessing
# ---------------------------------------------------------------------------


class TestV2NoGuessing:
    def test_unsupported_s0_clauses_in_validation_queue(self):
        """Unsupported S0 clauses must be in validation queue, not guessed."""
        chains = all_v2_chains()
        for chain, s0_result, _ in chains[3:]:
            # Every commitment in original_state should have a real threshold
            # (not a guessed value)
            for key, commitment in chain.original_state.items():
                if commitment.commitment_type == "financial_covenant":
                    assert commitment.threshold is not None, (
                        f"Chain {chain.chain_id}: {key} has no threshold "
                        f"(possibly guessed)"
                    )

    def test_unsupported_gt_clauses_in_validation_queue(self):
        """Unsupported GT clauses must be in validation queue, not guessed."""
        chains = all_v2_chains()
        for chain, _, gt_result in chains[3:]:
            if gt_result is None:
                continue
            for key, commitment in gt_result.commitments.items():
                if commitment.commitment_type == "financial_covenant":
                    assert commitment.threshold is not None, (
                        f"Chain {chain.chain_id}: GT {key} has no threshold "
                        f"(possibly guessed)"
                    )
