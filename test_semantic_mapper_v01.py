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
    StructuredMutation,
    _extract_dollar_amount,
    _extract_maturity_date,
    _extract_percentage,
    _extract_step_down_schedule,
    _parse_date,
    _section_to_commitment_id,
    is_implemented,
    map_instruction,
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


def test_extract_maturity_date_standard():
    """Maturity Date extraction with nearby date."""
    assert _extract_maturity_date(
        'Maturity Date is hereby amended to mean "June 30, 2025".'
    ) == "2025-06-30"
    assert _extract_maturity_date(
        "The Maturity Date shall be extended to December 31, 2025."
    ) == "2025-12-31"


def test_extract_maturity_date_no_keyword():
    """No 'Maturity Date' keyword → None."""
    assert _extract_maturity_date("The effective date is June 30, 2025.") is None


def test_extract_maturity_date_no_date_nearby():
    """Maturity Date mentioned but no date within 80 chars → None."""
    assert _extract_maturity_date(
        "The Maturity Date is hereby amended as set forth in Annex A "
        "which is attached hereto and incorporated by reference. "
        "The date of the agreement is June 30, 2025."
    ) is None


def test_extract_maturity_date_returns_new_not_old():
    """When both old and new dates appear, the NEW date is returned.

    Regression test: the old implementation returned the first date
    near the keyword, which was the OLD value.  Amendment text like
    "The Maturity Date of June 30, 2024 is hereby extended to
    December 31, 2025" must yield 2025-12-31 (the new date), not
    2024-06-30 (the old date).
    """
    assert _extract_maturity_date(
        "The Maturity Date of June 30, 2024 is hereby extended to "
        "December 31, 2025."
    ) == "2025-12-31"


def test_extract_maturity_date_multiple_dates_no_amend_lang_is_ambiguous():
    """Multiple dates near 'Maturity Date' without amendment language → None.

    Without amendment verbs (amended to mean, extended to, etc.) we
    cannot determine which date is the new value, so the extraction
    must return None rather than guessing.
    """
    assert _extract_maturity_date(
        "The Maturity Date is June 30, 2024 and also December 31, 2025."
    ) is None


def test_extract_maturity_date_single_date_no_amend_lang():
    """A single date near 'Maturity Date' with no amendment language maps.

    When only one date appears near the keyword, it must be the new
    value (there is no old value stated to confuse the extraction).
    """
    assert _extract_maturity_date(
        "The Maturity Date is June 30, 2025."
    ) == "2025-06-30"


def test_extract_percentage_standard():
    """Percentage extraction."""
    assert _extract_percentage("2.50%") == 2.50
    assert _extract_percentage("amended to 1.75% per annum") == 1.75
    assert _extract_percentage("no percentage here") is None


def test_extract_percentage_returns_new_not_old():
    """When both old and new percentages appear, the NEW value is returned.

    Regression test: the old implementation returned the first
    percentage in the text, which was the OLD rate.  Amendment text
    like "The Applicable Rate of 3.00% is hereby amended to 2.50%"
    must yield 2.50 (the new rate), not 3.00 (the old rate).
    """
    assert _extract_percentage(
        "The Applicable Rate of 3.00% is hereby amended to 2.50% per annum."
    ) == 2.50


def test_extract_percentage_multiple_no_amend_lang_is_ambiguous():
    """Multiple percentages without amendment language → None.

    Without amendment verbs (amended to, to mean, set at, etc.) we
    cannot determine which percentage is the new value, so the
    extraction must return None rather than guessing.
    """
    assert _extract_percentage(
        "The rate is 3.00% and the margin is 2.50%."
    ) is None


def test_section_to_commitment_id_known():
    """Known sections map to commitment IDs."""
    assert _section_to_commitment_id("Section 7.10") == "financial_covenant.leverage_ratio"
    assert _section_to_commitment_id("Section 7.01") == "facility.credit_agreement"
    assert _section_to_commitment_id("section 7.10(a)") == "financial_covenant.leverage_ratio"


def test_section_to_commitment_id_unknown():
    """Unknown sections return None."""
    assert _section_to_commitment_id("Section 99.99") is None
    assert _section_to_commitment_id("") is None
    assert _section_to_commitment_id(None) is None


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
# Rule tests — maturity date replacement
# ---------------------------------------------------------------------------


def test_rule_maturity_date_maps_explicit_amendment():
    """An explicit Maturity Date amendment with a parseable date maps."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            'The definition of "Maturity Date" is hereby amended to mean '
            '"June 30, 2025."'
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.commitment_id == "facility.credit_agreement"
    assert mut.field == "deadline"
    assert mut.operation == InstructionType.REPLACE_VALUE
    assert mut.new_value == "2025-06-30"
    assert mut.unit == "date"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None


def test_rule_maturity_date_extended_to():
    """Maturity Date extended to a new date maps correctly."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            "The Maturity Date shall be extended to December 31, 2025."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    assert result.mutations[0].new_value == "2025-12-31"


def test_rule_maturity_date_no_date_is_ambiguous():
    """Maturity Date mentioned but no parseable date nearby → AMBIGUOUS_VALUE."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text="The Maturity Date is hereby amended as set forth in Annex A.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.AMBIGUOUS_VALUE


def test_rule_maturity_date_does_not_fire_without_keyword():
    """Text with a date but no 'Maturity Date' keyword does not trigger the rule."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text="The effective date is June 30, 2025.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    # Should not map to maturity date
    assert not any(
        m.commitment_id == "facility.credit_agreement" and m.field == "deadline"
        for m in result.mutations
    )


# ---------------------------------------------------------------------------
# Step 17B regression: maturity-date rule must not fire on non-replacement
# instruction types (RESTATE_SECTION / DELETE).  These produce confident
# mutations targeting facility.credit_agreement which does not exist in any
# chain's state, causing silent corruption (wrong + confident).
# ---------------------------------------------------------------------------


def test_regression_maturity_date_does_not_fire_on_restate_section():
    """RESTATE_SECTION containing 'Maturity Date' must NOT produce a
    confident mapped mutation.

    Reproduces STUDY-007 A1 ins 4/5: the parser groups multiple definition
    amendments (FATCA, Maturity Date, Other Taxes) into one RESTATE_SECTION.
    The mapper fires _rule_maturity_date_replacement on the Maturity Date
    mention, producing a confident REPLACE_VALUE targeting
    facility.credit_agreement — a key that does not exist in the chain's
    state.  The executor rejects it as an incorrect automatic mutation.
    """
    parser_ins = AmendmentInstruction(
        order=4,
        instruction_type=InstructionType.RESTATE_SECTION,
        target_section_ref="Section 1.1",
        source_text=(
            'The definition of FATCA set forth in Section 1.1 of the Credit '
            "Agreement is hereby amended and restated in its entirety to read "
            'as follows: "FATCA" shall mean Sections 1471 through 1474 of the '
            "Code. The definition of Maturity Date set forth in Section 1.1 of "
            "the Credit Agreement is hereby amended and restated in its entirety "
            'to read as follows: "Maturity Date" shall mean the date that is '
            "the earlier of (i) February 12, 2021 and (ii) the date that is six "
            "months prior to the maturity date of the Second Lien Notes."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    # Must NOT produce a confident mapped mutation
    assert len(result.mutations) == 0
    # Must be UNRESOLVED
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason is not None


def test_regression_maturity_date_does_not_fire_on_delete():
    """DELETE containing 'Maturity Date' must NOT produce a confident
    mapped mutation.

    Reproduces STUDY-022 A3 ins 2: the parser produces a DELETE instruction
    whose source text mentions 'Revolving Credit Maturity Date' as a defined
    term (not an amendment to the maturity date).  The mapper fires
    _rule_maturity_date_replacement, producing a confident REPLACE_VALUE
    targeting facility.credit_agreement — a key that does not exist in the
    chain's state.  The executor rejects it as an incorrect automatic
    mutation.
    """
    parser_ins = AmendmentInstruction(
        order=2,
        instruction_type=InstructionType.DELETE,
        target_section_ref="Section 2.5",
        source_text=(
            "in the event that a Replacement Rate with respect to LIBOR is "
            "implemented then all references herein to LIBOR shall be deemed "
            'references to such Replacement Rate. "Revolving Credit Maturity '
            'Date" means the earliest to occur of (a) November 30, 2023 (b) '
            "the date of termination of the entire Revolving Credit Commitment "
            "by the Borrower pursuant to Section 2.5."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    # Must NOT produce a confident mapped mutation
    assert len(result.mutations) == 0
    # Must be UNRESOLVED
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason is not None


# ---------------------------------------------------------------------------
# Rule tests — rate / percentage replacement
# ---------------------------------------------------------------------------


def test_rule_rate_percentage_maps_applicable_rate():
    """An explicit Applicable Rate change with a percentage maps."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            'The definition of "Applicable Rate" is hereby amended to '
            "mean 2.50% per annum."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.commitment_id == "facility.credit_agreement"
    assert mut.field == "rate"
    assert mut.operation == InstructionType.REPLACE_VALUE
    assert mut.new_value == 2.50
    assert mut.unit == "percent"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None


def test_rule_rate_percentage_maps_applicable_margin():
    """An explicit Applicable Margin change with a percentage maps."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 2.03",
        source_text=(
            'The "Applicable Margin" for Term Loans is hereby amended to 1.75%.'
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    assert result.mutations[0].new_value == 1.75


def test_rule_rate_percentage_no_percentage_is_ambiguous():
    """Applicable Rate mentioned but no percentage → AMBIGUOUS_VALUE."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text="The Applicable Rate shall be determined per Annex A.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.AMBIGUOUS_VALUE


# ---------------------------------------------------------------------------
# Rule tests — exception add / remove
# ---------------------------------------------------------------------------


def test_rule_exception_add_maps_notwithstanding():
    """An ADD with 'notwithstanding' language on a known section maps."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.10",
        source_text=(
            "Notwithstanding the foregoing, the Borrower may permit "
            "Indebtedness under the Junior Credit Agreement up to $50,000,000."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.commitment_id == "financial_covenant.leverage_ratio"
    assert mut.field == "exceptions"
    assert mut.operation == InstructionType.ADD
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None
    assert "Notwithstanding" in mut.new_value


def test_rule_exception_delete_maps_except_that():
    """A DELETE with 'except that' language on a known section maps."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.DELETE,
        target_section_ref="Section 7.10",
        source_text=(
            "The Borrower shall not permit any liens except that liens "
            "securing the Junior Credit Agreement shall no longer be permitted."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.commitment_id == "financial_covenant.leverage_ratio"
    assert mut.field == "exceptions"
    assert mut.operation == InstructionType.DELETE
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None


def test_rule_exception_unknown_section_returns_none():
    """An exception instruction on an unmapped section falls through to UNKNOWN_COMMITMENT."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 99.99",
        source_text="Notwithstanding anything herein, the Borrower may do X.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.UNKNOWN_COMMITMENT


def test_rule_exception_no_carveout_language_does_not_fire():
    """An ADD on a known section without exception language does not trigger the rule."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.10",
        source_text="The Borrower shall maintain a minimum liquidity of $10,000,000.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    # Should not map as an exception — no notwithstanding/except language
    assert not any(
        m.field == "exceptions" for m in result.mutations
    )


# ---------------------------------------------------------------------------
# Rule tests — party change
# ---------------------------------------------------------------------------


def test_rule_party_change_add_guarantor():
    """An explicit 'shall become a party' + Guarantor maps to party ADD."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 6.01",
        source_text=(
            "Each Subsidiary of the Borrower shall become a party to "
            "this Agreement as a Guarantor."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.commitment_id == "facility.credit_agreement"
    assert mut.field == "party"
    assert mut.operation == InstructionType.ADD
    assert mut.new_value == "guarantor"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
    assert mut.ambiguity_reason is None


def test_rule_party_change_release_guarantor():
    """An explicit 'is hereby released' + Guarantor maps to party DELETE."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.DELETE,
        target_section_ref="Section 6.01",
        source_text=(
            "Subsidiary X is hereby released as a Guarantor from its "
            "obligations under the Guarantee."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.commitment_id == "facility.credit_agreement"
    assert mut.field == "party"
    assert mut.operation == InstructionType.DELETE
    assert mut.old_value == "guarantor"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER


def test_rule_party_change_no_role_does_not_fire():
    """Party-change language without a role (Guarantor/Borrower/Lender) does not fire."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 6.01",
        source_text="The Company shall become a party to this Agreement.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    # No Guarantor/Borrower/Lender role → should not map as party change
    assert not any(
        m.field == "party" for m in result.mutations
    )


def test_rule_party_change_unknown_section_returns_none():
    """A party change on an unmapped section falls through to UNKNOWN_COMMITMENT."""
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 99.99",
        source_text="New Co shall become a party to this Agreement as a Guarantor.",
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 0
    assert len(result.unresolved) == 1
    assert result.unresolved[0].ambiguity_reason == AmbiguityReason.UNKNOWN_COMMITMENT


def test_rule_party_change_add_not_corrupted_by_release_elsewhere():
    """ADD trigger must not be flipped to DELETE by release language elsewhere.

    Regression test: the old implementation determined the operation
    (ADD vs DELETE) by searching the ENTIRE source text for
    "is hereby released".  If the trigger phrase was "shall become a
    party" (an ADD) but "is hereby released" appeared elsewhere in
    the text, the mapper incorrectly produced a DELETE.  The
    operation must be derived from the trigger phrase that actually
    matched, not from an unrelated phrase elsewhere in the text.
    """
    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 6.01",
        source_text=(
            "Each Subsidiary of the Borrower shall become a party to "
            "this Agreement as a Guarantor. "
            "Note: Subsidiary Y is hereby released as a Guarantor from "
            "a separate agreement."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    # Critical: the operation must be ADD, not DELETE
    assert mut.operation == InstructionType.ADD
    assert mut.new_value == "guarantor"
    assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER


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
# End-to-end mapper → executor integration tests
#
# These tests verify that mapped mutations are actually executable by the
# executor and produce the correct commitment-state changes.  They catch
# mismatches between the mapper's output schema and the executor's input
# expectations (e.g., a field that the mapper sets but CommitmentState
# does not have, or a domain_effect the executor does not handle).
# ---------------------------------------------------------------------------


def _map_and_execute(parser_ins, state):
    """Map a parser instruction and execute the result against the given state.

    Returns the ExecutionResult.  Asserts that the instruction was mapped
    (not unresolved) before executing.
    """
    from executor import execute_amendment

    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1, (
        f"Expected 1 mapped mutation, got {len(result.mutations)} mapped "
        f"and {len(result.unresolved)} unresolved"
    )
    mut = result.mutations[0]
    exec_ins = mut.to_amendment_instruction(order=parser_ins.order)
    return execute_amendment(state, [exec_ins])


def test_e2e_maturity_date_replacement():
    """Maturity date replacement maps and executes end-to-end."""
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            'The definition of "Maturity Date" is hereby amended to mean '
            '"June 30, 2025."'
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            deadline="2024-06-30",
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    assert er.state["facility.credit_agreement"].deadline == "2025-06-30"


def test_e2e_rate_percentage_replacement():
    """Rate/percentage replacement maps and executes end-to-end.

    The mapper produces field='rate', domain_effect=RATE_CHANGE.  The
    executor must update the 'rate' field on CommitmentState.
    """
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            'The definition of "Applicable Rate" is hereby amended to '
            "mean 2.50% per annum."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            rate=1.5,
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    assert er.state["facility.credit_agreement"].rate == 2.5


def test_e2e_exception_add():
    """Exception ADD maps and executes end-to-end."""
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 7.10",
        source_text=(
            "Notwithstanding the foregoing, the Borrower may permit "
            "Indebtedness under the Junior Credit Agreement up to $50,000,000."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            exceptions=[],
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    assert len(er.state["financial_covenant.leverage_ratio"].exceptions) == 1


def test_e2e_exception_delete_unresolved_when_representation_differs():
    """Exception DELETE is UNRESOLVED when the stored representation differs
    from the amendment language and no deterministic normalization proves
    identity.

    This test replaces the previous circular test which extracted the
    exception text from the mapper, placed it into the state, then
    re-ran the mapper and executor — guaranteeing exact-match success
    by construction.  That proved nothing about real-world behavior.

    The replacement uses an INDEPENDENT initial state whose exception
    is stored in a canonical short form ("JCA indebtedness permitted
    up to $50M") that differs from the full amendment-language
    sentence the mapper extracts ("The Borrower shall not permit any
    liens except that liens securing the Junior Credit Agreement shall
    no longer be permitted.").  The executor uses exact-match
    identity for exception removal (no normalization layer exists in
    v0.1), so the DELETE is correctly rejected as UNRESOLVED.

    This is the honest v0.1 behavior: when deterministic normalization
    cannot prove identity, the instruction is UNRESOLVED — never a
    forced exact-match success.
    """
    from models import CommitmentState
    from executor import execute_amendment

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.DELETE,
        target_section_ref="Section 7.10",
        source_text=(
            "The Borrower shall not permit any liens except that liens "
            "securing the Junior Credit Agreement shall no longer be permitted."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    # Independent initial state: exception stored in a canonical short
    # form that does NOT match the amendment-language sentence.
    state = {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            exceptions=["JCA indebtedness permitted up to $50M"],
        )
    }
    result = map_instruction(parser_ins)
    assert len(result.mutations) == 1
    mut = result.mutations[0]
    assert mut.operation == InstructionType.DELETE
    exec_ins = mut.to_amendment_instruction(order=parser_ins.order)
    er = execute_amendment(state, [exec_ins])
    # The executor must reject the DELETE — the stored representation
    # does not match the amendment-language sentence, and v0.1 has no
    # normalization layer to prove identity.
    assert len(er.unresolved) == 1
    assert er.status.value in ("UNRESOLVED", "PARTIAL")
    # The original exception must remain untouched (no silent removal)
    assert er.state["financial_covenant.leverage_ratio"].exceptions == [
        "JCA indebtedness permitted up to $50M"
    ]


def test_e2e_party_add_guarantor():
    """Party ADD (guarantor joins) maps and executes end-to-end.

    The mapper produces operation=ADD, field='party', domain_effect=PARTY_CHANGE.
    The executor must append to the party list, not reject the instruction.
    """
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD,
        target_section_ref="Section 6.01",
        source_text=(
            "Each Subsidiary of the Borrower shall become a party to "
            "this Agreement as a Guarantor."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            party=["borrower"],
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    assert "guarantor" in er.state["facility.credit_agreement"].party
    assert er.state["facility.credit_agreement"].status == "ACTIVE"


def test_e2e_party_delete_guarantor_release():
    """Party DELETE (guarantor release) maps and executes end-to-end.

    The mapper produces operation=DELETE, field='party', domain_effect=PARTY_CHANGE.
    The executor must remove the guarantor from the party list and must NOT
    mark the entire commitment as DELETED.
    """
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.DELETE,
        target_section_ref="Section 6.01",
        source_text=(
            "Subsidiary X is hereby released as a Guarantor from its "
            "obligations under the Guarantee."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            party=["borrower", "guarantor"],
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    # Critical: the guarantor must be removed from the party list
    assert "guarantor" not in er.state["facility.credit_agreement"].party
    # Critical: the commitment itself must NOT be marked DELETED
    assert er.state["facility.credit_agreement"].status == "ACTIVE"


def test_e2e_rate_with_old_and_new_percentage():
    """Rate replacement with both old and new percentages in text.

    Regression test: when the amendment text states both the old and
    new rate (e.g., "The Applicable Rate of 3.00% is hereby amended
    to 2.50%"), the mapper must extract the NEW rate (2.50), not the
    old rate (3.00).  The executor must then update the rate field to
    the new value.
    """
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            "The Applicable Rate of 3.00% is hereby amended to "
            "2.50% per annum."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            rate=3.0,
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    # Critical: the rate must be the NEW value (2.5), not the old (3.0)
    assert er.state["facility.credit_agreement"].rate == 2.5


def test_e2e_maturity_date_with_old_and_new_date():
    """Maturity date replacement with both old and new dates in text.

    Regression test: when the amendment text states both the old and
    new maturity date (e.g., "The Maturity Date of June 30, 2024 is
    hereby extended to December 31, 2025"), the mapper must extract
    the NEW date (2025-12-31), not the old date (2024-06-30).  The
    executor must then update the deadline field to the new value.
    """
    from models import CommitmentState

    parser_ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_TEXT,
        target_section_ref="Section 1.01",
        source_text=(
            "The Maturity Date of June 30, 2024 is hereby extended to "
            "December 31, 2025."
        ),
        provenance=InstructionProvenance.PARSER,
    )
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            deadline="2024-06-30",
        )
    }
    er = _map_and_execute(parser_ins, state)
    assert er.status.value == "COMPLETE"
    assert len(er.unresolved) == 0
    # Critical: the deadline must be the NEW value, not the old
    assert er.state["facility.credit_agreement"].deadline == "2025-12-31"


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
    """Compare an actual mutation to a gold mutation.

    For MAPPED mutations, compares commitment_id, field, operation,
    provenance, new_value, unit, and source_span.  old_value is only
    compared when both gold and actual have a non-None value — the
    mapper cannot always extract old_value from amendment text (e.g.,
    when the amendment says "deleting paragraph (a) in its entirety"
    without stating the old numeric values), so gold may carry the
    known prior state value while the mapper produces None.
    """
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
        # Compare unit if gold specifies it
        if gold.unit is not None:
            assert actual.unit == gold.unit, \
                f"{context}: unit {actual.unit} != {gold.unit}"
        # Compare source_span: the mapper sets source_span to the full
        # parser source_text, which may be longer than the gold's
        # source_span (the gold captures the key amendment language).
        # We verify that the actual source_span contains the gold's
        # key text, rather than requiring an exact match.
        if gold.source_span:
            # Use a representative substring from the gold source_span
            # (the first 60 chars of the core amendment language) to
            # verify the mapper operated on the right text.
            gold_key = gold.source_span[:60]
            assert gold_key in actual.source_span, \
                f"{context}: source_span does not contain gold key text " \
                f"'{gold_key}...'"
        # Compare old_value only when both sides have a value — the
        # mapper may not be able to extract old_value from amendment
        # text, so gold's old_value (known from chain context) may
        # differ from the mapper's None.
        if gold.old_value is not None and actual.old_value is not None:
            assert actual.old_value == gold.old_value, \
                f"{context}: old_value {actual.old_value} != {gold.old_value}"


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
    """Mapper output matches gold for Ameresco A2.

    A2 ins 3 (Section 7.10) is MAPPED → leverage ratio schedule change.
    All other instructions are UNRESOLVED.
    """
    instructions = _load_parser_instructions("ameresco", "A2_amend_2023_12.v04.json")
    gold = gold_ameresco_a2()
    assert len(instructions) == len(gold)
    for i, (gold_idx, gold_mut) in enumerate(gold):
        result = map_instruction(instructions[i], citation_document="Amendment No. 4")
        if gold_mut.ambiguity_reason is None:
            actual = result.mutations[0]
        else:
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
