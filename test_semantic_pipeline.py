"""Integration tests for the end-to-end semantic pipeline.

These tests run the full pipeline:
  EDGAR → parser → semantic mapper → executor → state → compare to ground truth

They verify:
  1. The pipeline runs without errors on all 3 chains.
  2. Mapped mutations carry SEMANTIC_MAPPER provenance.
  3. Unresolved mutations have ambiguity reasons (never best-guess).
  4. Incorrect automatic mutation rate is 0% (no false mappings).
  5. The Ameresco chain has at least 2 mapped mutations (A1 leverage + A3 JCA).
  6. Amedisys and Bausch & Lomb have 0 mapped (parser finds nothing).
"""
from __future__ import annotations

from edgar_chains import chain_amedisys, chain_ameresco, chain_bausch_lomb
from models import InstructionProvenance
from semantic_pipeline import (
    render_metrics_report,
    run_all_semantic_pipelines,
    run_semantic_pipeline,
)


def test_pipeline_runs_on_all_chains():
    """The semantic pipeline runs without errors on all 3 EDGAR chains."""
    results = run_all_semantic_pipelines()
    assert len(results) == 3
    chain_ids = {r.chain_id for r in results}
    assert chain_ids == {"EDGAR-AMERESCO", "EDGAR-AMEDISYS", "EDGAR-BAUSCH-LOMB"}


def test_pipeline_ameresco_has_mapped_mutations():
    """Ameresco has at least 3 mapped mutations (A1 leverage + A2 leverage + A3 JCA)."""
    result = run_semantic_pipeline(chain_ameresco())
    assert result.total_mapped >= 3
    assert result.total_parser_instructions == 14


def test_pipeline_ameresco_mapped_mutations_have_semantic_mapper_provenance():
    """All mapped mutations in Ameresco carry SEMANTIC_MAPPER provenance."""
    result = run_semantic_pipeline(chain_ameresco())
    for step in result.steps:
        for mut in step.mapper_mutations:
            assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
            assert mut.ambiguity_reason is None


def test_pipeline_ameresco_unresolved_have_ambiguity_reasons():
    """All unresolved mutations in Ameresco have an ambiguity reason."""
    result = run_semantic_pipeline(chain_ameresco())
    for step in result.steps:
        for mut in step.mapper_unresolved:
            assert mut.ambiguity_reason is not None
            assert mut.provenance == InstructionProvenance.MANUAL


def test_pipeline_ameresco_zero_incorrect_mutations():
    """No mapped mutation is rejected by the executor (0% incorrect rate)."""
    result = run_semantic_pipeline(chain_ameresco())
    assert result.incorrect_mutation_rate == 0.0
    assert len(result.incorrect_mutations) == 0


def test_pipeline_amedisys_zero_parser_instructions():
    """Amedisys has 0 parser instructions (full restatement pattern)."""
    result = run_semantic_pipeline(chain_amedisys())
    assert result.total_parser_instructions == 0
    assert result.total_mapped == 0
    assert result.total_unresolved == 0


def test_pipeline_bausch_lomb_zero_parser_instructions():
    """Bausch & Lomb has 0 parser instructions (conformed copy pattern)."""
    result = run_semantic_pipeline(chain_bausch_lomb())
    assert result.total_parser_instructions == 0
    assert result.total_mapped == 0
    assert result.total_unresolved == 0


def test_pipeline_ameresco_a1_leverage_ratio_mapped():
    """A1 has a mapped leverage ratio mutation with correct schedule."""
    result = run_semantic_pipeline(chain_ameresco())
    a1 = result.steps[0]
    assert a1.amendment_number == 1
    leverage_muts = [
        m for m in a1.mapper_mutations
        if m.commitment_id == "financial_covenant.leverage_ratio"
    ]
    assert len(leverage_muts) == 1
    mut = leverage_muts[0]
    assert mut.field == "applicability"
    assert mut.unit == "ratio"
    sched = mut.new_value
    assert len(sched["step_down_schedule"]) == 2
    assert sched["step_down_schedule"][0]["period_end"] == "2023-06-30"
    assert sched["step_down_schedule"][0]["threshold"] == 4.00
    assert sched["steady_state_threshold"] == 3.50


def test_pipeline_ameresco_a2_leverage_ratio_mapped():
    """A2 has a mapped leverage ratio mutation with correct schedule.

    The A2 Section 7.10 change was previously missed by the parser due
    to a regex bridging bug in REPLACE_V04.  The fix (tempered group
    that stops at section boundaries) now correctly captures it.
    """
    result = run_semantic_pipeline(chain_ameresco())
    a2 = result.steps[1]
    assert a2.amendment_number == 2
    leverage_muts = [
        m for m in a2.mapper_mutations
        if m.commitment_id == "financial_covenant.leverage_ratio"
    ]
    assert len(leverage_muts) == 1
    mut = leverage_muts[0]
    assert mut.field == "applicability"
    assert mut.unit == "ratio"
    sched = mut.new_value
    assert len(sched["step_down_schedule"]) == 1
    assert sched["step_down_schedule"][0]["period_end"] == "2023-12-31"
    assert sched["step_down_schedule"][0]["threshold"] == 3.75
    assert sched["steady_state_threshold"] == 3.50


def test_pipeline_ameresco_a3_junior_credit_agreement_mapped():
    """A3 has a mapped Junior Credit Agreement addition."""
    result = run_semantic_pipeline(chain_ameresco())
    a3 = result.steps[2]
    assert a3.amendment_number == 3
    jca_muts = [
        m for m in a3.mapper_mutations
        if m.commitment_id == "facility.junior_credit_agreement"
    ]
    assert len(jca_muts) == 1
    mut = jca_muts[0]
    assert mut.field == "amount"
    assert mut.unit == "usd"
    payload = mut.new_value
    assert payload["threshold"] == 150_000_000


def test_pipeline_ameresco_state_agreement_100_percent():
    """Ameresco state agreement is 100% — all 3 commitments match.

    The parser now correctly captures the A2 Section 7.10 leverage ratio
    change (previously missed due to a regex bridging bug in REPLACE_V04,
    fixed with a tempered group that stops at section boundaries).  With
    all three leverage ratio changes (A1, A2) and the JCA addition (A3)
    captured and mapped, the reconstructed state matches the ground truth
    exactly.
    """
    result = run_semantic_pipeline(chain_ameresco())
    assert result.final_state_agreement == 1.0
    assert len(result.state_mismatches) == 0


def test_pipeline_amedisys_state_agreement_vacuous():
    """Amedisys state agreement is 100% but vacuously — no parser instructions.

    The parser finds 0 instructions on both A1 and A2 (full restatement
    pattern).  The original state equals the ground truth state (both have
    the same two covenants with the same thresholds).  The 100% agreement
    is NOT a successful end-to-end reconstruction — the mapper did nothing
    because there was nothing to map.  This does NOT satisfy the v0.1
    success criterion.
    """
    result = run_semantic_pipeline(chain_amedisys())
    assert result.total_parser_instructions == 0
    assert result.total_mapped == 0
    assert result.final_state_agreement == 1.0  # vacuous: original == ground truth


def test_pipeline_bausch_lomb_state_agreement_low():
    """Bausch & Lomb state agreement is low (25%) due to conformed copy pattern.

    The parser finds 0 instructions on all 4 amendments (conformed copy
    pattern).  The ground truth has additional facilities and a changed
    term loan amount that the parser cannot extract.  This does NOT
    satisfy the v0.1 success criterion.
    """
    result = run_semantic_pipeline(chain_bausch_lomb())
    assert result.total_parser_instructions == 0
    assert result.total_mapped == 0
    assert result.final_state_agreement < 1.0


def test_pipeline_ameresco_meets_success_criterion():
    """Ameresco meets the v0.1 success criterion.

    The v0.1 success criterion requires at least one chain to be
    reconstructed end-to-end from filed amendment text without manual
    semantic mutation entry.  Ameresco meets this:

    - 3 mapped mutations (A1 leverage, A2 leverage, A3 JCA)
    - 0% incorrect mutation rate
    - 100% final state agreement
    - All unresolved have ambiguity reasons (no best-guess)

    Amedisys and Bausch & Lomb do NOT meet the criterion (0 parser
    instructions due to full-restatement / conformed-copy patterns).
    """
    results = run_all_semantic_pipelines()
    ameresco = next(r for r in results if r.chain_id == "EDGAR-AMERESCO")
    assert ameresco.total_mapped >= 3
    assert ameresco.incorrect_mutation_rate == 0.0
    assert ameresco.final_state_agreement == 1.0

    # At least one chain meets the criterion
    any_clean = any(
        r.total_mapped > 0
        and r.incorrect_mutation_rate == 0.0
        and r.final_state_agreement == 1.0
        for r in results
    )
    assert any_clean, "No chain meets the v0.1 success criterion"


def test_pipeline_metrics_report_renders():
    """The metrics report renders without errors and honestly reports criterion status."""
    results = run_all_semantic_pipelines()
    report = render_metrics_report(results)
    assert "Semantic Mapper v0.1" in report
    assert "Mapping accuracy" in report
    assert "Unresolved rate" in report
    assert "Incorrect automatic mutation rate" in report
    assert "State agreement" in report
    assert "meets_criterion" in report
    # The report must honestly state whether the success criterion is met
    assert "NOT YET" in report or "SUCCESS" in report


def test_pipeline_no_manual_in_mapped_mutations():
    """No mapped mutation has MANUAL or MANUAL_FALLBACK provenance."""
    results = run_all_semantic_pipelines()
    for r in results:
        for step in r.steps:
            for mut in step.mapper_mutations:
                assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER, \
                    f"{r.chain_id} A{step.amendment_number}: mapped mutation has " \
                    f"{mut.provenance} provenance, expected SEMANTIC_MAPPER"
