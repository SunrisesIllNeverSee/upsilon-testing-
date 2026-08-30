"""Tests for the semantic-mapping layer scaffold.

These tests verify that the semantic mapper is an honest interface stub:
  - is_implemented() returns False.
  - No rules are registered.
  - map_instruction returns all instructions as ambiguous (MANUAL provenance),
    not as SEMANTIC_MAPPER.
  - The stub does not pretend to map anything it cannot actually map.

When the mapper is implemented (rules validated against real parser output),
these tests will be updated to verify real mapping behavior.
"""
from __future__ import annotations

from datetime import datetime

from models import (
    AmendmentInstruction,
    DomainEffect,
    InstructionProvenance,
    InstructionType,
)
from semantic_mapper import (
    _RULES,
    is_implemented,
    map_instruction,
)


def test_is_implemented_returns_false():
    """The semantic mapper is not yet implemented."""
    assert is_implemented() is False


def test_no_rules_registered():
    """No mapping rules are registered until validated against real parser output."""
    assert _RULES == []


def test_map_instruction_returns_ambiguous_for_unmapped_instruction():
    """An instruction with no matching rule is flagged as ambiguous (MANUAL)."""
    parser_instruction = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 7.10",
        source_text="Section 7.10 is hereby amended by deleting paragraph (a)...",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction, citation_document="Amendment No. 3")
    assert len(result.instructions) == 0
    assert len(result.ambiguous) == 1
    assert result.ambiguous[0].provenance == InstructionProvenance.MANUAL
    assert result.ambiguous[0].citation_document == "Amendment No. 3"
    assert result.ambiguous[0].citation_section == "Section 7.10"
    assert result.confidence == 0.0


def test_map_instruction_does_not_produce_semantic_mapper_provenance():
    """The stub must never produce SEMANTIC_MAPPER provenance."""
    parser_instruction = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_section_ref="Section 7.10(a)",
        source_text="not to exceed 3.50 to 1.00",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction)
    for ins in result.instructions:
        assert ins.provenance != InstructionProvenance.SEMANTIC_MAPPER, \
            "Stub must not produce SEMANTIC_MAPPER provenance"


def test_map_instruction_preserves_instruction_metadata():
    """The stub preserves the original instruction's metadata in the ambiguous copy."""
    parser_instruction = AmendmentInstruction(
        order=2,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.01(a)(xi)",
        target_key="facility.junior_credit_agreement",
        field="amount",
        source_text="Indebtedness under the Junior Credit Agreement...",
        effective_start=datetime(2024, 6, 28),
        domain_effect=DomainEffect.COMMITMENT_AMOUNT_CHANGE,
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction, citation_document="Amendment No. 6")
    amb = result.ambiguous[0]
    assert amb.order == 2
    assert amb.instruction_type == InstructionType.ADD
    assert amb.target_section_ref == "Section 7.01(a)(xi)"
    assert amb.target_key == "facility.junior_credit_agreement"
    assert amb.field == "amount"
    assert amb.effective_start == datetime(2024, 6, 28)
    assert amb.domain_effect == DomainEffect.COMMITMENT_AMOUNT_CHANGE


def test_map_instruction_handles_none_citation_document():
    """The stub handles a None citation_document gracefully."""
    parser_instruction = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 2.07",
        source_text="some text",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction, citation_document=None)
    assert result.ambiguous[0].citation_document is None
