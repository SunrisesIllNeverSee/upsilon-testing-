"""Independent tests for Semantic Mapper v0.1.

These tests validate the mapper against gold semantic mappings derived
from real EDGAR parser output.  The mapper is tested independently
from the full pipeline — it receives parser instructions and its
output is compared to gold StructuredMutation objects.

Test structure:
  1. Schema tests — StructuredMutation and AmbiguityReason contracts.
  2. Unit tests — individual rules and value extraction helpers.
  3. Gold-mapping tests — mapper output vs gold for each real EDGAR chain.
  4. Safety tests — uncertain mappings are UNRESOLVED, never best-guess.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from models import (
    AmendmentInstruction,
    InstructionProvenance,
    InstructionType,
)
from semantic_mapper import (
    AmbiguityReason,
    MappingResult,
    StructuredMutation,
    _extract_dollar_amount,
    _extract_step_down_schedule,
    _parse_date,
    is_implemented,
    map_instruction,
    map_instructions,
)
from semantic_gold import (
    all_gold_mappings,
    gold_ameresco_a1,
    gold_ameresco_a2,
    gold_ameresco_a3,
)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_is_implemented_returns_true():
    """v0.1 mapper is implemented."""
    assert is_implemented() is True


def test_structured_mutation_is_resolved_property():
    """is_resolved is True only when ambiguity_reason is None and commitment_id is set."""
    resolved = StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        field="applicability",
        operation=InstructionType.REPLACE_VALUE,
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
        confidence=0.95,
    )
    assert resolved.is_resolved is True

    unresolved = StructuredMutation(
        commitment_id=None,
        operation=InstructionType.REPLACE_TEXT,
        ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
    )
    assert unresolved.is_resolved is False

    # Edge case: commitment_id set but ambiguity_reason also set → not resolved
    edge = StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        operation=InstructionType.REPLACE_VALUE,
        ambiguity_reason=AmbiguityReason.AMBIGUOUS_VALUE,
    )
    assert edge.is_resolved is False


def test_structured_mutation_to_amendment_instruction():
    """Conversion to AmendmentInstruction preserves all fields."""
    mut = StructuredMutation(
        commitment_id="financial_covenant.leverage_ratio",
        field="applicability",
        operation=InstructionType.REPLACE_VALUE,
        new_value={"steady_state_threshold": 3.50},
        unit="ratio",
        effective_at=datetime(2023, 8, 24),
        source_span="Section 7.10 ... to exceed 3.50 to 1.00",
        provenance=InstructionProvenance.SEMANTIC_MAPPER,
        confidence=0.95,
        citation_document="Amendment No. 3",
        citation_section="Section 7.10",
    )
    ins = mut.to_amendment_instruction(order=5)
    assert ins.order == 5
    assert ins.target_key == "financial_covenant.leverage_ratio"
    assert ins.field == "applicability"
    assert ins.instruction_type == InstructionType.REPLACE_VALUE
    assert ins.new_value == {"steady_state_threshold": 3.50}
    assert ins.effective_start == datetime(2023, 8, 24)
    assert ins.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert ins.confidence == 0.95
    assert ins.citation_document == "Amendment No. 3"
    assert ins.citation_section == "Section 7.10"


def test_ambiguity_reason_values():
    """All six ambiguity reasons are defined."""
    assert AmbiguityReason.UNKNOWN_COMMITMENT.value == "unknown_commitment"
    assert AmbiguityReason.UNKNOWN_FIELD.value == "unknown_field"
    assert AmbiguityReason.AMBIGUOUS_TARGET.value == "ambiguous_target"
    assert AmbiguityReason.AMBIGUOUS_VALUE.value == "ambiguous_value"
    assert AmbiguityReason.CROSS_REFERENCE_REQUIRED.value == "cross_reference_required"
    assert AmbiguityReason.DEFINED_TERM_REQUIRED.value == "defined_term_required"


# ---------------------------------------------------------------------------
# Value extraction helper tests
# ---------------------------------------------------------------------------


def test_parse_date_standard():
    assert _parse_date("June 30, 2023") == "2023-06-30"
    assert _parse_date("December 31, 2023") == "2023-12-31"
    assert _parse_date("September 30 2023") == "2023-09-30"


def test_parse_date_invalid():
    assert _parse_date("not a date") is None
    assert _parse_date("Junuary 30, 2023") is None


def test_extract_step_down_schedule_a1():
    """A1 leverage ratio schedule: 2 step-down entries + steady state."""
    text = (
        "(a) Total Funded Debt to EBITDA Ratio. The Loan Parties shall not "
        "permit the Core Leverage Ratio as of the end of each fiscal quarter "
        "(i) ending on June 30, 2023 to exceed 4.00 to 1.00, (ii) ending on "
        "September 30, 2023 to exceed 4.25 to 1.00, and (ii) for any quarter "
        "ending thereafter, to exceed 3.50 to 1.00."
    )
    schedule = _extract_step_down_schedule(text)
    assert schedule is not None
    assert len(schedule["step_down_schedule"]) == 2
    assert schedule["step_down_schedule"][0] == {"period_end": "2023-06-30", "threshold": 4.00}
    assert schedule["step_down_schedule"][1] == {"period_end": "2023-09-30", "threshold": 4.25}
    assert schedule["steady_state_threshold"] == 3.50


def test_extract_step_down_schedule_a2():
    """A2 leverage ratio schedule: 1 step-down entry + steady state."""
    text = (
        "(a) Total Funded Debt to EBITDA Ratio. The Loan Parties shall not "
        "permit the Core Leverage Ratio as of the end of each fiscal quarter "
        "(i) ending on December 31, 2023 to exceed 3.75 to 1.00, and (ii) "
        "for any quarter ending thereafter, to exceed 3.50 to 1.00."
    )
    schedule = _extract_step_down_schedule(text)
    assert schedule is not None
    assert len(schedule["step_down_schedule"]) == 1
    assert schedule["step_down_schedule"][0] == {"period_end": "2023-12-31", "threshold": 3.75}
    assert schedule["steady_state_threshold"] == 3.50


def test_extract_step_down_schedule_no_match():
    """No schedule pattern → None."""
    assert _extract_step_down_schedule("no schedule here") is None


def test_extract_dollar_amount():
    assert _extract_dollar_amount("$150,000,000") == 150_000_000
    assert _extract_dollar_amount("$2,802,125,000") == 2_802_125_000
    assert _extract_dollar_amount("not to exceed $150,000,000 plus") == 150_000_000
    assert _extract_dollar_amount("no amount") is None


# ---------------------------------------------------------------------------
# Rule tests — leverage ratio
# ---------------------------------------------------------------------------


def test_rule_leverage_ratio_maps_a1_instruction():
    """A1 Section 7.10 instruction maps to leverage ratio schedule change."""
    parser_ins = AmendmentInstruction(
        order=5,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 7.10",
        source_text=(
            "Section 7.10 of the Credit Agreement is hereby amended by "
            "deleting paragraph (a) in its entirety and replacing it with "
            "the following: (a) Total Funded Debt to EBITDA Ratio. The Loan "
            "Parties shall not permit the Core Leverage Ratio as of the end "
            "of each fiscal quarter (i) ending on June 30, 2023 to exceed "
            "4.00 to 1.00, (ii) ending on September 30, 2023 to exceed 4.25 "
            "to 1.00, and (ii) for any quarter ending thereafter, to exceed "
            "3.50 to 1.00."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins, citation_document="Amendment No. 3")
    assert len(result.mutations) == 1
    assert len(result.unresolved) == 0
    mut = result.mutations[0]
    assert mut.commitment_id == "financial_covenant.leverage_ratio"
    assert mut.field == "applicability"
    assert mut.operation == InstructionType.REPLACE_VALUE
    assert mut.unit == "ratio"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None
    assert mut.confidence == 0.95
    assert mut.citation_document == "Amendment No. 3"
    assert mut.citation_section == "Section 7.10"
    sched = mut.new_value
    assert len(sched["step_down_schedule"]) == 2
    assert sched["steady_state_threshold"] == 3.50


def test_rule_leverage_ratio_does_not_fire_on_wrong_section():
    """Section 7.04 instruction with 7.10 text in source window does NOT map."""
    parser_ins = AmendmentInstruction(
        order=4,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 7.04(c)(xiii)",
        source_text=(
            "Section 7.04(c)(xiii) is hereby amended to replace the term "
            "Net Cash Proceeds. (h) Section 7.10 of the Credit Agreement is "
            "hereby amended by deleting paragraph (a) in its entirety and "
            "replacing it with the following: (a) Total Funded Debt to EBITDA "
            "Ratio. The Loan Parties shall not permit the Core Leverage Ratio "
            "as of the end of each fiscal quarter (i) ending on December 31, "
            "2023 to exceed 3.75 to 1.00."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    # Must NOT map to leverage ratio — the instruction is for Section 7.04,
    # not Section 7.10.  The 7.10 text is noise in the source window.
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.UNKNOWN_COMMITMENT


def test_rule_leverage_ratio_ambiguous_value_on_unparseable_text():
    """Section 7.10 with unparseable schedule → AMBIGUOUS_VALUE, not mapped."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 7.10",
        source_text="Total Funded Debt to EBITDA Ratio. Some unparseable text.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    mut = result.unresolved[0]
    assert mut.commitment_id == "financial_covenant.leverage_ratio"
    assert mut.ambiguity_reason == AmbiguityReason.AMBIGUOUS_VALUE


# ---------------------------------------------------------------------------
# Rule tests — junior credit agreement
# ---------------------------------------------------------------------------


def test_rule_junior_credit_agreement_maps_a3_instruction():
    """A3 Section 7.01 instruction with Junior Credit Agreement maps to ADD."""
    parser_ins = AmendmentInstruction(
        order=2,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.01",
        source_text=(
            "Paragraph (a) of Section 7.01 of the Credit Agreement is hereby "
            "amended by adding the following new subclause (xi) immediately "
            "after subclause (x) and redesignating subclauses (xi) and (xii) "
            "as subclauses (xii) and (xiii) of such paragraph (a), "
            "respectively: (xi) Indebtedness of the Loan Parties under the "
            "Junior Credit Agreement in an aggregate amount not to exceed "
            "$150,000,000 plus any amount of interest added to the principal "
            "amount of such Indebtedness."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins, citation_document="Amendment No. 6")
    assert len(result.mutations) == 1
    assert len(result.unresolved) == 0
    mut = result.mutations[0]
    assert mut.commitment_id == "facility.junior_credit_agreement"
    assert mut.field == "amount"
    assert mut.operation == InstructionType.ADD
    assert mut.unit == "usd"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None
    assert mut.confidence == 0.90
    payload = mut.new_value
    assert payload["canonical_key"] == "facility.junior_credit_agreement"
    assert payload["threshold"] == 150_000_000
    assert payload["unit"] == "usd"


def test_rule_junior_credit_agreement_no_amount_is_ambiguous():
    """Section 7.01 with Junior Credit Agreement but no dollar amount → AMBIGUOUS_VALUE."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.01",
        source_text="Junior Credit Agreement provisions without a dollar amount.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.AMBIGUOUS_VALUE


# ---------------------------------------------------------------------------
# Default UNRESOLVED tests
# ---------------------------------------------------------------------------


def test_unknown_section_is_unresolved_unknown_commitment():
    """An instruction for an unmapped section → UNRESOLVED / UNKNOWN_COMMITMENT."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 2.12",
        source_text="Some repayment installment changes.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    mut = result.unresolved[0]
    assert mut.ambiguity_reason == AmbiguityReason.UNKNOWN_COMMITMENT
    assert mut.commitment_id is None
    assert mut.provenance == InstructionProvenance.MANUAL


def test_no_section_ref_is_unresolved():
    """An instruction with no section_ref → UNRESOLVED / UNKNOWN_COMMITMENT."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref=None,
        source_text="some text",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.UNKNOWN_COMMITMENT


# ---------------------------------------------------------------------------
# Safety test — no false positives
# ---------------------------------------------------------------------------


def test_mapper_never_provides_best_guess():
    """A bad automatic mapping is worse than unresolved.  Verify the mapper
    never produces a mapped mutation when it should be unresolved."""
    # Section 7.10 but without the identifying text → should NOT map
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 7.10",
        source_text="Some random text without ratio or EBITDA mentions.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1


# ---------------------------------------------------------------------------
# Gold-mapping tests — mapper output vs gold for real EDGAR parser output
# ---------------------------------------------------------------------------


def _load_parser_instructions(chain_dir: str, filename: str) -> list[AmendmentInstruction]:
    """Load real parser instructions from a .v04.json file."""
    path = Path("data/edgar_chains") / chain_dir / filename
    if not path.exists():
        pytest.skip(f"Parser output file not found: {path}")
    with open(path) as f:
        data = json.load(f)
    instructions = []
    for i, raw in enumerate(data["instructions"]):
        instructions.append(AmendmentInstruction(
            order=i + 1,
            instruction_type=InstructionType(raw["instruction_type"]),
            target_section_ref=raw.get("target_section_ref"),
            source_text=raw.get("source_text"),
            old_value=raw.get("old_value"),
            new_value=raw.get("new_value"),
            provenance=InstructionProvenance.PARSER,
        ))
    return instructions


def _compare_mutation(actual: StructuredMutation, gold: StructuredMutation, context: str):
    """Compare an actual mutation to a gold mutation."""
    if gold.ambiguity_reason is not None:
        # Gold expects UNRESOLVED
        assert actual.ambiguity_reason is not None, \
            f"{context}: expected UNRESOLVED, got mapped"
        assert actual.ambiguity_reason == gold.ambiguity_reason, \
            f"{context}: expected {gold.ambiguity_reason}, got {actual.ambiguity_reason}"
        assert actual.provenance == InstructionProvenance.MANUAL, \
            f"{context}: UNRESOLVED should have MANUAL provenance"
    else:
        # Gold expects MAPPED
        assert actual.ambiguity_reason is None, \
            f"{context}: expected MAPPED, got UNRESOLVED ({actual.ambiguity_reason})"
        assert actual.commitment_id == gold.commitment_id, \
            f"{context}: commitment_id {actual.commitment_id} != {gold.commitment_id}"
        assert actual.field == gold.field, \
            f"{context}: field {actual.field} != {gold.field}"
        assert actual.operation == gold.operation, \
            f"{context}: operation {actual.operation} != {gold.operation}"
        assert actual.provenance == InstructionProvenance.SEMANTIC_MAPPER, \
            f"{context}: mapped should have SEMANTIC_MAPPER provenance"
        # Compare new_value
        assert actual.new_value == gold.new_value, \
            f"{context}: new_value {actual.new_value} != {gold.new_value}"


def test_gold_ameresco_a1_mapping():
    """Mapper output matches gold for Ameresco A1."""
    instructions = _load_parser_instructions("ameresco", "A1_amend_2023_08.v04.json")
    gold = gold_ameresco_a1()
    assert len(instructions) == len(gold), \
        f"Expected {len(gold)} instructions, got {len(instructions)}"
    for i, (gold_idx, gold_mut) in enumerate(gold):
        result = map_instruction(instructions[i], citation_document="Amendment No. 3")
        if gold_mut.ambiguity_reason is None:
            actual = result.mutations[0]
        else:
            actual = result.unresolved[0]
        _compare_mutation(actual, gold_mut, f"A1 ins {i}")


def test_gold_ameresco_a2_mapping():
    """Mapper output matches gold for Ameresco A2 (all UNRESOLVED)."""
    instructions = _load_parser_instructions("ameresco", "A2_amend_2023_12.v04.json")
    gold = gold_ameresco_a2()
    assert len(instructions) == len(gold)
    for i, (gold_idx, gold_mut) in enumerate(gold):
        result = map_instruction(instructions[i], citation_document="Amendment No. 4")
        actual = result.unresolved[0]
        _compare_mutation(actual, gold_mut, f"A2 ins {i}")


def test_gold_ameresco_a3_mapping():
    """Mapper output matches gold for Ameresco A3."""
    instructions = _load_parser_instructions("ameresco", "A3_sixth_amend_2024.v04.json")
    gold = gold_ameresco_a3()
    assert len(instructions) == len(gold)
    for i, (gold_idx, gold_mut) in enumerate(gold):
        result = map_instruction(instructions[i], citation_document="Amendment No. 6")
        if gold_mut.ambiguity_reason is None:
            actual = result.mutations[0]
        else:
            actual = result.unresolved[0]
        _compare_mutation(actual, gold_mut, f"A3 ins {i}")


def test_gold_all_chains_summary():
    """Verify gold mapping registry has all 3 chains."""
    all_gold = all_gold_mappings()
    assert "EDGAR-AMERESCO" in all_gold
    assert "EDGAR-AMEDISYS" in all_gold
    assert "EDGAR-BAUSCH-LOMB" in all_gold
    # Ameresco has 3 amendments with gold mappings
    assert len(all_gold["EDGAR-AMERESCO"]) == 3
    # Amedisys and Bausch & Lomb have empty gold (parser finds 0)
    for amend in all_gold["EDGAR-AMEDISYS"].values():
        assert amend == []
    for amend in all_gold["EDGAR-BAUSCH-LOMB"].values():
        assert amend == []
