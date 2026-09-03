"""Semantic Pipeline v2 (Step 21 / Section C+E).

Wires the v2 semantic resolver and genre adapters into the full
end-to-end pipeline:

    EDGAR filing text
        ↓
    genre classifier (pattern_classifier)
        ↓
    genre adapter (genre_adapters)
        ↓
    v2 semantic resolver (semantic_resolver_v2)
        ↓
    model-assisted candidate validation (model_assisted_candidates)
        ↓
    StructuredMutation candidates (mapped | UNRESOLVED)
        ↓
    to_amendment_instruction (only mapped mutations)
        ↓
    executor (FROZEN — same safety guards as v1)
        ↓
    reconstructed commitment state
        ↓
    compare to ground truth

The v2 pipeline does NOT modify the frozen executor, lineage,
persistence, or authority model.  It only changes how parser
instructions are mapped to StructuredMutations (the resolver) and
how different amendment genres are processed (the adapters).

UNRESOLVED mutations are NOT passed to the executor.  They are
recorded as unresolved and prevent authoritative promotion (per the
chain-aware authority model in chain_reconstruction.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from upsilon.parsing.amendment_parser import parse_v04
from upsilon.lineage.chain_reconstruction import AmendmentStep, IssuerChain
from upsilon.execution.executor import ExecutionResult, execute_amendment
from upsilon.parsing.genre_adapters import GenreAdapterResult, process_amendment_by_genre
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    ExecutionStatus,
    InstructionProvenance,
    InstructionType,
)
from upsilon.parsing.pattern_classifier import AmendmentPattern, classify_amendment
from upsilon.transformations.semantic_mapper import AmbiguityReason, StructuredMutation
from upsilon.transformations.semantic_resolver_v2 import resolve_instruction
from upsilon.pipeline.conservation_first_spine import ConservationFirstSpine, SpineResult


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SemanticStepResultV2:
    """Result of one amendment step through the v2 semantic pipeline."""

    amendment_number: int
    effective_at: datetime
    pattern: str | None
    genre: str
    parser_instruction_count: int
    extraction_count: int
    mapped_count: int
    unresolved_count: int
    execution_result: ExecutionResult
    is_authoritative: bool
    inherited_unresolved_count: int
    adapter_notes: str
    # Mapped candidates broken down by source path:
    #   mapped_from_parser: candidates produced by the INCREMENTAL
    #     adapter (parse_v04 → resolver v2).  These are counted against
    #     parser_instruction_count for coverage.
    #   mapped_from_extraction: candidates produced by the
    #     FULL_RESTATEMENT / CONFORMED_COPY adapters (direct
    #     commitment extraction → diff).  These are NOT counted
    #     against parser_instruction_count — they have no parser
    #     instruction denominator.
    mapped_from_parser: int = 0
    mapped_from_extraction: int = 0
    # Step 24B conservation-first spine tracking.
    #   spine_promoted: number of curated instructions promoted to
    #     authoritative state through the conservation-first spine
    #     (Layer A–G).  These bypass the legacy resolver/executor.
    #   spine_rejected: number of curated instructions the spine
    #     rejected (fail-closed).  These are recorded as unresolved.
    #   spine_routed_away: number of curated instructions whose
    #     transformation family is not yet activated in the spine;
    #     they were routed to the legacy path.
    spine_promoted: int = 0
    spine_rejected: int = 0
    spine_routed_away: int = 0
    spine_results: list[SpineResult] = field(default_factory=list)


@dataclass
class SemanticPipelineResultV2:
    """Full result of running the v2 semantic pipeline on one chain."""

    chain_id: str
    issuer_name: str
    steps: list[SemanticStepResultV2]
    reconstructed_state: dict[str, CommitmentState]
    ground_truth_state: dict[str, CommitmentState]
    # Metrics
    total_parser_instructions: int
    total_mapped: int
    total_unresolved: int
    mapping_accuracy: float
    unresolved_rate: float
    incorrect_mutation_rate: float
    final_state_agreement: float
    # Breakdown of total_mapped by source path (see SemanticStepResultV2).
    # total_mapped = mapped_from_parser + mapped_from_extraction.
    # Semantic mapping coverage = mapped_from_parser / total_parser_instructions.
    mapped_from_parser: int = 0
    mapped_from_extraction: int = 0
    # Genre metrics
    genre_distribution: dict[str, int] = field(default_factory=dict)
    # Details
    incorrect_mutations: list[str] = field(default_factory=list)
    state_mismatches: list[str] = field(default_factory=list)
    # For temporal false-authoritative-promotion detection:
    # list of ((commitment_key, field), step_index) for each incorrect
    # mutation, where step_index is the 0-based index of the step at
    # which the incorrect mutation was applied.  A step marked
    # authoritative at index N is a false promotion only if an
    # incorrect mutation was applied at step <= N.
    incorrect_pair_steps: list[tuple[tuple[str, str | None], int]] = field(default_factory=list)
    # Step 24B conservation-first spine aggregate tracking.
    spine_total_promoted: int = 0
    spine_total_rejected: int = 0
    spine_total_routed_away: int = 0
    # The conservation-first spine instance, retained so callers
    # (Phase 9 integration verification) can inspect the final
    # authoritative kernel state, lineage graph, and proofs.
    spine: ConservationFirstSpine | None = None


# ---------------------------------------------------------------------------
# Step 23S: Semantic authority gate
# ---------------------------------------------------------------------------


class AuthorityDecision(str, Enum):
    """Authority promotion decision for one amendment step.

    Per ``SEMANTIC_AUTHORITY_GATE.md`` §3, the authority gate extends
    the existing chain-aware authority model with semantic proof and
    conservation preconditions.  The existing model
    (``chain_reconstruction.py``) determines authority from execution
    completeness and unresolved state; the semantic gate adds the
    proof-record and conservation-check requirements.
    """

    AUTHORITY_GRANTED = "AUTHORITY_GRANTED"
    AUTHORITY_BLOCKED = "AUTHORITY_BLOCKED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"


def assess_authority(
    execution_status: ExecutionStatus,
    proofs: list,
    inherited_unresolved_count: int,
    own_unresolved_count: int,
) -> AuthorityDecision:
    """Determine whether an amendment step may be promoted to authoritative.

    This implements the authority gate contract from
    ``SEMANTIC_AUTHORITY_GATE.md`` §5.  It consumes:

    - the execution result status (COMPLETE / PARTIAL / UNRESOLVED);
    - the semantic proof records attached to each candidate mutation;
    - the inherited unresolved count from prior steps;
    - the own unresolved count from this step.

    The decision logic is:

    ```
    IF execution == UNRESOLVED: → UNRESOLVED
    IF execution == PARTIAL:   → PARTIAL
    IF execution == COMPLETE:
        IF any proof is INCOMPLETE:        → AUTHORITY_BLOCKED
        IF any proof is INVALID:           → AUTHORITY_BLOCKED
        IF any proof is INDETERMINATE:     → VALIDATION_REQUIRED
        IF any proof has INSUFFICIENT
           target evidence:                → AUTHORITY_BLOCKED
        IF any proof has WEAK
           target evidence:                → VALIDATION_REQUIRED
        IF inherited_unresolved > 0:       → AUTHORITY_BLOCKED
        IF own_unresolved > 0:             → AUTHORITY_BLOCKED
        ELSE:                              → AUTHORITY_GRANTED
    ```

    Ground-truth labels never participate in this decision (Constraint #4).
    Only operational evidence (proof records, execution results, unresolved
    state) is consumed.

    When no proofs are present (e.g., a no-op step with no candidates),
    the gate falls back to the existing chain-aware authority model:
    authority is granted iff execution is COMPLETE and no unresolved
    state exists.  This preserves the existing contract for steps that
    do not produce mutations.
    """
    # Execution status gates (existing behavior).
    if execution_status == ExecutionStatus.UNRESOLVED:
        return AuthorityDecision.UNRESOLVED
    if execution_status == ExecutionStatus.PARTIAL:
        return AuthorityDecision.PARTIAL

    # COMPLETE execution — apply semantic proof preconditions.
    # When proofs are present, each must be COMPLETE and VALID.
    # An INCOMPLETE or INVALID proof blocks authority.  An
    # INDETERMINATE proof routes to VALIDATION_REQUIRED.
    #
    # When no proofs are present (no-op step), fall back to the
    # existing chain-aware authority model.
    if proofs:
        for proof in proofs:
            # proof is a moses_safety.SemanticProof (typed as Any to
            # avoid a hard import cycle; the fields are accessed by
            # attribute name).
            completeness = getattr(proof, "proof_completeness", None)
            validity = getattr(proof, "proof_validity", None)
            evidence_level = getattr(proof, "target_evidence_level", None)

            # Completeness is structural.  An INCOMPLETE proof means
            # the proof record could not be fully populated — there
            # is not enough structure to justify authority.
            if completeness is not None and completeness.value == "INCOMPLETE":
                return AuthorityDecision.AUTHORITY_BLOCKED

            # Validity is semantic.  An INVALID proof means the
            # evidence contradicts the transformation.
            if validity is not None and validity.value == "INVALID":
                return AuthorityDecision.AUTHORITY_BLOCKED

            # INSUFFICIENT target evidence blocks authority — the
            # engine could not establish what the amendment targets.
            if evidence_level is not None and evidence_level.value == "INSUFFICIENT":
                return AuthorityDecision.AUTHORITY_BLOCKED

            # WEAK target evidence routes to VALIDATION_REQUIRED —
            # the step is not auto-promoted but is not definitively
            # blocked either.
            if evidence_level is not None and evidence_level.value == "WEAK":
                return AuthorityDecision.VALIDATION_REQUIRED

            # INDETERMINATE validity routes to VALIDATION_REQUIRED.
            if validity is not None and validity.value == "INDETERMINATE":
                return AuthorityDecision.VALIDATION_REQUIRED

    # Chain-aware authority: inherited or own unresolved state blocks.
    if inherited_unresolved_count > 0:
        return AuthorityDecision.AUTHORITY_BLOCKED
    if own_unresolved_count > 0:
        return AuthorityDecision.AUTHORITY_BLOCKED

    return AuthorityDecision.AUTHORITY_GRANTED


# ---------------------------------------------------------------------------
# v2 semantic pipeline
# ---------------------------------------------------------------------------


def run_semantic_pipeline_v2(
    chain: IssuerChain,
) -> SemanticPipelineResultV2:
    """Run the v2 semantic pipeline on one EDGAR chain.

    For each amendment:
      1. Load the source text.
      2. Classify the amendment genre.
      3. Process through the genre-appropriate adapter:
         - INCREMENTAL: parse_v04 → resolver v2
         - FULL_RESTATEMENT: extract commitments → diff
         - CONFORMED_COPY: strip redline → extract → diff
         - UNKNOWN: try incremental, fall back to extraction
      4. Convert mapped mutations to AmendmentInstructions.
      5. Execute through the FROZEN executor.
      6. Track unresolved mutations (prevent authoritative promotion).

    The final reconstructed state is compared to the chain's
    ground_truth_state.
    """
    current_state = {
        k: v.model_copy(deep=True) for k, v in chain.original_state.items()
    }
    steps: list[SemanticStepResultV2] = []
    inherited_unresolved: list[StructuredMutation] = []

    total_parser = 0
    total_mapped = 0
    total_mapped_from_parser = 0
    total_mapped_from_extraction = 0
    total_unresolved = 0
    incorrect_mutations: list[str] = []
    genre_dist: dict[str, int] = {}

    # --- Step 24B: conservation-first spine initialization ---
    # Build section_refs from the curated instructions so the
    # agreement-local address map can resolve target identity for
    # SCALAR_REPLACEMENT amendments.  Commitments without a section
    # ref in the curated instructions are not registered in the
    # address map; the spine will fail-closed for them (correct
    # behavior — identity cannot be established without an address).
    section_refs: dict[str, str] = {}
    for _step in chain.amendments:
        for _ins in _step.instructions:
            if _ins.target_key and _ins.target_section_ref:
                section_refs.setdefault(_ins.target_key, _ins.target_section_ref)
    spine = ConservationFirstSpine(
        original_state=chain.original_state,
        agreement_identity=chain.chain_id,
        section_refs=section_refs,
    )
    spine_total_promoted = 0
    spine_total_rejected = 0
    spine_total_routed_away = 0
    # Spine-specific inherited unresolved: counts spine rejections
    # from prior steps.  This is separate from the legacy parser's
    # unresolved count because the spine's authority assessment is
    # about the specific commitments it controls, not the overall
    # amendment's unresolved non-covenant instructions.
    spine_inherited_unresolved = 0

    for step in chain.amendments:
        # 1. Load source text
        source_path = step.source_document_path
        if source_path and Path(source_path).exists():
            text = Path(source_path).read_text(encoding="utf-8", errors="ignore")
        else:
            text = ""

        # 2-3. Process through genre adapter
        genre_override = AmendmentPattern(step.pattern) if step.pattern else None
        adapter_result = process_amendment_by_genre(
            text, current_state, citation_document=step.description,
            genre_override=genre_override,
        )

        genre_str = adapter_result.genre.value
        genre_dist[genre_str] = genre_dist.get(genre_str, 0) + 1
        total_parser += adapter_result.parser_instruction_count

        # Separate mapped and unresolved
        mapped_mutations: list[StructuredMutation] = []
        unresolved_mutations: list[StructuredMutation] = []
        for candidate in adapter_result.candidates:
            if candidate.is_resolved:
                mapped_mutations.append(candidate)
            else:
                unresolved_mutations.append(candidate)

        # Classify mapped candidates by source path.  The INCREMENTAL
        # adapter produces candidates from parser instructions; the
        # FULL_RESTATEMENT and CONFORMED_COPY adapters produce
        # candidates from direct commitment extraction (no parser
        # instruction denominator).  The UNKNOWN adapter tries
        # incremental first and falls back to extraction, so its
        # source depends on whether the parser found instructions.
        is_extraction_genre = genre_str in (
            "full_restatement", "conformed_copy",
        )
        if is_extraction_genre:
            step_mapped_from_parser = 0
            step_mapped_from_extraction = len(mapped_mutations)
        elif genre_str == "unknown":
            # UNKNOWN: if the parser found instructions, the candidates
            # came from the incremental path; otherwise from extraction.
            if adapter_result.parser_instruction_count > 0:
                step_mapped_from_parser = len(mapped_mutations)
                step_mapped_from_extraction = 0
            else:
                step_mapped_from_parser = 0
                step_mapped_from_extraction = len(mapped_mutations)
        else:
            # INCREMENTAL (and any other parser-based genre)
            step_mapped_from_parser = len(mapped_mutations)
            step_mapped_from_extraction = 0

        total_mapped += len(mapped_mutations)
        total_mapped_from_parser += step_mapped_from_parser
        total_mapped_from_extraction += step_mapped_from_extraction
        total_unresolved += len(unresolved_mutations)

        # --- Step 24B: route curated SCALAR_REPLACEMENT instructions
        # through the conservation-first spine (Layers A–G). ---
        # The spine is the controlling semantic path for
        # SCALAR_REPLACEMENT.  Curated instructions whose
        # transformation family is activated in the spine are
        # processed through the full conservation-first architecture
        # (evidence → engine → candidate → conservation → proof →
        # execution → lineage → authority gate).  Instructions whose
        # family is not yet activated are routed away to the legacy
        # path below.
        #
        # The spine advances its own authoritative kernel state
        # independently.  After the spine processes its instructions,
        # we synchronize the pipeline's current_state with the
        # spine's authoritative state for spine-controlled
        # commitments so the legacy executor sees the updated state.
        spine_results: list[SpineResult] = []
        spine_promoted = 0
        spine_rejected = 0
        spine_routed_away = 0
        # Use the spine-specific inherited unresolved count, not the
        # legacy parser's unresolved count.  The spine's authority
        # assessment is about the specific commitments it controls.
        for ins in step.instructions:
            if not spine.is_activated(ins):
                spine_routed_away += 1
                continue
            spine_result = spine.process_instruction(
                ins,
                citation_document=step.description,
                inherited_unresolved=spine_inherited_unresolved,
            )
            spine_results.append(spine_result)
            if spine_result.promoted:
                spine_promoted += 1
            elif spine_result.routed_away:
                spine_routed_away += 1
            else:
                spine_rejected += 1
        # Synchronize current_state with the spine's authoritative
        # state for commitments the spine controls.  This ensures the
        # legacy executor and ground-truth comparison see the
        # conservation-first authoritative state.
        if spine_promoted > 0:
            spine_state = spine.authoritative_state()
            for cid, state in spine_state.items():
                current_state[cid] = state.model_copy(deep=True)

        # 4. Convert mapped mutations to AmendmentInstructions
        mapped_instructions: list[AmendmentInstruction] = []
        for i, mut in enumerate(mapped_mutations, 1):
            mapped_instructions.append(mut.to_amendment_instruction(order=i))

        # 5. Execute through the FROZEN executor
        execution_result = execute_amendment(current_state, mapped_instructions)

        # Executor rejections (execution_result.unresolved) are SAFE
        # outcomes — the executor's guards caught a mismatched
        # mutation.  These are NOT incorrect mutations; they are safe
        # rejections.  Truly incorrect mutations (executor APPLIED a
        # mutation that disagrees with ground truth) are detected
        # after the full chain runs by comparing the final state to
        # ground truth (see below).

        # 6. Chain-aware authority + semantic authority gate (Step 23S)
        # The authority gate extends the existing chain-aware model
        # (execution complete + no unresolved) with semantic proof
        # and conservation preconditions.  See SEMANTIC_AUTHORITY_GATE.md
        # §5 for the full decision logic.
        #
        # Step 24B: spine rejections also count as own unresolved for
        # the legacy authority assessment.  A spine rejection means
        # the conservation-first spine fail-closed on a curated
        # SCALAR_REPLACEMENT instruction; the step must not be
        # promoted to authoritative for that commitment.
        still_inherited = inherited_unresolved
        own_unresolved_count = (
            len(unresolved_mutations) + len(execution_result.unresolved)
            + spine_rejected
        )
        # Collect semantic proofs from all candidates (mapped + unresolved).
        # Mapped mutations carry VALID proofs (the resolver only maps
        # candidates with COMPLETE+VALID proofs).  Unresolved mutations
        # may carry INVALID/INDETERMINATE proofs (the resolver routed
        # them to unresolved because the proof failed).  Both are
        # consumed by the authority gate: an INVALID proof on an
        # unresolved candidate blocks authority just as it would on a
        # mapped one.
        step_proofs = [
            c.semantic_proof for c in adapter_result.candidates
            if c.semantic_proof is not None
        ]
        authority_decision = assess_authority(
            execution_status=execution_result.status,
            proofs=step_proofs,
            inherited_unresolved_count=len(still_inherited),
            own_unresolved_count=own_unresolved_count,
        )
        # The step is authoritative only when the authority gate
        # grants authority.  VALIDATION_REQUIRED and AUTHORITY_BLOCKED
        # both prevent promotion.
        is_authoritative = (
            authority_decision == AuthorityDecision.AUTHORITY_GRANTED
        )

        # Update inherited for next step
        inherited_unresolved = still_inherited + unresolved_mutations + [
            StructuredMutation(
                operation=InstructionType.UNRESOLVED,
                ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            )
            for _ in execution_result.unresolved
        ]

        steps.append(SemanticStepResultV2(
            amendment_number=step.amendment_number,
            effective_at=step.effective_at,
            pattern=step.pattern,
            genre=genre_str,
            parser_instruction_count=adapter_result.parser_instruction_count,
            extraction_count=adapter_result.extraction_count,
            mapped_count=len(mapped_mutations),
            mapped_from_parser=step_mapped_from_parser,
            mapped_from_extraction=step_mapped_from_extraction,
            unresolved_count=len(unresolved_mutations),
            execution_result=execution_result,
            is_authoritative=is_authoritative,
            inherited_unresolved_count=len(still_inherited),
            adapter_notes=adapter_result.notes,
            spine_promoted=spine_promoted,
            spine_rejected=spine_rejected,
            spine_routed_away=spine_routed_away,
            spine_results=spine_results,
        ))

        # Carry state forward.
        # Start from the legacy executor's state, then overlay the
        # spine's authoritative state for spine-controlled
        # commitments.  This ensures the spine's conservation-first
        # authoritative state persists across steps for the
        # commitments it controls, while the legacy executor's state
        # persists for everything else.
        current_state = {
            k: v.model_copy(deep=True)
            for k, v in execution_result.state.items()
        }
        if spine_promoted > 0 or spine_total_promoted > 0:
            spine_state = spine.authoritative_state()
            for cid, state in spine_state.items():
                current_state[cid] = state.model_copy(deep=True)

        # Aggregate spine tracking across all steps.
        spine_total_promoted += spine_promoted
        spine_total_rejected += spine_rejected
        spine_total_routed_away += spine_routed_away
        # Spine rejections become inherited unresolved for the next
        # step's spine authority assessment.
        spine_inherited_unresolved += spine_rejected

    # Compare final state to ground truth
    ground_truth = chain.ground_truth_state or {}
    has_ground_truth = len(ground_truth) > 0
    state_mismatches: list[str] = []
    # Structured mismatch map: (commitment_key, field) -> mismatch
    # description.  Used for precise incorrect-mutation detection
    # without fragile string parsing.  field is None for whole-
    # commitment mismatches (Missing / Extra).
    mismatch_map: dict[tuple[str, str | None], str] = {}
    matched = 0
    total_gt = len(ground_truth)

    _COMPARE_FIELDS = (
        "threshold", "rate", "deadline", "party", "exceptions",
        "applicability", "status", "unit",
    )

    # Only compute mismatches and incorrect mutations when ground
    # truth is available.  When ground_truth is None or empty, every
    # reconstructed commitment would appear as "Extra" — a false
    # positive that inflates the incorrect mutation count.  Chains
    # without ground truth cannot have measurable incorrect mutations.
    if has_ground_truth:
        for key, gt_commitment in ground_truth.items():
            if key not in current_state:
                desc = f"Missing: {key}"
                state_mismatches.append(desc)
                mismatch_map[(key, None)] = desc
                continue
            recon = current_state[key]
            field_diffs: list[str] = []
            for fname in _COMPARE_FIELDS:
                recon_val = getattr(recon, fname, None)
                gt_val = getattr(gt_commitment, fname, None)
                if recon_val != gt_val:
                    field_diffs.append(f"{fname}: {recon_val!r} vs {gt_val!r}")
            if not field_diffs:
                matched += 1
            else:
                desc = f"Mismatch {key}: " + ", ".join(field_diffs)
                state_mismatches.append(desc)
                for fname in _COMPARE_FIELDS:
                    recon_val = getattr(recon, fname, None)
                    gt_val = getattr(gt_commitment, fname, None)
                    if recon_val != gt_val:
                        mismatch_map[(key, fname)] = desc

        for key in current_state:
            if key not in ground_truth:
                desc = f"Extra: {key}"
                state_mismatches.append(desc)
                mismatch_map[(key, None)] = desc

    # Compute metrics
    # Semantic mapping coverage uses parser-mapped candidates only,
    # because only those have a parser-instruction denominator.
    # Extraction-mapped candidates (from full_restatement /
    # conformed_copy adapters) have no parser instruction denominator
    # and are tracked separately.
    mapping_accuracy = (
        total_mapped_from_parser / total_parser if total_parser > 0 else 1.0
    )
    unresolved_rate = total_unresolved / total_parser if total_parser > 0 else 0.0

    # Incorrect mutations: state mismatches on (commitment, field)
    # pairs that were actually APPLIED by the executor.  Pre-existing
    # mismatches on unmodified fields are NOT incorrect mutations —
    # they indicate the original state was wrong, not that v2
    # produced a wrong mutation.
    #
    # We use the structured mismatch_map (keyed by exact
    # (commitment_key, field) tuples) instead of fragile string
    # parsing.  This catches:
    #   - field-level mismatches on applied REPLACE_VALUE mutations
    #   - Missing commitments (ADD that should have added a
    #     commitment but the executor rejected it or it was never
    #     produced — counted if an ADD was applied for that key)
    #   - Extra commitments (ADD that added a commitment not in
    #     ground truth — counted if an ADD was applied for that key)
    #
    # We also record the step index at which each (key, field) pair
    # was applied, so that callers can determine whether an
    # authoritative promotion at step N was false (i.e., an incorrect
    # mutation was applied at or before step N).
    applied_pairs: set[tuple[str, str | None]] = set()
    applied_keys: set[str] = set()
    # Map (commitment_key, field) → highest step index (0-based) at
    # which it was applied.  Used for temporal false-promotion
    # detection: a step marked authoritative at index N is a false
    # promotion only if an incorrect mutation was applied at index <= N.
    applied_pair_step: dict[tuple[str, str | None], int] = {}
    applied_key_step: dict[str, int] = {}
    for step_idx, step_result in enumerate(steps):
        for ins in step_result.execution_result.applied:
            if ins.target_key:
                applied_keys.add(ins.target_key)
                applied_key_step[ins.target_key] = step_idx
                pair: tuple[str, str | None] = (
                    (ins.target_key, ins.field) if ins.field
                    else (ins.target_key, None)
                )
                if pair not in applied_pair_step or step_idx > applied_pair_step[pair]:
                    applied_pair_step[pair] = step_idx
                if ins.field:
                    applied_pairs.add((ins.target_key, ins.field))
                # Also track whole-commitment operations (ADD_COMMITMENT,
                # DELETE_COMMITMENT, status changes) with field=None.
                if ins.instruction_type in (
                    InstructionType.ADD_COMMITMENT,
                    InstructionType.DELETE_COMMITMENT,
                    InstructionType.SUSPEND,
                    InstructionType.REINSTATE,
                    InstructionType.WAIVE_TEMPORARILY,
                ):
                    applied_pairs.add((ins.target_key, None))

    incorrect_mutations: list[str] = []
    seen_incorrect: set[str] = set()
    # For each incorrect (key, field) pair, record the step index at
    # which it was applied.  A false authoritative promotion at step N
    # occurs only if an incorrect mutation was applied at step <= N.
    incorrect_pair_steps: list[tuple[tuple[str, str | None], int]] = []
    for (mismatch_key, mismatch_field), desc in mismatch_map.items():
        is_incorrect = False
        applied_step: int | None = None
        if mismatch_field is not None:
            # Field-level mismatch: incorrect only if that
            # (key, field) pair was applied by the executor.
            pair = (mismatch_key, mismatch_field)
            if pair in applied_pairs:
                is_incorrect = True
                applied_step = applied_pair_step.get(pair)
        else:
            # Whole-commitment mismatch (Missing or Extra):
            # incorrect only if an operation was applied to that
            # commitment key (e.g., an ADD that should have added it
            # but didn't take, or an ADD that added an extra one).
            if mismatch_key in applied_keys:
                is_incorrect = True
                applied_step = applied_key_step.get(mismatch_key)
        if is_incorrect and desc not in seen_incorrect:
            incorrect_mutations.append(desc)
            seen_incorrect.add(desc)
            if applied_step is not None:
                incorrect_pair_steps.append(
                    ((mismatch_key, mismatch_field), applied_step)
                )

    incorrect_mutation_rate = (
        len(incorrect_mutations) / total_mapped if total_mapped > 0 else 0.0
    )
    final_state_agreement = matched / total_gt if total_gt > 0 else 1.0

    return SemanticPipelineResultV2(
        chain_id=chain.chain_id,
        issuer_name=chain.issuer_name,
        steps=steps,
        reconstructed_state=current_state,
        ground_truth_state=ground_truth,
        total_parser_instructions=total_parser,
        total_mapped=total_mapped,
        mapped_from_parser=total_mapped_from_parser,
        mapped_from_extraction=total_mapped_from_extraction,
        total_unresolved=total_unresolved,
        mapping_accuracy=round(mapping_accuracy, 4),
        unresolved_rate=round(unresolved_rate, 4),
        incorrect_mutation_rate=round(incorrect_mutation_rate, 4),
        final_state_agreement=round(final_state_agreement, 4),
        genre_distribution=genre_dist,
        incorrect_mutations=incorrect_mutations,
        state_mismatches=state_mismatches,
        incorrect_pair_steps=incorrect_pair_steps,
        spine_total_promoted=spine_total_promoted,
        spine_total_rejected=spine_total_rejected,
        spine_total_routed_away=spine_total_routed_away,
        spine=spine,
    )
