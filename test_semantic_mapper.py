"""Basic regression tests for the semantic-mapping layer.

These tests verify the v0.1 mapper's basic API contracts:
  - is_implemented() returns True.
  - Rules are registered and validated against real parser output.
  - map_instruction returns MappingResult with mutations/unresolved.
  - Mapped mutations carry SEMANTIC_MAPPER provenance.
  - Unresolved mutations carry MANUAL provenance and an ambiguity reason.
  - The mapper never produces a best-guess mapping for uncertain input.

Thorough gold-mapping tests against real EDGAR parser output are in
test_semantic_mapper_v01.py.
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
    AmbiguityReason,
    MappingResult,
    StructuredMutation,
    _RULES,
    is_implemented,
    map_instruction,
)


def test_is_implemented_returns_true():
    """v0.1 mapper is implemented."""
    assert is_implemented() is True


def test_rules_registered():
    """Mapping rules are registered (validated against real parser output)."""
    assert len(_RULES) >= 6


def test_map_instruction_returns_mapping_result_for_unmapped():
    """An instruction with no matching rule returns UNRESOLVED."""
    parser_instruction = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 2.07",
        source_text="some text without commitment-level content",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction, citation_document="Amendment No. 1")
    assert isinstance(result, MappingResult)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].provenance == InstructionProvenance.MANUAL
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.UNKNOWN_COMMITMENT
    assert result.unresolved[0].citation_document == "Amendment No. 1"
    assert result.unresolved[0].citation_section == "Section 2.07"


def test_map_instruction_produces_semantic_mapper_provenance_for_mapped():
    """A mapped instruction carries SEMANTIC_MAPPER provenance."""
    parser_instruction = AmendmentInstruction(
        order=5,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 7.10",
        source_text=(
            "Total Funded Debt to EBITDA Ratio. The Loan Parties shall not "
            "permit the Core Leverage Ratio as of the end of each fiscal "
            "quarter (i) ending on June 30, 2023 to exceed 4.00 to 1.00, "
            "and (ii) for any quarter ending thereafter, to exceed 3.50 to 1.00."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None
    assert mut.commitment_id == "financial_covenant.leverage_ratio"


def test_map_instruction_preserves_effective_at():
    """The mapper preserves effective_start as effective_at in the mutation."""
    parser_instruction = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.01",
        source_text=(
            "Junior Credit Agreement in an aggregate amount not to exceed "
            "$150,000,000"
        ),
        effective_start=datetime(2024, 6, 28),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction, citation_document="Amendment No. 6")
    mut = result.mutations[0]
    assert mut.effective_at == datetime(2024, 6, 28)


def test_map_instruction_handles_none_citation_document():
    """The mapper handles a None citation_document gracefully."""
    parser_instruction = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 2.07",
        source_text="some text",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_instruction, citation_document=None)
    assert result.unresolved[0].citation_document is None


def test_structured_mutation_to_amendment_instruction_sets_domain_effect():
    """Conversion to AmendmentInstruction sets domain_effect based on field."""
    # Threshold/applicability → COVENANT_THRESHOLD_CHANGE
    mut1 = StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        field="applicability",
        operation=InstructionType.REPLACE_VALUE,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins1 = mut1.to_amendment_instruction()
    assert ins1.domain_effect == DomainEffect.COVENANT_THRESHOLD_CHANGE

    # Amount → COMMITMENT_AMOUNT_CHANGE
    mut2 = StructuredMutation(
        commitment_id="facility.junior_credit_agreement",
        field="amount",
        operation=InstructionType.ADD,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins2 = mut2.to_amendment_instruction()
    assert ins2.domain_effect == DomainEffect.COMMITMENT_AMOUNT_CHANGE

    # Deadline → DEADLINE_CHANGE
    mut4 = StructuredMutation(
        commitment_id="facility.credit_agreement",
        field="deadline",
        operation=InstructionType.REPLACE_VALUE,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins4 = mut4.to_amendment_instruction()
    assert ins4.domain_effect == DomainEffect.DEADLINE_CHANGE

    # Rate → RATE_CHANGE
    mut5 = StructuredMutation(
        commitment_id="facility.credit_agreement",
        field="rate",
        operation=InstructionType.REPLACE_VALUE,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins5 = mut5.to_amendment_instruction()
    assert ins5.domain_effect == DomainEffect.RATE_CHANGE

    # Exceptions ADD → EXCEPTION_EXPANSION
    mut6 = StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        field="exceptions",
        operation=InstructionType.ADD,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins6 = mut6.to_amendment_instruction()
    assert ins6.domain_effect == DomainEffect.EXCEPTION_EXPANSION

    # Exceptions DELETE → EXCEPTION_REMOVAL
    mut7 = StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        field="exceptions",
        operation=InstructionType.DELETE,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins7 = mut7.to_amendment_instruction()
    assert ins7.domain_effect == DomainEffect.EXCEPTION_REMOVAL

    # Party → PARTY_CHANGE
    mut8 = StructuredMutation(
        commitment_id="facility.credit_agreement",
        field="party",
        operation=InstructionType.ADD,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
    )
    ins8 = mut8.to_amendment_instruction()
    assert ins8.domain_effect == DomainEffect.PARTY_CHANGE

    # UNRESOLVED → no domain effect
    mut3 = StructuredMutation(
        operation=InstructionType.REPLACE_TEXT,
        ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
    )
    ins3 = mut3.to_amendment_instruction()
    assert ins3.domain_effect is None
