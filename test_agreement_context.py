"""Tests for Step 22D agreement context and 22E registry expansion."""
from __future__ import annotations

from agreement_context import (
    AgreementContext,
    build_agreement_context,
    resolve_with_context,
)
from commitment_registry import (
    resolve_commitment_from_text,
    resolve_commitment_from_section,
    get_aliases_for_class,
)
from models import AmendmentInstruction, CommitmentState, InstructionProvenance, InstructionType


def _make_state():
    return {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            threshold=4.0,
            unit="ratio",
            status="ACTIVE",
        ),
        "financial_covenant.tangible_net_worth": CommitmentState(
            canonical_key="financial_covenant.tangible_net_worth",
            commitment_type="financial_covenant",
            threshold=1000000.0,
            unit="usd",
            status="ACTIVE",
        ),
    }


def test_build_context_extracts_section_headings():
    """Context should extract section headings from source text."""
    text = (
        "Section 7.10 Financial Covenants\n"
        "The Borrower shall maintain...\n"
        "Section 7.11 Leverage Ratio\n"
        "The Borrower will not permit..."
    )
    ctx = build_agreement_context(text, {}, section_ref="Section 7.10")
    assert "7.10" in ctx.section_headings
    assert "7.11" in ctx.section_headings
    assert "Financial Covenants" in ctx.section_headings["7.10"]


def test_build_context_extracts_defined_terms():
    """Context should extract defined terms from source text."""
    text = (
        '"Leverage Ratio" means the ratio of Total Debt to EBITDA. '
        '"Current Ratio" means current assets divided by current liabilities.'
    )
    ctx = build_agreement_context(text, {})
    assert "Leverage Ratio" in ctx.defined_terms
    assert "Current Ratio" in ctx.defined_terms


def test_build_context_resolves_section_commitments():
    """Context should resolve section → commitment candidates."""
    text = "Section 7.10 Financial Covenants\nThe Borrower shall maintain..."
    ctx = build_agreement_context(text, {}, section_ref="Section 7.10")
    # Section 7.10 should map to leverage_ratio
    assert "7.10" in ctx.section_commitments
    assert "financial_covenant.leverage_ratio" in ctx.section_commitments["7.10"]


def test_build_context_captures_state_keys():
    """Context should capture current state keys."""
    state = _make_state()
    ctx = build_agreement_context("", state)
    assert "financial_covenant.leverage_ratio" in ctx.current_state_keys
    assert "financial_covenant.tangible_net_worth" in ctx.current_state_keys


def test_resolve_with_context_alias_match():
    """Resolve via alias match in source text."""
    state = _make_state()
    ctx = build_agreement_context("", state)
    ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_section_ref="Section 7.10",
        source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
        provenance=InstructionProvenance.PARSER,
    )
    cid, field, conf = resolve_with_context(ins, state, ctx)
    assert cid == "financial_covenant.leverage_ratio"
    assert conf > 0.5


def test_resolve_with_context_section_mapping():
    """Resolve via context section → commitment mapping."""
    state = _make_state()
    text = "Section 7.10 Financial Covenants\nThe Borrower shall maintain..."
    ctx = build_agreement_context(text, state, section_ref="Section 7.10")
    # An instruction with no alias match but a section that maps to a
    # commitment in state
    ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.RESTATE_SECTION,
        target_section_ref="Section 7.10",
        source_text="The section is hereby amended to read as follows",
        provenance=InstructionProvenance.PARSER,
    )
    cid, field, conf = resolve_with_context(ins, state, ctx)
    assert cid == "financial_covenant.leverage_ratio"


# --- Step 22E: Registry expansion tests ---


def test_registry_minimum_tangible_net_worth():
    """Minimum Tangible Net Worth should resolve to tangible_net_worth."""
    cid, field, _ = resolve_commitment_from_text(
        "Minimum Tangible Net Worth of not less than $50,000,000",
    )
    assert cid == "financial_covenant.tangible_net_worth"


def test_registry_funded_debt_to_ebitda():
    """Funded Debt to EBITDA should resolve to leverage_ratio."""
    cid, field, _ = resolve_commitment_from_text(
        "Funded Debt to EBITDA ratio shall not exceed 4.00",
    )
    assert cid == "financial_covenant.leverage_ratio"


def test_registry_net_leverage_ratio():
    """Net Leverage Ratio should resolve to leverage_ratio."""
    cid, field, _ = resolve_commitment_from_text(
        "Net Leverage Ratio shall not exceed 3.50 to 1.00",
    )
    assert cid == "financial_covenant.leverage_ratio"


def test_registry_first_lien_leverage_ratio():
    """First Lien Leverage Ratio should resolve to leverage_ratio."""
    cid, field, _ = resolve_commitment_from_text(
        "First Lien Leverage Ratio shall not exceed 3.00 to 1.00",
    )
    assert cid == "financial_covenant.leverage_ratio"


def test_registry_secured_leverage_ratio():
    """Secured Leverage Ratio should resolve to leverage_ratio."""
    cid, field, _ = resolve_commitment_from_text(
        "Secured Leverage Ratio shall not exceed 3.00 to 1.00",
    )
    assert cid == "financial_covenant.leverage_ratio"


def test_registry_asset_coverage_ratio():
    """Asset Coverage Ratio should resolve to debt_service_coverage."""
    cid, field, _ = resolve_commitment_from_text(
        "Asset Coverage Ratio shall not be less than 1.50",
    )
    assert cid == "financial_covenant.debt_service_coverage"


def test_registry_minimum_working_capital():
    """Minimum Working Capital should resolve to current_ratio."""
    cid, field, _ = resolve_commitment_from_text(
        "Minimum Working Capital not less than $10,000,000",
    )
    assert cid == "financial_covenant.current_ratio"


def test_registry_minimum_shareholders_equity():
    """Minimum Shareholders' Equity should resolve to tangible_net_worth."""
    cid, field, _ = resolve_commitment_from_text(
        "Minimum Shareholders' Equity of not less than $100,000,000",
    )
    assert cid == "financial_covenant.tangible_net_worth"


def test_registry_section_6_01():
    """Section 6.01 should resolve to revolving_facility."""
    cid = resolve_commitment_from_section("Section 6.01")
    assert cid == "facility.revolving_facility"


def test_registry_section_6_02():
    """Section 6.02 should resolve to term_loan."""
    cid = resolve_commitment_from_section("Section 6.02")
    assert cid == "facility.term_loan"


def test_registry_priority_ordering_preserved():
    """Specific patterns should still match before generic ones."""
    # 'Maximum Total Leverage Ratio' (priority 5) should match before
    # generic 'Leverage Ratio' (priority 50)
    cid, field, _ = resolve_commitment_from_text(
        "Maximum Total Leverage Ratio shall not exceed 4.00 to 1.00",
    )
    assert cid == "financial_covenant.leverage_ratio"

    # 'Tier 1 Leverage Ratio' (priority 5) should match before
    # generic 'Leverage Ratio' (priority 50)
    cid, _, _ = resolve_commitment_from_text(
        "Tier 1 Leverage Ratio shall not be less than 5.00%",
    )
    assert cid == "financial_covenant.tier_1_leverage_ratio"
