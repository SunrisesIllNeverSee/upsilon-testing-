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
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_failure_matrix import FAILURE_CAUSES
from v02_change_spec import V02_CHANGES, render_change_spec

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
        required = {"id", "title", "priority", "layer", "failure_causes",
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
        """Every affected chain must have at least one of the listed failure causes."""
        _fm, fm_by_id = self._load()
        for change in V02_CHANGES:
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
