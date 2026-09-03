from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import Connection

from upsilon.models.legacy_models import AmendmentInstruction, CommitmentState, ExecutionResult, InstructionType


def build_persistence_plan(
    result: ExecutionResult,
    amendment_effective_at: datetime | None,
) -> dict[str, Any]:
    """
    Pure planning layer.

    Rules:
    - one commitment version per target commitment per amendment;
    - all applied instructions affecting that target point to that version;
    - reference renumberings are separate metadata events;
    - temporary waiver is a bounded state [start,end) followed by restoration of
      the post-amendment terms, not the pre-amendment terms.
    """
    by_order = {ins.order: ins for ins in result.applied}
    grouped: dict[str, list[AmendmentInstruction]] = {}

    for event in result.events:
        if event.get("status") == "UNRESOLVED":
            continue
        order = int(event["order"])
        ins = by_order[order]
        if ins.instruction_type == InstructionType.RENUMBER_REFERENCE:
            continue
        target = event.get("target")
        if target:
            grouped.setdefault(target, []).append(ins)

    mutations = []
    for target, instructions in grouped.items():
        if target not in result.state:
            raise ValueError(f"Missing final state for target {target}")

        state = result.state[target].model_copy(deep=True)

        starts = [i.effective_start for i in instructions if i.effective_start]
        valid_from = min(starts) if starts else amendment_effective_at
        if valid_from is None:
            raise ValueError(
                f"No effective time for state-changing amendment target {target}"
            )

        waiver_instructions = [
            i for i in instructions
            if i.instruction_type == InstructionType.WAIVE_TEMPORARILY
        ]

        valid_to = None
        restore_state = None
        if waiver_instructions:
            # MVP rule: overlapping/stacked waivers on the same commitment in one
            # amendment require human resolution rather than temporal guessing.
            if len(waiver_instructions) > 1:
                raise ValueError(f"Multiple waivers for target {target} require validation")
            waiver = waiver_instructions[0]
            if not waiver.effective_start or not waiver.effective_end:
                raise ValueError(f"Waiver for {target} lacks bounded effective interval")
            valid_from = waiver.effective_start
            valid_to = waiver.effective_end

            # Restore the final post-amendment economics, merely removing waiver state.
            restore_state = state.model_copy(deep=True)
            restore_state.status = "ACTIVE"
            restore_state.valid_from = valid_to
            restore_state.valid_to = None
            restore_state.applicability = dict(restore_state.applicability)
            restore_state.applicability.pop("waiver", None)

        state.valid_from = valid_from
        state.valid_to = valid_to

        mutations.append({
            "target": target,
            "state": state,
            "instructions": instructions,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "restore_state": restore_state,
        })

    return {
        "mutations": mutations,
        "reference_events": list(result.reference_events),
        "unresolved_orders": [ins.order for ins in result.unresolved],
    }


def _fetch_instruction_ids(conn: "Connection", amendment_version_id: UUID) -> dict[int, UUID]:
    rows = conn.execute(
        """
        SELECT instruction_order, id
        FROM amendment_instruction
        WHERE amendment_version_id = %s
        """,
        (amendment_version_id,),
    ).fetchall()
    return {int(order): iid for order, iid in rows}


def _get_agreement_version_context(
    conn: "Connection", agreement_version_id: UUID
) -> tuple[UUID, datetime | None]:
    row = conn.execute(
        """
        SELECT agreement_id, effective_at
        FROM agreement_version
        WHERE id = %s
        """,
        (agreement_version_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown agreement_version_id: {agreement_version_id}")
    return row[0], row[1]


def _get_or_create_commitment(
    conn: "Connection",
    agreement_id: UUID,
    state: CommitmentState,
) -> UUID:
    row = conn.execute(
        """
        SELECT id FROM commitment
        WHERE agreement_id = %s AND canonical_key = %s
        """,
        (agreement_id, state.canonical_key),
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        """
        INSERT INTO commitment (agreement_id, canonical_key, commitment_type)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (agreement_id, state.canonical_key, state.commitment_type),
    ).fetchone()[0]


def _latest_version(conn: "Connection", commitment_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
          id, status, valid_from, valid_to, applicability,
          party, modality, action, subject, operator, threshold, unit,
          frequency, deadline, scope, exceptions, trigger, grace_period,
          cure, application_order
        FROM commitment_version
        WHERE commitment_id = %s
        ORDER BY
            (valid_to IS NULL) DESC,
            valid_from DESC,
            recorded_at DESC,
            created_at DESC
        LIMIT 1
        """,
        (commitment_id,),
    ).fetchone()
    if not row:
        return None
    names = [
        "id","status","valid_from","valid_to","applicability",
        "party","modality","action","subject","operator","threshold","unit",
        "frequency","deadline","scope","exceptions","trigger","grace_period",
        "cure","application_order",
    ]
    return dict(zip(names, row))


def _insert_version(
    conn: "Connection",
    commitment_id: UUID,
    agreement_version_id: UUID,
    parent_id: UUID | None,
    state: CommitmentState,
) -> UUID:
    from psycopg.types.json import Jsonb
    return conn.execute(
        """
        INSERT INTO commitment_version (
          commitment_id, agreement_version_id, parent_commitment_version_id,
          status, valid_from, valid_to, applicability,
          party, modality, action, subject, operator, threshold, unit,
          frequency, deadline, scope, exceptions, trigger, grace_period,
          cure, application_order, normalized_payload
        )
        VALUES (
          %s,%s,%s,
          %s,%s,%s,%s,
          %s,%s,%s,%s,%s,%s,%s,
          %s,%s,%s,%s,%s,%s,
          %s,%s,%s
        )
        RETURNING id
        """,
        (
            commitment_id, agreement_version_id, parent_id,
            state.status, state.valid_from, state.valid_to, Jsonb(state.applicability),
            Jsonb(state.party), state.modality, state.action, state.subject,
            state.operator, state.threshold, state.unit, state.frequency,
            state.deadline, Jsonb(state.scope), Jsonb(state.exceptions),
            Jsonb(state.trigger), state.grace_period, Jsonb(state.cure),
            Jsonb(state.application_order), Jsonb(state.model_dump(mode="json")),
        ),
    ).fetchone()[0]


def _edge_type(ins: AmendmentInstruction) -> str:
    return {
        InstructionType.WAIVE_TEMPORARILY: "WAIVES",
        InstructionType.REINSTATE: "REINSTATES",
        InstructionType.DELETE_COMMITMENT: "SUPERSEDES",
        InstructionType.DELETE: "SUPERSEDES",
    }.get(ins.instruction_type, "MODIFIES")


def persist_execution(
    result: ExecutionResult,
    amendment_version_id: UUID,
    conn: "Connection",
) -> dict[str, int]:
    """
    Persist an amendment atomically.

    The amendment agreement version is the legal authority for every resulting
    state transition. No permanent `is_authoritative` flag is used.
    """
    agreement_id, amendment_effective_at = _get_agreement_version_context(
        conn, amendment_version_id
    )
    instruction_ids = _fetch_instruction_ids(conn, amendment_version_id)
    plan = build_persistence_plan(result, amendment_effective_at)

    written_versions = 0
    written_edges = 0
    written_refs = 0

    with conn.transaction():
        for order in plan["unresolved_orders"]:
            iid = instruction_ids.get(order)
            if iid:
                conn.execute(
                    "UPDATE amendment_instruction SET status = 'UNRESOLVED' WHERE id = %s",
                    (iid,),
                )

        # Reference renumbering is independently persisted and never mutates scope.
        for ref in plan["reference_events"]:
            order = int(ref["order"])
            iid = instruction_ids.get(order)
            target_key = ref.get("target_key")
            commitment_id = None
            if target_key:
                row = conn.execute(
                    """
                    SELECT id FROM commitment
                    WHERE agreement_id = %s AND canonical_key = %s
                    """,
                    (agreement_id, target_key),
                ).fetchone()
                commitment_id = row[0] if row else None

            ins = next((x for x in result.applied if x.order == order), None)
            effective_at = (
                ins.effective_start if ins and ins.effective_start
                else amendment_effective_at
            )
            if effective_at is None:
                raise ValueError("Reference change has no effective time")

            conn.execute(
                """
                INSERT INTO reference_change (
                  agreement_id, amendment_version_id, amendment_instruction_id,
                  commitment_id, old_section_ref, new_section_ref, effective_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    agreement_id, amendment_version_id, iid, commitment_id,
                    ref["old_section_ref"], ref["new_section_ref"], effective_at,
                ),
            )
            written_refs += 1
            if iid:
                conn.execute(
                    "UPDATE amendment_instruction SET status = 'APPLIED' WHERE id = %s",
                    (iid,),
                )

        for mutation in plan["mutations"]:
            state: CommitmentState = mutation["state"]
            commitment_id = _get_or_create_commitment(conn, agreement_id, state)
            prior = _latest_version(conn, commitment_id)
            parent_id = prior["id"] if prior else None

            # Close prior effective interval at the new state's start.
            if prior and (
                prior["valid_to"] is None
                or prior["valid_to"] > mutation["valid_from"]
            ):
                conn.execute(
                    "UPDATE commitment_version SET valid_to = %s WHERE id = %s",
                    (mutation["valid_from"], parent_id),
                )

            new_id = _insert_version(
                conn, commitment_id, amendment_version_id, parent_id, state
            )
            written_versions += 1

            # Every contributing amendment instruction is linked to the single
            # authoritative resulting state.
            if parent_id:
                for ins in mutation["instructions"]:
                    iid = instruction_ids.get(ins.order)
                    conn.execute(
                        """
                        INSERT INTO lineage_edge (
                          from_commitment_version_id, to_commitment_version_id,
                          amendment_instruction_id, edge_type, authority_version_id
                        )
                        VALUES (%s,%s,%s,%s,%s)
                        """,
                        (
                            parent_id, new_id, iid,
                            _edge_type(ins), amendment_version_id,
                        ),
                    )
                    written_edges += 1

            for ins in mutation["instructions"]:
                iid = instruction_ids.get(ins.order)
                if iid:
                    conn.execute(
                        "UPDATE amendment_instruction SET status = 'APPLIED' WHERE id = %s",
                        (iid,),
                    )

            restore_state = mutation["restore_state"]
            if restore_state is not None:
                restore_id = _insert_version(
                    conn, commitment_id, amendment_version_id, new_id, restore_state
                )
                waiver_ins = next(
                    i for i in mutation["instructions"]
                    if i.instruction_type == InstructionType.WAIVE_TEMPORARILY
                )
                iid = instruction_ids.get(waiver_ins.order)
                conn.execute(
                    """
                    INSERT INTO lineage_edge (
                      from_commitment_version_id, to_commitment_version_id,
                      amendment_instruction_id, edge_type, authority_version_id
                    )
                    VALUES (%s,%s,%s,'REINSTATES',%s)
                    """,
                    (new_id, restore_id, iid, amendment_version_id),
                )
                written_versions += 1
                written_edges += 1

    return {
        "commitment_versions_written": written_versions,
        "lineage_edges_written": written_edges,
        "reference_changes_written": written_refs,
        "unresolved_instructions": len(plan["unresolved_orders"]),
    }
