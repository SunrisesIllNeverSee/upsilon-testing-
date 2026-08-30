"""Tests for real EDGAR issuer chains.

These tests verify that the real EDGAR chain fixtures are well-formed
and that the reconstruction pipeline produces correct results on real
SEC filing data.

Distinct from test_chain_reconstruction.py which tests synthetic oracle
chains.  These tests use real EDGAR chains from edgar_chains.py.
"""
from __future__ import annotations

from chain_reconstruction import reconstruct_chain
from edgar_chains import all_edgar_chains, chain_ameresco, chain_amedisys, chain_bausch_lomb


def test_all_edgar_chains_returns_three():
    """The real EDGAR smoke test has exactly 3 issuer chains."""
    chains = all_edgar_chains()
    assert len(chains) == 3


def test_edgar_chain_ids_are_distinct():
    """Each EDGAR chain has a unique chain_id."""
    chains = all_edgar_chains()
    ids = [c.chain_id for c in chains]
    assert len(ids) == len(set(ids))


def test_edgar_chains_have_ground_truth():
    """Each EDGAR chain has independently extracted ground truth."""
    for chain in all_edgar_chains():
        assert chain.ground_truth_state is not None, f"{chain.chain_id} missing ground truth"
        assert chain.ground_truth_label is not None, f"{chain.chain_id} missing ground truth label"
        assert "EDGAR" not in chain.ground_truth_label or "independently" in chain.ground_truth_label.lower() or "extracted" in chain.ground_truth_label.lower(), \
            f"{chain.chain_id} ground truth label should mention independent extraction"


def test_edgar_chains_have_comparison_at():
    """Each EDGAR chain has an explicit comparison_at timestamp."""
    for chain in all_edgar_chains():
        assert chain.comparison_at is not None, f"{chain.chain_id} missing comparison_at"


def test_ameresco_chain_structure():
    """Ameresco chain has S0 + 3 amendments with incremental changes."""
    chain = chain_ameresco()
    assert chain.chain_id == "EDGAR-AMERESCO"
    assert len(chain.amendments) == 3
    assert len(chain.original_state) == 2  # leverage_ratio + debt_service_coverage

    # A1 and A2 change the leverage ratio applicability (step-down schedule)
    a1_instructions = chain.amendments[0].instructions
    assert len(a1_instructions) == 1
    assert a1_instructions[0].target_key == "financial_covenant.leverage_ratio"
    assert a1_instructions[0].field == "applicability"

    a2_instructions = chain.amendments[1].instructions
    assert len(a2_instructions) == 1
    assert a2_instructions[0].target_key == "financial_covenant.leverage_ratio"
    assert a2_instructions[0].field == "applicability"

    # A3 adds the Junior Credit Agreement (does not change 7.10)
    a3_instructions = chain.amendments[2].instructions
    assert len(a3_instructions) == 1
    assert a3_instructions[0].target_key == "facility.junior_credit_agreement"


def test_amedisys_chain_structure():
    """Amedisys chain has S0 + 2 full restatement amendments."""
    chain = chain_amedisys()
    assert chain.chain_id == "EDGAR-AMEDISYS"
    assert len(chain.amendments) == 2
    assert len(chain.original_state) == 2  # leverage_ratio + fixed_charge_coverage

    # Full restatement amendments have no commitment-level instructions
    # (covenants persist through restatement)
    for i, step in enumerate(chain.amendments, 1):
        assert len(step.instructions) == 0, f"A{i} should have 0 commitment-level instructions"


def test_bausch_lomb_chain_structure():
    """Bausch & Lomb chain has S0 + 4 conformed copy amendments."""
    chain = chain_bausch_lomb()
    assert chain.chain_id == "EDGAR-BAUSCH-LOMB"
    assert len(chain.amendments) == 4
    assert len(chain.original_state) == 2  # leverage_ratio + term_loan_b

    # A1 and A2 add new term loan facilities
    a1 = chain.amendments[0].instructions
    assert len(a1) == 1
    assert a1[0].target_key == "facility.first_incremental_term_loan"

    a2 = chain.amendments[1].instructions
    assert len(a2) == 1
    assert a2[0].target_key == "facility.second_incremental_term_loan"

    # A3 replaces term_loan_b threshold
    a3 = chain.amendments[2].instructions
    assert len(a3) == 1
    assert a3[0].target_key == "facility.term_loan_b"
    assert a3[0].field == "threshold"

    # A4 is a no-op for commitment state (interest rate change only)
    a4 = chain.amendments[3].instructions
    assert len(a4) == 0


def test_ameresco_reconstruction_passes():
    """Ameresco chain reconstruction passes all four questions."""
    result = reconstruct_chain(chain_ameresco())
    assert all(result.questions[k]["pass"] for k in (
        "Q1_state_preservation",
        "Q2_lineage_completeness",
        "Q3_unresolved_blocks_promotion",
        "Q4_ground_truth_match",
    )), f"Ameresco failed: {[(k, r['summary']) for k, r in result.questions.items() if not r['pass']]}"


def test_amedisys_reconstruction_passes():
    """Amedisys chain reconstruction passes all four questions."""
    result = reconstruct_chain(chain_amedisys())
    assert all(result.questions[k]["pass"] for k in (
        "Q1_state_preservation",
        "Q2_lineage_completeness",
        "Q3_unresolved_blocks_promotion",
        "Q4_ground_truth_match",
    )), f"Amedisys failed: {[(k, r['summary']) for k, r in result.questions.items() if not r['pass']]}"


def test_bausch_lomb_reconstruction_passes():
    """Bausch & Lomb chain reconstruction passes all four questions."""
    result = reconstruct_chain(chain_bausch_lomb())
    assert all(result.questions[k]["pass"] for k in (
        "Q1_state_preservation",
        "Q2_lineage_completeness",
        "Q3_unresolved_blocks_promotion",
        "Q4_ground_truth_match",
    )), f"Bausch & Lomb failed: {[(k, r['summary']) for k, r in result.questions.items() if not r['pass']]}"


def test_ameresco_leverage_ratio_threshold_preserved():
    """Ameresco: leverage ratio steady-state threshold remains 3.50 throughout."""
    result = reconstruct_chain(chain_ameresco())
    leverage = result.final_state.get("financial_covenant.leverage_ratio")
    assert leverage is not None
    assert leverage.threshold == 3.50  # steady-state unchanged


def test_ameresco_leverage_ratio_applicability_changed():
    """Ameresco: leverage ratio applicability (step-down schedule) changes across amendments."""
    result = reconstruct_chain(chain_ameresco())
    leverage = result.final_state.get("financial_covenant.leverage_ratio")
    assert leverage is not None
    # After A2, the step-down schedule should have Q4 2023: 3.75
    schedule = leverage.applicability.get("step_down_schedule", [])
    assert any(s["period_end"] == "2023-12-31" and s["threshold"] == 3.75 for s in schedule), \
        f"Expected Q4 2023 threshold 3.75, got {schedule}"


def test_ameresco_junior_credit_agreement_added():
    """Ameresco: A3 adds the Junior Credit Agreement ($150M)."""
    result = reconstruct_chain(chain_ameresco())
    junior = result.final_state.get("facility.junior_credit_agreement")
    assert junior is not None
    assert junior.threshold == 150_000_000


def test_bausch_lomb_term_loan_b_refinanced():
    """Bausch & Lomb: A3 refinances term_loan_b from $2.5B to $2.8B."""
    result = reconstruct_chain(chain_bausch_lomb())
    term_loan = result.final_state.get("facility.term_loan_b")
    assert term_loan is not None
    assert term_loan.threshold == 2_802_125_000


def test_bausch_lomb_incremental_loans_added():
    """Bausch & Lomb: A1 and A2 add incremental term loan facilities."""
    result = reconstruct_chain(chain_bausch_lomb())
    assert "facility.first_incremental_term_loan" in result.final_state
    assert "facility.second_incremental_term_loan" in result.final_state
    assert result.final_state["facility.first_incremental_term_loan"].threshold == 750_000_000
    assert result.final_state["facility.second_incremental_term_loan"].threshold == 500_000_000
