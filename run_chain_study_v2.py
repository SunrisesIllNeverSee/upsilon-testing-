"""Development Chain Study v2 — measurement-loop report generator.

Runs the FROZEN semantic-mapper-v0.1 system across 25 real EDGAR
issuer chains, but this time with:

  1. S0 Commitment Extractor v0.1 — extracts origin state from S0
     documents (replaces the empty original_state from v1)
  2. Authoritative GT Extractor v0.1 — extracts ground truth from
     composite/conformed documents (replaces the None ground_truth_state
     from v1)

Both extractors use the shared commitment extraction engine
(commitment_extractor.extract_commitments). The frozen semantic
mapper, parser, executor, authority, lineage, and persistence
components are NOT modified.

CRITICAL: prediction path != validation path.
  - S0 extraction feeds the reconstruction pipeline (origin state)
  - GT extraction feeds the comparison (ground truth state)
  - Neither uses amendment reconstruction output to construct the other

Usage:
    python run_chain_study_v2.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chain_reconstruction import AmendmentStep, IssuerChain
from chain_study_chains import existing_study_chains, new_study_chains
from commitment_extractor import ExtractionResult
from gt_extractor import extract_ground_truth_for_chain
from s0_extractor import extract_s0_state_for_chain
from semantic_pipeline import (
    SemanticPipelineResult,
    run_semantic_pipeline,
)

# Reuse v1 infrastructure for failure classification and metrics
from run_chain_study import (
    AggregateMetrics,
    FAILURE_CATEGORIES,
    IssuerStudyResult,
    _compute_supported_field_agreement,
    _extract_cik,
    _get_chain_manifest_entry,
    classify_failure,
    compute_aggregate_metrics,
)


# ---------------------------------------------------------------------------
# v2 per-issuer result (extends v1 with extraction metadata)
# ---------------------------------------------------------------------------


@dataclass
class IssuerStudyResultV2(IssuerStudyResult):
    """Per-issuer capture for Development Chain Study v2.

    Extends v1 with S0 and GT extraction metadata.
    """

    # S0 extraction metadata
    s0_extraction_commitments: int = 0
    s0_extraction_validation_queue: int = 0
    s0_extraction_coverage: float = 0.0
    s0_extraction_text_length: int = 0

    # GT extraction metadata
    gt_extraction_commitments: int = 0
    gt_extraction_validation_queue: int = 0
    gt_extraction_coverage: float = 0.0
    gt_extraction_text_length: int = 0
    gt_extraction_source: str = ""  # "CMP" or "manual" or "none"

    # v2-specific metrics
    s0_extraction_success: bool = False  # at least 1 commitment extracted
    gt_extraction_success: bool = False  # at least 1 commitment extracted


# ---------------------------------------------------------------------------
# Chain building with extracted S0 and GT states
# ---------------------------------------------------------------------------


def _build_v2_chain_from_manifest_entry(
    entry: dict,
) -> tuple[IssuerChain, ExtractionResult, ExtractionResult | None]:
    """Build an IssuerChain for v2 with extracted S0 and GT states.

    Returns (chain, s0_result, gt_result).
    gt_result is None if no CMP file exists.
    """
    chain_id = entry["chain_id"]
    cik = entry["cik"]
    issuer = entry["issuer"]
    documents = entry["documents"]

    # Extract S0 state
    s0_path = f"data/chain_study/{chain_id}/S0.txt"
    s0_result = extract_s0_state_for_chain(chain_id, s0_path)

    # Extract GT state if CMP file exists
    cmp_path = f"data/chain_study/{chain_id}/CMP.txt"
    gt_result: ExtractionResult | None = None
    if Path(cmp_path).exists():
        gt_result = extract_ground_truth_for_chain(chain_id, cmp_path)

    # Find amendment documents
    amendment_docs = [d for d in documents if d["role"].startswith("A")]
    amendment_docs.sort(key=lambda d: d["role"])

    # Build AmendmentStep objects (same as v1)
    from pattern_classifier import classify_amendment
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


def all_v2_chains() -> list[tuple[IssuerChain, ExtractionResult, ExtractionResult | None]]:
    """Return all 25 chains for v2 with extraction results.

    Returns a list of (chain, s0_result, gt_result) tuples.
    """
    results: list[tuple[IssuerChain, ExtractionResult, ExtractionResult | None]] = []

    # Existing chains (Ameresco, Amedisys, Bausch-Lomb) — keep hand-extracted
    # states from edgar_chains.py. These are the v1 fixtures with
    # hand-extracted ground truth that serve as the validation baseline.
    for chain in existing_study_chains():
        # Create empty extraction results for existing chains
        # (they use hand-extracted states, not the v0.1 extractors)
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
        results.append((chain, s0_result, gt_result))

    # New chains — use v0.1 extractors
    manifest_path = Path("data/chain_study/manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("chains", []):
            chain, s0_result, gt_result = _build_v2_chain_from_manifest_entry(entry)
            results.append((chain, s0_result, gt_result))

    return results


# ---------------------------------------------------------------------------
# v2 per-issuer result extraction
# ---------------------------------------------------------------------------


def build_v2_issuer_result(
    chain: IssuerChain,
    pipe_result: SemanticPipelineResult,
    s0_result: ExtractionResult,
    gt_result: ExtractionResult | None,
) -> IssuerStudyResultV2:
    """Build a per-issuer result for v2 with extraction metadata."""
    # Build the base v1 result
    base = _build_v1_base_result(chain, pipe_result)

    # Determine GT extraction source
    # Existing chains use hand-extracted ground truth (source_label="CMP-manual")
    # New chains use the v0.1 GT extractor (source_label="CMP")
    if s0_result.source_label == "S0-manual":
        # Existing chain — hand-extracted ground truth
        gt_source = "manual"
    elif gt_result is not None:
        gt_source = "CMP"
    elif chain.ground_truth_state is not None and len(chain.ground_truth_state) > 0:
        gt_source = "manual"
    else:
        gt_source = "none"

    return IssuerStudyResultV2(
        **base.__dict__,
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
    )


def _build_v1_base_result(
    chain: IssuerChain,
    pipe_result: SemanticPipelineResult,
) -> IssuerStudyResult:
    """Build a v1 IssuerStudyResult (reuses v1 logic)."""
    cik = _extract_cik(chain)
    manifest_entry = _get_chain_manifest_entry(cik)

    has_gt = chain.ground_truth_state is not None and len(chain.ground_truth_state) > 0

    if manifest_entry:
        s0_accession = manifest_entry["s0_accession"]
        amendment_accessions = manifest_entry["amendment_accessions"]
        final_authoritative_source = manifest_entry["final_authoritative_source"]
        comparison_source_accession = manifest_entry.get("comparison_source_accession")
        comparison_source_file_date = manifest_entry.get("comparison_source_file_date")
        comparison_source_kind = manifest_entry.get("comparison_source_kind")
    else:
        s0_accession = "N/A (existing fixture)"
        amendment_accessions = [f"A{step.amendment_number}" for step in chain.amendments]
        final_authoritative_source = "manually_extracted_ground_truth"
        comparison_source_accession = None
        comparison_source_file_date = None
        comparison_source_kind = None

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

    failure_category = classify_failure(pipe_result, chain, has_gt)

    return IssuerStudyResult(
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
        failure_category=failure_category,
        steps=steps_detail,
        has_ground_truth=has_gt,
        comparison_source_accession=comparison_source_accession,
        comparison_source_file_date=comparison_source_file_date,
        comparison_source_kind=comparison_source_kind,
    )


# ---------------------------------------------------------------------------
# v2 aggregate metrics (extends v1 with extraction metrics)
# ---------------------------------------------------------------------------


@dataclass
class AggregateMetricsV2:
    """Aggregate study metrics for v2."""

    # Base v1 metrics
    base: AggregateMetrics

    # v2 extraction metrics
    s0_extraction_success_rate: float
    gt_extraction_success_rate: float
    s0_extraction_coverage_avg: float
    gt_extraction_coverage_avg: float
    chains_with_extracted_s0: int
    chains_with_extracted_gt: int
    chains_with_cmp_document: int
    total_s0_commitments_extracted: int
    total_gt_commitments_extracted: int
    total_s0_validation_queue: int
    total_gt_validation_queue: int


def compute_v2_aggregate_metrics(
    issuer_results: list[IssuerStudyResultV2],
    pipeline_results: list[SemanticPipelineResult],
) -> AggregateMetricsV2:
    """Compute v2 aggregate metrics."""
    base = compute_aggregate_metrics(issuer_results, pipeline_results)

    total = len(issuer_results)
    new_chains = [r for r in issuer_results if r.gt_extraction_source != "manual"]

    s0_success = sum(1 for r in new_chains if r.s0_extraction_success)
    gt_success = sum(1 for r in new_chains if r.gt_extraction_success)
    cmp_count = sum(1 for r in new_chains if r.gt_extraction_source == "CMP")

    s0_cov_avg = (
        sum(r.s0_extraction_coverage for r in new_chains) / len(new_chains)
        if new_chains else 0.0
    )
    gt_cov_avg = (
        sum(r.gt_extraction_coverage for r in new_chains if r.gt_extraction_source == "CMP")
        / max(1, sum(1 for r in new_chains if r.gt_extraction_source == "CMP"))
    )

    total_s0 = sum(r.s0_extraction_commitments for r in new_chains)
    total_gt = sum(r.gt_extraction_commitments for r in new_chains)
    total_s0_vq = sum(r.s0_extraction_validation_queue for r in new_chains)
    total_gt_vq = sum(r.gt_extraction_validation_queue for r in new_chains)

    return AggregateMetricsV2(
        base=base,
        s0_extraction_success_rate=round(s0_success / len(new_chains), 4) if new_chains else 0.0,
        gt_extraction_success_rate=round(gt_success / max(1, cmp_count), 4) if cmp_count else 0.0,
        s0_extraction_coverage_avg=round(s0_cov_avg, 4),
        gt_extraction_coverage_avg=round(gt_cov_avg, 4),
        chains_with_extracted_s0=s0_success,
        chains_with_extracted_gt=gt_success,
        chains_with_cmp_document=cmp_count,
        total_s0_commitments_extracted=total_s0,
        total_gt_commitments_extracted=total_gt,
        total_s0_validation_queue=total_s0_vq,
        total_gt_validation_queue=total_gt_vq,
    )


# ---------------------------------------------------------------------------
# v2 report generation
# ---------------------------------------------------------------------------


def render_v2_study_report(
    issuer_results: list[IssuerStudyResultV2],
    pipeline_results: list[SemanticPipelineResult],
    metrics: AggregateMetricsV2,
) -> str:
    """Render the complete v2 study report."""
    lines: list[str] = []
    b = metrics.base

    lines.append("# Development Chain Study v2 — Measurement-Loop Report")
    lines.append("")
    lines.append("**Frozen system: semantic-mapper-v0.1 (tag: semantic-mapper-v0.1)**")
    lines.append("**New components: S0 Commitment Extractor v0.1, Authoritative GT Extractor v0.1**")
    lines.append("")
    lines.append("## Study Protocol")
    lines.append("")
    lines.append("```text")
    lines.append("S0 legal document")
    lines.append("  → automated origin-state extraction (S0 Extractor v0.1)")
    lines.append("  → structured initial commitment state")
    lines.append("  → amendment parser / semantic mapper / executor / lineage")
    lines.append("  → reconstructed final state")
    lines.append("  → independent authoritative ground-truth extraction (GT Extractor v0.1)")
    lines.append("  → exact comparison")
    lines.append("```")
    lines.append("")
    lines.append("### Key principle: prediction path != validation path")
    lines.append("")
    lines.append("The S0 extractor feeds the reconstruction pipeline (origin state).")
    lines.append("The GT extractor feeds the comparison (ground truth state).")
    lines.append("Both use the same deterministic extraction engine but process")
    lines.append("different documents. Neither uses amendment reconstruction output")
    lines.append("to construct the other.")
    lines.append("")

    # --- Extraction summary ---
    lines.append("## Extraction Summary")
    lines.append("")
    lines.append("```text")
    lines.append(f"Chains with extracted S0 state:    {metrics.chains_with_extracted_s0}/{len(issuer_results) - 3}")
    lines.append(f"Chains with CMP document:          {metrics.chains_with_cmp_document}/{len(issuer_results) - 3}")
    lines.append(f"Chains with extracted GT state:    {metrics.chains_with_extracted_gt}/{metrics.chains_with_cmp_document}")
    lines.append(f"Total S0 commitments extracted:    {metrics.total_s0_commitments_extracted}")
    lines.append(f"Total GT commitments extracted:    {metrics.total_gt_commitments_extracted}")
    lines.append(f"Total S0 validation queue items:   {metrics.total_s0_validation_queue}")
    lines.append(f"Total GT validation queue items:   {metrics.total_gt_validation_queue}")
    lines.append(f"S0 extraction success rate:        {metrics.s0_extraction_success_rate:.1%}")
    lines.append(f"GT extraction success rate:        {metrics.gt_extraction_success_rate:.1%}")
    lines.append(f"S0 extraction coverage (avg):      {metrics.s0_extraction_coverage_avg:.1%}")
    lines.append(f"GT extraction coverage (avg):      {metrics.gt_extraction_coverage_avg:.1%}")
    lines.append("```")
    lines.append("")

    # --- Per-issuer results ---
    lines.append("## Per-Issuer Results")
    lines.append("")
    lines.append("```text")
    for r in issuer_results:
        gt_label = "yes" if r.has_ground_truth else "no"
        final_agree = (
            f"{r.final_state_exact_agreement:.1%}"
            if r.final_state_exact_agreement is not None
            else "N/A"
        )
        field_agree = (
            f"{r.supported_field_agreement:.1%}"
            if r.supported_field_agreement is not None
            else "N/A"
        )
        lines.append(f"{r.chain_id}  {r.issuer_name[:40]:40s}")
        lines.append(f"  has ground truth:         {gt_label} (source: {r.gt_extraction_source})")
        lines.append(f"  S0 extracted commitments: {r.s0_extraction_commitments} (coverage: {r.s0_extraction_coverage:.1%})")
        lines.append(f"  GT extracted commitments: {r.gt_extraction_commitments} (coverage: {r.gt_extraction_coverage:.1%})")
        lines.append(f"  parser-detected instr:    {r.parser_detected_instructions}")
        lines.append(f"  semantic-mapped instr:    {r.semantic_mapped_instructions}")
        lines.append(f"  UNRESOLVED instr:         {r.unresolved_instructions}")
        lines.append(f"  incorrect auto mutations: {r.incorrect_automatic_mutations}")
        lines.append(f"  chain authoritative?      {'yes' if r.chain_authoritative else 'no'}")
        lines.append(f"  lineage complete?         {'yes' if r.lineage_complete else 'no'}")
        lines.append(f"  final-state exact agree:  {final_agree}")
        lines.append(f"  supported-field agree:    {field_agree}")
        lines.append(f"  failure category:         {r.failure_category}")
        lines.append("")

    lines.append("```")
    lines.append("")

    # --- Aggregate metrics ---
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append("```text")
    lines.append(f"Total chains:                      {b.total_chains}")
    lines.append(f"Total amendments:                  {b.total_amendments}")
    lines.append(f"Total parser instructions:         {b.total_parser_instructions}")
    lines.append(f"Total semantic-mapped:             {b.total_mapped_instructions}")
    lines.append(f"Total UNRESOLVED:                  {b.total_unresolved}")
    lines.append(f"Total incorrect mutations:         {b.total_incorrect_mutations}")
    lines.append("")

    recon = (
        f"{b.chain_level_exact_reconstruction_rate:.1%}"
        if b.chain_level_exact_reconstruction_rate is not None
        else "N/A"
    )

    lines.append("Primary study metrics:")
    lines.append("")
    lines.append(f"  Semantic mapping precision:        {b.semantic_mapping_precision:.1%}")
    lines.append(f"  Semantic mapping coverage:         {b.semantic_mapping_coverage:.1%}")
    lines.append(f"  Incorrect automatic mutation rate: {b.incorrect_automatic_mutation_rate:.1%}")
    lines.append(f"  UNRESOLVED rate:                   {b.unresolved_rate:.1%}")
    lines.append(f"  Chain-level exact reconstruction:  {recon}")
    lines.append(f"  Lineage completeness rate:         {b.lineage_completeness_rate:.1%}")
    lines.append(f"  False authoritative promotion rate: {b.false_authoritative_promotion_rate:.1%}")
    lines.append(f"  False authoritative promotion count: {b.false_authoritative_promotion_count}")
    lines.append("")
    lines.append("Extraction metrics (new chains only):")
    lines.append("")
    lines.append(f"  S0 extraction success rate:        {metrics.s0_extraction_success_rate:.1%}")
    lines.append(f"  GT extraction success rate:        {metrics.gt_extraction_success_rate:.1%}")
    lines.append(f"  S0 extraction coverage (avg):      {metrics.s0_extraction_coverage_avg:.1%}")
    lines.append(f"  GT extraction coverage (avg):      {metrics.gt_extraction_coverage_avg:.1%}")
    lines.append("```")
    lines.append("")

    # --- Safety check ---
    lines.append("## Safety Check")
    lines.append("")
    lines.append("> **False authoritative promotion rate should remain 0.**")
    lines.append("")
    if b.false_authoritative_promotion_count == 0:
        lines.append("**PASS** — False authoritative promotion rate is 0.")
    else:
        lines.append(f"**FAIL** — {b.false_authoritative_promotion_count} false authoritative promotions detected.")
    lines.append("")

    # --- Failure taxonomy ---
    lines.append("## Failure Taxonomy")
    lines.append("")
    lines.append("| Category | Count | Description |")
    lines.append("|---|---|---|")
    category_counts: dict[str, int] = {}
    for r in issuer_results:
        category_counts[r.failure_category] = category_counts.get(r.failure_category, 0) + 1
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        desc = FAILURE_CATEGORIES.get(cat, "")
        lines.append(f"| {cat} | {count} | {desc} |")
    lines.append("")

    # --- Extraction detail ---
    lines.append("## Extraction Detail")
    lines.append("")
    lines.append("### S0 Extraction (new chains)")
    lines.append("")
    lines.append("| Chain | S0 chars | Commitments | Validation Queue | Coverage |")
    lines.append("|---|---|---|---|---|")
    for r in issuer_results:
        if r.gt_extraction_source == "manual":
            continue  # skip existing chains
        lines.append(
            f"| {r.chain_id} | {r.s0_extraction_text_length} | "
            f"{r.s0_extraction_commitments} | "
            f"{r.s0_extraction_validation_queue} | "
            f"{r.s0_extraction_coverage:.1%} |"
        )
    lines.append("")

    lines.append("### GT Extraction (chains with CMP document)")
    lines.append("")
    lines.append("| Chain | CMP chars | Commitments | Validation Queue | Coverage |")
    lines.append("|---|---|---|---|---|")
    for r in issuer_results:
        if r.gt_extraction_source != "CMP":
            continue
        lines.append(
            f"| {r.chain_id} | {r.gt_extraction_text_length} | "
            f"{r.gt_extraction_commitments} | "
            f"{r.gt_extraction_validation_queue} | "
            f"{r.gt_extraction_coverage:.1%} |"
        )
    lines.append("")

    # --- Conclusion ---
    lines.append("## Conclusion")
    lines.append("")
    lines.append("```text")
    lines.append("Across real amendment chains, how often can Upsilon reconstruct")
    lines.append("authoritative commitment state correctly, and where does the")
    lines.append("current architecture stop?")
    lines.append("```")
    lines.append("")
    lines.append(f"- **Safety**: False authoritative promotion rate is")
    lines.append(f"  {b.false_authoritative_promotion_rate:.1%} ({b.false_authoritative_promotion_count} violations).")
    lines.append("")
    lines.append(f"- **S0 extraction**: {metrics.chains_with_extracted_s0}/{len(issuer_results) - 3} new chains")
    lines.append(f"  had at least 1 commitment extracted from S0. Average coverage:")
    lines.append(f"  {metrics.s0_extraction_coverage_avg:.1%}.")
    lines.append("")
    lines.append(f"- **GT extraction**: {metrics.chains_with_extracted_gt}/{metrics.chains_with_cmp_document}")
    lines.append(f"  chains with CMP documents had at least 1 commitment extracted.")
    lines.append(f"  Average coverage: {metrics.gt_extraction_coverage_avg:.1%}.")
    lines.append("")
    lines.append(f"- **Reconstruction accuracy**: {recon} for chains with ground truth.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    print("Development Chain Study v2")
    print("Frozen system: semantic-mapper-v0.1")
    print("New: S0 Commitment Extractor v0.1, Authoritative GT Extractor v0.1")
    print()

    # Load all 25 chains with extraction results
    chain_data = all_v2_chains()
    print(f"Loaded {len(chain_data)} chains")
    for chain, s0_res, gt_res in chain_data:
        gt = "yes" if chain.ground_truth_state else "no"
        s0_count = len(chain.original_state)
        gt_count = len(chain.ground_truth_state) if chain.ground_truth_state else 0
        print(
            f"  {chain.chain_id:20s}  {chain.issuer_name[:35]:35s}  "
            f"S0={s0_count}  GT={gt}({gt_count})  amendments={len(chain.amendments)}"
        )
    print()

    # Run the frozen semantic pipeline on each chain
    print("Running frozen semantic pipeline with extracted states...")
    pipeline_results: list[SemanticPipelineResult] = []
    issuer_results: list[IssuerStudyResultV2] = []

    for i, (chain, s0_result, gt_result) in enumerate(chain_data, 1):
        print(f"  [{i}/{len(chain_data)}] {chain.chain_id}...")
        pipe_result = run_semantic_pipeline(chain)
        pipeline_results.append(pipe_result)

        issuer_result = build_v2_issuer_result(
            chain, pipe_result, s0_result, gt_result
        )
        issuer_results.append(issuer_result)

        print(
            f"    S0={len(chain.original_state)}  GT={len(chain.ground_truth_state or {})}  "
            f"parser={pipe_result.total_parser_instructions}  "
            f"mapped={pipe_result.total_mapped}  "
            f"unresolved={pipe_result.total_unresolved}  "
            f"incorrect={len(pipe_result.incorrect_mutations)}  "
            f"category={issuer_result.failure_category}"
        )

    print()

    # Compute aggregate metrics
    metrics = compute_v2_aggregate_metrics(issuer_results, pipeline_results)

    # Render report
    report = render_v2_study_report(issuer_results, pipeline_results, metrics)

    # Write report
    report_path = Path("results/chain_study_v2_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}")

    # Write machine-readable results
    results_json: dict[str, Any] = {
        "study": "development_chain_study_v2",
        "frozen_version": "semantic-mapper-v0.1",
        "extractor_version": "s0-extractor-v0.1, gt-extractor-v0.1",
        "run_at": datetime.now(UTC).isoformat(),
        "issuer_results": [
            {
                "chain_id": r.chain_id,
                "issuer_name": r.issuer_name,
                "cik": r.cik,
                "has_ground_truth": r.has_ground_truth,
                "gt_extraction_source": r.gt_extraction_source,
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
    results_path = Path("results/chain_study_v2_results.json")
    results_path.write_text(json.dumps(results_json, indent=2), encoding="utf-8")
    print(f"Results JSON: {results_path}")

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY (v2)")
    print("=" * 60)
    print(f"Total chains:                  {metrics.base.total_chains}")
    print(f"S0 extraction success:         {metrics.chains_with_extracted_s0}/{len(chain_data) - 3}")
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
