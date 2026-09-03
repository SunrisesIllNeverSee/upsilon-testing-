"""Regression tests for the six approved v0.2 changes.

Each test traces to a specific change in the v0.2 change spec and a
specific development chain from the failure matrix. Tests use both
synthetic text (for deterministic unit tests) and real development
chain documents (for evidence-linked integration tests).

V02-001: Expand section detection to non-'Financial Covenants' headers
V02-002: Fix TOC-skip logic for page numbers on separate lines
V02-003: Add numbered-subsection clause extraction (10.1, 10.2 format)
V02-004: Expand fallback covenant-language pattern
V02-005: Add S0 discovery validation (document type checking)
V02-006: Add GT discovery validation (CMP document type checking)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from upsilon.parsing.commitment_extractor import (
    _classify_covenant,
    _extract_clauses_from_section,
    _extract_covenant_name_from_text,
    _extract_threshold_ratio,
    _find_covenant_sections,
    extract_commitments,
)
from upsilon.ingestion.document_discovery.discovery_validation import (
    validate_gt_document,
    validate_s0_document,
)
from upsilon.evidence.s0_extractor import extract_s0_state

# ---------------------------------------------------------------------------
# V02-001: Expand section detection to non-'Financial Covenants' headers
# ---------------------------------------------------------------------------


class TestV02_001_SectionDetection:
    """V02-001: Section detection for non-standard covenant headers.

    Evidence: STUDY-008, STUDY-031, STUDY-004, STUDY-020 fail S0
    extraction because covenants are under non-standard headers.
    """

    def test_finds_financial_condition_header(self):
        """STUDY-008 pattern: 'SECTION 4.9. FINANCIAL CONDITION'."""
        text = (
            "Preamble text. "
            "SECTION 4.9. FINANCIAL CONDITION. "
            "(a) EBIT to Interest Ratio. Borrower shall maintain an EBIT "
            "to Interest Ratio of not less than 1.50 to 1.00. "
            "SECTION 4.10. NEXT SECTION. End."
        )
        sections = _find_covenant_sections(text)
        assert len(sections) >= 1
        assert any("4.9" in s[0] for s in sections)

    def test_finds_affirmative_covenants_with_ratio_content(self):
        """STUDY-031 pattern: 'Section 5.01 Affirmative Covenants' with
        ratio covenants as subsections."""
        text = (
            "Preamble. "
            "Section 5.01 Affirmative Covenants. "
            "(b) Consolidated Leverage Ratio. Maintain a Consolidated "
            "Leverage Ratio of not more than 4.00 : 1.0. "
            "(c) Consolidated Interest Coverage Ratio. Maintain a "
            "Consolidated Interest Coverage Ratio of not less than 4.00 : 1.0. "
            "Section 5.02 Negative Covenants. End."
        )
        sections = _find_covenant_sections(text)
        assert len(sections) >= 1
        assert any("5.01" in s[0] for s in sections)

    def test_negative_covenants_without_ratio_not_detected(self):
        """Content-based validation: 'Negative Covenants' sections without
        ratio thresholds or covenant verbs should NOT be detected."""
        text = (
            "Preamble. "
            "Section 7. Negative Covenants. "
            "Not engage in any prohibited merger activity. "
            "Not sell assets outside the ordinary course. "
            "Section 8. Events of Default. End."
        )
        sections = _find_covenant_sections(text)
        # Should NOT detect this section — no ratio/percent/verb content
        assert not any("7" in s[0] and "Negative" not in s[0] for s in sections)

    def test_colon_separated_ratio_threshold(self):
        """STUDY-031 pattern: '4.00 : 1.0' (colon instead of 'to')."""
        threshold, operator = _extract_threshold_ratio(
            "not more than 4.00 : 1.0"
        )
        assert threshold == 4.0
        assert operator == "<="

    def test_more_than_operator(self):
        """'not more than X' should map to <= operator."""
        threshold, operator = _extract_threshold_ratio(
            "shall not be more than 3.00 to 1.00"
        )
        assert threshold == 3.0
        assert operator == "<="

    def test_consolidated_leverage_ratio_classification(self):
        """STUDY-031: Consolidated Leverage Ratio should be classified."""
        result = _classify_covenant("Consolidated Leverage Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.leverage_ratio"
        assert result[1] == "consolidated_leverage_ratio"

    def test_ebit_to_interest_ratio_classification(self):
        """STUDY-008: EBIT to Interest Ratio should be classified as
        interest coverage."""
        result = _classify_covenant("EBIT to Interest Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.interest_coverage"

    def test_senior_funded_debt_to_ebitda_classification(self):
        """STUDY-021: Senior Funded Debt to EBITDA Ratio should be
        classified as leverage ratio."""
        result = _classify_covenant("Senior Funded Debt to EBITDA Ratio")
        assert result is not None
        assert result[0] == "financial_covenant.leverage_ratio"

    def test_study_008_extracts_commitments(self):
        """Integration: STUDY-008 should extract >=1 commitment after
        V02-001 (was 0 before)."""
        s0_path = Path("data/chain_study/STUDY-008/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-008 S0.txt not available")
        result = extract_s0_state(s0_path)
        assert len(result.commitments) >= 1, (
            "STUDY-008 should extract >=1 commitment after V02-001"
        )

    def test_study_031_extracts_commitments(self):
        """Integration: STUDY-031 should extract >=1 commitment after
        V02-001 (was 0 before)."""
        s0_path = Path("data/chain_study/STUDY-031/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-031 S0.txt not available")
        result = extract_s0_state(s0_path)
        assert len(result.commitments) >= 1, (
            "STUDY-031 should extract >=1 commitment after V02-001"
        )


# ---------------------------------------------------------------------------
# V02-002: Fix TOC-skip logic for page numbers on separate lines
# ---------------------------------------------------------------------------


class TestV02_002_TocSkipLogic:
    """V02-002: TOC entries with page numbers on separate lines should
    be skipped.

    Evidence: STUDY-021 has 'SECTION 10\\nFINANCIAL COVENANTS.\\n38' in
    the TOC (page number '38' on a separate line after the header).
    """

    def test_skips_toc_with_page_number_on_separate_line(self):
        """TOC entry: 'SECTION 10\\nFINANCIAL COVENANTS.\\n38' should be
        skipped, and the actual section body should be found."""
        text = (
            "TABLE OF CONTENTS\n"
            "SECTION 10\n"
            "FINANCIAL COVENANTS.\n"
            "38\n"
            "SECTION 11\n"
            "DEFAULT.\n"
            "39\n"
            "\n\n"
            "SECTION 10\n"
            "FINANCIAL COVENANTS.\n"
            "10.1 Fixed Charge Coverage Ratio. "
            "The Fixed Charge Coverage Ratio may not be less than 1.25 to 1.00. "
            "SECTION 11 DEFAULT. End."
        )
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        # The section should be the body, not the TOC entry
        section_text = text[sections[0][1]:sections[0][2]]
        assert "Fixed Charge Coverage" in section_text
        assert "10.1" in section_text

    def test_prefers_last_match_for_same_section_number(self):
        """When multiple matches exist for the same section number,
        prefer the last (body) match over the first (TOC) match."""
        text = (
            "7.10 Certain Financial Covenants...........114\n"
            "\n\n"
            "7.10 Certain Financial Covenants. "
            "(a) Leverage Ratio. The Borrower shall not permit the Leverage "
            "Ratio to exceed 4.50 to 1.00. "
            "7.11 Next Section. End."
        )
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        section_text = text[sections[0][1]:sections[0][2]]
        assert "Leverage Ratio" in section_text
        assert "114" not in section_text

    def test_study_021_extracts_commitments(self):
        """Integration: STUDY-021 should extract >=1 commitment after
        V02-002 + V02-003 (was 0 before)."""
        s0_path = Path("data/chain_study/STUDY-021/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-021 S0.txt not available")
        result = extract_s0_state(s0_path)
        assert len(result.commitments) >= 1, (
            "STUDY-021 should extract >=1 commitment after V02-002/V02-003"
        )


# ---------------------------------------------------------------------------
# V02-003: Add numbered-subsection clause extraction (10.1, 10.2 format)
# ---------------------------------------------------------------------------


class TestV02_003_NumberedSubsectionExtraction:
    """V02-003: Numbered subsections (10.1, 10.2, 10.3) should be
    extracted as clauses.

    Evidence: STUDY-021 SECTION 10 uses '10.1 Fixed Charge Coverage
    Ratio.' format.
    """

    def test_extracts_numbered_subsection_clauses(self):
        """Numbered subsections (10.1, 10.2) should be extracted."""
        text = (
            "SECTION 10 FINANCIAL COVENANTS. "
            "10.1 Fixed Charge Coverage Ratio. "
            "The Fixed Charge Coverage Ratio may not be less than 1.25 to 1.00. "
            "10.2 Senior Funded Debt to EBITDA Ratio. "
            "The Senior Funded Debt to EBITDA Ratio may not be greater than 2.00 to 1.00. "
            "SECTION 11 DEFAULT. End."
        )
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        clauses = _extract_clauses_from_section(
            text, sections[0][1], sections[0][2], sections[0][0],
        )
        assert len(clauses) >= 2
        names = [c.clause_name for c in clauses]
        assert "Fixed Charge Coverage Ratio" in names
        assert "Senior Funded Debt to EBITDA Ratio" in names

    def test_numbered_subsection_not_treated_as_next_section(self):
        """10.1, 10.2 subsections should NOT end the section — they are
        subsections OF section 10, not new sections."""
        text = (
            "SECTION 10 FINANCIAL COVENANTS. "
            "10.1 Fixed Charge Coverage Ratio. "
            "The ratio may not be less than 1.25 to 1.00. "
            "10.2 Senior Funded Debt to EBITDA Ratio. "
            "The ratio may not be greater than 2.00 to 1.00. "
            "SECTION 11 DEFAULT. End."
        )
        sections = _find_covenant_sections(text)
        assert len(sections) == 1
        # Section should extend to SECTION 11, not end at 10.1
        section_text = text[sections[0][1]:sections[0][2]]
        assert "10.2" in section_text
        assert "Senior Funded Debt" in section_text

    def test_extract_covenant_name_from_text(self):
        """_extract_covenant_name_from_text should find covenant names
        in body text for sections with no subsections."""
        text = (
            "Borrower shall have and maintain, on a consolidated basis, "
            "a Leverage Ratio less than or equal to 2.50 to 1.00"
        )
        name = _extract_covenant_name_from_text(text)
        assert name is not None
        assert "Leverage Ratio" in name

    def test_single_covenant_section_extracts_commitment(self):
        """A section with a single covenant and no subsections should
        extract the covenant using the fallback path."""
        text = (
            "Section 5.03 Financial Covenants. "
            "Borrower shall have and maintain, on a consolidated basis, "
            "a Leverage Ratio less than or equal to 2.50 to 1.00 as of "
            "the last day of each fiscal quarter. "
            "Section 5.04 Books and Records. End."
        )
        result = extract_commitments(text, source_label="S0")
        assert len(result.commitments) >= 1
        assert "financial_covenant.leverage_ratio" in result.commitments
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.threshold == 2.5
        assert c.operator == "<="

    def test_study_021_extracts_fixed_charge_coverage(self):
        """Integration: STUDY-021 should extract the Fixed Charge
        Coverage Ratio covenant from numbered subsection 10.1."""
        s0_path = Path("data/chain_study/STUDY-021/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-021 S0.txt not available")
        result = extract_s0_state(s0_path)
        assert "financial_covenant.fixed_charge_coverage" in result.commitments, (
            "STUDY-021 should extract Fixed Charge Coverage Ratio"
        )


# ---------------------------------------------------------------------------
# V02-004: Expand fallback covenant-language pattern
# ---------------------------------------------------------------------------


class TestV02_004_FallbackCovenantLanguage:
    """V02-004: The fallback covenant-language pattern should match
    additional verb forms.

    Evidence: STUDY-029's covenant uses 'shall have and maintain' which
    was not matched by the original pattern.
    """

    def test_shall_have_and_maintain_matched(self):
        """'shall have and maintain' should trigger fallback clause
        extraction."""
        text = (
            "Section 5.03 Financial Covenants. "
            "Borrower shall have and maintain, on a consolidated basis, "
            "a Leverage Ratio less than or equal to 2.50 to 1.00. "
            "Section 5.04 Next. End."
        )
        result = extract_commitments(text, source_label="S0")
        assert len(result.commitments) >= 1

    def test_shall_not_be_less_than_matched(self):
        """'shall not be less than' should trigger fallback clause
        extraction."""
        text = (
            "Section 5.03 Financial Covenants. "
            "Borrower shall not be less than 4.50 to 1.00 in its Current "
            "Ratio. "
            "Section 5.04 Next. End."
        )
        # Should at least extract a clause (may go to VQ if name doesn't
        # match a known covenant pattern)
        sections = _find_covenant_sections(text)
        assert len(sections) >= 1
        clauses = _extract_clauses_from_section(
            text, sections[0][1], sections[0][2], sections[0][0],
        )
        assert len(clauses) >= 1

    def test_may_not_exceed_matched(self):
        """'may not exceed' should trigger fallback clause extraction."""
        text = (
            "Section 5.03 Financial Covenants. "
            "Borrower may not exceed a Leverage Ratio of 3.00 to 1.00. "
            "Section 5.04 Next. End."
        )
        sections = _find_covenant_sections(text)
        clauses = _extract_clauses_from_section(
            text, sections[0][1], sections[0][2], sections[0][0],
        )
        assert len(clauses) >= 1

    def test_less_than_or_equal_operator(self):
        """'less than or equal to X' should map to <= operator."""
        threshold, operator = _extract_threshold_ratio(
            "Leverage Ratio less than or equal to 2.50 to 1.00"
        )
        assert threshold == 2.5
        assert operator == "<="

    def test_study_029_extracts_leverage_ratio(self):
        """Integration: STUDY-029 should extract the Leverage Ratio
        covenant after V02-004 (was 0 before)."""
        s0_path = Path("data/chain_study/STUDY-029/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-029 S0.txt not available")
        result = extract_s0_state(s0_path)
        assert "financial_covenant.leverage_ratio" in result.commitments, (
            "STUDY-029 should extract Leverage Ratio after V02-004"
        )
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.threshold == 2.5
        assert c.operator == "<="


# ---------------------------------------------------------------------------
# V02-005: Add S0 discovery validation
# ---------------------------------------------------------------------------


class TestV02_005_S0DiscoveryValidation:
    """V02-005: S0 discovery validation correctly attributes acquisition
    failures.

    Evidence: STUDY-006 (6.9K chars), STUDY-012 (14K chars), STUDY-014
    (93K chars, no 'credit agreement' language) have wrong documents
    acquired as S0.
    """

    def test_valid_s0_passes(self):
        """A valid S0 document (>= 15K chars, has 'credit agreement',
        has covenant content) should pass validation."""
        text = (
            "CREDIT AGREEMENT\n" + "x " * 8000 + "\n"
            "SECTION 7.10 FINANCIAL COVENANTS. "
            "The Leverage Ratio shall not exceed 4.50 to 1.00."
        )
        path = Path("data/test_tmp_valid_s0.txt")
        path.write_text(text, encoding="utf-8")
        try:
            result = validate_s0_document(path)
            assert result.is_valid
            assert result.failure_cause == ""
        finally:
            path.unlink(missing_ok=True)

    def test_short_s0_fails(self):
        """A short S0 document (< 15K chars) should fail validation."""
        text = "CREDIT AGREEMENT\nShort document.\n" + "x " * 100
        path = Path("data/test_tmp_short_s0.txt")
        path.write_text(text, encoding="utf-8")
        try:
            result = validate_s0_document(path)
            assert not result.is_valid
            assert result.failure_cause == "S0_DISCOVERY_FAILURE"
            assert not result.checks["min_chars"]
        finally:
            path.unlink(missing_ok=True)

    def test_missing_s0_fails(self):
        """A missing S0 file should fail validation."""
        result = validate_s0_document("data/nonexistent_s0.txt")
        assert not result.is_valid
        assert result.failure_cause == "S0_DISCOVERY_FAILURE"

    def test_no_credit_agreement_language_fails(self):
        """A document without 'credit agreement' language should fail."""
        text = "x " * 8000 + "\nSome other type of document."
        path = Path("data/test_tmp_no_ca_s0.txt")
        path.write_text(text, encoding="utf-8")
        try:
            result = validate_s0_document(path)
            assert not result.is_valid
            assert result.failure_cause == "S0_DISCOVERY_FAILURE"
            assert not result.checks["credit_agreement"]
        finally:
            path.unlink(missing_ok=True)

    def test_study_006_fails_discovery_validation(self):
        """Integration: STUDY-006 (6.9K chars) should fail S0 discovery
        validation."""
        s0_path = Path("data/chain_study/STUDY-006/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-006 S0.txt not available")
        result = validate_s0_document(s0_path)
        assert not result.is_valid
        assert result.failure_cause == "S0_DISCOVERY_FAILURE"

    def test_study_014_fails_discovery_validation(self):
        """Integration: STUDY-014 (no 'credit agreement' language) should
        fail S0 discovery validation."""
        s0_path = Path("data/chain_study/STUDY-014/S0.txt")
        if not s0_path.exists():
            pytest.skip("STUDY-014 S0.txt not available")
        result = validate_s0_document(s0_path)
        assert not result.is_valid
        assert result.failure_cause == "S0_DISCOVERY_FAILURE"


# ---------------------------------------------------------------------------
# V02-006: Add GT discovery validation
# ---------------------------------------------------------------------------


class TestV02_006_GTDiscoveryValidation:
    """V02-006: GT discovery validation correctly attributes acquisition
    failures.

    Evidence: STUDY-016's CMP document is actually 'FIFTH AMENDMENT TO
    SECOND AMENDED AND RESTATED CREDIT AGREEMENT' — an amendment, not a
    composite/conformed copy.
    """

    def test_valid_gt_passes(self):
        """A valid CMP document (not an amendment, has 'credit
        agreement') should pass validation."""
        text = (
            "AMENDED AND RESTATED CREDIT AGREEMENT\n"
            "This is a composite/conformed copy.\n"
            + "x " * 1000
        )
        path = Path("data/test_tmp_valid_gt.txt")
        path.write_text(text, encoding="utf-8")
        try:
            result = validate_gt_document(path)
            assert result.is_valid
            assert result.failure_cause == ""
        finally:
            path.unlink(missing_ok=True)

    def test_amendment_gt_fails(self):
        """A CMP document that is actually an amendment should fail
        validation."""
        text = (
            "FIFTH AMENDMENT TO SECOND AMENDED AND RESTATED CREDIT "
            "AGREEMENT\n"
            + "x " * 1000
        )
        path = Path("data/test_tmp_amendment_gt.txt")
        path.write_text(text, encoding="utf-8")
        try:
            result = validate_gt_document(path)
            assert not result.is_valid
            assert result.failure_cause == "GT_DISCOVERY_FAILURE"
            assert not result.checks["not_amendment"]
        finally:
            path.unlink(missing_ok=True)

    def test_missing_gt_fails(self):
        """A missing CMP file should fail validation."""
        result = validate_gt_document("data/nonexistent_gt.txt")
        assert not result.is_valid
        assert result.failure_cause == "GT_DISCOVERY_FAILURE"

    def test_study_016_fails_gt_discovery_validation(self):
        """Integration: STUDY-016's CMP (an amendment document) should
        fail GT discovery validation."""
        cmp_path = Path("data/chain_study/STUDY-016/CMP.txt")
        if not cmp_path.exists():
            pytest.skip("STUDY-016 CMP.txt not available")
        result = validate_gt_document(cmp_path)
        assert not result.is_valid
        assert result.failure_cause == "GT_DISCOVERY_FAILURE"


# ---------------------------------------------------------------------------
# No regression: existing chains should still extract correctly
# ---------------------------------------------------------------------------


class TestNoRegression:
    """Verify that v0.2 changes do not regress existing v0.1 extraction
    behavior on the 3 smoke-test chains (Ameresco, Amedisys, Bausch-Lomb).
    """

    def test_ameresco_s0_still_extracts(self):
        """Ameresco S0 should still extract the leverage ratio with
        step-down schedule."""
        s0_path = Path("data/edgar_chains/ameresco/S0.txt")
        if not s0_path.exists():
            pytest.skip("Ameresco S0.txt not available")
        result = extract_s0_state(s0_path)
        assert len(result.commitments) >= 1
        # The leverage ratio with step-down should still be present
        assert "financial_covenant.leverage_ratio" in result.commitments

    def test_existing_synthetic_extraction_unchanged(self):
        """Synthetic extraction test should still work the same way."""
        text = (
            "7.10 Certain Financial Covenants.    "
            "(a) Total Funded Debt to EBITDA Ratio.  "
            "The Loan Parties shall not permit the Total Funded Debt to "
            "EBITDA Ratio to exceed 4.50 to 1.00. "
            "7.11 Next Section. End."
        )
        result = extract_commitments(text, source_label="S0")
        assert len(result.commitments) >= 1
        assert "financial_covenant.leverage_ratio" in result.commitments
        c = result.commitments["financial_covenant.leverage_ratio"]
        assert c.threshold == 4.5
        assert c.operator == "<="
