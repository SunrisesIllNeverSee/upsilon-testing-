"""Evaluation layer separation for the Upsilon measurement system.

Separates evaluation into three independent layers:

    A. EXTRACTION
       Can we correctly build S0 and GT from source documents?

    B. TRANSFORMATION
       Can we correctly interpret and execute amendments?

    C. RECONSTRUCTION
       Given valid S0 + GT, does reconstructed state match?

Each layer has its own metrics. No layer's metric is collapsed into a
single "accuracy" number. The final evaluator reports all three layers
separately.

This module defines:
  - The metric schema for each layer
  - The computation logic (from v2 results + failure matrix)
  - A report renderer that produces the three-layer evaluation

Output:
    results/evaluation_layers.json — machine-readable per-layer metrics
    results/evaluation_layers.md   — human-readable three-layer report
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Layer A: Extraction metrics
# ---------------------------------------------------------------------------


@dataclass
class ExtractionLayerMetrics:
    """Layer A: Can we correctly build S0 and GT from source documents?"""

    # S0 extraction
    s0_chains_attempted: int = 0  # new chains with S0 document
    s0_chains_succeeded: int = 0  # at least 1 commitment extracted
    s0_extraction_success_rate: float = 0.0
    s0_avg_coverage: float = 0.0  # commitments / (commitments + VQ)
    s0_total_commitments: int = 0
    s0_total_validation_queue: int = 0

    # S0 discovery failures (wrong document acquired)
    s0_discovery_failures: int = 0

    # S0 extraction failures (right document, extractor fails)
    s0_extraction_failures: int = 0

    # GT extraction
    gt_chains_with_cmp: int = 0  # chains with CMP document
    gt_chains_succeeded: int = 0  # at least 1 commitment extracted
    gt_extraction_success_rate: float = 0.0
    gt_avg_coverage: float = 0.0
    gt_total_commitments: int = 0
    gt_total_validation_queue: int = 0

    # GT discovery failures
    gt_discovery_failures: int = 0

    # GT extraction failures
    gt_extraction_failures: int = 0

    # Per-chain detail
    per_chain: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer B: Transformation metrics
# ---------------------------------------------------------------------------


@dataclass
class TransformationLayerMetrics:
    """Layer B: Can we correctly interpret and execute amendments?"""

    # Parser
    chains_with_parser_instructions: int = 0
    chains_with_zero_parser_instructions: int = 0
    total_parser_instructions: int = 0
    parser_failure_count: int = 0  # 0 instructions on non-trivial amendments
    unsupported_format_count: int = 0

    # Semantic mapper
    total_mapped_instructions: int = 0
    total_unresolved: int = 0
    semantic_mapping_coverage: float = 0.0  # mapped / parser
    semantic_mapping_precision: float = 0.0  # correct / mapped
    unresolved_rate: float = 0.0  # unresolved / parser
    mapper_failure_count: int = 0  # <50% coverage

    # Executor
    incorrect_automatic_mutations: int = 0
    incorrect_mutation_rate: float = 0.0
    execution_failure_count: int = 0

    # Per-chain detail
    per_chain: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer C: Reconstruction metrics
# ---------------------------------------------------------------------------


@dataclass
class ReconstructionLayerMetrics:
    """Layer C: Given valid S0 + GT, does reconstructed state match?

    Only computed for chains where:
      - S0 extraction succeeded (at least 1 commitment)
      - GT extraction succeeded (at least 1 commitment)
      - OR chain has manual ground truth

    This is the CONDITIONAL reconstruction metric — it measures
    reconstruction quality only when the measurement system has valid
    inputs. The unconditional metric (over all chains) is reported
    separately.
    """

    # Conditional reconstruction (valid S0 + GT only)
    chains_measurable: int = 0  # chains with valid S0 + GT
    chains_exact_match: int = 0  # 100% final state agreement
    conditional_exact_reconstruction_rate: float = 0.0
    avg_supported_field_agreement: float = 0.0

    # Unconditional (all chains with GT, including extraction failures)
    chains_with_gt_total: int = 0
    unconditional_exact_reconstruction_rate: float = 0.0

    # Lineage
    lineage_complete_count: int = 0
    lineage_completeness_rate: float = 0.0

    # Safety
    false_authoritative_promotion_count: int = 0
    false_authoritative_promotion_rate: float = 0.0

    # State comparison failures (reconstruction error, not extraction)
    state_comparison_failures: int = 0

    # Per-chain detail
    per_chain: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def compute_extraction_metrics(
    v2_results: dict,
    failure_matrix: dict,
) -> ExtractionLayerMetrics:
    """Compute Layer A (extraction) metrics."""
    m = ExtractionLayerMetrics()
    chains = failure_matrix["chains"]

    new_chains = [c for c in chains if c["gt_extraction_source"] != "manual"]

    m.s0_chains_attempted = len(new_chains)
    m.s0_chains_succeeded = sum(1 for c in new_chains if c["s0_extraction_commitments"] > 0)
    m.s0_extraction_success_rate = (
        m.s0_chains_succeeded / m.s0_chains_attempted
        if m.s0_chains_attempted > 0
        else 0.0
    )
    m.s0_total_commitments = sum(c["s0_extraction_commitments"] for c in new_chains)
    m.s0_total_validation_queue = sum(c["s0_extraction_validation_queue"] for c in new_chains)
    m.s0_avg_coverage = (
        sum(c["s0_extraction_commitments"] for c in new_chains)
        / max(1, sum(
            c["s0_extraction_commitments"] + c["s0_extraction_validation_queue"]
            for c in new_chains
        ))
    )

    m.s0_discovery_failures = sum(
        1 for c in new_chains if c["causes"].get("S0_DISCOVERY_FAILURE", False)
    )
    m.s0_extraction_failures = sum(
        1 for c in new_chains if c["causes"].get("S0_EXTRACTION_FAILURE", False)
    )

    cmp_chains = [c for c in new_chains if c["gt_extraction_source"] == "CMP"]
    m.gt_chains_with_cmp = len(cmp_chains)
    m.gt_chains_succeeded = sum(1 for c in cmp_chains if c["gt_extraction_commitments"] > 0)
    m.gt_extraction_success_rate = (
        m.gt_chains_succeeded / m.gt_chains_with_cmp
        if m.gt_chains_with_cmp > 0
        else 0.0
    )
    m.gt_total_commitments = sum(c["gt_extraction_commitments"] for c in cmp_chains)
    m.gt_total_validation_queue = sum(c["gt_extraction_validation_queue"] for c in cmp_chains)
    m.gt_avg_coverage = (
        sum(c["gt_extraction_commitments"] for c in cmp_chains)
        / max(1, sum(
            c["gt_extraction_commitments"] + c["gt_extraction_validation_queue"]
            for c in cmp_chains
        ))
    )

    m.gt_discovery_failures = sum(
        1 for c in cmp_chains if c["causes"].get("GT_DISCOVERY_FAILURE", False)
    )
    m.gt_extraction_failures = sum(
        1 for c in cmp_chains if c["causes"].get("GT_EXTRACTION_FAILURE", False)
    )

    m.per_chain = [
        {
            "chain_id": c["chain_id"],
            "s0_commitments": c["s0_extraction_commitments"],
            "s0_vq": c["s0_extraction_validation_queue"],
            "gt_commitments": c["gt_extraction_commitments"],
            "gt_vq": c["gt_extraction_validation_queue"],
            "gt_source": c["gt_extraction_source"],
            "s0_discovery_failure": c["causes"].get("S0_DISCOVERY_FAILURE", False),
            "s0_extraction_failure": c["causes"].get("S0_EXTRACTION_FAILURE", False),
            "gt_discovery_failure": c["causes"].get("GT_DISCOVERY_FAILURE", False),
            "gt_extraction_failure": c["causes"].get("GT_EXTRACTION_FAILURE", False),
        }
        for c in new_chains
    ]

    return m


def compute_transformation_metrics(
    v2_results: dict,
    failure_matrix: dict,
) -> TransformationLayerMetrics:
    """Compute Layer B (transformation) metrics."""
    m = TransformationLayerMetrics()
    chains = failure_matrix["chains"]

    # Only count chains with amendments (exclude manual chains with 0 amendments
    # if any — but all 25 have amendments)
    all_chains = chains

    m.total_parser_instructions = sum(c["parser_detected_instructions"] for c in all_chains)
    m.chains_with_parser_instructions = sum(
        1 for c in all_chains if c["parser_detected_instructions"] > 0
    )
    m.chains_with_zero_parser_instructions = sum(
        1 for c in all_chains if c["parser_detected_instructions"] == 0
    )

    m.parser_failure_count = sum(
        1 for c in all_chains if c["causes"].get("PARSER_FAILURE", False)
    )
    m.unsupported_format_count = sum(
        1 for c in all_chains if c["causes"].get("UNSUPPORTED_DOCUMENT_FORMAT", False)
    )

    m.total_mapped_instructions = sum(c["semantic_mapped_instructions"] for c in all_chains)
    m.total_unresolved = sum(c["unresolved_instructions"] for c in all_chains)
    m.semantic_mapping_coverage = (
        m.total_mapped_instructions / m.total_parser_instructions
        if m.total_parser_instructions > 0
        else 0.0
    )
    m.unresolved_rate = (
        m.total_unresolved / m.total_parser_instructions
        if m.total_parser_instructions > 0
        else 0.0
    )
    # Precision: (mapped - incorrect) / mapped
    total_incorrect = sum(c["incorrect_automatic_mutations"] for c in all_chains)
    m.semantic_mapping_precision = (
        (m.total_mapped_instructions - total_incorrect) / m.total_mapped_instructions
        if m.total_mapped_instructions > 0
        else 0.0
    )
    m.mapper_failure_count = sum(
        1 for c in all_chains if c["causes"].get("SEMANTIC_MAPPING_FAILURE", False)
    )

    m.incorrect_automatic_mutations = total_incorrect
    m.incorrect_mutation_rate = (
        total_incorrect / m.total_mapped_instructions
        if m.total_mapped_instructions > 0
        else 0.0
    )
    m.execution_failure_count = sum(
        1 for c in all_chains if c["causes"].get("EXECUTION_FAILURE", False)
    )

    m.per_chain = [
        {
            "chain_id": c["chain_id"],
            "parser_instructions": c["parser_detected_instructions"],
            "mapped": c["semantic_mapped_instructions"],
            "unresolved": c["unresolved_instructions"],
            "incorrect": c["incorrect_automatic_mutations"],
            "parser_failure": c["causes"].get("PARSER_FAILURE", False),
            "mapper_failure": c["causes"].get("SEMANTIC_MAPPING_FAILURE", False),
            "execution_failure": c["causes"].get("EXECUTION_FAILURE", False),
            "unsupported_format": c["causes"].get("UNSUPPORTED_DOCUMENT_FORMAT", False),
        }
        for c in all_chains
    ]

    return m


def compute_reconstruction_metrics(
    v2_results: dict,
    failure_matrix: dict,
) -> ReconstructionLayerMetrics:
    """Compute Layer C (reconstruction) metrics."""
    m = ReconstructionLayerMetrics()
    chains = failure_matrix["chains"]
    agg = v2_results["aggregate_metrics"]

    # Chains with ground truth (manual or extracted)
    gt_chains = [c for c in chains if c["has_ground_truth"]]
    m.chains_with_gt_total = len(gt_chains)

    # Conditional: chains where BOTH S0 and GT extraction succeeded
    # (or manual chains with hand-extracted states)
    measurable = []
    for c in gt_chains:
        if c["gt_extraction_source"] == "manual" or (
            c["s0_extraction_commitments"] > 0
            and c["gt_extraction_commitments"] > 0
        ):
            measurable.append(c)

    m.chains_measurable = len(measurable)
    m.chains_exact_match = sum(
        1 for c in measurable
        if c["final_state_exact_agreement"] is not None
        and c["final_state_exact_agreement"] == 1.0
    )
    m.conditional_exact_reconstruction_rate = (
        m.chains_exact_match / m.chains_measurable
        if m.chains_measurable > 0
        else 0.0
    )

    # Average supported field agreement (conditional)
    field_agreements = [
        c["supported_field_agreement"]
        for c in measurable
        if c["supported_field_agreement"] is not None
    ]
    m.avg_supported_field_agreement = (
        sum(field_agreements) / len(field_agreements)
        if field_agreements
        else 0.0
    )

    # Unconditional: all chains with GT
    exact_all = sum(
        1 for c in gt_chains
        if c["final_state_exact_agreement"] is not None
        and c["final_state_exact_agreement"] == 1.0
    )
    m.unconditional_exact_reconstruction_rate = (
        exact_all / m.chains_with_gt_total
        if m.chains_with_gt_total > 0
        else 0.0
    )

    # Lineage
    m.lineage_complete_count = sum(1 for c in chains if c["lineage_complete"])
    m.lineage_completeness_rate = m.lineage_complete_count / len(chains) if chains else 0.0

    # Safety
    m.false_authoritative_promotion_count = agg["false_authoritative_promotion_count"]
    m.false_authoritative_promotion_rate = agg["false_authoritative_promotion_rate"]

    # State comparison failures (reconstruction error only)
    m.state_comparison_failures = sum(
        1 for c in chains if c["causes"].get("STATE_COMPARISON_FAILURE", False)
    )

    m.per_chain = [
        {
            "chain_id": c["chain_id"],
            "has_gt": c["has_ground_truth"],
            "gt_source": c["gt_extraction_source"],
            "s0_commitments": c["s0_extraction_commitments"],
            "gt_commitments": c["gt_extraction_commitments"],
            "measurable": c in measurable,
            "final_state_agreement": c["final_state_exact_agreement"],
            "supported_field_agreement": c["supported_field_agreement"],
            "lineage_complete": c["lineage_complete"],
            "state_comparison_failure": c["causes"].get("STATE_COMPARISON_FAILURE", False),
        }
        for c in gt_chains
    ]

    return m


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_evaluation_report(
    extraction: ExtractionLayerMetrics,
    transformation: TransformationLayerMetrics,
    reconstruction: ReconstructionLayerMetrics,
) -> str:
    """Render the three-layer evaluation report."""
    lines: list[str] = []

    lines.append("# Development Chain Study v2 — Three-Layer Evaluation")
    lines.append("")
    lines.append("**Frozen reference**: tag `chain-study-v2-development` (commit fb0862d)")
    lines.append("")
    lines.append("Evaluation is separated into three independent layers. No layer's")
    lines.append("metric is collapsed into a single 'accuracy' number.")
    lines.append("")

    # --- Layer A ---
    lines.append("## Layer A: Extraction")
    lines.append("")
    lines.append("> Can we correctly build S0 and GT from source documents?")
    lines.append("")
    lines.append("### S0 Extraction (origin state)")
    lines.append("")
    lines.append("```text")
    lines.append(f"Chains attempted:              {extraction.s0_chains_attempted}")
    lines.append(f"Chains succeeded (≥1 commit):  {extraction.s0_chains_succeeded}")
    lines.append(f"S0 extraction success rate:    {extraction.s0_extraction_success_rate:.1%}")
    lines.append(f"S0 avg coverage:               {extraction.s0_avg_coverage:.1%}")
    lines.append(f"Total S0 commitments:          {extraction.s0_total_commitments}")
    lines.append(f"Total S0 validation queue:     {extraction.s0_total_validation_queue}")
    lines.append(f"S0 discovery failures:         {extraction.s0_discovery_failures}")
    lines.append(f"S0 extraction failures:        {extraction.s0_extraction_failures}")
    lines.append("```")
    lines.append("")
    lines.append("### GT Extraction (ground truth)")
    lines.append("")
    lines.append("```text")
    lines.append(f"Chains with CMP document:      {extraction.gt_chains_with_cmp}")
    lines.append(f"Chains succeeded (≥1 commit):  {extraction.gt_chains_succeeded}")
    lines.append(f"GT extraction success rate:    {extraction.gt_extraction_success_rate:.1%}")
    lines.append(f"GT avg coverage:               {extraction.gt_avg_coverage:.1%}")
    lines.append(f"Total GT commitments:          {extraction.gt_total_commitments}")
    lines.append(f"Total GT validation queue:     {extraction.gt_total_validation_queue}")
    lines.append(f"GT discovery failures:         {extraction.gt_discovery_failures}")
    lines.append(f"GT extraction failures:        {extraction.gt_extraction_failures}")
    lines.append("```")
    lines.append("")

    # --- Layer B ---
    lines.append("## Layer B: Transformation")
    lines.append("")
    lines.append("> Can we correctly interpret and execute amendments?")
    lines.append("")
    lines.append("```text")
    lines.append(f"Chains with parser instr:      {transformation.chains_with_parser_instructions}")
    lines.append(f"Chains with 0 parser instr:    {transformation.chains_with_zero_parser_instructions}")
    lines.append(f"Total parser instructions:     {transformation.total_parser_instructions}")
    lines.append(f"Total mapped:                  {transformation.total_mapped_instructions}")
    lines.append(f"Total unresolved:              {transformation.total_unresolved}")
    lines.append(f"Semantic mapping coverage:     {transformation.semantic_mapping_coverage:.1%}")
    lines.append(f"Semantic mapping precision:    {transformation.semantic_mapping_precision:.1%}")
    lines.append(f"Unresolved rate:               {transformation.unresolved_rate:.1%}")
    lines.append(f"Incorrect mutations:           {transformation.incorrect_automatic_mutations}")
    lines.append(f"Incorrect mutation rate:       {transformation.incorrect_mutation_rate:.1%}")
    lines.append(f"Parser failures:               {transformation.parser_failure_count}")
    lines.append(f"Unsupported format:            {transformation.unsupported_format_count}")
    lines.append(f"Mapper failures (<50% cov):    {transformation.mapper_failure_count}")
    lines.append(f"Execution failures:            {transformation.execution_failure_count}")
    lines.append("```")
    lines.append("")

    # --- Layer C ---
    lines.append("## Layer C: Reconstruction")
    lines.append("")
    lines.append("> Given valid S0 + GT, does reconstructed state match?")
    lines.append("")
    lines.append("```text")
    lines.append(f"Chains with GT (total):        {reconstruction.chains_with_gt_total}")
    lines.append(f"Chains measurable (valid S0+GT): {reconstruction.chains_measurable}")
    lines.append(f"Chains exact match:            {reconstruction.chains_exact_match}")
    lines.append(f"Conditional exact recon rate:  {reconstruction.conditional_exact_reconstruction_rate:.1%}")
    lines.append(f"Avg supported field agreement: {reconstruction.avg_supported_field_agreement:.1%}")
    lines.append(f"Unconditional exact recon rate: {reconstruction.unconditional_exact_reconstruction_rate:.1%}")
    lines.append(f"Lineage completeness rate:     {reconstruction.lineage_completeness_rate:.1%}")
    lines.append(f"False auth promotion count:    {reconstruction.false_authoritative_promotion_count}")
    lines.append(f"False auth promotion rate:     {reconstruction.false_authoritative_promotion_rate:.1%}")
    lines.append(f"State comparison failures:     {reconstruction.state_comparison_failures}")
    lines.append("```")
    lines.append("")
    lines.append("### Conditional vs Unconditional")
    lines.append("")
    lines.append("The **conditional** reconstruction rate measures reconstruction quality")
    lines.append("only when the measurement system has valid inputs (S0 and GT both")
    lines.append("extracted successfully). The **unconditional** rate includes chains")
    lines.append("where extraction failed — those chains cannot be reconstructed")
    lines.append("regardless of reconstruction quality.")
    lines.append("")
    lines.append("For the held-out study, the conditional rate is the primary endpoint.")
    lines.append("The unconditional rate is reported as a secondary endpoint to show")
    lines.append("the end-to-end system performance including extraction.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    with open("results/chain_study_v2_results.json", encoding="utf-8") as f:
        v2_results = json.load(f)
    with open("results/failure_matrix.json", encoding="utf-8") as f:
        failure_matrix = json.load(f)

    extraction = compute_extraction_metrics(v2_results, failure_matrix)
    transformation = compute_transformation_metrics(v2_results, failure_matrix)
    reconstruction = compute_reconstruction_metrics(v2_results, failure_matrix)

    # Write JSON
    layers_data = {
        "study": "development_chain_study_v2_evaluation_layers",
        "frozen_tag": "chain-study-v2-development",
        "layer_a_extraction": asdict(extraction),
        "layer_b_transformation": asdict(transformation),
        "layer_c_reconstruction": asdict(reconstruction),
    }
    json_path = Path("results/evaluation_layers.json")
    json_path.write_text(json.dumps(layers_data, indent=2), encoding="utf-8")
    print(f"Evaluation layers JSON: {json_path}")

    # Write report
    report = render_evaluation_report(extraction, transformation, reconstruction)
    report_path = Path("results/evaluation_layers.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Evaluation layers report: {report_path}")

    # Print summary
    print()
    print("=" * 60)
    print("THREE-LAYER EVALUATION SUMMARY")
    print("=" * 60)
    print()
    print("Layer A (Extraction):")
    print(f"  S0 success: {extraction.s0_chains_succeeded}/{extraction.s0_chains_attempted} "
          f"({extraction.s0_extraction_success_rate:.1%})")
    print(f"  GT success: {extraction.gt_chains_succeeded}/{extraction.gt_chains_with_cmp} "
          f"({extraction.gt_extraction_success_rate:.1%})")
    print()
    print("Layer B (Transformation):")
    print(f"  Mapping coverage: {transformation.semantic_mapping_coverage:.1%}")
    print(f"  Mapping precision: {transformation.semantic_mapping_precision:.1%}")
    print(f"  Unresolved rate: {transformation.unresolved_rate:.1%}")
    print(f"  Incorrect mutation rate: {transformation.incorrect_mutation_rate:.1%}")
    print()
    print("Layer C (Reconstruction):")
    print(f"  Conditional exact: {reconstruction.conditional_exact_reconstruction_rate:.1%} "
          f"({reconstruction.chains_exact_match}/{reconstruction.chains_measurable})")
    print(f"  Unconditional exact: {reconstruction.unconditional_exact_reconstruction_rate:.1%} "
          f"({reconstruction.chains_with_gt_total} chains with GT)")
    print(f"  False auth promotion: {reconstruction.false_authoritative_promotion_count}")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
