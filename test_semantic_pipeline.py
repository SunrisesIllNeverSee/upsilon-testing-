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

import pytest

from models import InstructionProvenance
from semantic_pipeline import (
    run_all_semantic_pipelines,
    run_semantic_pipeline,
    render_metrics_report,
)
from edgar_chains import chain_ameresco, chain_amedisys, chain_bausch_lomb


def test_pipeline_runs_on_all_chains():
    """The semantic pipeline runs without errors on all 3 EDGAR chains."""
    results = run_all_semantic_pipelines()
    assert len(results) == 3
    chain_ids = {r.chain_id for r in results}
    assert chain_ids == {"EDGAR-AMERESCO", "EDGAR-AMEDISYS", "EDGAR-BAUSCH-LOMB"}


def test_pipeline_ameresco_has_mapped_mutations():
    """Ameresco has at least 2 mapped mutations (A1 leverage + A3 JCA)."""
    result = run_semantic_pipeline(chain_ameresco())
    assert result.total_mapped >= 2
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


def test_pipeline_ameresco_state_agreement_partial_due_to_parser_gap():
    """Ameresco state agreement is partial due to A2 Section 7.10 parser gap.

    The parser misses the A2 Section 7.10 leverage ratio change, so the
    reconstructed state retains the A1 schedule instead of the A2 schedule.
    This is a parser limitation, not a mapper limitation.  The mapper
    correctly maps what the parser produces.
    """
    result = run_semantic_pipeline(chain_ameresco())
    # 2/3 commitments match (DSCR + JCA), leverage ratio doesn't due to parser gap
    assert result.final_state_agreement > 0.5
    assert result.final_state_agreement < 1.0
    # The mismatch should be about the leverage ratio schedule
    assert any("leverage_ratio" in m for m in result.state_mismatches)


def test_pipeline_amedisys_state_agreement_100_percent():
    """Amedisys state agreement is 100% (covenants persist, no changes)."""
    result = run_semantic_pipeline(chain_amedisys())
    assert result.final_state_agreement == 1.0


def test_pipeline_metrics_report_renders():
    """The metrics report renders without errors."""
    results = run_all_semantic_pipelines()
    report = render_metrics_report(results)
    assert "Semantic Mapper v0.1" in report
    assert "Mapping accuracy" in report
    assert "Unresolved rate" in report
    assert "Incorrect automatic mutation rate" in report
    assert "State agreement" in report


def test_pipeline_no_manual_in_mapped_mutations():
    """No mapped mutation has MANUAL or MANUAL_FALLBACK provenance."""
    results = run_all_semantic_pipelines()
    for r in results:
        for step in r.steps:
            for mut in step.mapper_mutations:
                assert mut.provenance == InstructionProvenance.SEMANTIC_MAPPER, \
                    f"{r.chain_id} A{step.amendment_number}: mapped mutation has " \
                    f"{mut.provenance} provenance, expected SEMANTIC_MAPPER"
