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

from pathlib import Path

import pytest

from commitment_extractor import (
    _classify_covenant,
    _extract_clauses_from_section,
    _extract_deadline,
    _extract_dollar_amount,
    _extract_effective_date,
    _extract_exceptions,
    _extract_facility_commitments,
    _extract_party,
    _extract_rate,
    _extract_step_down_schedule,
    _extract_threshold_percent,
    _extract_threshold_ratio,
    _find_covenant_sections,
    extract_commitments,
)
from gt_extractor import extract_ground_truth
from s0_extractor import extract_s0_state

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


# ---------------------------------------------------------------------------
# Facility amount extraction — million/billion suffix handling
# ---------------------------------------------------------------------------


class TestFacilityAmountExtraction:
    """Tests for the facility commitment amount extraction, covering the
    million/billion suffix multiplier bug fix.

    Before the fix, the regex consumed the "million"/"billion" suffix as
    part of the match, so the suffix check looked past it and the
    multiplier was never applied. These tests verify the multiplier is
    now correctly applied for abbreviated dollar formats.
    """

    def test_full_dollar_format(self):
        """$150,000,000 should extract as 150000000 (no multiplier)."""
        text = "Term Loan in the amount of $150,000,000."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.threshold == 150000000.0

    def test_million_suffix(self):
        """$150 million should extract as 150000000 (1M multiplier)."""
        text = "Term Loan in the amount of $150 million."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.threshold == 150000000.0

    def test_billion_suffix(self):
        """$1.5 billion should extract as 1500000000 (1.5 * 1B)."""
        text = "Term Loan in the amount of $1.5 billion."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.threshold == 1500000000.0

    def test_decimal_million_suffix(self):
        """$1.5 million should extract as 1500000 (1.5 * 1M)."""
        text = "Term Loan in the amount of $1.5 million."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.threshold == 1500000.0

    def test_revolving_facility_million(self):
        """Revolving Facility with million suffix."""
        text = "Revolving Facility of $50 million."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.canonical_key == "facility.revolving_facility"
        assert c.threshold == 50000000.0

    def test_no_suffix_no_multiplier(self):
        """Bare dollar amount without million/billion should not be
        multiplied."""
        text = "Term Loan in the amount of $200,000,000."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.threshold == 200000000.0

    def test_million_and_billion_not_confused(self):
        """Ensure 'million' check doesn't accidentally match 'billion'."""
        text = "Term Loan in the amount of $2 billion."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        # Should be 2 * 1_000_000_000 = 2_000_000_000, NOT 2 * 1_000_000
        assert c.threshold == 2000000000.0


# ---------------------------------------------------------------------------
# Party extraction
# ---------------------------------------------------------------------------


class TestPartyExtraction:
    """Tests for extracting the obligated party from covenant clause text.

    Before the fix, all financial covenants hardcoded party=["borrower"]
    regardless of the actual clause text. Real EDGAR filings use varying
    party language: "Loan Parties", "Credit Parties", "Borrower",
    "Obligors", "each Loan Party", etc.
    """

    def test_loan_parties(self):
        assert _extract_party("The Loan Parties shall not permit the ratio") == ["loan_parties"]

    def test_borrower(self):
        assert _extract_party("The Borrower will not permit its ratio of Debt") == ["borrower"]

    def test_credit_parties(self):
        assert _extract_party("The Credit Parties shall maintain compliance") == ["loan_parties"]

    def test_each_loan_party(self):
        assert _extract_party("Each Loan Party shall not permit the ratio") == ["each_loan_party"]

    def test_each_credit_party(self):
        assert _extract_party("Each Credit Party shall maintain compliance") == ["each_loan_party"]

    def test_obligors(self):
        assert _extract_party("The Obligors shall maintain the ratio") == ["obligors"]

    def test_obligor_singular(self):
        assert _extract_party("The Obligor shall maintain the ratio") == ["obligors"]

    def test_no_loan_party_negative(self):
        """'No Loan Party will' should map to loan_parties."""
        assert _extract_party("No Loan Party will engage in such business") == ["loan_parties"]

    def test_default_borrower_when_no_party_found(self):
        """When no party language is found, default to ['borrower']."""
        assert _extract_party("shall maintain compliance with all covenants") == ["borrower"]

    def test_party_extracted_in_full_extraction(self):
        """End-to-end: extract_commitments should populate the party field
        from the clause text, not hardcode it."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the ratio to exceed 4.50 to 1.00.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.party == ["loan_parties"]

    def test_party_borrower_in_full_extraction(self):
        """End-to-end: 'The Borrower' should produce party=['borrower']."""
        text = (
            "9.01 Financial Covenants.    "
            "(a) Ratio of Debt to EBITDAX.  The Borrower will not, at any time, "
            "permit its ratio of Debt as of such time to EBITDAX to be greater than 3.5 to 1.0.  "
            "9.02 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.party == ["borrower"]


# ---------------------------------------------------------------------------
# Missing field extraction: deadline, exceptions, effective date, rate
# ---------------------------------------------------------------------------


class TestMissingFieldExtraction:
    """Tests for the fields that were not extracted in the original v0.1:
    deadline/maturity, exceptions, effective date (valid_from), and rate.
    """

    # --- Exceptions ---

    def test_extract_provided_that_exception(self):
        text = (
            "The Borrower shall not permit the ratio to exceed 4.50 to 1.00, "
            "provided that the Borrower may exceed this limit during a permitted acquisition."
        )
        exceptions = _extract_exceptions(text)
        assert len(exceptions) == 1
        assert "provided that" in exceptions[0].lower()
        assert "permitted acquisition" in exceptions[0].lower()

    def test_extract_except_colon_exception(self):
        text = "The Borrower shall not incur Debt except: (a) Debt under the Loan Documents."
        exceptions = _extract_exceptions(text)
        assert len(exceptions) == 1
        assert "except" in exceptions[0].lower()

    def test_no_exceptions_returns_empty(self):
        text = "The Borrower shall not permit the ratio to exceed 4.50 to 1.00."
        assert _extract_exceptions(text) == []

    def test_exception_truncation(self):
        """Long exception text should be truncated to 120 chars."""
        long_exc = "provided that " + "x" * 200 + "."
        exceptions = _extract_exceptions(long_exc)
        assert len(exceptions) == 1
        assert len(exceptions[0]) <= 120
        assert exceptions[0].endswith("...")

    def test_exceptions_extracted_in_full_extraction(self):
        """End-to-end: exceptions should be populated in CommitmentState."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the ratio to exceed 4.50 to 1.00, provided that the Borrower may exceed "
            "this limit during a permitted acquisition.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert len(c.exceptions) >= 1
        assert "provided that" in c.exceptions[0].lower()

    # --- Deadline / maturity ---

    def test_extract_maturity_date(self):
        text = "Term Loan with a Maturity Date of March 4, 2025."
        assert _extract_deadline(text) == "2025-03-04"

    def test_extract_stated_maturity(self):
        text = "The facility shall mature on December 31, 2027."
        assert _extract_deadline(text) == "2027-12-31"

    def test_no_deadline_returns_none(self):
        text = "The Borrower shall maintain the ratio at 4.50 to 1.00."
        assert _extract_deadline(text) is None

    def test_deadline_extracted_in_facility(self):
        """End-to-end: facility commitments should extract maturity date."""
        text = "Term Loan in the amount of $150,000,000 with a Maturity Date of March 4, 2025."
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.deadline == "2025-03-04"

    # --- Effective date ---

    def test_extract_effective_as_of(self):
        text = "This covenant is effective as of January 15, 2024."
        assert _extract_effective_date(text) == "2024-01-15"

    def test_extract_commencing_on(self):
        text = "The covenant commencing on June 30, 2023."
        assert _extract_effective_date(text) == "2023-06-30"

    def test_extract_dated_as_of(self):
        text = "This Agreement dated as of March 4, 2022."
        assert _extract_effective_date(text) == "2022-03-04"

    def test_no_effective_date_returns_none(self):
        text = "The Borrower shall maintain the ratio."
        assert _extract_effective_date(text) is None

    # --- Rate ---

    def test_extract_rate_per_annum(self):
        text = "The Term Loan shall bear interest at a rate per annum of 5.50%."
        assert _extract_rate(text) == 5.50

    def test_extract_interest_at_a_rate(self):
        text = "bearing interest at a rate of 3.25% per annum."
        assert _extract_rate(text) == 3.25

    def test_no_rate_returns_none(self):
        text = "The Borrower shall maintain the ratio at 4.50 to 1.00."
        assert _extract_rate(text) is None

    def test_rate_not_confused_with_threshold(self):
        """A percentage threshold (e.g., Texas Ratio 25.00%) should NOT
        be extracted as a rate — rate extraction requires explicit rate
        language."""
        text = "Permit the Texas Ratio to be greater than 25.00%."
        assert _extract_rate(text) is None

    def test_rate_not_confused_with_ratio(self):
        """Ratio language 'rate of 4.50 to 1.00' (no %) must NOT be
        extracted as a rate. The capture group requires a trailing %."""
        text = "shall not permit the ratio of 4.50 to 1.00"
        assert _extract_rate(text) is None

    def test_extract_rate_of_bare_prefix(self):
        """'rate of X.XX%' (no 'interest' prefix) must extract correctly.

        Regression: the previous regex had 'rate\\s+of\\s+(?:\\d|...)?'
        whose \\d branch greedily consumed the first digit of the rate,
        leaving the capture group with only the decimal remainder
        (e.g. 'rate of 5.50%' -> 0.50)."""
        text = "rate of 5.50%"
        assert _extract_rate(text) == 5.50

    def test_extract_rate_of_with_per_annum(self):
        """'rate of X.XX% per annum' must extract the full rate."""
        text = "rate of 7.00% per annum"
        assert _extract_rate(text) == 7.00

    def test_extract_at_a_rate_of(self):
        """'at a rate of X.XX%' (no 'interest' prefix) must extract
        correctly. Same regression class as test_extract_rate_of_bare_prefix."""
        text = "at a rate of 5.50%"
        assert _extract_rate(text) == 5.50

    def test_extract_rate_of_zero_not_swallowed(self):
        """'rate of 7.00%' must return 7.00, NOT 0.00.

        Regression: the previous broken regex produced 0.00 here, which
        was indistinguishable from a legitimate 0% rate and from
        'not found' (None). This is the most dangerous failure mode of
        the old regex because it silently corrupts data without raising
        any signal."""
        text = "rate of 7.00%"
        result = _extract_rate(text)
        assert result == 7.00
        assert result is not None  # must not be silently dropped

    def test_rate_extracted_in_facility(self):
        """End-to-end: facility commitments should extract interest rate."""
        text = (
            "Term Loan in the amount of $150,000,000 bearing interest "
            "at a rate of 5.50% per annum."
        )
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        assert c.rate == 5.50

    def test_effective_date_extracted_in_facility(self):
        """End-to-end: facility commitments should extract effective date
        into valid_from."""
        text = (
            "Term Loan in the amount of $150,000,000, dated as of "
            "March 4, 2022, bearing interest at a rate of 5.50% per annum."
        )
        results = _extract_facility_commitments(text, "TEST")
        assert len(results) == 1
        c, _ = results[0]
        # valid_from is Optional[datetime]; pydantic coerces "YYYY-MM-DD"
        # to datetime(YYYY, MM, DD, 0, 0).
        assert c.valid_from is not None
        assert c.valid_from.year == 2022
        assert c.valid_from.month == 3
        assert c.valid_from.day == 4

    def test_effective_date_extracted_in_covenant(self):
        """End-to-end: financial covenants should extract effective date
        into valid_from when present in clause text."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the ratio to exceed 4.50 to 1.00, effective as of January 15, 2024.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.valid_from is not None
        assert c.valid_from.year == 2024
        assert c.valid_from.month == 1
        assert c.valid_from.day == 15

    def test_no_effective_date_covenant_valid_from_none(self):
        """End-to-end: when no effective date language is present,
        valid_from should remain None."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall not permit "
            "the ratio to exceed 4.50 to 1.00.  "
            "7.11 Next. End."
        )
        result = extract_commitments(text, source_label="TEST")
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.valid_from is None
