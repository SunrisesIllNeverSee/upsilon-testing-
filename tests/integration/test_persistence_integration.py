import os
import pytest
psycopg = pytest.importorskip("psycopg")
connect = psycopg.connect

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL to run PostgreSQL integration tests."
)

def test_database_schema_is_temporal_and_has_reference_changes():
    with connect(TEST_DATABASE_URL) as conn:
        cols = conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='commitment_version'
        """).fetchall()
        names = {r[0] for r in cols}
        assert {"valid_from","valid_to","recorded_at","applicability"} <= names

        tables = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
        """).fetchall()
        assert "reference_change" in {r[0] for r in tables}
