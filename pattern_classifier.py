"""Amendment pattern classification for real EDGAR filings.

Real SEC credit-agreement amendments come in at least three structural
patterns.  The parser can only handle one of them automatically; the
others require different processing strategies.  This module classifies
a filing's amendment pattern so the reconstruction pipeline can route
it to the correct handler.

Patterns
--------

INCREMENTAL
    Explicit section-level amendment language:
        "Section 7.10 is hereby amended by deleting paragraph (a)
         and replacing it with the following: ..."
    The parser (parse_v04) extracts section-level instructions from
    this pattern.  This is the only pattern the parser currently
    supports.

FULL_RESTATEMENT
    The entire credit agreement is replaced by an Annex A composite:
        "The Existing Credit Agreement is amended in its entirety
         to read in the form attached hereto as Annex A."
    The amendment text is short (~2-4K chars); the rest of the filing
    is the full restated credit agreement (Annex A).  The parser finds
    0 instructions because there are no section-level changes — the
    entire document is replaced.
    Strategy: treat the latest Annex A composite as the new
    authoritative base state.  Do NOT replay amendments; extract
    commitment state directly from the composite.

CONFORMED_COPY
    Changes are embedded as marked-up text (strikethrough +
    double-underline) in a full conformed copy of the credit
    agreement:
        "the Credit Agreement is hereby amended to delete the
         stricken text and add the double-underlined text as set
         forth in the conformed copy of the Amended Credit Agreement
         attached as Annex A hereto."
    The parser finds 0 instructions because the changes are not
    expressed as explicit section-level amendment language.
    Strategy: parse the final clean state from the Annex A conformed
    copy (strip redline markup).  Use the redlines for lineage and
    explanation, not for instruction extraction.

UNKNOWN
    The filing does not match any known pattern.  Flag for manual
    review.

Classification order
--------------------

Full restatement is checked first (most specific: "amended in its
entirety to read in the form").  Conformed copy is checked second
("stricken text" + "double-underlined" or "conformed copy").  These
two patterns can co-occur with incremental language (e.g., B&L A1
says "is hereby amended to delete the stricken text"), so the more
specific patterns must be checked before the incremental pattern.

Incremental is checked third.  If none match, the filing is UNKNOWN.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class AmendmentPattern(str, Enum):
    """Structural pattern of a credit-agreement amendment filing."""

    INCREMENTAL = "incremental"
    FULL_RESTATEMENT = "full_restatement"
    CONFORMED_COPY = "conformed_copy"
    UNKNOWN = "unknown"


@dataclass
class PatternClassification:
    """Result of classifying a filing's amendment pattern.

    Fields:
        pattern: the detected AmendmentPattern
        confidence: 0.0–1.0 (1.0 for unambiguous keyword match)
        evidence: list of (pattern_name, matched_text_snippet) tuples
        annex_a_detected: True if the filing contains an Annex A
            reference (common to full restatement and conformed copy)
        parser_supported: True if parse_v04 can extract instructions
            from this pattern (currently only INCREMENTAL)
        recommended_strategy: human-readable processing strategy
    """

    pattern: AmendmentPattern
    confidence: float
    evidence: list[tuple[str, str]]
    annex_a_detected: bool
    parser_supported: bool
    recommended_strategy: str


# ---------------------------------------------------------------------------
# Pattern signatures (checked in priority order)
# ---------------------------------------------------------------------------

_SIGNATURES: list[tuple[AmendmentPattern, str, str]] = [
    # Full restatement: most specific, check first.
    # "amended in its entirety to read in the form attached hereto as Annex A"
    # Words may be split across newlines in extracted text.
    (
        AmendmentPattern.FULL_RESTATEMENT,
        "full_restatement",
        r"amended\s+in\s+its\s+entirety\s+to\s+read\s+in\s+the\s+form",
    ),
    # Conformed copy: strikethrough + double-underline in conformed copy.
    # Check before incremental because conformed copies can contain
    # "is hereby amended to delete the stricken text" which would
    # falsely match the incremental pattern.
    (
        AmendmentPattern.CONFORMED_COPY,
        "conformed_copy_stricken_double_underlined",
        r"stricken\s+text.*?double.?underlined\s+text",
    ),
    (
        AmendmentPattern.CONFORMED_COPY,
        "conformed_copy_explicit",
        r"conformed\s+copy\s+of\s+the\s+Amended\s+Credit\s+Agreement",
    ),
    # Incremental: explicit section-level amendment language.
    (
        AmendmentPattern.INCREMENTAL,
        "incremental_section_amended_by",
        r"Section\s+[\d.]+\w*\s+is\s+hereby\s+amended\s+by",
    ),
    (
        AmendmentPattern.INCREMENTAL,
        "incremental_is_hereby_amended_to_delete",
        r"is\s+hereby\s+amended\s+to\s+delete\s+(?!the\s+stricken\s+text)",
    ),
    (
        AmendmentPattern.INCREMENTAL,
        "incremental_is_hereby_amended_by_deleting",
        r"is\s+hereby\s+amended\s+by\s+deleting",
    ),
    (
        AmendmentPattern.INCREMENTAL,
        "incremental_is_hereby_amended_by_replacing",
        r"is\s+hereby\s+amended\s+by\s+replacing",
    ),
    (
        AmendmentPattern.INCREMENTAL,
        "incremental_section_amended_to_read",
        r"Section\s+[\d.]+\w*\s+is\s+hereby\s+amended\s+to\s+read",
    ),
]

_ANNEX_A_RX = re.compile(r"Annex\s+A", re.IGNORECASE)
_FULL_RESTATEMENT_RX = re.compile(
    r"amended in its entirety to read in the form", re.IGNORECASE | re.DOTALL
)
_CONFORMED_COPY_RX = re.compile(
    r"stricken text.*double.?underlined text|conformed copy of the Amended Credit Agreement",
    re.IGNORECASE | re.DOTALL,
)


def classify_amendment(text: str, scan_limit: int = 200_000) -> PatternClassification:
    """Classify the amendment pattern of a filing's text.

    Args:
        text: the full text of the filing (or at least the amendment
            portion).  The first scan_limit chars are scanned for
            pattern signatures.
        scan_limit: maximum chars to scan (default 200K).  Amendment
            language appears early in the filing; the Annex A composite
            can be 600K+ chars and does not need to be fully scanned.

    Returns:
        PatternClassification with the detected pattern, confidence,
        evidence, and recommended strategy.
    """
    scan_text = text[:scan_limit]

    evidence: list[tuple[str, str]] = []
    detected_pattern = AmendmentPattern.UNKNOWN
    max_confidence = 0.0

    for pattern, sig_name, sig_rx in _SIGNATURES:
        m = re.search(sig_rx, scan_text, re.IGNORECASE | re.DOTALL)
        if m:
            snippet = scan_text[m.start() : m.start() + 120].replace("\n", " ").strip()
            evidence.append((sig_name, snippet))
            # Full restatement and conformed copy are high-confidence
            # single-keyword patterns.  Incremental is medium-confidence
            # because it can co-occur with conformed copy.
            if pattern in (AmendmentPattern.FULL_RESTATEMENT, AmendmentPattern.CONFORMED_COPY):
                max_confidence = max(max_confidence, 0.95)
            else:
                max_confidence = max(max_confidence, 0.80)
            detected_pattern = pattern
            # Full restatement and conformed copy are terminal — once
            # detected, they take priority over incremental.
            if pattern in (AmendmentPattern.FULL_RESTATEMENT, AmendmentPattern.CONFORMED_COPY):
                break

    annex_a_detected = bool(_ANNEX_A_RX.search(scan_text))

    # Parser support: only incremental is currently supported.
    parser_supported = detected_pattern == AmendmentPattern.INCREMENTAL

    strategies = {
        AmendmentPattern.INCREMENTAL: (
            "Use parse_v04 to extract section-level instructions. "
            "Map to commitment-level changes via semantic mapping layer."
        ),
        AmendmentPattern.FULL_RESTATEMENT: (
            "Do NOT replay amendments.  Treat the latest Annex A composite "
            "as the new authoritative base state.  Extract commitment state "
            "directly from the composite document."
        ),
        AmendmentPattern.CONFORMED_COPY: (
            "Parse the final clean state from the Annex A conformed copy "
            "(strip redline markup).  Use redlines for lineage and "
            "explanation, not for instruction extraction."
        ),
        AmendmentPattern.UNKNOWN: (
            "Pattern not recognized.  Flag for manual review."
        ),
    }

    return PatternClassification(
        pattern=detected_pattern,
        confidence=max_confidence,
        evidence=evidence,
        annex_a_detected=annex_a_detected,
        parser_supported=parser_supported,
        recommended_strategy=strategies[detected_pattern],
    )


def pattern_from_text(text: str) -> AmendmentPattern:
    """Convenience: classify and return just the pattern enum."""
    return classify_amendment(text).pattern
