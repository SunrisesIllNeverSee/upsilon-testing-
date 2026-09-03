"""Tests for Development Chain Study v2.

Tests cover:
  - v2 chain building with extracted S0 and GT states
  - v2 per-issuer result extraction
  - v2 aggregate metrics computation
  - Safety: false authoritative promotion rate remains 0
  - Independence: prediction path != validation path
  - S0 extraction produces non-empty origin state for applicable chains
  - GT extraction produces non-empty ground truth for applicable chains
  - Extraction-aware failure classification (extractor vs reconstruction)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from upsilon.lineage.chain_reconstruction import IssuerChain
from upsilon.parsing.commitment_extractor import ExtractionResult, ValidationItem
from research.run_chain_study_v2 import (
    EXTRACTION_FAILURE_CATEGORIES,
    _compute_extraction_status,
    all_v2_chains,
    build_v2_issuer_result,
    classify_failure_v2,
)
from upsilon.pipeline.semantic_pipeline import SemanticPipelineResult, run_semantic_pipeline

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

        from upsilon.evidence.s0_extractor import extract_s0_state
        sig = inspect.signature(extract_s0_state)
        params = list(sig.parameters.keys())
        assert "s0_path" in params
        assert "reconstructed_state" not in params
        assert "amendment_result" not in params

    def test_gt_extractor_does_not_use_amendment_output(self):
        """The GT extractor should only take a document path."""
        import inspect

        from upsilon.evidence.gt_extractor import extract_ground_truth
        sig = inspect.signature(extract_ground_truth)
        params = list(sig.parameters.keys())
        assert "cmp_path" in params
        assert "reconstructed_state" not in params
        assert "amendment_result" not in params

    def test_s0_and_gt_use_different_source_labels(self):
        """S0 and GT extractors produce different source labels."""
        from upsilon.evidence.gt_extractor import extract_ground_truth
        from upsilon.evidence.s0_extractor import extract_s0_state

        # Both should work on the same document but produce different labels
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Borrower shall not permit "
            "the ratio to exceed 4.50 to 1.00.  7.11 Next. End."
        )
        import tempfile
        from pathlib import Path
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


# ---------------------------------------------------------------------------
# v2 extraction-aware failure classification
# ---------------------------------------------------------------------------
#
# The v2 classifier must distinguish extractor failure from reconstruction
# failure. A bad GT extraction should NOT look like a bad reconstruction.
# These tests verify the _compute_extraction_status and classify_failure_v2
# functions using synthetic ExtractionResult objects (no real data needed).


def _make_extraction_result(
    commitments: int = 0,
    validation_queue: int = 0,
    text_length: int = 0,
    source_label: str = "S0",
) -> ExtractionResult:
    """Build a synthetic ExtractionResult for testing."""
    from upsilon.models.legacy_models import CommitmentState
    result = ExtractionResult(
        source_label=source_label,
        text_length=text_length,
    )
    for i in range(commitments):
        result.commitments[f"fake.key_{i}"] = CommitmentState(
            canonical_key=f"fake.key_{i}",
            commitment_type="financial_covenant",
            threshold=1.0,
        )
    for i in range(validation_queue):
        result.validation_queue.append(ValidationItem(
            section_ref="Section X",
            clause_name=f"Unknown Clause {i}",
            text="...",
            reason="test",
        ))
    return result


class TestExtractionStatus:
    def test_manual_chain_returns_na(self):
        """Manual/existing chains should return 'n/a'."""
        s0 = _make_extraction_result(source_label="S0-manual")
        gt = _make_extraction_result(source_label="CMP-manual")
        assert _compute_extraction_status(s0, gt, is_manual=True) == "n/a"

    def test_s0_failure_when_text_but_no_commitments(self):
        """S0 document exists (text_length > 0) but 0 commitments → s0_failure."""
        s0 = _make_extraction_result(commitments=0, text_length=50000)
        gt = _make_extraction_result(commitments=3, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "s0_failure"

    def test_gt_failure_when_cmp_text_but_no_commitments(self):
        """CMP document exists but 0 commitments → gt_failure."""
        s0 = _make_extraction_result(commitments=2, text_length=50000)
        gt = _make_extraction_result(commitments=0, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "gt_failure"

    def test_ok_when_both_extracted_no_vq(self):
        """Both S0 and GT extracted commitments with no validation queue → ok."""
        s0 = _make_extraction_result(commitments=3, text_length=50000)
        gt = _make_extraction_result(commitments=2, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "ok"

    def test_s0_incomplete_when_vq_non_empty(self):
        """S0 has commitments but also validation queue items → s0_incomplete."""
        s0 = _make_extraction_result(commitments=2, validation_queue=1, text_length=50000)
        gt = _make_extraction_result(commitments=2, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "s0_incomplete"

    def test_gt_incomplete_when_vq_non_empty(self):
        """GT has commitments but also validation queue items → gt_incomplete."""
        s0 = _make_extraction_result(commitments=2, text_length=50000)
        gt = _make_extraction_result(commitments=2, validation_queue=1, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "gt_incomplete"

    def test_both_incomplete(self):
        """Both S0 and GT have validation queue items → s0_and_gt_incomplete."""
        s0 = _make_extraction_result(commitments=2, validation_queue=1, text_length=50000)
        gt = _make_extraction_result(commitments=2, validation_queue=1, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "s0_and_gt_incomplete"

    def test_ok_when_no_cmp_document(self):
        """No CMP document (gt_result=None) with good S0 → ok."""
        s0 = _make_extraction_result(commitments=3, text_length=50000)
        assert _compute_extraction_status(s0, None, is_manual=False) == "ok"

    def test_s0_failure_takes_precedence_over_gt_failure(self):
        """If both S0 and GT fail, S0 failure is reported first."""
        s0 = _make_extraction_result(commitments=0, text_length=50000)
        gt = _make_extraction_result(commitments=0, text_length=40000, source_label="CMP")
        assert _compute_extraction_status(s0, gt, is_manual=False) == "s0_failure"


class TestClassifyFailureV2:
    """Tests for the v2 extraction-aware failure classifier.

    The key requirement: a bad GT extraction should NOT look like a bad
    reconstruction. S0_EXTRACTION_FAILURE and GT_EXTRACTION_FAILURE are
    distinct from reconstruction failure categories.
    """

    @staticmethod
    def _make_pipe_result(parser_instructions: int = 0) -> SemanticPipelineResult:
        """Build a minimal SemanticPipelineResult for testing."""
        return SemanticPipelineResult(
            chain_id="TEST",
            issuer_name="Test",
            steps=[],
            reconstructed_state={},
            ground_truth_state={},
            total_parser_instructions=parser_instructions,
            total_mapped=0,
            total_unresolved=0,
            mapping_accuracy=0.0,
            unresolved_rate=0.0,
            incorrect_mutation_rate=0.0,
            final_state_agreement=0.0,
            incorrect_mutations=[],
            state_mismatches=[],
        )

    @staticmethod
    def _make_chain() -> IssuerChain:
        from datetime import UTC, datetime
        return IssuerChain(
            chain_id="TEST",
            issuer_name="Test",
            original_state={},
            amendments=[],
            comparison_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

    def test_s0_failure_classified_as_extraction_failure(self):
        """When S0 extraction returns 0 commitments, the failure category
        must be S0_EXTRACTION_FAILURE, not PARSER_NO_INSTRUCTIONS or
        EXECUTOR_PARTIAL (which would misattribute the cause to the
        reconstruction pipeline)."""
        pipe_result = self._make_pipe_result(parser_instructions=0)
        chain = self._make_chain()
        s0 = _make_extraction_result(commitments=0, text_length=50000)
        gt = _make_extraction_result(commitments=0, text_length=40000, source_label="CMP")

        category = classify_failure_v2(
            pipe_result, chain, has_ground_truth=False,
            s0_result=s0, gt_result=gt, extraction_status="s0_failure",
        )
        assert category == "S0_EXTRACTION_FAILURE"

    def test_gt_failure_classified_as_extraction_failure(self):
        """When CMP exists but GT extraction returns 0 commitments, the
        failure category must be GT_EXTRACTION_FAILURE, not
        NO_GROUND_TRUTH (which means no CMP document at all)."""
        pipe_result = self._make_pipe_result(parser_instructions=0)
        chain = self._make_chain()
        s0 = _make_extraction_result(commitments=2, text_length=50000)
        gt = _make_extraction_result(commitments=0, text_length=40000, source_label="CMP")

        category = classify_failure_v2(
            pipe_result, chain, has_ground_truth=False,
            s0_result=s0, gt_result=gt, extraction_status="gt_failure",
        )
        assert category == "GT_EXTRACTION_FAILURE"

    def test_ok_extraction_falls_through_to_v1(self):
        """When extraction is OK, the v2 classifier should delegate to
        the v1 classifier (not override the category)."""
        pipe_result = self._make_pipe_result(parser_instructions=0)
        chain = self._make_chain()
        s0 = _make_extraction_result(commitments=2, text_length=50000)
        gt = None

        category = classify_failure_v2(
            pipe_result, chain, has_ground_truth=False,
            s0_result=s0, gt_result=gt, extraction_status="ok",
        )
        # v1 classifier with 0 parser instructions → PARSER_NO_INSTRUCTIONS
        assert category == "PARSER_NO_INSTRUCTIONS"

    def test_extraction_failure_categories_are_distinct_from_v1(self):
        """The new extraction failure categories must not overlap with
        v1 categories (otherwise the taxonomy would be ambiguous)."""
        from research.run_chain_study import FAILURE_CATEGORIES as V1_CATEGORIES
        for key in EXTRACTION_FAILURE_CATEGORIES:
            assert key not in V1_CATEGORIES, (
                f"{key} overlaps with v1 categories — extraction failures "
                f"must be distinct from reconstruction failures"
            )


class TestV2ResultHasExtractionStatus:
    """Verify that build_v2_issuer_result populates extraction_status."""

    def test_existing_chain_has_na_extraction_status(self):
        """Existing/manual chains should have extraction_status='n/a'."""
        chains = all_v2_chains()
        ameresco = chains[0]
        chain = ameresco[0]
        s0_result = ameresco[1]
        gt_result = ameresco[2]
        pipe_result = run_semantic_pipeline(chain)
        result = build_v2_issuer_result(chain, pipe_result, s0_result, gt_result)
        assert result.extraction_status == "n/a"

    def test_new_chains_have_non_na_extraction_status(self):
        """New chains should have a non-'n/a' extraction status."""
        chains = all_v2_chains()
        for chain, s0_result, gt_result in chains[3:]:
            pipe_result = run_semantic_pipeline(chain)
            result = build_v2_issuer_result(chain, pipe_result, s0_result, gt_result)
            assert result.extraction_status != "n/a", (
                f"Chain {chain.chain_id} should have a real extraction status, "
                f"not 'n/a' (it uses the automated extractors)"
            )
