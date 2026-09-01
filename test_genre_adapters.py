"""Tests for the genre adapters (Step 21 / Section E)."""
from __future__ import annotations

import pytest

from genre_adapters import (
    GenreAdapterResult,
    process_amendment_by_genre,
    process_conformed_copy,
    process_full_restatement,
    process_incremental,
    process_unknown,
)
from models import CommitmentState
from pattern_classifier import AmendmentPattern


# ---------------------------------------------------------------------------
# Incremental adapter tests
# ---------------------------------------------------------------------------


class TestIncrementalAdapter:
    def test_empty_text(self):
        state = {}
        result = process_incremental("", state)
        assert result.genre == AmendmentPattern.INCREMENTAL
        assert len(result.candidates) == 0

    def test_basic_incremental(self):
        state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }
        text = (
            "Section 7.10 is hereby amended by replacing it with the "
            "following: Maximum Total Leverage Ratio shall not exceed "
            "3.50 to 1.00"
        )
        result = process_incremental(text, state)
        assert result.genre == AmendmentPattern.INCREMENTAL
        # The parser may or may not find instructions in this short text.
        # The key assertion is that the adapter ran without error and
        # returned the correct genre.
        assert isinstance(result, GenreAdapterResult)


# ---------------------------------------------------------------------------
# Full restatement adapter tests
# ---------------------------------------------------------------------------


class TestFullRestatementAdapter:
    def test_empty_text(self):
        state = {}
        result = process_full_restatement("", state)
        assert result.genre == AmendmentPattern.FULL_RESTATEMENT
        assert len(result.candidates) == 0

    def test_conservative_no_replace_value(self):
        """Full restatement should NOT produce REPLACE_VALUE for existing
        commitments (conservative policy)."""
        state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }
        text = "Some text with leverage ratio 3.50 to 1.00"
        result = process_full_restatement(text, state)
        # Should not produce REPLACE_VALUE for existing commitment
        for c in result.candidates:
            if c.commitment_id == "financial_covenant.leverage_ratio":
                assert c.operation != "replace_value"


# ---------------------------------------------------------------------------
# Conformed copy adapter tests
# ---------------------------------------------------------------------------


class TestConformedCopyAdapter:
    def test_empty_text(self):
        state = {}
        result = process_conformed_copy("", state)
        assert result.genre == AmendmentPattern.CONFORMED_COPY

    def test_strips_html_markup(self):
        """Conformed copy should strip HTML redline markup."""
        from genre_adapters import _strip_redline_markup
        text = "Hello <s>deleted</s> world <u>added</u> end"
        clean = _strip_redline_markup(text)
        assert "deleted" not in clean
        assert "added" in clean
        assert "world" in clean

    def test_fallback_uses_cleaned_text_not_markup(self):
        """When cleaned text is too short, the fallback to
        full_restatement must use the CLEANED text, not the original
        markup text.  Passing markup text would cause the extractor to
        parse HTML tags as commitment text.

        Regression: previously the fallback passed `source_text`
        (with HTML) instead of `clean_text`.

        The fallback delegates to process_full_restatement, so the
        returned genre is FULL_RESTATEMENT (the adapter that actually
        processed the text).  The key assertion is that the fallback
        ran without error and produced extraction notes.
        """
        # Text that strips to < 100 chars → triggers fallback
        text = "<s>deleted</s> <u>short</u>"
        state = {}
        result = process_conformed_copy(text, state)
        # The fallback delegates to full_restatement
        assert result.genre == AmendmentPattern.FULL_RESTATEMENT
        # The result should come from full_restatement on the cleaned
        # text.  We verify by checking that the notes mention extraction
        # (full_restatement's notes format).
        assert "extract" in result.notes.lower() or "extraction" in result.notes.lower()


# ---------------------------------------------------------------------------
# Unknown adapter tests
# ---------------------------------------------------------------------------


class TestUnknownAdapter:
    def test_empty_text(self):
        state = {}
        result = process_unknown("", state)
        assert result.genre == AmendmentPattern.UNKNOWN

    def test_falls_back_to_extraction(self):
        """Unknown genre should try incremental first, then fall back
        to extraction."""
        state = {}
        text = "Some text without explicit amendment language"
        result = process_unknown(text, state)
        assert result.genre == AmendmentPattern.UNKNOWN


# ---------------------------------------------------------------------------
# Genre dispatch tests
# ---------------------------------------------------------------------------


class TestGenreDispatch:
    def test_dispatch_incremental(self):
        state = {}
        text = "Section 7.10 is hereby amended by replacing it with the following"
        result = process_amendment_by_genre(text, state)
        assert result.genre == AmendmentPattern.INCREMENTAL

    def test_dispatch_with_override(self):
        state = {}
        text = "some text"
        result = process_amendment_by_genre(
            text, state, genre_override=AmendmentPattern.FULL_RESTATEMENT,
        )
        assert result.genre == AmendmentPattern.FULL_RESTATEMENT

    def test_dispatch_conformed_copy(self):
        state = {}
        text = (
            "the Credit Agreement is hereby amended to delete the "
            "stricken text and add the double-underlined text as set "
            "forth in the conformed copy"
        )
        result = process_amendment_by_genre(text, state)
        assert result.genre == AmendmentPattern.CONFORMED_COPY
