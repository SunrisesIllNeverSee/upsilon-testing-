"""Tests for the Development Chain Study v1 harness.

These tests verify:
  1. The chain study manifest is well-formed.
  2. chain_study_chains.all_study_chains() returns 25 IssuerChain objects.
  3. Each chain has S0 + >=2 amendments.
  4. The frozen semantic pipeline runs on each chain without error.
  5. The false authoritative promotion rate is 0 (safety check).
  6. The study report is generated and contains required sections.
  7. classify_failure correctly distinguishes SUCCESS from failures.
  8. Composite exhibit detection works for amended-and-restated sources.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from research.chain_study_chains import all_study_chains, existing_study_chains, new_study_chains
from research.run_chain_study import classify_failure
from upsilon.pipeline.semantic_pipeline import run_semantic_pipeline

# ---------------------------------------------------------------------------
# Data availability guards
#
# data/ is gitignored so chain study data and existing EDGAR chain source
# files are absent in CI.  Tests that depend on real EDGAR source files
# or the chain study manifest skip gracefully when the files are not
# present, following the pattern established in test_semantic_regression.py
# (commit cabb5c5: "Skip corpus-dependent tests when source files absent
# in CI").
# ---------------------------------------------------------------------------

_CHAIN_STUDY_MANIFEST = Path("data/chain_study/manifest.json")
_EDGAR_CHAINS_DIR = Path("data/edgar_chains")


def _require_chain_study_data() -> None:
    """Skip test if the chain study manifest is absent (CI environment)."""
    if not _CHAIN_STUDY_MANIFEST.exists():
        pytest.skip("chain study data not available (data/ is gitignored)")


def _require_edgar_chain_source_files() -> None:
    """Skip test if existing EDGAR chain source files are absent (CI)."""
    ameresco_a1 = _EDGAR_CHAINS_DIR / "ameresco" / "A1_amend_2023_08.txt"
    if not ameresco_a1.exists():
        pytest.skip("EDGAR chain source files not available (data/ is gitignored)")


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


def test_chain_study_manifest_exists():
    """The chain study manifest must exist after acquisition."""
    _require_chain_study_data()
    assert _CHAIN_STUDY_MANIFEST.exists(), (
        "data/chain_study/manifest.json not found. "
        "Run: set -a && source .env && set +a && python acquire_chain_study.py"
    )


def test_chain_study_manifest_well_formed():
    """The manifest must have the expected schema."""
    _require_chain_study_data()
    manifest = json.loads(_CHAIN_STUDY_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["study"] == "development_chain_study_v1"
    assert manifest["frozen_version"] == "semantic-mapper-v0.1"
    assert "chains" in manifest
    assert len(manifest["chains"]) == 22, "Expected 22 new chains in manifest"
    for entry in manifest["chains"]:
        assert "chain_id" in entry
        assert "cik" in entry
        assert "issuer" in entry
        assert "s0_accession" in entry
        assert "amendment_accessions" in entry
        assert len(entry["amendment_accessions"]) >= 2, (
            f"{entry['chain_id']}: each chain must have >=2 amendments"
        )
        assert "documents" in entry
        for doc in entry["documents"]:
            assert "html_sha256" in doc, "each document must have html_sha256"
            assert "text_sha256" in doc, "each document must have text_sha256"
            assert "document_url" in doc, "each document must have document_url"
            assert "accession" in doc, "each document must have accession"


# ---------------------------------------------------------------------------
# Chain builder tests
# ---------------------------------------------------------------------------


def test_all_study_chains_returns_25():
    """all_study_chains() must return exactly 25 chains."""
    _require_chain_study_data()
    chains = all_study_chains()
    assert len(chains) == 25, f"Expected 25 chains, got {len(chains)}"


def test_existing_chains_have_ground_truth():
    """The 3 existing chains must have ground truth."""
    chains = existing_study_chains()
    assert len(chains) == 3
    for chain in chains:
        assert chain.ground_truth_state is not None
        assert len(chain.ground_truth_state) > 0
        assert chain.is_synthetic is False


def test_new_chains_are_real_edgar():
    """The 22 new chains must be real EDGAR (not synthetic)."""
    _require_chain_study_data()
    chains = new_study_chains()
    assert len(chains) == 22
    for chain in chains:
        assert chain.is_synthetic is False


def test_each_chain_has_s0_plus_2_amendments():
    """Each chain must have S0 state + >=2 amendments."""
    _require_chain_study_data()
    chains = all_study_chains()
    for chain in chains:
        assert len(chain.amendments) >= 2, (
            f"{chain.chain_id}: must have >=2 amendments, got {len(chain.amendments)}"
        )


def test_each_amendment_has_source_document():
    """Each amendment step must have a source_document_path that exists."""
    _require_chain_study_data()
    _require_edgar_chain_source_files()
    chains = all_study_chains()
    for chain in chains:
        for step in chain.amendments:
            assert step.source_document_path is not None, (
                f"{chain.chain_id} A{step.amendment_number}: no source_document_path"
            )
            assert Path(step.source_document_path).exists(), (
                f"{chain.chain_id} A{step.amendment_number}: "
                f"source file not found: {step.source_document_path}"
            )


def test_each_amendment_has_pattern():
    """Each amendment step must have a pattern classification."""
    _require_chain_study_data()
    chains = all_study_chains()
    for chain in chains:
        for step in chain.amendments:
            assert step.pattern is not None, (
                f"{chain.chain_id} A{step.amendment_number}: no pattern"
            )
            assert step.pattern in ("incremental", "full_restatement", "conformed_copy", "unknown")


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


def test_pipeline_runs_on_all_chains():
    """The frozen semantic pipeline must run on all 25 chains without error."""
    _require_chain_study_data()
    _require_edgar_chain_source_files()
    chains = all_study_chains()
    for chain in chains:
        result = run_semantic_pipeline(chain)
        assert result is not None
        assert result.chain_id == chain.chain_id


def test_false_authoritative_promotion_rate_is_zero():
    """SAFETY: the false authoritative promotion rate must be 0.

    A false authoritative promotion occurs when a step is marked
    is_authoritative=True but has unresolved instructions (own or
    inherited).  This is the primary safety/integrity guarantee.
    """
    _require_chain_study_data()
    _require_edgar_chain_source_files()
    chains = all_study_chains()
    false_promotions = 0
    for chain in chains:
        result = run_semantic_pipeline(chain)
        for step in result.steps:
            own_unresolved = (
                len(step.mapper_unresolved)
                + len(step.execution_result.unresolved)
            )
            if step.is_authoritative and (
                own_unresolved > 0 or step.inherited_unresolved_count > 0
            ):
                false_promotions += 1
    assert false_promotions == 0, (
        f"SAFETY VIOLATION: {false_promotions} false authoritative promotions detected"
    )


def test_no_incorrect_mutations_on_existing_chains():
    """The 3 existing chains (with ground truth) must have 0 incorrect mutations."""
    _require_edgar_chain_source_files()
    chains = existing_study_chains()
    for chain in chains:
        result = run_semantic_pipeline(chain)
        assert len(result.incorrect_mutations) == 0, (
            f"{chain.chain_id}: {len(result.incorrect_mutations)} incorrect mutations"
        )


# ---------------------------------------------------------------------------
# Report tests
# ---------------------------------------------------------------------------


def test_study_report_contains_required_sections():
    """The study report must contain all required sections."""
    report_path = Path("results/chain_study_v1_report.md")
    if not report_path.exists():
        pytest.skip("chain study report not found — run run_chain_study.py first")
    report = report_path.read_text(encoding="utf-8")
    required_sections = [
        "# Development Chain Study v1",
        "## Study Protocol",
        "## Per-Issuer Results",
        "## Per-Step Detail",
        "## Aggregate Metrics",
        "## Safety Check",
        "## Failure Taxonomy",
        "## Known First-Pass Limitations",
        "## Conclusion",
    ]
    for section in required_sections:
        assert section in report, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# classify_failure tests (Issue 2 fix: SUCCESS override)
# ---------------------------------------------------------------------------


def _mock_pipeline_result(
    total_parser: int = 0,
    total_mapped: int = 0,
    total_unresolved: int = 0,
    incorrect_mutation_rate: float = 0.0,
    mapping_accuracy: float = 1.0,
    final_state_agreement: float = 1.0,
    steps_authoritative: bool = False,
    steps_partial: bool = False,
):
    """Build a mock SemanticPipelineResult for classify_failure testing."""
    step = MagicMock()
    step.is_authoritative = steps_authoritative
    step.execution_result.status.value = "PARTIAL" if steps_partial else "COMPLETE"
    result = MagicMock()
    result.total_parser_instructions = total_parser
    result.total_mapped = total_mapped
    result.total_unresolved = total_unresolved
    result.incorrect_mutation_rate = incorrect_mutation_rate
    result.mapping_accuracy = mapping_accuracy
    result.final_state_agreement = final_state_agreement
    result.steps = [step]
    return result


def _mock_chain():
    """Build a minimal mock IssuerChain (fields not accessed by classify_failure)."""
    return MagicMock()


def test_classify_failure_success_with_unresolved():
    """Ameresco scenario: parser>0, 100% agreement, 0 incorrect, unresolved present.

    This is the core Issue 2 fix — a chain with unresolved instructions
    on out-of-model fields but 100% final-state agreement should be
    classified SUCCESS, not MULTIPLE_FAILURES.
    """
    result = _mock_pipeline_result(
        total_parser=14,
        total_mapped=3,
        total_unresolved=11,
        incorrect_mutation_rate=0.0,
        mapping_accuracy=0.21,
        final_state_agreement=1.0,
    )
    assert classify_failure(result, _mock_chain(), has_ground_truth=True) == "SUCCESS"


def test_classify_failure_parser_no_instructions():
    """Amedisys/Bausch-Lomb scenario: 0 parser instructions → PARSER_NO_INSTRUCTIONS.

    Even with 100% final-state agreement (trivial), 0 parser instructions
    means no reconstruction happened — this is 'unsupported format', not
    'reconstruction succeeded'.
    """
    result = _mock_pipeline_result(
        total_parser=0,
        final_state_agreement=1.0,
    )
    assert classify_failure(result, _mock_chain(), has_ground_truth=True) == "PARSER_NO_INSTRUCTIONS"


def test_classify_failure_success_requires_ground_truth():
    """Without ground truth, even with no incorrect mutations → SYSTEM_INGESTION_PASS.

    The system behaved correctly (no incorrect mutations, no false
    promotion) but reconstruction cannot be verified without ground
    truth.  This is SYSTEM_INGESTION_PASS, not SUCCESS.
    """
    result = _mock_pipeline_result(
        total_parser=10,
        total_mapped=10,
        final_state_agreement=1.0,
    )
    assert classify_failure(result, _mock_chain(), has_ground_truth=False) == "SYSTEM_INGESTION_PASS"


def test_classify_failure_system_ingestion_pass_with_unresolved():
    """No GT, no incorrect mutations, unresolved present → SYSTEM_INGESTION_PASS.

    The system found instructions it could not map, safely marked them
    UNRESOLVED, and did not falsely promote.  This is correct system
    behavior, not a failure.
    """
    result = _mock_pipeline_result(
        total_parser=11,
        total_mapped=0,
        total_unresolved=11,
        incorrect_mutation_rate=0.0,
        mapping_accuracy=0.0,
    )
    assert classify_failure(result, _mock_chain(), has_ground_truth=False) == "SYSTEM_INGESTION_PASS"


def test_classify_failure_incorrect_mutations_no_gt():
    """No GT but incorrect mutations present → real failure, not SYSTEM_INGESTION_PASS.

    Incorrect automatic mutations are a real failure regardless of
    ground truth availability — the system produced wrong changes.
    """
    result = _mock_pipeline_result(
        total_parser=4,
        total_mapped=1,
        total_unresolved=3,
        incorrect_mutation_rate=1.0,
        mapping_accuracy=0.25,
    )
    cat = classify_failure(result, _mock_chain(), has_ground_truth=False)
    assert cat != "SYSTEM_INGESTION_PASS"
    assert "INCORRECT_MUTATIONS" in cat or cat == "MULTIPLE_FAILURES"


def test_classify_failure_incorrect_mutations_blocks_success():
    """Incorrect automatic mutations block SUCCESS even with 100% agreement."""
    result = _mock_pipeline_result(
        total_parser=10,
        total_mapped=5,
        incorrect_mutation_rate=0.2,
        final_state_agreement=1.0,
    )
    assert classify_failure(result, _mock_chain(), has_ground_truth=True) != "SUCCESS"


def test_classify_failure_final_state_mismatch():
    """Parser>0, ground truth, agreement<1.0, no incorrect → FINAL_STATE_MISMATCH."""
    result = _mock_pipeline_result(
        total_parser=10,
        total_mapped=5,
        final_state_agreement=0.5,
    )
    cat = classify_failure(result, _mock_chain(), has_ground_truth=True)
    assert cat == "FINAL_STATE_MISMATCH"


def test_final_state_mismatch_in_failure_categories():
    """FINAL_STATE_MISMATCH must be present in the FAILURE_CATEGORIES dict."""
    from research.run_chain_study import FAILURE_CATEGORIES
    assert "FINAL_STATE_MISMATCH" in FAILURE_CATEGORIES, (
        "FINAL_STATE_MISMATCH is returned by classify_failure but missing "
        "from FAILURE_CATEGORIES dict — report would render empty description"
    )
    assert "SYSTEM_INGESTION_PASS" in FAILURE_CATEGORIES, (
        "SYSTEM_INGESTION_PASS is returned by classify_failure but missing "
        "from FAILURE_CATEGORIES dict"
    )


def test_classify_failure_ameresesco_actual():
    """Verify the actual Ameresco chain classifies as SUCCESS."""
    _require_edgar_chain_source_files()
    chains = existing_study_chains()
    ameresco = next(c for c in chains if "AMERESCO" in c.chain_id)
    result = run_semantic_pipeline(ameresco)
    has_gt = ameresco.ground_truth_state is not None and len(ameresco.ground_truth_state) > 0
    assert classify_failure(result, ameresco, has_gt) == "SUCCESS"


def test_classify_failure_amedisys_actual():
    """Verify the actual Amedisys chain classifies as PARSER_NO_INSTRUCTIONS."""
    _require_edgar_chain_source_files()
    chains = existing_study_chains()
    amedisys = next(c for c in chains if "AMEDISYS" in c.chain_id)
    result = run_semantic_pipeline(amedisys)
    has_gt = amedisys.ground_truth_state is not None and len(amedisys.ground_truth_state) > 0
    assert classify_failure(result, amedisys, has_gt) == "PARSER_NO_INSTRUCTIONS"


def test_classify_failure_bausch_lomb_actual():
    """Verify the actual Bausch-Lomb chain classifies as PARSER_NO_INSTRUCTIONS."""
    _require_edgar_chain_source_files()
    chains = existing_study_chains()
    bausch = next(c for c in chains if "BAUSCH" in c.chain_id)
    result = run_semantic_pipeline(bausch)
    has_gt = bausch.ground_truth_state is not None and len(bausch.ground_truth_state) > 0
    assert classify_failure(result, bausch, has_gt) == "PARSER_NO_INSTRUCTIONS"


# ---------------------------------------------------------------------------
# Composite exhibit detection tests (Issue 1 fix)
# ---------------------------------------------------------------------------


def test_is_composite_exhibit_amended_and_restated():
    """Amended and restated credit agreements are detected as composite."""
    from upsilon.ingestion.acquire_chain_study import is_composite_exhibit
    assert is_composite_exhibit("AMENDED AND RESTATED CREDIT AGREEMENT")
    assert is_composite_exhibit("Amended & Restated Credit Agreement")


def test_is_composite_exhibit_restated():
    """Restated credit agreements are detected as composite."""
    from upsilon.ingestion.acquire_chain_study import is_composite_exhibit
    assert is_composite_exhibit("RESTATED CREDIT AGREEMENT")


def test_is_composite_exhibit_conformed():
    """Conformed copies are detected as composite."""
    from upsilon.ingestion.acquire_chain_study import is_composite_exhibit
    assert is_composite_exhibit("CONFORMED COPY OF CREDIT AGREEMENT")


def test_is_composite_exhibit_not_incremental_amendment():
    """Incremental amendments are NOT composite sources."""
    from upsilon.ingestion.acquire_chain_study import is_composite_exhibit
    assert not is_composite_exhibit("SECOND AMENDMENT TO CREDIT AGREEMENT")
    assert not is_composite_exhibit("FIFTH AMENDMENT TO CREDIT AGREEMENT")


def test_is_composite_exhibit_not_plain_credit_agreement():
    """A plain credit agreement (S0) is NOT a composite source."""
    from upsilon.ingestion.acquire_chain_study import is_composite_exhibit
    assert not is_composite_exhibit("CREDIT AGREEMENT")


def test_manifest_has_comparison_source_fields():
    """Each manifest chain entry must have comparison source fields."""
    _require_chain_study_data()
    manifest = json.loads(_CHAIN_STUDY_MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["chains"]:
        assert "comparison_source_accession" in entry, (
            f"{entry['chain_id']}: missing comparison_source_accession field"
        )
        assert "comparison_source_file_date" in entry, (
            f"{entry['chain_id']}: missing comparison_source_file_date field"
        )
        assert "comparison_source_kind" in entry, (
            f"{entry['chain_id']}: missing comparison_source_kind field"
        )


# ---------------------------------------------------------------------------
# S0 != A1 collision regression tests
# ---------------------------------------------------------------------------


def test_no_s0_amendment_accession_collision():
    """S0 accession must never equal any amendment accession.

    Regression test for the amendment-as-S0 fallback bug in
    find_s0_for_cik that mislabeled amendment filings as the original
    credit agreement (S0), corrupting chain provenance.
    """
    _require_chain_study_data()
    manifest = json.loads(_CHAIN_STUDY_MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["chains"]:
        s0 = entry["s0_accession"]
        amendments = entry["amendment_accessions"]
        assert s0 not in amendments, (
            f"{entry['chain_id']}: S0 accession {s0} is also an "
            f"amendment accession — chain provenance is corrupted"
        )


def test_no_duplicate_chain_ids():
    """All chain_ids in the manifest must be unique."""
    _require_chain_study_data()
    manifest = json.loads(_CHAIN_STUDY_MANIFEST.read_text(encoding="utf-8"))
    ids = [c["chain_id"] for c in manifest["chains"]]
    from collections import Counter
    dups = {k: v for k, v in Counter(ids).items() if v > 1}
    assert not dups, f"Duplicate chain_ids in manifest: {dups}"


# ---------------------------------------------------------------------------
# Semantic mapping precision metric tests
# ---------------------------------------------------------------------------


def test_semantic_mapping_precision_accounts_for_incorrect_mutations():
    """Precision = correct_mapped / total_mapped, NOT mapped / parser.

    Regression test for the metric labeling bug where semantic_mapping_precision
    was computed as coverage (mapped/parser) instead of true precision
    (correct_mapped / total_mapped where correct = mapped - incorrect).
    """
    from unittest.mock import MagicMock
    from research.run_chain_study import AggregateMetrics, compute_aggregate_metrics

    # Build mock issuer results: 10 parser, 4 mapped, 1 incorrect
    issuer = MagicMock()
    issuer.parser_detected_instructions = 10
    issuer.semantic_mapped_instructions = 4
    issuer.unresolved_instructions = 6
    issuer.incorrect_automatic_mutations = 1
    issuer.has_ground_truth = False
    issuer.final_state_exact_agreement = None
    issuer.lineage_complete = False
    issuer.steps = [MagicMock()]

    pipe_result = MagicMock()
    pipe_result.steps = [MagicMock()]
    pipe_result.steps[0].is_authoritative = False
    pipe_result.steps[0].mapper_unresolved = []
    pipe_result.steps[0].execution_result.unresolved = []
    pipe_result.steps[0].inherited_unresolved_count = 0

    metrics = compute_aggregate_metrics([issuer], [pipe_result])

    # Precision = (4 - 1) / 4 = 0.75, NOT 4/10 = 0.4
    assert metrics.semantic_mapping_precision == 0.75, (
        f"Expected precision=0.75 (correct_mapped/total_mapped), "
        f"got {metrics.semantic_mapping_precision}"
    )
    # Coverage = 4 / 10 = 0.4
    assert metrics.semantic_mapping_coverage == 0.4, (
        f"Expected coverage=0.4 (mapped/parser), "
        f"got {metrics.semantic_mapping_coverage}"
    )


# ---------------------------------------------------------------------------
# Supported-field agreement tests (Fix #2: independent computation)
# ---------------------------------------------------------------------------


def test_supported_field_agreement_field_level():
    """supported_field_agreement measures field-level agreement, not
    commitment-level exact match.

    With 1 GT commitment that has 8 supported fields, where 7 of 8
    fields match: final_state_agreement = 0% (commitment doesn't match
    exactly), but supported_field_agreement = 87.5% (7/8 fields match).
    """
    from research.run_chain_study import _compute_supported_field_agreement
    from upsilon.models.legacy_models import CommitmentState

    gt = {"commitment_1": CommitmentState(
        canonical_key="commitment_1", commitment_type="covenant",
        threshold=100.0, rate=5.0, deadline="2024-01-01",
        party=["Lender"], exceptions=["A"], applicability={"scope": "All"},
        status="Active", unit="USD",
    )}
    recon = {"commitment_1": CommitmentState(
        canonical_key="commitment_1", commitment_type="covenant",
        threshold=100.0, rate=5.0, deadline="2024-01-01",
        party=["Lender"], exceptions=["A"], applicability={"scope": "All"},
        status="Active", unit="EUR",  # 1 field differs
    )}
    sfa = _compute_supported_field_agreement(recon, gt)
    assert sfa is not None
    # 7 of 8 fields match → 0.875
    assert abs(sfa - 0.875) < 0.001, f"Expected 0.875, got {sfa}"


def test_supported_field_agreement_missing_commitment():
    """A missing commitment counts all its fields as mismatched."""
    from research.run_chain_study import _compute_supported_field_agreement
    from upsilon.models.legacy_models import CommitmentState

    gt = {
        "c1": CommitmentState(
            canonical_key="c1", commitment_type="covenant",
            threshold=100.0, rate=5.0, deadline="2024-01-01",
            party=["L"], exceptions=[], applicability={},
            status="Active", unit="USD",
        ),
        "c2": CommitmentState(
            canonical_key="c2", commitment_type="covenant",
            threshold=200.0, rate=6.0, deadline="2025-01-01",
            party=["M"], exceptions=[], applicability={},
            status="Active", unit="EUR",
        ),
    }
    recon = {"c1": gt["c1"]}  # c2 is missing
    sfa = _compute_supported_field_agreement(recon, gt)
    # c1: 8/8 match. c2: 0/8 match. Total: 8/16 = 0.5
    assert sfa is not None
    assert abs(sfa - 0.5) < 0.001, f"Expected 0.5, got {sfa}"


def test_supported_field_agreement_no_ground_truth():
    """Returns None when there is no ground truth."""
    from research.run_chain_study import _compute_supported_field_agreement
    sfa = _compute_supported_field_agreement({}, {})
    assert sfa is None


def test_supported_field_agreement_differs_from_final_state_agreement():
    """On the actual Ameresco chain, supported_field_agreement may differ
    from final_state_agreement because it measures field-level agreement."""
    _require_edgar_chain_source_files()
    from research.run_chain_study import build_issuer_result
    chains = existing_study_chains()
    ameresco = next(c for c in chains if "AMERESCO" in c.chain_id)
    result = run_semantic_pipeline(ameresco)
    issuer_result = build_issuer_result(ameresco, result)
    # Ameresco has 100% final-state exact agreement
    assert issuer_result.final_state_exact_agreement == 1.0
    # Supported-field agreement should also be 100% (all fields match)
    # but it is computed independently, not re-derived
    assert issuer_result.supported_field_agreement is not None
    assert issuer_result.supported_field_agreement == 1.0


# ---------------------------------------------------------------------------
# chain_authoritative vs lineage_complete tests (Fix #3: differentiation)
# ---------------------------------------------------------------------------


def test_chain_authoritative_vs_lineage_complete_ameresco():
    """Ameresco: lineage complete (all steps COMPLETE) but NOT chain
    authoritative (final step has unresolved → not authoritative).

    This is the key differentiation: Ameresco reconstructed correctly
    (100% agreement) but the final step is not authoritative due to
    unresolved instructions on out-of-model fields.
    """
    _require_edgar_chain_source_files()
    from research.run_chain_study import build_issuer_result
    chains = existing_study_chains()
    ameresco = next(c for c in chains if "AMERESCO" in c.chain_id)
    result = run_semantic_pipeline(ameresco)
    issuer_result = build_issuer_result(ameresco, result)
    # Ameresco has unresolved instructions → final step not authoritative
    assert issuer_result.chain_authoritative is False, (
        "Ameresco should NOT be chain_authoritative (unresolved on final step)"
    )
    # But all steps executed COMPLETEly
    assert issuer_result.lineage_complete is True, (
        "Ameresco SHOULD be lineage_complete (all steps COMPLETE)"
    )


def test_chain_authoritative_vs_lineage_complete_amedisys():
    """Amedisys: both chain_authoritative and lineage_complete are True.

    0 parser instructions → vacuously authoritative (no unresolved),
    all steps COMPLETE.
    """
    _require_edgar_chain_source_files()
    from research.run_chain_study import build_issuer_result
    chains = existing_study_chains()
    amedisys = next(c for c in chains if "AMEDISYS" in c.chain_id)
    result = run_semantic_pipeline(amedisys)
    issuer_result = build_issuer_result(amedisys, result)
    assert issuer_result.chain_authoritative is True
    assert issuer_result.lineage_complete is True


def test_chain_authoritative_requires_final_step_authoritative():
    """chain_authoritative checks the FINAL step, not all steps.

    A chain where step 1 is authoritative but step 2 is not should
    be NOT chain_authoritative.
    """
    from unittest.mock import MagicMock
    from research.run_chain_study import build_issuer_result

    step1 = MagicMock()
    step1.is_authoritative = True
    step1.execution_result.status.value = "COMPLETE"
    step1.mapper_unresolved = []
    step1.execution_result.unresolved = []
    step1.inherited_unresolved_count = 0
    step1.amendment_number = 1
    step1.effective_at = MagicMock()
    step1.effective_at.isoformat.return_value = "2024-01-01T00:00:00"
    step1.pattern = "incremental"
    step1.parser_instruction_count = 5
    step1.mapper_mutations = []

    step2 = MagicMock()
    step2.is_authoritative = False  # final step NOT authoritative
    step2.execution_result.status.value = "COMPLETE"
    step2.mapper_unresolved = [MagicMock()]
    step2.execution_result.unresolved = []
    step2.inherited_unresolved_count = 0
    step2.amendment_number = 2
    step2.effective_at = MagicMock()
    step2.effective_at.isoformat.return_value = "2024-06-01T00:00:00"
    step2.pattern = "incremental"
    step2.parser_instruction_count = 3
    step2.mapper_mutations = []

    pipe_result = MagicMock()
    pipe_result.steps = [step1, step2]
    pipe_result.chain_id = "TEST"
    pipe_result.issuer_name = "Test (CIK 0000000000)"
    pipe_result.total_parser_instructions = 8
    pipe_result.total_mapped = 5
    pipe_result.total_unresolved = 3
    pipe_result.incorrect_mutations = []
    pipe_result.incorrect_mutation_rate = 0.0
    pipe_result.mapping_accuracy = 1.0
    pipe_result.final_state_agreement = 1.0
    pipe_result.reconstructed_state = {}
    pipe_result.state_mismatches = []

    chain = MagicMock()
    chain.chain_id = "TEST"
    chain.issuer_name = "Test (CIK 0000000000)"
    chain.ground_truth_state = {}
    chain.amendments = [MagicMock(), MagicMock()]
    chain.comparison_at = MagicMock()
    chain.comparison_at.isoformat.return_value = "2024-06-01T00:00:00"

    result = build_issuer_result(chain, pipe_result)
    assert result.chain_authoritative is False, (
        "chain_authoritative should be False when final step is not authoritative"
    )
    assert result.lineage_complete is True, (
        "lineage_complete should be True when all steps are COMPLETE"
    )
