"""Semantic mapping layer: parsed legal instructions → structured commitment mutations.

STATUS: v0.1 — IMPLEMENTED for high-confidence patterns only.

This module converts parser-extracted section-level instructions (from
parse_v04) into StructuredMutation objects that the executor can apply
to commitment state.  The mapper uses deterministic rules validated
against real EDGAR parser output.

v0.1 scope:
  - Numeric threshold replacement (leverage ratio step-down schedules)
  - Commitment amount replacement (facility additions)
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
            if self.field == "threshold" or self.field == "applicability":
                domain_effect = DomainEffect.COVENANT_THRESHOLD_CHANGE
            elif self.field == "amount":
                domain_effect = DomainEffect.COMMITMENT_AMOUNT_CHANGE

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


# ---------------------------------------------------------------------------
# Mapping rules
# ---------------------------------------------------------------------------


def _rule_ameresco_leverage_ratio(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map Ameresco Section 7.10 leverage ratio step-down schedule changes.

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


def _rule_ameresco_junior_credit_agreement(
    parser_instruction: AmendmentInstruction,
) -> StructuredMutation | None:
    """Map Ameresco Section 7.01 Junior Credit Agreement permitted indebtedness.

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


# Ordered list of mapping rules.  Each rule takes a parser instruction
# and returns a StructuredMutation if it matches, or None if it doesn't.
# The first matching rule wins.  Rules are validated against real EDGAR
# parser output.
_RULES: list = [
    _rule_ameresco_leverage_ratio,
    _rule_ameresco_junior_credit_agreement,
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

    Returns True for v0.1: the mapper has deterministic rules validated
    against real EDGAR parser output and can map high-confidence
    patterns (leverage ratio step-down schedules, commitment amount
    additions).  Low-confidence patterns are routed to UNRESOLVED.
    """
    return True
