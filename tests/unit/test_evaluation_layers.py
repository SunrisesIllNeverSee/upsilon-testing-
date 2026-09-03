"""Tests for the three-layer evaluation system.

Tests cover:
  - Extraction layer metric computation (S0/GT success rates, coverage)
  - Transformation layer metric computation (mapping coverage/precision, unresolved rate)
  - Reconstruction layer metric computation (conditional vs unconditional)
  - Metric separation (no layer collapsed into another)
  - Unresolved rate is computed and reported
  - Conditional reconstruction only counts measurable chains
  - Integration with real failure matrix data
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.methodology.evaluation_layers import (
    ExtractionLayerMetrics,
    ReconstructionLayerMetrics,
    TransformationLayerMetrics,
    compute_extraction_metrics,
    compute_reconstruction_metrics,
    compute_transformation_metrics,
    render_evaluation_report,
)

# ---------------------------------------------------------------------------
# Synthetic data fixtures
# ---------------------------------------------------------------------------


def _make_chain(
    chain_id: str,
    *,
    s0_commitments: int = 0,
    s0_vq: int = 0,
    gt_commitments: int = 0,
    gt_vq: int = 0,
    gt_source: str = "CMP",
    parser_instructions: int = 0,
    mapped: int = 0,
    unresolved: int = 0,
    incorrect: int = 0,
    has_gt: bool = False,
    final_agreement: float | None = None,
    supported_agreement: float | None = None,
    lineage_complete: bool = True,
    causes: dict[str, bool] | None = None,
) -> dict:
    """Build a synthetic chain dict matching the failure matrix schema."""
    if causes is None:
        causes = {}
    return {
        "chain_id": chain_id,
        "issuer_name": f"Issuer {chain_id}",
        "v2_failure_category": "SUCCESS" if s0_commitments > 0 and final_agreement == 1.0 else "FAILURE",
        "extraction_status": "ok" if s0_commitments > 0 else "s0_failure",
        "s0_extraction_commitments": s0_commitments,
        "s0_extraction_validation_queue": s0_vq,
        "s0_extraction_text_length": 50000,
        "gt_extraction_commitments": gt_commitments,
        "gt_extraction_validation_queue": gt_vq,
        "gt_extraction_text_length": 50000,
        "parser_detected_instructions": parser_instructions,
        "semantic_mapped_instructions": mapped,
        "unresolved_instructions": unresolved,
        "incorrect_automatic_mutations": incorrect,
        "chain_authoritative": False,
        "lineage_complete": lineage_complete,
        "final_state_exact_agreement": final_agreement,
        "supported_field_agreement": supported_agreement,
        "has_ground_truth": has_gt,
        "gt_extraction_source": gt_source,
        "causes": causes,
        "primary_layer": "none",
    }


def _make_failure_matrix(chains: list[dict]) -> dict:
    return {
        "study": "test",
        "frozen_tag": "test",
        "frozen_commit": "test",
        "causes": {},
        "chains": chains,
        "aggregate_cause_counts": {},
        "layer_counts": {},
    }


def _make_v2_results(false_promo_count: int = 0, false_promo_rate: float = 0.0) -> dict:
    return {
        "study": "test",
        "aggregate_metrics": {
            "false_authoritative_promotion_count": false_promo_count,
            "false_authoritative_promotion_rate": false_promo_rate,
        },
    }


# ---------------------------------------------------------------------------
# Extraction layer
# ---------------------------------------------------------------------------


class TestExtractionMetrics:
    def test_s0_success_rate(self):
        chains = [
            _make_chain("C1", s0_commitments=5, gt_source="none"),
            _make_chain("C2", s0_commitments=0, gt_source="none", causes={"S0_EXTRACTION_FAILURE": True}),
            _make_chain("C3", s0_commitments=3, gt_source="none"),
            _make_chain("C4", s0_commitments=0, gt_source="none", causes={"S0_DISCOVERY_FAILURE": True}),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_extraction_metrics(v2, fm)
        assert m.s0_chains_attempted == 4
        assert m.s0_chains_succeeded == 2
        assert m.s0_extraction_success_rate == 0.5

    def test_s0_discovery_vs_extraction_failures(self):
        chains = [
            _make_chain("C1", s0_commitments=0, gt_source="none",
                        causes={"S0_DISCOVERY_FAILURE": True}),
            _make_chain("C2", s0_commitments=0, gt_source="none",
                        causes={"S0_EXTRACTION_FAILURE": True}),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_extraction_metrics(v2, fm)
        assert m.s0_discovery_failures == 1
        assert m.s0_extraction_failures == 1

    def test_gt_success_rate_only_counts_cmp_chains(self):
        """GT success rate denominator should only be chains with CMP documents."""
        chains = [
            _make_chain("C1", s0_commitments=5, gt_commitments=3, gt_source="CMP"),
            _make_chain("C2", s0_commitments=5, gt_commitments=0, gt_source="CMP",
                        causes={"GT_EXTRACTION_FAILURE": True}),
            _make_chain("C3", s0_commitments=5, gt_source="none"),  # No CMP — excluded
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_extraction_metrics(v2, fm)
        assert m.gt_chains_with_cmp == 2  # Only C1 and C2
        assert m.gt_chains_succeeded == 1
        assert m.gt_extraction_success_rate == 0.5

    def test_manual_chains_excluded_from_extraction_metrics(self):
        """Manual chains (hand-extracted) should not count in S0/GT extraction metrics."""
        chains = [
            _make_chain("MANUAL", s0_commitments=0, gt_commitments=0, gt_source="manual"),
            _make_chain("AUTO", s0_commitments=5, gt_commitments=3, gt_source="CMP"),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_extraction_metrics(v2, fm)
        assert m.s0_chains_attempted == 1  # Only AUTO
        assert m.gt_chains_with_cmp == 1

    def test_s0_coverage(self):
        chains = [
            _make_chain("C1", s0_commitments=5, s0_vq=5, gt_source="none"),  # 50% coverage
            _make_chain("C2", s0_commitments=10, s0_vq=0, gt_source="none"),  # 100% coverage
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_extraction_metrics(v2, fm)
        # avg coverage = (5+10) / (5+5+10+0) = 15/20 = 0.75
        assert m.s0_avg_coverage == pytest.approx(0.75)

    def test_empty_chains_returns_zero_rates(self):
        fm = _make_failure_matrix([])
        v2 = _make_v2_results()
        m = compute_extraction_metrics(v2, fm)
        assert m.s0_extraction_success_rate == 0.0
        assert m.gt_extraction_success_rate == 0.0


# ---------------------------------------------------------------------------
# Transformation layer
# ---------------------------------------------------------------------------


class TestTransformationMetrics:
    def test_mapping_coverage(self):
        chains = [
            _make_chain("C1", parser_instructions=10, mapped=5, unresolved=5),
            _make_chain("C2", parser_instructions=20, mapped=10, unresolved=10),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_transformation_metrics(v2, fm)
        assert m.total_parser_instructions == 30
        assert m.total_mapped_instructions == 15
        assert m.semantic_mapping_coverage == pytest.approx(0.5)

    def test_unresolved_rate(self):
        """The unresolved_rate metric must be computed (unresolved / parser)."""
        chains = [
            _make_chain("C1", parser_instructions=10, mapped=5, unresolved=5),
            _make_chain("C2", parser_instructions=20, mapped=10, unresolved=10),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_transformation_metrics(v2, fm)
        assert m.total_unresolved == 15
        assert m.total_parser_instructions == 30
        assert m.unresolved_rate == pytest.approx(0.5)

    def test_unresolved_rate_zero_when_no_parser_instructions(self):
        chains = [
            _make_chain("C1", parser_instructions=0, mapped=0, unresolved=0),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_transformation_metrics(v2, fm)
        assert m.unresolved_rate == 0.0

    def test_mapping_precision(self):
        """Precision = (mapped - incorrect) / mapped."""
        chains = [
            _make_chain("C1", parser_instructions=10, mapped=5, unresolved=5, incorrect=1),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_transformation_metrics(v2, fm)
        # precision = (5 - 1) / 5 = 0.8
        assert m.semantic_mapping_precision == pytest.approx(0.8)

    def test_incorrect_mutation_rate(self):
        chains = [
            _make_chain("C1", parser_instructions=10, mapped=5, unresolved=5, incorrect=2),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_transformation_metrics(v2, fm)
        assert m.incorrect_mutation_rate == pytest.approx(0.4)  # 2/5

    def test_parser_failure_count(self):
        chains = [
            _make_chain("C1", parser_instructions=0, causes={"PARSER_FAILURE": True}),
            _make_chain("C2", parser_instructions=5),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_transformation_metrics(v2, fm)
        assert m.parser_failure_count == 1
        assert m.chains_with_zero_parser_instructions == 1
        assert m.chains_with_parser_instructions == 1


# ---------------------------------------------------------------------------
# Reconstruction layer
# ---------------------------------------------------------------------------


class TestReconstructionMetrics:
    def test_conditional_reconstruction_only_measurable_chains(self):
        """Conditional rate should only count chains with valid S0 + GT (or manual)."""
        chains = [
            # Manual chain with exact match — measurable
            _make_chain("M1", gt_source="manual", has_gt=True, final_agreement=1.0),
            # Auto chain with S0+GT — measurable
            _make_chain("A1", s0_commitments=5, gt_commitments=3, gt_source="CMP",
                        has_gt=True, final_agreement=1.0),
            # Auto chain with S0 but no GT — not measurable
            _make_chain("A2", s0_commitments=5, gt_commitments=0, gt_source="CMP",
                        has_gt=True, final_agreement=0.0),
            # Auto chain with no S0 — not measurable
            _make_chain("A3", s0_commitments=0, gt_commitments=3, gt_source="CMP",
                        has_gt=True, final_agreement=0.0),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_reconstruction_metrics(v2, fm)
        assert m.chains_with_gt_total == 4
        assert m.chains_measurable == 2  # M1 and A1
        assert m.chains_exact_match == 2
        assert m.conditional_exact_reconstruction_rate == 1.0

    def test_unconditional_includes_extraction_failures(self):
        """Unconditional rate includes ALL chains with GT, even if extraction failed."""
        chains = [
            _make_chain("A1", s0_commitments=5, gt_commitments=3, gt_source="CMP",
                        has_gt=True, final_agreement=1.0),
            # Extraction failed — not measurable but counted in unconditional
            _make_chain("A2", s0_commitments=0, gt_commitments=0, gt_source="CMP",
                        has_gt=True, final_agreement=0.0),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_reconstruction_metrics(v2, fm)
        assert m.chains_with_gt_total == 2
        assert m.chains_measurable == 1
        # Unconditional: 1 exact match out of 2 = 0.5
        assert m.unconditional_exact_reconstruction_rate == 0.5
        # Conditional: 1 exact match out of 1 measurable = 1.0
        assert m.conditional_exact_reconstruction_rate == 1.0

    def test_conditional_and_unconditional_are_separate(self):
        """The two rates must not be collapsed into one number."""
        chains = [
            _make_chain("A1", s0_commitments=5, gt_commitments=3, gt_source="CMP",
                        has_gt=True, final_agreement=1.0),
            _make_chain("A2", s0_commitments=5, gt_commitments=3, gt_source="CMP",
                        has_gt=True, final_agreement=0.0),
            _make_chain("A3", s0_commitments=0, gt_commitments=0, gt_source="CMP",
                        has_gt=True, final_agreement=0.0),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_reconstruction_metrics(v2, fm)
        assert m.conditional_exact_reconstruction_rate != m.unconditional_exact_reconstruction_rate

    def test_lineage_completeness(self):
        chains = [
            _make_chain("C1", lineage_complete=True),
            _make_chain("C2", lineage_complete=True),
            _make_chain("C3", lineage_complete=False),
        ]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_reconstruction_metrics(v2, fm)
        assert m.lineage_complete_count == 2
        assert m.lineage_completeness_rate == pytest.approx(2 / 3)

    def test_false_authoritative_promotion_from_v2_aggregate(self):
        chains = [_make_chain("C1")]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results(false_promo_count=0, false_promo_rate=0.0)
        m = compute_reconstruction_metrics(v2, fm)
        assert m.false_authoritative_promotion_count == 0
        assert m.false_authoritative_promotion_rate == 0.0

    def test_no_gt_chains_returns_zero(self):
        chains = [_make_chain("C1", has_gt=False, gt_source="none")]
        fm = _make_failure_matrix(chains)
        v2 = _make_v2_results()
        m = compute_reconstruction_metrics(v2, fm)
        assert m.chains_with_gt_total == 0
        assert m.conditional_exact_reconstruction_rate == 0.0
        assert m.unconditional_exact_reconstruction_rate == 0.0


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


class TestReportRendering:
    def test_report_contains_all_three_layers(self):
        extraction = ExtractionLayerMetrics()
        transformation = TransformationLayerMetrics()
        reconstruction = ReconstructionLayerMetrics()
        report = render_evaluation_report(extraction, transformation, reconstruction)
        assert "Layer A: Extraction" in report
        assert "Layer B: Transformation" in report
        assert "Layer C: Reconstruction" in report

    def test_report_contains_unresolved_rate(self):
        transformation = TransformationLayerMetrics(unresolved_rate=0.75)
        reconstruction = ReconstructionLayerMetrics()
        extraction = ExtractionLayerMetrics()
        report = render_evaluation_report(extraction, transformation, reconstruction)
        assert "Unresolved rate" in report

    def test_report_does_not_collapse_into_accuracy(self):
        """The report should not present a single 'accuracy' number as the metric."""
        extraction = ExtractionLayerMetrics()
        transformation = TransformationLayerMetrics()
        reconstruction = ReconstructionLayerMetrics()
        report = render_evaluation_report(extraction, transformation, reconstruction)
        # The report explicitly states layers are NOT collapsed into one "accuracy" number.
        # Verify no line presents a single "accuracy:" metric line.
        for line in report.split("\n"):
            stripped = line.strip().lower()
            if stripped.startswith(("accuracy:", "overall accuracy:")):
                pytest.fail(f"Report contains collapsed accuracy metric: {line}")

    def test_report_contains_conditional_vs_unconditional(self):
        extraction = ExtractionLayerMetrics()
        transformation = TransformationLayerMetrics()
        reconstruction = ReconstructionLayerMetrics()
        report = render_evaluation_report(extraction, transformation, reconstruction)
        assert "conditional" in report.lower()
        assert "unconditional" in report.lower()


# ---------------------------------------------------------------------------
# Integration tests (require real data)
# ---------------------------------------------------------------------------


V2_RESULTS = Path("results/chain_study_v2_results.json")
FAILURE_MATRIX = Path("results/failure_matrix.json")
EVAL_LAYERS = Path("results/evaluation_layers.json")


@pytest.mark.skipif(
    not (V2_RESULTS.exists() and FAILURE_MATRIX.exists()),
    reason="v2 results or failure matrix not available",
)
class TestEvaluationLayersIntegration:
    def test_extraction_metrics_match_frozen_results(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2 = json.load(f)
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        m = compute_extraction_metrics(v2, fm)
        # S0: 16/22 = 72.7%
        # Pre-v0.2 this was 12/22; the four approved v0.2 extraction
        # improvements (V02-001/003/004: STUDY-008, 021, 029, 031) moved
        # four chains from 0 to >=1 extracted commitment.
        assert m.s0_chains_succeeded == 16
        assert m.s0_chains_attempted == 22
        assert m.s0_extraction_success_rate == pytest.approx(16 / 22)

    def test_gt_metrics_match_frozen_results(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2 = json.load(f)
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        m = compute_extraction_metrics(v2, fm)
        # GT: 2/5 = 40.0%
        assert m.gt_chains_succeeded == 2
        assert m.gt_chains_with_cmp == 5
        assert m.gt_extraction_success_rate == pytest.approx(0.4)

    def test_unresolved_rate_matches_v2_aggregate(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2 = json.load(f)
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        m = compute_transformation_metrics(v2, fm)
        # v2 aggregate rounds to 4 decimal places; use relative tolerance
        assert m.unresolved_rate == pytest.approx(
            v2["aggregate_metrics"]["unresolved_rate"], rel=1e-3
        )

    def test_conditional_reconstruction_5_measurable(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2 = json.load(f)
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        m = compute_reconstruction_metrics(v2, fm)
        assert m.chains_measurable == 5
        assert m.chains_exact_match == 2
        assert m.conditional_exact_reconstruction_rate == pytest.approx(0.4)

    def test_false_authoritative_promotion_is_zero(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2 = json.load(f)
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        m = compute_reconstruction_metrics(v2, fm)
        assert m.false_authoritative_promotion_count == 0


@pytest.mark.skipif(
    not EVAL_LAYERS.exists(),
    reason="evaluation_layers.json not available",
)
class TestEvaluationLayersJSON:
    def test_json_has_three_layers(self):
        with open(EVAL_LAYERS, encoding="utf-8") as f:
            data = json.load(f)
        assert "layer_a_extraction" in data
        assert "layer_b_transformation" in data
        assert "layer_c_reconstruction" in data

    def test_json_has_unresolved_rate(self):
        with open(EVAL_LAYERS, encoding="utf-8") as f:
            data = json.load(f)
        assert "unresolved_rate" in data["layer_b_transformation"]
