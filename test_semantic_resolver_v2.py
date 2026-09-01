"""Tests for the semantic resolver v2 (Step 21 / Section C)."""
from __future__ import annotations

from datetime import datetime

import pytest

from models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)
from semantic_resolver_v2 import (
    _extract_dollar_amount,
    _extract_dollar_amount_with_scale,
    _extract_maturity_date,
    _extract_percentage,
    _extract_ratio_threshold,
    _identify_field,
    _identify_operation,
    _normalize_value,
    _value_in_source,
    resolve_instruction,
)


# ---------------------------------------------------------------------------
# Value extraction tests
# ---------------------------------------------------------------------------


class TestValueExtraction:
    def test_extract_ratio_threshold(self):
        assert _extract_ratio_threshold("not to exceed 4.00 to 1.00") == 4.0
        assert _extract_ratio_threshold("shall not exceed 3.50:1.00") == 3.5
        assert _extract_ratio_threshold("not greater than 2.50 to 1.00") == 2.5

    def test_extract_ratio_threshold_no_match(self):
        assert _extract_ratio_threshold("some text without a ratio") is None

    def test_extract_dollar_amount(self):
        assert _extract_dollar_amount("$150,000,000") == 150000000
        assert _extract_dollar_amount("$25,000,000.00") == 25000000

    def test_extract_dollar_amount_no_match(self):
        assert _extract_dollar_amount("no money here") is None

    def test_extract_dollar_amount_with_scale(self):
        assert _extract_dollar_amount_with_scale("$150 million") == 150000000
        assert _extract_dollar_amount_with_scale("$1.5 billion") == 1500000000
        assert _extract_dollar_amount_with_scale("$150,000,000") == 150000000

    def test_extract_percentage(self):
        assert _extract_percentage("amended to 2.50%") == 2.5
        assert _extract_percentage("shall be 10%") == 10.0

    def test_extract_percentage_no_match(self):
        assert _extract_percentage("no percentage here") is None

    def test_extract_maturity_date(self):
        result = _extract_maturity_date(
            'Maturity Date is amended to mean "June 30, 2023"'
        )
        assert result == "2023-06-30"

    def test_extract_maturity_date_no_match(self):
        assert _extract_maturity_date("no date here") is None


# ---------------------------------------------------------------------------
# Field identification tests
# ---------------------------------------------------------------------------


class TestFieldIdentification:
    def test_maturity_date_field(self):
        assert _identify_field(
            InstructionType.RESTATE_SECTION,
            "Maturity Date is amended to mean June 30, 2023",
            "facility.term_loan",
            "threshold",
        ) == "deadline"

    def test_threshold_field_for_ratio(self):
        assert _identify_field(
            InstructionType.RESTATE_SECTION,
            "not to exceed 4.00 to 1.00",
            "financial_covenant.leverage_ratio",
            "threshold",
        ) == "threshold"

    def test_threshold_field_for_dollar(self):
        assert _identify_field(
            InstructionType.RESTATE_SECTION,
            "$150,000,000",
            "facility.term_loan",
            "threshold",
        ) == "threshold"

    def test_threshold_field_for_dollar_covenant(self):
        """Dollar amounts on covenants (e.g., tangible net worth) should
        also resolve to 'threshold'."""
        assert _identify_field(
            InstructionType.RESTATE_SECTION,
            "Tangible Net Worth of not less than $25,000,000",
            "financial_covenant.tangible_net_worth",
            "threshold",
        ) == "threshold"

    def test_rate_field(self):
        assert _identify_field(
            InstructionType.RESTATE_SECTION,
            "applicable rate shall be 2.50%",
            "facility.revolving_facility",
            "threshold",
        ) == "rate"


# ---------------------------------------------------------------------------
# Operation identification tests
# ---------------------------------------------------------------------------


class TestOperationIdentification:
    def test_restate_section_to_replace_value(self):
        assert _identify_operation(
            InstructionType.RESTATE_SECTION, "text", "threshold",
        ) == InstructionType.REPLACE_VALUE

    def test_restate_section_to_add_for_exceptions(self):
        assert _identify_operation(
            InstructionType.RESTATE_SECTION, "text", "exceptions",
        ) == InstructionType.ADD

    def test_list_field_coerced_to_add(self):
        """REPLACE_VALUE on list fields should be coerced to ADD."""
        assert _identify_operation(
            InstructionType.REPLACE_VALUE, "text", "exceptions",
        ) == InstructionType.ADD
        assert _identify_operation(
            InstructionType.REPLACE_TEXT, "text", "party",
        ) == InstructionType.ADD

    def test_non_list_field_preserves_operation(self):
        assert _identify_operation(
            InstructionType.ADD, "text", "threshold",
        ) == InstructionType.ADD


# ---------------------------------------------------------------------------
# Value normalization tests
# ---------------------------------------------------------------------------


class TestValueNormalization:
    def test_normalize_float(self):
        assert _normalize_value(4.0, "ratio", "threshold") == 4.0
        assert _normalize_value(4, "ratio", "threshold") == 4.0

    def test_normalize_string(self):
        assert _normalize_value("2023-06-30", "date", "deadline") == "2023-06-30"

    def test_normalize_none(self):
        assert _normalize_value(None, "ratio", "threshold") is None


# ---------------------------------------------------------------------------
# Value in source tests
# ---------------------------------------------------------------------------


class TestValueInSource:
    def test_float_in_source(self):
        assert _value_in_source(4.0, "not to exceed 4.00 to 1.00")
        assert _value_in_source(3.5, "shall not exceed 3.50:1.00")

    def test_float_not_in_source(self):
        assert not _value_in_source(99.0, "not to exceed 4.00 to 1.00")

    def test_int_in_source(self):
        assert _value_in_source(150000000, "$150,000,000")
        assert not _value_in_source(999, "$150,000,000")

    def test_string_in_source(self):
        assert _value_in_source("2023-06-30", "date is 2023-06-30")
        assert not _value_in_source("2099-12-31", "date is 2023-06-30")

    def test_dict_in_source(self):
        schedule = {"steady_state_threshold": 3.5}
        assert _value_in_source(schedule, "to exceed 3.50 to 1.00")
        assert not _value_in_source(
            {"steady_state_threshold": 99.0}, "to exceed 3.50 to 1.00"
        )


# ---------------------------------------------------------------------------
# Resolver integration tests
# ---------------------------------------------------------------------------


class TestResolverIntegration:
    def _make_state(self) -> dict[str, CommitmentState]:
        return {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }

    def test_resolve_leverage_ratio_replacement(self):
        state = self._make_state()
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_section_ref="Section 7.10",
            source_text="Maximum Total Leverage Ratio shall not exceed 3.50 to 1.00",
            provenance=InstructionProvenance.PARSER,
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 1
        mut = result.mutations[0]
        assert mut.commitment_id == "financial_covenant.leverage_ratio"
        assert mut.field == "threshold"
        assert mut.new_value == 3.5
        assert mut.operation == InstructionType.REPLACE_VALUE

    def test_resolve_unknown_commitment(self):
        state = self._make_state()
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_section_ref="Section 99.99",
            source_text="some text without covenant keywords",
            provenance=InstructionProvenance.PARSER,
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 0
        assert len(result.unresolved) == 1
        assert trace.failed_step == 1

    def test_resolve_delete_is_unresolved(self):
        """DELETE operations should always be UNRESOLVED (conservative)."""
        state = self._make_state()
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.DELETE,
            target_section_ref="Section 7.10",
            source_text="delete the leverage ratio covenant",
            provenance=InstructionProvenance.PARSER,
        )
        result, trace = resolve_instruction(ins, state)
        assert len(result.mutations) == 0
        assert len(result.unresolved) == 1
        assert "delete_requires_manual_review" in trace.failure_reason

    def test_resolve_value_not_in_source(self):
        """When the extracted value doesn't appear in source, should be
        UNRESOLVED."""
        state = self._make_state()
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_section_ref="Section 7.10",
            source_text="Maximum Total Leverage Ratio",
            provenance=InstructionProvenance.PARSER,
        )
        result, trace = resolve_instruction(ins, state)
        # No value extracted → UNRESOLVED
        assert len(result.unresolved) >= 1
