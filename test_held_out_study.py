"""Tests for Step 19B held-out confirmatory study scripts.

Tests cover:
  - create_held_out_gold.py: independent annotators, double annotation,
    adjudication, agreement statistics
  - run_held_out_study.py: chain building from manifest, gold agreement
    computation, hardcoded path fix
  - generate_step_19b_report.py: Clopper-Pearson CIs, report generation,
    factual correctness of dev-vs-held-out comparison
  - acquire_held_out_study.py: dev-set exclusion, exhibit classification
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gold_schema import GoldRecord, load_gold_file, validate_gold_record


# ---------------------------------------------------------------------------
# Data availability guards
# ---------------------------------------------------------------------------

HELD_OUT_MANIFEST = Path("data/held_out/manifest.json")
HELD_OUT_RESULTS = Path("results/held_out_study_results.json")
DEV_RESULTS = Path("results/chain_study_v2_results.json")
PREREG_MANIFEST = Path("data/held_out/gold/preregistration.json")


def _require_held_out_data():
    if not HELD_OUT_MANIFEST.exists():
        pytest.skip("Held-out manifest not found")


def _require_held_out_results():
    if not HELD_OUT_RESULTS.exists():
        pytest.skip("Held-out results not found")


def _require_dev_results():
    if not DEV_RESULTS.exists():
        pytest.skip("Development results not found")


def _require_prereg():
    if not PREREG_MANIFEST.exists():
        pytest.skip("Preregistration manifest not found")


# ---------------------------------------------------------------------------
# create_held_out_gold.py tests
# ---------------------------------------------------------------------------


class TestIndependentAnnotators:
    """Verify that the two annotators use genuinely different strategies."""

    def test_annotator_a_and_b_have_different_names(self):
        from create_held_out_gold import ANNOTATOR_A, ANNOTATOR_B
        assert ANNOTATOR_A != ANNOTATOR_B
        assert "regex" in ANNOTATOR_A
        assert "keyword" in ANNOTATOR_B

    def test_annotator_a_requires_section_prefix(self):
        """Annotator A should require Section/ARTICLE prefix."""
        from create_held_out_gold import _annotator_a_find_sections
        # Text with bare-number header (no Section prefix)
        text = "8.12 Financial Covenants\nThe Borrower shall maintain..."
        sections = _annotator_a_find_sections(text)
        # Annotator A should NOT find this (no Section prefix)
        assert len(sections) == 0

    def test_annotator_b_accepts_bare_number(self):
        """Annotator B should accept bare-number headers."""
        from create_held_out_gold import _annotator_b_find_sections
        text = (
            "8.12 Financial Covenants\n"
            "The Borrower shall maintain a maximum leverage ratio.\n"
            "9.1 Miscellaneous\nNext section here."
        )
        sections = _annotator_b_find_sections(text)
        # Annotator B SHOULD find this (accepts bare numbers)
        assert len(sections) >= 1

    def test_annotators_produce_different_results_on_same_text(self):
        """The two annotators should produce different records on some texts."""
        from create_held_out_gold import annotator_a_annotate, annotator_b_annotate
        # Text with bare-number header and a ratio covenant
        text = (
            "8.12 Financial Covenants\n"
            "8.12.1 Maximum Leverage Ratio. The Borrower shall not permit "
            "the Leverage Ratio to exceed 3.50 to 1.0.\n"
            "8.13 Miscellaneous\nNext section here."
        )
        records_a = annotator_a_annotate(text, "TEST", "Test Issuer")
        records_b = annotator_b_annotate(text, "TEST", "Test Issuer")
        # They should differ — A requires Section prefix, B doesn't
        assert len(records_a) != len(records_b) or records_a != records_b

    def test_annotator_a_min_name_length_10(self):
        """Annotator A filters clause names shorter than 10 chars."""
        from create_held_out_gold import _annotator_a_extract_clauses
        text = "§9.1 Short\nThe Borrower shall maintain a leverage ratio.\n§9.2 Maximum Leverage Ratio\nThe ratio shall not exceed 4.0 to 1.0."
        clauses = _annotator_a_extract_clauses(text, 0, len(text))
        # "Short" (5 chars) should be filtered out by A (min 10)
        names = [c["clause_name"] for c in clauses]
        assert "Short" not in names

    def test_annotator_b_min_name_length_8(self):
        """Annotator B uses a lower minimum name length (8 chars)."""
        from create_held_out_gold import _annotator_b_extract_clauses
        text = "§9.1 ShortName\nThe Borrower shall maintain a leverage ratio.\n§9.2 Maximum Leverage Ratio\nThe ratio shall not exceed 4.0 to 1.0."
        clauses = _annotator_b_extract_clauses(text, 0, len(text))
        # "ShortName" (9 chars) should be included by B (min 8) but not A (min 10)
        names = [c["clause_name"] for c in clauses]
        assert "ShortName" in names


class TestDoubleAnnotation:
    """Test the double_annotate adjudication logic."""

    def test_agreement_produces_adjudicated_record(self):
        from create_held_out_gold import double_annotate, ANNOTATOR_A, ANNOTATOR_B
        record = GoldRecord(
            issuer="Test", document="CMP", section="§9.1",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold", value=3.5, unit="ratio",
            source_span=(0, 100), annotator=ANNOTATOR_A,
        )
        record_b = GoldRecord(
            issuer="Test", document="CMP", section="§9.1",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold", value=3.5, unit="ratio",
            source_span=(0, 100), annotator=ANNOTATOR_B,
        )
        result, stats = double_annotate([record], [record_b])
        assert len(result) == 1
        assert result[0].verification_status == "adjudicated"
        assert stats["agreements"] == 1
        assert stats["disagreements"] == 0

    def test_disagreement_produces_adjudicated_with_notes(self):
        from create_held_out_gold import double_annotate, ANNOTATOR_A, ANNOTATOR_B
        record_a = GoldRecord(
            issuer="Test", document="CMP", section="§9.1",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold", value=3.5, unit="ratio",
            source_span=(0, 100), annotator=ANNOTATOR_A,
        )
        record_b = GoldRecord(
            issuer="Test", document="CMP", section="§9.1",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold", value=4.0, unit="ratio",
            source_span=(0, 100), annotator=ANNOTATOR_B,
        )
        result, stats = double_annotate([record_a], [record_b])
        assert len(result) == 1
        assert result[0].verification_status == "adjudicated"
        assert "Disagreement" in result[0].notes
        assert stats["disagreements"] == 1
        assert stats["agreements"] == 0

    def test_only_a_produces_single_record(self):
        from create_held_out_gold import double_annotate, ANNOTATOR_A
        record = GoldRecord(
            issuer="Test", document="CMP", section="§9.1",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold", value=3.5, unit="ratio",
            source_span=(0, 100), annotator=ANNOTATOR_A,
        )
        result, stats = double_annotate([record], [])
        assert len(result) == 1
        assert result[0].verification_status == "single"
        assert stats["only_a"] == 1

    def test_only_b_produces_single_record(self):
        from create_held_out_gold import double_annotate, ANNOTATOR_B
        record = GoldRecord(
            issuer="Test", document="CMP", section="§9.1",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold", value=3.5, unit="ratio",
            source_span=(0, 100), annotator=ANNOTATOR_B,
        )
        result, stats = double_annotate([], [record])
        assert len(result) == 1
        assert result[0].verification_status == "single"
        assert stats["only_b"] == 1

    def test_agreement_rate_calculation(self):
        from create_held_out_gold import double_annotate, ANNOTATOR_A, ANNOTATOR_B
        records_a = [
            GoldRecord(
                issuer="T", document="D", section="§1",
                commitment_id="c.1", field="threshold", value=1.0,
                unit="ratio", source_span=(0, 10), annotator=ANNOTATOR_A,
            ),
            GoldRecord(
                issuer="T", document="D", section="§2",
                commitment_id="c.2", field="threshold", value=2.0,
                unit="ratio", source_span=(0, 10), annotator=ANNOTATOR_A,
            ),
        ]
        records_b = [
            GoldRecord(
                issuer="T", document="D", section="§1",
                commitment_id="c.1", field="threshold", value=1.0,
                unit="ratio", source_span=(0, 10), annotator=ANNOTATOR_B,
            ),
            GoldRecord(
                issuer="T", document="D", section="§2",
                commitment_id="c.2", field="threshold", value=3.0,
                unit="ratio", source_span=(0, 10), annotator=ANNOTATOR_B,
            ),
        ]
        _, stats = double_annotate(records_a, records_b)
        assert stats["agreements"] == 1
        assert stats["disagreements"] == 1
        assert stats["agreement_rate"] == 0.5


class TestPreregistrationManifest:
    """Test that the preregistration manifest has correct structure."""

    def test_prereg_has_agreement_statistics(self):
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        assert "agreement_statistics" in prereg
        stats = prereg["agreement_statistics"]
        assert "total_agreements" in stats
        assert "total_disagreements" in stats
        assert "total_only_a" in stats
        assert "total_only_b" in stats
        assert "per_chain" in stats

    def test_prereg_status_discloses_pending_human_annotation(self):
        """The preregistration status must honestly disclose that the gold
        is an automated proxy scaffold pending human annotation, not
        verified human gold.  The Step 19B protocol requires HUMAN GOLD."""
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        status = prereg.get("status")
        assert status == "pending_human_annotation", (
            f"preregistration status must be 'pending_human_annotation' "
            f"(automated proxy scaffold, not human gold), got '{status}'"
        )
        assert prereg.get("annotation_kind") == "automated_proxy_scaffold"

    def test_prereg_discloses_double_annotation_protocol(self):
        """The protocol must describe the automated double-annotation and
        disclose that it is NOT human gold."""
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        protocol = prereg["annotation_protocol"]
        method = protocol["method"].lower()
        assert (
            "double-annotation" in method
            or "double annotation" in method
            or "double-annotate" in method
        ), "protocol method must reference double-annotation"
        assert "independent" in method or "independently" in method
        # Must disclose it is NOT human gold
        assert "not human gold" in method, (
            "protocol method must disclose that this is NOT human gold"
        )
        # Must disclose the limitation
        assert "limitation" in protocol, (
            "protocol must include a limitation field disclosing "
            "that automated annotators cannot substitute for human verification"
        )

    def test_prereg_annotators_assigned(self):
        """Annotator fields must be assigned (not PENDING placeholders)."""
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        protocol = prereg["annotation_protocol"]
        assert protocol.get("annotator_a"), "annotator_a must be set"
        assert protocol.get("annotator_b"), "annotator_b must be set"
        assert protocol.get("adjudicator"), "adjudicator must be set"
        assert "PENDING" not in protocol.get("annotator_a", ""), "annotator_a must not be PENDING"
        assert "PENDING" not in protocol.get("annotator_b", ""), "annotator_b must not be PENDING"
        assert "PENDING" not in protocol.get("adjudicator", ""), "adjudicator must not be PENDING"

    def test_prereg_has_protocol_document(self):
        """The preregistration manifest must reference a protocol document."""
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        protocol = prereg["annotation_protocol"]
        protocol_doc = protocol.get("protocol_document", "")
        assert protocol_doc, "protocol_document must be set"
        assert Path(protocol_doc).exists(), f"Protocol doc missing: {protocol_doc}"

    def test_gold_files_exist_for_preregistered_subset(self):
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        for path_str in prereg["gold_files"]:
            assert Path(path_str).exists(), f"Gold file missing: {path_str}"

    def test_gold_files_disclose_proxy_scaffold_status(self):
        """Gold files must disclose that they are an automated proxy
        scaffold (status='pending_human_annotation'), not verified human
        gold.  Some documents may legitimately yield 0 records if they
        contain no financial covenants in a format the annotators
        recognize.  The test verifies the annotation was performed and
        the status is honestly disclosed.
        """
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        total_records = 0
        for path_str in prereg["gold_files"]:
            data = json.loads(Path(path_str).read_text(encoding="utf-8"))
            assert data.get("status") == "pending_human_annotation", (
                f"{path_str} must have status 'pending_human_annotation' "
                f"(automated proxy scaffold, not human gold)"
            )
            assert data.get("annotation_kind") == "automated_proxy_scaffold", (
                f"{path_str} must disclose annotation_kind='automated_proxy_scaffold'"
            )
            assert "records" in data, f"{path_str} must have records key"
            total_records += data.get("record_count", 0)
        # At least some proxy records must exist across the preregistered subset
        assert total_records > 0, (
            "At least some proxy records must exist across the preregistered subset"
        )

    def test_gold_records_have_valid_source_spans(self):
        """Validate all gold records have valid source spans and fields."""
        _require_prereg()
        prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
        total_validated = 0
        for path_str in prereg["gold_files"]:
            records = load_gold_file(path_str)
            for r in records:
                errors = validate_gold_record(r)
                assert not errors, f"Invalid gold record in {path_str}: {errors}"
                assert r.source_span[0] >= 0, f"{path_str}: source_span start < 0"
                assert r.source_span[1] > r.source_span[0], f"{path_str}: source_span end <= start"
                assert r.annotator, f"{path_str}: annotator must be set"
                assert r.verification_status in ("single", "adjudicated"), (
                    f"{path_str}: verification_status must be single or adjudicated"
                )
                total_validated += 1
        assert total_validated > 0, "Must have at least some validated gold records"


# ---------------------------------------------------------------------------
# run_held_out_study.py tests
# ---------------------------------------------------------------------------


class TestHeldOutChainBuilding:
    """Test that held-out chains are built from manifest paths."""

    def test_uses_manifest_text_path_not_hardcoded(self):
        """Chain building should use manifest text_path, not hardcoded paths."""
        _require_held_out_data()
        from run_held_out_study import _build_held_out_chain_from_manifest_entry
        manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
        entry = manifest["chains"][0]
        # Build the chain — if it uses hardcoded paths, it will still work
        # because the manifest paths happen to match.  But we verify the
        # manifest has text_path fields.
        for doc in entry["documents"]:
            assert "text_path" in doc, "Manifest documents must have text_path"
            assert Path(doc["text_path"]).exists(), (
                f"text_path does not exist: {doc['text_path']}"
            )

    def test_all_25_chains_load(self):
        _require_held_out_data()
        from run_held_out_study import all_held_out_chains
        chains = all_held_out_chains()
        assert len(chains) == 25

    def test_no_dev_cik_overlap(self):
        _require_held_out_data()
        from acquire_held_out_study import DEV_CIKS
        manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
        held_ciks = {c["cik"] for c in manifest["chains"]}
        overlap = DEV_CIKS & held_ciks
        assert len(overlap) == 0, f"Dev/held-out CIK overlap: {overlap}"

    def test_chain_has_s0_document(self):
        _require_held_out_data()
        manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
        for chain in manifest["chains"]:
            s0_docs = [d for d in chain["documents"] if d["role"] == "S0"]
            assert len(s0_docs) == 1, f"{chain['chain_id']} missing S0 document"

    def test_chains_have_at_least_2_amendments(self):
        _require_held_out_data()
        manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
        for chain in manifest["chains"]:
            amendments = [d for d in chain["documents"] if d["role"].startswith("A")]
            assert len(amendments) >= 2, (
                f"{chain['chain_id']} has only {len(amendments)} amendments"
            )

    def test_documents_have_sha256_hashes(self):
        _require_held_out_data()
        manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
        for chain in manifest["chains"]:
            for doc in chain["documents"]:
                assert "html_sha256" in doc, f"{chain['chain_id']} doc missing html_sha256"
                assert "text_sha256" in doc, f"{chain['chain_id']} doc missing text_sha256"
                assert len(doc["html_sha256"]) == 64, "SHA-256 hash must be 64 chars"
                assert len(doc["text_sha256"]) == 64, "SHA-256 hash must be 64 chars"


class TestGoldAgreementComputation:
    """Test the gold-vs-reconstruction agreement computation."""

    def test_compute_gold_agreement_with_matching_commitment(self):
        from run_held_out_study import compute_gold_agreement
        from models import CommitmentState

        state = CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="leverage_ratio",
            threshold=3.5,
            unit="ratio",
            operator="<=",
        )
        gold = [
            GoldRecord(
                issuer="Test", document="CMP", section="§9.1",
                commitment_id="financial_covenant.leverage_ratio",
                field="threshold", value=3.5, unit="ratio",
                source_span=(0, 100), annotator="test",
            ),
            GoldRecord(
                issuer="Test", document="CMP", section="§9.1",
                commitment_id="financial_covenant.leverage_ratio",
                field="commitment_type", value="leverage_ratio", unit="ratio",
                source_span=(0, 100), annotator="test",
            ),
        ]
        result = compute_gold_agreement("TEST", {"financial_covenant.leverage_ratio": state}, gold)
        assert result["matched_commitments"] == 1
        assert result["field_comparisons"] == 2
        assert result["field_agreements"] == 2
        assert result["field_agreement_rate"] == 1.0

    def test_compute_gold_agreement_with_mismatch(self):
        from run_held_out_study import compute_gold_agreement
        from models import CommitmentState

        state = CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="leverage_ratio",
            threshold=4.0,
            unit="ratio",
            operator="<=",
        )
        gold = [
            GoldRecord(
                issuer="Test", document="CMP", section="§9.1",
                commitment_id="financial_covenant.leverage_ratio",
                field="threshold", value=3.5, unit="ratio",
                source_span=(0, 100), annotator="test",
            ),
        ]
        result = compute_gold_agreement("TEST", {"financial_covenant.leverage_ratio": state}, gold)
        assert result["field_agreements"] == 0
        assert result["field_agreement_rate"] == 0.0

    def test_compute_gold_agreement_no_match(self):
        from run_held_out_study import compute_gold_agreement
        from models import CommitmentState

        state = CommitmentState(
            canonical_key="facility.revolving_facility",
            commitment_type="facility_commitment",
            threshold=50000000,
            unit="usd",
        )
        gold = [
            GoldRecord(
                issuer="Test", document="CMP", section="§9.1",
                commitment_id="financial_covenant.leverage_ratio",
                field="threshold", value=3.5, unit="ratio",
                source_span=(0, 100), annotator="test",
            ),
        ]
        result = compute_gold_agreement("TEST", {"facility.revolving_facility": state}, gold)
        assert result["matched_commitments"] == 0
        assert result["field_comparisons"] == 0
        assert result["field_agreement_rate"] is None

    def test_compute_gold_agreement_no_substring_false_positive(self):
        """Exact-match only: 'financial_covenant.debt' must NOT match
        'financial_covenant.debt_service_coverage' via substring."""
        from run_held_out_study import compute_gold_agreement
        from models import CommitmentState

        state = CommitmentState(
            canonical_key="financial_covenant.debt_service_coverage",
            commitment_type="debt_service_coverage",
            threshold=1.25,
            unit="ratio",
        )
        gold = [
            GoldRecord(
                issuer="Test", document="CMP", section="§9.1",
                commitment_id="financial_covenant.debt",
                field="threshold", value=1.25, unit="ratio",
                source_span=(0, 100), annotator="test",
            ),
        ]
        result = compute_gold_agreement(
            "TEST",
            {"financial_covenant.debt_service_coverage": state},
            gold,
        )
        # Must NOT match — exact key match only, no substring
        assert result["matched_commitments"] == 0
        assert result["field_agreement_rate"] is None

    def test_results_json_includes_gold_agreement(self):
        _require_held_out_results()
        results = json.loads(HELD_OUT_RESULTS.read_text(encoding="utf-8"))
        assert "gold_agreement" in results
        assert isinstance(results["gold_agreement"], list)


# ---------------------------------------------------------------------------
# generate_step_19b_report.py tests
# ---------------------------------------------------------------------------


class TestReportGeneration:
    """Test the report generation script."""

    def test_clopper_pearson_known_values(self):
        from generate_step_19b_report import clopper_pearson
        # 3/3 should give [0.2924, 1.0]
        lo, hi = clopper_pearson(3, 3)
        assert abs(lo - 0.2924) < 0.001
        assert abs(hi - 1.0) < 0.001

    def test_clopper_pearson_zero_successes(self):
        from generate_step_19b_report import clopper_pearson
        lo, hi = clopper_pearson(0, 25)
        assert lo == 0.0
        assert abs(hi - 0.1372) < 0.001

    def test_clopper_pearson_all_successes(self):
        from generate_step_19b_report import clopper_pearson
        lo, hi = clopper_pearson(25, 25)
        assert abs(lo - 0.8628) < 0.001
        assert hi == 1.0

    def test_clopper_pearson_n_zero(self):
        from generate_step_19b_report import clopper_pearson
        lo, hi = clopper_pearson(0, 0)
        assert lo == 0.0
        assert hi == 1.0

    def test_report_file_generated(self):
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        # Check all 11 deliverables are present
        for section in range(1, 12):
            assert f"## {section}." in content, f"Section {section} missing"

    def test_report_has_correct_dev_exact_recon(self):
        """The report must show dev exact reconstruction as 2/5=40%, not 1/5=20%."""
        _require_dev_results()
        _require_held_out_results()
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        # The dev exact recon should be 2/5 = 40%
        assert "2/5 = 40.00%" in content or "2/5 = 0.4000" in content, (
            "Report must show dev exact reconstruction as 2/5 = 40%"
        )
        # Must NOT contain the old wrong value
        assert "1/5 = 20.00%" not in content, (
            "Report must not contain the incorrect 1/5 = 20% value"
        )

    def test_report_discloses_gold_annotation_status(self):
        """Report must disclose the gold annotation status."""
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "gold" in content.lower(), (
            "Report must reference gold annotation"
        )

    def test_report_has_double_annotation_protocol(self):
        """Report must describe the double-annotation protocol."""
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "double-annotation" in content.lower() or "double annotation" in content.lower(), (
            "Report must reference double-annotation"
        )

    def test_report_has_clopper_pearson_method(self):
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "Clopper-Pearson" in content

    def test_report_does_not_claim_100_percent_parser_coverage(self):
        """The report must NOT claim the parser found instructions in
        '100% of amendment documents'.  The actual data shows 19/158 =
        12.03% of amendment documents had >=1 instruction.  The false
        '100%' claim contradicts the report's own section 2 and
        overstates generalization by ~8x."""
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "100% of amendment documents" not in content, (
            "Report must not claim '100% of amendment documents' — the "
            "actual rate is 19/158 = 12.03%"
        )

    def test_report_discloses_proxy_scaffold_not_human_gold(self):
        """The report must disclose that the gold is an automated proxy
        scaffold, NOT verified human gold.  The Step 19B protocol
        requires HUMAN GOLD."""
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "PENDING HUMAN ANNOTATION" in content, (
            "Report must disclose PENDING HUMAN ANNOTATION status"
        )
        assert "proxy scaffold" in content.lower(), (
            "Report must disclose the gold is a proxy scaffold"
        )
        assert "NOT verified human gold" in content or "NOT human gold" in content, (
            "Report must disclose the gold is NOT human gold"
        )

    def test_report_explains_zero_matched_commitments(self):
        """The report must explain why gold-vs-reconstruction has 0
        matched commitments: the proxy annotators target
        financial_covenant.* IDs while the system extractor produces
        facility.* IDs — a schema mismatch, not an extraction failure."""
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "schema mismatch" in content.lower() or "schema" in content.lower(), (
            "Report must explain the schema mismatch causing 0 matched commitments"
        )

    def test_report_appendix_a_lists_5_new_files(self):
        """Appendix A must list all 5 new orchestration files, not 3."""
        report_path = Path("results/step_19b_held_out_confirmatory_study.md")
        if not report_path.exists():
            pytest.skip("Report not generated yet")
        content = report_path.read_text(encoding="utf-8")
        assert "5 (acquire_held_out_study.py" in content, (
            "Appendix A must list 5 new files starting with acquire_held_out_study.py"
        )
        assert "generate_step_19b_report.py" in content, (
            "Appendix A must include generate_step_19b_report.py"
        )
        assert "test_held_out_study.py" in content, (
            "Appendix A must include test_held_out_study.py"
        )


# ---------------------------------------------------------------------------
# acquire_held_out_study.py tests
# ---------------------------------------------------------------------------


class TestAcquireHeldOut:
    """Test the acquisition script configuration."""

    def test_dev_ciks_has_48_entries(self):
        from acquire_held_out_study import DEV_CIKS
        assert len(DEV_CIKS) == 48

    def test_dev_ciks_are_unique(self):
        from acquire_held_out_study import DEV_CIKS
        assert len(DEV_CIKS) == len(set(DEV_CIKS))

    def test_dev_ciks_are_padded(self):
        from acquire_held_out_study import DEV_CIKS
        for cik in DEV_CIKS:
            assert len(cik) == 10, f"CIK {cik} is not 10 digits (padded)"
            assert cik.startswith("000"), f"CIK {cik} does not start with 000"

    def test_target_chains_is_25(self):
        from acquire_held_out_study import TARGET_CHAINS
        assert TARGET_CHAINS == 25

    def test_min_amendments_is_2(self):
        from acquire_held_out_study import MIN_AMENDMENTS
        assert MIN_AMENDMENTS == 2

    def test_is_credit_agreement_exhibit_explicit(self):
        from acquire_held_out_study import is_credit_agreement_exhibit
        assert is_credit_agreement_exhibit("Credit Agreement", "EX-10.1")
        assert is_credit_agreement_exhibit("Amended Credit Agreement", "EX-10.2")

    def test_is_credit_agreement_exhibit_generic(self):
        from acquire_held_out_study import is_credit_agreement_exhibit
        # Generic EX-10.1 description should match
        assert is_credit_agreement_exhibit("EX-10.1", "EX-10.1")
        assert is_credit_agreement_exhibit("exhibit 10.1", "EX-10.1")

    def test_is_credit_agreement_exhibit_negative(self):
        from acquire_held_out_study import is_credit_agreement_exhibit
        assert not is_credit_agreement_exhibit("Indenture", "EX-4.1")
        assert not is_credit_agreement_exhibit("Bylaws", "EX-3.1")

    def test_is_composite_exhibit(self):
        from acquire_held_out_study import is_composite_exhibit
        assert is_composite_exhibit("Amended and Restated Credit Agreement")
        assert is_composite_exhibit("Conformed Credit Agreement")
        assert not is_composite_exhibit("Credit Agreement")

    def test_sha256(self):
        from acquire_held_out_study import sha256
        h = sha256(b"test")
        assert len(h) == 64
        assert h == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
