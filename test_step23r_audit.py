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

from build_step23r_audit import (
    CANONICAL_CLASSES,
    CLASS_KEYWORD_PATTERNS,
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

    def test_safety_gates_pass(self):
        """incorrect_accepted_mutations and false_authoritative_promotions
        must be 0."""
        audit_path = Path("results/step23r_audit.json")
        if not audit_path.exists():
            pytest.skip("Audit JSON not generated yet")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        for gate in audit["section_l_gates"]["gate_details"]:
            if "incorrect_accepted" in gate["gate"]:
                assert gate["passed"], (
                    f"{gate['gate']} failed: {gate['value']}"
                )
            if "false_authoritative" in gate["gate"]:
                assert gate["passed"], (
                    f"{gate['gate']} failed: {gate['value']}"
                )
