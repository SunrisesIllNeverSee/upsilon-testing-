"""Synthetic end-to-end amendment-chain reconstruction harness.

This is the synthetic system smoke test for the Financial Commitment
Integrity tester. It drives the full pipeline:

    S0 original credit agreement
    ↓
    A1 amendment  →  reconstruct S1
    ↓
    A2 amendment  →  reconstruct S2
    ↓
    ...
    ↓
    compare reconstructed current state
    against oracle ground-truth state at a specified comparison time

The harness uses the REAL executor (`executor.execute_amendment`) and
the REAL persistence planner (`persistence.build_persistence_plan`).
It does not reimplement application or lineage logic. The smoke test
validates that the system plumbing — sequential application, lineage
edge construction, unresolved-instruction blocking, and ground-truth
comparison — works end-to-end.

Chain fixtures in `synthetic_chains.py` are SYNTHETIC ORACLE fixtures,
not independent ground truth. The ground-truth states are hand-
constructed in the same fixture module as the amendments. They model
real credit-agreement amendment-chain structure (sequential threshold
changes, commitment additions/deletions, waivers, and chains with
intentional UNRESOLVED instructions). Real multi-amendment chain
acquisition from EDGAR is the next phase (25-issuer chain study);
this synthetic smoke test validates the system plumbing before that
acquisition work.

Authority model (chain-aware):
    A step is authoritative iff:
      (a) its own execution status is COMPLETE, AND
      (b) no inherited unresolved uncertainty from ancestor amendments
          remains after this step's applied instructions are checked
          against the inherited unresolved set.

    A later clean amendment does NOT automatically erase uncertainty
    inherited from an earlier PARTIAL/UNRESOLVED amendment. The
    inherited unresolved must be explicitly addressed by a later
    amendment's applied instructions targeting the same commitment
    before the chain can promote to authoritative.

Waiver restoration model (chain-wide pending queue):
    Temporary waivers produce a restore_state in the persistence plan.
    The reconstruction maintains a chain-wide queue of pending restore
    events. At each amendment transition, restores whose valid_from
    <= the next amendment's effective_at are applied to the carried-
    forward state. This correctly handles waivers that expire between
    two unrelated intervening amendments — the restore is not lost just
    because the immediately preceding amendment didn't touch the waived
    commitment.

Comparison time:
    The ground-truth comparison uses an explicit `comparison_at`
    timestamp on the IssuerChain (typically the composite/A&R filing
    date). The final state is reconstructed at that timestamp, with all
    pending restores due by that time applied. This replaces the
    earlier `datetime.max` approach, which incorrectly forced every
    waiver to be considered expired regardless of the actual comparison
    time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    DomainEffect,
    ExecutionResult,
    ExecutionStatus,
    InstructionType,
)
from upsilon.execution.executor import execute_amendment
from upsilon.commitments.persistence import build_persistence_plan


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AmendmentStep:
    """One amendment in a chain: instructions + effective time + pattern.

    Fields:
        amendment_number: 1-based amendment index
        effective_at: effective date of the amendment
        instructions: commitment-level instructions to apply
        description: human-readable description
        pattern: amendment structural pattern (incremental,
            full_restatement, conformed_copy, unknown).  Determines
            whether the parser can extract instructions automatically
            or whether a fallback strategy is needed.  None for
            synthetic chains (no real filing pattern).
        parser_instruction_count: number of instructions the parser
            (parse_v04) extracted from the source document.  0 for
            unsupported patterns (full restatement, conformed copy).
            None if the parser was not run.
        source_document_path: path to the source text file (for real
            EDGAR chains).  None for synthetic chains.
    """

    amendment_number: int
    effective_at: datetime
    instructions: list[AmendmentInstruction]
    description: str = ""
    pattern: str | None = None
    parser_instruction_count: int | None = None
    source_document_path: str | None = None


@dataclass
class IssuerChain:
    """A complete issuer amendment chain with oracle ground truth.

    Fields:
        chain_id: short identifier (e.g., "CHAIN-ACME")
        issuer_name: human-readable issuer name
        original_state: S0 — the original credit-agreement commitment kernel
        amendments: ordered list of AmendmentStep (A1, A2, ...)
        ground_truth_state: the oracle authoritative state, used as the
            comparison target for Q4. May be None if no composite/A&R
            was filed for this chain. NOTE: in the synthetic phase this
            is a hand-constructed oracle, not an independent document.
        ground_truth_label: human-readable label for the ground-truth source
        comparison_at: the timestamp at which the reconstructed state
            should be compared to ground truth (typically the composite/
            A&R filing date). Pending waiver restores due by this time
            are applied before comparison. Required.
        is_synthetic: True for synthetic oracle chains, False for real
            EDGAR chains.  Used by the report renderer to distinguish
            synthetic validation from real-data validation.
    """

    chain_id: str
    issuer_name: str
    original_state: dict[str, CommitmentState]
    amendments: list[AmendmentStep]
    comparison_at: datetime
    ground_truth_state: dict[str, CommitmentState] | None = None
    ground_truth_label: str | None = None
    is_synthetic: bool = True


@dataclass
class StepResult:
    """Result of reconstructing one amendment step."""

    amendment_number: int
    effective_at: datetime
    execution_result: ExecutionResult
    persistence_plan: dict[str, Any]
    reconstructed_state: dict[str, CommitmentState]
    # True only if this step's state may be promoted to authoritative.
    # Chain-aware: requires both (a) this step's status COMPLETE and
    # (b) no inherited unresolved uncertainty from ancestor amendments.
    is_authoritative: bool
    # Unresolved instructions inherited from ancestor amendments that
    # were NOT resolved by this step's applied instructions. Empty for
    # authoritative steps.
    inherited_unresolved: list[AmendmentInstruction] = field(default_factory=list)
    # This step's own unresolved instructions (subset of inherited_unresolved
    # for the NEXT step).
    own_unresolved: list[AmendmentInstruction] = field(default_factory=list)
    # Amendment pattern (incremental, full_restatement, conformed_copy,
    # unknown).  None for synthetic chains.
    pattern: str | None = None
    # Number of instructions the parser extracted from the source doc.
    # 0 for unsupported patterns.  None if parser was not run.
    parser_instruction_count: int | None = None
    # Provenance breakdown of the instructions in this step.
    # Counts by InstructionProvenance value.
    provenance_counts: dict[str, int] = field(default_factory=dict)


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
    lineage_graph: LineageGraph


# ---------------------------------------------------------------------------
# Lineage graph (for Q2 — real origin-to-current lineage verification)
# ---------------------------------------------------------------------------


@dataclass
class VersionNode:
    """One version of one commitment in the lineage graph."""

    version_id: str  # e.g., "S0:financial_covenant.total_leverage_ratio"
    target: str
    amendment_number: int  # 0 for origin (S0)
    kind: str  # "origin", "state", or "restore"
    state: CommitmentState
    parent_id: str | None
    authority_amendment_number: int  # amendment that authorized this version
    edge_type: str  # "ORIGIN", "MODIFIES", "WAIVES", "REINSTATES", "SUPERSEDES"


@dataclass
class LineageGraph:
    """The full parent/child version graph across all steps."""

    nodes: dict[str, VersionNode] = field(default_factory=dict)

    def add(self, node: VersionNode) -> None:
        if node.version_id in self.nodes:
            raise ValueError(f"Duplicate version_id: {node.version_id}")
        self.nodes[node.version_id] = node

    def children_of(self, version_id: str) -> list[str]:
        return sorted(
            n.version_id for n in self.nodes.values()
            if n.parent_id == version_id
        )

    def current_version_for(self, target: str) -> VersionNode | None:
        """The latest version of `target` (highest amendment_number, restore
        preferred over state within the same amendment)."""
        candidates = [
            n for n in self.nodes.values()
            if n.target == target
        ]
        if not candidates:
            return None
        # Sort by (amendment_number, kind priority) — restore > state > origin.
        kind_order = {"origin": 0, "state": 1, "restore": 2}
        candidates.sort(
            key=lambda n: (n.amendment_number, kind_order.get(n.kind, 0))
        )
        return candidates[-1]

    def origin_version_for(self, target: str) -> VersionNode | None:
        candidates = [
            n for n in self.nodes.values()
            if n.target == target and n.kind == "origin"
        ]
        return candidates[0] if candidates else None

    def reach_origin(self, version_id: str) -> list[str] | None:
        """Follow parent_id chain from version_id back to origin. Returns
        None if the chain is broken (parent missing) or doesn't reach an
        origin node."""
        path: list[str] = [version_id]
        current = version_id
        seen = {version_id}
        while True:
            node = self.nodes.get(current)
            if node is None:
                return None
            if node.parent_id is None:
                # Origin or a root — must be an origin node.
                if node.kind == "origin":
                    return path
                return None
            if node.parent_id in seen:
                return None  # cycle
            path.append(node.parent_id)
            seen.add(node.parent_id)
            current = node.parent_id

    def orphans(self) -> list[str]:
        """Versions whose parent_id references a non-existent node."""
        return sorted(
            n.version_id for n in self.nodes.values()
            if n.parent_id is not None and n.parent_id not in self.nodes
        )


# ---------------------------------------------------------------------------
# Resolution policy for inherited unresolved instructions
# ---------------------------------------------------------------------------

# Constructive instruction types — ones that produce a state mutation on
# the target commitment. Reference-only types (RENUMBER_REFERENCE) do not
# resolve inherited uncertainty about the commitment's semantic content.
_CONSTRUCTIVE_TYPES = frozenset({
    InstructionType.REPLACE_VALUE,
    InstructionType.REPLACE_TEXT,
    InstructionType.ADD,
    InstructionType.ADD_COMMITMENT,
    InstructionType.DELETE,
    InstructionType.DELETE_COMMITMENT,
    InstructionType.WAIVE_TEMPORARILY,
    InstructionType.SUSPEND,
    InstructionType.REINSTATE,
    InstructionType.RESTATE_SECTION,
})


def _effective_field(ins: AmendmentInstruction) -> str | None:
    """The effective field an instruction targets, deriving from
    domain_effect when field is not explicitly set. Mirrors the
    executor's field-derivation logic."""
    if ins.field:
        return ins.field
    if ins.domain_effect:
        de = ins.domain_effect
        if de == DomainEffect.DEADLINE_CHANGE:
            return "deadline"
        if de == DomainEffect.FREQUENCY_CHANGE:
            return "frequency"
        if de == DomainEffect.PARTY_CHANGE:
            return "party"
        if de == DomainEffect.SCOPE_CHANGE:
            return "scope"
        if de == DomainEffect.COVENANT_THRESHOLD_CHANGE:
            return "threshold"
    return None


def _resolution_key(
    ins: AmendmentInstruction,
) -> tuple[str, str | None, InstructionType]:
    """The resolution key for an instruction.

    Tuple: (target_key, effective_field, instruction_type).

    Two instructions with the same resolution key address the same
    commitment + field/path + operation. An inherited unresolved
    instruction is resolved by a later applied instruction with the
    same resolution key.

    This is field/claim-specific: a REPLACE_VALUE on
    interest_coverage.threshold does NOT resolve an unresolved
    REPLACE_VALUE on interest_coverage.frequency, even though they
    target the same commitment. The field/path must match.

    RESTATE_SECTION instructions have field=None (they cover a whole
    section). A RESTATE_SECTION is only resolved by another
    successfully-decomposed RESTATE_SECTION on the same target — not
    by a single field change. Since the executor currently always
    raises for RESTATE_SECTION, RESTATE_SECTION uncertainty is
    permanent until the executor can decompose restatements.
    """
    return (
        ins.target_key or "",
        _effective_field(ins),
        ins.instruction_type,
    )


def _is_resolved_by(
    unresolved: AmendmentInstruction,
    applied: list[AmendmentInstruction],
) -> bool:
    """Field/claim-specific resolution matcher for inherited unresolved.

    An inherited unresolved instruction is considered resolved by a
    later step if that step has at least one applied constructive
    instruction with the same resolution key (target_key +
    effective_field + instruction_type).

    This is field-specific: a REPLACE_VALUE on
    interest_coverage.threshold does NOT resolve an unresolved
    REPLACE_VALUE on interest_coverage.frequency, even though they
    target the same commitment. The field/path must match.
    """
    if not unresolved.target_key:
        return False
    urk = _resolution_key(unresolved)
    for a in applied:
        if a.instruction_type not in _CONSTRUCTIVE_TYPES:
            continue
        if _resolution_key(a) == urk:
            return True
    return False


# ---------------------------------------------------------------------------
# Waiver restore: chain-wide pending-restoration queue
# ---------------------------------------------------------------------------


@dataclass
class PendingRestore:
    """A scheduled waiver restore that hasn't been applied yet."""

    valid_from: datetime  # when the waiver expires → restore takes effect
    target: str
    restore_state: CommitmentState


def _apply_due_restores(
    state: dict[str, CommitmentState],
    pending: list[PendingRestore],
    at_time: datetime,
) -> tuple[dict[str, CommitmentState], list[PendingRestore]]:
    """Apply all pending restores whose valid_from <= at_time.

    Returns (updated_state, still_pending). Applied restores are removed
    from the pending list. This is chain-wide: it consults ALL pending
    restores from ALL prior steps, not just the immediately preceding
    persistence plan.
    """
    out = {k: v.model_copy(deep=True) for k, v in state.items()}
    still_pending: list[PendingRestore] = []
    for r in pending:
        if r.valid_from is not None and r.valid_from <= at_time:
            out[r.target] = r.restore_state.model_copy(deep=True)
        else:
            still_pending.append(r)
    return out, still_pending


# ---------------------------------------------------------------------------
# Reconstruction engine
# ---------------------------------------------------------------------------


def _build_lineage_graph(
    original_state: dict[str, CommitmentState],
    steps: list[StepResult],
) -> LineageGraph:
    """Build the full parent/child version graph across all steps.

    For each target, the version chain is:
        S0 origin version (no parent)
        → A1 state version (parent = S0 origin)
        → A2 state version (parent = A1 state, or A1 restore if waiver)
        → ...
    Waiver mutations produce an additional restore version whose parent
    is the waiver (state) version, with edge_type REINSTATES.
    """
    graph = LineageGraph()

    # Track the latest version_id for each target so we can set parents.
    latest_for_target: dict[str, str] = {}

    # Origin nodes (S0).
    for target, state in original_state.items():
        vid = f"S0:{target}"
        graph.add(VersionNode(
            version_id=vid,
            target=target,
            amendment_number=0,
            kind="origin",
            state=state.model_copy(deep=True),
            parent_id=None,
            authority_amendment_number=0,
            edge_type="ORIGIN",
        ))
        latest_for_target[target] = vid

    # Step versions.
    for step in steps:
        for m in step.persistence_plan["mutations"]:
            target = m["target"]
            parent_id = latest_for_target.get(target)

            # State version (the post-amendment version, possibly WAIVED).
            state_vid = f"A{step.amendment_number}:{target}:state"
            # Determine edge type from the instructions.
            edge_type = "MODIFIES"
            for ins in m["instructions"]:
                if ins.instruction_type == InstructionType.WAIVE_TEMPORARILY:
                    edge_type = "WAIVES"
                    break
                if ins.instruction_type in (
                    InstructionType.DELETE,
                    InstructionType.DELETE_COMMITMENT,
                ):
                    edge_type = "SUPERSEDES"
                    break
            # If this target has no prior version, this is the first version
            # of a commitment added by an amendment. Treat it as a root
            # (kind="origin", edge_type="ADDS") so it's a legitimate lineage
            # starting point — not an orphan.
            is_added = parent_id is None
            kind = "origin" if is_added else "state"
            root_edge = "ADDS" if is_added else edge_type
            graph.add(VersionNode(
                version_id=state_vid,
                target=target,
                amendment_number=step.amendment_number,
                kind=kind,
                state=m["state"].model_copy(deep=True),
                parent_id=parent_id,
                authority_amendment_number=step.amendment_number,
                edge_type=root_edge if is_added else edge_type,
            ))
            latest_for_target[target] = state_vid

            # Restore version (post-waiver reinstatement), if any.
            restore_state = m.get("restore_state")
            if restore_state is not None:
                restore_vid = f"A{step.amendment_number}:{target}:restore"
                graph.add(VersionNode(
                    version_id=restore_vid,
                    target=target,
                    amendment_number=step.amendment_number,
                    kind="restore",
                    state=restore_state.model_copy(deep=True),
                    parent_id=state_vid,  # restore's parent is the waiver version
                    authority_amendment_number=step.amendment_number,
                    edge_type="REINSTATES",
                ))
                latest_for_target[target] = restore_vid

    return graph


def reconstruct_chain(chain: IssuerChain) -> ChainReconstructionResult:
    """Run S0 → A1 → S1 → A2 → S2 → ... → Sn for one issuer chain.

    Each step uses the real executor and persistence planner. The
    reconstructed state after step N becomes the input to step N+1,
    with expired waivers restored to their post-amendment terms per
    the "kernel at time T" rule.

    Authority is chain-aware: a step is authoritative only if its own
    execution is COMPLETE AND no inherited unresolved uncertainty from
    ancestor amendments remains.
    """
    current_state = {k: v.model_copy(deep=True) for k, v in chain.original_state.items()}
    steps: list[StepResult] = []
    pending_restores: list[PendingRestore] = []
    inherited_unresolved: list[AmendmentInstruction] = []

    for i, step in enumerate(chain.amendments):
        # Apply pending restores from prior steps that are due by THIS
        # step's effective_at. This is the chain-wide queue — restores
        # from any prior amendment whose valid_from <= step.effective_at
        # are applied before this step's execution. This correctly
        # handles waivers that expire between two unrelated intervening
        # amendments.
        current_state, pending_restores = _apply_due_restores(
            current_state, pending_restores, step.effective_at
        )

        execution_result = execute_amendment(current_state, step.instructions)
        plan = build_persistence_plan(execution_result, step.effective_at)
        reconstructed = execution_result.state

        # --- Chain-aware authority ---
        # Resolve inherited unresolved against this step's applied.
        # An inherited unresolved is resolved if this step has an applied
        # constructive instruction targeting the same commitment.
        still_inherited = [
            u for u in inherited_unresolved
            if not _is_resolved_by(u, execution_result.applied)
        ]
        own_unresolved = list(execution_result.unresolved)
        # The inherited set for the NEXT step is: prior inherited not
        # resolved by this step + this step's own new unresolved.
        inherited_unresolved = still_inherited + own_unresolved

        is_authoritative = (
            execution_result.status == ExecutionStatus.COMPLETE
            and not inherited_unresolved
        )

        # Provenance counts for this step's instructions.
        prov_counts: dict[str, int] = {}
        for ins in step.instructions:
            prov = ins.provenance.value if hasattr(ins.provenance, "value") else str(ins.provenance)
            prov_counts[prov] = prov_counts.get(prov, 0) + 1

        steps.append(
            StepResult(
                amendment_number=step.amendment_number,
                effective_at=step.effective_at,
                execution_result=execution_result,
                persistence_plan=plan,
                reconstructed_state=reconstructed,
                is_authoritative=is_authoritative,
                inherited_unresolved=list(inherited_unresolved),
                own_unresolved=own_unresolved,
                pattern=step.pattern,
                parser_instruction_count=step.parser_instruction_count,
                provenance_counts=prov_counts,
            )
        )

        # Carry the state forward for the next amendment.
        # NOTE: even PARTIAL executions produce a (provisional) state,
        # but is_authoritative=False signals it must not be promoted.
        # For chaining purposes we still carry the state forward so the
        # next amendment can be applied — the unresolved instructions
        # are recorded and the provisional flag travels with the step.
        current_state = {k: v.model_copy(deep=True) for k, v in reconstructed.items()}

        # Add THIS step's new restore_states to the chain-wide pending
        # queue. They will be applied at a future transition when their
        # valid_from <= that transition's effective_at.
        for m in plan["mutations"]:
            restore_state = m.get("restore_state")
            if restore_state is not None and restore_state.valid_from is not None:
                pending_restores.append(PendingRestore(
                    valid_from=restore_state.valid_from,
                    target=m["target"],
                    restore_state=restore_state.model_copy(deep=True),
                ))

    # The final state for ground-truth comparison. Apply all pending
    # restores due by the chain's comparison_at (the ground-truth filing
    # date). This replaces the earlier datetime.max approach, which
    # incorrectly forced every waiver to be considered expired.
    final_state, _ = _apply_due_restores(
        current_state, pending_restores, chain.comparison_at
    )

    # Build the lineage graph for Q2.
    lineage_graph = _build_lineage_graph(chain.original_state, steps)

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
        lineage_graph=lineage_graph,
        original_state=chain.original_state,
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
        lineage_graph=lineage_graph,
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
    lineage_graph: LineageGraph,
    original_state: dict[str, CommitmentState],
) -> dict[str, dict[str, Any]]:
    """Answer the four system smoke-test questions mechanically.

    Each answer is a dict with:
        pass: bool — did this question pass for this chain?
        evidence: dict — the mechanical evidence supporting the answer
        summary: str — human-readable one-line summary
    """
    # --- Q1: Can Upsilon preserve authoritative state across amendments? ---
    # Pass: every step's status is COMPLETE or PARTIAL (no UNRESOLVED-only),
    # and no commitment is silently lost between steps.
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

    # --- Q2: Can it maintain complete lineage from origin to current? ---
    # Real lineage-graph verification: every non-origin version has a
    # parent, every version is reachable from an origin node, no orphans,
    # waiver→reinstatement edges are connected, and every version has a
    # valid_from anchor.
    q2_evidence: dict[str, Any] = {
        "step_mutation_counts": [len(s.persistence_plan["mutations"]) for s in steps],
        "step_unresolved_orders": [s.persistence_plan["unresolved_orders"] for s in steps],
        "total_versions": len(lineage_graph.nodes),
        "total_targets": len({n.target for n in lineage_graph.nodes.values()}),
    }
    lineage_gaps: list[str] = []

    # Check 1: every mutation has a valid_from (lineage anchor).
    for s in steps:
        if s.execution_result.applied and not s.persistence_plan["mutations"]:
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

    # Check 2: no orphan versions (parent_id references non-existent node).
    orphans = lineage_graph.orphans()
    for o in orphans:
        lineage_gaps.append(f"orphan version {o}: parent not in graph")

    # Check 3: every non-origin version is reachable from an origin node.
    unreachable: list[str] = []
    for vid, node in lineage_graph.nodes.items():
        if node.kind == "origin":
            continue
        path = lineage_graph.reach_origin(vid)
        if path is None:
            unreachable.append(vid)
    for u in unreachable:
        lineage_gaps.append(f"version {u} not reachable from origin")

    # Check 4: every target in the final state has a current version
    # reachable from its origin.
    current_unreachable: list[str] = []
    for target in sorted(final_state.keys()):
        current = lineage_graph.current_version_for(target)
        if current is None:
            current_unreachable.append(target)
            continue
        path = lineage_graph.reach_origin(current.version_id)
        if path is None:
            current_unreachable.append(target)
    for t in current_unreachable:
        lineage_gaps.append(f"current version for {t} not reachable from origin")

    # Check 5: waiver→reinstatement edge connectivity. Every restore node
    # must have its parent be a state node with edge_type WAIVES.
    broken_reinstatements: list[str] = []
    for vid, node in lineage_graph.nodes.items():
        if node.kind != "restore":
            continue
        parent = lineage_graph.nodes.get(node.parent_id) if node.parent_id else None
        if parent is None or parent.kind != "state" or parent.edge_type != "WAIVES":
            broken_reinstatements.append(
                f"{vid}: parent is not a WAIVES state node"
            )
    for b in broken_reinstatements:
        lineage_gaps.append(b)

    # Check 6: every version's authority_amendment_number matches the step
    # that created it (origin = 0).
    authority_mismatches: list[str] = []
    for vid, node in lineage_graph.nodes.items():
        expected = node.amendment_number
        if node.authority_amendment_number != expected:
            authority_mismatches.append(
                f"{vid}: authority_amendment_number={node.authority_amendment_number} "
                f"expected {expected}"
            )
    for a in authority_mismatches:
        lineage_gaps.append(a)

    q2_evidence["lineage_gaps"] = lineage_gaps
    q2_evidence["orphans"] = orphans
    q2_evidence["unreachable_versions"] = unreachable
    q2_evidence["broken_reinstatements"] = broken_reinstatements
    q2_evidence["authority_mismatches"] = authority_mismatches
    q2_pass = not lineage_gaps

    # --- Q3: Does any unresolved instruction block authoritative promotion? ---
    # Chain-aware: a step is authoritative iff (a) own status COMPLETE and
    # (b) no inherited unresolved. This checks BOTH:
    #   - steps with own unresolved → not authoritative
    #   - steps with inherited unresolved → not authoritative
    #   - steps with no unresolved (own or inherited) and COMPLETE → authoritative
    q3_evidence: dict[str, Any] = {
        "steps_with_own_unresolved": [
            {
                "amendment": s.amendment_number,
                "status": s.execution_result.status.value,
                "unresolved_count": len(s.execution_result.unresolved),
                "inherited_unresolved_count": len(s.inherited_unresolved),
                "is_authoritative": s.is_authoritative,
            }
            for s in steps if s.execution_result.unresolved
        ],
        "steps_with_inherited_unresolved": [
            {
                "amendment": s.amendment_number,
                "status": s.execution_result.status.value,
                "inherited_unresolved_count": len(s.inherited_unresolved),
                "is_authoritative": s.is_authoritative,
            }
            for s in steps if s.inherited_unresolved
        ],
    }
    promotion_blocked_correctly = True
    for s in steps:
        # Steps with own unresolved must not be authoritative.
        if s.execution_result.unresolved and s.is_authoritative:
            promotion_blocked_correctly = False
            q3_evidence.setdefault("promotion_block_failures", []).append(
                f"A{s.amendment_number}: has own unresolved but is_authoritative=True"
            )
        # Steps with inherited unresolved must not be authoritative,
        # even if their own execution is COMPLETE.
        if s.inherited_unresolved and s.is_authoritative:
            promotion_blocked_correctly = False
            q3_evidence.setdefault("promotion_block_failures", []).append(
                f"A{s.amendment_number}: has inherited unresolved but is_authoritative=True"
            )
        # Steps with own unresolved must have status PARTIAL or UNRESOLVED.
        if s.execution_result.unresolved and s.execution_result.status not in (
            ExecutionStatus.PARTIAL,
            ExecutionStatus.UNRESOLVED,
        ):
            promotion_blocked_correctly = False
            q3_evidence.setdefault("promotion_block_failures", []).append(
                f"A{s.amendment_number}: has own unresolved but status="
                f"{s.execution_result.status.value}"
            )
        # Steps with no unresolved (own or inherited) and COMPLETE must
        # be authoritative (positive case).
        if (
            not s.execution_result.unresolved
            and not s.inherited_unresolved
            and s.execution_result.status == ExecutionStatus.COMPLETE
            and not s.is_authoritative
        ):
            promotion_blocked_correctly = False
            q3_evidence.setdefault("promotion_block_failures", []).append(
                f"A{s.amendment_number}: no unresolved, COMPLETE, "
                f"but is_authoritative=False"
            )
    q3_evidence["promotion_blocked_correctly"] = promotion_blocked_correctly
    q3_pass = promotion_blocked_correctly

    # --- Q4: Does reconstructed state exactly match ground truth? ---
    if comparison is None:
        q4_evidence: dict[str, Any] = {"ground_truth_available": False}
        q4_pass = False
        q4_summary = "No oracle ground-truth state available for this chain"
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
                f"{q2_evidence['total_versions']} versions across "
                f"{q2_evidence['total_targets']} targets, "
                f"{len(lineage_gaps)} lineage gaps"
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
            "summary": q4_summary,
        },
    }
