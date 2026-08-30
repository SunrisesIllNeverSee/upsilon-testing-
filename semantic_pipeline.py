"""End-to-end semantic pipeline: EDGAR → parser → mapper → executor → state.

This module wires the semantic mapper into the real EDGAR pipeline.
Instead of using the hand-crafted MANUAL_FALLBACK instructions in
edgar_chains.py, it:

  1. Runs the real parser (parse_v04) on the amendment source text.
  2. Runs the semantic mapper on the parser instructions.
  3. Converts mapped StructuredMutations to AmendmentInstructions.
  4. Executes them through the real executor.
  5. Compares the reconstructed state to the independently extracted
     ground truth.

This is the pipeline that proves "Upsilon has performed real end-to-end
reconstruction from filed amendment text into authoritative structured
state" — without manual semantic mutation entry for the mapped
instructions.

Pipeline flow:

    EDGAR filing text
        ↓
    parse_v04 (deterministic parser)
        ↓
    parser instructions (section-level)
        ↓
    semantic_mapper.map_instruction (deterministic rules)
        ↓
    StructuredMutation (mapped | UNRESOLVED)
        ↓
    to_amendment_instruction (only mapped mutations)
        ↓
    executor.execute_amendment
        ↓
    reconstructed commitment state
        ↓
    compare to ground truth

UNRESOLVED mutations are NOT passed to the executor.  They are recorded
as unresolved and prevent authoritative promotion (per the chain-aware
authority model in chain_reconstruction.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from amendment_parser import parse_v04
from chain_reconstruction import IssuerChain
from executor import execute_amendment, ExecutionResult
from models import (
    AmendmentInstruction,
    CommitmentState,
    ExecutionStatus,
    InstructionProvenance,
    InstructionType,
)
from semantic_mapper import (
    AmbiguityReason,
    MappingResult,
    StructuredMutation,
    map_instruction,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SemanticStepResult:
    """Result of one amendment step through the semantic pipeline."""
    amendment_number: int
    effective_at: datetime
    pattern: str | None
    parser_instruction_count: int
    mapper_mutations: list[StructuredMutation]
    mapper_unresolved: list[StructuredMutation]
    execution_result: ExecutionResult
    is_authoritative: bool
    # Inherited unresolved from prior steps
    inherited_unresolved_count: int


@dataclass
class SemanticPipelineResult:
    """Full result of running the semantic pipeline on one chain."""
    chain_id: str
    issuer_name: str
    steps: list[SemanticStepResult]
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
    # Details
    incorrect_mutations: list[str]
    state_mismatches: list[str]


# ---------------------------------------------------------------------------
# Parser → AmendmentInstruction conversion
# ---------------------------------------------------------------------------


def _parser_rows_to_instructions(
    parser_rows: list[dict],
) -> list[AmendmentInstruction]:
    """Convert raw parser output rows to AmendmentInstruction objects."""
    instructions = []
    for i, row in enumerate(parser_rows):
        instructions.append(AmendmentInstruction(
            order=i + 1,
            instruction_type=InstructionType(row["instruction_type"]),
            target_section_ref=row.get("target_section_ref"),
            source_text=row.get("source_text"),
            old_value=row.get("old_value"),
            new_value=row.get("new_value"),
            provenance=InstructionProvenance.PARSER,
        ))
    return instructions


# ---------------------------------------------------------------------------
# Semantic pipeline
# ---------------------------------------------------------------------------


def run_semantic_pipeline(chain: IssuerChain) -> SemanticPipelineResult:
    """Run the full semantic pipeline on one EDGAR chain.

    For each amendment:
      1. Load the source text from source_document_path.
      2. Parse with parse_v04.
      3. Map each parser instruction through the semantic mapper.
      4. Convert mapped mutations to AmendmentInstructions.
      5. Execute through the real executor.
      6. Track unresolved mutations (prevent authoritative promotion).

    The final reconstructed state is compared to the chain's
    ground_truth_state.

    Args:
        chain: an IssuerChain from edgar_chains.py.

    Returns:
        SemanticPipelineResult with metrics and per-step details.
    """
    current_state = {k: v.model_copy(deep=True) for k, v in chain.original_state.items()}
    steps: list[SemanticStepResult] = []
    inherited_unresolved: list[StructuredMutation] = []

    total_parser = 0
    total_mapped = 0
    total_unresolved = 0
    incorrect_mutations: list[str] = []

    for step in chain.amendments:
        # 1. Load source text
        source_path = step.source_document_path
        if source_path and Path(source_path).exists():
            text = Path(source_path).read_text(encoding="utf-8", errors="ignore")
        else:
            # No source file — no parser instructions
            text = ""

        # 2. Parse
        if text:
            parser_result = parse_v04(text)
            parser_instructions = _parser_rows_to_instructions(
                parser_result["instructions"]
            )
        else:
            parser_instructions = []

        total_parser += len(parser_instructions)

        # 3. Map each parser instruction
        mapped_instructions: list[AmendmentInstruction] = []
        step_mutations: list[StructuredMutation] = []
        step_unresolved: list[StructuredMutation] = []

        for ins in parser_instructions:
            result = map_instruction(ins, citation_document=step.description)
            step_mutations.extend(result.mutations)
            step_unresolved.extend(result.unresolved)

            # 4. Convert mapped mutations to AmendmentInstructions
            for mut in result.mutations:
                mapped_instructions.append(
                    mut.to_amendment_instruction(order=ins.order)
                )

        total_mapped += len(step_mutations)
        total_unresolved += len(step_unresolved)

        # 5. Execute mapped instructions through the real executor
        execution_result = execute_amendment(current_state, mapped_instructions)

        # Track incorrect mutations (executor rejected as unresolved)
        for ins in execution_result.unresolved:
            incorrect_mutations.append(
                f"{chain.chain_id} A{step.amendment_number} ins {ins.order}: "
                f"{ins.instruction_type} {ins.target_key}"
            )

        # 6. Chain-aware authority
        # Inherited unresolved that are not resolved by this step's applied
        still_inherited = inherited_unresolved  # simplified: no resolution logic here
        own_unresolved_count = len(step_unresolved) + len(execution_result.unresolved)
        is_authoritative = (
            execution_result.status == ExecutionStatus.COMPLETE
            and not still_inherited
            and own_unresolved_count == 0
        )

        # Update inherited for next step
        inherited_unresolved = still_inherited + [
            StructuredMutation(
                operation=InstructionType.UNRESOLVED,
                ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            )
            for _ in execution_result.unresolved
        ]

        steps.append(SemanticStepResult(
            amendment_number=step.amendment_number,
            effective_at=step.effective_at,
            pattern=step.pattern,
            parser_instruction_count=len(parser_instructions),
            mapper_mutations=step_mutations,
            mapper_unresolved=step_unresolved,
            execution_result=execution_result,
            is_authoritative=is_authoritative,
            inherited_unresolved_count=len(still_inherited),
        ))

        # Carry state forward
        current_state = {k: v.model_copy(deep=True) for k, v in execution_result.state.items()}

    # Compare final state to ground truth
    ground_truth = chain.ground_truth_state or {}
    state_mismatches: list[str] = []
    matched = 0
    total_gt = len(ground_truth)

    for key, gt_commitment in ground_truth.items():
        if key not in current_state:
            state_mismatches.append(f"Missing: {key}")
            continue
        recon = current_state[key]
        # Compare key fields
        if (recon.threshold == gt_commitment.threshold
                and recon.unit == gt_commitment.unit
                and recon.applicability == gt_commitment.applicability
                and recon.status == gt_commitment.status):
            matched += 1
        else:
            state_mismatches.append(
                f"Mismatch {key}: "
                f"threshold {recon.threshold} vs {gt_commitment.threshold}, "
                f"applicability {recon.applicability} vs {gt_commitment.applicability}"
            )

    # Check for extra commitments in reconstructed state
    for key in current_state:
        if key not in ground_truth:
            state_mismatches.append(f"Extra: {key}")

    # Compute metrics
    mapping_accuracy = total_mapped / total_parser if total_parser > 0 else 1.0
    unresolved_rate = total_unresolved / total_parser if total_parser > 0 else 0.0
    incorrect_mutation_rate = len(incorrect_mutations) / total_mapped if total_mapped > 0 else 0.0
    final_state_agreement = matched / total_gt if total_gt > 0 else 1.0

    return SemanticPipelineResult(
        chain_id=chain.chain_id,
        issuer_name=chain.issuer_name,
        steps=steps,
        reconstructed_state=current_state,
        ground_truth_state=ground_truth,
        total_parser_instructions=total_parser,
        total_mapped=total_mapped,
        total_unresolved=total_unresolved,
        mapping_accuracy=round(mapping_accuracy, 4),
        unresolved_rate=round(unresolved_rate, 4),
        incorrect_mutation_rate=round(incorrect_mutation_rate, 4),
        final_state_agreement=round(final_state_agreement, 4),
        incorrect_mutations=incorrect_mutations,
        state_mismatches=state_mismatches,
    )


def run_all_semantic_pipelines() -> list[SemanticPipelineResult]:
    """Run the semantic pipeline on all 3 EDGAR chains."""
    from edgar_chains import all_edgar_chains
    return [run_semantic_pipeline(chain) for chain in all_edgar_chains()]


# ---------------------------------------------------------------------------
# Metrics report
# ---------------------------------------------------------------------------


def render_metrics_report(results: list[SemanticPipelineResult]) -> str:
    """Render a metrics report for the semantic pipeline."""
    lines = []
    lines.append("# Semantic Mapper v0.1 — End-to-End Pipeline Metrics")
    lines.append("")
    lines.append("Pipeline: EDGAR → parser → semantic mapper → executor → state")
    lines.append("")

    lines.append("## Per-chain metrics")
    lines.append("")
    lines.append("| Chain | Parser ins | Mapped | Unresolved | Mapping acc | Unresolved rate | Incorrect rate | State agreement |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r.chain_id} | {r.total_parser_instructions} | {r.total_mapped} | "
            f"{r.total_unresolved} | {r.mapping_accuracy:.1%} | {r.unresolved_rate:.1%} | "
            f"{r.incorrect_mutation_rate:.1%} | {r.final_state_agreement:.1%} |"
        )
    lines.append("")

    # Aggregate
    total_parser = sum(r.total_parser_instructions for r in results)
    total_mapped = sum(r.total_mapped for r in results)
    total_unresolved = sum(r.total_unresolved for r in results)
    total_incorrect = sum(len(r.incorrect_mutations) for r in results)
    agg_mapping_acc = total_mapped / total_parser if total_parser > 0 else 1.0
    agg_unresolved_rate = total_unresolved / total_parser if total_parser > 0 else 0.0
    agg_incorrect_rate = total_incorrect / total_mapped if total_mapped > 0 else 0.0

    lines.append("## Aggregate metrics")
    lines.append("")
    lines.append(f"- Total parser instructions: {total_parser}")
    lines.append(f"- Total mapped (SEMANTIC_MAPPER): {total_mapped}")
    lines.append(f"- Total unresolved: {total_unresolved}")
    lines.append(f"- Mapping accuracy: {agg_mapping_acc:.1%}")
    lines.append(f"- Unresolved rate: {agg_unresolved_rate:.1%}")
    lines.append(f"- Incorrect automatic mutation rate: {agg_incorrect_rate:.1%}")
    lines.append("")

    # Per-step detail
    lines.append("## Per-step detail")
    lines.append("")
    for r in results:
        lines.append(f"### {r.chain_id}")
        lines.append("")
        for s in r.steps:
            lines.append(
                f"- A{s.amendment_number} ({s.pattern}): "
                f"parser={s.parser_instruction_count}, "
                f"mapped={len(s.mapper_mutations)}, "
                f"unresolved={len(s.mapper_unresolved)}, "
                f"exec_status={s.execution_result.status.value}, "
                f"authoritative={s.is_authoritative}"
            )
        lines.append("")

    # State mismatches
    lines.append("## State mismatches (reconstructed vs ground truth)")
    lines.append("")
    for r in results:
        if r.state_mismatches:
            lines.append(f"### {r.chain_id}")
            for m in r.state_mismatches:
                lines.append(f"- {m}")
            lines.append("")
        else:
            lines.append(f"### {r.chain_id}: PERFECT MATCH")
            lines.append("")

    # Incorrect mutations
    if any(r.incorrect_mutations for r in results):
        lines.append("## Incorrect automatic mutations (executor rejected)")
        lines.append("")
        for r in results:
            for m in r.incorrect_mutations:
                lines.append(f"- {m}")
        lines.append("")

    # Success criterion
    lines.append("## v0.1 Success criterion")
    lines.append("")
    lines.append("> At least one real EDGAR chain can be reconstructed end-to-end")
    lines.append("> from filed amendment text without manual semantic mutation entry,")
    lines.append("> while every unsupported instruction safely becomes UNRESOLVED.")
    lines.append("")
    for r in results:
        no_manual = all(
            mut.provenance == InstructionProvenance.SEMANTIC_MAPPER
            for s in r.steps
            for mut in s.mapper_mutations
        )
        all_unresolved_safe = all(
            mut.ambiguity_reason is not None
            for s in r.steps
            for mut in s.mapper_unresolved
        )
        lines.append(
            f"- {r.chain_id}: mapped={r.total_mapped}, "
            f"no_manual_in_mapped={'YES' if no_manual else 'NO'}, "
            f"all_unresolved_safe={'YES' if all_unresolved_safe else 'NO'}, "
            f"state_agreement={r.final_state_agreement:.1%}"
        )

    return "\n".join(lines)
