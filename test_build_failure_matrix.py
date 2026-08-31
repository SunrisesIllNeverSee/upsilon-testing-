"""Tests for the failure matrix builder.

Tests cover:
  - Failure cause taxonomy completeness
  - S0 document analysis (discovery vs extraction failure)
  - GT document analysis (discovery vs extraction failure)
  - Amendment format analysis (parser vs unsupported format)
  - Full-restatement detection (title signal + structural signal)
  - Primary layer assignment logic
  - Per-chain attribution consistency
  - Aggregate count integrity
  - Change-spec traces to failure matrix (cross-module invariant)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from build_failure_matrix import (
    FAILURE_CAUSES,
    _analyze_amendment_format,
    _analyze_gt_document,
    _analyze_s0_document,
    _assign_primary_layer,
    attribute_chain_failure,
)

# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


EXPECTED_CAUSES = {
    "S0_DISCOVERY_FAILURE",
    "S0_EXTRACTION_FAILURE",
    "GT_DISCOVERY_FAILURE",
    "GT_EXTRACTION_FAILURE",
    "PARSER_FAILURE",
    "SEMANTIC_MAPPING_FAILURE",
    "EXECUTION_FAILURE",
    "LINEAGE_FAILURE",
    "STATE_COMPARISON_FAILURE",
    "UNSUPPORTED_DOCUMENT_FORMAT",
}


class TestFailureCauseTaxonomy:
    def test_all_expected_causes_present(self):
        """The taxonomy must include all 10 causes from the prompt."""
        assert set(FAILURE_CAUSES.keys()) == EXPECTED_CAUSES

    def test_all_causes_have_descriptions(self):
        """Every cause must have a non-empty description."""
        for cause, desc in FAILURE_CAUSES.items():
            assert desc, f"Cause {cause} has empty description"

    def test_no_extra_causes(self):
        """No causes beyond the 10 specified in the prompt."""
        assert len(FAILURE_CAUSES) == 10


# ---------------------------------------------------------------------------
# S0 document analysis
# ---------------------------------------------------------------------------


class TestS0DocumentAnalysis:
    @pytest.fixture
    def tmp_chain(self, tmp_path):
        """Create a temporary chain directory with an S0 file."""
        chain_dir = tmp_path / "data" / "chain_study" / "TEST-001"
        chain_dir.mkdir(parents=True)
        return chain_dir

    def test_missing_s0_file_is_discovery_failure(self, tmp_chain):
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            cause, evidence = _analyze_s0_document("TEST-001")
        assert cause == "S0_DISCOVERY_FAILURE"
        assert "missing" in evidence.lower()

    def test_short_s0_is_discovery_failure(self, tmp_chain):
        s0_file = tmp_chain / "S0.txt"
        s0_file.write_text("Short document content", encoding="utf-8")
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = "Short document content"
            cause, evidence = _analyze_s0_document("TEST-001")
        assert cause == "S0_DISCOVERY_FAILURE"
        assert "too short" in evidence.lower()

    def test_no_credit_agreement_language_is_discovery_failure(self, tmp_chain):
        long_text = "A" * 20000  # Long enough but no "credit agreement"
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = long_text
            cause, evidence = _analyze_s0_document("TEST-001")
        assert cause == "S0_DISCOVERY_FAILURE"
        assert "wrong" in evidence.lower() or "credit agreement" in evidence.lower()

    def test_financial_covenants_section_is_extraction_failure(self, tmp_chain):
        text = "credit agreement " + "x" * 20000 + " Section 7.10 Financial Covenants. Some content."
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = text
            cause, _ = _analyze_s0_document("TEST-001")
        assert cause == "S0_EXTRACTION_FAILURE"

    def test_negative_covenants_section_is_extraction_failure(self, tmp_chain):
        text = "credit agreement " + "x" * 20000 + " Section 7. Negative Covenants. Borrower shall not."
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = text
            cause, evidence = _analyze_s0_document("TEST-001")
        assert cause == "S0_EXTRACTION_FAILURE"
        assert "Negative Covenants" in evidence


# ---------------------------------------------------------------------------
# GT document analysis
# ---------------------------------------------------------------------------


class TestGTDocumentAnalysis:
    def test_missing_cmp_returns_empty(self):
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            cause, evidence = _analyze_gt_document("TEST-001")
        assert cause == ""
        assert "No CMP" in evidence

    def test_amendment_title_is_discovery_failure(self):
        text = "FIFTH AMENDMENT TO SECOND AMENDED AND RESTATED CREDIT AGREEMENT\n" + "x" * 500
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = text
            cause, evidence = _analyze_gt_document("TEST-001")
        assert cause == "GT_DISCOVERY_FAILURE"
        assert "amendment" in evidence.lower()

    def test_no_covenant_content_is_extraction_failure(self):
        text = "Some document " + "x" * 20000
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = text
            cause, _ = _analyze_gt_document("TEST-001")
        assert cause == "GT_EXTRACTION_FAILURE"

    def test_covenant_content_is_extraction_failure(self):
        text = "credit agreement " + "x" * 20000 + " Financial Covenant. 4.50 to 1.00"
        with patch("build_failure_matrix.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = text
            cause, _ = _analyze_gt_document("TEST-001")
        assert cause == "GT_EXTRACTION_FAILURE"


# ---------------------------------------------------------------------------
# Amendment format analysis
# ---------------------------------------------------------------------------


class TestAmendmentFormatAnalysis:
    @pytest.fixture
    def setup_chain(self, tmp_path):
        """Set up a temporary chain directory and patch Path to use it."""
        chain_dir = tmp_path / "data" / "chain_study" / "TEST-001"
        chain_dir.mkdir(parents=True)
        a1_file = chain_dir / "A1.txt"
        return a1_file

    def test_redline_is_unsupported_format(self, setup_chain):
        a1_file = setup_chain
        a1_file.write_text("delete the stricken text and add the double-underlined text", encoding="utf-8")
        with patch("build_failure_matrix.Path") as mock_path_class:
            mock_instance = mock_path_class.return_value
            mock_instance.exists.return_value = True
            mock_instance.glob.return_value = [a1_file]
            cause, evidence = _analyze_amendment_format("TEST-001")
        assert cause == "UNSUPPORTED_DOCUMENT_FORMAT"
        assert "redline" in evidence.lower()

    def test_full_restate_title_is_unsupported_format(self, setup_chain):
        a1_file = setup_chain
        a1_file.write_text("AMENDED AND RESTATED CREDIT AGREEMENT\nSome content here.", encoding="utf-8")
        with patch("build_failure_matrix.Path") as mock_path_class:
            mock_instance = mock_path_class.return_value
            mock_instance.exists.return_value = True
            mock_instance.glob.return_value = [a1_file]
            cause, evidence = _analyze_amendment_format("TEST-001")
        assert cause == "UNSUPPORTED_DOCUMENT_FORMAT"
        assert "amended-and-restated" in evidence.lower()

    def test_full_restate_structural_is_unsupported_format(self, setup_chain):
        """Full restatement detected via ARTICLE I / DEFINITIONS after NOW THEREFORE.

        This is the STUDY-013 case: the title doesn't say 'amended and restated'
        but the document restates the entire agreement body.
        """
        a1_file = setup_chain
        text = (
            "JOINDER AND SECOND AMENDMENT TO CREDIT AGREEMENT\n"
            + "x" * 1000
            + "\nNOW THEREFORE in consideration of the mutual agreements herein contained\n"
            + "the parties hereto hereby agree as follows:\n"
            + "ARTICLE I\nDEFINITIONS\n1.1 Definitions. When used herein the following terms\n"
            + "shall have the following meanings:\n"
            + "x" * 5000
        )
        a1_file.write_text(text, encoding="utf-8")
        with patch("build_failure_matrix.Path") as mock_path_class:
            mock_instance = mock_path_class.return_value
            mock_instance.exists.return_value = True
            mock_instance.glob.return_value = [a1_file]
            cause, evidence = _analyze_amendment_format("TEST-001")
        assert cause == "UNSUPPORTED_DOCUMENT_FORMAT"
        assert "structural signal" in evidence.lower()

    def test_section_amend_format_is_supported(self, setup_chain):
        a1_file = setup_chain
        a1_file.write_text(
            "Section 6.07 is hereby amended to read as follows: New content.",
            encoding="utf-8",
        )
        with patch("build_failure_matrix.Path") as mock_path_class:
            mock_instance = mock_path_class.return_value
            mock_instance.exists.return_value = True
            mock_instance.glob.return_value = [a1_file]
            cause, evidence = _analyze_amendment_format("TEST-001")
        assert cause == ""
        assert "supported" in evidence.lower()

    def test_unknown_format_is_parser_failure(self, setup_chain):
        a1_file = setup_chain
        a1_file.write_text("Some amendment that uses no recognized format pattern.", encoding="utf-8")
        with patch("build_failure_matrix.Path") as mock_path_class:
            mock_instance = mock_path_class.return_value
            mock_instance.exists.return_value = True
            mock_instance.glob.return_value = [a1_file]
            cause, _ = _analyze_amendment_format("TEST-001")
        assert cause == "PARSER_FAILURE"


# ---------------------------------------------------------------------------
# Primary layer assignment
# ---------------------------------------------------------------------------


class TestPrimaryLayerAssignment:
    def test_extraction_layer_for_s0_discovery(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["S0_DISCOVERY_FAILURE"] = True
        assert _assign_primary_layer(causes) == "extraction"

    def test_extraction_layer_for_gt_extraction(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["GT_EXTRACTION_FAILURE"] = True
        assert _assign_primary_layer(causes) == "extraction"

    def test_transformation_layer_for_parser(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["PARSER_FAILURE"] = True
        assert _assign_primary_layer(causes) == "transformation"

    def test_transformation_layer_for_unsupported_format(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["UNSUPPORTED_DOCUMENT_FORMAT"] = True
        assert _assign_primary_layer(causes) == "transformation"

    def test_reconstruction_layer_for_lineage(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["LINEAGE_FAILURE"] = True
        assert _assign_primary_layer(causes) == "reconstruction"

    def test_reconstruction_layer_for_state_comparison(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["STATE_COMPARISON_FAILURE"] = True
        assert _assign_primary_layer(causes) == "reconstruction"

    def test_none_layer_for_success(self):
        causes = {c: False for c in FAILURE_CAUSES}
        assert _assign_primary_layer(causes) == "none"

    def test_extraction_takes_priority_over_transformation(self):
        """Extraction failures should be primary even if transformation also failed."""
        causes = {c: False for c in FAILURE_CAUSES}
        causes["S0_EXTRACTION_FAILURE"] = True
        causes["SEMANTIC_MAPPING_FAILURE"] = True
        assert _assign_primary_layer(causes) == "extraction"

    def test_transformation_takes_priority_over_reconstruction(self):
        causes = {c: False for c in FAILURE_CAUSES}
        causes["PARSER_FAILURE"] = True
        causes["LINEAGE_FAILURE"] = True
        assert _assign_primary_layer(causes) == "transformation"


# ---------------------------------------------------------------------------
# Integration tests (require data files)
# ---------------------------------------------------------------------------


V2_RESULTS = Path("results/chain_study_v2_results.json")
FAILURE_MATRIX = Path("results/failure_matrix.json")


@pytest.mark.skipif(
    not V2_RESULTS.exists(),
    reason="v2 results not available",
)
class TestFailureMatrixIntegration:
    def test_all_25_chains_attributed(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2_data = json.load(f)
        attributions = [attribute_chain_failure(r) for r in v2_data["issuer_results"]]
        assert len(attributions) == 25

    def test_every_chain_has_primary_layer(self):
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2_data = json.load(f)
        attributions = [attribute_chain_failure(r) for r in v2_data["issuer_results"]]
        for attr in attributions:
            assert attr.primary_layer in ("extraction", "transformation", "reconstruction", "none")

    def test_success_chain_has_no_failures(self):
        """The Ameresco chain (SUCCESS) should have no attributed causes."""
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2_data = json.load(f)
        for result in v2_data["issuer_results"]:
            if result["failure_category"] == "SUCCESS":
                attr = attribute_chain_failure(result)
                flagged = [c for c, v in attr.causes.items() if v]
                assert not flagged, f"SUCCESS chain {attr.chain_id} has causes: {flagged}"

    def test_attribution_metrics_match_v2_results(self):
        """Attribution metrics should match the source v2 results."""
        with open(V2_RESULTS, encoding="utf-8") as f:
            v2_data = json.load(f)
        for result in v2_data["issuer_results"]:
            attr = attribute_chain_failure(result)
            assert attr.s0_extraction_commitments == result["s0_extraction_commitments"]
            assert attr.gt_extraction_commitments == result["gt_extraction_commitments"]
            assert attr.parser_detected_instructions == result["parser_detected_instructions"]
            assert attr.semantic_mapped_instructions == result["semantic_mapped_instructions"]
            assert attr.v2_failure_category == result["failure_category"]


@pytest.mark.skipif(
    not FAILURE_MATRIX.exists(),
    reason="Failure matrix not available",
)
class TestFailureMatrixDataIntegrity:
    def test_matrix_has_25_chains(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        assert len(fm["chains"]) == 25

    def test_aggregate_counts_match_per_chain(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        for cause in FAILURE_CAUSES:
            actual = sum(1 for c in fm["chains"] if c["causes"].get(cause, False))
            assert actual == fm["aggregate_cause_counts"][cause], (
                f"Aggregate count mismatch for {cause}: {actual} != {fm['aggregate_cause_counts'][cause]}"
            )

    def test_layer_counts_match_per_chain(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        for layer in ("extraction", "transformation", "reconstruction", "none"):
            actual = sum(1 for c in fm["chains"] if c["primary_layer"] == layer)
            assert actual == fm["layer_counts"][layer], (
                f"Layer count mismatch for {layer}: {actual} != {fm['layer_counts'][layer]}"
            )

    def test_all_causes_in_taxonomy(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        for c in fm["chains"]:
            for cause in c["causes"]:
                assert cause in FAILURE_CAUSES, f"Unknown cause {cause} in chain {c['chain_id']}"

    def test_frozen_tag_is_set(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        assert fm["frozen_tag"] == "chain-study-v2-development"

    def test_frozen_commit_is_set(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        assert fm["frozen_commit"] == "fb0862d"

    def test_study_013_is_unsupported_format(self):
        """STUDY-013 must be classified as UNSUPPORTED_DOCUMENT_FORMAT (not just PARSER_FAILURE).

        This is the regression test for the full-restatement structural detection fix.
        """
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        study_013 = next(c for c in fm["chains"] if c["chain_id"] == "STUDY-013")
        assert study_013["causes"].get("UNSUPPORTED_DOCUMENT_FORMAT", False), (
            "STUDY-013 must be flagged as UNSUPPORTED_DOCUMENT_FORMAT (full restatement)"
        )
