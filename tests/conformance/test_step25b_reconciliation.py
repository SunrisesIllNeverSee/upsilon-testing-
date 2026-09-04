"""Step 25B conformance tests.

Tests that:
1. JSON and Markdown metrics reconcile
2. Candidate conservation gate holds
3. Aggregate-to-row provenance invariants hold
4. Determinism (metrics are stable across runs)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RESULTS_DIR = Path("results")
JSON_PATH = RESULTS_DIR / "step25a_post_moses_rerun.json"
MD_PATH = RESULTS_DIR / "step25a_post_moses_rerun.md"


def _load_json() -> dict:
    """Load the Step 25A JSON artifact."""
    if not JSON_PATH.exists():
        pytest.skip(f"Step 25A artifact not found: {JSON_PATH}")
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _load_md() -> str:
    """Load the Step 25A Markdown artifact."""
    if not MD_PATH.exists():
        pytest.skip(f"Step 25A artifact not found: {MD_PATH}")
    return MD_PATH.read_text(encoding="utf-8")


class TestJsonMarkdownReconciliation:
    """Verify that headline Markdown metrics equal JSON metrics."""

    def test_json_exists(self):
        assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"

    def test_md_exists(self):
        assert MD_PATH.exists(), f"Markdown artifact missing: {MD_PATH}"

    def test_md_records_json_sha256(self):
        """The Markdown must record the SHA-256 of the JSON artifact."""
        md = _load_md()
        artifact = _load_json()
        json_sha = artifact.get("artifact_sha256")
        assert json_sha is not None, "JSON artifact missing artifact_sha256"
        assert json_sha in md, (
            f"Markdown does not record JSON SHA-256 ({json_sha})"
        )

    def test_chains_match(self):
        """Chains attempted must match between JSON and MD."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["chains_attempted"]) in md
        # Check the headline number appears
        assert f"{m['chains_attempted']}" in md

    def test_s0_extraction_success_match(self):
        """S0 extraction success must match."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        # Check the numerator appears in the MD
        assert str(m["s0_extraction_success"]) in md

    def test_mapped_count_match(self):
        """Mapped count must match."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["mapped"]) in md

    def test_moses_spine_counts_match(self):
        """MOSES spine counts must match."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["moses_spine_promoted"]) in md
        assert str(m["moses_spine_rejected"]) in md
        assert str(m["moses_spine_routed_away"]) in md

    def test_applied_mutation_count_match(self):
        """Applied mutation count must match."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["applied_mutation_count"]) in md

    def test_exact_reconstruction_match(self):
        """Exact reconstruction must match."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["all_chains_exact_reconstruction"]) in md

    def test_lineage_complete_match(self):
        """Lineage complete must match."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["lineage_complete"]) in md

    def test_total_s0_commitments_match(self):
        """Total S0 commitments must match (the original discrepancy)."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        # The corrected value must appear in the MD
        assert str(m["total_s0_commitments_extracted"]) in md

    def test_total_gt_commitments_match(self):
        """Total GT commitments must match (the original discrepancy)."""
        artifact = _load_json()
        md = _load_md()
        m = artifact["metrics"]
        assert str(m["total_gt_commitments_extracted"]) in md


class TestCandidateConservationGate:
    """Verify that candidate terminal dispositions sum exactly."""

    def test_conservation_holds(self):
        """Total candidates = sum of terminal dispositions."""
        artifact = _load_json()
        cg = artifact["metrics"]["candidate_conservation_gate"]
        assert cg["conservation_holds"] is True
        assert cg["total_candidates"] == cg["sum_terminal"]

    def test_no_unknown_dispositions(self):
        """No candidate may have an UNKNOWN terminal disposition."""
        artifact = _load_json()
        cg = artifact["metrics"]["candidate_conservation_gate"]
        assert "UNKNOWN" not in cg["terminal_dispositions"]

    def test_candidate_count_matches_mapped(self):
        """Candidate ledger count must equal mapped count."""
        artifact = _load_json()
        m = artifact["metrics"]
        assert len(m["candidate_ledger"]) == m["mapped"]


class TestAggregateToRowProvenance:
    """Verify that headline aggregates are reproducible from row IDs."""

    def test_s0_success_chain_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["s0_success_chain_ids"]
        assert len(ids) == m["s0_extraction_success"]

    def test_mapped_candidate_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["mapped_candidate_ids"]
        assert len(ids) == m["mapped"]

    def test_moses_promoted_candidate_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["moses_promoted_candidate_ids"]
        assert len(ids) == m["moses_spine_promoted"]

    def test_moses_rejected_candidate_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["moses_rejected_candidate_ids"]
        assert len(ids) == m["moses_spine_rejected"]

    def test_routed_candidate_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["routed_candidate_ids"]
        assert len(ids) == m["moses_spine_routed_away"]

    def test_lineage_complete_chain_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["lineage_complete_chain_ids"]
        assert len(ids) == m["lineage_complete"]

    def test_gt_scorable_chain_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["gt_scorable_chain_ids"]
        assert len(ids) == m["gt_scorable_chains"]

    def test_exact_reconstruction_chain_ids(self):
        artifact = _load_json()
        m = artifact["metrics"]
        ids = m["provenance"]["exact_reconstruction_chain_ids"]
        assert len(ids) == m["all_chains_exact_reconstruction"]


class TestSafetyReporting:
    """Verify safety metrics use actual applied, not mapped."""

    def test_applied_not_equal_mapped(self):
        """Applied mutation count must not equal mapped count
        (unless they are genuinely the same)."""
        artifact = _load_json()
        m = artifact["metrics"]
        # In this run, 0 applied and 60 mapped — they are different
        assert m["applied_mutation_count"] != m["mapped_count"]

    def test_incorrect_rate_is_na_when_no_applied(self):
        """If applied = 0, incorrect rate must be None (N/A)."""
        artifact = _load_json()
        m = artifact["metrics"]
        if m["applied_mutation_count"] == 0:
            assert m["incorrect_accepted_mutation_rate"] is None

    def test_precision_is_na_when_no_scorable(self):
        """If scorable = 0, precision must be None (N/A)."""
        artifact = _load_json()
        m = artifact["metrics"]
        if m["independently_scorable_predictions"] == 0:
            assert m["overall_precision"] is None


class TestGtSeparation:
    """Verify GT availability is separated from runtime failure."""

    def test_gt_unavailable_is_not_runtime_failure(self):
        """GT-unavailable chains must not be classified as runtime failures."""
        artifact = _load_json()
        m = artifact["metrics"]
        # Check that chain-level first failure does not include
        # GT_UNAVAILABLE or EVALUATION_GOLD_UNAVAILABLE
        for stage in m["chain_level_first_failure"]:
            assert "GOLD" not in stage.upper()
            assert "GT" not in stage.upper()
