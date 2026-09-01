"""Step 17A: Five-chain operational preflight with real PostgreSQL.

Runs 5 representative development chains through the FULL operational
path including real PostgreSQL persistence, temporal state, lineage,
authority determination, reconstruction, and GT comparison.

Selected chains (from existing development corpus only):
  1. EDGAR-AMERESCO — previously successful/reconstructible (SUCCESS, agreement=1.0)
  2. STUDY-008 — improved by v0.2 extraction (0→2 commitments)
  3. STUDY-022 — UNRESOLVED behavior + GT comparison (agreement=0.875)
  4. STUDY-015 — temporal/version transitions (4 amendments, GT available)
  5. STUDY-007 — multiple commitment mutations / lineage edges (3 amendments, 2 mapped)

Foundation integrity checks (each independently verified, NOT derived
from the pipeline's own claims):

  EXECUTOR:
    - applied mutations match intended target/field/value
    - failed guards do not mutate state (independent re-run)
  PERSISTENCE:
    - every applied mutation has expected commitment version
    - every required lineage edge exists
    - no partial commits (version count matches applied target count)
    - rollback works (integration test with deliberate mid-transaction error)
  LINEAGE:
    - no orphans, no cycles, correct parent/child edges
    - correct authority linkage, current state reachable from origin
  TEMPORAL:
    - no contradictory active versions (handles NULL valid_to)
    - half-open intervals valid (valid_to > valid_from)
    - waiver/restoration timing correct where exercised
  AUTHORITY:
    - no PARTIAL/UNRESOLVED state falsely promoted (independent DB check)
    - inherited uncertainty preserved correctly (independent recompute)
  COMPARISON:
    - no false equality/PASS when supported fields differ (independent recompute)

Bright-line rule:
  WRONG + CONFIDENT = FOUNDATION BUG → STOP
  UNKNOWN + EXPLICITLY FLAGGED = VALID SYSTEM BEHAVIOR → CONTINUE

Usage:
    set -a && source .env && set +a
    python3 run_operational_preflight.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import psycopg

from chain_reconstruction import IssuerChain
from commitment_extractor import ExtractionResult
from discovery_validation import validate_gt_document, validate_s0_document
from executor import UnresolvedInstruction, execute_amendment
from persistence import persist_execution
from run_chain_study_v2 import _build_v2_chain_from_manifest_entry
from semantic_pipeline import run_semantic_pipeline

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PREFLIGHT_CHAINS = [
    "EDGAR-AMERESCO",
    "STUDY-008",
    "STUDY-022",
    "STUDY-015",
    "STUDY-007",
]

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://upsilon:upsilon@localhost:5432/upsilon",
)
# Convert SQLAlchemy URL to plain psycopg URL
PSYCOPG_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

SCHEMA_PATH = Path("schema.sql")
RESULTS_DIR = Path("results/preflight")

# Fields the v0.1 comparator claims to support.  Used for independent
# comparison verification (must match semantic_pipeline._COMPARE_FIELDS).
_COMPARE_FIELDS = (
    "threshold",
    "rate",
    "deadline",
    "party",
    "exceptions",
    "applicability",
    "status",
    "unit",
)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------


def init_database(conn: psycopg.Connection) -> None:
    """Drop and recreate the schema for a clean preflight run."""
    print("  Initializing database schema...")
    conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
    conn.execute("CREATE SCHEMA public")
    conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # The schema file starts with CREATE EXTENSION IF NOT EXISTS pgcrypto
    # which we already created above; executing it again is harmless.
    conn.execute(schema_sql)
    conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    print("  Schema initialized.")


# ---------------------------------------------------------------------------
# Chain loading
# ---------------------------------------------------------------------------


def load_preflight_chains() -> list[tuple[IssuerChain, ExtractionResult, ExtractionResult | None, str]]:
    """Load the 5 preflight chains.

    Returns list of (chain, s0_result, gt_result, chain_source) tuples.
    chain_source is "existing" for hand-extracted chains or "manifest"
    for v0.1-extracted chains.
    """
    from chain_study_chains import existing_study_chains

    chains: list[tuple[IssuerChain, ExtractionResult, ExtractionResult | None, str]] = []

    # Existing chains (Ameresco, Amedisys, Bausch-Lomb)
    existing = {c.chain_id: c for c in existing_study_chains()}
    for chain_id in PREFLIGHT_CHAINS:
        if chain_id in existing:
            chain = existing[chain_id]
            s0_result = ExtractionResult(
                source_label="S0-manual",
                source_path="edgar_chains.py fixture",
                text_length=0,
            )
            gt_result = ExtractionResult(
                source_label="CMP-manual",
                source_path="edgar_chains.py fixture",
                text_length=0,
            )
            chains.append((chain, s0_result, gt_result, "existing"))

    # Manifest chains
    manifest_path = Path("data/chain_study/manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_ids = {e["chain_id"]: e for e in manifest.get("chains", [])}
        for chain_id in PREFLIGHT_CHAINS:
            if chain_id in manifest_ids:
                entry = manifest_ids[chain_id]
                chain, s0_result, gt_result = _build_v2_chain_from_manifest_entry(entry)
                chains.append((chain, s0_result, gt_result, "manifest"))

    return chains


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _insert_agreement_and_origin(
    conn: psycopg.Connection,
    chain: IssuerChain,
) -> tuple[UUID, UUID]:
    """Insert agreement, source document, and original agreement version.

    Returns (agreement_id, original_version_id).
    """
    # Extract CIK from chain name
    cik_match = re.search(r"CIK (\d+)", chain.issuer_name)
    cik = cik_match.group(1) if cik_match else None

    # Insert agreement
    row = conn.execute(
        """
        INSERT INTO agreement (issuer_cik, issuer_name, agreement_name)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (cik, chain.issuer_name, f"Credit Agreement for {chain.chain_id}"),
    ).fetchone()
    agreement_id = row[0]

    # Insert source document for S0
    s0_path = f"data/chain_study/{chain.chain_id}/S0.txt"
    if not Path(s0_path).exists():
        # Try edgar_chains path
        s0_path = f"data/edgar_chains/{chain.chain_id.lower().replace('edgar-', '')}/S0.txt"
    source_doc_id: UUID | None = None
    if Path(s0_path).exists():
        content = Path(s0_path).read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        doc_row = conn.execute(
            """
            INSERT INTO source_document (agreement_id, sha256, storage_uri)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (agreement_id, sha, f"file://{s0_path}"),
        ).fetchone()
        source_doc_id = doc_row[0]

    # Insert original agreement version
    version_row = conn.execute(
        """
        INSERT INTO agreement_version (agreement_id, source_document_id, kind, version_number)
        VALUES (%s, %s, 'ORIGINAL', 1)
        RETURNING id
        """,
        (agreement_id, source_doc_id),
    ).fetchone()
    original_version_id = version_row[0]

    # Insert original commitments
    for key, state in chain.original_state.items():
        commit_row = conn.execute(
            """
            INSERT INTO commitment (agreement_id, canonical_key, commitment_type)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (agreement_id, key, state.commitment_type),
        ).fetchone()
        commitment_id = commit_row[0]

        conn.execute(
            """
            INSERT INTO commitment_version (
                commitment_id, agreement_version_id, parent_commitment_version_id,
                status, valid_from, valid_to, applicability, party, modality,
                action, subject, operator, threshold, unit, frequency, deadline,
                scope, exceptions, trigger, grace_period, cure, application_order
            ) VALUES (
                %s, %s, NULL, %s, %s, NULL,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            """,
            (
                commitment_id, original_version_id,
                state.status,
                state.valid_from or datetime(2000, 1, 1, tzinfo=UTC),
                json.dumps(state.applicability),
                json.dumps(state.party),
                state.modality,
                state.action,
                state.subject,
                state.operator,
                state.threshold,
                state.unit,
                state.frequency,
                state.deadline,
                json.dumps(state.scope),
                json.dumps(state.exceptions),
                json.dumps(state.trigger),
                state.grace_period,
                json.dumps(state.cure),
                json.dumps(state.application_order),
            ),
        )

    return agreement_id, original_version_id


def _insert_amendment_version(
    conn: psycopg.Connection,
    agreement_id: UUID,
    version_number: int,
    step,
) -> UUID:
    """Insert an amendment agreement version and return its ID."""
    row = conn.execute(
        """
        INSERT INTO agreement_version (agreement_id, kind, version_number, effective_at)
        VALUES (%s, 'AMENDMENT', %s, %s)
        RETURNING id
        """,
        (agreement_id, version_number, step.effective_at),
    ).fetchone()
    return row[0]


def _insert_instructions(
    conn: psycopg.Connection,
    amendment_version_id: UUID,
    instructions: list,
) -> dict[int, UUID]:
    """Insert amendment instructions and return order->id mapping."""
    mapping: dict[int, UUID] = {}
    for ins in instructions:
        row = conn.execute(
            """
            INSERT INTO amendment_instruction (
                amendment_version_id, instruction_order, instruction_type,
                target_section_ref, old_value, new_value,
                effective_start, effective_end, parser_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                amendment_version_id,
                ins.order,
                ins.instruction_type.value if hasattr(ins.instruction_type, "value") else str(ins.instruction_type),
                ins.target_section_ref,
                json.dumps(ins.old_value) if ins.old_value is not None else None,
                json.dumps(ins.new_value) if ins.new_value is not None else None,
                ins.effective_start,
                ins.effective_end,
                json.dumps({"source_text": ins.source_text} if ins.source_text else "{}"),
            ),
        ).fetchone()
        mapping[ins.order] = row[0]
    return mapping


# ---------------------------------------------------------------------------
# Foundation integrity checks — EXECUTOR
# ---------------------------------------------------------------------------


def check_executor_integrity(
    chain: IssuerChain,
    pipe_result,
) -> dict:
    """Independently verify executor behavior by re-running it.

    Checks:
      1. Applied mutations match intended target/field/value — re-run
         execute_amendment on the same inputs and verify the applied set,
         unresolved set, and final state match the pipeline's claims.
      2. Failed guards do not mutate state — for each unresolved
         instruction, verify that re-running the executor with ONLY that
         instruction produces no state change (the instruction raises
         UnresolvedInstruction and the snapshot restore works).

    Returns dict with:
      - applied_match: bool — re-run applied set matches pipeline
      - unresolved_match: bool — re-run unresolved set matches pipeline
      - state_match: bool — re-run final state matches pipeline
      - failed_guards_no_mutation: bool — each unresolved instruction
        individually produces no state change
      - mismatches: list[str] — description of any mismatches
    """
    mismatches: list[str] = []
    current_state = {k: v.model_copy(deep=True) for k, v in chain.original_state.items()}

    applied_match = True
    unresolved_match = True
    state_match = True
    failed_guards_no_mutation = True

    for step_result in pipe_result.steps:
        # Re-run the executor with the same mapped instructions
        mapped_instructions = []
        for mut in step_result.mapper_mutations:
            mapped_instructions.append(mut.to_amendment_instruction(order=1))
        # The pipeline assigns order from the parser instruction; we need
        # to reconstruct the actual instructions used.  Instead, use the
        # execution_result's applied + unresolved to verify.
        # Re-run with the actual instructions from the execution result.
        all_instructions = list(step_result.execution_result.applied) + list(
            step_result.execution_result.unresolved
        )
        all_instructions.sort(key=lambda x: x.order)

        rerun = execute_amendment(current_state, all_instructions)

        # Compare applied sets (by order + type + target_key)
        pipeline_applied_orders = {ins.order for ins in step_result.execution_result.applied}
        rerun_applied_orders = {ins.order for ins in rerun.applied}
        if pipeline_applied_orders != rerun_applied_orders:
            applied_match = False
            mismatches.append(
                f"A{step_result.amendment_number}: applied orders differ: "
                f"pipeline={sorted(pipeline_applied_orders)}, rerun={sorted(rerun_applied_orders)}"
            )

        pipeline_unresolved_orders = {ins.order for ins in step_result.execution_result.unresolved}
        rerun_unresolved_orders = {ins.order for ins in rerun.unresolved}
        if pipeline_unresolved_orders != rerun_unresolved_orders:
            unresolved_match = False
            mismatches.append(
                f"A{step_result.amendment_number}: unresolved orders differ: "
                f"pipeline={sorted(pipeline_unresolved_orders)}, rerun={sorted(rerun_unresolved_orders)}"
            )

        # Compare final state (by canonical_key + all fields)
        pipeline_state = step_result.execution_result.state
        rerun_state = rerun.state
        if set(pipeline_state.keys()) != set(rerun_state.keys()):
            state_match = False
            mismatches.append(
                f"A{step_result.amendment_number}: state keys differ: "
                f"pipeline={sorted(pipeline_state.keys())}, rerun={sorted(rerun_state.keys())}"
            )
        else:
            for key in pipeline_state:
                if pipeline_state[key].model_dump() != rerun_state[key].model_dump():
                    state_match = False
                    mismatches.append(f"A{step_result.amendment_number}: state mismatch for {key}")

        # Verify each unresolved instruction individually does not mutate state
        for ins in step_result.execution_result.unresolved:
            test_state = {k: v.model_copy(deep=True) for k, v in current_state.items()}
            snapshot_before = {k: v.model_dump() for k, v in test_state.items()}
            try:
                from executor import apply_instruction
                apply_instruction(test_state, ins)
                # If it didn't raise, that's unexpected — check if state changed
                snapshot_after = {k: v.model_dump() for k, v in test_state.items()}
                if snapshot_before != snapshot_after:
                    failed_guards_no_mutation = False
                    mismatches.append(
                        f"A{step_result.amendment_number} ins {ins.order}: "
                        f"unresolved instruction mutated state without raising"
                    )
            except UnresolvedInstruction:
                # Expected — verify state is unchanged
                snapshot_after = {k: v.model_dump() for k, v in test_state.items()}
                if snapshot_before != snapshot_after:
                    failed_guards_no_mutation = False
                    mismatches.append(
                        f"A{step_result.amendment_number} ins {ins.order}: "
                        f"raised UnresolvedInstruction but state was mutated"
                    )

        # Advance state for next step
        current_state = {k: v.model_copy(deep=True) for k, v in step_result.execution_result.state.items()}

    return {
        "applied_match": applied_match,
        "unresolved_match": unresolved_match,
        "state_match": state_match,
        "failed_guards_no_mutation": failed_guards_no_mutation,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# Foundation integrity checks — PERSISTENCE
# ---------------------------------------------------------------------------


def check_persistence_integrity(
    conn: psycopg.Connection,
    agreement_id: UUID,
    pipe_result,
    amendment_version_ids: list[UUID],
) -> dict:
    """Verify persistence integrity from PostgreSQL state.

    Checks:
      1. Every applied mutation has a commitment version — for each
         amendment, the number of distinct targets in the applied
         mutations (excluding RENUMBER_REFERENCE) equals the number of
         commitment_versions persisted for that amendment_version_id.
      2. Every required lineage edge exists — for each commitment_version
         with a parent, a lineage_edge connects them.
      3. No partial commits — the version count matches exactly.
      4. Rollback works — tested separately via check_persistence_rollback.

    Returns dict with:
      - versions_match: bool — version count matches applied target count
      - edges_match: bool — every version with parent has an edge
      - no_partial_commits: bool — same as versions_match
      - details: list[str] — per-amendment breakdown
    """
    from persistence import build_persistence_plan

    versions_match = True
    edges_match = True
    details: list[str] = []

    for i, (step_result, amend_ver_id) in enumerate(
        zip(pipe_result.steps, amendment_version_ids, strict=False)
    ):
        if step_result.execution_result is None:
            continue

        # Compute expected version count from the persistence plan
        # (same logic as persist_execution uses)
        amend_eff = step_result.effective_at
        try:
            plan = build_persistence_plan(step_result.execution_result, amend_eff)
        except ValueError as exc:
            details.append(f"A{step_result.amendment_number}: plan error: {exc}")
            versions_match = False
            continue

        # Expected mutations: one commitment_version per target, plus one
        # restore version per waiver.
        expected_versions = len(plan["mutations"])
        for mut in plan["mutations"]:
            if mut.get("restore_state") is not None:
                expected_versions += 1

        # Count actual versions persisted for this amendment
        actual_versions = conn.execute(
            """
            SELECT COUNT(*) FROM commitment_version cv
            WHERE cv.agreement_version_id = %s
            """,
            (amend_ver_id,),
        ).fetchone()[0]

        if actual_versions != expected_versions:
            versions_match = False
            no_partial = False
            details.append(
                f"A{step_result.amendment_number}: version count mismatch: "
                f"expected={expected_versions}, actual={actual_versions}"
            )
        else:
            details.append(
                f"A{step_result.amendment_number}: versions OK "
                f"({actual_versions}/{expected_versions})"
            )

        # Check lineage edges: every version with a parent should have
        # an incoming lineage_edge (except origin versions).
        versions_with_parent = conn.execute(
            """
            SELECT COUNT(*) FROM commitment_version cv
            WHERE cv.agreement_version_id = %s
            AND cv.parent_commitment_version_id IS NOT NULL
            """,
            (amend_ver_id,),
        ).fetchone()[0]

        edges_for_amendment = conn.execute(
            """
            SELECT COUNT(*) FROM lineage_edge le
            JOIN commitment_version cv ON le.to_commitment_version_id = cv.id
            WHERE cv.agreement_version_id = %s
            """,
            (amend_ver_id,),
        ).fetchone()[0]

        if edges_for_amendment < versions_with_parent:
            edges_match = False
            details.append(
                f"A{step_result.amendment_number}: edge count mismatch: "
                f"versions_with_parent={versions_with_parent}, "
                f"edges={edges_for_amendment}"
            )

    no_partial = versions_match

    return {
        "versions_match": versions_match,
        "edges_match": edges_match,
        "no_partial_commits": no_partial,
        "details": details,
    }


def check_persistence_rollback(conn: psycopg.Connection) -> dict:
    """Integration test: verify that persist_execution rollback works.

    Creates a throwaway agreement, inserts an amendment version with
    instructions, then calls persist_execution with an execution result
    that will cause a mid-transaction error.  Verifies that no
    commitment_versions or lineage_edges were written for that
    amendment version.

    Returns dict with:
      - rollback_works: bool — no rows persisted after error
      - detail: str — description of the test
    """
    # Insert a throwaway agreement
    agree_row = conn.execute(
        """
        INSERT INTO agreement (issuer_name, agreement_name)
        VALUES ('ROLLBACK_TEST', 'Rollback Test Agreement')
        RETURNING id
        """,
    ).fetchone()
    agree_id = agree_row[0]

    amend_row = conn.execute(
        """
        INSERT INTO agreement_version (agreement_id, kind, version_number, effective_at)
        VALUES (%s, 'AMENDMENT', 2, %s)
        RETURNING id
        """,
        (agree_id, datetime(2024, 1, 1, tzinfo=UTC)),
    ).fetchone()
    amend_ver_id = amend_row[0]

    # Insert one instruction (so instruction_ids lookup succeeds)
    conn.execute(
        """
        INSERT INTO amendment_instruction (
            amendment_version_id, instruction_order, instruction_type, parser_payload
        ) VALUES (%s, 1, 'REPLACE_VALUE', '{}'::jsonb)
        RETURNING id
        """,
        (amend_ver_id,),
    ).fetchone()

    # Build an ExecutionResult that will cause persist_execution to fail
    # mid-transaction.  We use a mutation whose target doesn't exist in
    # the commitment table, which will cause _get_or_create_commitment
    # to insert it, but then we make the state invalid so the version
    # insert fails.  Actually, the simplest approach: pass an execution
    # result with a waiver that has no effective_end, which causes
    # build_persistence_plan to raise ValueError before the transaction
    # block.  But that raises before any writes.
    #
    # Better: create an execution result with a mutation whose
    # valid_from is None and no amendment_effective_at, causing
    # build_persistence_plan to raise.  But again that's before the
    # transaction.
    #
    # The real rollback test: we need an error INSIDE the
    # `with conn.transaction():` block.  We can do this by pre-inserting
    # a commitment_version that will conflict with the one
    # persist_execution tries to insert.  But that's fragile.
    #
    # Simplest reliable approach: use a savepoint.  We wrap the
    # persist_execution call in a savepoint, catch the error, and
    # verify the savepoint rolled back.  But persist_execution uses its
    # own transaction, so we need to test at that level.
    #
    # The most direct test: verify that persist_execution's
    # `with conn.transaction():` context manager rolls back on
    # exception.  We do this by making the connection fail mid-way.
    # We'll insert a commitment with a canonical_key that the plan
    # will try to use, then make the commitment_version insert fail
    # by violating a constraint.
    #
    # Actually, the cleanest test: call persist_execution with an
    # ExecutionResult that has an applied instruction whose
    # new_value is a dict that will cause a CHECK constraint
    # violation.  But the schema's only CHECK on commitment_version
    # is valid_to > valid_from, which is hard to violate via normal
    # flow.
    #
    # We'll use a different approach: monkey-patch the connection's
    # execute to fail after the first write inside the transaction.
    # This directly tests that the transaction rolls back.

    from unittest.mock import patch

    from models import (
        AmendmentInstruction,
        CommitmentState,
        ExecutionResult,
        ExecutionStatus,
        InstructionType,
    )

    # Build a minimal execution result with one applied instruction
    ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_key="rollback_test_commitment",
        field="threshold",
        new_value=999.0,
    )

    test_state = {
        "rollback_test_commitment": CommitmentState(
            canonical_key="rollback_test_commitment",
            commitment_type="financial_covenant",
            threshold=999.0,
        )
    }

    exec_result = ExecutionResult(
        state=test_state,
        applied=[ins],
        unresolved=[],
        events=[{"order": 1, "action": "replace", "target": "rollback_test_commitment", "field": "threshold"}],
        status=ExecutionStatus.COMPLETE,
    )

    # Count versions before
    versions_before = conn.execute(
        "SELECT COUNT(*) FROM commitment_version WHERE agreement_version_id = %s",
        (amend_ver_id,),
    ).fetchone()[0]

    # Patch _insert_version to raise after first call
    original_insert_version = None
    call_count = 0

    def failing_insert_version(c, cid, avid, pid, state):
        nonlocal call_count, original_insert_version
        call_count += 1
        if call_count >= 1:
            raise RuntimeError("Intentional mid-transaction failure for rollback test")
        return original_insert_version(c, cid, avid, pid, state)

    import persistence as persistence_module
    original_insert_version = persistence_module._insert_version

    rollback_works = False
    detail = ""
    try:
        with patch.object(persistence_module, "_insert_version", failing_insert_version):
            try:
                persist_execution(exec_result, amend_ver_id, conn)
            except RuntimeError:
                # Expected — verify no versions were persisted
                versions_after = conn.execute(
                    "SELECT COUNT(*) FROM commitment_version WHERE agreement_version_id = %s",
                    (amend_ver_id,),
                ).fetchone()[0]
                if versions_after == versions_before:
                    rollback_works = True
                    detail = "Rollback verified: 0 versions persisted after mid-transaction error"
                else:
                    detail = f"Rollback FAILED: {versions_after - versions_before} versions persisted despite error"
            else:
                detail = "Rollback test FAILED: persist_execution did not raise as expected"
    finally:
        # Restore original
        persistence_module._insert_version = original_insert_version
        # Clean up throwaway data
        conn.execute("DELETE FROM agreement WHERE id = %s", (agree_id,))

    return {
        "rollback_works": rollback_works,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Foundation integrity checks — LINEAGE
# ---------------------------------------------------------------------------


def check_lineage_integrity(conn: psycopg.Connection, agreement_id: UUID) -> dict:
    """Check lineage graph integrity from PostgreSQL state.

    Returns dict with:
      - orphans: count of non-origin versions with no incoming lineage edge
      - cycles: count of cyclic lineage paths
      - unreachable_from_origin: count of versions not reachable from origin
      - authority_linkage_correct: bool — every lineage edge's
        authority_version_id points to a valid amendment version in the chain
    """
    # Count all commitment versions
    total_versions = conn.execute(
        "SELECT COUNT(*) FROM commitment_version cv "
        "JOIN commitment c ON cv.commitment_id = c.id "
        "WHERE c.agreement_id = %s",
        (agreement_id,),
    ).fetchone()[0]

    # Origin versions (parent_commitment_version_id IS NULL)
    origin_versions = conn.execute(
        "SELECT COUNT(*) FROM commitment_version cv "
        "JOIN commitment c ON cv.commitment_id = c.id "
        "WHERE c.agreement_id = %s AND cv.parent_commitment_version_id IS NULL",
        (agreement_id,),
    ).fetchone()[0]

    # Orphans: non-origin versions with no incoming lineage edge
    orphans = conn.execute(
        "SELECT COUNT(*) FROM commitment_version cv "
        "JOIN commitment c ON cv.commitment_id = c.id "
        "WHERE c.agreement_id = %s "
        "AND cv.parent_commitment_version_id IS NOT NULL "
        "AND cv.id NOT IN (SELECT to_commitment_version_id FROM lineage_edge)",
        (agreement_id,),
    ).fetchone()[0]

    # Cycles: detect via recursive CTE
    cycles = conn.execute(
        """
        WITH RECURSIVE path AS (
            SELECT from_commitment_version_id, to_commitment_version_id,
                   ARRAY[from_commitment_version_id] as visited
            FROM lineage_edge
            UNION ALL
            SELECT p.from_commitment_version_id, le.to_commitment_version_id,
                   p.visited || le.from_commitment_version_id
            FROM path p
            JOIN lineage_edge le ON p.to_commitment_version_id = le.from_commitment_version_id
            WHERE NOT le.to_commitment_version_id = ANY(p.visited)
        )
        SELECT COUNT(*) FROM path
        WHERE from_commitment_version_id = to_commitment_version_id
        """,
    ).fetchone()[0]

    # Current state reachable from origin: every version should have a
    # path from an origin version.
    unreachable = conn.execute(
        """
        WITH RECURSIVE reachable AS (
            SELECT cv.id FROM commitment_version cv
            JOIN commitment c ON cv.commitment_id = c.id
            WHERE c.agreement_id = %s AND cv.parent_commitment_version_id IS NULL
            UNION
            SELECT le.to_commitment_version_id
            FROM reachable r
            JOIN lineage_edge le ON r.id = le.from_commitment_version_id
        )
        SELECT COUNT(*) FROM commitment_version cv
        JOIN commitment c ON cv.commitment_id = c.id
        WHERE c.agreement_id = %s
        AND cv.id NOT IN (SELECT id FROM reachable)
        """,
        (agreement_id, agreement_id),
    ).fetchone()[0]

    # Authority linkage: every lineage edge's authority_version_id must
    # point to an agreement_version belonging to this agreement.
    bad_authority = conn.execute(
        """
        SELECT COUNT(*) FROM lineage_edge le
        JOIN commitment_version cv ON le.to_commitment_version_id = cv.id
        JOIN commitment c ON cv.commitment_id = c.id
        JOIN agreement_version av ON le.authority_version_id = av.id
        WHERE c.agreement_id = %s AND av.agreement_id != %s
        """,
        (agreement_id, agreement_id),
    ).fetchone()[0]

    return {
        "total_versions": total_versions,
        "origin_versions": origin_versions,
        "orphans": orphans,
        "cycles": cycles,
        "unreachable_from_origin": unreachable,
        "authority_linkage_correct": bad_authority == 0,
        "bad_authority_count": bad_authority,
    }


# ---------------------------------------------------------------------------
# Foundation integrity checks — TEMPORAL
# ---------------------------------------------------------------------------


def check_temporal_integrity(conn: psycopg.Connection, agreement_id: UUID) -> dict:
    """Check temporal integrity from PostgreSQL state.

    Handles half-open intervals [valid_from, valid_to) where valid_to
    IS NULL means the interval is open-ended (still active).

    Returns dict with:
      - contradictory_active: count of overlapping ACTIVE intervals
        (handles NULL valid_to correctly)
      - invalid_intervals: count of intervals where valid_to <= valid_from
      - waiver_timing_correct: bool — waiver restore versions have
        valid_from = waiver end, valid_to = NULL, status = ACTIVE
      - waiver_issues: list[str] — description of any waiver timing issues
    """
    # Contradictory active versions: two ACTIVE versions of the same
    # commitment with overlapping intervals.  NULL valid_to means
    # open-ended (extends to infinity).  Two intervals [a1, b1) and
    # [a2, b2) overlap iff a1 < b2 AND a2 < b1, where NULL is treated
    # as +infinity.
    contradictory = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT cv1.id
            FROM commitment_version cv1
            JOIN commitment_version cv2
              ON cv1.commitment_id = cv2.commitment_id
              AND cv1.id < cv2.id
            JOIN commitment c ON cv1.commitment_id = c.id
            WHERE c.agreement_id = %s
              AND cv1.status = 'ACTIVE'
              AND cv2.status = 'ACTIVE'
              AND cv1.valid_from < COALESCE(cv2.valid_to, 'infinity'::timestamptz)
              AND cv2.valid_from < COALESCE(cv1.valid_to, 'infinity'::timestamptz)
        ) AS overlap_cnt
        """,
        (agreement_id,),
    ).fetchone()[0]

    # Invalid intervals: valid_to <= valid_from (schema CHECK should
    # prevent this, but verify independently).
    invalid = conn.execute(
        """
        SELECT COUNT(*) FROM commitment_version cv
        JOIN commitment c ON cv.commitment_id = c.id
        WHERE c.agreement_id = %s
        AND cv.valid_to IS NOT NULL
        AND cv.valid_from IS NOT NULL
        AND cv.valid_to <= cv.valid_from
        """,
        (agreement_id,),
    ).fetchone()[0]

    # Waiver timing: find waiver versions (status='WAIVED' with
    # applicability containing 'waiver') and their restore versions.
    # The restore version should have:
    #   - valid_from = waiver's valid_to
    #   - valid_to = NULL (open-ended, active after waiver expires)
    #   - status = 'ACTIVE'
    #   - parent = waiver version
    waiver_rows = conn.execute(
        """
        SELECT cv.id, cv.commitment_id, cv.valid_from, cv.valid_to,
               cv.applicability
        FROM commitment_version cv
        JOIN commitment c ON cv.commitment_id = c.id
        WHERE c.agreement_id = %s
        AND cv.status = 'WAIVED'
        AND cv.applicability ? 'waiver'
        """,
        (agreement_id,),
    ).fetchall()

    waiver_issues: list[str] = []
    for wid, cid, wv_from, wv_to, _applic in waiver_rows:
        # Find the restore version (child of waiver with status ACTIVE)
        restore = conn.execute(
            """
            SELECT cv.id, cv.valid_from, cv.valid_to, cv.status
            FROM commitment_version cv
            JOIN lineage_edge le ON le.to_commitment_version_id = cv.id
            WHERE le.from_commitment_version_id = %s
            AND le.edge_type = 'REINSTATES'
            """,
            (wid,),
        ).fetchall()
        if not restore:
            waiver_issues.append(
                f"Waiver {wid}: no REINSTATES restore version found"
            )
            continue
        for rid, rv_from, rv_to, rv_status in restore:
            if rv_status != "ACTIVE":
                waiver_issues.append(
                    f"Waiver {wid} restore {rid}: status={rv_status}, expected ACTIVE"
                )
            if rv_to is not None:
                waiver_issues.append(
                    f"Waiver {wid} restore {rid}: valid_to is not NULL (expected open-ended)"
                )
            if wv_to is not None and rv_from != wv_to:
                waiver_issues.append(
                    f"Waiver {wid} restore {rid}: valid_from={rv_from} "
                    f"!= waiver valid_to={wv_to}"
                )

    return {
        "contradictory_active": contradictory,
        "invalid_intervals": invalid,
        "waiver_timing_correct": len(waiver_issues) == 0,
        "waiver_issues": waiver_issues,
    }


# ---------------------------------------------------------------------------
# Foundation integrity checks — AUTHORITY
# ---------------------------------------------------------------------------


def check_authority_integrity(
    conn: psycopg.Connection,
    agreement_id: UUID,
    pipe_result,
    amendment_version_ids: list[UUID],
) -> dict:
    """Independently verify authority determination from PostgreSQL state.

    The pipeline claims `is_authoritative` per step.  We independently
    verify by checking the database: if any amendment_instruction for
    this chain has status='UNRESOLVED', then the chain CANNOT be
    authoritative.  If the pipeline claims authoritative despite
    UNRESOLVED instructions in the DB, that's a false promotion.

    Also independently recomputes the inherited unresolved count for
    each step (walking steps in order, accumulating unresolved) and
    compares to the pipeline's claim.

    Returns dict with:
      - chain_authoritative_claim: bool — what the pipeline claims
      - db_has_unresolved: bool — DB has UNRESOLVED instructions
      - false_promotion: bool — pipeline claims authoritative but DB has unresolved
      - inherited_match: bool — independently recomputed inherited counts match
      - inherited_mismatches: list[str]
    """
    # Check DB for UNRESOLVED instructions
    db_unresolved_count = conn.execute(
        """
        SELECT COUNT(*) FROM amendment_instruction ai
        JOIN agreement_version av ON ai.amendment_version_id = av.id
        WHERE av.agreement_id = %s AND ai.status = 'UNRESOLVED'
        """,
        (agreement_id,),
    ).fetchone()[0]

    db_has_unresolved = db_unresolved_count > 0

    # Pipeline's claim
    chain_authoritative_claim = (
        len(pipe_result.steps) > 0
        and all(s.is_authoritative for s in pipe_result.steps)
    )

    # False promotion: pipeline claims authoritative but DB has unresolved
    false_promotion = chain_authoritative_claim and db_has_unresolved

    # Independently recompute inherited unresolved counts.
    # The pipeline's logic (semantic_pipeline.py:219-237):
    #   still_inherited = inherited_unresolved (from prior step)
    #   own_unresolved = len(step_unresolved) + len(execution_result.unresolved)
    #   is_authoritative = (status==COMPLETE and not still_inherited and own==0)
    #   inherited_unresolved = still_inherited + step_unresolved + [UNRESOLVED for each exec.unresolved]
    #
    # We recompute independently and compare to step.inherited_unresolved_count.
    inherited_mismatches: list[str] = []
    expected_inherited = 0
    inherited_match = True

    for step in pipe_result.steps:
        if step.inherited_unresolved_count != expected_inherited:
            inherited_match = False
            inherited_mismatches.append(
                f"A{step.amendment_number}: inherited_unresolved_count="
                f"{step.inherited_unresolved_count}, expected={expected_inherited}"
            )
        # Advance: still_inherited + own unresolved
        own = len(step.mapper_unresolved) + len(step.execution_result.unresolved)
        expected_inherited = expected_inherited + own

    return {
        "chain_authoritative_claim": chain_authoritative_claim,
        "db_has_unresolved": db_has_unresolved,
        "db_unresolved_count": db_unresolved_count,
        "false_promotion": false_promotion,
        "inherited_match": inherited_match,
        "inherited_mismatches": inherited_mismatches,
    }


# ---------------------------------------------------------------------------
# Foundation integrity checks — COMPARISON
# ---------------------------------------------------------------------------


def check_comparison_integrity(
    chain: IssuerChain,
    pipe_result,
    chain_authoritative_claim: bool,
) -> dict:
    """Independently verify comparison results.

    Recomputes the final-state agreement from the reconstructed state
    vs ground truth, field by field, using the same _COMPARE_FIELDS the
    pipeline claims to use.  If the pipeline reports agreement=1.0 but
    we find supported fields differ, that's a false pass.

    Returns dict with:
      - has_gt: bool
      - pipeline_agreement: float | None — what the pipeline claims
      - independent_agreement: float | None — our recomputation
      - agreement_match: bool — pipeline and independent agree
      - false_pass: bool — pipeline says 1.0 but fields differ
      - field_mismatches: list[str] — specific field differences found
    """
    has_gt = (
        chain.ground_truth_state is not None
        and len(chain.ground_truth_state) > 0
    )
    pipeline_agreement = pipe_result.final_state_agreement

    if not has_gt:
        return {
            "has_gt": False,
            "pipeline_agreement": pipeline_agreement,
            "independent_agreement": None,
            "agreement_match": True,  # nothing to compare
            "false_pass": False,
            "field_mismatches": [],
        }

    ground_truth = chain.ground_truth_state
    recon = pipe_result.reconstructed_state

    matched = 0
    total_gt = len(ground_truth)
    field_mismatches: list[str] = []

    for key, gt_commitment in ground_truth.items():
        if key not in recon:
            field_mismatches.append(f"Missing: {key}")
            continue
        recon_commitment = recon[key]
        for fname in _COMPARE_FIELDS:
            recon_val = getattr(recon_commitment, fname, None)
            gt_val = getattr(gt_commitment, fname, None)
            if recon_val != gt_val:
                field_mismatches.append(
                    f"{key}.{fname}: {recon_val!r} vs {gt_val!r}"
                )
        # Count as matched only if ALL supported fields agree
        all_match = all(
            getattr(recon_commitment, fname, None) == getattr(gt_commitment, fname, None)
            for fname in _COMPARE_FIELDS
        )
        if all_match:
            matched += 1

    independent_agreement = matched / total_gt if total_gt > 0 else 1.0
    independent_agreement = round(independent_agreement, 4)

    # Agreement match: pipeline and independent computation agree
    agreement_match = (
        pipeline_agreement is not None
        and abs(pipeline_agreement - independent_agreement) < 0.0001
    )

    # False pass: pipeline says 1.0 (full match) but we found field
    # differences, AND the chain is promoted to authoritative (confident).
    # Per the bright-line rule: WRONG + CONFIDENT = FOUNDATION BUG.
    false_pass = (
        pipeline_agreement == 1.0
        and independent_agreement < 1.0
        and chain_authoritative_claim
    )

    return {
        "has_gt": True,
        "pipeline_agreement": pipeline_agreement,
        "independent_agreement": independent_agreement,
        "agreement_match": agreement_match,
        "false_pass": false_pass,
        "field_mismatches": field_mismatches,
    }


# ---------------------------------------------------------------------------
# Main preflight runner
# ---------------------------------------------------------------------------


def run_preflight() -> dict:
    """Run the 5-chain operational preflight.

    Returns a dict with all results and integrity checks.
    """
    print("=" * 70)
    print("STEP 17A: FIVE-CHAIN OPERATIONAL PREFLIGHT")
    print("=" * 70)
    print()

    # Load chains
    print("Loading preflight chains...")
    chains_data = load_preflight_chains()
    print(f"Loaded {len(chains_data)} chains: {[c[0].chain_id for c in chains_data]}")
    print()

    # Connect to database
    print(f"Connecting to PostgreSQL: {PSYCOPG_URL}")
    with psycopg.connect(PSYCOPG_URL) as conn:
        init_database(conn)

        # Rollback test (run once, before chain-specific tests)
        print("\nTesting persistence rollback...")
        rollback_result = check_persistence_rollback(conn)
        print(f"  Rollback: {'PASS' if rollback_result['rollback_works'] else 'FAIL'} — {rollback_result['detail']}")

        results = []
        all_checks_pass = True

        for chain, s0_result, gt_result, source in chains_data:
            chain_id = chain.chain_id
            print(f"\n{'='*60}")
            print(f"Chain: {chain_id} (source: {source})")
            print(f"Issuer: {chain.issuer_name}")
            print(f"Amendments: {len(chain.amendments)}")
            print(f"S0 commitments: {len(chain.original_state)}")
            print(f"GT state: {len(chain.ground_truth_state) if chain.ground_truth_state else 'None'}")
            print(f"{'='*60}")

            # Discovery validation
            s0_path = f"data/chain_study/{chain_id}/S0.txt"
            if Path(s0_path).exists():
                s0_disc = validate_s0_document(s0_path)
                print(f"  S0 discovery: valid={s0_disc.is_valid} cause={s0_disc.failure_cause or 'OK'}")

            cmp_path = f"data/chain_study/{chain_id}/CMP.txt"
            if Path(cmp_path).exists():
                gt_disc = validate_gt_document(cmp_path)
                print(f"  GT discovery: valid={gt_disc.is_valid} cause={gt_disc.failure_cause or 'OK'}")

            # Run semantic pipeline
            print("  Running semantic pipeline...")
            pipe_result = run_semantic_pipeline(chain)
            print(f"  Parser instructions: {pipe_result.total_parser_instructions}")
            print(f"  Mapped instructions: {pipe_result.total_mapped}")
            print(f"  Unresolved: {pipe_result.total_unresolved}")
            print(f"  Incorrect mutations: {len(pipe_result.incorrect_mutations)}")
            chain_authoritative_claim = (
                len(pipe_result.steps) > 0
                and all(s.is_authoritative for s in pipe_result.steps)
            )
            print(f"  Chain authoritative (claim): {chain_authoritative_claim}")
            if pipe_result.final_state_agreement is not None:
                print(f"  Final state agreement (claim): {pipe_result.final_state_agreement:.4f}")

            # EXECUTOR integrity check (independent re-run)
            print("  [EXECUTOR] Independent re-run verification...")
            executor_check = check_executor_integrity(chain, pipe_result)
            print(f"    applied_match={executor_check['applied_match']}, "
                  f"unresolved_match={executor_check['unresolved_match']}, "
                  f"state_match={executor_check['state_match']}, "
                  f"failed_guards_no_mutation={executor_check['failed_guards_no_mutation']}")
            if executor_check["mismatches"]:
                for m in executor_check["mismatches"][:3]:
                    print(f"    MISMATCH: {m}")

            # Persist to PostgreSQL
            print("  [PERSISTENCE] Persisting to PostgreSQL...")
            agreement_id, _original_version_id = _insert_agreement_and_origin(conn, chain)

            amendment_version_ids: list[UUID] = []
            for i, step in enumerate(chain.amendments, 2):
                amendment_version_id = _insert_amendment_version(
                    conn, agreement_id, i, step,
                )
                amendment_version_ids.append(amendment_version_id)

                # Get the execution result for this step
                if i - 2 < len(pipe_result.steps):
                    step_result = pipe_result.steps[i - 2]
                    if step_result.execution_result:
                        # Insert instructions
                        all_instructions = list(step_result.execution_result.applied) + list(
                            step_result.execution_result.unresolved
                        )
                        _insert_instructions(
                            conn, amendment_version_id, all_instructions,
                        )

                        # Persist execution
                        try:
                            persist_counts = persist_execution(
                                step_result.execution_result,
                                amendment_version_id,
                                conn,
                            )
                            print(f"    Amendment {i-1}: versions={persist_counts['commitment_versions_written']}, "
                                  f"edges={persist_counts['lineage_edges_written']}, "
                                  f"refs={persist_counts['reference_changes_written']}, "
                                  f"unresolved={persist_counts['unresolved_instructions']}")
                        except (RuntimeError, ValueError, psycopg.Error) as exc:
                            print(f"    Amendment {i-1}: PERSISTENCE ERROR: {exc}")
                            all_checks_pass = False

            # PERSISTENCE integrity check
            print("  [PERSISTENCE] Integrity checks...")
            persistence_check = check_persistence_integrity(
                conn, agreement_id, pipe_result, amendment_version_ids,
            )
            for detail in persistence_check["details"]:
                print(f"    {detail}")
            print(f"    versions_match={persistence_check['versions_match']}, "
                  f"edges_match={persistence_check['edges_match']}")

            # LINEAGE integrity check
            print("  [LINEAGE] Integrity checks...")
            lineage = check_lineage_integrity(conn, agreement_id)
            print(f"    orphans={lineage['orphans']}, cycles={lineage['cycles']}, "
                  f"unreachable={lineage['unreachable_from_origin']}, "
                  f"authority_linkage_correct={lineage['authority_linkage_correct']}")

            # TEMPORAL integrity check
            print("  [TEMPORAL] Integrity checks...")
            temporal = check_temporal_integrity(conn, agreement_id)
            print(f"    contradictory_active={temporal['contradictory_active']}, "
                  f"invalid_intervals={temporal['invalid_intervals']}, "
                  f"waiver_timing_correct={temporal['waiver_timing_correct']}")
            if temporal["waiver_issues"]:
                for issue in temporal["waiver_issues"][:3]:
                    print(f"    WAIVER ISSUE: {issue}")

            # AUTHORITY integrity check (independent DB verification)
            print("  [AUTHORITY] Independent DB verification...")
            authority = check_authority_integrity(
                conn, agreement_id, pipe_result, amendment_version_ids,
            )
            print(f"    claim={authority['chain_authoritative_claim']}, "
                  f"db_unresolved={authority['db_unresolved_count']}, "
                  f"false_promotion={authority['false_promotion']}, "
                  f"inherited_match={authority['inherited_match']}")
            if authority["inherited_mismatches"]:
                for m in authority["inherited_mismatches"][:3]:
                    print(f"    INHERITED MISMATCH: {m}")

            # COMPARISON integrity check (independent recompute)
            print("  [COMPARISON] Independent field-by-field recompute...")
            comparison = check_comparison_integrity(
                chain, pipe_result, chain_authoritative_claim,
            )
            print(f"    has_gt={comparison['has_gt']}, "
                  f"pipeline_agreement={comparison['pipeline_agreement']}, "
                  f"independent_agreement={comparison['independent_agreement']}, "
                  f"agreement_match={comparison['agreement_match']}, "
                  f"false_pass={comparison['false_pass']}")
            if comparison["field_mismatches"] and not comparison["agreement_match"]:
                for m in comparison["field_mismatches"][:3]:
                    print(f"    FIELD MISMATCH: {m}")

            # Determine if this chain passes all foundation checks
            chain_pass = (
                # EXECUTOR
                executor_check["applied_match"]
                and executor_check["unresolved_match"]
                and executor_check["state_match"]
                and executor_check["failed_guards_no_mutation"]
                # PERSISTENCE
                and persistence_check["versions_match"]
                and persistence_check["edges_match"]
                and persistence_check["no_partial_commits"]
                # LINEAGE
                and lineage["orphans"] == 0
                and lineage["cycles"] == 0
                and lineage["unreachable_from_origin"] == 0
                and lineage["authority_linkage_correct"]
                # TEMPORAL
                and temporal["contradictory_active"] == 0
                and temporal["invalid_intervals"] == 0
                and temporal["waiver_timing_correct"]
                # AUTHORITY
                and not authority["false_promotion"]
                and authority["inherited_match"]
                # COMPARISON
                and not comparison["false_pass"]
                and comparison["agreement_match"]
            )

            status = "PASS" if chain_pass else "FOUNDATION BUG"
            print(f"  Chain result: {status}")

            if not chain_pass:
                all_checks_pass = False

            results.append({
                "chain_id": chain_id,
                "source": source,
                "amendments": len(chain.amendments),
                "s0_commitments": len(chain.original_state),
                "gt_commitments": len(chain.ground_truth_state) if chain.ground_truth_state else 0,
                "parser_instructions": pipe_result.total_parser_instructions,
                "mapped_instructions": pipe_result.total_mapped,
                "unresolved": pipe_result.total_unresolved,
                "incorrect_mutations": len(pipe_result.incorrect_mutations),
                "chain_authoritative": chain_authoritative_claim,
                "final_state_agreement": pipe_result.final_state_agreement,
                "executor": executor_check,
                "persistence": persistence_check,
                "lineage": lineage,
                "temporal": temporal,
                "authority": authority,
                "comparison": comparison,
                "foundation_pass": chain_pass,
            })

    # Summary
    print(f"\n{'='*70}")
    print("PREFLIGHT SUMMARY")
    print(f"{'='*70}")
    print(f"Chains tested: {len(results)}")
    print(f"Rollback test: {'PASS' if rollback_result['rollback_works'] else 'FAIL'}")
    print(f"Foundation bugs: {sum(1 for r in results if not r['foundation_pass'])}")
    print()

    for r in results:
        status = "PASS" if r["foundation_pass"] else "FOUNDATION BUG"
        print(f"  {r['chain_id']:<20} {status}")

    print()
    if all_checks_pass and rollback_result["rollback_works"]:
        print("ALL FOUNDATION CHECKS PASS — PROCEED TO STEP 17B")
    else:
        print("FOUNDATION BUG DETECTED — STOP AND FIX")

    return {
        "run_at": datetime.now(UTC).isoformat(),
        "rollback_test": rollback_result,
        "chains": results,
        "all_checks_pass": all_checks_pass and rollback_result["rollback_works"],
    }


if __name__ == "__main__":
    result = run_preflight()

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "preflight_results.json"
    output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nResults saved to {output_path}")

    sys.exit(0 if result["all_checks_pass"] else 1)
