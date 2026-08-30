"""Semantic mapping layer: parsed legal instructions → structured commitment mutations.

STATUS: v0.1 — IMPLEMENTED for high-confidence patterns only.

This module converts parser-extracted section-level instructions (from
parse_v04) into StructuredMutation objects that the executor can apply
to commitment state.  The mapper uses deterministic rules validated
against real EDGAR parser output.

v0.1 scope:
  - Numeric threshold replacement (leverage ratio step-down schedules)
  - Commitment amount replacement (facility additions)
  - Date / maturity replacement (explicit maturity date amendments)
  - Rate / percentage replacement (explicit applicable-rate changes)
  - Explicit exception add/remove (carve-out additions/removals)
  - Explicit party change (guarantor/borrower additions/removals)
  - Everything else → UNRESOLVED with a specific ambiguity reason

Critical rule: a bad automatic mapping is worse than an unresolved one.
Uncertain mappings are routed to UNRESOLVED with no authoritative
promotion, never to a best-guess mutation.

Architecture:

    parsed legal instruction (AmendmentInstruction from parse_v04)
            ↓
    semantic mapper (deterministic rules)
            ↓
    StructuredMutation (mapped)  |  StructuredMutation (UNRESOLVED)
            ↓                              ↓
    executor applies              no authoritative promotion
    to commitment state

The StructuredMutation is the mapper's strict output schema.  It is
converted to AmendmentInstruction for the executor via
to_amendment_instruction().
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from models import (
    AmendmentInstruction,
    DomainEffect,
    InstructionProvenance,
    InstructionType,
)


# ---------------------------------------------------------------------------
# Ambiguity reasons
# ---------------------------------------------------------------------------


class AmbiguityReason(str, Enum):
    """Why a mapping was unresolved.

    A StructuredMutation with ambiguity_reason != None is UNRESOLVED and
    must not be promoted to authoritative state.  The reason guides
    manual review and future rule development.
    """
    UNKNOWN_COMMITMENT = "unknown_commitment"
    """The section reference does not map to any known commitment."""

    UNKNOWN_FIELD = "unknown_field"
    """The commitment is known but the specific field cannot be identified."""

    AMBIGUOUS_TARGET = "ambiguous_target"
    """Multiple commitments could be the target; cannot disambiguate."""

    AMBIGUOUS_VALUE = "ambiguous_value"
    """The target is clear but the new value cannot be extracted with confidence."""

    CROSS_REFERENCE_REQUIRED = "cross_reference_required"
    """The instruction references another section/exhibit that must be resolved first."""

    DEFINED_TERM_REQUIRED = "defined_term_required"
    """The instruction uses a defined term whose definition must be resolved first."""


# ---------------------------------------------------------------------------
# StructuredMutation — the mapper's strict output schema
# ---------------------------------------------------------------------------


@dataclass
class StructuredMutation:
    """A structured commitment-level mutation produced by the semantic mapper.

    A mutation is either MAPPED (ambiguity_reason is None, commitment_id
    is set) or UNRESOLVED (ambiguity_reason is set, commitment_id may be
    None).  UNRESOLVED mutations are never promoted to authoritative state.

    Fields:
        commitment_id: canonical commitment key (e.g.,
            "financial_covenant.leverage_ratio").  None if UNRESOLVED
            and the commitment could not be identified.
        field: the CommitmentState field to modify (e.g., "threshold",
            "applicability", "amount").  None if UNRESOLVED.
        operation: the InstructionType for this mutation
            (REPLACE_VALUE, ADD, etc.).
        old_value: the previous value, if known from the amendment text.
            None if the old value is not stated in the text (the executor
            will skip the old-value consistency check).
        new_value: the new value extracted from the amendment text.
            For ADD operations, this may be a dict payload for a new
            CommitmentState.  None if UNRESOLVED and no value could be
            extracted.
        unit: the unit of the value (e.g., "ratio", "usd", "percent").
            None if not applicable or UNRESOLVED.
        effective_at: effective date of the mutation.
        source_span: the source text span that was mapped.  This is the
            text the mapper operated on, taken from the parser's
            source_text field.
        provenance: InstructionProvenance.SEMANTIC_MAPPER for mapped
            mutations, InstructionProvenance.MANUAL for UNRESOLVED.
        confidence: mapper confidence in the mapping (0.0–1.0).
        ambiguity_reason: None if mapped, set to an AmbiguityReason if
            UNRESOLVED.
        citation_document: source document name.
        citation_section: source section reference.
    """

    commitment_id: str | None = None
    field: str | None = None
    operation: InstructionType = InstructionType.UNRESOLVED
    old_value: Any = None
    new_value: Any = None
    unit: str | None = None
    effective_at: datetime | None = None
    source_span: str = ""
    provenance: InstructionProvenance = InstructionProvenance.MANUAL
    confidence: float = 0.0
    ambiguity_reason: AmbiguityReason | None = None
    citation_document: str | None = None
    citation_section: str | None = None

    @property
    def is_resolved(self) -> bool:
        """True if this mutation was successfully mapped (not UNRESOLVED)."""
        return self.ambiguity_reason is None and self.commitment_id is not None

    def to_amendment_instruction(self, order: int = 0) -> AmendmentInstruction:
        """Convert to AmendmentInstruction for the executor.

        Args:
            order: instruction order within the amendment (defaults to 0).
        """
        domain_effect: DomainEffect | None = None
        if self.is_resolved:
            if self.field in ("threshold", "applicability"):
                domain_effect = DomainEffect.COVENANT_THRESHOLD_CHANGE
            elif self.field == "amount":
                domain_effect = DomainEffect.COMMITMENT_AMOUNT_CHANGE
            elif self.field == "deadline":
                domain_effect = DomainEffect.DEADLINE_CHANGE
            elif self.field == "rate":
                domain_effect = DomainEffect.RATE_CHANGE
            elif self.field == "exceptions":
                if self.operation == InstructionType.ADD:
                    domain_effect = DomainEffect.EXCEPTION_EXPANSION
                elif self.operation == InstructionType.DELETE:
                    domain_effect = DomainEffect.EXCEPTION_REMOVAL
            elif self.field == "party":
                domain_effect = DomainEffect.PARTY_CHANGE

        return AmendmentInstruction(
            order=order,
            instruction_type=self.operation,
            target_key=self.commitment_id,
            target_section_ref=self.citation_section,
            field=self.field,
            old_value=self.old_value,
            new_value=self.new_value,
            effective_start=self.effective_at,
            source_text=self.source_span,
            confidence=self.confidence,
            domain_effect=domain_effect,
            provenance=self.provenance,
            citation_document=self.citation_document,
            citation_section=self.citation_section,
        )


# ---------------------------------------------------------------------------
# Mapping result
# ---------------------------------------------------------------------------


@dataclass
class MappingResult:
    """Result of mapping a single parser instruction.

    Fields:
        mutations: successfully mapped StructuredMutation objects
            (provenance = SEMANTIC_MAPPER, ambiguity_reason = None).
        unresolved: StructuredMutation objects that could not be mapped
            (provenance = MANUAL, ambiguity_reason set).
        rules_matched: list of rule descriptions that fired.
    """
    mutations: list[StructuredMutation] = field(default_factory=list)
    unresolved: list[StructuredMutation] = field(default_factory=list)
    rules_matched: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Value extraction helpers
# ---------------------------------------------------------------------------


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _parse_date(text: str) -> str | None:
    """Parse a date like 'June 30, 2023' → '2023-06-30'.

    Returns None if the text does not match the expected format.
    """
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


def _extract_step_down_schedule(source_text: str) -> dict | None:
    """Extract a leverage ratio step-down schedule from amendment text.

    Looks for patterns like:
        (i) ending on June 30, 2023 to exceed 4.00 to 1.00,
        (ii) ending on September 30, 2023 to exceed 4.25 to 1.00,
        and (ii) for any quarter ending thereafter, to exceed 3.50 to 1.00.

    Returns a dict with:
        step_down_schedule: list of {period_end, threshold}
        steady_state_threshold: float
    Returns None if the pattern is not found.
    """
    # Step-down entries: "(i) ending on <month> <day>, <year> to exceed <num> to 1.00"
    step_pattern = re.compile(
        r"\([ivx]+\)\s+ending\s+on\s+"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        r"\s+to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
        re.IGNORECASE,
    )
    # Steady state: "for any quarter ending thereafter, to exceed <num> to 1.00"
    steady_pattern = re.compile(
        r"for\s+any\s+quarter\s+ending\s+thereafter,?\s+to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
        re.IGNORECASE,
    )

    schedule = []
    for m in step_pattern.finditer(source_text):
        date_str = _parse_date(m.group(1))
        if date_str is None:
            return None  # date parse failure → cannot confidently map
        threshold = float(m.group(2))
        schedule.append({"period_end": date_str, "threshold": threshold})

    steady_match = steady_pattern.search(source_text)
    steady_state = float(steady_match.group(1)) if steady_match else None

    if not schedule and steady_state is None:
        return None  # neither pattern matched

    return {
        "step_down_schedule": schedule,
        "steady_state_threshold": steady_state,
    }


def _extract_dollar_amount(source_text: str) -> int | None:
    """Extract a dollar amount like '$150,000,000' → 150000000.

    Returns None if no dollar amount is found.
    """
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", source_text)
    if not m:
        return None
    return int(m.group(1).replace(",", "").split(".")[0])


def _extract_maturity_date(source_text: str) -> str | None:
    """Extract the NEW maturity date from amendment text.

    Amendment text often contains both the old and new date, e.g.:
        "The Maturity Date of June 30, 2024 is hereby extended to
         December 31, 2025"

    The old date typically follows "of" / "from" / "currently", while
    the new date follows amendment verbs like "amended to mean",
    "extended to", "shall be", "means", or a bare "to" introducing
    the replacement.

    Strategy (in priority order):
      1. Match a date that follows amendment language after the
         "Maturity Date" keyword.
      2. If exactly one date appears near "Maturity Date" (within 80
         chars), return it (the simple case where only the new value
         is stated).
      3. If multiple dates appear near "Maturity Date" but none
         follows amendment language, return None (ambiguous).

    Returns the date as 'YYYY-MM-DD' or None if no unambiguous new
    maturity date can be identified.
    """
    # Must mention "Maturity Date" at all.
    if not re.search(r"Maturity\s+Date", source_text, re.IGNORECASE):
        return None

    # Pattern 1: "Maturity Date" followed by amendment language and
    # then a date.  The amendment language ("amended to mean",
    # "extended to", "shall be", "means", "to") signals that the
    # following date is the NEW value.
    amend_pattern = re.compile(
        r"Maturity\s+Date"
        r"[^.]{0,80}?"
        r"(?:amended\s+to\s+mean|extended\s+to|shall\s+be|"
        r"means|to)\s+"
        r"\"?([A-Za-z]+\s+\d{1,2},?\s+\d{4})\"?",
        re.IGNORECASE,
    )
    m = amend_pattern.search(source_text)
    if m:
        return _parse_date(m.group(1))

    # Pattern 2: find all dates in the sentence(s) containing
    # "Maturity Date".  We extract the surrounding sentence and count
    # dates within it.  If exactly one date appears, it must be the
    # new value (the simple case where only the new value is stated).
    # If multiple dates appear without amendment language, the value
    # is ambiguous.
    date_re = re.compile(r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
    sentences = re.split(r"(?<=[.])\s+", source_text)
    near_dates: list[str] = []
    for s in sentences:
        if re.search(r"Maturity\s+Date", s, re.IGNORECASE):
            near_dates.extend(m.group(1) for m in date_re.finditer(s))

    if len(near_dates) == 1:
        # Only one date near the keyword — it must be the new value.
        return _parse_date(near_dates[0])

    # Zero or multiple dates near the keyword without amendment
    # language → ambiguous.
    return None


def _extract_percentage(source_text: str) -> float | None:
    """Extract the NEW percentage value from amendment text.

    Amendment text often contains both the old and new rate, e.g.:
        "The Applicable Rate of 3.00% is hereby amended to 2.50%"

    The old value typically follows "of" / "from" / "currently", while
    the new value follows amendment verbs like "amended to", "to mean",
    "set at", "shall be", or a bare "to" introducing the replacement.

    Strategy (in priority order):
      1. Match a percentage that follows amendment language
         ("amended to", "to mean", "set at", "shall be", "to").
      2. If exactly one percentage appears in the text, return it
         (the simple case where only the new value is stated).
      3. If multiple percentages appear but none follows amendment
         language, return None (ambiguous — cannot determine which is
         the new value with high confidence).

    Returns the new percentage as a float, or None if no unambiguous
    new value can be identified.
    """
    # Pattern 1: amendment language followed by a percentage.
    # Captures the percentage that follows phrases like "amended to",
    # "to mean", "set at", or "shall be".  A bare "to" is intentionally
    # excluded — it is too common in legal text (e.g., "adjustments to
    # 1.50% for certain loans") and would produce false positives.
    amend_pattern = re.compile(
        r"(?:amended\s+to|to\s+mean|set\s+at|shall\s+be)"
        r"\s*"
        r"(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )
    m = amend_pattern.search(source_text)
    if m:
        return float(m.group(1))

    # Pattern 2: count all percentages in the text.
    all_pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", source_text)
    if len(all_pcts) == 1:
        # Only one percentage — it must be the new value.
        return float(all_pcts[0])

    # Zero or multiple percentages without amendment language → ambiguous.
    return None


# ---------------------------------------------------------------------------
# Mapping rules
# ---------------------------------------------------------------------------


def _rule_leverage_ratio_step_down(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map leverage ratio step-down schedule changes (e.g., Section 7.10).

    Trigger: target_section_ref matches "Section 7.10" AND source_text
    contains "Total Funded Debt to EBITDA" or "Core Leverage Ratio".

    Extracts the step-down schedule from the source_text and produces a
    REPLACE_VALUE mutation on financial_covenant.leverage_ratio.applicability.

    Returns None if the rule does not match (so the caller can try other
    rules or fall back to UNRESOLVED).
    """
    section_ref = parser_instruction.target_section_ref or ""
    source_text = parser_instruction.source_text or ""

    if not re.search(r"Section\s+7\.10", section_ref, re.IGNORECASE):
        return None

    if not re.search(r"Total Funded Debt to EBITDA|Core Leverage Ratio",
                      source_text, re.IGNORECASE):
        return None

    schedule = _extract_step_down_schedule(source_text)
    if schedule is None:
        # Section matches and covenant identified, but value extraction
        # failed → AMBIGUOUS_VALUE, not UNKNOWN_COMMITMENT.
        return StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="applicability",
            operation=InstructionType.REPLACE_VALUE,
            unit="ratio",
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.MANUAL,
            confidence=0.0,
            ambiguity_reason=AmbiguityReason.AMBIGUOUS_VALUE,
            citation_document=None,
            citation_section=section_ref,
        )

    return StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        field="applicability",
        operation=InstructionType.REPLACE_VALUE,
        new_value=schedule,
        unit="ratio",
        effective_at=parser_instruction.effective_start,
        source_span=source_text,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
        confidence=0.95,
        ambiguity_reason=None,
        citation_document=None,
        citation_section=section_ref,
    )


def _rule_junior_credit_agreement_addition(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map Junior Credit Agreement permitted indebtedness additions (e.g., Section 7.01).

    Trigger: target_section_ref matches "Section 7.01" AND source_text
    contains "Junior Credit Agreement" AND source_text contains a dollar
    amount.

    Produces an ADD mutation for facility.junior_credit_agreement with
    the extracted amount as a new CommitmentState payload.

    Returns None if the rule does not match.
    """
    section_ref = parser_instruction.target_section_ref or ""
    source_text = parser_instruction.source_text or ""

    if not re.search(r"Section\s+7\.01", section_ref, re.IGNORECASE):
        return None

    if not re.search(r"Junior Credit Agreement", source_text, re.IGNORECASE):
        return None

    amount = _extract_dollar_amount(source_text)
    if amount is None:
        return StructuredMutation(
            commitment_id="facility.junior_credit_agreement",
            field="amount",
            operation=InstructionType.ADD,
            unit="usd",
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.MANUAL,
            confidence=0.0,
            ambiguity_reason=AmbiguityReason.AMBIGUOUS_VALUE,
            citation_document=None,
            citation_section=section_ref,
        )

    new_value = {
        "canonical_key": "facility.junior_credit_agreement",
        "commitment_type": "facility_commitment",
        "party": ["borrower"],
        "action": "permit",
        "subject": "junior_credit_agreement",
        "threshold": amount,
        "unit": "usd",
    }

    return StructuredMutation(
        commitment_id="facility.junior_credit_agreement",
        field="amount",
        operation=InstructionType.ADD,
        new_value=new_value,
        unit="usd",
        effective_at=parser_instruction.effective_start,
        source_span=source_text,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
        confidence=0.90,
        ambiguity_reason=None,
        citation_document=None,
        citation_section=section_ref,
    )


# ---------------------------------------------------------------------------
# v0.1 scope — additional high-confidence pattern rules
# ---------------------------------------------------------------------------
#
# The following rules implement the remaining v0.1 scope patterns:
#   - Date / maturity replacement
#   - Rate / percentage replacement
#   - Explicit exception add/remove
#   - Explicit party change
#
# Each rule is deterministic and only fires when the textual evidence is
# strong enough for a high-confidence mapping.  Uncertain cases fall
# through to UNRESOLVED with a specific ambiguity reason.


def _rule_maturity_date_replacement(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map explicit Maturity Date amendments.

    Trigger: source_text contains "Maturity Date" AND a parseable date
    within 80 chars of that mention AND the section is not a known
    financial covenant section (a Maturity Date mention in a covenant
    section is likely a cross-reference, not an amendment to the
    maturity date).

    Produces a REPLACE_VALUE mutation on facility.credit_agreement.deadline
    with the extracted date string (YYYY-MM-DD).

    Returns None if the rule does not match.
    """
    source_text = parser_instruction.source_text or ""
    section_ref = parser_instruction.target_section_ref or ""

    if not re.search(r"Maturity\s+Date", source_text, re.IGNORECASE):
        return None

    # Guard: if the section maps to a financial covenant, do not fire.
    # A "Maturity Date" mention in a covenant section is likely a
    # cross-reference, not an amendment to the maturity date.
    mapped_cid = _section_to_commitment_id(section_ref)
    if mapped_cid is not None and mapped_cid.startswith("financial_covenant."):
        return None

    date_str = _extract_maturity_date(source_text)
    if date_str is None:
        # "Maturity Date" mentioned but no parseable date nearby →
        # AMBIGUOUS_VALUE, not a mapped mutation.
        return StructuredMutation(
            commitment_id="facility.credit_agreement",
            field="deadline",
            operation=InstructionType.REPLACE_VALUE,
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.MANUAL,
            confidence=0.0,
            ambiguity_reason=AmbiguityReason.AMBIGUOUS_VALUE,
            citation_document=None,
            citation_section=section_ref,
        )

    return StructuredMutation(
        commitment_id="facility.credit_agreement",
        field="deadline",
        operation=InstructionType.REPLACE_VALUE,
        new_value=date_str,
        unit="date",
        effective_at=parser_instruction.effective_start,
        source_span=source_text,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
        confidence=0.90,
        ambiguity_reason=None,
        citation_document=None,
        citation_section=section_ref,
    )


def _rule_rate_percentage_replacement(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map explicit applicable-rate / margin percentage changes.

    Trigger: source_text contains "Applicable Rate" or "Applicable Margin"
    AND a percentage value (e.g., "2.50%") AND the section is not a known
    financial covenant section (an Applicable Rate mention in a covenant
    section is likely a cross-reference, not an amendment to the rate).

    Produces a REPLACE_VALUE mutation on facility.credit_agreement.rate
    with the extracted percentage as a float.

    Returns None if the rule does not match.
    """
    source_text = parser_instruction.source_text or ""
    section_ref = parser_instruction.target_section_ref or ""

    if not re.search(r"Applicable\s+(Rate|Margin)", source_text, re.IGNORECASE):
        return None

    # Guard: if the section maps to a financial covenant, do not fire.
    # An "Applicable Rate" mention in a covenant section is likely a
    # cross-reference (e.g., pricing grid referenced by a covenant),
    # not an amendment to the rate itself.
    mapped_cid = _section_to_commitment_id(section_ref)
    if mapped_cid is not None and mapped_cid.startswith("financial_covenant."):
        return None

    pct = _extract_percentage(source_text)
    if pct is None:
        return StructuredMutation(
            commitment_id="facility.credit_agreement",
            field="rate",
            operation=InstructionType.REPLACE_VALUE,
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.MANUAL,
            confidence=0.0,
            ambiguity_reason=AmbiguityReason.AMBIGUOUS_VALUE,
            citation_document=None,
            citation_section=section_ref,
        )

    return StructuredMutation(
        commitment_id="facility.credit_agreement",
        field="rate",
        operation=InstructionType.REPLACE_VALUE,
        new_value=pct,
        unit="percent",
        effective_at=parser_instruction.effective_start,
        source_span=source_text,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
        confidence=0.85,
        ambiguity_reason=None,
        citation_document=None,
        citation_section=section_ref,
    )


def _rule_exception_add_remove(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map explicit exception (carve-out) additions and removals.

    Trigger: instruction_type is ADD or DELETE AND source_text contains
    "notwithstanding" or "shall not apply" or "except" followed by a
    specific carve-out description.

    For ADD: produces an ADD mutation with EXCEPTION_EXPANSION domain
    effect on the commitment identified by target_section_ref.
    For DELETE: produces a DELETE mutation with EXCEPTION_REMOVAL domain
    effect.

    The target commitment must be identifiable from target_section_ref.
    If the section does not map to a known commitment, the rule returns
    None so the caller can fall through to UNRESOLVED with
    UNKNOWN_COMMITMENT.

    Returns None if the rule does not match.
    """
    source_text = parser_instruction.source_text or ""
    section_ref = parser_instruction.target_section_ref or ""
    op = parser_instruction.instruction_type

    if op not in (InstructionType.ADD, InstructionType.DELETE):
        return None

    # Must contain explicit exception/carve-out language for high confidence.
    if not re.search(
        r"notwithstanding|shall\s+not\s+apply|except\s+(that|as)\b",
        source_text,
        re.IGNORECASE,
    ):
        return None

    # Map common covenant sections to commitment IDs.  If the section
    # does not map to a known commitment, return None so the caller
    # falls through to UNKNOWN_COMMITMENT.
    commitment_id = _section_to_commitment_id(section_ref)
    if commitment_id is None:
        return None

    # Extract the exception text — the sentence containing the
    # notwithstanding/except language.  The full-text regex guard above
    # guarantees at least one sentence matches, so exception_text is
    # always set here.
    sentences = re.split(r"(?<=[.])\s+", source_text)
    exception_text = ""
    for s in sentences:
        if re.search(
            r"notwithstanding|shall\s+not\s+apply|except\s+(that|as)\b",
            s,
            re.IGNORECASE,
        ):
            exception_text = s.strip()
            break

    if op == InstructionType.ADD:
        return StructuredMutation(
            commitment_id=commitment_id,
            field="exceptions",
            operation=InstructionType.ADD,
            new_value=exception_text,
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.85,
            ambiguity_reason=None,
            citation_document=None,
            citation_section=section_ref,
        )
    else:  # DELETE
        return StructuredMutation(
            commitment_id=commitment_id,
            field="exceptions",
            operation=InstructionType.DELETE,
            old_value=exception_text,
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.85,
            ambiguity_reason=None,
            citation_document=None,
            citation_section=section_ref,
        )


def _rule_party_change(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map explicit party (guarantor/borrower) additions and removals.

    Trigger: source_text contains "shall become a party" or "is hereby
    released" or "is hereby added as" followed by a party role
    (Guarantor, Borrower, Lender).

    Produces a REPLACE_VALUE mutation on the party field of the
    commitment identified by target_section_ref.

    Returns None if the rule does not match.
    """
    source_text = parser_instruction.source_text or ""
    section_ref = parser_instruction.target_section_ref or ""

    # Must contain explicit party-change language.  We capture WHICH
    # trigger phrase matched so the operation (ADD vs DELETE) is derived
    # from the actual trigger, not from a separate full-text search that
    # could match an unrelated phrase elsewhere in the source text.
    trigger_match = re.search(
        r"(?P<become>shall\s+become\s+a\s+party)"
        r"|(?P<released>is\s+hereby\s+released)"
        r"|(?P<added>is\s+hereby\s+added\s+as)",
        source_text,
        re.IGNORECASE,
    )
    if not trigger_match:
        return None

    # Must identify a party role for high confidence.  Search for the
    # role AFTER the trigger phrase (e.g., "shall become a party to
    # this Agreement as a Guarantor" → role is "Guarantor", not
    # "Borrower" which may appear earlier in the text).
    after_trigger = source_text[trigger_match.end():]
    role_match = re.search(
        r"\b(Guarantor|Borrower|Lender)\b",
        after_trigger,
        re.IGNORECASE,
    )
    if not role_match:
        return None

    role = role_match.group(1).lower()

    # Determine operation from the matched trigger phrase itself:
    #   "is hereby released" → DELETE (party leaving)
    #   "shall become a party" / "is hereby added as" → ADD (party joining)
    is_release = trigger_match.group("released") is not None

    commitment_id = _section_to_commitment_id(section_ref)
    if commitment_id is None:
        return None

    if is_release:
        return StructuredMutation(
            commitment_id=commitment_id,
            field="party",
            operation=InstructionType.DELETE,
            old_value=role,
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.85,
            ambiguity_reason=None,
            citation_document=None,
            citation_section=section_ref,
        )
    else:
        return StructuredMutation(
            commitment_id=commitment_id,
            field="party",
            operation=InstructionType.ADD,
            new_value=role,
            effective_at=parser_instruction.effective_start,
            source_span=source_text,
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.85,
            ambiguity_reason=None,
            citation_document=None,
            citation_section=section_ref,
        )


# Section-to-commitment mapping for exception and party-change rules.
# Maps common credit-agreement section references to canonical
# commitment IDs.  Returns None for unmapped sections.
_SECTION_COMMITMENT_MAP: dict[str, str] = {
    "section 7.10": "financial_covenant.leverage_ratio",
    "section 7.11": "financial_covenant.leverage_ratio",
    "section 7.01": "facility.credit_agreement",
    "section 7.02": "facility.credit_agreement",
    "section 7.03": "facility.credit_agreement",
    "section 6.01": "facility.credit_agreement",
    "section 6.02": "facility.credit_agreement",
}


def _section_to_commitment_id(section_ref: str) -> str | None:
    """Map a section reference to a canonical commitment ID.

    Returns None if the section does not map to a known commitment.
    """
    if not section_ref:
        return None
    ref_lower = section_ref.lower().strip()
    # Try exact match first, then prefix match (e.g., "Section 7.10(a)"
    # matches "section 7.10").
    if ref_lower in _SECTION_COMMITMENT_MAP:
        return _SECTION_COMMITMENT_MAP[ref_lower]
    for prefix, cid in _SECTION_COMMITMENT_MAP.items():
        if ref_lower.startswith(prefix):
            return cid
    return None


# Ordered list of mapping rules.  Each rule takes a parser instruction
# and returns a StructuredMutation if it matches, or None if it doesn't.
# The first matching rule wins.  Rules are validated against real EDGAR
# parser output and synthetic test cases.
_RULES: list = [
    _rule_leverage_ratio_step_down,
    _rule_junior_credit_agreement_addition,
    _rule_maturity_date_replacement,
    _rule_rate_percentage_replacement,
    _rule_exception_add_remove,
    _rule_party_change,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def map_instruction(
    parser_instruction: AmendmentInstruction,
    citation_document: str | None = None,
) -> MappingResult:
    """Map a parser-extracted instruction to a StructuredMutation.

    Args:
        parser_instruction: an instruction from parse_v04 (has
            instruction_type, target_section_ref, source_text).
        citation_document: the source document name for citation.

    Returns:
        MappingResult with either:
        - mutations: successfully mapped StructuredMutation(s)
          (provenance=SEMANTIC_MAPPER, ambiguity_reason=None), or
        - unresolved: a StructuredMutation with ambiguity_reason set
          (provenance=MANUAL).
    """
    result = MappingResult()
    section_ref = parser_instruction.target_section_ref or ""
    source_text = parser_instruction.source_text or ""

    for rule in _RULES:
        mutation = rule(parser_instruction)
        if mutation is not None:
            mutation.citation_document = citation_document
            if mutation.is_resolved:
                result.mutations.append(mutation)
                result.rules_matched.append(rule.__name__)
            else:
                result.unresolved.append(mutation)
            return result

    # No rule matched → UNRESOLVED with UNKNOWN_COMMITMENT.
    unresolved = StructuredMutation(
        commitment_id=None,
        field=None,
        operation=parser_instruction.instruction_type,
        effective_at=parser_instruction.effective_start,
        source_span=source_text,
        provenance=InstructionProvenance.MANUAL,
        confidence=0.0,
        ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
        citation_document=citation_document,
        citation_section=section_ref,
    )
    result.unresolved.append(unresolved)
    return result


def map_instructions(
    parser_instructions: list[AmendmentInstruction],
    citation_document: str | None = None,
) -> MappingResult:
    """Map a list of parser instructions to StructuredMutations.

    Args:
        parser_instructions: list of instructions from parse_v04.
        citation_document: source document name for all instructions.

    Returns:
        MappingResult with all mutations and unresolved from all
        instructions combined.
    """
    combined = MappingResult()
    for ins in parser_instructions:
        sub = map_instruction(ins, citation_document=citation_document)
        combined.mutations.extend(sub.mutations)
        combined.unresolved.extend(sub.unresolved)
        combined.rules_matched.extend(sub.rules_matched)
    return combined


def is_implemented() -> bool:
    """Check whether the semantic mapper is implemented.

    Returns True for v0.1: the mapper has deterministic rules for all
    six high-confidence v0.1 scope patterns (numeric threshold, commitment
    amount, date/maturity, rate/percentage, exception add/remove, party
    change).  Low-confidence patterns are routed to UNRESOLVED.
    """
    return True
