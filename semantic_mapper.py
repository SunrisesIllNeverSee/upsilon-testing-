"""Semantic mapping layer: section-level instructions → commitment fields.

This is the layer that converts parser-extracted section-level
instructions (from parse_v04) into commitment-level changes
(target_key, field, old_value, new_value) with citations,
confidence, and provenance.

STATUS: INTERFACE SCAFFOLD / NOT YET IMPLEMENTED.

This module defines the interface and data structures so the
real EDGAR smoke test can track provenance (SEMANTIC_MAPPER vs
MANUAL_FALLBACK) and so the 25-issuer study has a clear target
for implementation.  The map_instruction function is a stub that
returns all instructions as ambiguous (MANUAL provenance) — it
does not perform any mapping.  No rules are registered because
rules validated against synthetic text would be misleading: the
real parser output format (e.g., section_ref="Section 7.10" and
source_text containing "to exceed 4.00 to 1.00") differs from
what a naive rule would expect (e.g., "Section 7.10(a)" and "not
to exceed 3.50 to 1.00").  Rules must be validated against real
parser output before being registered.

When implemented, the semantic mapper will:

1. Take parser-extracted instructions (InstructionType, target_section_ref,
   source_text) as input.
2. Use a rule-based + pattern-matching approach to identify:
   - Which commitment is being modified (target_key)
   - Which field is being changed (threshold, frequency, deadline, etc.)
   - The old and new values (extracted from the source text)
   - The domain effect (COVENANT_THRESHOLD_CHANGE, COMMITMENT_AMOUNT_CHANGE, etc.)
3. Produce AmendmentInstruction objects with:
   - provenance = SEMANTIC_MAPPER
   - citation_document and citation_section populated
   - confidence reflecting extraction certainty
4. Flag ambiguous mappings for manual review (provenance = MANUAL).

The mapper will NOT be a general-purpose NLP system.  It will use
deterministic rules keyed to the section reference and pattern-matched
values (e.g., "Section 7.10" → financial_covenant.leverage_ratio,
"not to exceed X.XX to 1.00" → threshold = X.XX).

Release acceptance requires that routine field population be automated
by this layer, with manual review reserved for ambiguous mappings only.
Until is_implemented() returns True, all commitment-level instructions
in the EDGAR chains carry MANUAL_FALLBACK provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models import (
    AmendmentInstruction,
    DomainEffect,
    InstructionProvenance,
)


@dataclass
class MappingRule:
    r"""A deterministic rule for mapping a section reference to a commitment.

    Fields:
        section_pattern: regex pattern matching the target_section_ref
            (e.g., r"Section 7\.10\(a\)" matches "Section 7.10(a)")
        target_key: the commitment canonical key
        field: the CommitmentState field to modify
        domain_effect: the DomainEffect for this mapping
        value_pattern: regex pattern for extracting the new value from
            source_text (e.g., r"not to exceed ([\d.]+) to 1\.00"
            extracts the threshold from "not to exceed 3.50 to 1.00")
        value_converter: function to convert the regex match to the
            final value (e.g., float, int, dict)
        description: human-readable description of the rule

    NOTE: no rules are registered yet.  Rules must be validated against
    real parser output (target_section_ref format, source_text phrasing)
    before being added to _RULES.
    """

    section_pattern: str
    target_key: str
    field: str
    domain_effect: DomainEffect
    value_pattern: str | None = None
    value_converter: Any = None
    description: str = ""


@dataclass
class MappingResult:
    """Result of attempting to map a parser instruction to a commitment.

    Fields:
        instructions: successfully mapped AmendmentInstruction objects
            (provenance = SEMANTIC_MAPPER)
        ambiguous: instructions that could not be mapped automatically
            and require manual review (provenance = MANUAL)
        confidence: average confidence of mapped instructions
        rules_matched: list of MappingRule descriptions that fired
    """

    instructions: list[AmendmentInstruction] = field(default_factory=list)
    ambiguous: list[AmendmentInstruction] = field(default_factory=list)
    confidence: float = 0.0
    rules_matched: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule registry (empty — to be populated during 25-issuer study)
# ---------------------------------------------------------------------------

# This registry maps section references to commitment fields.
# It is populated incrementally as the 25-issuer study encounters
# new section patterns.  Each issuer's credit agreement uses
# different section numbers for covenants, so the registry is
# keyed by (issuer_pattern, section_pattern) or by a generic
# section pattern that works across issuers.
#
# IMPORTANT: rules must be validated against real parser output
# before being registered.  The parser's target_section_ref format
# (e.g., "Section 7.10" not "Section 7.10(a)") and source_text
# phrasing (e.g., "to exceed 4.00 to 1.00" not "not to exceed 3.50
# to 1.00") must match the rule's section_pattern and value_pattern
# respectively.  Rules that work on synthetic text but not on real
# parser output are misleading and must not be registered.
_RULES: list[MappingRule] = []


def map_instruction(
    parser_instruction: AmendmentInstruction,
    citation_document: str | None = None,
) -> MappingResult:
    """Attempt to map a parser-extracted instruction to a commitment field.

    Args:
        parser_instruction: an instruction from parse_v04 (has
            instruction_type, target_section_ref, source_text, but
            may not have target_key, field, old_value, new_value).
        citation_document: the source document name for citation.

    Returns:
        MappingResult with mapped instructions (provenance=SEMANTIC_MAPPER)
        or ambiguous instructions (provenance=MANUAL).

    NOTE: this is a stub.  No rules are registered, so every instruction
    is returned as ambiguous (MANUAL provenance).  When rules are added
    and validated against real parser output, this function will perform
    actual mapping.
    """
    result = MappingResult()

    # No rules registered — flag the original as ambiguous for manual review.
    result.ambiguous.append(
        AmendmentInstruction(
            order=parser_instruction.order,
            instruction_type=parser_instruction.instruction_type,
            target_key=parser_instruction.target_key,
            target_section_ref=parser_instruction.target_section_ref,
            field=parser_instruction.field,
            old_value=parser_instruction.old_value,
            new_value=parser_instruction.new_value,
            effective_start=parser_instruction.effective_start,
            effective_end=parser_instruction.effective_end,
            source_text=parser_instruction.source_text,
            confidence=0.3,
            domain_effect=parser_instruction.domain_effect,
            provenance=InstructionProvenance.MANUAL,
            citation_document=citation_document,
            citation_section=parser_instruction.target_section_ref,
        )
    )

    return result


def is_implemented() -> bool:
    """Check whether the semantic mapper is fully implemented.

    Returns False until the mapper can handle routine field population
    without manual intervention.  The 25-issuer study requires this
    to return True before release acceptance.

    The mapper is currently a pure interface stub:
      - No rules are registered in _RULES.
      - map_instruction returns all instructions as ambiguous (MANUAL).
      - No instruction in the EDGAR chains carries SEMANTIC_MAPPER provenance.
    """
    return False
