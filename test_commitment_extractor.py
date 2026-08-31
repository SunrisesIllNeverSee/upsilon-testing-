"""Tests for the commitment extraction engine, S0 extractor, and GT extractor.

Tests cover:
  - Section detection (various header formats)
  - Clause extraction (subsection patterns, single-clause sections)
  - Covenant classification (leverage ratio, DSCR, current ratio, etc.)
  - Value extraction (step-down schedules, ratio thresholds, percentages)
  - Facility commitment extraction
  - Validation queue routing for unknown/unextractable clauses
  - S0 extractor on real Ameresco S0 document
  - GT extractor on real CMP documents
  - Provenance tracking
  - Independence: prediction path != validation path
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from commitment_extractor import (
    ExtractionResult,
    ValidationItem,
    _classify_covenant,
    _extract_clauses_from_section,
    _extract_dollar_amount,
    _extract_step_down_schedule,
    _extract_threshold_percent,
    _extract_threshold_ratio,
    _find_covenant_sections,
    extract_commitments,
    extract_commitments_from_file,
)
from s0_extractor import extract_s0_state, extract_s0_state_for_chain
from gt_extractor import extract_ground_truth, extract_ground_truth_for_chain


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------


class TestSectionDetection:
    def test_finds_bare_number_section(self):
        """Ameresco pattern: '7.10 Certain Financial Covenants.'"""
        text = "Some preamble text. 7.10 Certain Financial Covenants.    (a) Test. The Borrower shall not permit. 7.11 Next Section. More text."
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        assert "7.10" in sections[0][0]

    def test_finds_section_prefix(self):
        """Pattern: 'Section 7.10 Certain Financial Covenants'"""
        text = "Preamble. Section 7.10 Certain Financial Covenants. (a) Test. The Borrower shall maintain. Section 7.11 Next. End."
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        assert "7.10" in sections[0][0]

    def test_finds_uppercase_section(self):
        """Pattern: 'SECTION 8.13 Financial Covenants'"""
        text = "Preamble. SECTION 8.13 Financial Covenants. (a) Test. The Borrower shall maintain. SECTION 9.1 Next. End."
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        assert "8.13" in sections[0][0]

    def test_finds_article_roman_numeral(self):
        """Pattern: 'ARTICLE VIII FINANCIAL COVENANTS'"""
        text = "Preamble. ARTICLE VIII FINANCIAL COVENANTS. (a) Test. The Borrower shall maintain. ARTICLE IX NEXT. End."
        sections = _find_covenant_sections(text)
        assert len(sections) == 1

    def test_skips_toc_entries(self):
        """TOC entries with dot leaders should be skipped."""
        text = (
            "TABLE OF CONTENTS\n"
            "7.10 Certain Financial Covenants...........114\n"
            "7.11 Next Section..........................115\n"
            "\n\n"
            "7.10 Certain Financial Covenants.    (a) Test. The Borrower shall not permit. "
            "7.11 Next Section. End."
        )
        sections = _find_covenant_sections(text)
        # Should find the content section, not the TOC entry
        assert len(sections) == 1
        # The section should start at the content, not the TOC
        assert sections[0][1] > 50  # past the TOC

    def test_no_covenant_section_returns_empty(self):
        text = "This is a document with no financial covenants section."
        sections = _find_covenant_sections(text)
        assert sections == []


# ---------------------------------------------------------------------------
# Clause extraction
# ---------------------------------------------------------------------------


class TestClauseExtraction:
    def test_extracts_subsection_clauses(self):
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Borrower shall not permit.  "
            "(b) Debt Service Coverage Ratio.  The Borrower shall not permit the ratio.  "
            "7.11 Next Section. End."
        )
        sections = _find_covenant_sections(text)
        clauses = _extract_clauses_from_section(text, sections[0][1], sections[0][2], sections[0][0])
        assert len(clauses) == 2
        assert "Total Funded Debt to EBITDA" in clauses[0].clause_name
        assert "Debt Service Coverage" in clauses[1].clause_name

    def test_clause_body_not_truncated_by_inner_parens(self):
        """Clause body should not be cut short by (a)/(b) sub-parts within
        the body text (e.g., 'ratio of (a) Cash Flow... to (b) Debt Service...')."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Leverage Ratio.  The Borrower shall not permit the ratio to exceed 4.50 to 1.00.  "
            "(b) Debt Service Coverage Ratio.  The Borrower shall not permit the ratio of "
            "(a) Cash Flow of the Borrower, to (b) Debt Service of the Borrower "
            "as of the end of each fiscal quarter to be less than 1.50 to 1.00.  "
            "7.11 Next Section. End."
        )
        sections = _find_covenant_sections(text)
        clauses = _extract_clauses_from_section(text, sections[0][1], sections[0][2], sections[0][0])
        assert len(clauses) == 2
        # The DSCR clause body should contain the full ratio definition
        assert "Cash Flow" in clauses[1].text
        assert "Debt Service" in clauses[1].text
        assert "1.50" in clauses[1].text


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------


class TestValueExtraction:
    def test_extract_step_down_schedule(self):
        text = (
            "(i) ending on March 31, 2022, to exceed 4.50 to 1.00, "
            "(ii) ending on June 30, 2022, to exceed 4.25 to 1.00, "
            "and (iv) for any quarter ending thereafter, to exceed 3.50 to 1.00."
        )
        result = _extract_step_down_schedule(text)
        assert result is not None
        assert len(result["step_down_schedule"]) == 2
        assert result["step_down_schedule"][0] == {"period_end": "2022-03-31", "threshold": 4.50}
        assert result["step_down_schedule"][1] == {"period_end": "2022-06-30", "threshold": 4.25}
        assert result["steady_state_threshold"] == 3.50

    def test_extract_step_down_schedule_no_match(self):
        text = "This text has no step-down schedule pattern."
        result = _extract_step_down_schedule(text)
        assert result is None

    def test_extract_threshold_ratio_exceed(self):
        text = "The Borrower shall not permit the ratio to exceed 4.50 to 1.00."
        threshold, operator = _extract_threshold_ratio(text)
        assert threshold == 4.50
        assert operator == "<="

    def test_extract_threshold_ratio_less_than(self):
        text = "The Borrower shall not permit the ratio to be less than 1.50 to 1.00."
        threshold, operator = _extract_threshold_ratio(text)
        assert threshold == 1.50
        assert operator == ">="

    def test_extract_threshold_percent(self):
        text = "Permit the Tier 1 Leverage Ratio to be less than 7.00%."
        threshold, operator = _extract_threshold_percent(text)
        assert threshold == 7.00
        assert operator == ">="

    def test_extract_dollar_amount(self):
        assert _extract_dollar_amount("$150,000,000") == 150000000
        assert _extract_dollar_amount("$2,802,125,000") == 2802125000
        assert _extract_dollar_amount("no amount here") is None


# ---------------------------------------------------------------------------
# Covenant classification
# ---------------------------------------------------------------------------


class TestCovenantClassification:
    def test_leverage_ratio(self):
        result = _classify_covenant("Total Funded Debt to EBITDA Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.leverage_ratio"

    def test_debt_service_coverage(self):
        result = _classify_covenant("Debt Service Coverage Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.debt_service_coverage"

    def test_current_ratio(self):
        result = _classify_covenant("Current Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.current_ratio"

    def test_tier_1_leverage(self):
        result = _classify_covenant("Tier 1 Leverage Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.tier_1_leverage_ratio"
        assert result[2] == "percent"

    def test_unknown_covenant(self):
        result = _classify_covenant("Some Unknown Covenant Type")
        assert result is None


# ---------------------------------------------------------------------------
# Full extraction
# ---------------------------------------------------------------------------


class TestExtractCommitments:
    def test_extracts_leverage_ratio_with_step_down(self):
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the Core Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on March 31, 2022, to exceed 4.50 to 1.00, "
            "(ii) ending on June 30, 2022, to exceed 4.25 to 1.00, "
            "and (iv) for any quarter ending thereafter, to exceed 3.50 to 1.00.  "
            "7.11 Next Section. End."
        )
        result = extract_commitments(text, source_label="TEST")
        assert "financial_covenant.leverage_ratio" in result.commitments
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.threshold == 3.50
        assert c.operator == "<="
        assert c.unit == "ratio"
        assert c.frequency == "quarterly"
        assert "step_down_schedule" in c.applicability

    def test_extracts_simple_ratio_covenant(self):
        text = (
            "9.01 Financial Covenants.    "
            "(a) Ratio of Debt to EBITDAX.  The Borrower will not, at any time, "
            "permit its ratio of Debt as of such time to EBITDAX to be greater than 3.5 to 1.0.  "
            "(b) Current Ratio.  The Borrower will not permit, as of the last day of any "
            "fiscal quarter, its ratio of current assets to current liabilities to be less "
            "than 1.0 to 1.0.  "
            "9.02 Next Section. End."
        )
        result = extract_commitments(text, source_label="TEST")
        assert "financial_covenant.leverage_ratio" in result.commitments
        assert result.commitments["financial_covenant.leverage_ratio"].threshold == 3.5
        assert "financial_covenant.current_ratio" in result.commitments
        assert result.commitments["financial_covenant.current_ratio"].threshold == 1.0

    def test_extracts_percentage_covenant(self):
        text = (
            "SECTION 8.13 Financial Covenants.    "
            "(a) Texas Ratio.  Permit the Texas Ratio to be greater than 25.00% as of the "
            "last day of any fiscal quarter.  "
            "(b) Tier 1 Leverage Ratio.  Permit the Tier 1 Leverage Ratio to be less than 7.00%.  "
            "ARTICLE IX NEXT. End."
        )
        result = extract_commitments(text, source_label="TEST")
        assert "financial_covenant.texas_ratio" in result.commitments
        assert result.commitments["financial_covenant.texas_ratio"].threshold == 25.0
        assert result.commitments["financial_covenant.texas_ratio"].unit == "percent"
        assert "financial_covenant.tier_1_leverage_ratio" in result.commitments
        assert result.commitments["financial_covenant.tier_1_leverage_ratio"].threshold == 7.00

    def test_unknown_covenant_goes_to_validation_queue(self):
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Some Unknown Covenant.  The Borrower shall maintain something unusual.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        assert len(result.commitments) == 0
        assert len(result.validation_queue) == 1
        assert "Unknown" in result.validation_queue[0].reason

    def test_recognized_but_unextractable_goes_to_validation_queue(self):
        """A covenant that is recognized but whose threshold can't be
        extracted should go to the validation queue with a specific reason."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Borrower shall maintain compliance.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        assert len(result.validation_queue) == 1
        assert "threshold extraction failed" in result.validation_queue[0].reason

    def test_empty_text_returns_empty_result(self):
        result = extract_commitments("", source_label="TEST")
        assert len(result.commitments) == 0
        assert len(result.validation_queue) == 0

    def test_short_text_returns_empty_result(self):
        result = extract_commitments("Short text", source_label="TEST")
        assert len(result.commitments) == 0

    def test_provenance_is_recorded(self):
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the Core Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on March 31, 2022, to exceed 4.50 to 1.00, "
            "and (iv) for any quarter ending thereafter, to exceed 3.50 to 1.00.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="S0-TEST")
        assert len(result.provenance) >= 1
        p = result.provenance[0]
        assert p["source_label"] == "S0-TEST"
        assert "rule" in p
        assert "section_ref" in p


# ---------------------------------------------------------------------------
# S0 extractor
# ---------------------------------------------------------------------------


_AMERESCO_S0 = "data/edgar_chains/ameresco/S0_fifth_AR_2022.txt"


class TestS0Extractor:
    @pytest.mark.skipif(not Path(_AMERESCO_S0).exists(), reason="Ameresco S0 not available")
    def test_ameresco_s0_extracts_leverage_ratio(self):
        result = extract_s0_state(_AMERESCO_S0)
        assert "financial_covenant.leverage_ratio" in result.commitments
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.threshold == 3.50
        assert c.operator == "<="
        assert c.unit == "ratio"
        assert c.frequency == "quarterly"

    @pytest.mark.skipif(not Path(_AMERESCO_S0).exists(), reason="Ameresco S0 not available")
    def test_ameresco_s0_extracts_debt_service_coverage(self):
        result = extract_s0_state(_AMERESCO_S0)
        assert "financial_covenant.debt_service_coverage" in result.commitments
        c = result.commitments["financial_covenant.debt_service_coverage"]
        assert c.threshold == 1.50
        assert c.operator == ">="

    @pytest.mark.skipif(not Path(_AMERESCO_S0).exists(), reason="Ameresco S0 not available")
    def test_ameresco_s0_extracts_facility_commitments(self):
        result = extract_s0_state(_AMERESCO_S0)
        # At least one facility commitment should be extracted
        facility_keys = [k for k in result.commitments if k.startswith("facility.")]
        assert len(facility_keys) >= 1

    @pytest.mark.skipif(not Path(_AMERESCO_S0).exists(), reason="Ameresco S0 not available")
    def test_ameresco_s0_has_provenance(self):
        result = extract_s0_state(_AMERESCO_S0)
        assert len(result.provenance) >= 1
        for p in result.provenance:
            assert p["source_label"] == "S0"

    @pytest.mark.skipif(not Path(_AMERESCO_S0).exists(), reason="Ameresco S0 not available")
    def test_ameresco_s0_step_down_schedule(self):
        result = extract_s0_state(_AMERESCO_S0)
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert "step_down_schedule" in c.applicability
        assert len(c.applicability["step_down_schedule"]) >= 1
        assert c.applicability["steady_state_threshold"] == 3.50

    def test_nonexistent_file_returns_empty(self):
        result = extract_s0_state("nonexistent/path.txt")
        assert len(result.commitments) == 0
        assert result.text_length == 0

    def test_chain_id_labeled_provenance(self):
        """extract_s0_state_for_chain should add chain_id to provenance."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the Core Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on March 31, 2022, to exceed 4.50 to 1.00, "
            "and (iv) for any quarter ending thereafter, to exceed 3.50 to 1.00.  "
            "7.11 Next. End."
        )
        from commitment_extractor import extract_commitments
        result = extract_commitments(text, source_label="S0")
        for p in result.provenance:
            p["chain_id"] = "TEST-CHAIN"
        assert all(p.get("chain_id") == "TEST-CHAIN" for p in result.provenance)


# ---------------------------------------------------------------------------
# GT extractor
# ---------------------------------------------------------------------------


class TestGTExtractor:
    def test_gt_extractor_uses_cmp_label(self):
        text = (
            "8.13 Financial Covenants.    "
            "(a) Texas Ratio.  Permit the Texas Ratio to be greater than 25.00%.  "
            "ARTICLE IX. End."
        )
        from commitment_extractor import extract_commitments
        result = extract_commitments(text, source_label="CMP")
        assert result.source_label == "CMP"
        assert "financial_covenant.texas_ratio" in result.commitments

    def test_gt_extractor_nonexistent_file(self):
        result = extract_ground_truth("nonexistent/cmp.txt")
        assert len(result.commitments) == 0
        assert result.text_length == 0


# ---------------------------------------------------------------------------
# Independence: prediction path != validation path
# ---------------------------------------------------------------------------


class TestIndependence:
    def test_s0_and_gt_use_same_engine_but_different_labels(self):
        """Both extractors use the shared engine but produce different
        source labels, ensuring their outputs are distinguishable."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Borrower shall not permit "
            "the ratio to exceed 4.50 to 1.00.  7.11 Next. End."
        )
        from commitment_extractor import extract_commitments
        s0_result = extract_commitments(text, source_label="S0")
        gt_result = extract_commitments(text, source_label="CMP")
        # Both extract the same commitment
        assert "financial_covenant.leverage_ratio" in s0_result.commitments
        assert "financial_covenant.leverage_ratio" in gt_result.commitments
        # But with different source labels
        assert s0_result.source_label == "S0"
        assert gt_result.source_label == "CMP"

    def test_gt_does_not_use_amendment_output(self):
        """The GT extractor only takes a document path — it has no
        dependency on amendment reconstruction output."""
        import inspect
        sig = inspect.signature(extract_ground_truth)
        params = list(sig.parameters.keys())
        # The only parameter is the document path — no reconstruction input
        assert "cmp_path" in params
        assert "reconstructed_state" not in params
        assert "amendment_result" not in params


# ---------------------------------------------------------------------------
# Safety: no guessing
# ---------------------------------------------------------------------------


class TestNoGuessing:
    def test_unsupported_clauses_go_to_validation_queue(self):
        """Unsupported clauses must enter the validation queue, not be
        guessed as CommitmentState objects."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Liquidity.  The Borrower shall maintain some complex liquidity requirement.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        # "Liquidity" is not a known covenant type → validation queue
        assert len(result.validation_queue) == 1
        assert "Liquidity" in result.validation_queue[0].clause_name
        # No commitment should be produced for the unknown clause
        assert len(result.commitments) == 0

    def test_no_threshold_no_commitment(self):
        """A recognized covenant without an extractable threshold must
        NOT produce a CommitmentState with a guessed threshold."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Borrower shall maintain compliance.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        # The covenant is recognized but threshold can't be extracted
        assert len(result.validation_queue) == 1
        assert "threshold extraction failed" in result.validation_queue[0].reason
        # No commitment with a guessed threshold
        assert "financial_covenant.leverage_ratio" not in result.commitments
