"""Tests for the amendment pattern classifier.

Tests that the classifier correctly identifies all three amendment
patterns from real EDGAR filing text, and that the classification
determines the correct parser support flag and recommended strategy.
"""
from __future__ import annotations

from pathlib import Path

from pattern_classifier import (
    AmendmentPattern,
    classify_amendment,
    pattern_from_text,
)


_EDGAR_DIR = Path("data/edgar_chains")


def _read(path: str) -> str:
    return (_EDGAR_DIR / path).read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# Synthetic text tests (no EDGAR data dependency)
# ---------------------------------------------------------------------------


def test_incremental_pattern_detected():
    """Incremental section-level language is classified correctly."""
    text = (
        "WHEREAS, Section 7.10 of the Credit Agreement is hereby amended "
        "by deleting paragraph (a) in its entirety and replacing it with "
        "the following: (a) Total Funded Debt to EBITDA Ratio..."
    )
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.INCREMENTAL
    assert result.parser_supported is True
    assert result.confidence >= 0.80


def test_full_restatement_pattern_detected():
    """Full restatement language is classified correctly."""
    text = (
        "WHEREAS, the Existing Credit Agreement is amended in its entirety "
        "to read in the form attached hereto as Annex A (the credit "
        "agreement attached hereto as Annex A being referred to herein "
        "as the 'Amended Credit Agreement')."
    )
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.FULL_RESTATEMENT
    assert result.parser_supported is False
    assert result.annex_a_detected is True
    assert result.confidence >= 0.95


def test_conformed_copy_pattern_detected():
    """Conformed copy language is classified correctly."""
    text = (
        "the Credit Agreement is hereby amended to delete the stricken text "
        "(indicated textually in the same manner as the following example: "
        "stricken text) and to add the double-underlined text (indicated "
        "textually in the same manner as the following example: "
        "double-underlined text) as set forth in the conformed copy of the "
        "Amended Credit Agreement attached as Annex A hereto."
    )
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.CONFORMED_COPY
    assert result.parser_supported is False
    assert result.annex_a_detected is True
    assert result.confidence >= 0.95


def test_unknown_pattern_for_unrecognized_text():
    """Unrecognized text is classified as UNKNOWN."""
    text = "This is a random legal document with no amendment language."
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.UNKNOWN
    assert result.parser_supported is False
    assert result.confidence == 0.0


def test_full_restatement_takes_priority_over_incremental():
    """Full restatement is checked before incremental (priority order)."""
    text = (
        "Section 2.07 is hereby amended by deleting it in its entirety. "
        "The Existing Credit Agreement is amended in its entirety to read "
        "in the form attached hereto as Annex A."
    )
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.FULL_RESTATEMENT


def test_conformed_copy_takes_priority_over_incremental():
    """Conformed copy is checked before incremental (priority order)."""
    text = (
        "the Credit Agreement is hereby amended to delete the stricken text "
        "and to add the double-underlined text as set forth in the conformed "
        "copy of the Amended Credit Agreement attached as Annex A hereto. "
        "Section 2.07 is hereby amended by deleting paragraph (a)."
    )
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.CONFORMED_COPY


def test_newline_split_text_handled():
    """Words split across newlines in extracted text are handled."""
    text = (
        "The Existing Credit Agreement is amended in its\n"
        "entirety to read\n"
        "in the form attached hereto as\n"
        "Annex A"
    )
    result = classify_amendment(text)
    assert result.pattern == AmendmentPattern.FULL_RESTATEMENT


def test_evidence_contains_snippet():
    """Classification evidence includes a text snippet."""
    text = "Section 7.10 is hereby amended by deleting paragraph (a)."
    result = classify_amendment(text)
    assert len(result.evidence) > 0
    sig_name, snippet = result.evidence[0]
    assert "Section 7.10" in snippet or "amended by" in snippet


def test_recommended_strategy_populated():
    """Each pattern has a recommended strategy."""
    for text, expected_pattern in [
        ("Section 7.10 is hereby amended by deleting paragraph (a).", AmendmentPattern.INCREMENTAL),
        ("amended in its entirety to read in the form", AmendmentPattern.FULL_RESTATEMENT),
        ("stricken text and double-underlined text", AmendmentPattern.CONFORMED_COPY),
        ("random text", AmendmentPattern.UNKNOWN),
    ]:
        result = classify_amendment(text)
        assert result.recommended_strategy, f"No strategy for {result.pattern}"
        assert len(result.recommended_strategy) > 10


def test_pattern_from_text_convenience():
    """pattern_from_text returns just the enum."""
    text = "Section 7.10 is hereby amended by deleting paragraph (a)."
    assert pattern_from_text(text) == AmendmentPattern.INCREMENTAL


# ---------------------------------------------------------------------------
# Real EDGAR document tests (skip if data not present)
# ---------------------------------------------------------------------------


def _has_edgar_data() -> bool:
    return _EDGAR_DIR.exists() and any(_EDGAR_DIR.rglob("*.txt"))


def test_real_ameresco_amendments_classified_incremental():
    """All 3 Ameresco amendments are classified as incremental."""
    if not _has_edgar_data():
        import pytest
        pytest.skip("EDGAR chain data not present")
    for path in [
        "ameresco/A1_amend_2023_08.txt",
        "ameresco/A2_amend_2023_12.txt",
        "ameresco/A3_sixth_amend_2024.txt",
    ]:
        result = classify_amendment(_read(path))
        assert result.pattern == AmendmentPattern.INCREMENTAL, f"{path}: expected incremental, got {result.pattern}"
        assert result.parser_supported is True


def test_real_amedisys_amendments_classified_full_restatement():
    """Both Amedisys amendments are classified as full restatement."""
    if not _has_edgar_data():
        import pytest
        pytest.skip("EDGAR chain data not present")
    for path in [
        "amedisys/A1_first_amend_2019.txt",
        "amedisys/A2_second_amend_2021.txt",
    ]:
        result = classify_amendment(_read(path))
        assert result.pattern == AmendmentPattern.FULL_RESTATEMENT, f"{path}: expected full_restatement, got {result.pattern}"
        assert result.parser_supported is False
        assert result.annex_a_detected is True


def test_real_bausch_lomb_amendments_classified_conformed_copy():
    """All 4 Bausch & Lomb amendments are classified as conformed copy."""
    if not _has_edgar_data():
        import pytest
        pytest.skip("EDGAR chain data not present")
    for path in [
        "bausch_lomb/A1_first_incremental_2023.txt",
        "bausch_lomb/A2_second_incremental_2024.txt",
        "bausch_lomb/A3_third_amend_2025.txt",
        "bausch_lomb/A4_fourth_amend_2026.txt",
    ]:
        result = classify_amendment(_read(path))
        assert result.pattern == AmendmentPattern.CONFORMED_COPY, f"{path}: expected conformed_copy, got {result.pattern}"
        assert result.parser_supported is False
        assert result.annex_a_detected is True
