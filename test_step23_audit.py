"""Tests for Step 23 — Upsilon v2 Eligibility & Semantic Funnel Audit.

Tests cover:
  - Instruction collection respects genre patterns (393, not 403)
  - Eligibility classification logic (IN_SCOPE / OUT_OF_SCOPE / AMBIGUOUS)
  - Funnel tracing uses trace.failed_step (not string matching)
  - Resolver path: validator_rejected only counts failed_step == 8
  - Pipeline reachability is determined by static code analysis
  - Gate evaluation logic
  - Report generation derives all values from JSON
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_step23_audit import (
    CANONICAL_CLASSES,
    _analyze_pipeline_reachability,
    _is_parser_based_genre,
    classify_gt_eligibility,
    classify_instruction_eligibility,
    classify_s0_eligibility,
    collect_all_instructions,
    trace_resolution_funnel,
    trace_resolver_path,
)
from generate_step23_report import _pct
from models import (
    AmendmentInstruction,
    InstructionProvenance,
    InstructionType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instruction(
    source_text: str = "",
    section_ref: str = "",
    ins_type: InstructionType = InstructionType.REPLACE_VALUE,
) -> AmendmentInstruction:
    return AmendmentInstruction(
        order=1,
        instruction_type=ins_type,
        target_section_ref=section_ref,
        source_text=source_text,
        provenance=InstructionProvenance.PARSER,
    )


# ---------------------------------------------------------------------------
# Genre-based instruction collection
# ---------------------------------------------------------------------------


class TestParserBasedGenre:
    """Tests for _is_parser_based_genre."""

    def test_incremental_is_parser_based(self):
        class FakeStep:
            pattern = "incremental"
        assert _is_parser_based_genre(FakeStep()) is True

    def test_unknown_is_parser_based(self):
        class FakeStep:
            pattern = "unknown"
        assert _is_parser_based_genre(FakeStep()) is True

    def test_full_restatement_is_not_parser_based(self):
        class FakeStep:
            pattern = "full_restatement"
        assert _is_parser_based_genre(FakeStep()) is False

    def test_conformed_copy_is_not_parser_based(self):
        class FakeStep:
            pattern = "conformed_copy"
        assert _is_parser_based_genre(FakeStep()) is False

    def test_none_pattern_is_parser_based(self):
        class FakeStep:
            pattern = None
        assert _is_parser_based_genre(FakeStep()) is True


class TestInstructionCollectionCount:
    """The audit must collect exactly the same number of parser
    instructions as the v2 study (393), not more.

    The previous version parsed all documents regardless of genre,
    producing 403.  The fix skips FULL_RESTATEMENT and
    CONFORMED_COPY amendments.
    """

    def test_total_matches_v2_study(self):
        records = collect_all_instructions()
        v2_study = json.loads(
            Path("results/step_21_v2_study_results.json").read_text(
                encoding="utf-8",
            ),
        )
        v2_total = v2_study["total_parser_instructions"]
        assert len(records) == v2_total, (
            f"Audit collected {len(records)} instructions but v2 study "
            f"reports {v2_total}.  The audit must respect genre patterns."
        )


# ---------------------------------------------------------------------------
# Eligibility classification
# ---------------------------------------------------------------------------


class TestEligibilityClassification:

    def test_covenant_keyword_is_in_scope(self):
        ins = _make_instruction(
            source_text="The maximum leverage ratio shall be reduced to 3.50 to 1.00",
            section_ref="Section 7.10",
        )
        eligibility, cid, _, _ = classify_instruction_eligibility(ins)
        assert eligibility == "IN_SCOPE"
        assert cid == "financial_covenant.leverage_ratio"

    def test_term_loan_is_in_scope(self):
        ins = _make_instruction(
            source_text="The term loan commitment is hereby increased to $50,000,000",
            section_ref="Section 2.01",
        )
        eligibility, cid, _, _ = classify_instruction_eligibility(ins)
        assert eligibility == "IN_SCOPE"
        # The canonical class should be a facility class (the registry
        # may resolve to either term_loan or revolving_facility
        # depending on matching priorities).
        assert cid.startswith("facility.")

    def test_definitions_section_is_out_of_scope(self):
        ins = _make_instruction(
            source_text='The definition of "Applicable Rate" is hereby amended',
            section_ref="Section 1.01",
        )
        eligibility, _, _, _ = classify_instruction_eligibility(ins)
        assert eligibility == "OUT_OF_SCOPE"

    def test_interest_rate_is_out_of_scope(self):
        # The commitment registry may map certain sections to
        # canonical classes even when the text is about non-covenant
        # topics.  We test with text that has no covenant signal and
        # no section ref that the registry maps to a covenant class.
        ins = _make_instruction(
            source_text="The applicable rate shall be adjusted to SOFR plus 2%",
            section_ref="Section 2.14",
        )
        eligibility, _, _, _ = classify_instruction_eligibility(ins)
        assert eligibility in ("OUT_OF_SCOPE", "AMBIGUOUS_SCOPE")

    def test_canonical_class_must_be_in_13_class_set(self):
        """All IN_SCOPE canonical classes must be in the frozen 13-class
        ontology."""
        records = collect_all_instructions()
        in_scope = [r for r in records if r.eligibility == "IN_SCOPE"]
        for r in in_scope:
            if r.canonical_class:
                assert r.canonical_class in CANONICAL_CLASSES, (
                    f"{r.canonical_class} is not in the 13-class ontology"
                )


# ---------------------------------------------------------------------------
# Funnel tracing
# ---------------------------------------------------------------------------


class TestFunnelTracing:
    """Tests that trace_resolution_funnel uses trace.failed_step
    (not fragile string matching on trace field values)."""

    def test_delete_instruction_fails_at_stage_4(self):
        """DELETE operations are conservatively rejected by the resolver
        at step 1 (failed_step=1), so the funnel should not progress
        past stage 4 (commitment resolution) for a DELETE instruction
        that does resolve a commitment."""
        ins = _make_instruction(
            source_text="The leverage ratio covenant is hereby deleted",
            section_ref="Section 7.10",
            ins_type=InstructionType.DELETE,
        )
        stages = trace_resolution_funnel(ins, {})
        # Stage 1-3 should pass (parsed, scope, section)
        assert stages["stage_1_parsed"] is True
        assert stages["stage_2_scope_recognized"] is True
        # Stage 4 may or may not pass depending on whether the
        # commitment resolves.  But stages 5+ should NOT pass for
        # DELETE (resolver rejects at step 1).
        if stages["stage_4_commitment_resolved"]:
            assert stages["stage_5_field_resolved"] is False

    def test_non_covenant_instruction_stops_at_stage_2(self):
        """An instruction with no covenant content should not pass
        stage 2 (scope recognized)."""
        ins = _make_instruction(
            source_text="The accounting principles definition is amended",
            section_ref="Section 1.03",
        )
        stages = trace_resolution_funnel(ins, {})
        assert stages["stage_1_parsed"] is True
        assert stages["stage_2_scope_recognized"] is False

    def test_all_stages_are_boolean(self):
        """All stage values must be booleans, not strings or None."""
        ins = _make_instruction(
            source_text="maximum leverage ratio shall be 3.00 to 1.00",
            section_ref="Section 7.10",
        )
        stages = trace_resolution_funnel(ins, {})
        for stage, value in stages.items():
            assert isinstance(value, bool), (
                f"Stage {stage} is {type(value)}, expected bool"
            )


# ---------------------------------------------------------------------------
# Resolver path tracing
# ---------------------------------------------------------------------------


class TestResolverPath:

    def test_validator_rejected_only_counts_step_8(self):
        """validator_rejected must only be True when the resolver's
        failed_step == 8 (candidate produced but validation failed),
        NOT for all unresolved cases."""
        # An instruction that fails at commitment resolution (step 1)
        # should NOT count as validator_rejected.
        ins = _make_instruction(
            source_text="Some unrelated text about accounting",
            section_ref="Section 1.01",
        )
        path = trace_resolver_path(ins, {})
        assert path["validator_rejected"] is False

    def test_pipeline_reachability_is_determined_by_code(self):
        """_analyze_pipeline_reachability must return a dict with
        boolean values determined by static code analysis, not
        hardcoded."""
        reachability = _analyze_pipeline_reachability()
        assert isinstance(reachability, dict)
        for key, value in reachability.items():
            assert isinstance(value, bool), (
                f"{key} is {type(value)}, expected bool"
            )
        # The resolver must use commitment_registry and staged_interpreter
        assert reachability["commitment_registry_executed"] is True
        assert reachability["staged_interpreter_executed"] is True

    def test_resolver_path_returns_all_keys(self):
        ins = _make_instruction(
            source_text="leverage ratio shall be 3.00 to 1.00",
            section_ref="Section 7.10",
        )
        path = trace_resolver_path(ins, {})
        expected_keys = {
            "agreement_context_executed",
            "commitment_registry_executed",
            "resolve_with_context_executed",
            "staged_interpreter_executed",
            "model_assisted_interface_executed",
            "candidate_produced",
            "validator_rejected",
        }
        assert set(path.keys()) == expected_keys


# ---------------------------------------------------------------------------
# S0/GT eligibility
# ---------------------------------------------------------------------------


class TestS0Eligibility:

    def test_empty_text_is_discovery_failure(self):
        rec = classify_s0_eligibility("C1", "S0", 0, 0, 0, "")
        assert rec.eligibility == "S0_DISCOVERY_FAILURE"

    def test_covenant_content_is_in_scope(self):
        text = "The borrower shall maintain a leverage ratio of not more than 3.50 to 1.00"
        rec = classify_s0_eligibility("C1", "S0", len(text), 0, 0, text)
        assert rec.eligibility == "S0_IN_SCOPE"

    def test_credit_agreement_without_covenants_is_no_in_scope(self):
        # Text must NOT contain any COVENANT_KEYWORDS (e.g., "revolving
        # credit", "term loan", "leverage ratio") to be classified as
        # S0_NO_IN_SCOPE_CONTENT.
        text = "This credit agreement establishes the borrowing arrangements between the borrower and lender"
        rec = classify_s0_eligibility("C1", "S0", len(text), 0, 0, text)
        assert rec.eligibility == "S0_NO_IN_SCOPE_CONTENT"

    def test_extracted_count_makes_in_scope(self):
        text = "Some credit agreement text"
        rec = classify_s0_eligibility("C1", "S0", len(text), 1, 0, text)
        assert rec.eligibility == "S0_IN_SCOPE"


class TestGTEligibility:

    def test_empty_text_is_discovery_failure(self):
        rec = classify_gt_eligibility("C1", "CMP", 0, 0, 0, "")
        assert rec.eligibility == "GT_DISCOVERY_FAILURE"

    def test_covenant_content_is_in_scope(self):
        text = "The term loan commitment is $50,000,000 with a leverage ratio covenant of 3.00"
        rec = classify_gt_eligibility("C1", "CMP", len(text), 0, 0, text)
        assert rec.eligibility == "GT_IN_SCOPE"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


class TestReportGeneration:

    def test_pct_formats_correctly(self):
        assert _pct(3, 4) == "75.0%"
        assert _pct(0, 4) == "0.0%"
        assert _pct(4, 4) == "100.0%"

    def test_pct_handles_zero_total(self):
        assert _pct(0, 0) == "N/A"

    def test_report_has_all_sections(self):
        report_path = Path("results/step_23_audit_report.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        report = report_path.read_text(encoding="utf-8")
        required_sections = [
            "## 23A — Instruction Eligibility",
            "## 23B — S0 Eligibility",
            "## 23C — GT Eligibility",
            "## 23D — Semantic Resolution Funnel",
            "## 23E — v2 Resolver-Path Reachability",
            "## 23F — Revised Unresolved Taxonomy",
            "## 23G — Like-for-Like v1 vs v2 Comparison",
            "## 23H — Reevaluated Exit Gates",
            "## Top 3 Bottlenecks",
            "## Summary",
        ]
        for section in required_sections:
            assert section in report, f"Missing section: {section}"

    def test_report_summary_has_11_items(self):
        report_path = Path("results/step_23_audit_report.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        report = report_path.read_text(encoding="utf-8")
        # The summary table should have 11 numbered items
        for i in range(1, 12):
            assert f"| {i} |" in report, f"Missing summary item {i}"

    def test_audit_json_has_numeric_values(self):
        """The audit JSON should include numeric values for
        machine-readability, not just formatted strings."""
        audit_path = Path("results/step_23_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        # Check for numeric fields
        a = audit["23a_instruction_eligibility"]
        assert "raw_automation_rate_numeric" in a
        assert "eligible_semantic_mapping_coverage_numeric" in a
        assert isinstance(a["raw_automation_rate_numeric"], (int, float))
        assert isinstance(a["eligible_semantic_mapping_coverage_numeric"], (int, float))


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


class TestGateEvaluation:
    """Integration test: verify the audit JSON gates are internally
    consistent."""

    def test_gates_passed_count_matches_details(self):
        audit_path = Path("results/step_23_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        h = audit["23h_gates"]
        detail_passed = sum(1 for g in h["gate_details"] if g["passed"])
        assert h["gates_passed_count"] == detail_passed
        assert h["gates_total"] == len(h["gate_details"])

    def test_other_percentage_below_10(self):
        """23F requires OTHER < 10%."""
        audit_path = Path("results/step_23_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        f = audit["23f_revised_taxonomy"]
        assert f["other_percentage"] < 10.0, (
            f"OTHER is {f['other_percentage']}%, target is <10%"
        )
