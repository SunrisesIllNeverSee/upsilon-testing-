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

from models import CommitmentState


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


def _find_covenant_sections(text: str) -> list[tuple[str, int, int]]:
    """Find financial covenant sections in the document.

    Returns a list of (section_ref, start_offset, end_offset) tuples.
    The end_offset is the start of the next section or article, or the
    end of the document.

    We skip table-of-contents entries (which have page numbers or
    dot-leader patterns following the section title).
    """
    sections: list[tuple[str, int, int]] = []
    matches = list(_FINANCIAL_COVENANT_SECTION_RE.finditer(text))
    if not matches:
        matches = list(_COVENANT_SECTION_RE.finditer(text))

    for m in matches:
        # Skip TOC entries: they typically have dot leaders (3+ dots)
        # within 20 chars after the match.
        after = text[m.end():m.end() + 20]
        if re.match(r"\s*\.{3,}", after):
            continue
        # Also skip if the match is in the first 10% of the document
        # AND followed by dot leaders within 50 chars (common TOC pattern).
        if m.start() < len(text) * 0.1:
            after_more = text[m.end():m.end() + 50]
            if re.search(r"\.{3,}", after_more):
                continue

        section_num = m.group(1)
        section_ref = f"Section {section_num}"
        start = m.start()

        # Find the end: next section/article header after this one.
        # Match both "Section 7.11" and bare "7.11" patterns, as well
        # as "ARTICLE IX" patterns. The key is to find a new top-level
        # section header that starts a different section.
        remaining = text[m.end():]
        # Pattern: optional "Section"/"SECTION"/"ARTICLE" prefix,
        # followed by a number (e.g., "7.11") or roman numeral (e.g., "IX"),
        # followed by a space and a capitalized word (the section title).
        # We require the section number to differ from the current one.
        current_num = section_num
        next_section = None
        for sm in re.finditer(
            r"(?:(?:Section|SECTION|ARTICLE)\s+)?"
            r"(\d+(?:\.\d+)?|[IVX]+)\s+"
            r"([A-Z][a-zA-Z]+\s+[A-Z])",
            remaining,
        ):
            candidate_num = sm.group(1)
            # Skip if it's the same section number (could be a
            # cross-reference within the section).
            if candidate_num == current_num:
                continue
            # Skip single-digit numbers that are not prefixed with
            # Section/SECTION/ARTICLE — these are almost certainly part
            # of clause text (e.g., "Tier 1 Leverage Ratio") rather than
            # section headers.
            if not candidate_num.startswith(tuple("0123456789")) or \
               "." in candidate_num:
                # Roman numeral or dotted number (e.g., "7.11") — more
                # likely a real section reference.
                pass
            elif len(candidate_num) == 1 and \
                 not re.match(r"(?:Section|SECTION|ARTICLE)\s+",
                              remaining[sm.start():sm.start()+20],
                              re.IGNORECASE):
                # Single digit without Section/ARTICLE prefix — skip
                # (likely part of clause text like "Tier 1 Leverage")
                continue
            # Check that this is at a section-header position: either
            # prefixed with Section/SECTION/ARTICLE, or at the start of
            # a line / after a period + whitespace.
            has_prefix = re.match(
                r"(?:Section|SECTION|ARTICLE)\s+",
                remaining[sm.start():sm.start()+20],
                re.IGNORECASE,
            )
            abs_pos = m.end() + sm.start()
            before = text[max(0, abs_pos - 5):abs_pos]
            at_line_start = re.search(r"(?:\n\s*|\.\s+)$", before)
            if has_prefix or at_line_start:
                next_section = sm
                break
        if next_section:
            end = m.end() + next_section.start()
        else:
            end = len(text)

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


def _extract_clauses_from_section(
    text: str,
    start: int,
    end: int,
    section_ref: str,
) -> list[ExtractedClause]:
    """Extract individual covenant clauses from a section.

    Looks for (a), (b), (c) subsection patterns within the section.
    If no subsections are found, treats the entire section as one clause.
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

    # If no subsection clauses were found, try treating the section
    # header itself as a clause (some sections have the covenant directly
    # after the section title without (a)/(b) subsections).
    if not clauses:
        # Look for "shall not permit" or "will not permit" or "permit"
        # within the section
        covenant_match = re.search(
            r"(shall\s+not\s+permit|will\s+not\s+permit|shall\s+maintain|permit\s+(?:the|its))",
            section_text,
            re.IGNORECASE,
        )
        if covenant_match:
            # Extract the sentence containing the covenant language
            sent_start = section_text.rfind(".", 0, covenant_match.start())
            sent_start = sent_start + 1 if sent_start != -1 else 0
            sent_end = section_text.find(".", covenant_match.end())
            sent_end = sent_end + 1 if sent_end != -1 else len(section_text)
            clause_text = section_text[sent_start:sent_end].strip()
            clause_text = re.sub(r"\s+", " ", clause_text).strip()

            if len(clause_text) > 20:
                clauses.append(ExtractedClause(
                    section_ref=section_ref,
                    clause_name=section_ref,
                    text=clause_text,
                    start_offset=start + sent_start,
                    end_offset=start + sent_end,
                ))

    return clauses


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

    Returns (None, None) if no threshold is found.
    """
    # Ratio pattern: "X.XX to 1.00" or "X.X to 1.0"
    ratio_match = re.search(
        r"([\d.]+)\s+to\s+1\.0+",
        text,
        re.IGNORECASE,
    )
    if not ratio_match:
        return None, None

    threshold = float(ratio_match.group(1))

    # Determine operator from language
    text_lower = text.lower()
    if "exceed" in text_lower or "greater than" in text_lower:
        operator = "<="
    elif "less than" in text_lower or "be less than" in text_lower:
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
    # Debt service / fixed charge coverage
    (r"Debt Service Coverage",
     "financial_covenant.debt_service_coverage", "debt_service_coverage_ratio", "ratio"),
    (r"Fixed Charge Coverage",
     "financial_covenant.fixed_charge_coverage", "fixed_charge_coverage_ratio", "ratio"),
    (r"Interest Coverage",
     "financial_covenant.interest_coverage", "interest_coverage_ratio", "ratio"),
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
        party=["borrower"],
        action="maintain",
        subject=subject,
        operator="<=",
        threshold=steady,
        unit=unit,
        frequency=_extract_frequency(clause.text),
        applicability=schedule,
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
        party=["borrower"],
        action="maintain",
        subject=subject,
        operator=operator,
        threshold=threshold,
        unit=unit,
        frequency=_extract_frequency(clause.text),
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
        party=["borrower"],
        action="maintain",
        subject=subject,
        operator=operator,
        threshold=threshold,
        unit="percent",
        frequency=_extract_frequency(clause.text),
    )


# Ordered list of extraction rules. Each rule takes an ExtractedClause
# and returns a CommitmentState if it matches, or None if it doesn't.
# The first matching rule wins.
_EXTRACTION_RULES: list = [
    _rule_leverage_ratio_with_step_down,
    _rule_simple_ratio_covenant,
    _rule_percentage_covenant,
]


# ---------------------------------------------------------------------------
# Facility commitment extraction
# ---------------------------------------------------------------------------


# Facility commitment patterns: "Term Loan" / "Revolving Facility" / etc.
# with a dollar amount.
_FACILITY_PATTERNS: list[tuple[str, str]] = [
    (r"(?:Term\s+Loan|Term\s+Commitment).*?\$([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
     "facility.term_loan"),
    (r"(?:Revolving\s+(?:Loan|Facility|Credit|Commitment)|Revolving\s+Facility).*?\$([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
     "facility.revolving_facility"),
    (r"(?:Delayed\s+Draw\s+Term).*?\$([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
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
            amount = int(amount_str.split(".")[0])

            # Check for "million" / "billion" multiplier
            suffix = text[m.end():m.end() + 10].lower()
            if "billion" in suffix:
                amount *= 1_000_000_000
            elif "million" in suffix:
                amount *= 1_000_000

            if key in seen_keys:
                continue  # only take the first occurrence per facility type
            seen_keys.add(key)

            commitment = CommitmentState(
                canonical_key=key,
                commitment_type="facility_commitment",
                status="ACTIVE",
                party=["lender"],
                action="commit",
                subject=key.split(".")[-1],
                threshold=amount,
                unit="usd",
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
