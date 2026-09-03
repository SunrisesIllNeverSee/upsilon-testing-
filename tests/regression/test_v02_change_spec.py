"""Tests for the v0.2 change specification.

Tests cover:
  - Every change traces to at least one failure cause in the taxonomy
  - Every affected chain exists in the failure matrix
  - Every affected chain has at least one of the listed failure causes
  - Priority ordering: extraction (1) > parser (2) > mapper (3)
  - No change is added without evidence (no "sounds useful" changes)
  - Mapper changes (priority 3) have "DO NOT implement" notes
  - Change spec references the frozen commit/tag
  - Report rendering contains all changes
  - Every change has a MUST FIX / SHOULD FIX / DEFER / REJECT classification
  - Classification is consistent with priority and evidence
  - Proposed v0.2 scope contains only MUST FIX + SHOULD FIX
  - Scope is proposed (pending human review), not pre-locked
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from audits.failure_census.build_failure_matrix import FAILURE_CAUSES
from archive.legacy_code.v02_change_spec import (
    CLASSIFICATIONS,
    PROPOSED_SCOPE_CLASSIFICATIONS,
    V02_CHANGES,
    proposed_v02_scope,
    render_change_spec,
)

# ---------------------------------------------------------------------------
# Change spec structure
# ---------------------------------------------------------------------------


class TestChangeSpecStructure:
    def test_changes_exist(self):
        assert len(V02_CHANGES) > 0

    def test_every_change_has_id(self):
        for change in V02_CHANGES:
            assert "id" in change
            assert change["id"].startswith("V02-")

    def test_every_change_has_required_fields(self):
        required = {"id", "title", "priority", "layer", "classification",
                    "classification_rationale", "failure_causes",
                    "affected_chains", "evidence", "change", "risk",
                    "regression_test", "touches"}
        for change in V02_CHANGES:
            missing = required - set(change.keys())
            assert not missing, f"Change {change['id']} missing fields: {missing}"

    def test_every_change_has_non_empty_evidence(self):
        for change in V02_CHANGES:
            assert change["evidence"], f"Change {change['id']} has empty evidence"

    def test_every_change_has_at_least_one_affected_chain(self):
        for change in V02_CHANGES:
            assert len(change["affected_chains"]) > 0, (
                f"Change {change['id']} has no affected chains"
            )

    def test_every_change_has_at_least_one_failure_cause(self):
        for change in V02_CHANGES:
            assert len(change["failure_causes"]) > 0, (
                f"Change {change['id']} has no failure causes"
            )

    def test_unique_ids(self):
        ids = [c["id"] for c in V02_CHANGES]
        assert len(ids) == len(set(ids)), "Duplicate change IDs"

    def test_all_failure_causes_in_taxonomy(self):
        for change in V02_CHANGES:
            for cause in change["failure_causes"]:
                assert cause in FAILURE_CAUSES, (
                    f"Change {change['id']} references unknown cause: {cause}"
                )


# ---------------------------------------------------------------------------
# Classification scheme (MUST FIX / SHOULD FIX / DEFER / REJECT)
# ---------------------------------------------------------------------------


class TestClassificationScheme:
    def test_every_change_has_valid_classification(self):
        """Every change must have a classification from the 4-value scheme."""
        for change in V02_CHANGES:
            assert change["classification"] in CLASSIFICATIONS, (
                f"Change {change['id']} has invalid classification: "
                f"{change['classification']}"
            )

    def test_every_change_has_non_empty_classification_rationale(self):
        """Every change must have a non-empty classification rationale."""
        for change in V02_CHANGES:
            assert change.get("classification_rationale"), (
                f"Change {change['id']} has empty classification_rationale"
            )

    def test_all_four_classifications_are_used(self):
        """All four classification values must appear at least once."""
        used = {c["classification"] for c in V02_CHANGES}
        assert used == set(CLASSIFICATIONS.keys()), (
            f"Missing classifications: {set(CLASSIFICATIONS.keys()) - used}"
        )

    def test_must_fix_changes_are_extraction_layer(self):
        """MUST FIX changes must be extraction layer (the publication bottleneck)."""
        for change in V02_CHANGES:
            if change["classification"] == "MUST FIX":
                assert change["layer"] == "extraction", (
                    f"MUST FIX change {change['id']} is not extraction layer"
                )

    def test_must_fix_changes_affect_multiple_chains(self):
        """MUST FIX changes should affect multiple chains (high evidence strength)."""
        for change in V02_CHANGES:
            if change["classification"] == "MUST FIX":
                assert len(change["affected_chains"]) >= 2, (
                    f"MUST FIX change {change['id']} affects only "
                    f"{len(change['affected_chains'])} chain — should be SHOULD FIX"
                )

    def test_reject_changes_are_priority_3(self):
        """REJECT changes should be priority 3 (mapper, lowest priority)."""
        for change in V02_CHANGES:
            if change["classification"] == "REJECT":
                assert change["priority"] == 3, (
                    f"REJECT change {change['id']} is priority "
                    f"{change['priority']}, not 3"
                )

    def test_defer_changes_have_wait_rationale(self):
        """DEFER changes must explain why they wait (not just 'lower priority')."""
        wait_keywords = (
            "wait", "defer", "until", "after", "reassess",
            "re-acqui", "complexity", "architecture",
        )
        for change in V02_CHANGES:
            if change["classification"] == "DEFER":
                rationale = change["classification_rationale"].lower()
                assert any(kw in rationale for kw in wait_keywords), (
                    f"DEFER change {change['id']} rationale does not explain "
                    f"why it waits: {change['classification_rationale']}"
                )

    def test_proposed_scope_excludes_defer_and_reject(self):
        """Proposed v0.2 scope must exclude DEFER and REJECT changes."""
        proposed = proposed_v02_scope()
        for change in proposed:
            assert change["classification"] in PROPOSED_SCOPE_CLASSIFICATIONS, (
                f"Proposed scope includes {change['classification']} change {change['id']}"
            )

    def test_proposed_scope_is_not_empty(self):
        """Proposed v0.2 scope must contain at least one change."""
        proposed = proposed_v02_scope()
        assert len(proposed) > 0, "Proposed v0.2 scope is empty"

    def test_proposed_scope_is_subset_of_all_changes(self):
        """Proposed scope must be a proper subset of all changes."""
        proposed = proposed_v02_scope()
        assert len(proposed) < len(V02_CHANGES), (
            "Proposed scope equals all changes — nothing was cut"
        )

    def test_exactly_eleven_changes_exist(self):
        """The v0.2 change spec must contain exactly 11 changes."""
        assert len(V02_CHANGES) == 11, (
            f"Expected 11 changes, got {len(V02_CHANGES)}"
        )


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_extraction_is_priority_1(self):
        """All extraction-layer changes must be priority 1."""
        for change in V02_CHANGES:
            if change["layer"] == "extraction":
                assert change["priority"] == 1, (
                    f"Extraction change {change['id']} is not priority 1"
                )

    def test_parser_is_priority_2(self):
        """Parser/transformation changes should be priority 2."""
        for change in V02_CHANGES:
            if change["layer"] == "transformation" and "PARSER_FAILURE" in change["failure_causes"]:
                assert change["priority"] == 2, (
                    f"Parser change {change['id']} is not priority 2"
                )

    def test_mapper_is_priority_3(self):
        """Mapper changes should be priority 3 (lowest)."""
        for change in V02_CHANGES:
            if change["layer"] == "transformation" and "SEMANTIC_MAPPING_FAILURE" in change["failure_causes"]:
                assert change["priority"] == 3, (
                    f"Mapper change {change['id']} is not priority 3"
                )

    def test_priority_1_has_more_changes_than_priority_2(self):
        """Extraction (priority 1) should have the most changes — it's the bottleneck."""
        p1 = sum(1 for c in V02_CHANGES if c["priority"] == 1)
        p2 = sum(1 for c in V02_CHANGES if c["priority"] == 2)
        assert p1 >= p2, "Priority 1 should have at least as many changes as priority 2"

    def test_priority_1_has_more_changes_than_priority_3(self):
        p1 = sum(1 for c in V02_CHANGES if c["priority"] == 1)
        p3 = sum(1 for c in V02_CHANGES if c["priority"] == 3)
        assert p1 >= p3, "Priority 1 should have at least as many changes as priority 3"


# ---------------------------------------------------------------------------
# Mapper changes have "DO NOT implement" notes
# ---------------------------------------------------------------------------


class TestMapperChangesHaveNotes:
    def test_priority_3_changes_have_do_not_implement_note(self):
        """Mapper changes (priority 3) should have a 'DO NOT implement' note."""
        for change in V02_CHANGES:
            if change["priority"] == 3:
                assert "note" in change, (
                    f"Priority 3 change {change['id']} should have a note"
                )
                assert "DO NOT implement" in change["note"], (
                    f"Priority 3 change {change['id']} note should say 'DO NOT implement'"
                )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


class TestReportRendering:
    def test_report_contains_all_changes(self):
        report = render_change_spec()
        for change in V02_CHANGES:
            assert change["id"] in report, f"Change {change['id']} not in report"
            assert change["title"] in report, f"Change {change['title']} not in report"

    def test_report_contains_priority_sections(self):
        report = render_change_spec()
        assert "Priority 1" in report
        assert "Priority 2" in report
        assert "Priority 3" in report

    def test_report_contains_design_principle(self):
        report = render_change_spec()
        assert "sounds useful" in report.lower()

    def test_report_contains_frozen_reference(self):
        report = render_change_spec()
        assert "chain-study-v2-development" in report
        assert "fb0862d" in report

    def test_report_contains_what_v02_does_not_include(self):
        report = render_change_spec()
        assert "Does NOT Include" in report or "does not include" in report.lower()

    def test_report_contains_expected_impact(self):
        report = render_change_spec()
        assert "Expected Impact" in report

    def test_report_contains_classification_scheme(self):
        report = render_change_spec()
        assert "Classification Scheme" in report
        assert "MUST FIX" in report
        assert "SHOULD FIX" in report
        assert "DEFER" in report
        assert "REJECT" in report

    def test_report_contains_proposed_scope(self):
        report = render_change_spec()
        assert "Proposed v0.2 Scope" in report
        assert "MUST FIX + SHOULD FIX" in report
        assert "pending review" in report.lower()

    def test_report_contains_classification_for_each_change(self):
        report = render_change_spec()
        for change in V02_CHANGES:
            assert change["classification"] in report, (
                f"Classification {change['classification']} for "
                f"{change['id']} not in report"
            )

    def test_report_contains_classification_rationale_for_each_change(self):
        report = render_change_spec()
        assert "Classification rationale" in report


# ---------------------------------------------------------------------------
# Cross-module invariant: change spec traces to failure matrix
# ---------------------------------------------------------------------------


FAILURE_MATRIX = Path("results/failure_matrix.json")
CHANGE_SPEC_JSON = Path("results/v02_change_spec.json")


@pytest.mark.skipif(
    not FAILURE_MATRIX.exists(),
    reason="Failure matrix not available",
)
class TestChangeSpecTracesToFailureMatrix:
    def _load(self):
        with open(FAILURE_MATRIX, encoding="utf-8") as f:
            fm = json.load(f)
        return fm, {c["chain_id"]: c for c in fm["chains"]}

    def test_every_affected_chain_exists_in_matrix(self):
        _fm, fm_by_id = self._load()
        for change in V02_CHANGES:
            for chain_id in change["affected_chains"]:
                assert chain_id in fm_by_id, (
                    f"Change {change['id']} references unknown chain: {chain_id}"
                )

    def test_every_affected_chain_has_listed_cause(self):
        """Every affected chain must have at least one of the listed failure causes.

        This invariant only holds for UNIMPLEMENTED changes (DEFER/REJECT).
        The implemented changes (MUST FIX/SHOULD FIX, V02-001 through V02-006)
        intentionally remove the listed cause from successfully fixed chains
        — that is the whole point of the fix.  The post-fix state of those
        chains is verified by test_v02_regression.py.
        """
        _fm, fm_by_id = self._load()
        for change in V02_CHANGES:
            if change["classification"] in PROPOSED_SCOPE_CLASSIFICATIONS:
                # Implemented change: the cause may have been resolved.
                continue
            for chain_id in change["affected_chains"]:
                chain = fm_by_id[chain_id]
                has_any = any(
                    chain["causes"].get(cause, False)
                    for cause in change["failure_causes"]
                )
                flagged = [k for k, v in chain["causes"].items() if v]
                assert has_any, (
                    f"Change {change['id']} attributes {change['failure_causes']} "
                    f"to {chain_id} but matrix flags: {flagged}"
                )

    def test_study_013_traces_to_unsupported_format(self):
        """V02-009 should trace to STUDY-013 with UNSUPPORTED_DOCUMENT_FORMAT."""
        _fm, fm_by_id = self._load()
        v02_009 = next(c for c in V02_CHANGES if c["id"] == "V02-009")
        assert "STUDY-013" in v02_009["affected_chains"]
        assert "UNSUPPORTED_DOCUMENT_FORMAT" in v02_009["failure_causes"]
        # Verify the matrix now flags STUDY-013 as UNSUPPORTED_DOCUMENT_FORMAT
        study_013 = fm_by_id["STUDY-013"]
        assert study_013["causes"].get("UNSUPPORTED_DOCUMENT_FORMAT", False), (
            "STUDY-013 must be flagged as UNSUPPORTED_DOCUMENT_FORMAT in the failure matrix"
        )


@pytest.mark.skipif(
    not CHANGE_SPEC_JSON.exists(),
    reason="v02_change_spec.json not available",
)
class TestChangeSpecJSON:
    def test_json_has_frozen_commit(self):
        with open(CHANGE_SPEC_JSON, encoding="utf-8") as f:
            data = json.load(f)
        assert data["frozen_commit"] == "fb0862d"

    def test_json_has_principle(self):
        with open(CHANGE_SPEC_JSON, encoding="utf-8") as f:
            data = json.load(f)
        assert "principle" in data
        assert "trace" in data["principle"].lower() or "failure" in data["principle"].lower()

    def test_json_changes_match_module(self):
        with open(CHANGE_SPEC_JSON, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["changes"]) == len(V02_CHANGES)

    def test_json_has_classifications(self):
        with open(CHANGE_SPEC_JSON, encoding="utf-8") as f:
            data = json.load(f)
        assert "classifications" in data
        assert "MUST FIX" in data["classifications"]
        assert "SHOULD FIX" in data["classifications"]
        assert "DEFER" in data["classifications"]
        assert "REJECT" in data["classifications"]

    def test_json_has_proposed_scope(self):
        with open(CHANGE_SPEC_JSON, encoding="utf-8") as f:
            data = json.load(f)
        assert "proposed_scope" in data
        assert data["proposed_scope"]["change_count"] == len(proposed_v02_scope())
        proposed_ids = set(data["proposed_scope"]["change_ids"])
        expected_ids = {c["id"] for c in proposed_v02_scope()}
        assert proposed_ids == expected_ids, "Proposed scope IDs mismatch"
        assert data["proposed_scope"]["status"] == "pending human review"

    def test_json_every_change_has_classification(self):
        with open(CHANGE_SPEC_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for change in data["changes"]:
            assert "classification" in change, (
                f"Change {change['id']} missing classification in JSON"
            )
            assert change["classification"] in CLASSIFICATIONS
