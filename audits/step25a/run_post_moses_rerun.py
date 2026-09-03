"""Step 25A — Post-MOSES re-run of the Step 19B held-out corpus.

Runs the CURRENT production path (semantic_pipeline_v2 with the
conservation-first spine) on the same 25-chain held-out corpus used
in ``results/step_19b_held_out_confirmatory_study.md``.

This is an EVALUATION HARNESS, not runtime code.  It reuses the
held-out chain building logic from ``research/run_held_out_study.py``
but substitutes ``run_semantic_pipeline_v2`` for the legacy
``run_semantic_pipeline``.  No runtime code is modified.

Usage:
    python -m audits.step25a.run_post_moses_rerun
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from upsilon.pipeline.semantic_pipeline_v2 import (
    AuthorityDecision,
    SemanticPipelineResultV2,
    run_semantic_pipeline_v2,
)

# Reuse the held-out chain builder from the existing study runner.
from research.run_held_out_study import (
    HELD_OUT_MANIFEST,
    all_held_out_chains,
    build_held_out_issuer_result,
)
from research.run_chain_study import (
    _compute_supported_field_agreement,
)

RESULTS_DIR = Path("results")
ARTIFACT_JSON = RESULTS_DIR / "step25a_post_moses_rerun.json"


# ---------------------------------------------------------------------------
# Failure-stage classification for the v2 pipeline
# ---------------------------------------------------------------------------

FAILURE_STAGES = [
    "source_s0_acquisition",
    "s0_commitment_extraction",
    "amendment_instruction_detection",
    "amendment_classification",
    "target_identity_resolution",
    "affected_field_determination",
    "value_extraction",
    "old_value_consistency",
    "conservation_validation",
    "semantic_proof",
    "execution_staging",
    "lineage",
    "authority_gate",
    "unsupported_transformation_family",
    "true_ambiguity",
    "evaluation_gold_unavailable",
]


def classify_failure_stage_v2(
    chain,
    pipe_result: SemanticPipelineResultV2,
    s0_result,
    gt_result,
) -> str:
    """Classify the primary failure stage for a chain under the v2 pipeline.

    Assigns each chain to the FIRST meaningful failure stage.  A chain
    with no measurable failure is classified as ``system_ingestion_pass``
    (not a failure stage, but recorded for the census).
    """
    s0_count = len(s0_result.commitments) if s0_result else 0
    has_gt = gt_result is not None and len(gt_result.commitments) > 0
    parser_count = pipe_result.total_parser_instructions
    mapped = pipe_result.total_mapped
    unresolved = pipe_result.total_unresolved
    incorrect = len(pipe_result.incorrect_mutations)
    spine_promoted = pipe_result.spine_total_promoted
    spine_rejected = pipe_result.spine_total_rejected
    spine_routed = pipe_result.spine_total_routed_away

    # S0 extraction failure
    if s0_count == 0:
        return "s0_commitment_extraction"

    # Parser found no instructions
    if parser_count == 0:
        return "amendment_instruction_detection"

    # All unresolved — mapper could not resolve any instruction
    if mapped == 0 and unresolved > 0:
        return "target_identity_resolution"

    # Spine rejected everything it tried, and legacy mapped nothing
    if (spine_promoted == 0 and spine_rejected > 0
            and mapped == spine_rejected + spine_routed):
        return "conservation_validation"

    # Has mapped but all incorrect (and has GT to measure against)
    if has_gt and incorrect > 0 and incorrect >= mapped:
        return "value_extraction"

    # No GT to measure against
    if not has_gt:
        return "evaluation_gold_unavailable"

    # No failures detected
    return "system_ingestion_pass"


# ---------------------------------------------------------------------------
# Metric collection
# ---------------------------------------------------------------------------


def _safe_div(num: int, denom: int) -> float:
    return round(num / denom, 4) if denom > 0 else 0.0


def collect_metrics(
    chain_data: list,
    pipeline_results: list[SemanticPipelineResultV2],
    s0_results: list,
    gt_results: list,
    manifest: dict,
) -> dict[str, Any]:
    """Collect all Step 25A metrics from the v2 pipeline results."""

    total_chains = len(chain_data)
    total_amendments = sum(len(c.amendments) for c, _, _ in chain_data)
    total_documents = sum(
        len(m_entry.get("documents", []))
        for m_entry in manifest.get("chains", [])
    )
    cmp_chains = [
        i for i, (_, _, gt) in enumerate(chain_data) if gt is not None
    ]
    cmp_count = len(cmp_chains)

    # --- S0 extraction ---
    s0_success_chains = [
        i for i, sr in enumerate(s0_results) if sr and len(sr.commitments) > 0
    ]
    s0_success_count = len(s0_success_chains)
    s0_total_commitments = sum(
        len(sr.commitments) for sr in s0_results if sr
    )
    s0_coverages = [
        sr.extraction_coverage for sr in s0_results if sr
    ]
    s0_avg_coverage = round(
        sum(s0_coverages) / len(s0_coverages), 4
    ) if s0_coverages else 0.0

    # --- GT extraction ---
    gt_success_chains = [
        i for i, gr in enumerate(gt_results)
        if gr is not None and len(gr.commitments) > 0
    ]
    gt_success_count = len(gt_success_chains)
    gt_total_commitments = sum(
        len(gr.commitments) for gr in gt_results if gr
    )
    gt_coverages = [
        gr.extraction_coverage for gr in gt_results if gr
    ]
    gt_avg_coverage = round(
        sum(gt_coverages) / len(gt_coverages), 4
    ) if gt_coverages else 0.0

    # --- Parser ---
    total_parser_instructions = sum(
        pr.total_parser_instructions for pr in pipeline_results
    )
    # Amendments with >=1 parser instruction
    amendments_with_instructions = 0
    for pr in pipeline_results:
        for step in pr.steps:
            if step.parser_instruction_count > 0:
                amendments_with_instructions += 1

    # --- Semantic mapping ---
    total_mapped = sum(pr.total_mapped for pr in pipeline_results)
    total_mapped_from_parser = sum(
        pr.mapped_from_parser for pr in pipeline_results
    )
    total_mapped_from_extraction = sum(
        pr.mapped_from_extraction for pr in pipeline_results
    )
    total_unresolved = sum(pr.total_unresolved for pr in pipeline_results)

    # Mapping coverage = mapped_from_parser / total_parser_instructions
    mapping_coverage = _safe_div(
        total_mapped_from_parser, total_parser_instructions
    )
    # Unresolved rate = total_unresolved / total_parser_instructions
    unresolved_rate = _safe_div(total_unresolved, total_parser_instructions)

    # --- MOSES spine ---
    spine_total_promoted = sum(
        pr.spine_total_promoted for pr in pipeline_results
    )
    spine_total_rejected = sum(
        pr.spine_total_rejected for pr in pipeline_results
    )
    spine_total_routed_away = sum(
        pr.spine_total_routed_away for pr in pipeline_results
    )

    # --- Safety ---
    total_incorrect = sum(
        len(pr.incorrect_mutations) for pr in pipeline_results
    )
    total_accepted = total_mapped  # all mapped mutations are "accepted"
    incorrect_rate = _safe_div(total_incorrect, total_accepted)
    false_auth_promotions = sum(
        pr.false_authoritative_promotions for pr in pipeline_results
    )
    false_auth_rate = _safe_div(false_auth_promotions, total_chains)

    # Authority outcomes
    authority_granted = 0
    authority_blocked = 0
    validation_required = 0
    unresolved_authority = 0
    partial_authority = 0
    for pr in pipeline_results:
        for step in pr.steps:
            # Reconstruct authority decision from is_authoritative + unresolved
            if step.is_authoritative:
                authority_granted += 1
            elif step.unresolved_count > 0 or step.execution_result.unresolved:
                unresolved_authority += 1
            elif step.spine_rejected > 0:
                authority_blocked += 1
            else:
                authority_blocked += 1

    # --- Reconstruction (GT chains only) ---
    gt_chain_indices = [
        i for i, (chain, _, _) in enumerate(chain_data)
        if chain.ground_truth_state and len(chain.ground_truth_state) > 0
    ]
    gt_chain_count = len(gt_chain_indices)

    supported_field_agreements = 0
    whole_commitment_agreements = 0
    exact_chain_reconstructions = 0

    for i in gt_chain_indices:
        chain = chain_data[i][0]
        pr = pipeline_results[i]
        gt = chain.ground_truth_state

        # Whole-commitment agreement: all GT commitments match exactly
        all_match = True
        for key, gt_comm in gt.items():
            recon = pr.reconstructed_state.get(key)
            if recon is None:
                all_match = False
                break
            # Compare key fields
            for fname in ("threshold", "rate", "party", "exceptions",
                          "applicability", "status", "unit"):
                if getattr(recon, fname, None) != getattr(gt_comm, fname, None):
                    all_match = False
                    break
            if not all_match:
                break
        if all_match:
            whole_commitment_agreements += 1
            exact_chain_reconstructions += 1

        # Supported-field agreement
        sfa = _compute_supported_field_agreement(
            pr.reconstructed_state, gt
        )
        if sfa is not None and sfa >= 1.0:
            supported_field_agreements += 1

    # Exact reconstruction overall: (GT chains with exact agreement) /
    # (total chains).  This matches the Step 19B definition where only
    # GT-measurable chains can be "exact" and the denominator is all
    # chains.  Non-GT chains cannot be verified as exact.
    exact_overall = exact_chain_reconstructions

    # --- Lineage ---
    # Match Step 19B definition: lineage_complete = all amendment steps
    # were processed AND all steps have COMPLETE execution status.
    lineage_complete = 0
    lineage_incomplete = 0
    for i, (chain, _, _) in enumerate(chain_data):
        pr = pipeline_results[i]
        if (len(pr.steps) == len(chain.amendments)
                and len(pr.steps) > 0
                and all(
                    s.execution_result.status.value == "COMPLETE"
                    for s in pr.steps
                )):
            lineage_complete += 1
        else:
            lineage_incomplete += 1
    lineage_completeness = _safe_div(lineage_complete, total_chains)

    # --- Failure-stage census ---
    failure_stages: dict[str, int] = {}
    per_chain: list[dict] = []
    for i, (chain, s0_res, gt_res) in enumerate(chain_data):
        pr = pipeline_results[i]
        stage = classify_failure_stage_v2(chain, pr, s0_res, gt_res)
        failure_stages[stage] = failure_stages.get(stage, 0) + 1

        # Lineage complete per chain (Step 19B definition)
        chain_lineage = (
            len(pr.steps) == len(chain.amendments)
            and len(pr.steps) > 0
            and all(
                s.execution_result.status.value == "COMPLETE"
                for s in pr.steps
            )
        )

        per_chain.append({
            "chain_id": chain.chain_id,
            "issuer_name": chain.issuer_name,
            "s0_commitments": len(chain.original_state),
            "has_gt": bool(chain.ground_truth_state),
            "gt_commitments": len(chain.ground_truth_state or {}),
            "amendments": len(chain.amendments),
            "parser_instructions": pr.total_parser_instructions,
            "mapped": pr.total_mapped,
            "mapped_from_parser": pr.mapped_from_parser,
            "mapped_from_extraction": pr.mapped_from_extraction,
            "unresolved": pr.total_unresolved,
            "incorrect_mutations": len(pr.incorrect_mutations),
            "spine_promoted": pr.spine_total_promoted,
            "spine_rejected": pr.spine_total_rejected,
            "spine_routed_away": pr.spine_total_routed_away,
            "false_authoritative_promotions": pr.false_authoritative_promotions,
            "final_state_agreement": pr.final_state_agreement,
            "lineage_complete": chain_lineage,
            "failure_stage": stage,
        })

    return {
        # Corpus
        "chains_attempted": total_chains,
        "chains_completed": total_chains,
        "amendments": total_amendments,
        "documents": total_documents,
        "cmp_documents": cmp_count,
        # S0 extraction
        "s0_documents_found": total_chains,
        "s0_extraction_attempted": total_chains,
        "s0_extraction_success": s0_success_count,
        "s0_extraction_success_rate": _safe_div(s0_success_count, total_chains),
        "total_s0_commitments_extracted": s0_total_commitments,
        "s0_avg_coverage": s0_avg_coverage,
        # GT extraction
        "gt_extraction_attempted": cmp_count,
        "gt_extraction_success": gt_success_count,
        "gt_extraction_success_rate": _safe_div(gt_success_count, cmp_count),
        "total_gt_commitments_extracted": gt_total_commitments,
        "gt_avg_coverage": gt_avg_coverage,
        # Parser
        "amendment_documents": total_amendments,
        "total_parser_instructions": total_parser_instructions,
        "amendments_with_instructions": amendments_with_instructions,
        "instruction_detection_rate": _safe_div(
            amendments_with_instructions, total_amendments
        ),
        # Semantic mapping
        "instructions_to_semantic": total_parser_instructions,
        "mapped_resolved": total_mapped,
        "mapped_from_parser": total_mapped_from_parser,
        "mapped_from_extraction": total_mapped_from_extraction,
        "unresolved": total_unresolved,
        "semantic_mapping_coverage": mapping_coverage,
        "unresolved_rate": unresolved_rate,
        # Mapping precision: (mapped - incorrect) / mapped, where
        # incorrect is counted only on chains with GT (measurable).
        # This matches the Step 19B definition where mapping precision
        # = correct_automatic_mappings / total_automatic_mappings.
        "mapping_precision": _safe_div(
            total_mapped - total_incorrect, total_mapped
        ),
        # MOSES spine
        "moses_spine_promoted": spine_total_promoted,
        "moses_spine_rejected": spine_total_rejected,
        "moses_spine_routed_away": spine_total_routed_away,
        "legacy_path_resolutions": total_mapped_from_extraction,
        # Safety
        "incorrect_accepted_mutations": total_incorrect,
        "total_accepted_mutations": total_accepted,
        "incorrect_accepted_mutation_rate": incorrect_rate,
        "false_authoritative_promotions": false_auth_promotions,
        "false_authoritative_promotion_rate": false_auth_rate,
        "authority_granted_steps": authority_granted,
        "authority_blocked_steps": authority_blocked,
        "validation_required_steps": validation_required,
        "unresolved_authority_steps": unresolved_authority,
        # Reconstruction
        "gt_chains": gt_chain_count,
        "supported_field_gt_agreement": supported_field_agreements,
        "supported_field_gt_agreement_rate": _safe_div(
            supported_field_agreements, gt_chain_count
        ),
        "whole_commitment_gt_agreement": whole_commitment_agreements,
        "whole_commitment_gt_agreement_rate": _safe_div(
            whole_commitment_agreements, gt_chain_count
        ),
        "exact_gt_chain_reconstruction": exact_chain_reconstructions,
        "exact_gt_chain_reconstruction_rate": _safe_div(
            exact_chain_reconstructions, gt_chain_count
        ),
        "exact_reconstruction_overall": exact_overall,
        "exact_reconstruction_overall_rate": _safe_div(
            exact_overall, total_chains
        ),
        # Lineage
        "lineage_complete": lineage_complete,
        "lineage_incomplete": lineage_incomplete,
        "lineage_completeness": lineage_completeness,
        # Failure stages
        "failure_stage_census": failure_stages,
        # Per-chain detail
        "per_chain": per_chain,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Step 25A — Post-MOSES Re-Run of Step 19B Corpus")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print()

    # --- Phase 1: Lock the evaluation ---
    import subprocess
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], text=True
    ).strip()

    manifest_bytes = HELD_OUT_MANIFEST.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)

    print(f"Branch: {branch}")
    print(f"Commit: {commit}")
    print(f"Corpus manifest: {HELD_OUT_MANIFEST}")
    print(f"Corpus manifest SHA-256: {manifest_hash}")
    print(f"Chains: {len(manifest['chains'])}")
    print()

    # --- Phase 2: Run the current system ---
    print("Loading held-out chains...")
    chain_data = all_held_out_chains()
    print(f"Loaded {len(chain_data)} chains")
    print()

    print("Running current v2 pipeline (semantic_pipeline_v2)...")
    pipeline_results: list[SemanticPipelineResultV2] = []
    s0_results = []
    gt_results = []

    manifest_by_id = {c["chain_id"]: c for c in manifest["chains"]}

    for i, (chain, s0_result, gt_result) in enumerate(chain_data, 1):
        print(f"  [{i}/{len(chain_data)}] {chain.chain_id}...", end=" ")
        pr = run_semantic_pipeline_v2(chain)
        pipeline_results.append(pr)
        s0_results.append(s0_result)
        gt_results.append(gt_result)

        print(
            f"S0={len(chain.original_state)} "
            f"GT={len(chain.ground_truth_state or {})} "
            f"parser={pr.total_parser_instructions} "
            f"mapped={pr.total_mapped} "
            f"unresolved={pr.total_unresolved} "
            f"incorrect={len(pr.incorrect_mutations)} "
            f"spine(P/R/A)={pr.spine_total_promoted}/"
            f"{pr.spine_total_rejected}/{pr.spine_total_routed_away} "
            f"false_auth={pr.false_authoritative_promotions}"
        )

    print()

    # --- Phase 3: Collect metrics ---
    metrics = collect_metrics(
        chain_data, pipeline_results, s0_results, gt_results, manifest
    )

    # Print summary
    print("=" * 60)
    print("SUMMARY (Step 25A — Post-MOSES Re-Run)")
    print("=" * 60)
    print(f"Chains:                        {metrics['chains_attempted']}")
    print(f"Amendments:                    {metrics['amendments']}")
    print(f"Documents:                     {metrics['documents']}")
    print(f"CMP documents:                 {metrics['cmp_documents']}")
    print()
    print(f"S0 extraction success:         {metrics['s0_extraction_success']}/{metrics['chains_attempted']} = {metrics['s0_extraction_success_rate']:.2%}")
    print(f"S0 avg coverage:               {metrics['s0_avg_coverage']:.2%}")
    print(f"GT extraction success:         {metrics['gt_extraction_success']}/{metrics['gt_extraction_attempted']} = {metrics['gt_extraction_success_rate']:.2%}")
    print()
    print(f"Parser instructions:           {metrics['total_parser_instructions']}")
    print(f"Amendments with instructions:  {metrics['amendments_with_instructions']}/{metrics['amendments']} = {metrics['instruction_detection_rate']:.2%}")
    print(f"Semantic mapped:               {metrics['mapped_resolved']}")
    print(f"  from parser:                 {metrics['mapped_from_parser']}")
    print(f"  from extraction:             {metrics['mapped_from_extraction']}")
    print(f"Unresolved:                    {metrics['unresolved']}")
    print(f"Mapping coverage:              {metrics['semantic_mapping_coverage']:.2%}")
    print(f"Unresolved rate:               {metrics['unresolved_rate']:.2%}")
    print()
    print(f"MOSES spine promoted:          {metrics['moses_spine_promoted']}")
    print(f"MOSES spine rejected:          {metrics['moses_spine_rejected']}")
    print(f"MOSES spine routed away:       {metrics['moses_spine_routed_away']}")
    print()
    print(f"Incorrect accepted mutations:  {metrics['incorrect_accepted_mutations']}")
    print(f"Total accepted mutations:      {metrics['total_accepted_mutations']}")
    print(f"Incorrect mutation rate:       {metrics['incorrect_accepted_mutation_rate']:.2%}")
    print(f"False auth promotions:         {metrics['false_authoritative_promotions']}")
    print(f"False auth promotion rate:     {metrics['false_authoritative_promotion_rate']:.2%}")
    print()
    print(f"GT chains:                     {metrics['gt_chains']}")
    print(f"Supported-field GT agreement:  {metrics['supported_field_gt_agreement']}/{metrics['gt_chains']} = {metrics['supported_field_gt_agreement_rate']:.2%}")
    print(f"Whole-commitment GT agreement: {metrics['whole_commitment_gt_agreement']}/{metrics['gt_chains']} = {metrics['whole_commitment_gt_agreement_rate']:.2%}")
    print(f"Exact GT-chain reconstruction: {metrics['exact_gt_chain_reconstruction']}/{metrics['gt_chains']} = {metrics['exact_gt_chain_reconstruction_rate']:.2%}")
    print(f"Exact reconstruction overall:  {metrics['exact_reconstruction_overall']}/{metrics['chains_attempted']} = {metrics['exact_reconstruction_overall_rate']:.2%}")
    print()
    print(f"Lineage completeness:          {metrics['lineage_complete']}/{metrics['chains_attempted']} = {metrics['lineage_completeness']:.2%}")
    print()
    print("Failure-stage census:")
    for stage, count in sorted(
        metrics["failure_stage_census"].items(),
        key=lambda x: -x[1]
    ):
        pct = count / metrics["chains_attempted"] * 100
        print(f"  {stage:40s}  {count:3d}  ({pct:.1f}%)")
    print()

    # --- Phase 6: Write artifacts ---
    artifact: dict[str, Any] = {
        "study": "step25a_post_moses_rerun",
        "label": "POST-MOSES RE-RUN / FIXED REGRESSION CORPUS",
        "run_at": datetime.now(UTC).isoformat(),
        "branch": branch,
        "commit": commit,
        "corpus_manifest_path": str(HELD_OUT_MANIFEST),
        "corpus_manifest_sha256": manifest_hash,
        "frozen_gt_manifest_sha256": hashlib.sha256(
            Path("data/ground_truth/frozen/manifest.json").read_bytes()
        ).hexdigest(),
        "pipeline": "run_semantic_pipeline_v2",
        "runtime_path": (
            "raw EDGAR -> parser -> semantic_mapper (StructuredMutation) "
            "-> mutation_to_evidence -> S0-established identity "
            "-> AuthorizedTransformationEngine -> delta -> candidate "
            "-> conservation -> proof (pre-execution) "
            "-> KernelStore.stage (provisional) -> lineage "
            "-> ProofAssembler.update_post_execution -> AuthorityGate "
            "-> promote/discard"
        ),
        "metrics": metrics,
    }

    ARTIFACT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_JSON.write_text(
        json.dumps(artifact, indent=2, default=str), encoding="utf-8"
    )
    print(f"Artifact JSON: {ARTIFACT_JSON}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
