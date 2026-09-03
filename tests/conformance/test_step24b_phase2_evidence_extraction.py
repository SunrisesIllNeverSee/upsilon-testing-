"""Step 24B Phase 2 conformance tests — Evidence Extraction.

These tests enforce that:
1. AmendmentInstruction → AmendmentEvidence conversion preserves
   evidence signals (source text, section ref, instruction type).
2. The evidence extractor does NOT perform final identity resolution.
3. The evidence extractor does NOT perform final field determination.
4. The evidence extractor does NOT perform final value extraction
   beyond what the parser/instruction already declared.
5. Alias matches are WEAK signals (evidence, not authority).
6. A violation path: evidence with no section ref and no alias
   produces no identity signals.
7. Designated real EDGAR case: Ameresco A1 Section 7.10(a) evidence.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from upsilon.models.legacy_models import (
    AmendmentInstruction,
    InstructionType,
    InstructionProvenance,
    DomainEffect,
)
from upsilon.transformations.authorized_change import AmendmentEvidence
from upsilon.evidence.evidence_extractor import (
    instruction_to_evidence,
    instructions_to_evidence,
)


def _ameresco_a1_instruction() -> AmendmentInstruction:
    """Ameresco A1 Section 7.10(a) leverage ratio amendment instruction.

    This is the designated real EDGAR SCALAR_REPLACEMENT case.
    """
    return AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_key="financial_covenant.leverage_ratio",
        target_section_ref="Section 7.10(a)",
        field="applicability",
        old_value={
            "step_down_schedule": [
                {"period_end": "2022-03-31", "threshold": 4.50},
                {"period_end": "2022-06-30", "threshold": 4.25},
                {"period_end": "2022-09-30", "threshold": 4.00},
                {"period_end": "2022-12-31", "threshold": 4.00},
            ],
            "steady_state_threshold": 3.50,
        },
        new_value={
            "step_down_schedule": [
                {"period_end": "2023-06-30", "threshold": 4.00},
                {"period_end": "2023-09-30", "threshold": 4.25},
            ],
            "steady_state_threshold": 3.50,
        },
        effective_start=datetime(2023, 8, 24),
        source_text=(
            "Section 7.10 of the Credit Agreement is hereby amended "
            "by deleting paragraph (a) in its entirety and replacing "
            "it with the following: (a) Total Funded Debt to EBITDA "
            "Ratio. The Loan Parties shall not permit the Core "
            "Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on June 30, 2023 to exceed 4.00 to 1.00, "
            "(ii) ending on September 30, 2023 to exceed 4.25 to "
            "1.00, and (ii) for any quarter ending thereafter, to "
            "exceed 3.50 to 1.00."
        ),
        domain_effect=DomainEffect.COVENANT_THRESHOLD_CHANGE,
        provenance=InstructionProvenance.MANUAL_FALLBACK,
        citation_document="Amendment No. 3, Aug 24, 2023",
        citation_section="Section 7.10(a)",
    )


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestInstructionToEvidence:
    """Test AmendmentInstruction → AmendmentEvidence conversion."""

    def test_conversion_produces_evidence_object(self):
        """Positive: conversion produces an AmendmentEvidence object."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert isinstance(evidence, AmendmentEvidence)

    def test_evidence_carries_source_text(self):
        """Positive: evidence carries the source text span."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.source_text == ins.source_text
        assert "Section 7.10" in evidence.source_text
        assert "Core Leverage Ratio" in evidence.source_text

    def test_evidence_carries_section_ref(self):
        """Positive: evidence carries the section reference."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.source_section_ref == "Section 7.10(a)"

    def test_evidence_carries_instruction_type(self):
        """Positive: evidence carries the parser instruction type."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.instruction_type == "REPLACE_VALUE"

    def test_evidence_carries_target_field_hint(self):
        """Positive: evidence carries the target field as a hint."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.target_field == "applicability"

    def test_evidence_carries_declared_values(self):
        """Positive: evidence carries declared old/new values."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.new_value is not None
        assert evidence.new_value["steady_state_threshold"] == 3.50
        assert evidence.declared_old_value is not None
        assert evidence.declared_old_value["steady_state_threshold"] == 3.50

    def test_evidence_carries_source_authority(self):
        """Positive: evidence carries the source authority string."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )

        assert "Amendment No. 3" in evidence.source_authority
        assert "Section 7.10(a)" in evidence.source_authority

    def test_evidence_carries_canonical_key_hint(self):
        """Positive: evidence carries the canonical key hint."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.canonical_key_hint == "financial_covenant.leverage_ratio"

    def test_evidence_carries_effective_date(self):
        """Positive: evidence carries the effective date."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.effective_date == datetime(2023, 8, 24)

    def test_evidence_carries_alias_match(self):
        """Positive: evidence carries an alias match (weak signal)."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        # "Core Leverage Ratio" in the source text should produce
        # an alias match for "leverage_ratio"
        assert evidence.alias_match is not None
        assert "leverage" in evidence.alias_match.lower()

    def test_evidence_carries_value_provenance(self):
        """Positive: evidence carries value provenance from the instruction.

        The Ameresco A1 instruction has MANUAL_FALLBACK provenance,
        so the evidence's value_provenance must be CURATOR_PROVIDED.
        """
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert evidence.value_provenance == "CURATOR_PROVIDED"

    def test_evidence_parser_provenance_for_automated_instructions(self):
        """Positive: PARSER provenance produces PARSER_EXTRACTED evidence."""
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_section_ref="Section 7.10(a)",
            field="threshold",
            new_value=3.00,
            source_text="Some text",
            provenance=InstructionProvenance.PARSER,
        )
        evidence = instruction_to_evidence(ins)

        assert evidence.value_provenance == "PARSER_EXTRACTED"


class TestInstructionsToEvidence:
    """Test batch conversion."""

    def test_batch_conversion_preserves_order(self):
        """Positive: batch conversion preserves instruction order."""
        ins1 = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_section_ref="Section 7.10(a)",
            source_text="First instruction",
        )
        ins2 = AmendmentInstruction(
            order=2,
            instruction_type=InstructionType.ADD,
            target_section_ref="Section 7.01",
            source_text="Second instruction",
        )

        evidence_list = instructions_to_evidence([ins1, ins2])

        assert len(evidence_list) == 2
        assert evidence_list[0].source_text == "First instruction"
        assert evidence_list[1].source_text == "Second instruction"


# ---------------------------------------------------------------------------
# Evidence/interpretation separation tests
# ---------------------------------------------------------------------------


class TestEvidenceInterpretationSeparation:
    """Test that evidence extraction does NOT perform interpretation."""

    def test_evidence_does_not_resolve_identity(self):
        """Positive: evidence does not carry a resolved commitment_id.

        The AmendmentEvidence dataclass has no commitment_id field.
        Identity resolution is the engine's job (Layer B).
        """
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        # AmendmentEvidence has no commitment_id field
        assert not hasattr(evidence, "commitment_id")
        # canonical_key_hint is a HINT, not a resolved identity
        assert evidence.canonical_key_hint is not None

    def test_evidence_does_not_determine_operation(self):
        """Positive: evidence carries instruction_type but not
        TransformationFamily.  Operation classification is the engine's job."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        # evidence.instruction_type is the parser's raw type
        assert evidence.instruction_type == "REPLACE_VALUE"
        # AmendmentEvidence has no transformation_family field
        assert not hasattr(evidence, "transformation_family")

    def test_field_hint_is_evidence_not_determination(self):
        """Positive: target_field is a hint from the instruction,
        not a final field determination by the evidence extractor."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        # The field comes from the instruction, not from the extractor
        # interpreting the text.  The engine may override it.
        assert evidence.target_field == ins.field


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestEvidenceExtractionViolations:
    """Violation paths in evidence extraction."""

    def test_empty_source_text_produces_no_alias(self):
        """Violation: empty source text produces no alias match."""
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            source_text="",
        )
        evidence = instruction_to_evidence(ins)

        assert evidence.alias_match is None
        assert evidence.text_match is None

    def test_no_section_ref_produces_no_section_signal(self):
        """Violation: no section ref means no address-map signal."""
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            source_text="Some text without section ref",
        )
        evidence = instruction_to_evidence(ins)

        assert evidence.source_section_ref is None

    def test_unrelated_text_produces_no_alias(self):
        """Violation: text with no commitment terms produces no alias."""
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            source_text="The Borrower agrees to pay fees.",
        )
        evidence = instruction_to_evidence(ins)

        assert evidence.alias_match is None

    def test_no_declared_values_produces_none_values(self):
        """Violation: instruction with no values produces None evidence values."""
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            source_text="Some text",
        )
        evidence = instruction_to_evidence(ins)

        assert evidence.new_value is None
        assert evidence.declared_old_value is None


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1Evidence:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_evidence_has_correct_signals(self):
        """Positive: Ameresco A1 evidence has all required signals."""
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )

        # Section ref signal (for address-map resolution)
        assert evidence.source_section_ref == "Section 7.10(a)"
        # Instruction type (for transformation family classification)
        assert evidence.instruction_type == "REPLACE_VALUE"
        # Field hint (for affected field determination)
        assert evidence.target_field == "applicability"
        # Declared old value (for old-value consistency check)
        assert evidence.declared_old_value is not None
        assert evidence.declared_old_value["steady_state_threshold"] == 3.50
        # New value (for successor state)
        assert evidence.new_value is not None
        assert evidence.new_value["steady_state_threshold"] == 3.50
        # Source authority (for lineage continuity)
        assert "Amendment No. 3" in evidence.source_authority
        # Canonical key hint (for identity resolution corroboration)
        assert evidence.canonical_key_hint == "financial_covenant.leverage_ratio"
        # Alias match (weak signal for corroboration)
        assert evidence.alias_match is not None

    def test_ameresco_a1_evidence_does_not_resolve_identity(self):
        """Positive: Ameresco A1 evidence does NOT resolve identity.

        The evidence carries signals (section ref, alias, canonical key
        hint) but does NOT carry a resolved commitment_id.  The
        AuthorizedTransformationEngine will resolve identity using
        the AgreementAddressMap.
        """
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(ins)

        assert not hasattr(evidence, "commitment_id")
        assert evidence.canonical_key_hint == "financial_covenant.leverage_ratio"
        assert evidence.source_section_ref == "Section 7.10(a)"
        assert evidence.alias_match is not None
