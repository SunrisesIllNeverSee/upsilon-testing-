"""End-to-end amendment-chain reconstruction harness.

This is the system smoke test for the Financial Commitment Integrity
tester. It drives the full pipeline:

    S0 original credit agreement
    ↓
    A1 amendment  →  reconstruct S1
    ↓
    A2 amendment  →  reconstruct S2
    ↓
    ...
    ↓
    compare reconstructed current state
    against filed composite / amended-and-restated ground truth

The harness uses the REAL executor (`executor.execute_amendment`) and
the REAL persistence planner (`persistence.build_persistence_plan`).
It does not reimplement application or lineage logic. The smoke test
validates that the system plumbing — sequential application, lineage
edge construction, unresolved-instruction blocking, and ground-truth
comparison — works end-to-end.

Chain fixtures in `synthetic_chains.py` are synthetic but model real
credit-agreement amendment-chain structure (sequential threshold
changes, commitment additions/deletions, waivers, and one chain with
an intentional UNRESOLVED instruction). Real multi-amendment chain
acquisition from EDGAR is the next phase (25-issuer chain study);
this smoke test validates the system before that acquisition work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from models import (
    AmendmentInstruction,
    CommitmentState,
    ExecutionResult,
    ExecutionStatus,
)
from executor import execute_amendment
from persistence import build_persistence_plan


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AmendmentStep:
    """One amendment in a chain: instructions + effective time."""

    amendment_number: int
    effective_at: datetime
    instructions: list[AmendmentInstruction]
    description: str = ""


@dataclass
class IssuerChain:
    """A complete issuer amendment chain with ground truth.

    Fields:
        chain_id: short identifier (e.g., "CHAIN-ACME")
        issuer_name: human-readable issuer name
        original_state: S0 — the original credit-agreement commitment kernel
        amendments: ordered list of AmendmentStep (A1, A2, ...)
        ground_truth_state: the filed composite / A&R authoritative state,
            used as the independent comparison target for Q4. May be None
            if no composite/A&R was filed for this chain.
        ground_truth_label: human-readable label for the ground-truth source
            (e.g., "Amended and Restated Credit Agreement, filed 2026-03-01")
    """

    chain_id: str
    issuer_name: str
    original_state: dict[str, CommitmentState]
    amendments: list[AmendmentStep]
    ground_truth_state: dict[str, CommitmentState] | None = None
    ground_truth_label: str | None = None


@dataclass
class StepResult:
    """Result of reconstructing one amendment step."""

    amendment_number: int
    effective_at: datetime
    execution_result: ExecutionResult
    persistence_plan: dict[str, Any]
    reconstructed_state: dict[str, CommitmentState]
    # True only if this step's state may be promoted to authoritative.
    # PARTIAL / UNRESOLVED executions are provisional and must not promote.
    is_authoritative: bool


@dataclass
class FieldMismatch:
    """A single field mismatch between reconstructed and ground-truth state."""

    canonical_key: str
    field: str
    reconstructed: Any
    ground_truth: Any


@dataclass
class ComparisonResult:
    """Field-by-field comparison of reconstructed vs ground-truth state."""

    exact_match: bool
    matched_commitments: int
    missing_commitments: list[str]  # in ground truth but not reconstructed
    extra_commitments: list[str]  # in reconstructed but not ground truth
    field_mismatches: list[FieldMismatch]
    # Commitments in reconstructed that are DELETED/SUPERSEDED and not in
    # ground truth are NOT counted as extra (they were intentionally removed).
    deleted_in_reconstructed: list[str]


@dataclass
class ChainReconstructionResult:
    """Full result of reconstructing an issuer chain."""

    chain_id: str
    issuer_name: str
    steps: list[StepResult]
    final_state: dict[str, CommitmentState]
    ground_truth_state: dict[str, CommitmentState] | None
    ground_truth_label: str | None
    comparison: ComparisonResult | None
    questions: dict[str, dict[str, Any]]


# ---------------------------------------------------------------------------
# Reconstruction engine
# ---------------------------------------------------------------------------


def _apply_expired_waiver_restores(
    state: dict[str, CommitmentState],
    plan: dict[str, Any],
    at_time: datetime,
) -> dict[str, CommitmentState]:
    """Return state with expired waivers restored to their post-amendment terms.

    The executor correctly produces the in-amendment state (status=WAIVED,
    bounded [valid_from, valid_to)). The persistence plan correctly
    produces a restore_state (status=ACTIVE, valid_from=waiver end). This
    helper implements the "kernel at time T" rule from
    COMMITMENT_LINEAGE_SCHEMA.md: if a waiver's valid_to <= at_time, the
    authoritative state at at_time is the restore_state, not the WAIVED
    version.

    This is the reconstruction layer's responsibility — the executor and
    persistence plan are correct as-is. The reconstruction picks the
    right version at time T when carrying state forward.
    """
    out = {k: v.model_copy(deep=True) for k, v in state.items()}
    for mutation in plan["mutations"]:
        restore = mutation.get("restore_state")
        if restore is None:
            continue
        # The waiver's valid_to is the restore_state's valid_from.
        restore_valid_from = restore.valid_from
        if restore_valid_from is not None and restore_valid_from <= at_time:
            out[mutation["target"]] = restore.model_copy(deep=True)
    return out


def reconstruct_chain(chain: IssuerChain) -> ChainReconstructionResult:
    """Run S0 → A1 → S1 → A2 → S2 → ... → Sn for one issuer chain.

    Each step uses the real executor and persistence planner. The
    reconstructed state after step N becomes the input to step N+1,
    with expired waivers restored to their post-amendment terms per
    the "kernel at time T" rule.
    """
    current_state = {k: v.model_copy(deep=True) for k, v in chain.original_state.items()}
    steps: list[StepResult] = []

    for i, step in enumerate(chain.amendments):
        execution_result = execute_amendment(current_state, step.instructions)
        plan = build_persistence_plan(execution_result, step.effective_at)
        reconstructed = execution_result.state

        is_authoritative = execution_result.status == ExecutionStatus.COMPLETE

        steps.append(
            StepResult(
                amendment_number=step.amendment_number,
                effective_at=step.effective_at,
                execution_result=execution_result,
                persistence_plan=plan,
                reconstructed_state=reconstructed,
                is_authoritative=is_authoritative,
            )
        )

        # Carry the state forward to the next amendment. If this step
        # produced a waiver and the next amendment's effective_at is
        # after the waiver's valid_to, the carry-forward state must use
        # the restore_state (ACTIVE) — the waiver has expired by then.
        # NOTE: even PARTIAL executions produce a (provisional) state,
        # but is_authoritative=False signals it must not be promoted.
        # For chaining purposes we still carry the state forward so the
        # next amendment can be applied — the unresolved instructions
        # are recorded and the provisional flag travels with the step.
        next_effective_at = (
            chain.amendments[i + 1].effective_at
            if i + 1 < len(chain.amendments)
            else step.effective_at
        )
        current_state = _apply_expired_waiver_restores(
            reconstructed, plan, next_effective_at
        )

    # The final state for ground-truth comparison. The ground truth
    # (composite/A&R) is filed after all amendments, so the authoritative
    # state at comparison time is the state with all expired waivers
    # restored. current_state already has restores applied for inter-step
    # carry-forward; for the last step we restore with datetime.max so
    # any waiver in the final amendment is also restored (the ground
    # truth reflects the post-waiver state).
    final_state = current_state
    if steps:
        last = steps[-1]
        final_state = _apply_expired_waiver_restores(
            final_state,
            last.persistence_plan,
            datetime.max.replace(tzinfo=last.effective_at.tzinfo),
        )
    comparison = (
        compare_to_ground_truth(final_state, chain.ground_truth_state)
        if chain.ground_truth_state is not None
        else None
    )
    questions = answer_four_questions(
        chain_id=chain.chain_id,
        steps=steps,
        final_state=final_state,
        ground_truth_state=chain.ground_truth_state,
        comparison=comparison,
    )

    return ChainReconstructionResult(
        chain_id=chain.chain_id,
        issuer_name=chain.issuer_name,
        steps=steps,
        final_state=final_state,
        ground_truth_state=chain.ground_truth_state,
        ground_truth_label=chain.ground_truth_label,
        comparison=comparison,
        questions=questions,
    )


# ---------------------------------------------------------------------------
# Ground-truth comparison
# ---------------------------------------------------------------------------

# Semantic fields compared for Q4. Temporal/infrastructure fields
# (valid_from, valid_to, applicability) are excluded because they are
# reconstruction metadata, not commitment semantics. The ground-truth
# composite/A&R carries the semantic state, not Upsilon's temporal model.
SEMANTIC_FIELDS = (
    "commitment_type",
    "status",
    "party",
    "modality",
    "action",
    "subject",
    "operator",
    "threshold",
    "unit",
    "frequency",
    "deadline",
    "scope",
    "exceptions",
    "grace_period",
)


def compare_to_ground_truth(
    reconstructed: dict[str, CommitmentState],
    ground_truth: dict[str, CommitmentState],
) -> ComparisonResult:
    """Field-by-field comparison of reconstructed vs ground-truth state.

    A commitment is "matched" if its canonical_key exists in both and
    every SEMANTIC_FIELDS field is equal. Commitments that are DELETED
    in reconstructed and absent from ground truth are not counted as
    extra — they were intentionally removed by an amendment.
    """
    rec_keys = set(reconstructed.keys())
    gt_keys = set(ground_truth.keys())

    missing = sorted(gt_keys - rec_keys)
    deleted_in_reconstructed = sorted(
        k for k in (rec_keys - gt_keys)
        if reconstructed[k].status in ("DELETED", "SUPERSEDED")
    )
    extra = sorted(
        k for k in (rec_keys - gt_keys)
        if reconstructed[k].status not in ("DELETED", "SUPERSEDED")
    )

    mismatches: list[FieldMismatch] = []
    matched = 0
    for key in sorted(gt_keys & rec_keys):
        rec = reconstructed[key]
        gt = ground_truth[key]
        # If reconstructed is DELETED but ground truth is ACTIVE, that's
        # a status mismatch (counted), not a "deleted in reconstructed".
        all_match = True
        for fname in SEMANTIC_FIELDS:
            rv = getattr(rec, fname)
            gv = getattr(gt, fname)
            if rv != gv:
                mismatches.append(
                    FieldMismatch(
                        canonical_key=key,
                        field=fname,
                        reconstructed=rv,
                        ground_truth=gv,
                    )
                )
                all_match = False
        if all_match:
            matched += 1

    exact_match = (
        not missing
        and not extra
        and not mismatches
        and matched == len(gt_keys)
    )

    return ComparisonResult(
        exact_match=exact_match,
        matched_commitments=matched,
        missing_commitments=missing,
        extra_commitments=extra,
        field_mismatches=mismatches,
        deleted_in_reconstructed=deleted_in_reconstructed,
    )


# ---------------------------------------------------------------------------
# The four smoke-test questions
# ---------------------------------------------------------------------------


def answer_four_questions(
    chain_id: str,
    steps: list[StepResult],
    final_state: dict[str, CommitmentState],
    ground_truth_state: dict[str, CommitmentState] | None,
    comparison: ComparisonResult | None,
) -> dict[str, dict[str, Any]]:
    """Answer the four system smoke-test questions mechanically.

    Each answer is a dict with:
        pass: bool — did this question pass for this chain?
        evidence: dict — the mechanical evidence supporting the answer
        summary: str — human-readable one-line summary
    """
    # --- Q1: Can Upsilon preserve authoritative state across amendments? ---
    # Pass: every step's status is COMPLETE (or PARTIAL with documented
    # unresolved), and no commitment is silently lost between steps.
    q1_evidence: dict[str, Any] = {
        "step_statuses": [s.execution_result.status.value for s in steps],
        "step_applied_counts": [len(s.execution_result.applied) for s in steps],
        "step_unresolved_counts": [len(s.execution_result.unresolved) for s in steps],
    }
    # Check no commitment silently lost: each step's reconstructed state
    # must be a superset of the prior step's non-DELETED commitments.
    silent_losses: list[str] = []
    prior_keys: set[str] = set()
    for s in steps:
        current_keys = set(s.reconstructed_state.keys())
        for k in prior_keys:
            if k not in current_keys:
                silent_losses.append(k)
        prior_keys = {
            k for k in current_keys
            if s.reconstructed_state[k].status not in ("DELETED", "SUPERSEDED")
        }
    q1_evidence["silent_commitment_losses"] = silent_losses
    q1_pass = (
        all(
            s.execution_result.status in (ExecutionStatus.COMPLETE, ExecutionStatus.PARTIAL)
            for s in steps
        )
        and not silent_losses
    )
    q1_evidence["authoritative_steps"] = sum(1 for s in steps if s.is_authoritative)
    q1_evidence["provisional_steps"] = sum(1 for s in steps if not s.is_authoritative)

    # --- Q2: Can it maintain complete lineage from origin to current state? ---
    # Pass: every state-changing step has a persistence plan with at least
    # one mutation, and every mutation has a valid_from (lineage anchor).
    q2_evidence: dict[str, Any] = {
        "step_mutation_counts": [len(s.persistence_plan["mutations"]) for s in steps],
        "step_unresolved_orders": [s.persistence_plan["unresolved_orders"] for s in steps],
    }
    lineage_gaps: list[str] = []
    for s in steps:
        if s.execution_result.applied and not s.persistence_plan["mutations"]:
            # Applied instructions but no mutations → lineage gap.
            # (Reference renumberings are not mutations; check if all
            # applied were renumberings.)
            non_ref = [
                i for i in s.execution_result.applied
                if i.instruction_type.value != "RENUMBER_REFERENCE"
            ]
            if non_ref:
                lineage_gaps.append(
                    f"A{s.amendment_number}: {len(non_ref)} applied non-reference "
                    f"instructions but 0 mutations"
                )
        for m in s.persistence_plan["mutations"]:
            if m["valid_from"] is None:
                lineage_gaps.append(
                    f"A{s.amendment_number}: mutation for {m['target']} has no valid_from"
                )
    q2_evidence["lineage_gaps"] = lineage_gaps
    q2_pass = not lineage_gaps

    # --- Q3: Does any unresolved instruction block authoritative promotion? ---
    # Pass: every step with unresolved instructions has
    #   is_authoritative=False AND status in (PARTIAL, UNRESOLVED).
    q3_evidence: dict[str, Any] = {
        "steps_with_unresolved": [
            {
                "amendment": s.amendment_number,
                "status": s.execution_result.status.value,
                "unresolved_count": len(s.execution_result.unresolved),
                "is_authoritative": s.is_authoritative,
            }
            for s in steps if s.execution_result.unresolved
        ],
    }
    promotion_blocked_correctly = True
    for s in steps:
        if s.execution_result.unresolved:
            if s.is_authoritative:
                promotion_blocked_correctly = False
                q3_evidence.setdefault("promotion_block_failures", []).append(
                    f"A{s.amendment_number}: has unresolved but is_authoritative=True"
                )
            if s.execution_result.status not in (
                ExecutionStatus.PARTIAL,
                ExecutionStatus.UNRESOLVED,
            ):
                promotion_blocked_correctly = False
                q3_evidence.setdefault("promotion_block_failures", []).append(
                    f"A{s.amendment_number}: has unresolved but status="
                    f"{s.execution_result.status.value}"
                )
    # Also verify the positive case: steps with no unresolved ARE authoritative.
    for s in steps:
        if not s.execution_result.unresolved and not s.is_authoritative:
            # No unresolved but not authoritative — only acceptable if it's
            # a no-op step (no applied and no unresolved).
            if s.execution_result.applied:
                promotion_blocked_correctly = False
                q3_evidence.setdefault("promotion_block_failures", []).append(
                    f"A{s.amendment_number}: no unresolved, has applied, "
                    f"but is_authoritative=False"
                )
    q3_evidence["promotion_blocked_correctly"] = promotion_blocked_correctly
    q3_pass = promotion_blocked_correctly

    # --- Q4: Does reconstructed state exactly match ground truth? ---
    if comparison is None:
        q4_evidence: dict[str, Any] = {"ground_truth_available": False}
        q4_pass = False
        q4_summary = "No ground-truth composite/A&R available for this chain"
    else:
        q4_evidence = {
            "ground_truth_available": True,
            "exact_match": comparison.exact_match,
            "matched_commitments": comparison.matched_commitments,
            "missing_commitments": comparison.missing_commitments,
            "extra_commitments": comparison.extra_commitments,
            "deleted_in_reconstructed": comparison.deleted_in_reconstructed,
            "field_mismatches": [
                {
                    "canonical_key": m.canonical_key,
                    "field": m.field,
                    "reconstructed": m.reconstructed,
                    "ground_truth": m.ground_truth,
                }
                for m in comparison.field_mismatches
            ],
        }
        q4_pass = comparison.exact_match
        q4_summary = (
            "exact match"
            if comparison.exact_match
            else f"{len(comparison.field_mismatches)} field mismatches, "
            f"{len(comparison.missing_commitments)} missing, "
            f"{len(comparison.extra_commitments)} extra"
        )

    return {
        "Q1_state_preservation": {
            "pass": q1_pass,
            "evidence": q1_evidence,
            "summary": (
                f"{q1_evidence['authoritative_steps']} authoritative, "
                f"{q1_evidence['provisional_steps']} provisional, "
                f"{len(silent_losses)} silent losses"
            ),
        },
        "Q2_lineage_completeness": {
            "pass": q2_pass,
            "evidence": q2_evidence,
            "summary": (
                f"{sum(q2_evidence['step_mutation_counts'])} mutations across "
                f"{len(steps)} steps, {len(lineage_gaps)} lineage gaps"
            ),
        },
        "Q3_unresolved_blocks_promotion": {
            "pass": q3_pass,
            "evidence": q3_evidence,
            "summary": (
                "promotion blocked correctly"
                if q3_pass
                else f"failures: {q3_evidence.get('promotion_block_failures', [])}"
            ),
        },
        "Q4_ground_truth_match": {
            "pass": q4_pass,
            "evidence": q4_evidence,
            "summary": q4_summary if comparison is not None else q4_summary,
        },
    }
