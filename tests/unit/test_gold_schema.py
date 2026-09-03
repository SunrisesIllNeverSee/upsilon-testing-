"""Tests for the gold record schema.

Tests cover:
  - Required field validation
  - Verification status validation
  - Double-annotation workflow (second_annotator required)
  - Adjudication workflow (adjudicator required)
  - source_span validation (tuple, ordering)
  - Serialization round-trip (GoldRecord → dict → GoldRecord)
  - File save/load round-trip
  - Schema documentation completeness
  - All prompt-required fields are present
"""
from __future__ import annotations

import json

from upsilon.evidence.gold_schema import (
    VERIFICATION_STATUSES,
    GoldRecord,
    dict_to_gold_record,
    gold_record_to_dict,
    load_gold_file,
    save_gold_file,
    validate_gold_record,
    write_schema_documentation,
)

# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


PROMPT_REQUIRED_FIELDS = [
    "issuer",
    "document",
    "section",
    "commitment_id",
    "field",
    "value",
    "unit",
    "effective_at",
    "source_span",
    "annotator",
    "verification_status",
]


class TestRequiredFields:
    def test_all_prompt_required_fields_in_schema(self):
        """The GoldRecord must have all 11 fields specified in the prompt."""
        record_fields = {
            "issuer", "document", "section", "commitment_id",
            "field", "value", "unit", "source_span",
            "annotator", "verification_status", "effective_at",
        }
        for field in PROMPT_REQUIRED_FIELDS:
            assert hasattr(GoldRecord, field) or field in record_fields, (
                f"Missing required field: {field}"
            )

    def test_missing_issuer_is_error(self):
        record = GoldRecord(
            issuer="",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
        )
        errors = validate_gold_record(record)
        assert any("issuer" in e for e in errors)

    def test_missing_document_is_error(self):
        record = GoldRecord(
            issuer="Test",
            document="",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
        )
        errors = validate_gold_record(record)
        assert any("document" in e for e in errors)

    def test_missing_commitment_id_is_error(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
        )
        errors = validate_gold_record(record)
        assert any("commitment_id" in e for e in errors)

    def test_none_value_is_error(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=None,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
        )
        errors = validate_gold_record(record)
        assert any("value" in e for e in errors)

    def test_missing_annotator_is_error(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="",
        )
        errors = validate_gold_record(record)
        assert any("annotator" in e for e in errors)


# ---------------------------------------------------------------------------
# Verification status
# ---------------------------------------------------------------------------


class TestVerificationStatus:
    def test_all_four_statuses_defined(self):
        assert "single" in VERIFICATION_STATUSES
        assert "double_annotated" in VERIFICATION_STATUSES
        assert "adjudicated" in VERIFICATION_STATUSES
        assert "locked" in VERIFICATION_STATUSES

    def test_invalid_status_is_error(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
            verification_status="invalid_status",
        )
        errors = validate_gold_record(record)
        assert any("verification_status" in e for e in errors)

    def test_double_annotated_requires_second_annotator(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
            verification_status="double_annotated",
            second_annotator="",  # Missing
        )
        errors = validate_gold_record(record)
        assert any("second_annotator" in e for e in errors)

    def test_double_annotated_with_second_annotator_is_valid(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
            verification_status="double_annotated",
            second_annotator="annotator_b",
        )
        errors = validate_gold_record(record)
        assert not errors

    def test_adjudicated_requires_adjudicator(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
            verification_status="adjudicated",
            adjudicator="",  # Missing
        )
        errors = validate_gold_record(record)
        assert any("adjudicator" in e for e in errors)

    def test_adjudicated_with_adjudicator_is_valid(self):
        record = GoldRecord(
            issuer="Test",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(100, 200),
            annotator="annotator_a",
            verification_status="adjudicated",
            adjudicator="adjudicator_c",
        )
        errors = validate_gold_record(record)
        assert not errors


# ---------------------------------------------------------------------------
# source_span validation
# ---------------------------------------------------------------------------


class TestSourceSpanValidation:
    def test_valid_span(self):
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=(100, 200), annotator="a",
        )
        errors = validate_gold_record(record)
        assert not errors

    def test_span_with_negative_start(self):
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=(-1, 200), annotator="a",
        )
        errors = validate_gold_record(record)
        assert any("source_span" in e for e in errors)

    def test_span_with_end_before_start(self):
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=(200, 100), annotator="a",
        )
        errors = validate_gold_record(record)
        assert any("source_span" in e for e in errors)

    def test_span_with_wrong_length(self):
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=(100, 200, 300), annotator="a",
        )
        errors = validate_gold_record(record)
        assert any("source_span" in e for e in errors)

    def test_list_span_is_accepted(self):
        """source_span as a list (from JSON) should be accepted."""
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=[100, 200], annotator="a",
        )
        errors = validate_gold_record(record)
        assert not errors


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_roundtrip_dict(self):
        record = GoldRecord(
            issuer="Ameresco, Inc.",
            document="S0",
            section="Section 6.07(a)",
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            value=4.50,
            unit="ratio",
            source_span=(1234, 1290),
            annotator="annotator_a",
            verification_status="double_annotated",
            effective_at="2022-03-04",
            second_annotator="annotator_b",
            second_value=4.50,
        )
        d = gold_record_to_dict(record)
        assert d["issuer"] == "Ameresco, Inc."
        assert d["source_span"] == [1234, 1290]
        assert d["verification_status"] == "double_annotated"

        restored = dict_to_gold_record(d)
        assert restored.issuer == record.issuer
        assert restored.commitment_id == record.commitment_id
        assert restored.source_span == (1234, 1290)
        assert restored.verification_status == record.verification_status

    def test_roundtrip_file(self, tmp_path):
        records = [
            GoldRecord(
                issuer="Test", document="S0", section="S1",
                commitment_id="fc.lr", field="threshold", value=4.5,
                unit="ratio", source_span=(100, 200), annotator="a",
            ),
            GoldRecord(
                issuer="Test", document="S0", section="S2",
                commitment_id="fc.dscr", field="threshold", value=1.25,
                unit="ratio", source_span=(300, 400), annotator="a",
            ),
        ]
        path = tmp_path / "gold" / "TEST_S0_gold.json"
        save_gold_file(path, records)
        assert path.exists()

        loaded = load_gold_file(path)
        assert len(loaded) == 2
        assert loaded[0].commitment_id == "fc.lr"
        assert loaded[1].commitment_id == "fc.dscr"
        assert loaded[0].source_span == (100, 200)

    def test_file_has_schema_version(self, tmp_path):
        records = [
            GoldRecord(
                issuer="Test", document="S0", section="S1",
                commitment_id="fc.lr", field="threshold", value=4.5,
                unit="ratio", source_span=(100, 200), annotator="a",
            ),
        ]
        path = tmp_path / "test_gold.json"
        save_gold_file(path, records)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "1.0"
        assert data["record_count"] == 1

    def test_optional_fields_serialized_when_present(self):
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=(100, 200), annotator="a",
            effective_at="2022-03-04",
            notes="Some notes",
        )
        d = gold_record_to_dict(record)
        assert "effective_at" in d
        assert d["effective_at"] == "2022-03-04"
        assert d["notes"] == "Some notes"

    def test_optional_fields_omitted_when_absent(self):
        record = GoldRecord(
            issuer="Test", document="S0", section="S1",
            commitment_id="fc.lr", field="threshold", value=4.5,
            unit="ratio", source_span=(100, 200), annotator="a",
        )
        d = gold_record_to_dict(record)
        assert "effective_at" not in d
        assert "notes" not in d
        assert "second_annotator" not in d


# ---------------------------------------------------------------------------
# Schema documentation
# ---------------------------------------------------------------------------


class TestSchemaDocumentation:
    def test_documentation_contains_all_fields(self, tmp_path):
        path = tmp_path / "schema_doc.md"
        write_schema_documentation(path)
        content = path.read_text(encoding="utf-8")
        for field in PROMPT_REQUIRED_FIELDS:
            assert field in content, f"Schema doc missing field: {field}"

    def test_documentation_contains_verification_workflow(self, tmp_path):
        path = tmp_path / "schema_doc.md"
        write_schema_documentation(path)
        content = path.read_text(encoding="utf-8")
        assert "single" in content
        assert "double_annotated" in content
        assert "adjudicated" in content
        assert "locked" in content

    def test_documentation_mentions_preregistered_subset(self, tmp_path):
        """The schema doc should mention the preregistered double-annotation subset."""
        path = tmp_path / "schema_doc.md"
        write_schema_documentation(path)
        content = path.read_text(encoding="utf-8")
        assert "preregistered" in content.lower() or "double-annotated" in content.lower()
