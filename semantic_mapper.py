"""Semantic mapping layer: section-level instructions → commitment fields.

This is the layer that converts parser-extracted section-level
instructions (from parse_v04) into commitment-level changes
(target_key, field, old_value, new_value) with citations,
confidence, and provenance.

STATUS: SCAFFOLD / NOT YET IMPLEMENTED.

The scaffold defines the interface and data structures so the
real EDGAR smoke test can track provenance (SEMANTIC_MAPPER vs
MANUAL_FALLBACK) and so the 25-issuer study has a clear target
for implementation.

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
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models import (
    AmendmentInstruction,
    DomainEffect,
    InstructionProvenance,
    InstructionType,
)


@dataclass
class MappingRule:
    """A deterministic rule for mapping a section reference to a commitment.

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
# Rule registry (to be populated during 25-issuer study)
# ---------------------------------------------------------------------------

# This registry maps section references to commitment fields.
# It is populated incrementally as the 25-issuer study encounters
# new section patterns.  Each issuer's credit agreement uses
# different section numbers for covenants, so the registry is
# keyed by (issuer_pattern, section_pattern) or by a generic
# section pattern that works across issuers.

_RULES: list[MappingRule] = [
    # Ameresco: Section 7.10(a) = Core Leverage Ratio
    MappingRule(
        section_pattern=r"Section 7\.10\(a\)",
        target_key="financial_covenant.leverage_ratio",
        field="applicability",
        domain_effect=DomainEffect.COVENANT_THRESHOLD_CHANGE,
        value_pattern=r"not to exceed ([\d.]+) to 1\.00",
        value_converter=float,
        description="Ameresco Section 7.10(a) Core Leverage Ratio threshold",
    ),
    # Ameresco: Section 7.10(b) = Debt Service Coverage Ratio
    MappingRule(
        section_pattern=r"Section 7\.10\(b\)",
        target_key="financial_covenant.debt_service_coverage",
        field="threshold",
        domain_effect=DomainEffect.COVENANT_THRESHOLD_CHANGE,
        value_pattern=r"not to be less than ([\d.]+) to 1\.00",
        value_converter=float,
        description="Ameresco Section 7.10(b) Debt Service Coverage Ratio threshold",
    ),
]


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
    """
    import re

    result = MappingResult()
    section_ref = parser_instruction.target_section_ref or ""

    for rule in _RULES:
        if re.search(rule.section_pattern, section_ref, re.IGNORECASE):
            result.rules_matched.append(rule.description)

            # Try to extract value from source_text
            new_value = None
            if rule.value_pattern and rule.value_converter and parser_instruction.source_text:
                m = re.search(rule.value_pattern, parser_instruction.source_text, re.IGNORECASE)
                if m:
                    try:
                        new_value = rule.value_converter(m.group(1))
                    except (ValueError, TypeError):
                        pass

            if new_value is not None:
                mapped = AmendmentInstruction(
                    order=parser_instruction.order,
                    instruction_type=parser_instruction.instruction_type,
                    target_key=rule.target_key,
                    target_section_ref=parser_instruction.target_section_ref,
                    field=rule.field,
                    old_value=parser_instruction.old_value,
                    new_value=new_value,
                    effective_start=parser_instruction.effective_start,
                    effective_end=parser_instruction.effective_end,
                    source_text=parser_instruction.source_text,
                    confidence=0.85,
                    domain_effect=rule.domain_effect,
                    provenance=InstructionProvenance.SEMANTIC_MAPPER,
                    citation_document=citation_document,
                    citation_section=parser_instruction.target_section_ref,
                )
                result.instructions.append(mapped)
            else:
                # Value could not be extracted — flag for manual review
                ambiguous = AmendmentInstruction(
                    order=parser_instruction.order,
                    instruction_type=parser_instruction.instruction_type,
                    target_key=rule.target_key,
                    target_section_ref=parser_instruction.target_section_ref,
                    field=rule.field,
                    old_value=parser_instruction.old_value,
                    new_value=parser_instruction.new_value,
                    effective_start=parser_instruction.effective_start,
                    effective_end=parser_instruction.effective_end,
                    source_text=parser_instruction.source_text,
                    confidence=0.5,
                    domain_effect=rule.domain_effect,
                    provenance=InstructionProvenance.MANUAL,
                    citation_document=citation_document,
                    citation_section=parser_instruction.target_section_ref,
                )
                result.ambiguous.append(ambiguous)
            break

    if not result.rules_matched:
        # No rule matched — flag the original as ambiguous
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

    if result.instructions:
        result.confidence = sum(i.confidence for i in result.instructions) / len(result.instructions)

    return result


def is_implemented() -> bool:
    """Check whether the semantic mapper is fully implemented.

    Returns False until the mapper can handle routine field population
    without manual intervention.  The 25-issuer study requires this
    to return True before release acceptance.
    """
    # The mapper is scaffolded but not yet production-ready.
    # It has rules for Ameresco sections but not for the full corpus.
    return False
