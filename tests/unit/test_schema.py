from pathlib import Path

SCHEMA = (Path(__file__).resolve().parent.parent.parent / "config" / "sql" / "schema.sql").read_text()


def test_temporal_columns_exist():
    assert "valid_from TIMESTAMPTZ" in SCHEMA
    assert "valid_to TIMESTAMPTZ" in SCHEMA
    assert "recorded_at TIMESTAMPTZ" in SCHEMA
    assert "applicability JSONB" in SCHEMA


def test_authoritative_boolean_removed():
    assert "is_authoritative" not in SCHEMA


def test_reference_change_is_dedicated_structure():
    assert "CREATE TABLE reference_change" in SCHEMA
