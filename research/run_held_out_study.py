"""Held-Out Confirmatory Study (Step 19B) — frozen-system evaluation runner.

Runs the FROZEN v1.0-operational-build system once on 25 held-out issuer
chains.  This is an EXTERNAL ORCHESTRATION LAYER that feeds held-out
inputs into the same frozen pipeline functions without modifying any
frozen code, rules, thresholds, or classifications.

FROZEN BASELINE: v1.0-frozen-operational-build

KEY CONSTRAINTS:
  - Do NOT modify frozen code.
  - Do NOT add parser/mapper/extractor rules.
  - Do NOT change thresholds or failure classifications.
  - Do NOT inspect development failures for tuning.
  - Run the frozen system ONCE on held-out chains.

This script reuses the frozen functions from run_chain_study_v2.py and
related modules, but reads from data/held_out/ instead of
data/chain_study/.  The only adaptation is the data source path.

Usage:
    python run_held_out_study.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from upsilon.lineage.chain_reconstruction import AmendmentStep, IssuerChain
from upsilon.parsing.commitment_extractor import ExtractionResult
from upsilon.evidence.gold_schema import load_gold_file
from upsilon.evidence.gt_extractor import extract_ground_truth_for_chain
from upsilon.parsing.pattern_classifier import classify_amendment
from research.run_chain_study import (
    FAILURE_CATEGORIES,
    AggregateMetrics,
    IssuerStudyResult,
    _compute_supported_field_agreement,
    _extract_cik,
    classify_failure,
    compute_aggregate_metrics,
)
from research.run_chain_study_v2 import (
    EXTRACTION_FAILURE_CATEGORIES,
    AggregateMetricsV2,
    IssuerStudyResultV2,
    _compute_extraction_status,
    classify_failure_v2,
    compute_v2_aggregate_metrics,
)
from upsilon.evidence.s0_extractor import extract_s0_state_for_chain
from upsilon.pipeline.semantic_pipeline import (
    SemanticPipelineResult,
    run_semantic_pipeline,
)

HELD_OUT_MANIFEST = Path("data/held_out/manifest.json")
HELD_OUT_DATA_DIR = Path("data/held_out")
HELD_OUT_GOLD_DIR = Path("data/held_out/gold")
RESULTS_DIR = Path("results")


# ---------------------------------------------------------------------------
# Held-out chain building (same as v2 but with held-out paths)
# ---------------------------------------------------------------------------


def _build_held_out_chain_from_manifest_entry(
    entry: dict,
) -> tuple[IssuerChain, ExtractionResult, ExtractionResult | None]:
    """Build an IssuerChain for a held-out chain with extracted S0 and GT states.

    This is the same as _build_v2_chain_from_manifest_entry in
    run_chain_study_v2.py, but uses data/held_out/ paths instead of
    data/chain_study/ paths.

    Returns (chain, s0_result, gt_result).
    gt_result is None if no CMP file exists.
    """
    chain_id = entry["chain_id"]
    cik = entry["cik"]
    issuer = entry["issuer"]
    documents = entry["documents"]

    # Extract S0 state using manifest text_path (not hardcoded path)
    s0_doc = next((d for d in documents if d["role"] == "S0"), None)
    if s0_doc is None:
        raise ValueError(f"Chain {chain_id} has no S0 document in manifest")
    s0_path = s0_doc["text_path"]
    s0_result = extract_s0_state_for_chain(chain_id, s0_path)

    # Extract GT state if CMP file exists (using manifest text_path)
    cmp_doc = next((d for d in documents if d["role"] == "CMP"), None)
    gt_result: ExtractionResult | None = None
    if cmp_doc is not None and Path(cmp_doc["text_path"]).exists():
        gt_result = extract_ground_truth_for_chain(chain_id, cmp_doc["text_path"])

    # Find amendment documents
    amendment_docs = [d for d in documents if d["role"].startswith("A")]
    amendment_docs.sort(key=lambda d: d["role"])

    # Build AmendmentStep objects (same as v2)
    amendments: list[AmendmentStep] = []
    for i, doc in enumerate(amendment_docs, 1):
        text_path = doc["text_path"]
        try:
            text = Path(text_path).read_text(encoding="utf-8", errors="ignore")
            pattern = classify_amendment(text).pattern.value if text else "unknown"
        except Exception:  # noqa: BLE001
            pattern = "unknown"
        amendments.append(AmendmentStep(
            amendment_number=i,
            effective_at=datetime.fromisoformat(doc["file_date"] + "T00:00:00"),
            description=(
                f"{doc['exhibit_description']} "
                f"(filed {doc['file_date']}, accession {doc['accession']})"
            ),
            pattern=pattern,
            parser_instruction_count=None,
            source_document_path=text_path,
            instructions=[],
        ))

    comparison_at = datetime.fromisoformat(entry["comparison_at"] + "T00:00:00")

    # Build ground-truth label
    if gt_result is not None and len(gt_result.commitments) > 0:
        gt_label = (
            f"Independently extracted from composite/conformed document "
            f"for {chain_id} (CMP.txt, {gt_result.text_length} chars). "
            f"Extracted {len(gt_result.commitments)} commitments with "
            f"{len(gt_result.validation_queue)} clauses in validation queue."
        )
    elif gt_result is not None:
        gt_label = (
            f"Composite/conformed document exists for {chain_id} "
            f"(CMP.txt, {gt_result.text_length} chars) but extraction "
            f"yielded 0 commitments. All clauses routed to validation queue."
        )
    else:
        gt_label = (
            f"No composite/conformed document available for {chain_id}. "
            f"Ground-truth extraction not possible."
        )

    return (
        IssuerChain(
            chain_id=chain_id,
            issuer_name=f"{issuer} (CIK {cik})",
            original_state=s0_result.commitments,  # extracted S0 state
            amendments=amendments,
            comparison_at=comparison_at,
            ground_truth_state=gt_result.commitments if gt_result else None,
            ground_truth_label=gt_label,
            is_synthetic=False,
        ),
        s0_result,
        gt_result,
    )


def all_held_out_chains() -> list[tuple[IssuerChain, ExtractionResult, ExtractionResult | None]]:
    """Return all 25 held-out chains with extraction results.

    Returns a list of (chain, s0_result, gt_result) tuples.
    """
    results: list[tuple[IssuerChain, ExtractionResult, ExtractionResult | None]] = []

    manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest.get("chains", []):
        chain, s0_result, gt_result = _build_held_out_chain_from_manifest_entry(entry)
        results.append((chain, s0_result, gt_result))

    return results


# ---------------------------------------------------------------------------
# Held-out per-issuer result building (reuses v2 logic)
# ---------------------------------------------------------------------------


def build_held_out_issuer_result(
    chain: IssuerChain,
    pipe_result: SemanticPipelineResult,
    s0_result: ExtractionResult,
    gt_result: ExtractionResult | None,
    manifest_entry: dict,
) -> IssuerStudyResultV2:
    """Build a per-issuer result for a held-out chain.

    Reuses the v2 result building logic but with held-out manifest data.
    """
    cik = _extract_cik(chain)

    # Build manifest entry data for the result
    s0_accession = manifest_entry.get("s0_accession", "N/A")
    amendment_accessions = manifest_entry.get("amendment_accessions", [])
    final_authoritative_source = manifest_entry.get("final_authoritative_source", "N/A")
    comparison_source_accession = manifest_entry.get("comparison_source_accession")
    comparison_source_file_date = manifest_entry.get("comparison_source_file_date")
    comparison_source_kind = manifest_entry.get("comparison_source_kind")

    has_gt = chain.ground_truth_state is not None and len(chain.ground_truth_state) > 0

    # Build steps detail
    steps_detail: list[dict[str, Any]] = []
    for step in pipe_result.steps:
        own_unresolved = (
            len(step.mapper_unresolved)
            + len(step.execution_result.unresolved)
        )
        steps_detail.append({
            "amendment_number": step.amendment_number,
            "effective_at": step.effective_at.isoformat(),
            "pattern": step.pattern,
            "parser_instruction_count": step.parser_instruction_count,
            "mapper_mutations": len(step.mapper_mutations),
            "mapper_unresolved": len(step.mapper_unresolved),
            "execution_status": step.execution_result.status.value,
            "is_authoritative": step.is_authoritative,
            "inherited_unresolved_count": step.inherited_unresolved_count,
            "own_unresolved_count": own_unresolved,
        })

    chain_authoritative = (
        len(pipe_result.steps) > 0
        and pipe_result.steps[-1].is_authoritative
    )

    lineage_complete = (
        len(pipe_result.steps) == len(chain.amendments)
        and len(pipe_result.steps) > 0
        and all(
            s.execution_result.status.value == "COMPLETE"
            for s in pipe_result.steps
        )
    )

    if has_gt:
        final_state_agreement = pipe_result.final_state_agreement
        supported_field_agreement = _compute_supported_field_agreement(
            pipe_result.reconstructed_state,
            chain.ground_truth_state,
        )
    else:
        final_state_agreement = None
        supported_field_agreement = None

    if has_gt:
        total_amendment_instructions = sum(
            len(step.instructions) for step in chain.amendments
        )
    else:
        total_amendment_instructions = -1

    # Determine GT extraction source
    is_manual = s0_result.source_label == "S0-manual"
    if is_manual:
        gt_source = "manual"
    elif gt_result is not None:
        gt_source = "CMP"
    elif chain.ground_truth_state is not None and len(chain.ground_truth_state) > 0:
        gt_source = "manual"
    else:
        gt_source = "none"

    # Compute extraction status
    extraction_status = _compute_extraction_status(
        s0_result, gt_result, is_manual,
    )

    # Classify failure using v2 extraction-aware classifier
    v2_category = classify_failure_v2(
        pipe_result, chain, has_gt, s0_result, gt_result, extraction_status,
    )

    # Build base v1 result
    base = IssuerStudyResult(
        chain_id=chain.chain_id,
        issuer_name=chain.issuer_name,
        cik=cik,
        s0_accession=s0_accession,
        amendment_accessions=amendment_accessions,
        comparison_at=chain.comparison_at.isoformat(),
        final_authoritative_source=final_authoritative_source,
        total_amendment_instructions=total_amendment_instructions,
        parser_detected_instructions=pipe_result.total_parser_instructions,
        semantic_mapped_instructions=pipe_result.total_mapped,
        unresolved_instructions=pipe_result.total_unresolved,
        incorrect_automatic_mutations=len(pipe_result.incorrect_mutations),
        chain_authoritative=chain_authoritative,
        lineage_complete=lineage_complete,
        final_state_exact_agreement=final_state_agreement,
        supported_field_agreement=supported_field_agreement,
        failure_category=v2_category,
        steps=steps_detail,
        has_ground_truth=has_gt,
        comparison_source_accession=comparison_source_accession,
        comparison_source_file_date=comparison_source_file_date,
        comparison_source_kind=comparison_source_kind,
    )

    return IssuerStudyResultV2(
        **{k: v for k, v in base.__dict__.items() if k != "failure_category"},
        s0_extraction_commitments=len(s0_result.commitments),
        s0_extraction_validation_queue=len(s0_result.validation_queue),
        s0_extraction_coverage=round(s0_result.extraction_coverage, 4),
        s0_extraction_text_length=s0_result.text_length,
        gt_extraction_commitments=len(gt_result.commitments) if gt_result else 0,
        gt_extraction_validation_queue=len(gt_result.validation_queue) if gt_result else 0,
        gt_extraction_coverage=round(gt_result.extraction_coverage, 4) if gt_result else 0.0,
        gt_extraction_text_length=gt_result.text_length if gt_result else 0,
        gt_extraction_source=gt_source,
        s0_extraction_success=len(s0_result.commitments) > 0,
        gt_extraction_success=(gt_result is not None and len(gt_result.commitments) > 0),
        extraction_status=extraction_status,
        failure_category=v2_category,
    )


# ---------------------------------------------------------------------------
# Gold-vs-reconstruction agreement
# ---------------------------------------------------------------------------


def compute_gold_agreement(
    chain_id: str,
    reconstructed_state: dict,
    gold_records: list,
) -> dict:
    """Compute agreement between reconstructed state and human gold records.

    Compares each gold record's field/value against the corresponding
    field in the reconstructed commitment state.  Gold records are
    matched to commitments by commitment_id (extracted from the gold
    record's commitment_id field, which maps to canonical_key).

    Returns a dict with:
      - chain_id
      - total_gold_records
      - matched_commitments: count of gold commitment_ids found in
        reconstructed state
      - field_comparisons: count of gold fields that could be compared
      - field_agreements: count of gold fields that matched
      - field_agreement_rate: agreements / comparisons
      - per_field: per-field breakdown
    """
    # Group gold records by commitment_id
    by_commitment: dict[str, list] = {}
    for gr in gold_records:
        by_commitment.setdefault(gr.commitment_id, []).append(gr)

    total_records = len(gold_records)
    matched_commitments = 0
    field_comparisons = 0
    field_agreements = 0
    per_field: dict[str, dict] = {}

    for cid, records in by_commitment.items():
        # Match gold commitment_id to reconstructed state by exact key.
        # Gold commitment_id is like "financial_covenant.leverage_ratio"
        # and reconstructed state keys are canonical_keys of the same form.
        # Substring matching (cid in key / key in cid) is avoided because
        # it produces false positives (e.g., "financial_covenant.debt"
        # would incorrectly match "financial_covenant.debt_service_coverage").
        commitment = reconstructed_state.get(cid)
        if commitment is None:
            continue
        matched_commitments += 1

        for gr in records:
            field_name = gr.field
            gold_value = gr.value

            # Map gold field names to CommitmentState field names
            state_value = getattr(commitment, field_name, None)
            if state_value is None and field_name == "commitment_type":
                state_value = commitment.commitment_type

            if state_value is None:
                continue

            field_comparisons += 1

            # Normalize for comparison
            if isinstance(state_value, list):
                state_norm = set(str(v).lower() for v in state_value)
            else:
                state_norm = str(state_value).lower()
            if isinstance(gold_value, list):
                gold_norm = set(str(v).lower() for v in gold_value)
            else:
                gold_norm = str(gold_value).lower()

            if state_norm == gold_norm:
                field_agreements += 1
                per_field.setdefault(field_name, {"agree": 0, "disagree": 0})
                per_field[field_name]["agree"] += 1
            else:
                per_field.setdefault(field_name, {"agree": 0, "disagree": 0})
                per_field[field_name]["disagree"] += 1

    agreement_rate = (
        field_agreements / field_comparisons
        if field_comparisons > 0
        else None
    )

    return {
        "chain_id": chain_id,
        "total_gold_records": total_records,
        "matched_commitments": matched_commitments,
        "field_comparisons": field_comparisons,
        "field_agreements": field_agreements,
        "field_agreement_rate": agreement_rate,
        "per_field": per_field,
    }


def load_gold_agreement_stats(
    chain_data: list,
    pipeline_results: list[SemanticPipelineResult],
) -> list[dict]:
    """Load gold files for preregistered chains and compute agreement.

    Returns a list of per-chain agreement dicts.  Chains without gold
    files are skipped.
    """
    stats: list[dict] = []
    for (chain, _, _), pipe_result in zip(chain_data, pipeline_results, strict=False):
        gold_path = HELD_OUT_GOLD_DIR / f"{chain.chain_id}_gold.json"
        if not gold_path.exists():
            continue
        gold_records = load_gold_file(gold_path)
        if not gold_records:
            stats.append({
                "chain_id": chain.chain_id,
                "total_gold_records": 0,
                "matched_commitments": 0,
                "field_comparisons": 0,
                "field_agreements": 0,
                "field_agreement_rate": None,
                "per_field": {},
            })
            continue
        agreement = compute_gold_agreement(
            chain.chain_id, pipe_result.reconstructed_state, gold_records,
        )
        stats.append(agreement)
    return stats


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    print("Held-Out Confirmatory Study (Step 19B)")
    print("Frozen system: v1.0-frozen-operational-build")
    print("Extractor: S0 Commitment Extractor v0.1, Authoritative GT Extractor v0.1")
    print()

    # Verify frozen baseline
    frozen_tag = "v1.0-frozen-operational-build"
    print(f"Frozen baseline: {frozen_tag}")
    print()

    # Load all 25 held-out chains with extraction results
    chain_data = all_held_out_chains()
    print(f"Loaded {len(chain_data)} held-out chains")
    for chain, s0_res, gt_res in chain_data:
        gt = "yes" if chain.ground_truth_state else "no"
        s0_count = len(chain.original_state)
        gt_count = len(chain.ground_truth_state) if chain.ground_truth_state else 0
        print(
            f"  {chain.chain_id:20s}  {chain.issuer_name[:35]:35s}  "
            f"S0={s0_count}  GT={gt}({gt_count})  amendments={len(chain.amendments)}"
        )
    print()

    # Load manifest for per-chain metadata
    manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
    manifest_by_chain_id = {c["chain_id"]: c for c in manifest["chains"]}

    # Run the frozen semantic pipeline on each chain
    print("Running frozen semantic pipeline with extracted states...")
    pipeline_results: list[SemanticPipelineResult] = []
    issuer_results: list[IssuerStudyResultV2] = []

    for i, (chain, s0_result, gt_result) in enumerate(chain_data, 1):
        print(f"  [{i}/{len(chain_data)}] {chain.chain_id}...")
        pipe_result = run_semantic_pipeline(chain)
        pipeline_results.append(pipe_result)

        manifest_entry = manifest_by_chain_id.get(chain.chain_id, {})
        issuer_result = build_held_out_issuer_result(
            chain, pipe_result, s0_result, gt_result, manifest_entry
        )
        issuer_results.append(issuer_result)

        print(
            f"    S0={len(chain.original_state)}  GT={len(chain.ground_truth_state or {})}  "
            f"parser={pipe_result.total_parser_instructions}  "
            f"mapped={pipe_result.total_mapped}  "
            f"unresolved={pipe_result.total_unresolved}  "
            f"incorrect={len(pipe_result.incorrect_mutations)}  "
            f"ext={issuer_result.extraction_status}  "
            f"category={issuer_result.failure_category}"
        )

    print()

    # Compute aggregate metrics
    metrics = compute_v2_aggregate_metrics(issuer_results, pipeline_results)

    # Compute gold-vs-reconstruction agreement for preregistered chains
    gold_agreement_stats = load_gold_agreement_stats(chain_data, pipeline_results)
    if gold_agreement_stats:
        print()
        print("Gold-vs-reconstruction agreement:")
        for gs in gold_agreement_stats:
            rate_str = (
                f"{gs['field_agreement_rate']:.1%}"
                if gs["field_agreement_rate"] is not None
                else "N/A"
            )
            print(
                f"  {gs['chain_id']}: gold_records={gs['total_gold_records']}  "
                f"matched={gs['matched_commitments']}  "
                f"comparisons={gs['field_comparisons']}  "
                f"agreements={gs['field_agreements']}  "
                f"rate={rate_str}"
            )

    # Write machine-readable results
    results_json: dict[str, Any] = {
        "study": "held_out_confirmatory_study_19b",
        "frozen_system": frozen_tag,
        "run_at": datetime.now(UTC).isoformat(),
        "total_chains": len(chain_data),
        "gold_agreement": gold_agreement_stats,
        "issuer_results": [
            {
                "chain_id": r.chain_id,
                "issuer_name": r.issuer_name,
                "cik": r.cik,
                "has_ground_truth": r.has_ground_truth,
                "gt_extraction_source": r.gt_extraction_source,
                "extraction_status": r.extraction_status,
                "s0_extraction_commitments": r.s0_extraction_commitments,
                "s0_extraction_validation_queue": r.s0_extraction_validation_queue,
                "s0_extraction_coverage": r.s0_extraction_coverage,
                "gt_extraction_commitments": r.gt_extraction_commitments,
                "gt_extraction_validation_queue": r.gt_extraction_validation_queue,
                "gt_extraction_coverage": r.gt_extraction_coverage,
                "parser_detected_instructions": r.parser_detected_instructions,
                "semantic_mapped_instructions": r.semantic_mapped_instructions,
                "unresolved_instructions": r.unresolved_instructions,
                "incorrect_automatic_mutations": r.incorrect_automatic_mutations,
                "chain_authoritative": r.chain_authoritative,
                "lineage_complete": r.lineage_complete,
                "final_state_exact_agreement": r.final_state_exact_agreement,
                "supported_field_agreement": r.supported_field_agreement,
                "failure_category": r.failure_category,
            }
            for r in issuer_results
        ],
        "aggregate_metrics": {
            "total_chains": metrics.base.total_chains,
            "total_amendments": metrics.base.total_amendments,
            "total_parser_instructions": metrics.base.total_parser_instructions,
            "total_mapped_instructions": metrics.base.total_mapped_instructions,
            "total_unresolved": metrics.base.total_unresolved,
            "total_incorrect_mutations": metrics.base.total_incorrect_mutations,
            "semantic_mapping_precision": metrics.base.semantic_mapping_precision,
            "semantic_mapping_coverage": metrics.base.semantic_mapping_coverage,
            "incorrect_automatic_mutation_rate": metrics.base.incorrect_automatic_mutation_rate,
            "unresolved_rate": metrics.base.unresolved_rate,
            "chain_level_exact_reconstruction_rate": metrics.base.chain_level_exact_reconstruction_rate,
            "lineage_completeness_rate": metrics.base.lineage_completeness_rate,
            "false_authoritative_promotion_rate": metrics.base.false_authoritative_promotion_rate,
            "false_authoritative_promotion_count": metrics.base.false_authoritative_promotion_count,
            "s0_extraction_success_rate": metrics.s0_extraction_success_rate,
            "gt_extraction_success_rate": metrics.gt_extraction_success_rate,
            "s0_extraction_coverage_avg": metrics.s0_extraction_coverage_avg,
            "gt_extraction_coverage_avg": metrics.gt_extraction_coverage_avg,
            "chains_with_extracted_s0": metrics.chains_with_extracted_s0,
            "chains_with_extracted_gt": metrics.chains_with_extracted_gt,
            "chains_with_cmp_document": metrics.chains_with_cmp_document,
            "total_s0_commitments_extracted": metrics.total_s0_commitments_extracted,
            "total_gt_commitments_extracted": metrics.total_gt_commitments_extracted,
        },
    }
    results_path = RESULTS_DIR / "held_out_study_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results_json, indent=2), encoding="utf-8")
    print(f"Results JSON: {results_path}")

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY (Held-Out Confirmatory Study)")
    print("=" * 60)
    print(f"Total chains:                  {metrics.base.total_chains}")
    print(f"S0 extraction success:         {metrics.chains_with_extracted_s0}/{len(chain_data)}")
    print(f"GT extraction success:         {metrics.chains_with_extracted_gt}/{metrics.chains_with_cmp_document}")
    print(f"False auth promotion rate:     {metrics.base.false_authoritative_promotion_rate:.1%}")
    print(f"False auth promotion count:    {metrics.base.false_authoritative_promotion_count}")
    print()

    if metrics.base.false_authoritative_promotion_count == 0:
        print("SAFETY: PASS — false authoritative promotion rate is 0")
    else:
        print(f"SAFETY: FAIL — {metrics.base.false_authoritative_promotion_count} false promotions")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
