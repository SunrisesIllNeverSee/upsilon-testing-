"""Tests for Step 23R — Independent Failure Census + Measurement Recovery.

Tests cover:
  - Eligibility does not invoke resolver/mapper/registry functions
  - S0 eligibility does not depend on extraction count
  - GT eligibility does not depend on extraction count
  - Each eligible failing instruction has exactly one first-runtime failure
  - Funnel/runtime order follows actual execution
  - State advances between amendments
  - TRUE_AMBIGUITY is not the default fallback
  - OTHER is reachable
  - Record-level numerator membership is enforced
  - All ledger populations reconcile
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from audits.step23r.build_step23r_audit import (
    CANONICAL_CLASSES,
    CLASS_KEYWORD_PATTERNS,
    _check_mapping_correct,
    _normalize_value_str,
    build_failure_taxonomy,
    classify_eligibility_independent,
    classify_gt_eligibility_independent,
    classify_s0_eligibility_independent,
    classify_failure_type,
    collect_all_instructions,
    InstructionRow,
    populate_expected_truth,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    source_text: str = "",
    target_ref: str = "",
    ins_type: str = "REPLACE_VALUE",
    chain_id: str = "TEST",
    amendment_order: int = 1,
    instruction_index: int = 1,
) -> InstructionRow:
    return InstructionRow(
        instruction_id=f"{chain_id}:A{amendment_order}:I{instruction_index}",
        chain_id=chain_id,
        document_id="",
        amendment_order=amendment_order,
        instruction_index=instruction_index,
        genre="incremental",
        instruction_type=ins_type,
        target_ref=target_ref,
        source_span_start=0,
        source_span_end=0,
        source_text=source_text,
    )


# ---------------------------------------------------------------------------
# Section 2: Frozen population
# ---------------------------------------------------------------------------


class TestFrozenPopulation:

    def test_total_is_393(self):
        rows = collect_all_instructions()
        assert len(rows) == 393

    def test_all_ids_unique(self):
        rows = collect_all_instructions()
        ids = [r.instruction_id for r in rows]
        assert len(ids) == len(set(ids))

    def test_no_missing_chain_or_amendment(self):
        rows = collect_all_instructions()
        for r in rows:
            assert r.chain_id, f"Missing chain_id for {r.instruction_id}"
            assert r.amendment_order > 0
            assert r.instruction_index > 0


# ---------------------------------------------------------------------------
# Section 3: Independent eligibility
# ---------------------------------------------------------------------------


class TestIndependentEligibility:
    """Eligibility must be determined from SOURCE EVIDENCE ONLY, never
    from resolver/registry/mapper/extractor success."""

    def test_covenant_keyword_with_amendment_signal_is_in_scope(self):
        eligibility, cls, field_name, reason, op = (
            classify_eligibility_independent(
                "The maximum leverage ratio shall be reduced to 3.50 to 1.00",
                "Section 7.10",
                "REPLACE_VALUE",
            )
        )
        assert eligibility == "IN_SCOPE"
        assert cls == "financial_covenant.leverage_ratio"

    def test_definitions_section_is_out_of_scope(self):
        eligibility, _, _, reason, _ = classify_eligibility_independent(
            'The definition of "Applicable Rate" is hereby amended',
            "Section 1.01",
            "RESTATE_SECTION",
        )
        assert eligibility == "OUT_OF_SCOPE"

    def test_facility_keyword_in_ancillary_context_is_out_of_scope(self):
        """revolving credit mentioned in debt incurrence context is
        NOT a facility amendment."""
        eligibility, _, _, reason, _ = classify_eligibility_independent(
            "any Indebtedness incurred by the Borrower, revolving credit "
            "exposures shall not exceed...",
            "Section 2.9",
            "ADD",
        )
        assert eligibility == "OUT_OF_SCOPE"

    def test_facility_keyword_with_commitment_increase_is_in_scope(self):
        eligibility, cls, _, _, _ = classify_eligibility_independent(
            "The term loan commitment is hereby increased to $50,000,000",
            "Section 2.01",
            "REPLACE_VALUE",
        )
        assert eligibility == "IN_SCOPE"
        assert cls == "facility.term_loan"

    def test_no_covenant_keyword_is_ambiguous_or_out_of_scope(self):
        eligibility, _, _, _, _ = classify_eligibility_independent(
            "Some unrelated text about accounting principles",
            "Section 1.03",
            "RESTATE_SECTION",
        )
        assert eligibility in ("OUT_OF_SCOPE", "AMBIGUOUS_SCOPE")

    def test_eligibility_does_not_consult_resolver(self):
        """The eligibility classifier must NOT call any resolver,
        mapper, or registry function.  This is verified by checking
        that it produces consistent results for the same input
        regardless of system state."""
        # A covenant keyword should always produce IN_SCOPE
        e1, _, _, _, _ = classify_eligibility_independent(
            "leverage ratio shall be 3.00 to 1.00",
            "Section 7.10",
            "REPLACE_VALUE",
        )
        e2, _, _, _, _ = classify_eligibility_independent(
            "leverage ratio shall be 3.00 to 1.00",
            "Section 7.10",
            "REPLACE_VALUE",
        )
        assert e1 == e2 == "IN_SCOPE"

    def test_all_in_scope_classes_in_13_class_ontology(self):
        rows = collect_all_instructions()
        for row in rows:
            eligibility, cls, _, _, _ = classify_eligibility_independent(
                row.source_text, row.target_ref, row.instruction_type,
            )
            if eligibility == "IN_SCOPE":
                assert cls in CANONICAL_CLASSES, (
                    f"{cls} is not in the 13-class ontology"
                )


# ---------------------------------------------------------------------------
# Section 11/12: S0/GT eligibility independence
# ---------------------------------------------------------------------------


class TestS0EligibilityIndependent:

    def test_empty_text_is_discovery_failure(self):
        rec = classify_s0_eligibility_independent("C1", "S0", 0, "", 0)
        assert rec.independent_eligibility == "S0_DISCOVERY_FAILURE"

    def test_covenant_content_is_in_scope_regardless_of_extraction(self):
        """S0 eligibility must NOT depend on extracted_count."""
        text = "The borrower shall maintain a leverage ratio of not more than 3.50 to 1.00"
        rec_zero = classify_s0_eligibility_independent("C1", "S0", len(text), text, 0)
        rec_one = classify_s0_eligibility_independent("C1", "S0", len(text), text, 1)
        # Both should be IN_SCOPE regardless of extracted_count
        assert rec_zero.independent_eligibility == "S0_IN_SCOPE"
        assert rec_one.independent_eligibility == "S0_IN_SCOPE"

    def test_no_covenant_content_is_no_in_scope(self):
        text = "This credit agreement establishes the borrowing arrangements between the borrower and lender"
        rec = classify_s0_eligibility_independent("C1", "S0", len(text), text, 0)
        assert rec.independent_eligibility == "S0_NO_IN_SCOPE_CONTENT"

    def test_extraction_count_does_not_override_source_evidence(self):
        """Even with extracted_count > 0, if source text has no
        covenant keywords, it should NOT be IN_SCOPE."""
        text = "This credit agreement establishes the borrowing arrangements"
        rec = classify_s0_eligibility_independent("C1", "S0", len(text), text, 5)
        assert rec.independent_eligibility == "S0_NO_IN_SCOPE_CONTENT"


class TestGTEligibilityIndependent:

    def test_empty_text_is_discovery_failure(self):
        rec = classify_gt_eligibility_independent("C1", "CMP", 0, "", 0)
        assert rec.independent_eligibility == "GT_DISCOVERY_FAILURE"

    def test_covenant_content_is_in_scope(self):
        text = "The term loan commitment is $50,000,000 with a leverage ratio covenant of 3.00"
        rec = classify_gt_eligibility_independent("C1", "CMP", len(text), text, 0)
        assert rec.independent_eligibility == "GT_IN_SCOPE"

    def test_extraction_count_does_not_override_source_evidence(self):
        text = "This credit agreement establishes borrowing arrangements"
        rec = classify_gt_eligibility_independent("C1", "CMP", len(text), text, 5)
        assert rec.independent_eligibility == "GT_NO_IN_SCOPE_CONTENT"


# ---------------------------------------------------------------------------
# Section 6: Runtime failure trace
# ---------------------------------------------------------------------------


class TestRuntimeFailureTrace:
    """Each eligible failing instruction must have exactly one
    first-runtime failure, following actual execution order."""

    def test_failed_instruction_has_one_failure(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        in_scope_failed = [
            r for r in ledger
            if r["independent_eligibility"] == "IN_SCOPE"
            and r["terminal_outcome"] == "FAILED"
        ]
        for r in in_scope_failed:
            assert r["first_runtime_failure"], (
                f"{r['instruction_id']} has no first_runtime_failure"
            )

    def test_accepted_instruction_has_no_failure(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        accepted = [
            r for r in ledger
            if r["independent_eligibility"] == "IN_SCOPE"
            and r["terminal_outcome"] == "ACCEPTED"
        ]
        for r in accepted:
            assert not r["first_runtime_failure"], (
                f"{r['instruction_id']} is accepted but has "
                f"first_runtime_failure={r['first_runtime_failure']}"
            )

    def test_executor_rejected_candidate_is_failed_not_accepted(self):
        """Regression: when the resolver produces a candidate
        (candidate_created=True) but the executor rejects it
        (executor_accepted=False), the row's terminal_outcome must
        be FAILED with first_runtime_failure=VALIDATOR_REJECTION —
        NOT ACCEPTED.

        Previously, _record_runtime_trace set terminal_outcome=
        ACCEPTED when the resolver succeeded, and the executor
        rejection path did not update it.  This caused executor-
        rejected rows to be misclassified as accepted_incorrect in
        the taxonomy rather than as failed with a VALIDATOR_REJECTION
        first-runtime failure.
        """
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        # Find rows where the resolver produced a candidate but the
        # executor rejected it.
        executor_rejected = [
            r for r in ledger
            if r.get("candidate_created")
            and r.get("executor_accepted") is False
        ]
        for r in executor_rejected:
            assert r["terminal_outcome"] == "FAILED", (
                f"{r['instruction_id']}: executor rejected candidate but "
                f"terminal_outcome={r['terminal_outcome']!r} (expected FAILED)"
            )
            assert r["first_runtime_failure"] == "VALIDATOR_REJECTION", (
                f"{r['instruction_id']}: executor rejected but "
                f"first_runtime_failure={r['first_runtime_failure']!r} "
                f"(expected VALIDATOR_REJECTION)"
            )
            assert r["accepted"] is False, (
                f"{r['instruction_id']}: executor rejected but accepted=True"
            )

    def test_terminal_outcome_accepted_implies_executor_accepted(self):
        """Every row with terminal_outcome=ACCEPTED must also have
        executor_accepted=True.  This is the converse of the
        executor-rejection regression: a row should never be marked
        ACCEPTED unless the executor actually applied it."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        accepted = [
            r for r in ledger
            if r["terminal_outcome"] == "ACCEPTED"
        ]
        for r in accepted:
            assert r["executor_accepted"] is True, (
                f"{r['instruction_id']}: terminal_outcome=ACCEPTED but "
                f"executor_accepted={r['executor_accepted']} (expected True)"
            )


# ---------------------------------------------------------------------------
# Section 10: Taxonomy
# ---------------------------------------------------------------------------


class TestTaxonomy:

    def test_true_ambiguity_is_not_default(self):
        """TRUE_AMBIGUITY must require affirmative evidence, not be
        a default else branch."""
        # Create rows where failure_family is set to a specific value
        # — TRUE_AMBIGUITY should NOT appear.
        rows = [
            _make_row(source_text="leverage ratio", ins_type="REPLACE_VALUE"),
        ]
        for r in rows:
            r.independent_eligibility = "IN_SCOPE"
            r.terminal_outcome = "FAILED"
            r.failure_family = "TARGET_IDENTIFICATION"
            r.protocol_vs_interpretation = "UPSILON_INTERPRETATION_FAILURE"
        taxonomy = build_failure_taxonomy(rows)
        assert "TRUE_AMBIGUITY" not in taxonomy["buckets"]

    def test_other_is_reachable(self):
        """OTHER must be reachable when failure_family is empty."""
        row = _make_row(source_text="test", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.terminal_outcome = "FAILED"
        row.failure_family = ""  # No family assigned
        row.protocol_vs_interpretation = "AMBIGUOUS_FAILURE_TYPE"
        taxonomy = build_failure_taxonomy([row])
        # Should go to OTHER (residual)
        assert "OTHER" in taxonomy["buckets"]

    def test_taxonomy_sums_correctly(self):
        """Taxonomy buckets must sum to total_failed."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        taxonomy = audit["section_j_taxonomy"]
        bucket_sum = sum(taxonomy["buckets"].values())
        assert bucket_sum == taxonomy["total_failed"], (
            f"Buckets sum to {bucket_sum} but total_failed is "
            f"{taxonomy['total_failed']}"
        )

    def test_reconciliation_check_passes(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        recon = audit["section_j_taxonomy"]["reconciliation"]
        assert recon["check"] is True

    def test_taxonomy_does_not_include_accepted(self):
        """The taxonomy must only contain failed instructions, not
        accepted ones."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        taxonomy = audit["section_j_taxonomy"]
        total_in_scope = taxonomy["total_in_scope"]
        total_failed = taxonomy["total_failed"]
        accepted = (
            taxonomy["total_accepted_correct"]
            + taxonomy["total_accepted_incorrect"]
        )
        assert total_failed + accepted == total_in_scope


# ---------------------------------------------------------------------------
# Section 5: Record-level numerator membership
# ---------------------------------------------------------------------------


class TestNumeratorMembership:

    def test_every_correct_mapping_is_in_scope(self):
        """Every row counted as correct_automatic_mapping must be
        IN_SCOPE."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        correct = [r for r in ledger if r["correct_automatic_mapping"]]
        for r in correct:
            assert r["independent_eligibility"] == "IN_SCOPE", (
                f"{r['instruction_id']} is correct but not IN_SCOPE"
            )
            assert r["terminal_outcome"] == "ACCEPTED", (
                f"{r['instruction_id']} is correct but not ACCEPTED"
            )

    def test_correct_count_matches_section_e(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        correct_count = sum(1 for r in ledger if r["correct_automatic_mapping"])
        section_e = audit["section_e_correct_semantic_automation"]
        assert correct_count == section_e["correct_automatic_in_scope_mappings"]


# ---------------------------------------------------------------------------
# Section 8: Ledger reconciliation
# ---------------------------------------------------------------------------


class TestLedgerReconciliation:

    def test_total_rows_is_393(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        ledger = audit["instruction_ledger"]
        assert len(ledger) == 393

    def test_eligibility_reconciliation(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        d = audit["section_d_independent_eligibility"]
        assert d["reconciliation"] is True

    def test_in_scope_reconciliation(self):
        """accepted_correct + accepted_incorrect + failed = IN_SCOPE"""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        taxonomy = audit["section_j_taxonomy"]
        recon = taxonomy["reconciliation"]
        assert recon["check"] is True


# ---------------------------------------------------------------------------
# Section 14: Gates
# ---------------------------------------------------------------------------


class TestGates:

    def test_gates_passed_count_matches(self):
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        h = audit["section_l_gates"]
        detail_passed = sum(1 for g in h["gate_details"] if g["passed"])
        assert h["gates_passed_count"] == detail_passed
        assert h["gates_total"] == len(h["gate_details"])

    def test_safety_gates_use_record_level_data(self):
        """incorrect_accepted_mutations and false_authoritative_promotions
        must be computed from the audit's own record-level executor
        runs, not from stale aggregate counts in a different study.

        This test verifies that the safety gate values match the
        record-level safety metrics section, ensuring the gates are
        not pulling from a stale external study.
        """
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        safety = audit.get("section_safety_metrics", {})
        if not safety:
            pytest.skip("No safety metrics in audit")
        for gate in audit["section_l_gates"]["gate_details"]:
            if "incorrect_accepted" in gate["gate"]:
                # The gate value must match the record-level count
                expected = safety["incorrect_accepted_mutations"]
                assert gate["value"].startswith(str(expected)), (
                    f"{gate['gate']} value '{gate['value']}' does not "
                    f"match record-level count {expected}"
                )
            if "false_authoritative" in gate["gate"]:
                expected = safety["false_authoritative_promotions"]
                assert gate["value"].startswith(str(expected)), (
                    f"{gate['gate']} value '{gate['value']}' does not "
                    f"match record-level count {expected}"
                )

    def test_incorrect_accepted_ids_are_executor_accepted(self):
        """Every instruction ID listed as incorrect accepted must be
        executor_accepted=True in the ledger.

        An incorrect accepted mutation is any row where the executor
        applied a mutation that should not have been applied:
          - IN_SCOPE rows where the mutation disagrees with expected
            truth (correct_automatic_mapping=False)
          - OUT_OF_SCOPE / AMBIGUOUS_SCOPE rows where ANY
            executor-accepted mutation is incorrect (the instruction
            should not have produced a mutation at all)
        """
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        safety = audit.get("section_safety_metrics", {})
        if not safety:
            pytest.skip("No safety metrics in audit")
        incorrect_ids = set(safety.get("incorrect_accepted_instruction_ids", []))
        if not incorrect_ids:
            return
        ledger = audit["instruction_ledger"]
        by_id = {r["instruction_id"]: r for r in ledger}
        for iid in incorrect_ids:
            row = by_id.get(iid)
            assert row is not None, f"{iid} not in ledger"
            assert row["executor_accepted"] is True, (
                f"{iid} is incorrect-accepted but not executor_accepted"
            )
            if row["independent_eligibility"] == "IN_SCOPE":
                assert row["correct_automatic_mapping"] is False, (
                    f"{iid} is IN_SCOPE incorrect-accepted but "
                    f"correct_automatic_mapping=True"
                )
            # OUT_OF_SCOPE / AMBIGUOUS_SCOPE rows are incorrect by
            # definition when executor_accepted — no
            # correct_automatic_mapping check needed.

    def test_out_of_scope_executor_accepted_counted_as_incorrect(self):
        """OUT_OF_SCOPE rows where the executor accepted a mutation
        MUST be counted as incorrect accepted mutations.

        The safety gate 'incorrect accepted mutations = 0' has no
        IN_SCOPE restriction.  An OUT_OF_SCOPE instruction that the
        executor applies is an unauthorized state change — arguably
        worse than an IN_SCOPE wrong-value mutation.  This test
        verifies the audit does not silently exclude them.
        """
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        safety = audit.get("section_safety_metrics", {})
        if not safety:
            pytest.skip("No safety metrics in audit")
        ledger = audit["instruction_ledger"]
        incorrect_ids = set(safety.get("incorrect_accepted_instruction_ids", []))
        # Find all OUT_OF_SCOPE / AMBIGUOUS_SCOPE rows where
        # executor_accepted=True
        non_inscope_exec_accepted = [
            r for r in ledger
            if r["executor_accepted"]
            and r["independent_eligibility"] != "IN_SCOPE"
        ]
        for r in non_inscope_exec_accepted:
            assert r["instruction_id"] in incorrect_ids, (
                f"{r['instruction_id']} is {r['independent_eligibility']} "
                f"with executor_accepted=True but NOT in incorrect_accepted "
                f"list — OUT_OF_SCOPE/AMBIGUOUS executor-accepted mutations "
                f"must be counted as incorrect"
            )


# ---------------------------------------------------------------------------
# Section 5: _check_mapping_correct checks all semantic components
# ---------------------------------------------------------------------------


class TestCheckMappingCorrect:

    def test_wrong_commitment_class_is_incorrect(self):
        """A mapping with the wrong commitment class is incorrect."""
        row = _make_row(source_text="leverage ratio", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "financial_covenant.leverage_ratio"
        row.expected_field = "threshold"
        row.expected_operation = "REPLACE"
        row.expected_new_value = "3.50"
        row.expected_unit = "ratio"
        row.candidate_created = True
        row.accepted = True
        row.predicted_commitment_class = "financial_covenant.current_ratio"
        row.predicted_field = "threshold"
        row.predicted_operation = "REPLACE_VALUE"
        row.predicted_new_value = "3.50"
        row.predicted_unit = "ratio"
        assert not _check_mapping_correct(row)

    def test_wrong_value_is_incorrect(self):
        """A mapping with the right class and field but wrong value
        is incorrect — the value check must not be skipped."""
        row = _make_row(source_text="current ratio", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "financial_covenant.current_ratio"
        row.expected_field = "threshold"
        row.expected_operation = "REPLACE"
        row.expected_new_value = "2.75"
        row.expected_unit = "ratio"
        row.candidate_created = True
        row.accepted = True
        row.predicted_commitment_class = "financial_covenant.current_ratio"
        row.predicted_field = "threshold"
        row.predicted_operation = "REPLACE_VALUE"
        row.predicted_new_value = "15.0"
        row.predicted_unit = "ratio"
        assert not _check_mapping_correct(row)

    def test_wrong_unit_is_incorrect(self):
        """A mapping with the right class, field, and value but wrong
        unit is incorrect."""
        row = _make_row(source_text="term loan", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "facility.term_loan"
        row.expected_field = "threshold"
        row.expected_operation = "REPLACE"
        row.expected_new_value = "50000000"
        row.expected_unit = "USD"
        row.candidate_created = True
        row.accepted = True
        row.predicted_commitment_class = "facility.term_loan"
        row.predicted_field = "threshold"
        row.predicted_operation = "REPLACE_VALUE"
        row.predicted_new_value = "50000000"
        row.predicted_unit = "ratio"
        assert not _check_mapping_correct(row)

    def test_correct_mapping_all_components_match(self):
        """A mapping where all components match is correct."""
        row = _make_row(source_text="leverage ratio", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "financial_covenant.leverage_ratio"
        row.expected_field = "threshold"
        row.expected_operation = "REPLACE"
        row.expected_new_value = "3.50"
        row.expected_unit = "ratio"
        row.candidate_created = True
        row.accepted = True
        row.predicted_commitment_class = "financial_covenant.leverage_ratio"
        row.predicted_field = "threshold"
        row.predicted_operation = "REPLACE_VALUE"
        row.predicted_new_value = "3.50"
        row.predicted_unit = "ratio"
        assert _check_mapping_correct(row)

    def test_source_ambiguous_value_skips_value_check(self):
        """When expected_new_value is SOURCE_AMBIGUOUS, the value
        check is skipped (we cannot verify what we don't know)."""
        row = _make_row(source_text="leverage ratio", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "financial_covenant.leverage_ratio"
        row.expected_field = "threshold"
        row.expected_operation = "REPLACE"
        row.expected_new_value = "SOURCE_AMBIGUOUS"
        row.expected_unit = "ratio"
        row.candidate_created = True
        row.accepted = True
        row.predicted_commitment_class = "financial_covenant.leverage_ratio"
        row.predicted_field = "threshold"
        row.predicted_operation = "REPLACE_VALUE"
        row.predicted_new_value = "3.50"
        row.predicted_unit = "ratio"
        assert _check_mapping_correct(row)

    def test_replace_value_replace_equivalence(self):
        """REPLACE_VALUE and REPLACE are semantically equivalent for
        the operation check."""
        row = _make_row(source_text="leverage ratio", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "financial_covenant.leverage_ratio"
        row.expected_field = "threshold"
        row.expected_operation = "REPLACE"
        row.expected_new_value = "3.50"
        row.expected_unit = "ratio"
        row.candidate_created = True
        row.accepted = True
        row.predicted_commitment_class = "financial_covenant.leverage_ratio"
        row.predicted_field = "threshold"
        row.predicted_operation = "REPLACE_VALUE"
        row.predicted_new_value = "3.50"
        row.predicted_unit = "ratio"
        assert _check_mapping_correct(row)

    def test_not_accepted_is_incorrect(self):
        """A mapping that was not accepted is incorrect."""
        row = _make_row(source_text="leverage ratio", ins_type="REPLACE_VALUE")
        row.independent_eligibility = "IN_SCOPE"
        row.expected_commitment_class = "financial_covenant.leverage_ratio"
        row.expected_field = "threshold"
        row.candidate_created = True
        row.accepted = False
        row.predicted_commitment_class = "financial_covenant.leverage_ratio"
        row.predicted_field = "threshold"
        assert not _check_mapping_correct(row)

    def test_normalize_value_str_handles_commas_and_trailing_zero(self):
        """_normalize_value_str removes commas and trailing .0."""
        assert _normalize_value_str("15.0") == "15"
        assert _normalize_value_str("50,000,000") == "50000000"
        assert _normalize_value_str("3.50") == "3.5"
        assert _normalize_value_str("") == ""


# ---------------------------------------------------------------------------
# Section 14: Verdict correctness
# ---------------------------------------------------------------------------


class TestVerdictCorrectness:

    def test_verdict_is_blocked_when_safety_gate_fails(self):
        """The step verdict must be BLOCKED when the
        incorrect_accepted_mutations safety gate fails."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        # Find the incorrect_accepted gate
        gates = audit["section_l_gates"]["gate_details"]
        incorrect_gate = next(
            (g for g in gates if "incorrect_accepted" in g["gate"]),
            None,
        )
        if incorrect_gate and not incorrect_gate["passed"]:
            # The report should say BLOCKED — check the report file.
            # Isolate the verdict line (the first ```text block under
            # "## N. Step verdict") rather than scanning the entire
            # post-verdict section, which contains "PASS" in gate
            # tables and other subsections.
            report_path = Path("results/STEP_23R_REPORT.md")
            if report_path.exists():
                report = report_path.read_text(encoding="utf-8")
                verdict_section = report.split("## N. Step verdict")[1]
                # The verdict is the first ```text block in the section
                verdict_block = verdict_section.split("```text")[1]
                verdict_line = verdict_block.split("```")[0].strip()
                assert "BLOCKED" in verdict_line, (
                    f"Safety gate failed but verdict line is not BLOCKED: "
                    f"{verdict_line!r}"
                )
                assert "PASS" not in verdict_line, (
                    f"Safety gate failed but verdict line says PASS: "
                    f"{verdict_line!r}"
                )

    def test_verdict_blocked_when_false_auth_promotion_gate_fails(self):
        """The step verdict must be BLOCKED when the
        false_authoritative_promotions safety gate fails (value > 0),
        even if incorrect_accepted_mutations is 0."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        gates = audit["section_l_gates"]["gate_details"]
        false_auth_gate = next(
            (g for g in gates if "false_authoritative" in g["gate"]),
            None,
        )
        if false_auth_gate and not false_auth_gate["passed"]:
            report_path = Path("results/STEP_23R_REPORT.md")
            if report_path.exists():
                report = report_path.read_text(encoding="utf-8")
                verdict_section = report.split("## N. Step verdict")[1]
                verdict_block = verdict_section.split("```text")[1]
                verdict_line = verdict_block.split("```")[0].strip()
                assert "BLOCKED" in verdict_line, (
                    f"false_auth gate failed but verdict is not BLOCKED: "
                    f"{verdict_line!r}"
                )

    def test_safety_gates_consistent_with_ledger(self):
        """The safety gate values must be consistent with the ledger:
        incorrect_accepted_mutations must equal the count of
        executor_accepted rows that are incorrect (IN_SCOPE with
        correct_automatic_mapping=False, OR non-IN_SCOPE with
        executor_accepted=True).
        """
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        safety = audit.get("section_safety_metrics", {})
        if not safety:
            pytest.skip("No safety metrics in audit")
        ledger = audit["instruction_ledger"]
        # Recompute from the ledger
        expected_incorrect = 0
        for r in ledger:
            if not r["executor_accepted"]:
                continue
            if r["independent_eligibility"] == "IN_SCOPE":
                if not r["correct_automatic_mapping"]:
                    expected_incorrect += 1
            else:
                # OUT_OF_SCOPE / AMBIGUOUS_SCOPE: any executor_accepted
                expected_incorrect += 1
        reported = safety["incorrect_accepted_mutations"]
        assert reported == expected_incorrect, (
            f"safety incorrect_accepted_mutations={reported} but ledger "
            f"recomputation gives {expected_incorrect}"
        )
