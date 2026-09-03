"""Shared commitment extraction engine v0.1.

Extracts structured CommitmentState objects from credit agreement text.
Used by BOTH:

  - s0_extractor.py  (origin-state extraction from S0 documents)
  - gt_extractor.py  (ground-truth extraction from composite/conformed documents)

CRITICAL ARCHITECTURAL PRINCIPLE:
    prediction path != validation path

The S0 extractor feeds the reconstruction pipeline (origin state).
The GT extractor feeds the comparison (ground truth state).
Both use the SAME deterministic extraction rules, but they process
DIFFERENT documents and their outputs are used for DIFFERENT purposes.
Neither uses amendment reconstruction output to construct the other.

v0.1 scope — high-confidence patterns only:
  1. Financial covenants with explicit numeric thresholds:
     - Leverage ratios (Total Debt to EBITDA, Debt to EBITDAX, etc.)
     - Debt service coverage ratios
     - Fixed charge coverage ratios
     - Interest coverage ratios
     - Current ratios
     - Tangible net worth ratios
     - Bank regulatory ratios (Tier 1 Leverage, Risk-Based Capital,
       Texas Ratio, Return on Average Assets)
  2. Step-down threshold schedules (Ameresco pattern)
  3. Facility commitments with explicit dollar amounts

Unsupported clauses → validation queue. No guessing.

Extraction strategy:
  1. Segment the document to find financial covenant sections.
  2. Extract individual covenant clauses using deterministic regex rules.
  3. Convert each clause to a CommitmentState object.
  4. Route unsupported clauses to a validation queue with reason.

A bad automatic extraction is worse than a missed one. Uncertain
extractions are routed to the validation queue, never to a best-guess
CommitmentState.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from upsilon.models.legacy_models import CommitmentState

# ---------------------------------------------------------------------------
# Extraction result
# ---------------------------------------------------------------------------


@dataclass
class ExtractedClause:
    """A clause identified in the source text that may contain a commitment."""

    section_ref: str
    clause_name: str
    text: str
    start_offset: int
    end_offset: int


@dataclass
class ValidationItem:
    """A clause that could not be extracted with high confidence.

    Routed to the validation queue for manual review. No CommitmentState
    is produced — the clause is NOT guessed.
    """

    section_ref: str
    clause_name: str
    text: str
    reason: str  # why extraction failed


@dataclass
class ExtractionResult:
    """Result of extracting commitments from a credit agreement document.

    Fields:
        commitments: successfully extracted CommitmentState objects,
            keyed by canonical_key.
        validation_queue: clauses that could not be extracted with high
            confidence. These are NOT commitments — they require manual
            review.
        provenance: per-commitment provenance records (source span,
            confidence, rule matched).
        source_label: label for the source document (e.g., "S0" or "CMP").
        source_path: path to the source text file.
        text_length: total character count of the source text.
    """

    commitments: dict[str, CommitmentState] = field(default_factory=dict)
    validation_queue: list[ValidationItem] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    source_label: str = ""
    source_path: str = ""
    text_length: int = 0

    @property
    def extraction_coverage(self) -> float:
        """Fraction of identified clauses that were successfully extracted."""
        total = len(self.commitments) + len(self.validation_queue)
        if total == 0:
            return 0.0
        return len(self.commitments) / total


# ---------------------------------------------------------------------------
# Document segmentation — find financial covenant sections
# ---------------------------------------------------------------------------


# Section header patterns for financial covenants. These match:
#   "Section 7.10 Certain Financial Covenants"
#   "SECTION 8.13 Financial Covenants"
#   "Section 9.01 Financial Covenants."
#   "7.10 Certain Financial Covenants."  (bare number, no "Section" prefix)
#   "ARTICLE VIII FINANCIAL COVENANTS"  (roman numeral article)
_FINANCIAL_COVENANT_SECTION_RE = re.compile(
    r"(?:(?:Section|SECTION|ARTICLE)\s+)?"
    r"([\d.]+|[IVX]+)\s+"
    r"(?:Certain\s+)?Financial\s+Covenants",
    re.IGNORECASE,
)

# Some agreements use "Financial Covenant" in the section title without
# the word "Certain". Also catch "Negative Covenants" sections that
# contain financial covenants as subsections.
_COVENANT_SECTION_RE = re.compile(
    r"(?:(?:Section|SECTION|ARTICLE)\s+)?"
    r"([\d.]+|[IVX]+)\s+"
    r"(?:Certain\s+)?(?:Financial\s+)?Covenants",
    re.IGNORECASE,
)

# V02-001: Non-standard covenant section headers. Some credit agreements
# put financial covenants under headers that don't include the word
# "Covenants" at all. The most common alternative is "Financial
# Condition" (STUDY-008: "SECTION 4.9. FINANCIAL CONDITION"). We match
# these separately and then apply content-based validation to confirm
# the section actually contains covenant language (ratio thresholds,
# maintain-language, etc.) before treating it as a covenant section.
_NONSTANDARD_COVENANT_SECTION_RE = re.compile(
    r"(?:(?:Section|SECTION|ARTICLE)\s+)?"
    r"([\d.]+|[IVX]+)\s+"
    r"(?:Certain\s+)?Financial\s+Condition",
    re.IGNORECASE,
)

# V02-001: Broader covenant section patterns that include
# "Affirmative Covenants" and "Negative Covenants" headers. These
# sections often contain financial covenants as subsections (e.g.,
# STUDY-031: "Section 5.01 Affirmative Covenants" with ratio covenants
# as subsections (b) and (c)). Content-based validation is applied
# downstream to confirm the section contains ratio/percent thresholds
# or covenant verbs before treating it as a covenant section.
_BROAD_COVENANT_SECTION_RE = re.compile(
    r"(?:(?:Section|SECTION|ARTICLE)\s+)?"
    r"([\d.]+|[IVX]+)\s+"
    r"(?:Certain\s+)?(?:Affirmative|Negative)\s+Covenants",
    re.IGNORECASE,
)

# Content-based detection: ratio thresholds ("X.XX to 1.00" or
# "X.XX : 1.0"), percentage thresholds, and covenant verb language.
# Used to confirm that a non-standard section header actually contains
# covenant content before treating it as a covenant section.
_RATIO_THRESHOLD_RE = re.compile(
    r"[\d.]+\s*(?:to|:)\s*1\.0+", re.IGNORECASE,
)
_COVENANT_VERB_RE = re.compile(
    r"shall\s+(?:not\s+)?(?:permit|maintain|have\s+and\s+maintain|be\s+"
    r"(?:less|greater)\s+than|exceed)"
    r"|may\s+not\s+(?:be\s+)?(?:less|greater)\s+than"
    r"|will\s+not\s+permit",
    re.IGNORECASE,
)


def _find_covenant_sections(text: str) -> list[tuple[str, int, int]]:
    """Find financial covenant sections in the document.

    Returns a list of (section_ref, start_offset, end_offset) tuples.
    The end_offset is the start of the next section or article, or the
    end of the document.

    We skip table-of-contents entries (which have page numbers or
    dot-leader patterns following the section title).

    V02-001: In addition to "Financial Covenants" headers, we now detect:
      - "Financial Condition" headers (STUDY-008 pattern)
      - "Affirmative Covenants" / "Negative Covenants" headers when the
        section content contains ratio thresholds or covenant verbs
        (STUDY-031, STUDY-004 patterns)
    Content-based validation is applied to non-standard headers to
    avoid false positives from non-covenant sections.
    """
    sections: list[tuple[str, int, int]] = []
    seen_starts: set[int] = set()

    # V02-002: Helper to find the end of a section (next section header).
    def _find_section_end(text: str, match_end: int, section_num: str) -> int:
        remaining = text[match_end:]
        current_num = section_num
        for sm in re.finditer(
            r"(?:(?:Section|SECTION|ARTICLE)\s+)?"
            r"(\d+(?:\.\d+)?|[IVX]+)\s*\.?\s*"
            r"([A-Z][a-zA-Z]+\s+[A-Z])",
            remaining,
        ):
            candidate_num = sm.group(1)
            if candidate_num == current_num:
                continue
            # V02-003: Skip numbered subsections of the current section
            # (e.g., "10.1", "10.2" when current section is "10"). These
            # are subsections OF the current section, not new sections.
            if "." in candidate_num and candidate_num.split(".")[0] == current_num:
                continue
            if not candidate_num.startswith(tuple("0123456789")) or \
               "." in candidate_num:
                pass
            elif len(candidate_num) == 1 and \
                 not re.match(r"(?:Section|SECTION|ARTICLE)\s+",
                              remaining[sm.start():sm.start()+20],
                              re.IGNORECASE):
                continue
            has_prefix = re.match(
                r"(?:Section|SECTION|ARTICLE)\s+",
                remaining[sm.start():sm.start()+20],
                re.IGNORECASE,
            )
            abs_pos = match_end + sm.start()
            before = text[max(0, abs_pos - 5):abs_pos]
            at_line_start = re.search(r"(?:\n\s*|\.\s+)$", before)
            if has_prefix or at_line_start:
                return match_end + sm.start()
        return len(text)

    # V02-002: Helper to check if a match is a TOC entry.
    def _is_toc_entry(m: re.Match, text: str) -> bool:
        """Check if a section header match is a table-of-contents entry.

        V02-002: In addition to dot-leader patterns, we now also detect
        page numbers on separate lines (STUDY-021 pattern: the TOC has
        "SECTION 10\\nFINANCIAL COVENANTS.\\n38" where "38" is a page
        number on a separate line after the header).
        """
        after = text[m.end():m.end() + 20]
        if re.match(r"\s*\.{3,}", after):
            return True
        # V02-002: Check for page number on a separate line within 10
        # chars after the match. This catches TOC entries like:
        #   "SECTION 10\nFINANCIAL COVENANTS.\n38"
        # where "38" is a page number on its own line. The pattern
        # allows an optional period (from the header ".") before the
        # newline that precedes the page number.
        after_10 = text[m.end():m.end() + 10]
        if re.match(r"[\s.]*\n\s*\d{1,4}\s*\n", after_10):
            return True
        # Also skip if the match is in the first 10% of the document
        # AND followed by dot leaders within 50 chars (common TOC pattern).
        if m.start() < len(text) * 0.1:
            after_more = text[m.end():m.end() + 50]
            if re.search(r"\.{3,}", after_more):
                return True
            # V02-002: Also check for page number on separate line in
            # the first 15% of the document (broader TOC detection).
            after_15 = text[m.end():m.end() + 15]
            if re.match(r"[\s.]*\n\s*\d{1,4}\s*\n", after_15):
                return True
        return False

    # V02-002: Collect all matches for each section number so we can
    # prefer the last (body) match over the first (TOC) match.
    section_matches: dict[str, list[re.Match]] = {}

    # Standard "Financial Covenants" headers
    matches = list(_FINANCIAL_COVENANT_SECTION_RE.finditer(text))
    if not matches:
        matches = list(_COVENANT_SECTION_RE.finditer(text))

    for m in matches:
        if _is_toc_entry(m, text):
            continue
        section_num = m.group(1)
        section_matches.setdefault(section_num, []).append(m)

    # V02-001: Non-standard "Financial Condition" headers
    for m in _NONSTANDARD_COVENANT_SECTION_RE.finditer(text):
        if _is_toc_entry(m, text):
            continue
        section_num = m.group(1)
        # Avoid duplicates with standard matches
        if section_num in section_matches:
            continue
        section_matches.setdefault(section_num, []).append(m)

    # V02-001: "Affirmative Covenants" / "Negative Covenants" headers
    # with content-based validation
    for m in _BROAD_COVENANT_SECTION_RE.finditer(text):
        if _is_toc_entry(m, text):
            continue
        section_num = m.group(1)
        # Avoid duplicates with standard matches
        if section_num in section_matches:
            continue
        # Content-based validation: peek at the section content to
        # confirm it contains ratio thresholds or covenant verbs before
        # treating it as a covenant section. This avoids false positives
        # from "Negative Covenants" sections that only contain operational
        # restrictions (no financial thresholds).
        peek_end = min(len(text), m.end() + 3000)
        peek_text = text[m.end():peek_end]
        has_ratio = bool(_RATIO_THRESHOLD_RE.search(peek_text))
        has_verb = bool(_COVENANT_VERB_RE.search(peek_text))
        if not (has_ratio or has_verb):
            continue
        section_matches.setdefault(section_num, []).append(m)

    # Step 22H: Content-based individual covenant section detection.
    # Many credit agreements list covenants as individual numbered
    # sections without a parent "Financial Covenants" header, e.g.:
    #   SECTION 6.11. Minimum Tangible Net Worth
    #   SECTION 6.12. Minimum Liquidity Ratio
    #   SECTION 6.13. Leverage Ratio
    # These are not found by the header-based patterns above.  We scan
    # for section headers that contain a known covenant name and extract
    # them as individual covenant sections.
    _INDIVIDUAL_COVENANT_SECTION_RE = re.compile(
        r"(?:SECTION|Section)\s+(\d+\.\d+)\s*\.?\s*"
        r"([A-Z][^\n]{3,80}?)\s*[\.\n]",
        re.IGNORECASE,
    )
    for m in _INDIVIDUAL_COVENANT_SECTION_RE.finditer(text):
        if _is_toc_entry(m, text):
            continue
        section_num = m.group(1)
        header_name = m.group(2).strip()
        # Check if the header name matches any known covenant name
        classification = _classify_covenant(header_name)
        if classification is None:
            continue
        # Content-based validation: confirm the section body contains
        # a ratio threshold, dollar amount, or covenant verb.
        peek_end = min(len(text), m.end() + 2000)
        peek_text = text[m.end():peek_end]
        has_ratio = bool(_RATIO_THRESHOLD_RE.search(peek_text))
        has_verb = bool(_COVENANT_VERB_RE.search(peek_text))
        has_dollar = bool(re.search(r"\$\s*[\d,]+", peek_text))
        has_percent = bool(re.search(r"\d+(?:\.\d+)?\s*%", peek_text))
        if not (has_ratio or has_verb or has_dollar or has_percent):
            continue
        # Avoid duplicates with standard matches
        if section_num in section_matches:
            continue
        section_matches.setdefault(section_num, []).append(m)

    # V02-002: For each section number, prefer the LAST match (the
    # actual section body) over earlier matches (TOC entries that
    # survived the dot-leader/page-number checks).
    for section_num, matches_list in section_matches.items():
        m = matches_list[-1]
        section_ref = f"Section {section_num}"
        start = m.start()
        if start in seen_starts:
            continue
        seen_starts.add(start)
        end = _find_section_end(text, m.end(), section_num)
        sections.append((section_ref, start, end))

    return sections


# ---------------------------------------------------------------------------
# Covenant clause extraction
# ---------------------------------------------------------------------------


# Covenant clause pattern: a named clause within a financial covenant
# section. Matches patterns like:
#   (a) Total Funded Debt to EBITDA Ratio.  The Loan Parties shall...
#   (a) Ratio of Debt to EBITDAX.  The Borrower will not...
#   (a) Texas Ratio.  ...permit the Texas Ratio to be greater than...
#   (b) Debt Service Coverage Ratio.  The Loan Parties shall not...
_CLAUSE_RE = re.compile(
    r"\(([a-z])\)\s*"
    r"([A-Z][^.]{3,80}?)\s*\.\s+"  # clause name (capitalized, ends with period)
    # clause body: until the NEXT clause header (parenthesized letter +
    # capitalized name + period) or end of text. The lookahead requires
    # the period so that "(a) Cash Flow of the Core Ameresco Companies"
    # (a sub-part of a ratio definition, no period after the name) is
    # NOT treated as a new clause header.
    r"(.*?)(?=\([a-z]\)\s+[A-Z][^.]{3,80}?\s*\.\s|\Z)",
    re.DOTALL,
)

# V02-003: Numbered-subsection clause pattern. Some credit agreements
# use numbered subsections (10.1, 10.2, 10.3) instead of lettered
# subsections ((a), (b), (c)). Matches patterns like:
#   10.1 Fixed Charge Coverage Ratio.  Beginning with...
#   10.2 Senior Funded Debt to EBITDA Ratio.  Beginning with...
#   10.3 Minimum Tangible Net Worth.  The sum of...
_NUMBERED_CLAUSE_RE = re.compile(
    r"(\d+\.\d+)\s+"
    r"([A-Z][^.]{3,80}?)\s*\.\s+"  # clause name (capitalized, ends with period)
    # clause body: until the NEXT numbered clause header or end of text
    r"(.*?)(?=\d+\.\d+\s+[A-Z][^.]{3,80}?\s*\.\s|\Z)",
    re.DOTALL,
)

# Step 22H: Three-level numbered subsection pattern with newlines.
# Some credit agreements use three-level numbering (7.19.1, 7.19.2)
# with the name on a separate line from the number, and the period
# on yet another line:
#   7.19.1
#   Liquidity
#   . Not suffer or permit...
#   7.19.2
#   Total Leverage Ratio
#   . Not suffer or permit...
_THREE_LEVEL_NUMBERED_CLAUSE_RE = re.compile(
    r"(\d+\.\d+\.\d+)\s*\n\s*"
    r"([A-Z][^\n]{3,80}?)\s*\n\s*\.\s*"
    # clause body: until the NEXT three-level clause header or end
    r"(.*?)(?=\d+\.\d+\.\d+\s*\n\s*[A-Z][^\n]{3,80}?\s*\n\s*\.\s|\Z)",
    re.DOTALL,
)


def _extract_clauses_from_section(
    text: str,
    start: int,
    end: int,
    section_ref: str,
) -> list[ExtractedClause]:
    """Extract individual covenant clauses from a section.

    Looks for (a), (b), (c) subsection patterns within the section.
    V02-003: Also looks for numbered subsections (10.1, 10.2, 10.3).
    If no subsections are found, treats the entire section as one clause
    if it contains covenant language.
    """
    section_text = text[start:end]
    clauses: list[ExtractedClause] = []

    for m in _CLAUSE_RE.finditer(section_text):
        clause_letter = m.group(1)
        clause_name = m.group(2).strip()
        clause_body = m.group(3).strip()
        clause_start = start + m.start()
        clause_end = start + m.end()

        # Clean up the clause body — remove excessive whitespace
        clause_body = re.sub(r"\s+", " ", clause_body).strip()

        clauses.append(ExtractedClause(
            section_ref=f"{section_ref}({clause_letter})",
            clause_name=clause_name,
            text=clause_body,
            start_offset=clause_start,
            end_offset=clause_end,
        ))

    # V02-003: If no lettered subsections were found, try numbered
    # subsections (10.1, 10.2, 10.3 format).
    if not clauses:
        # Extract the section number from the section_ref (e.g., "10"
        # from "Section 10", "5.03" from "Section 5.03"). Numbered
        # subsections (10.1, 10.2) are only valid for top-level sections
        # (no dot in the section number). For sections like "5.03" that
        # already have a dot, "5.04" is the NEXT section, not a subsection.
        section_num = section_ref.replace("Section ", "").strip()
        is_top_level = "." not in section_num
        for m in _NUMBERED_CLAUSE_RE.finditer(section_text):
            clause_num = m.group(1)
            # Skip if this is the section header itself
            if clause_num == section_num:
                continue
            # V02-003: Only treat numbered clauses as subsections if the
            # section is top-level (e.g., "10") and the clause number
            # starts with the section number + "." (e.g., "10.1").
            # For dotted section numbers (e.g., "5.03"), numbered matches
            # like "5.04" are the next section, not subsections.
            if not is_top_level:
                continue
            if not clause_num.startswith(section_num + "."):
                continue
            clause_name = m.group(2).strip()
            clause_body = m.group(3).strip()
            clause_start = start + m.start()
            clause_end = start + m.end()

            # Clean up the clause body — remove excessive whitespace
            clause_body = re.sub(r"\s+", " ", clause_body).strip()

            clauses.append(ExtractedClause(
                section_ref=f"{section_ref}({clause_num})",
                clause_name=clause_name,
                text=clause_body,
                start_offset=clause_start,
                end_offset=clause_end,
            ))

    # Step 22H: Try three-level numbered subsections (7.19.1, 7.19.2
    # format with newlines between number, name, and period).
    if not clauses:
        for m in _THREE_LEVEL_NUMBERED_CLAUSE_RE.finditer(section_text):
            clause_num = m.group(1)
            clause_name = m.group(2).strip()
            clause_body = m.group(3).strip()
            clause_start = start + m.start()
            clause_end = start + m.end()

            # Clean up the clause body — remove excessive whitespace
            clause_body = re.sub(r"\s+", " ", clause_body).strip()

            clauses.append(ExtractedClause(
                section_ref=f"{section_ref}({clause_num})",
                clause_name=clause_name,
                text=clause_body,
                start_offset=clause_start,
                end_offset=clause_end,
            ))

    # Step 22H: Try lenient lettered subsections — clauses where the
    # name and body are not separated by a period (e.g., HELD-005:
    # "(b)     Interest Coverage Ratio not less than 3.0 to 1.0").
    # This pattern matches (letter) followed by text containing a
    # covenant name, without requiring a period after the name.
    if not clauses:
        _LENIENT_CLAUSE_RE = re.compile(
            r"\(([a-z])\)\s+"
            r"(.*?)(?=\([a-z]\)\s+|\Z)",
            re.DOTALL,
        )
        for m in _LENIENT_CLAUSE_RE.finditer(section_text):
            clause_letter = m.group(1)
            clause_text = m.group(2).strip()
            clause_text = re.sub(r"\s+", " ", clause_text).strip()
            # Try to extract a covenant name from the text
            clause_name = _extract_covenant_name_from_text(clause_text)
            if clause_name is None:
                continue
            # Only accept if the clause name matches a known covenant
            classification = _classify_covenant(clause_name)
            if classification is None:
                continue
            clauses.append(ExtractedClause(
                section_ref=f"{section_ref}({clause_letter})",
                clause_name=clause_name,
                text=clause_text,
                start_offset=start + m.start(),
                end_offset=start + m.end(),
            ))

    # If no subsection clauses were found, try treating the section
    # header itself as a clause (some sections have the covenant directly
    # after the section title without (a)/(b) subsections).
    if not clauses:
        # V02-004: Expanded covenant-language pattern to match additional
        # verb forms observed in development chains:
        #   "shall have and maintain" (STUDY-029)
        #   "shall not be less than" / "shall not be greater than"
        #   "may not be less than" / "may not be greater than"
        #   "shall not permit" / "will not permit" (existing)
        #   "shall maintain" (existing)
        #   "may not exceed" / "shall not exceed"
        covenant_match = re.search(
            r"(shall\s+not\s+permit|will\s+not\s+permit"
            r"|shall\s+have\s+and\s+maintain|shall\s+maintain"
            r"|will\s+maintain"
            r"|shall\s+(?:not\s+)?be\s+(?:less|greater)\s+than"
            r"|may\s+not\s+(?:be\s+)?(?:less|greater)\s+than"
            r"|shall\s+(?:not\s+)?exceed|may\s+not\s+exceed"
            r"|permit\s+(?:the|its))",
            section_text,
            re.IGNORECASE,
        )
        if covenant_match:
            # Extract the sentence containing the covenant language.
            # V02-004: Skip periods that are part of decimal numbers
            # (e.g., "2.50 to 1.00") when finding sentence boundaries.
            # A period followed by a digit is a decimal point, not a
            # sentence boundary.
            sent_start = section_text.rfind(".", 0, covenant_match.start())
            # Walk backward past decimal-point periods
            while sent_start != -1 and sent_start + 1 < len(section_text) \
                    and section_text[sent_start + 1].isdigit():
                sent_start = section_text.rfind(".", 0, sent_start)
            sent_start = sent_start + 1 if sent_start != -1 else 0
            # Find sentence end, skipping decimal-point periods
            sent_end = section_text.find(".", covenant_match.end())
            while sent_end != -1 and sent_end + 1 < len(section_text) \
                    and section_text[sent_end + 1].isdigit():
                sent_end = section_text.find(".", sent_end + 1)
            sent_end = sent_end + 1 if sent_end != -1 else len(section_text)
            clause_text = section_text[sent_start:sent_end].strip()
            clause_text = re.sub(r"\s+", " ", clause_text).strip()

            if len(clause_text) > 20:
                # V02-003: Try to extract a covenant name from the
                # clause text for sections with no subsections. This
                # allows classification rules to match when the section
                # header itself doesn't contain a covenant name (e.g.,
                # "Section 5.03 Financial Covenants" with a single
                # "Leverage Ratio" covenant in the body text).
                clause_name = _extract_covenant_name_from_text(clause_text)
                if clause_name is None:
                    clause_name = section_ref

                clauses.append(ExtractedClause(
                    section_ref=section_ref,
                    clause_name=clause_name,
                    text=clause_text,
                    start_offset=start + sent_start,
                    end_offset=start + sent_end,
                ))

    return clauses


def _extract_covenant_name_from_text(text: str) -> str | None:
    """Try to identify a covenant name from clause body text.

    V02-003: For sections with no subsections (e.g., STUDY-029's
    "Section 5.03 Financial Covenants" with a single Leverage Ratio
    covenant), the fallback clause extraction uses the section_ref as
    the clause name, which won't match any classification rule. This
    function searches the clause text for known covenant name patterns
    so the classification rules can match.

    Returns the matched covenant name, or None if no known pattern is
    found.
    """
    for pattern, _key, _subject, _unit in _COVENANT_NAME_MAP:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return None


# ---------------------------------------------------------------------------
# Value extraction helpers
# ---------------------------------------------------------------------------


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _parse_date(text: str) -> str | None:
    """Parse a date like 'June 30, 2023' -> '2023-06-30'."""
    m = re.match(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
        text.strip(),
    )
    if not m:
        return None
    month_name = m.group(1).lower()
    if month_name not in _MONTHS:
        return None
    month = _MONTHS[month_name]
    day = int(m.group(2))
    year = int(m.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_step_down_schedule(text: str) -> dict | None:
    """Extract a step-down threshold schedule from covenant text.

    Looks for patterns like:
        (i) ending on June 30, 2023 to exceed 4.00 to 1.00,
        (ii) ending on September 30, 2023 to exceed 4.25 to 1.00,
        and (ii) for any quarter ending thereafter, to exceed 3.50 to 1.00.

    Returns a dict with:
        step_down_schedule: list of {period_end, threshold}
        steady_state_threshold: float or None
    Returns None if the pattern is not found.
    """
    step_pattern = re.compile(
        r"\([ivx]+\)\s+ending\s+on\s+"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}),?\s+"  # optional comma after date
        r"to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
        re.IGNORECASE,
    )
    steady_pattern = re.compile(
        r"for\s+any\s+quarter\s+ending\s+thereafter,?\s+to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
        re.IGNORECASE,
    )

    schedule = []
    for m in step_pattern.finditer(text):
        date_str = _parse_date(m.group(1))
        if date_str is None:
            return None
        threshold = float(m.group(2))
        schedule.append({"period_end": date_str, "threshold": threshold})

    steady_match = steady_pattern.search(text)
    steady_state = float(steady_match.group(1)) if steady_match else None

    if not schedule and steady_state is None:
        return None

    return {
        "step_down_schedule": schedule,
        "steady_state_threshold": steady_state,
    }


def _extract_threshold_ratio(text: str) -> tuple[float | None, str | None]:
    """Extract a ratio threshold like '4.50 to 1.00' or '3.5 to 1.0'.

    Returns (threshold_value, operator) where operator is "<=" or ">=".
    The operator is derived from the covenant language:
      "exceed" / "greater than" → "<=" (shall not exceed means <= threshold)
      "less than" / "be less than" → ">=" (shall not be less than means >= threshold)

    V02-001: Also handles colon-separated ratio format "4.00 : 1.0"
    (STUDY-031 pattern: "not more than 4.00 : 1.0").

    Step 22H: Also handles bare ratio thresholds without the "to 1.00"
    suffix (e.g., "of at least 1.20" in HELD-003).  This pattern is
    only used when the standard "X.XX to 1.00" pattern is not found,
    and requires explicit ratio language ("of at least", "of not less
    than", "to exceed", etc.) to avoid false positives.

    Returns (None, None) if no threshold is found.
    """
    # Ratio pattern: "X.XX to 1.00" or "X.X to 1.0" or "X.XX : 1.0"
    ratio_match = re.search(
        r"([\d.]+)\s*(?:to|:)\s*1\.0+",
        text,
        re.IGNORECASE,
    )
    if ratio_match:
        threshold = float(ratio_match.group(1))
    else:
        # Step 22H: Bare ratio threshold without "to 1.00" suffix.
        # Only match when preceded by ratio covenant language to avoid
        # false positives from non-covenant numbers.
        bare_match = re.search(
            r"(?:of\s+(?:at\s+least|not\s+less\s+than|no\s+less\s+than)\s+"
            r"|to\s+exceed\s+"
            r"|shall\s+not\s+exceed\s+"
            r"|shall\s+not\s+be\s+less\s+than\s+"
            r"|not\s+greater\s+than\s+)"
            r"([\d.]+)",
            text,
            re.IGNORECASE,
        )
        if not bare_match:
            return None, None
        threshold = float(bare_match.group(1))
        # Validate: ratio thresholds are typically between 0.01 and 100
        if threshold <= 0 or threshold > 100:
            return None, None

    # Determine operator from language
    text_lower = text.lower()
    # V02-004: "less than or equal to X" means the ratio must be <= X
    # (the borrower must keep the ratio at or below X). This is different
    # from "shall not be less than X" which means the ratio must be >= X.
    # Check "less than or equal" first (more specific) before "less than".
    if "less than or equal" in text_lower or "exceed" in text_lower or "greater than" in text_lower or "more than" in text_lower:
        operator = "<="
    elif "less than" in text_lower or "be less than" in text_lower or "at least" in text_lower:
        operator = ">="
    else:
        operator = "<="  # default for "shall not permit ... to exceed"

    return threshold, operator


def _extract_threshold_percent(text: str) -> tuple[float | None, str | None]:
    """Extract a percentage threshold like '7.00%' or '25.00%'.

    Returns (threshold_value, operator) where operator is "<=" or ">=".
    """
    pct_match = re.search(
        r"([\d.]+)\s*%",
        text,
    )
    if not pct_match:
        return None, None

    threshold = float(pct_match.group(1))

    text_lower = text.lower()
    if "greater than" in text_lower or "exceed" in text_lower:
        operator = "<="
    elif "less than" in text_lower or "be less than" in text_lower:
        operator = ">="
    else:
        operator = ">="  # default for "permit ... to be less than X%"

    return threshold, operator


def _extract_dollar_amount(text: str) -> int | None:
    """Extract a dollar amount like '$150,000,000' -> 150000000."""
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    return int(m.group(1).replace(",", "").split(".")[0])


def _extract_frequency(text: str) -> str:
    """Extract the measurement frequency from covenant text."""
    text_lower = text.lower()
    if "end of each fiscal quarter" in text_lower or \
       "last day of any fiscal quarter" in text_lower or \
       "last day of each fiscal quarter" in text_lower:
        return "quarterly"
    if "at any time" in text_lower or "as of such time" in text_lower:
        return "continuous"
    if "end of each fiscal year" in text_lower:
        return "annually"
    return "quarterly"  # default for financial covenants


# Party language patterns observed in real EDGAR credit agreements.
# Order matters: more specific phrases first. Each entry maps a regex
# (matched against the clause body) to a canonical party label. We match
# the subject of the covenant verb ("shall not permit", "shall maintain",
# "will not permit", etc.) so we capture the actual obligated party.
#
# Examples from real filings:
#   "The Loan Parties shall not permit the Core Leverage Ratio..."
#   "The Borrower will not permit its ratio of Debt..."
#   "The Credit Parties shall maintain..."
#   "Each Loan Party shall not permit..."
_PARTY_PATTERNS: list[tuple[str, str]] = [
    # "each Loan Party" / "each Credit Party" (singular, distributive)
    (r"\beach\s+(Loan\s+Part(?:y|ies)|Credit\s+Part(?:y|ies))\b", "each_loan_party"),
    # "the Loan Parties" / "the Credit Parties" (plural)
    (r"\bthe\s+(Loan\s+Parties|Credit\s+Parties)\b", "loan_parties"),
    # "the Borrower" (singular)
    (r"\bthe\s+Borrower\b", "borrower"),
    # "the Obligors" / "the Obligor"
    (r"\bthe\s+Obligor(?:s)?\b", "obligors"),
    # "No Loan Party will" / "No Loan Party shall" (negative subject)
    (r"\bNo\s+(Loan\s+Part(?:y|ies)|Credit\s+Part(?:y|ies))\b", "loan_parties"),
]


def _extract_party(text: str) -> list[str]:
    """Extract the obligated party from covenant clause text.

    Returns a list of canonical party labels. Returns ["borrower"] as a
    conservative default ONLY when no party language is found, since
    financial covenants in credit agreements are virtually always
    borrower/loan-party obligations and the default matches the v0.1
    behavior. When party language IS found, the actual phrase is used.

    Canonical labels:
      - "borrower"      — "the Borrower"
      - "loan_parties"  — "the Loan Parties" / "the Credit Parties"
      - "each_loan_party" — "each Loan Party" / "each Credit Party"
      - "obligors"      — "the Obligors" / "the Obligor"
    """
    for pattern, label in _PARTY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return [label]
    return ["borrower"]  # conservative default for financial covenants


# Exception patterns within covenant clauses. These capture carve-out
# language ("provided that ...", "except ...") that modifies the
# covenant's applicability. We extract a short summary string for each
# exception found, not the full text. The match extends to the next
# period (sentence boundary) or end of string.
_EXCEPTION_RE = re.compile(
    r"(provided\s+that[^.]{10,}?)(?:\.|$)"
    r"|(except\s*:[^.]{10,}?)(?:\.|$)",
    re.IGNORECASE,
)


def _extract_exceptions(text: str) -> list[str]:
    """Extract exception/carve-out clauses from covenant text.

    Looks for "provided that ..." and "except: ..." patterns that
    modify the covenant's applicability. Returns a list of short
    summary strings (truncated to 120 chars). Returns an empty list
    if no exceptions are found.

    Conservative: only extracts clearly delimited exception language.
    Does NOT guess at implicit exceptions.
    """
    exceptions: list[str] = []
    for m in _EXCEPTION_RE.finditer(text):
        # Pick whichever group matched
        raw = m.group(1) or m.group(2)
        if raw is None:
            continue
        cleaned = re.sub(r"\s+", " ", raw).strip()
        if len(cleaned) > 120:
            cleaned = cleaned[:117] + "..."
        exceptions.append(cleaned)
    return exceptions


# Maturity/deadline patterns. Financial covenants rarely have explicit
# deadlines (they are ongoing), but facility commitments have maturity
# dates. We extract the maturity date when present.
_MATURITY_RE = re.compile(
    r"(?:Maturity\s+Date|stated\s+maturity|final\s+maturity|shall\s+mature)"
    r"[^.]{0,40}?"
    r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)


def _extract_deadline(text: str) -> str | None:
    """Extract a maturity date or deadline from covenant/facility text.

    Looks for "Maturity Date ... <Month DD, YYYY>" patterns. Returns
    the date as YYYY-MM-DD, or None if not found.
    """
    m = _MATURITY_RE.search(text)
    if not m:
        return None
    return _parse_date(m.group(1))


# Effective date patterns. Covenants may state "effective as of <date>"
# or "commencing on <date>". We extract this as valid_from.
_EFFECTIVE_DATE_RE = re.compile(
    r"(?:effective\s+as\s+of|commencing\s+on|effective\s+on|dated\s+as\s+of)"
    r"\s+"
    r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)


def _extract_effective_date(text: str) -> str | None:
    """Extract an effective date from covenant text.

    Looks for "effective as of <Month DD, YYYY>" patterns. Returns
    the date as YYYY-MM-DD, or None if not found.
    """
    m = _EFFECTIVE_DATE_RE.search(text)
    if not m:
        return None
    return _parse_date(m.group(1))


# Interest rate patterns for facility commitments. Looks for rate
# language like "rate per annum of X.XX%" or "interest at a rate of
# X.XX% per annum".
#
# Each alternative is a bare prefix (no digit consumption). The capture
# group ([\d.]+)\s*% requires a trailing %, so ratio language like
# "rate of 4.50 to 1.00" (no %) does NOT false-positive. Earlier versions
# had "rate\s+of\s+(?:\d|[\d.]+\s*%)?" here, whose \d branch greedily
# consumed the first digit of the rate and left the capture group with
# only the decimal remainder (e.g. "rate of 5.50%" -> 0.50). Do not
# reintroduce a digit-consuming prefix.
_RATE_RE = re.compile(
    r"(?:rate\s+per\s+annum|interest\s+at\s+a\s+rate|bearing\s+interest"
    r"|rate\s+of|interest\s+rate\s+of)"
    r"[^.]{0,30}?"
    r"([\d.]+)\s*%",
    re.IGNORECASE,
)


def _extract_rate(text: str) -> float | None:
    """Extract an interest rate from facility/covenant text.

    Looks for "rate per annum of X.XX%" patterns. Returns the rate
    as a float (percentage points), or None if not found.

    Conservative: only extracts rates that appear in explicit rate
    language. Does NOT extract generic percentages (which are usually
    thresholds, not rates).
    """
    m = _RATE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Covenant classification — map clause names to canonical commitment keys
# ---------------------------------------------------------------------------


# Map covenant name patterns to canonical keys and commitment metadata.
# Each entry: (name_pattern, canonical_key, subject, unit)
_COVENANT_NAME_MAP: list[tuple[str, str, str, str]] = [
    # Leverage ratios
    (r"Total Funded Debt to EBITDA|Core Leverage Ratio|Total Debt to EBITDA",
     "financial_covenant.leverage_ratio", "leverage_ratio", "ratio"),
    (r"Debt to EBITDAX|Ratio of Debt to EBITDAX",
     "financial_covenant.leverage_ratio", "debt_to_ebitdax", "ratio"),
    (r"Total Leverage Ratio|Total Leverage",
     "financial_covenant.leverage_ratio", "total_leverage_ratio", "ratio"),
    # V02-001: Additional leverage ratio patterns from development chains
    (r"Senior Funded Debt to EBITDA",
     "financial_covenant.leverage_ratio", "senior_funded_debt_to_ebitda", "ratio"),
    (r"Consolidated Leverage Ratio",
     "financial_covenant.leverage_ratio", "consolidated_leverage_ratio", "ratio"),
    (r"Long Term Debt to Long Term Capitalization",
     "financial_covenant.leverage_ratio", "long_term_debt_to_capitalization", "ratio"),
    # Debt service / fixed charge coverage
    (r"Debt Service Coverage",
     "financial_covenant.debt_service_coverage", "debt_service_coverage_ratio", "ratio"),
    (r"Fixed Charge Coverage",
     "financial_covenant.fixed_charge_coverage", "fixed_charge_coverage_ratio", "ratio"),
    (r"Interest Coverage",
     "financial_covenant.interest_coverage", "interest_coverage_ratio", "ratio"),
    # V02-001: EBIT to Interest Ratio (STUDY-008 pattern) — a form of
    # interest coverage ratio.
    (r"EBIT to Interest Ratio",
     "financial_covenant.interest_coverage", "ebit_to_interest_ratio", "ratio"),
    # Current ratio
    (r"Current Ratio",
     "financial_covenant.current_ratio", "current_ratio", "ratio"),
    # Tangible net worth
    (r"Tangible Net Worth",
     "financial_covenant.tangible_net_worth", "tangible_net_worth", "ratio"),
    # Bank regulatory ratios
    (r"Tier 1 Leverage Ratio",
     "financial_covenant.tier_1_leverage_ratio", "tier_1_leverage_ratio", "percent"),
    (r"Risk.Based Capital Ratio",
     "financial_covenant.risk_based_capital_ratio", "risk_based_capital_ratio", "percent"),
    (r"Texas Ratio",
     "financial_covenant.texas_ratio", "texas_ratio", "percent"),
    (r"Return on Average Assets",
     "financial_covenant.return_on_average_assets", "return_on_average_assets_ratio", "percent"),
    # V02-004: Generic "Leverage Ratio" (STUDY-029 pattern) — must come
    # AFTER all specific leverage ratio patterns (including "Tier 1
    # Leverage Ratio") so they match first.
    (r"Leverage Ratio",
     "financial_covenant.leverage_ratio", "leverage_ratio", "ratio"),
    # Step 22E: Evidence-derived covenant name patterns from the
    # 50-chain corpus.  These are covenant section headers that appear
    # in S0/GT documents but were not in the original name map.
    (r"Minimum\s+Tangible\s+Net\s+Worth",
     "financial_covenant.tangible_net_worth", "tangible_net_worth", "ratio"),
    (r"Minimum\s+Shareholders.?\s+Equity",
     "financial_covenant.tangible_net_worth", "shareholders_equity", "ratio"),
    (r"Minimum\s+Stockholders.?\s+Equity",
     "financial_covenant.tangible_net_worth", "stockholders_equity", "ratio"),
    (r"Asset\s+Coverage\s+Ratio",
     "financial_covenant.debt_service_coverage", "asset_coverage_ratio", "ratio"),
    (r"Minimum\s+Working\s+Capital",
     "financial_covenant.current_ratio", "working_capital", "ratio"),
    (r"Minimum\s+Liquidity(?:\s+Ratio)?",
     "financial_covenant.interest_coverage", "liquidity_ratio", "ratio"),
    (r"Funded\s+Debt\s+to\s+EBITDA",
     "financial_covenant.leverage_ratio", "funded_debt_to_ebitda", "ratio"),
    (r"Net\s+Leverage\s+Ratio",
     "financial_covenant.leverage_ratio", "net_leverage_ratio", "ratio"),
    (r"First\s+Lien\s+Leverage\s+Ratio",
     "financial_covenant.leverage_ratio", "first_lien_leverage_ratio", "ratio"),
    (r"Secured\s+Leverage\s+Ratio",
     "financial_covenant.leverage_ratio", "secured_leverage_ratio", "ratio"),
]


def _classify_covenant(clause_name: str) -> tuple[str, str, str] | None:
    """Classify a covenant clause by name.

    Returns (canonical_key, subject, unit) or None if the clause name
    does not match any known covenant pattern.
    """
    for pattern, key, subject, unit in _COVENANT_NAME_MAP:
        if re.search(pattern, clause_name, re.IGNORECASE):
            return key, subject, unit
    return None


# ---------------------------------------------------------------------------
# Extraction rules — each rule takes an ExtractedClause and returns
# a CommitmentState (success) or None (rule did not match).
# ---------------------------------------------------------------------------


def _rule_leverage_ratio_with_step_down(clause: ExtractedClause) -> CommitmentState | None:
    """Extract leverage ratio covenants with step-down schedules.

    Trigger: clause name matches a leverage ratio pattern AND clause text
    contains a step-down schedule pattern.

    Produces a CommitmentState with:
      - threshold = steady_state_threshold
      - applicability = {step_down_schedule, steady_state_threshold}
    """
    classification = _classify_covenant(clause.clause_name)
    if classification is None:
        return None
    key, subject, unit = classification
    if "leverage_ratio" not in key:
        return None

    schedule = _extract_step_down_schedule(clause.text)
    if schedule is None:
        return None  # no step-down schedule → let other rules handle it

    steady = schedule.get("steady_state_threshold")
    if steady is None:
        # If there's no steady state, use the last step-down entry
        steps = schedule.get("step_down_schedule", [])
        if steps:
            steady = steps[-1]["threshold"]
        else:
            return None

    return CommitmentState(
        canonical_key=key,
        commitment_type="financial_covenant",
        status="ACTIVE",
        party=_extract_party(clause.text),
        action="maintain",
        subject=subject,
        operator="<=",
        threshold=steady,
        unit=unit,
        frequency=_extract_frequency(clause.text),
        applicability=schedule,
        exceptions=_extract_exceptions(clause.text),
        deadline=_extract_deadline(clause.text),
        valid_from=_extract_effective_date(clause.text),
    )


def _rule_simple_ratio_covenant(clause: ExtractedClause) -> CommitmentState | None:
    """Extract simple ratio covenants (single threshold, no step-down).

    Trigger: clause name matches a known ratio covenant pattern AND
    clause text contains a ratio threshold (X.XX to 1.00).

    Produces a CommitmentState with threshold and operator.
    """
    classification = _classify_covenant(clause.clause_name)
    if classification is None:
        return None
    key, subject, unit = classification
    if unit != "ratio":
        return None

    # Skip if this has a step-down schedule (handled by _rule_leverage_ratio_with_step_down)
    if _extract_step_down_schedule(clause.text) is not None:
        return None

    threshold, operator = _extract_threshold_ratio(clause.text)
    if threshold is None:
        return None

    return CommitmentState(
        canonical_key=key,
        commitment_type="financial_covenant",
        status="ACTIVE",
        party=_extract_party(clause.text),
        action="maintain",
        subject=subject,
        operator=operator,
        threshold=threshold,
        unit=unit,
        frequency=_extract_frequency(clause.text),
        exceptions=_extract_exceptions(clause.text),
        deadline=_extract_deadline(clause.text),
        valid_from=_extract_effective_date(clause.text),
    )


def _rule_percentage_covenant(clause: ExtractedClause) -> CommitmentState | None:
    """Extract percentage-based covenants (bank regulatory ratios).

    Trigger: clause name matches a known percentage covenant pattern AND
    clause text contains a percentage threshold.

    Produces a CommitmentState with threshold (as a float percentage)
    and unit="percent".
    """
    classification = _classify_covenant(clause.clause_name)
    if classification is None:
        return None
    key, subject, unit = classification
    if unit != "percent":
        return None

    threshold, operator = _extract_threshold_percent(clause.text)
    if threshold is None:
        return None

    return CommitmentState(
        canonical_key=key,
        commitment_type="financial_covenant",
        status="ACTIVE",
        party=_extract_party(clause.text),
        action="maintain",
        subject=subject,
        operator=operator,
        threshold=threshold,
        unit="percent",
        frequency=_extract_frequency(clause.text),
        exceptions=_extract_exceptions(clause.text),
        deadline=_extract_deadline(clause.text),
        valid_from=_extract_effective_date(clause.text),
    )


# Ordered list of extraction rules. Each rule takes an ExtractedClause
# and returns a CommitmentState if it matches, or None if it doesn't.
# The first matching rule wins.
def _rule_dollar_amount_covenant(clause: ExtractedClause) -> CommitmentState | None:
    """Extract dollar-amount covenants (e.g., Tangible Net Worth in dollars).

    Trigger: clause name matches a known covenant pattern with unit
    "ratio" (Tangible Net Worth can be expressed as either a ratio or
    a dollar amount) AND clause text contains a dollar amount.

    Produces a CommitmentState with threshold (as a float dollar
    amount) and unit="usd".
    """
    classification = _classify_covenant(clause.clause_name)
    if classification is None:
        return None
    key, subject, unit = classification

    # Only apply to covenants that can be expressed as dollar amounts
    # (tangible_net_worth is the most common one).  Ratio covenants
    # (leverage_ratio, current_ratio, etc.) should NOT match this rule
    # — their thresholds are ratios, not dollar amounts.
    if key not in ("financial_covenant.tangible_net_worth",):
        return None

    # Skip if this has a step-down schedule or ratio threshold
    if _extract_step_down_schedule(clause.text) is not None:
        return None
    if _extract_threshold_ratio(clause.text)[0] is not None:
        return None

    amount = _extract_dollar_amount(clause.text)
    if amount is None or amount <= 0:
        return None

    # Determine operator from text
    text_lower = clause.text.lower()
    if "not less than" in text_lower or "at least" in text_lower:
        operator = ">="
    elif "not greater than" in text_lower or "not exceed" in text_lower:
        operator = "<="
    else:
        operator = ">="  # default for "maintain" covenants

    return CommitmentState(
        canonical_key=key,
        commitment_type="financial_covenant",
        status="ACTIVE",
        party=_extract_party(clause.text),
        action="maintain",
        subject=subject,
        operator=operator,
        threshold=float(amount),
        unit="usd",
        frequency=_extract_frequency(clause.text),
        exceptions=_extract_exceptions(clause.text),
        deadline=_extract_deadline(clause.text),
        valid_from=_extract_effective_date(clause.text),
    )


# Ordered list of extraction rules. Each rule takes an ExtractedClause
# and returns a CommitmentState if it matches, or None if it doesn't.
# The first matching rule wins.
_EXTRACTION_RULES: list = [
    _rule_leverage_ratio_with_step_down,
    _rule_simple_ratio_covenant,
    _rule_percentage_covenant,
    _rule_dollar_amount_covenant,
]


# ---------------------------------------------------------------------------
# Facility commitment extraction
# ---------------------------------------------------------------------------


# Facility commitment patterns: "Term Loan" / "Revolving Facility" / etc.
# with a dollar amount. The million/billion suffix is matched separately
# (NOT consumed by the capture regex) so the multiplier can be applied
# correctly. See _extract_facility_commitments for the suffix handling.
_FACILITY_PATTERNS: list[tuple[str, str]] = [
    (r"(?:Term\s+Loan|Term\s+Commitment).*?\$([\d,]+(?:\.\d+)?)",
     "facility.term_loan"),
    (r"(?:Revolving\s+(?:Loan|Facility|Credit|Commitment)|Revolving\s+Facility).*?\$([\d,]+(?:\.\d+)?)",
     "facility.revolving_facility"),
    (r"(?:Delayed\s+Draw\s+Term).*?\$([\d,]+(?:\.\d+)?)",
     "facility.delayed_draw_term_loan"),
]


def _extract_facility_commitments(
    text: str,
    source_label: str,
) -> list[tuple[CommitmentState, dict[str, Any]]]:
    """Extract facility commitments (loan amounts) from the document.

    Looks for patterns like "Term Loan in the amount of $150,000,000"
    or "Revolving Facility of $50,000,000".

    Returns a list of (CommitmentState, provenance) tuples.
    """
    results: list[tuple[CommitmentState, dict[str, Any]]] = []
    seen_keys: set[str] = set()

    for pattern, key in _FACILITY_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            amount_str = m.group(1).replace(",", "")
            # Parse as float so decimal abbreviated amounts (e.g. "$1.5
            # billion", "$1.5 million") are scaled correctly. The threshold
            # field is Optional[float], so a float value is accepted
            # directly. Whole-dollar amounts parse to x.0 with no loss.
            amount = float(amount_str)

            # Check for "million" / "billion" multiplier in the text
            # immediately following the matched dollar amount. The suffix
            # is NOT consumed by the capture regex, so m.end() points right
            # after the digits.
            suffix = text[m.end():m.end() + 12].lower()
            if "billion" in suffix:
                amount *= 1_000_000_000
            elif "million" in suffix:
                amount *= 1_000_000

            if key in seen_keys:
                continue  # only take the first occurrence per facility type
            seen_keys.add(key)

            # Extract a context window around the match for field
            # extraction (deadline, rate, effective date). We use a
            # 300-char window after the match since maturity/rate
            # language typically follows the facility amount.
            context_start = max(0, m.start() - 100)
            context_end = min(len(text), m.end() + 300)
            context = text[context_start:context_end]

            commitment = CommitmentState(
                canonical_key=key,
                commitment_type="facility_commitment",
                status="ACTIVE",
                party=["lender"],
                action="commit",
                subject=key.split(".")[-1],
                threshold=amount,
                unit="usd",
                deadline=_extract_deadline(context),
                rate=_extract_rate(context),
                valid_from=_extract_effective_date(context),
            )

            provenance = {
                "canonical_key": key,
                "rule": "facility_commitment",
                "source_span": text[max(0, m.start() - 50):m.end() + 50].strip(),
                "confidence": 0.80,
                "source_label": source_label,
            }
            results.append((commitment, provenance))

    return results


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------


def extract_commitments(
    text: str,
    source_label: str = "",
    source_path: str = "",
) -> ExtractionResult:
    """Extract structured commitments from a credit agreement document.

    This is the shared extraction engine used by both the S0 extractor
    (origin state) and the GT extractor (ground truth state).

    Args:
        text: the full text of the credit agreement document.
        source_label: label for the source (e.g., "S0" or "CMP").
        source_path: path to the source file (for provenance).

    Returns:
        ExtractionResult with:
          - commitments: successfully extracted CommitmentState objects
          - validation_queue: clauses that could not be extracted
          - provenance: per-commitment provenance records
    """
    result = ExtractionResult(
        source_label=source_label,
        source_path=source_path,
        text_length=len(text),
    )

    if not text or len(text) < 100:
        return result

    # 1. Find financial covenant sections
    sections = _find_covenant_sections(text)

    # 2. Extract clauses from each section
    all_clauses: list[ExtractedClause] = []
    for section_ref, start, end in sections:
        clauses = _extract_clauses_from_section(text, start, end, section_ref)
        all_clauses.extend(clauses)

    # 3. Apply extraction rules to each clause
    for clause in all_clauses:
        extracted = False
        for rule in _EXTRACTION_RULES:
            commitment = rule(clause)
            if commitment is not None:
                # Don't overwrite if already extracted (first match wins)
                if commitment.canonical_key not in result.commitments:
                    result.commitments[commitment.canonical_key] = commitment
                    result.provenance.append({
                        "canonical_key": commitment.canonical_key,
                        "rule": rule.__name__,
                        "section_ref": clause.section_ref,
                        "clause_name": clause.clause_name,
                        "source_span": clause.text[:200],
                        "confidence": 0.90,
                        "source_label": source_label,
                    })
                extracted = True
                break

        if not extracted:
            # Check if the clause name matches a known covenant pattern
            # but extraction failed → validation queue with reason
            classification = _classify_covenant(clause.clause_name)
            if classification is not None:
                reason = "Covenant recognized but threshold extraction failed"
            else:
                reason = "Unknown covenant type — no matching classification rule"

            result.validation_queue.append(ValidationItem(
                section_ref=clause.section_ref,
                clause_name=clause.clause_name,
                text=clause.text[:500],
                reason=reason,
            ))

    # 4. Extract facility commitments (loan amounts)
    facility_results = _extract_facility_commitments(text, source_label)
    for commitment, provenance in facility_results:
        if commitment.canonical_key not in result.commitments:
            result.commitments[commitment.canonical_key] = commitment
            result.provenance.append(provenance)

    return result


def extract_commitments_from_file(
    path: str | Path,
    source_label: str = "",
) -> ExtractionResult:
    """Extract commitments from a text file.

    Args:
        path: path to the text file.
        source_label: label for the source (e.g., "S0" or "CMP").

    Returns:
        ExtractionResult.
    """
    p = Path(path)
    if not p.exists():
        return ExtractionResult(
            source_label=source_label,
            source_path=str(path),
            text_length=0,
        )
    text = p.read_text(encoding="utf-8", errors="ignore")
    return extract_commitments(text, source_label=source_label, source_path=str(path))
