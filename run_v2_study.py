"""V2 Development Study runner (Step 21 / Section F).

Runs the v2 semantic pipeline on all 50 known real issuer chains
(25 development + 25 v1 held-out) and tracks all required metrics.

The former v1 held-out set is now eligible for v2 DEVELOPMENT because
its results have already been inspected.

This is a DEVELOPMENT phase — tuning is allowed.  The engineering gates
(Section G) determine whether v2 is ready for new held-out validation.

Metrics tracked:
  - semantic mapping coverage
  - semantic mapping precision
  - incorrect accepted mutation rate
  - UNRESOLVED rate
  - S0 extraction coverage
  - GT extraction coverage
  - genre coverage
  - end-to-end reconstruction rate
  - false authoritative promotion rate

Usage:
    python run_v2_study.py
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chain_reconstruction import IssuerChain
from commitment_extractor import ExtractionResult
from genre_adapters import analyze_genre_distribution
from gt_extractor import extract_ground_truth_for_chain
from pattern_classifier import classify_amendment
from run_chain_study import (
    _compute_supported_field_agreement,
    classify_failure,
)
from run_chain_study_v2 import (
    AggregateMetricsV2,
    IssuerStudyResultV2,
    _compute_extraction_status,
    build_v2_issuer_result,
    classify_failure_v2,
    compute_v2_aggregate_metrics,
)
from run_held_out_study import all_held_out_chains
from s0_extractor import extract_s0_state_for_chain
from semantic_pipeline_v2 import SemanticPipelineResultV2, run_semantic_pipeline_v2


# ---------------------------------------------------------------------------
# V2 study result
# ---------------------------------------------------------------------------


@dataclass
class V2StudyResult:
    """Aggregate result of the v2 development study."""

    total_chains: int
    total_amendments: int
    total_parser_instructions: int
    total_mapped: int
    total_unresolved: int
    total_incorrect_mutations: int
    # Coverage metrics
    semantic_mapping_coverage: float
    semantic_mapping_precision: float
    incorrect_accepted_mutation_rate: float
    unresolved_rate: float
    # Extraction metrics
    s0_extraction_success_rate: float
    gt_extraction_success_rate: float
    s0_extraction_coverage_avg: float
    gt_extraction_coverage_avg: float
    # Genre metrics
    genre_distribution: dict[str, int]
    unknown_genre_rate: float
    # Reconstruction metrics
    end_to_end_reconstruction_rate: float
    lineage_completeness_rate: float
    false_authoritative_promotion_rate: float
    false_authoritative_promotion_count: int
    # Breakdown of total_mapped by source path:
    #   mapped_from_parser: candidates from the INCREMENTAL adapter
    #     (parse_v04 → resolver v2).  Used as the numerator for
    #     semantic_mapping_coverage.
    #   mapped_from_extraction: candidates from the FULL_RESTATEMENT /
    #     CONFORMED_COPY adapters (direct extraction → diff).  No
    #     parser-instruction denominator; tracked separately.
    mapped_from_parser: int = 0
    mapped_from_extraction: int = 0
    # Per-chain results
    per_chain: list[dict[str, Any]] = field(default_factory=list)
    # Engineering gates
    gates: dict[str, bool] = field(default_factory=dict)
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Study runner
# ---------------------------------------------------------------------------


def run_v2_study() -> V2StudyResult:
    """Run the v2 study on all 50 chains.

    Returns a V2StudyResult with all metrics and gate evaluations.
    """
    from run_chain_study_v2 import all_v2_chains

    # Load all 50 chains (25 dev + 25 held-out)
    dev_chains = all_v2_chains()
    held_chains = all_held_out_chains()

    all_chain_data = dev_chains + held_chains
    print(f"Loaded {len(all_chain_data)} chains ({len(dev_chains)} dev + {len(held_chains)} held-out)")

    # Run v2 pipeline on each chain
    pipeline_results: list[SemanticPipelineResultV2] = []
    per_chain_results: list[dict[str, Any]] = []

    total_parser = 0
    total_mapped = 0
    total_mapped_from_parser = 0
    total_mapped_from_extraction = 0
    total_unresolved = 0
    total_incorrect = 0
    total_amendments = 0
    genre_dist: dict[str, int] = {}
    false_auth_promotions = 0
    chains_with_gt = 0
    chains_with_exact_recon = 0
    chains_with_lineage = 0

    # Extraction metrics (new chains only — exclude manual/existing)
    s0_success = 0
    gt_success = 0
    cmp_count = 0
    s0_cov_sum = 0.0
    gt_cov_sum = 0.0
    new_chain_count = 0

    for i, (chain, s0_result, gt_result) in enumerate(all_chain_data, 1):
        print(f"  [{i}/{len(all_chain_data)}] {chain.chain_id}...", end=" ")

        # Run v2 pipeline
        pipe_result = run_semantic_pipeline_v2(chain)

        # Accumulate metrics
        total_parser += pipe_result.total_parser_instructions
        total_mapped += pipe_result.total_mapped
        total_mapped_from_parser += pipe_result.mapped_from_parser
        total_mapped_from_extraction += pipe_result.mapped_from_extraction
        total_unresolved += pipe_result.total_unresolved
        # incorrect_mutations now comes from state mismatches (truly
        # incorrect applied mutations), not executor rejections.
        total_incorrect += len(pipe_result.incorrect_mutations)
        total_amendments += len(chain.amendments)

        for g, c in pipe_result.genre_distribution.items():
            genre_dist[g] = genre_dist.get(g, 0) + c

        # Check false authoritative promotion
        # (chain claims authoritative but has incorrect mutations or mismatches)
        has_gt = chain.ground_truth_state is not None and len(chain.ground_truth_state) > 0
        if has_gt:
            chains_with_gt += 1
            if pipe_result.final_state_agreement == 1.0 and len(pipe_result.incorrect_mutations) == 0:
                chains_with_exact_recon += 1

        # Check lineage completeness
        lineage_complete = (
            len(pipe_result.steps) == len(chain.amendments)
            and len(pipe_result.steps) > 0
            and all(s.execution_result.status.value == "COMPLETE" for s in pipe_result.steps)
        )
        if lineage_complete:
            chains_with_lineage += 1

        # Check false authoritative promotion
        # A false promotion occurs when a step is marked authoritative
        # but an incorrect mutation was applied at or before that step.
        # We use temporal ordering: an incorrect mutation in amendment 5
        # does NOT retroactively make amendment 2's authoritative
        # promotion false — the system had no way to know at the time.
        incorrect_steps = {s for _, s in pipe_result.incorrect_pair_steps}
        for step_idx, step in enumerate(pipe_result.steps):
            if not step.is_authoritative:
                continue
            # Check if any incorrect mutation was applied at or before
            # this step's index.
            if any(inc_step <= step_idx for inc_step in incorrect_steps):
                false_auth_promotions += 1
                break  # count once per chain

        # Extraction metrics (new chains only)
        is_manual = s0_result.source_label == "S0-manual"
        if not is_manual:
            new_chain_count += 1
            if len(s0_result.commitments) > 0:
                s0_success += 1
            s0_cov_sum += s0_result.extraction_coverage
            if gt_result is not None:
                cmp_count += 1
                if len(gt_result.commitments) > 0:
                    gt_success += 1
                gt_cov_sum += gt_result.extraction_coverage

        # Per-chain result
        per_chain_results.append({
            "chain_id": chain.chain_id,
            "issuer_name": chain.issuer_name,
            "amendments": len(chain.amendments),
            "parser_instructions": pipe_result.total_parser_instructions,
            "mapped": pipe_result.total_mapped,
            "mapped_from_parser": pipe_result.mapped_from_parser,
            "mapped_from_extraction": pipe_result.mapped_from_extraction,
            "unresolved": pipe_result.total_unresolved,
            "incorrect_mutations": len(pipe_result.incorrect_mutations),
            # Semantic mapping coverage = parser-mapped / parser
            # instructions.  Extraction-mapped candidates have no
            # parser-instruction denominator and are excluded from
            # this ratio (they are tracked separately).
            "mapping_coverage": round(
                pipe_result.mapped_from_parser / pipe_result.total_parser_instructions
                if pipe_result.total_parser_instructions > 0 else 0.0, 4
            ),
            "final_state_agreement": pipe_result.final_state_agreement,
            "has_ground_truth": has_gt,
            "genre_distribution": pipe_result.genre_distribution,
            "incorrect_mutation_details": pipe_result.incorrect_mutations,
            "state_mismatches": pipe_result.state_mismatches[:10],  # cap for JSON size
        })

        print(
            f"parser={pipe_result.total_parser_instructions} "
            f"mapped={pipe_result.total_mapped} "
            f"(parser={pipe_result.mapped_from_parser} "
            f"extract={pipe_result.mapped_from_extraction}) "
            f"unresolved={pipe_result.total_unresolved} "
            f"incorrect={len(pipe_result.incorrect_mutations)}"
        )

    # Compute aggregate metrics
    total_chains = len(all_chain_data)
    # Semantic mapping coverage = parser-mapped / parser instructions.
    # Extraction-mapped candidates (from full_restatement /
    # conformed_copy adapters) have no parser-instruction denominator
    # and are excluded from this ratio.  They are reported separately
    # as extraction_coverage_count.
    semantic_mapping_coverage = (
        total_mapped_from_parser / total_parser if total_parser > 0 else 0.0
    )
    semantic_mapping_precision = (
        (total_mapped - total_incorrect) / total_mapped if total_mapped > 0 else 1.0
    )
    incorrect_accepted_mutation_rate = (
        total_incorrect / total_mapped if total_mapped > 0 else 0.0
    )
    unresolved_rate = total_unresolved / total_parser if total_parser > 0 else 0.0
    end_to_end_reconstruction_rate = (
        chains_with_exact_recon / chains_with_gt if chains_with_gt > 0 else 0.0
    )
    lineage_completeness_rate = chains_with_lineage / total_chains
    false_auth_rate = false_auth_promotions / total_chains
    unknown_genre_rate = genre_dist.get("unknown", 0) / total_amendments if total_amendments > 0 else 0.0

    s0_extraction_success_rate = s0_success / new_chain_count if new_chain_count > 0 else 0.0
    gt_extraction_success_rate = gt_success / cmp_count if cmp_count > 0 else 0.0
    s0_extraction_coverage_avg = s0_cov_sum / new_chain_count if new_chain_count > 0 else 0.0
    gt_extraction_coverage_avg = gt_cov_sum / cmp_count if cmp_count > 0 else 0.0

    # Evaluate engineering gates (Section G)
    gates = {
        "semantic_mapping_coverage_gte_50pct": semantic_mapping_coverage >= 0.50,
        "incorrect_accepted_mutations_eq_0": total_incorrect == 0,
        "false_authoritative_promotions_eq_0": false_auth_promotions == 0,
        "s0_extraction_gte_85pct": s0_extraction_success_rate >= 0.85,
        "gt_extraction_gte_70pct": gt_extraction_success_rate >= 0.70,
        "unknown_genre_rate_lt_20pct": unknown_genre_rate < 0.20,
        "stretch_mapping_coverage_gte_70pct": semantic_mapping_coverage >= 0.70,
    }

    result = V2StudyResult(
        total_chains=total_chains,
        total_amendments=total_amendments,
        total_parser_instructions=total_parser,
        total_mapped=total_mapped,
        mapped_from_parser=total_mapped_from_parser,
        mapped_from_extraction=total_mapped_from_extraction,
        total_unresolved=total_unresolved,
        total_incorrect_mutations=total_incorrect,
        semantic_mapping_coverage=round(semantic_mapping_coverage, 4),
        semantic_mapping_precision=round(semantic_mapping_precision, 4),
        incorrect_accepted_mutation_rate=round(incorrect_accepted_mutation_rate, 4),
        unresolved_rate=round(unresolved_rate, 4),
        s0_extraction_success_rate=round(s0_extraction_success_rate, 4),
        gt_extraction_success_rate=round(gt_extraction_success_rate, 4),
        s0_extraction_coverage_avg=round(s0_extraction_coverage_avg, 4),
        gt_extraction_coverage_avg=round(gt_extraction_coverage_avg, 4),
        genre_distribution=genre_dist,
        unknown_genre_rate=round(unknown_genre_rate, 4),
        end_to_end_reconstruction_rate=round(end_to_end_reconstruction_rate, 4),
        lineage_completeness_rate=round(lineage_completeness_rate, 4),
        false_authoritative_promotion_rate=round(false_auth_rate, 4),
        false_authoritative_promotion_count=false_auth_promotions,
        per_chain=per_chain_results,
        gates=gates,
        generated_at=datetime.now(UTC).isoformat(),
    )

    return result


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_v2_study_report(result: V2StudyResult) -> str:
    """Render the v2 study report as markdown."""
    lines: list[str] = []
    lines.append("# Step 21 — Upsilon v2 Semantic Coverage Build — Development Study")
    lines.append("")
    lines.append(f"**Generated:** {result.generated_at}")
    lines.append(f"**Chains:** {result.total_chains} (25 development + 25 v1 held-out)")
    lines.append(f"**Phase:** DEVELOPMENT (tuning allowed)")
    lines.append("")

    lines.append("## Summary Metrics")
    lines.append("")
    lines.append("```text")
    lines.append(f"Total chains:                      {result.total_chains}")
    lines.append(f"Total amendments:                  {result.total_amendments}")
    lines.append(f"Total parser instructions:         {result.total_parser_instructions}")
    lines.append(f"Total semantic-mapped:             {result.total_mapped}")
    lines.append(f"  mapped from parser:              {result.mapped_from_parser}")
    lines.append(f"  mapped from extraction:           {result.mapped_from_extraction}")
    lines.append(f"Total UNRESOLVED:                  {result.total_unresolved}")
    lines.append(f"Total incorrect mutations:         {result.total_incorrect_mutations}")
    lines.append("")
    lines.append(f"Semantic mapping coverage:         {result.semantic_mapping_coverage:.2%}")
    lines.append(f"  (parser-mapped / parser instr.)")
    lines.append(f"Semantic mapping precision:        {result.semantic_mapping_precision:.2%}")
    lines.append(f"Incorrect accepted mutation rate:  {result.incorrect_accepted_mutation_rate:.2%}")
    lines.append(f"UNRESOLVED rate:                   {result.unresolved_rate:.2%}")
    lines.append(f"End-to-end reconstruction rate:    {result.end_to_end_reconstruction_rate:.2%}")
    lines.append(f"Lineage completeness rate:         {result.lineage_completeness_rate:.2%}")
    lines.append(f"False auth promotion rate:         {result.false_authoritative_promotion_rate:.2%}")
    lines.append(f"False auth promotion count:        {result.false_authoritative_promotion_count}")
    lines.append("")
    lines.append(f"S0 extraction success rate:        {result.s0_extraction_success_rate:.2%}")
    lines.append(f"GT extraction success rate:        {result.gt_extraction_success_rate:.2%}")
    lines.append(f"S0 extraction coverage (avg):      {result.s0_extraction_coverage_avg:.2%}")
    lines.append(f"GT extraction coverage (avg):      {result.gt_extraction_coverage_avg:.2%}")
    lines.append(f"Unknown genre rate:                {result.unknown_genre_rate:.2%}")
    lines.append("```")
    lines.append("")

    # Genre distribution
    lines.append("## Genre Distribution")
    lines.append("")
    lines.append("| Genre | Count |")
    lines.append("|---|---:|")
    for g, c in sorted(result.genre_distribution.items(), key=lambda x: -x[1]):
        lines.append(f"| {g} | {c} |")
    lines.append("")

    # Engineering gates
    lines.append("## Engineering Gates (Section G)")
    lines.append("")
    lines.append("| Gate | Requirement | Status |")
    lines.append("|---|---|---|")
    lines.append(f"| Semantic mapping coverage | >= 50% | {'PASS' if result.gates['semantic_mapping_coverage_gte_50pct'] else 'FAIL'} ({result.semantic_mapping_coverage:.2%}) |")
    lines.append(f"| Incorrect accepted mutations | = 0 | {'PASS' if result.gates['incorrect_accepted_mutations_eq_0'] else 'FAIL'} ({result.total_incorrect_mutations}) |")
    lines.append(f"| False authoritative promotions | = 0 | {'PASS' if result.gates['false_authoritative_promotions_eq_0'] else 'FAIL'} ({result.false_authoritative_promotion_count}) |")
    lines.append(f"| S0 extraction (where eligible) | >= 85% | {'PASS' if result.gates['s0_extraction_gte_85pct'] else 'FAIL'} ({result.s0_extraction_success_rate:.2%}) |")
    lines.append(f"| GT extraction (where eligible) | >= 70% | {'PASS' if result.gates['gt_extraction_gte_70pct'] else 'FAIL'} ({result.gt_extraction_success_rate:.2%}) |")
    lines.append(f"| Unknown genre rate | < 20% | {'PASS' if result.gates['unknown_genre_rate_lt_20pct'] else 'FAIL'} ({result.unknown_genre_rate:.2%}) |")
    lines.append(f"| Stretch: mapping coverage | >= 70% | {'PASS' if result.gates['stretch_mapping_coverage_gte_70pct'] else 'FAIL'} ({result.semantic_mapping_coverage:.2%}) |")
    lines.append("")

    all_gates_pass = all(
        v for k, v in result.gates.items() if not k.startswith("stretch")
    )
    if all_gates_pass:
        lines.append("**ALL ENGINEERING GATES PASS** — v2 is ready for new held-out validation.")
    else:
        lines.append("**NOT ALL GATES PASS** — v2 is NOT ready for new held-out validation.")
        lines.append("")
        lines.append("Failing gates:")
        for gate, passed in result.gates.items():
            if not passed and not gate.startswith("stretch"):
                lines.append(f"  - {gate}")
    lines.append("")

    # Per-chain results
    lines.append("## Per-Chain Results")
    lines.append("")
    lines.append("| Chain | Amendments | Parser | Mapped (parser/extract) | Unresolved | Incorrect | Coverage | State Agreement |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in result.per_chain:
        agreement = (
            f"{r['final_state_agreement']:.1%}"
            if r["final_state_agreement"] is not None
            else "N/A"
        )
        mapped_str = (
            f"{r['mapped']} ({r.get('mapped_from_parser', 0)}/"
            f"{r.get('mapped_from_extraction', 0)})"
        )
        lines.append(
            f"| {r['chain_id']} | {r['amendments']} | {r['parser_instructions']} | "
            f"{mapped_str} | {r['unresolved']} | {r['incorrect_mutations']} | "
            f"{r['mapping_coverage']:.1%} | {agreement} |"
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 60)
    print("Step 21 — Upsilon v2 Semantic Coverage Build")
    print("=" * 60)
    print()

    result = run_v2_study()

    # Write report
    report = render_v2_study_report(result)
    report_path = Path("results/step_21_v2_study_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport: {report_path}")

    # Write machine-readable results
    results_json = {
        "study": "v2_semantic_coverage_build",
        "generated_at": result.generated_at,
        "total_chains": result.total_chains,
        "total_amendments": result.total_amendments,
        "total_parser_instructions": result.total_parser_instructions,
        "total_mapped": result.total_mapped,
        "mapped_from_parser": result.mapped_from_parser,
        "mapped_from_extraction": result.mapped_from_extraction,
        "total_unresolved": result.total_unresolved,
        "total_incorrect_mutations": result.total_incorrect_mutations,
        "semantic_mapping_coverage": result.semantic_mapping_coverage,
        "semantic_mapping_precision": result.semantic_mapping_precision,
        "incorrect_accepted_mutation_rate": result.incorrect_accepted_mutation_rate,
        "unresolved_rate": result.unresolved_rate,
        "s0_extraction_success_rate": result.s0_extraction_success_rate,
        "gt_extraction_success_rate": result.gt_extraction_success_rate,
        "s0_extraction_coverage_avg": result.s0_extraction_coverage_avg,
        "gt_extraction_coverage_avg": result.gt_extraction_coverage_avg,
        "genre_distribution": result.genre_distribution,
        "unknown_genre_rate": result.unknown_genre_rate,
        "end_to_end_reconstruction_rate": result.end_to_end_reconstruction_rate,
        "lineage_completeness_rate": result.lineage_completeness_rate,
        "false_authoritative_promotion_rate": result.false_authoritative_promotion_rate,
        "false_authoritative_promotion_count": result.false_authoritative_promotion_count,
        "gates": result.gates,
        "per_chain": result.per_chain,
    }
    results_path = Path("results/step_21_v2_study_results.json")
    results_path.write_text(json.dumps(results_json, indent=2), encoding="utf-8")
    print(f"Results JSON: {results_path}")

    # Print summary
    print()
    print("=" * 60)
    print("V2 STUDY SUMMARY")
    print("=" * 60)
    print(f"Total chains:                  {result.total_chains}")
    print(f"Total parser instructions:     {result.total_parser_instructions}")
    print(f"Total mapped:                  {result.total_mapped}")
    print(f"  mapped from parser:          {result.mapped_from_parser}")
    print(f"  mapped from extraction:       {result.mapped_from_extraction}")
    print(f"Total unresolved:              {result.total_unresolved}")
    print(f"Total incorrect mutations:     {result.total_incorrect_mutations}")
    print(f"Semantic mapping coverage:     {result.semantic_mapping_coverage:.2%}")
    print(f"  (parser-mapped / parser instr.)")
    print(f"Semantic mapping precision:    {result.semantic_mapping_precision:.2%}")
    print(f"Incorrect mutation rate:       {result.incorrect_accepted_mutation_rate:.2%}")
    print(f"False auth promotion count:    {result.false_authoritative_promotion_count}")
    print(f"Unknown genre rate:            {result.unknown_genre_rate:.2%}")
    print()
    print("Engineering gates:")
    for gate, passed in result.gates.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {gate}: {status}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
