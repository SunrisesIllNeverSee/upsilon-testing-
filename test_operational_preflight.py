"""Regression tests for Step 17A operational preflight.

Tests cover:
  1. The foundation bug fix in persistence._latest_version —
     multi-amendment chains must not produce contradictory ACTIVE
     versions (two open-ended intervals for the same commitment).
  2. Operational preflight integrity check functions produce correct
     results on synthetic data.
  3. The preflight chain selection matches the 5 specified chains.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL or DATABASE_URL to run PostgreSQL integration tests.",
)

PSYCOPG_URL = (
    TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    if TEST_DATABASE_URL
    else ""
)

SCHEMA_PATH = Path("schema.sql")


# ---------------------------------------------------------------------------
# Helper: initialize a clean database
# ---------------------------------------------------------------------------


def _init_db(conn: psycopg.Connection) -> None:
    conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
    conn.execute("CREATE SCHEMA public")
    conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def _insert_agreement_version(conn: psycopg.Connection, agree_id, kind="ORIGINAL", version_number=1):
    """Insert an agreement_version and return its id."""
    return conn.execute(
        """
        INSERT INTO agreement_version (agreement_id, kind, version_number)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (agree_id, kind, version_number),
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Regression test: _latest_version must find the currently-active version
# (valid_to IS NULL), not the one with the latest recorded_at.
# ---------------------------------------------------------------------------


def test_latest_version_finds_current_active_not_latest_recorded():
    """Regression: _latest_version must prefer valid_to IS NULL over
    recorded_at DESC.  Without this fix, multi-amendment chains produce
    contradictory ACTIVE versions (two open-ended intervals).

    Bug mechanism:
      1. Origin version inserted (recorded_at = T0, valid_to = NULL)
      2. A1 version inserted (recorded_at = T1 ≈ T0, valid_to = NULL,
         origin's valid_to closed to A1.valid_from)
      3. A2 version: _latest_version returns origin (T0 == T1, ambiguous
         sort) instead of A1 → A1's valid_to never closed → two ACTIVE
         versions with valid_to = NULL.
    """
    from persistence import _latest_version

    with psycopg.connect(PSYCOPG_URL) as conn:
        _init_db(conn)

        # Insert a throwaway agreement + commitment
        agree_id = conn.execute(
            "INSERT INTO agreement (issuer_name, agreement_name) "
            "VALUES ('TEST_LATEST_VERSION', 'Test') RETURNING id"
        ).fetchone()[0]

        ver_id = _insert_agreement_version(conn, agree_id)

        commit_id = conn.execute(
            "INSERT INTO commitment (agreement_id, canonical_key, commitment_type) "
            "VALUES (%s, 'test_covenant', 'financial_covenant') RETURNING id",
            (agree_id,),
        ).fetchone()[0]

        # Insert origin version
        origin_id = conn.execute(
            """
            INSERT INTO commitment_version (
                commitment_id, agreement_version_id, parent_commitment_version_id,
                status, valid_from, valid_to
            ) VALUES (%s, %s, NULL, 'ACTIVE', '2020-01-01+00', NULL)
            RETURNING id
            """,
            (commit_id, ver_id),
        ).fetchone()[0]

        # Insert A1 version (closes origin's valid_to)
        a1_id = conn.execute(
            """
            INSERT INTO commitment_version (
                commitment_id, agreement_version_id, parent_commitment_version_id,
                status, valid_from, valid_to
            ) VALUES (%s, %s, %s, 'ACTIVE', '2023-08-24+00', NULL)
            RETURNING id
            """,
            (commit_id, ver_id, origin_id),
        ).fetchone()[0]
        # Close origin
        conn.execute(
            "UPDATE commitment_version SET valid_to = '2023-08-24+00' WHERE id = %s",
            (origin_id,),
        )

        # Now _latest_version should return A1 (valid_to IS NULL), not origin
        latest = _latest_version(conn, commit_id)
        assert latest is not None, "Should find a latest version"
        assert latest["id"] == a1_id, (
            f"_latest_version returned {latest['id']} (origin), "
            f"expected {a1_id} (A1 — the currently active version)"
        )

        # Clean up


# ---------------------------------------------------------------------------
# Regression test: multi-amendment persistence must not produce
# contradictory ACTIVE versions.
# ---------------------------------------------------------------------------


def test_multi_amendment_no_contradictory_active():
    """Regression: persisting multiple amendments to the same commitment
    must not leave two ACTIVE versions with valid_to = NULL.

    This is the exact bug found in EDGAR-AMERESCO Step 17A preflight:
    A1 and A3 both modify the same commitment, but A3's parent was set
    to the origin instead of A1, leaving A1's valid_to = NULL.
    """
    from models import (
        AmendmentInstruction,
        CommitmentState,
        ExecutionResult,
        ExecutionStatus,
        InstructionType,
    )
    from persistence import persist_execution

    with psycopg.connect(PSYCOPG_URL) as conn:
        _init_db(conn)

        # Insert agreement
        agree_id = conn.execute(
            "INSERT INTO agreement (issuer_name, agreement_name) "
            "VALUES ('TEST_CONTRADICTORY', 'Test') RETURNING id"
        ).fetchone()[0]

        # Insert original agreement version
        orig_ver_id = _insert_agreement_version(conn, agree_id)

        # Insert original commitment
        commit_id = conn.execute(
            "INSERT INTO commitment (agreement_id, canonical_key, commitment_type) "
            "VALUES (%s, 'leverage_ratio', 'financial_covenant') RETURNING id",
            (agree_id,),
        ).fetchone()[0]

        # Insert origin version
        conn.execute(
            """
            INSERT INTO commitment_version (
                commitment_id, agreement_version_id, parent_commitment_version_id,
                status, valid_from, valid_to, threshold
            ) VALUES (%s, %s, NULL, 'ACTIVE', '2020-01-01+00', NULL, 4.5)
            """,
            (commit_id, orig_ver_id),
        )

        # Amendment 1: change threshold to 4.0
        amend1_ver_id = conn.execute(
            "INSERT INTO agreement_version (agreement_id, kind, version_number, effective_at) "
            "VALUES (%s, 'AMENDMENT', 2, '2023-08-24+00') RETURNING id",
            (agree_id,),
        ).fetchone()[0]

        ins1 = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="leverage_ratio",
            field="threshold",
            new_value=4.0,
        )
        conn.execute(
            """
            INSERT INTO amendment_instruction (
                amendment_version_id, instruction_order, instruction_type, parser_payload
            ) VALUES (%s, 1, 'REPLACE_VALUE', '{}'::jsonb)
            """,
            (amend1_ver_id,),
        )

        state1 = {"leverage_ratio": CommitmentState(
            canonical_key="leverage_ratio",
            commitment_type="financial_covenant",
            threshold=4.0,
        )}
        exec1 = ExecutionResult(
            state=state1,
            applied=[ins1],
            unresolved=[],
            events=[{"order": 1, "action": "replace", "target": "leverage_ratio", "field": "threshold"}],
            status=ExecutionStatus.COMPLETE,
        )
        persist_execution(exec1, amend1_ver_id, conn)

        # Amendment 2: change threshold to 3.5
        amend2_ver_id = conn.execute(
            "INSERT INTO agreement_version (agreement_id, kind, version_number, effective_at) "
            "VALUES (%s, 'AMENDMENT', 3, '2023-12-11+00') RETURNING id",
            (agree_id,),
        ).fetchone()[0]

        ins2 = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="leverage_ratio",
            field="threshold",
            new_value=3.5,
        )
        conn.execute(
            """
            INSERT INTO amendment_instruction (
                amendment_version_id, instruction_order, instruction_type, parser_payload
            ) VALUES (%s, 1, 'REPLACE_VALUE', '{}'::jsonb)
            """,
            (amend2_ver_id,),
        )

        state2 = {"leverage_ratio": CommitmentState(
            canonical_key="leverage_ratio",
            commitment_type="financial_covenant",
            threshold=3.5,
        )}
        exec2 = ExecutionResult(
            state=state2,
            applied=[ins2],
            unresolved=[],
            events=[{"order": 1, "action": "replace", "target": "leverage_ratio", "field": "threshold"}],
            status=ExecutionStatus.COMPLETE,
        )
        persist_execution(exec2, amend2_ver_id, conn)

        # Check: no contradictory ACTIVE versions
        contradictory = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT cv1.id
                FROM commitment_version cv1
                JOIN commitment_version cv2
                  ON cv1.commitment_id = cv2.commitment_id
                  AND cv1.id < cv2.id
                WHERE cv1.commitment_id = %s
                  AND cv1.status = 'ACTIVE'
                  AND cv2.status = 'ACTIVE'
                  AND cv1.valid_from < COALESCE(cv2.valid_to, 'infinity'::timestamptz)
                  AND cv2.valid_from < COALESCE(cv1.valid_to, 'infinity'::timestamptz)
            ) AS overlap_cnt
            """,
            (commit_id,),
        ).fetchone()[0]

        assert contradictory == 0, (
            f"Found {contradictory} contradictory ACTIVE version pairs — "
            f"two open-ended intervals for the same commitment"
        )

        # Also verify: exactly one version with valid_to IS NULL
        open_ended = conn.execute(
            """
            SELECT COUNT(*) FROM commitment_version
            WHERE commitment_id = %s AND valid_to IS NULL
            """,
            (commit_id,),
        ).fetchone()[0]
        assert open_ended == 1, (
            f"Expected exactly 1 open-ended version, found {open_ended}"
        )

        # Verify parent chain: A2's parent should be A1, not origin
        versions = conn.execute(
            """
            SELECT id, parent_commitment_version_id, valid_from, valid_to
            FROM commitment_version
            WHERE commitment_id = %s
            ORDER BY valid_from
            """,
            (commit_id,),
        ).fetchall()
        assert len(versions) == 3, f"Expected 3 versions, got {len(versions)}"
        _origin_v, a1_v, a2_v = versions
        assert a2_v[1] == a1_v[0], (
            f"A2 parent should be A1 ({a1_v[0]}), but is {a2_v[1]}"
        )

        # Clean up


# ---------------------------------------------------------------------------
# Test: preflight chain selection
# ---------------------------------------------------------------------------


class TestPreflightChainSelection:
    def test_preflight_chains_are_five(self):
        from run_operational_preflight import PREFLIGHT_CHAINS
        assert len(PREFLIGHT_CHAINS) == 5

    def test_preflight_chains_match_specification(self):
        """The 5 chains should match the Step 17A selection criteria."""
        from run_operational_preflight import PREFLIGHT_CHAINS
        expected = {"EDGAR-AMERESCO", "STUDY-008", "STUDY-022", "STUDY-015", "STUDY-007"}
        assert set(PREFLIGHT_CHAINS) == expected

    def test_no_new_issuers_selected(self):
        """All chains must be from the existing development corpus."""
        from run_operational_preflight import PREFLIGHT_CHAINS
        # EDGAR-* chains are existing fixtures; STUDY-* chains are from
        # the manifest (development corpus). No new issuer IDs.
        for chain_id in PREFLIGHT_CHAINS:
            assert chain_id.startswith(("EDGAR-", "STUDY-")), (
                f"Chain {chain_id} is not from the development corpus"
            )


# ---------------------------------------------------------------------------
# Test: integrity check functions on synthetic data
# ---------------------------------------------------------------------------


class TestIntegrityChecks:
    """Test the integrity check functions with known-good and known-bad data."""

    def test_temporal_check_detects_contradictory_active(self):
        """The temporal check must detect two overlapping ACTIVE versions
        with NULL valid_to (the exact bug pattern)."""
        from run_operational_preflight import check_temporal_integrity

        with psycopg.connect(PSYCOPG_URL) as conn:
            _init_db(conn)

            agree_id = conn.execute(
                "INSERT INTO agreement (issuer_name, agreement_name) "
                "VALUES ('TEST_TEMPORAL', 'Test') RETURNING id"
            ).fetchone()[0]

            ver_id = _insert_agreement_version(conn, agree_id)

            commit_id = conn.execute(
                "INSERT INTO commitment (agreement_id, canonical_key, commitment_type) "
                "VALUES (%s, 'test', 'financial_covenant') RETURNING id",
                (agree_id,),
            ).fetchone()[0]

            # Insert two ACTIVE versions with NULL valid_to (contradictory)
            conn.execute(
                """
                INSERT INTO commitment_version (
                    commitment_id, agreement_version_id, status, valid_from, valid_to
                ) VALUES (%s, %s, 'ACTIVE', '2023-08-24+00', NULL)
                """,
                (commit_id, ver_id),
            )
            conn.execute(
                """
                INSERT INTO commitment_version (
                    commitment_id, agreement_version_id, status, valid_from, valid_to
                ) VALUES (%s, %s, 'ACTIVE', '2023-12-11+00', NULL)
                """,
                (commit_id, ver_id),
            )

            result = check_temporal_integrity(conn, agree_id)
            assert result["contradictory_active"] >= 1, (
                "Temporal check must detect contradictory ACTIVE versions with NULL valid_to"
            )


    def test_temporal_check_passes_on_correct_intervals(self):
        """The temporal check must pass when intervals are properly closed."""
        from run_operational_preflight import check_temporal_integrity

        with psycopg.connect(PSYCOPG_URL) as conn:
            _init_db(conn)

            agree_id = conn.execute(
                "INSERT INTO agreement (issuer_name, agreement_name) "
                "VALUES ('TEST_TEMPORAL_OK', 'Test') RETURNING id"
            ).fetchone()[0]

            ver_id = _insert_agreement_version(conn, agree_id)

            commit_id = conn.execute(
                "INSERT INTO commitment (agreement_id, canonical_key, commitment_type) "
                "VALUES (%s, 'test', 'financial_covenant') RETURNING id",
                (agree_id,),
            ).fetchone()[0]

            # Insert properly closed intervals: [2020-01-01, 2023-08-24) and [2023-08-24, NULL)
            conn.execute(
                """
                INSERT INTO commitment_version (
                    commitment_id, agreement_version_id, status, valid_from, valid_to
                ) VALUES (%s, %s, 'ACTIVE', '2020-01-01+00', '2023-08-24+00')
                """,
                (commit_id, ver_id),
            )
            conn.execute(
                """
                INSERT INTO commitment_version (
                    commitment_id, agreement_version_id, status, valid_from, valid_to
                ) VALUES (%s, %s, 'ACTIVE', '2023-08-24+00', NULL)
                """,
                (commit_id, ver_id),
            )

            result = check_temporal_integrity(conn, agree_id)
            assert result["contradictory_active"] == 0, (
                f"Temporal check should pass on properly closed intervals, "
                f"but found {result['contradictory_active']} contradictory"
            )


    def test_lineage_check_detects_orphans(self):
        """The lineage check must detect orphan versions."""
        from run_operational_preflight import check_lineage_integrity

        with psycopg.connect(PSYCOPG_URL) as conn:
            _init_db(conn)

            agree_id = conn.execute(
                "INSERT INTO agreement (issuer_name, agreement_name) "
                "VALUES ('TEST_LINEAGE_ORPHAN', 'Test') RETURNING id"
            ).fetchone()[0]

            ver_id = _insert_agreement_version(conn, agree_id)

            commit_id = conn.execute(
                "INSERT INTO commitment (agreement_id, canonical_key, commitment_type) "
                "VALUES (%s, 'test', 'financial_covenant') RETURNING id",
                (agree_id,),
            ).fetchone()[0]

            # Insert origin
            origin_id = conn.execute(
                """
                INSERT INTO commitment_version (
                    commitment_id, agreement_version_id, status, valid_from, valid_to
                ) VALUES (%s, %s, 'ACTIVE', '2020-01-01+00', NULL)
                RETURNING id
                """,
                (commit_id, ver_id),
            ).fetchone()[0]

            # Insert child WITHOUT lineage edge (orphan)
            conn.execute(
                """
                INSERT INTO commitment_version (
                    commitment_id, agreement_version_id,
                    parent_commitment_version_id, status, valid_from, valid_to
                ) VALUES (%s, %s, %s, 'ACTIVE', '2023-08-24+00', NULL)
                """,
                (commit_id, ver_id, origin_id),
            )

            result = check_lineage_integrity(conn, agree_id)
            assert result["orphans"] >= 1, (
                f"Lineage check should detect orphan, found {result['orphans']}"
            )



# ---------------------------------------------------------------------------
# Test: rollback works
# ---------------------------------------------------------------------------


def test_persistence_rollback_works():
    """Verify that persist_execution rolls back on mid-transaction error."""
    from run_operational_preflight import check_persistence_rollback

    with psycopg.connect(PSYCOPG_URL) as conn:
        _init_db(conn)
        result = check_persistence_rollback(conn)
        assert result["rollback_works"], result["detail"]
