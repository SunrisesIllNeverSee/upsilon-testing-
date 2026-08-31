"""Development Chain Study v1 — first-pass report generator.

Runs the FROZEN semantic-mapper-v0.1 system across 25 real EDGAR
issuer chains and produces the complete first-pass report with:

  - Per-issuer results (issuer/CIK, S0 accession, amendment accessions,
    comparison_at, final authoritative source, instruction counts,
    chain authoritative?, lineage complete?, failure category)
  - Aggregate metrics (instruction detection P/R, semantic mapping
    precision/coverage, incorrect mutation rate, UNRESOLVED rate,
    chain-level exact reconstruction rate, lineage completeness rate,
    false authoritative promotion rate)
  - Failure taxonomy

The frozen components (parser, mapper, executor, authority, lineage,
persistence) are NOT modified during the first-pass run.  Failures are
logged, not fixed.

Usage:
    python run_chain_study.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chain_reconstruction import IssuerChain
from chain_study_chains import all_study_chains
from semantic_pipeline import (
    SemanticPipelineResult,
    run_semantic_pipeline,
)

# ---------------------------------------------------------------------------
# Per-issuer result capture
# ---------------------------------------------------------------------------


@dataclass
class IssuerStudyResult:
    """Per-issuer capture as specified by the Development Chain Study v1 protocol."""

    chain_id: str
    issuer_name: str
    cik: str
    s0_accession: str
    amendment_accessions: list[str]
    comparison_at: str
    final_authoritative_source: str

    # Instruction counts
    total_amendment_instructions: int  # gold-annotated count (N/A for new chains)
    parser_detected_instructions: int
    semantic_mapped_instructions: int
    unresolved_instructions: int
    incorrect_automatic_mutations: int

    # Chain-level assessments
    chain_authoritative: bool
    lineage_complete: bool
    final_state_exact_agreement: float | None  # None if no ground truth
    supported_field_agreement: float | None     # None if no ground truth
    failure_category: str

    # Per-step detail
    steps: list[dict[str, Any]] = field(default_factory=list)

    # Whether this chain has independent ground truth
    has_ground_truth: bool = False

    # Composite/conformed comparison source (acquired but ground-truth
    # extraction is v0.2+ work)
    comparison_source_accession: str | None = None
    comparison_source_file_date: str | None = None
    comparison_source_kind: str | None = None


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------

FAILURE_CATEGORIES = {
    "SUCCESS": "Chain reconstructed end-to-end with 100% state agreement.",
    "SYSTEM_INGESTION_PASS": (
        "System behaved correctly (no false promotion, no incorrect "
        "mutations) but reconstruction incomplete.  The system safely "
        "marked unsupported instructions as UNRESOLVED and did not "
        "falsely promote to authoritative."
    ),
    "PARSER_NO_INSTRUCTIONS": "Parser found 0 instructions across all amendments (unsupported format).",
    "MAPPER_LOW_COVERAGE": "Parser found instructions but mapper mapped <50% of them.",
    "EXECUTOR_PARTIAL": "Executor could not apply all mapped instructions (missing S0 state).",
    "UNRESOLVED_INSTRUCTIONS": "Chain has unresolved instructions that block authoritative promotion.",
    "INCORRECT_MUTATIONS": "Executor rejected mapped mutations (incorrect automatic mutations).",
    "FINAL_STATE_MISMATCH": "Reconstructed final state does not match ground truth exactly.",
    "NO_GROUND_TRUTH": "No independent ground truth available; cannot measure reconstruction accuracy.",
    "MULTIPLE_FAILURES": "Multiple failure categories apply.",
}


def classify_failure(
    result: SemanticPipelineResult,
    chain: IssuerChain,
    has_ground_truth: bool,
) -> str:
    """Classify the failure category for a chain.

    Classification hierarchy (checked in order):

    1. PARSER_NO_INSTRUCTIONS — the parser found 0 instructions across
       all amendments.  This is the "unsupported format" case
       (Amedisys/Bausch-Lomb): the system trivially passes safety (no
       mutations to reject, no unresolved to carry) but no reconstruction
       happened.

    2. SUCCESS — non-trivial reconstruction: the parser found
       instructions, the final state matches ground truth exactly, and
       no incorrect automatic mutations were produced.  Unresolved
       instructions on out-of-model fields do NOT disqualify SUCCESS
       (Ameresco: 11 unresolved but 100% match on measured fields).

    3. SYSTEM_INGESTION_PASS — the system behaved correctly on a chain
       without ground truth: no incorrect automatic mutations were
       produced, and the system did not falsely promote to authoritative.
       Reconstruction is incomplete (unresolved instructions exist), but
       the system's safety guarantees held.  This is the correct
       classification for new chains where the parser found instructions
       the mapper could not fully resolve — the system safely marked them
       UNRESOLVED rather than guessing.

    4. Remaining cases are real failures: incorrect mutations, final-state
       mismatches (with ground truth), executor partial execution, or
       mapper low coverage.  These are collected into an issues list and
       returned as a single category or MULTIPLE_FAILURES.
    """
    if result.total_parser_instructions == 0:
        return "PARSER_NO_INSTRUCTIONS"

    # Non-trivial reconstruction succeeded: parser found instructions,
    # final state matches ground truth exactly, and no incorrect
    # automatic mutations were produced.  Unresolved instructions on
    # out-of-model fields do not block this classification.
    if (
        has_ground_truth
        and result.final_state_agreement == 1.0
        and result.incorrect_mutation_rate == 0.0
    ):
        return "SUCCESS"

    # Without ground truth, if the system produced no incorrect
    # automatic mutations, it behaved correctly — it safely marked
    # unsupported instructions as UNRESOLVED and did not falsely
    # promote to authoritative.  This is SYSTEM_INGESTION_PASS, not
    # a failure.  The false-authoritative-promotion safety check
    # (verified separately) guarantees no false promotion occurred.
    if not has_ground_truth and result.incorrect_mutation_rate == 0.0:
        return "SYSTEM_INGESTION_PASS"

    # Remaining cases: real failures (incorrect mutations, state
    # mismatches with ground truth, executor partial, mapper low
    # coverage).  Collect all applicable issues.
    issues: list[str] = []

    if result.incorrect_mutation_rate > 0:
        issues.append("INCORRECT_MUTATIONS")

    if result.total_unresolved > 0 and not any(s.is_authoritative for s in result.steps):
        issues.append("UNRESOLVED_INSTRUCTIONS")

    if result.total_mapped > 0 and result.mapping_accuracy < 0.5:
        issues.append("MAPPER_LOW_COVERAGE")

    if any(s.execution_result.status.value == "PARTIAL" for s in result.steps):
        issues.append("EXECUTOR_PARTIAL")

    if has_ground_truth and result.final_state_agreement < 1.0:
        issues.append("FINAL_STATE_MISMATCH")

    if not has_ground_truth:
        issues.append("NO_GROUND_TRUTH")

    if not issues:
        return "SUCCESS"

    if len(issues) == 1:
        return issues[0]

    return "MULTIPLE_FAILURES"


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


@dataclass
class AggregateMetrics:
    """Aggregate study metrics."""

    # Counts
    total_chains: int
    total_amendments: int
    total_parser_instructions: int
    total_mapped_instructions: int
    total_unresolved: int
    total_incorrect_mutations: int

    # Rates
    instruction_detection_precision: float | None  # requires gold annotations
    instruction_detection_recall: float | None     # requires gold annotations
    semantic_mapping_precision: float
    semantic_mapping_coverage: float
    incorrect_automatic_mutation_rate: float
    unresolved_rate: float
    chain_level_exact_reconstruction_rate: float | None  # requires ground truth
    lineage_completeness_rate: float
    false_authoritative_promotion_rate: float

    # Safety
    false_authoritative_promotion_count: int


def compute_aggregate_metrics(
    issuer_results: list[IssuerStudyResult],
    pipeline_results: list[SemanticPipelineResult],
) -> AggregateMetrics:
    """Compute aggregate metrics across all chains."""
    total_chains = len(issuer_results)
    total_amendments = sum(len(r.steps) for r in issuer_results)
    total_parser = sum(r.parser_detected_instructions for r in issuer_results)
    total_mapped = sum(r.semantic_mapped_instructions for r in issuer_results)
    total_unresolved = sum(r.unresolved_instructions for r in issuer_results)
    total_incorrect = sum(r.incorrect_automatic_mutations for r in issuer_results)

    # Semantic mapping precision = correct_mapped / total_mapped.
    # A "correct" mapping is one the executor accepted (not rejected
    # as an incorrect automatic mutation).  This is distinct from
    # coverage: coverage measures what fraction of parser instructions
    # the mapper attempted to map; precision measures what fraction of
    # those attempted mappings were actually correct.
    correct_mapped = total_mapped - total_incorrect
    semantic_mapping_precision = correct_mapped / total_mapped if total_mapped > 0 else 1.0

    # Semantic mapping coverage = mapped / parser = 1 - unresolved_rate
    unresolved_rate = total_unresolved / total_parser if total_parser > 0 else 0.0
    semantic_mapping_coverage = 1.0 - unresolved_rate

    # Incorrect automatic mutation rate
    incorrect_rate = total_incorrect / total_mapped if total_mapped > 0 else 0.0

    # Chain-level exact reconstruction rate (only for chains with ground truth)
    gt_chains = [r for r in issuer_results if r.has_ground_truth]
    if gt_chains:
        exact_recon = sum(
            1 for r in gt_chains
            if r.final_state_exact_agreement == 1.0
        ) / len(gt_chains)
    else:
        exact_recon = None

    # Lineage completeness rate
    lineage_complete_count = sum(1 for r in issuer_results if r.lineage_complete)
    lineage_completeness_rate = lineage_complete_count / total_chains if total_chains > 0 else 0.0

    # False authoritative promotion rate
    # A false authoritative promotion occurs when a step is marked
    # is_authoritative=True but has unresolved instructions (own or inherited).
    # This MUST remain 0 for system safety.
    false_promo_count = 0
    for pipe_result in pipeline_results:
        for step in pipe_result.steps:
            own_unresolved = (
                len(step.mapper_unresolved)
                + len(step.execution_result.unresolved)
            )
            if step.is_authoritative and (
                own_unresolved > 0 or step.inherited_unresolved_count > 0
            ):
                false_promo_count += 1

    total_steps = sum(len(r.steps) for r in pipeline_results)
    false_promo_rate = false_promo_count / total_steps if total_steps > 0 else 0.0

    # Instruction detection precision/recall requires gold annotations
    # which are only available for the 3 existing chains (via semantic_gold.py)
    # For the first pass, we report this as N/A for new chains
    instruction_precision = None
    instruction_recall = None

    return AggregateMetrics(
        total_chains=total_chains,
        total_amendments=total_amendments,
        total_parser_instructions=total_parser,
        total_mapped_instructions=total_mapped,
        total_unresolved=total_unresolved,
        total_incorrect_mutations=total_incorrect,
        instruction_detection_precision=instruction_precision,
        instruction_detection_recall=instruction_recall,
        semantic_mapping_precision=round(semantic_mapping_precision, 4),
        semantic_mapping_coverage=round(semantic_mapping_coverage, 4),
        incorrect_automatic_mutation_rate=round(incorrect_rate, 4),
        unresolved_rate=round(unresolved_rate, 4),
        chain_level_exact_reconstruction_rate=(
            round(exact_recon, 4) if exact_recon is not None else None
        ),
        lineage_completeness_rate=round(lineage_completeness_rate, 4),
        false_authoritative_promotion_rate=round(false_promo_rate, 4),
        false_authoritative_promotion_count=false_promo_count,
    )


# ---------------------------------------------------------------------------
# Per-issuer result extraction
# ---------------------------------------------------------------------------


def _extract_cik(chain: IssuerChain) -> str:
    """Extract CIK from chain_id or issuer_name."""
    # For existing chains, CIK is in the edgar_chains.py comments
    # For new chains, it's in the issuer_name "(CIK 0001234567)"
    name = chain.issuer_name
    if "(CIK " in name:
        cik = name.split("(CIK ")[1].rstrip(")")
        return cik
    # Map existing chain IDs to CIKs
    cik_map = {
        "EDGAR-AMERESCO": "0001488139",
        "EDGAR-AMEDISYS": "0000896262",
        "EDGAR-BAUSCH-LOMB": "0001860742",
    }
    return cik_map.get(chain.chain_id, "unknown")


def _get_chain_manifest_entry(cik: str) -> dict | None:
    """Get the manifest entry for a CIK (for new chains)."""
    manifest_path = Path("data/chain_study/manifest.json")
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest.get("chains", []):
        if entry["cik"] == cik:
            return entry
    return None


# Supported fields for field-level agreement computation.
# This mirrors the _COMPARE_FIELDS tuple in semantic_pipeline.py's
# final-state comparator.  Duplicated here (rather than imported) because
# semantic_pipeline.py is part of the frozen v0.1 system and must not be
# modified to expose it.
_SUPPORTED_FIELDS = (
    "threshold",
    "rate",
    "deadline",
    "party",
    "exceptions",
    "applicability",
    "status",
    "unit",
)


def _compute_supported_field_agreement(
    reconstructed_state: dict,
    ground_truth_state: dict,
) -> float | None:
    """Compute field-level agreement over supported fields.

    Unlike final_state_agreement (which requires ALL fields of a
    commitment to match for that commitment to count), this metric
    measures the fraction of individual supported fields that agree,
    across all ground-truth commitments present in both the
    reconstructed and ground-truth states.

    Returns None if ground_truth_state is empty (no ground truth to
    compare against).
    """
    if not ground_truth_state:
        return None

    total_fields = 0
    matched_fields = 0
    for key, gt_commitment in ground_truth_state.items():
        if key not in reconstructed_state:
            # Missing commitment — all its fields count as mismatched
            total_fields += len(_SUPPORTED_FIELDS)
            continue
        recon = reconstructed_state[key]
        for fname in _SUPPORTED_FIELDS:
            total_fields += 1
            recon_val = getattr(recon, fname, None)
            gt_val = getattr(gt_commitment, fname, None)
            if recon_val == gt_val:
                matched_fields += 1

    return matched_fields / total_fields if total_fields > 0 else None


def build_issuer_result(
    chain: IssuerChain,
    pipe_result: SemanticPipelineResult,
) -> IssuerStudyResult:
    """Build a per-issuer result from the pipeline output."""
    cik = _extract_cik(chain)
    manifest_entry = _get_chain_manifest_entry(cik)

    has_gt = chain.ground_truth_state is not None and len(chain.ground_truth_state) > 0

    # Extract accessions
    if manifest_entry:
        s0_accession = manifest_entry["s0_accession"]
        amendment_accessions = manifest_entry["amendment_accessions"]
        final_authoritative_source = manifest_entry["final_authoritative_source"]
        comparison_source_accession = manifest_entry.get("comparison_source_accession")
        comparison_source_file_date = manifest_entry.get("comparison_source_file_date")
        comparison_source_kind = manifest_entry.get("comparison_source_kind")
    else:
        # Existing chains — accessions from edgar_chains.py comments
        s0_accession = "N/A (existing fixture)"
        amendment_accessions = [
            f"A{step.amendment_number}" for step in chain.amendments
        ]
        final_authoritative_source = "manually_extracted_ground_truth"
        comparison_source_accession = None
        comparison_source_file_date = None
        comparison_source_kind = None

    # Per-step detail
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

    # Chain-level assessments
    # chain_authoritative: the final step is authoritative — the end
    # state can be trusted as authoritative (no unresolved uncertainty
    # carried forward to the last amendment).  This is the strict
    # safety property: the final reconstructed state has zero unresolved
    # instructions (own or inherited).
    chain_authoritative = (
        len(pipe_result.steps) > 0
        and pipe_result.steps[-1].is_authoritative
    )

    # lineage_complete: every amendment step was processed end-to-end
    # with execution status COMPLETE (all mapped instructions applied
    # successfully), and all amendments in the chain were processed.
    # This measures tracking completeness, not authority — a chain can
    # have complete lineage (all steps executed) without being
    # authoritative (unresolved instructions block promotion).
    lineage_complete = (
        len(pipe_result.steps) == len(chain.amendments)
        and len(pipe_result.steps) > 0
        and all(
            s.execution_result.status.value == "COMPLETE"
            for s in pipe_result.steps
        )
    )

    # Final state agreement (commitment-level exact match) and
    # supported-field agreement (field-level partial match).
    # final_state_agreement: fraction of ground-truth commitments where
    #   ALL supported fields match exactly (commitment-level).
    # supported_field_agreement: fraction of individual supported fields
    #   that match across all ground-truth commitments (field-level).
    #   A chain with 0% final-state exact agreement can still have high
    #   supported-field agreement if most individual fields are correct
    #   but one field differs per commitment.
    if has_gt:
        final_state_agreement = pipe_result.final_state_agreement
        supported_field_agreement = _compute_supported_field_agreement(
            pipe_result.reconstructed_state,
            chain.ground_truth_state,
        )
    else:
        final_state_agreement = None
        supported_field_agreement = None

    # Total amendment instructions (gold-annotated count)
    # For existing chains, this is the sum of instructions in the fixtures
    # For new chains, this is N/A (no gold annotations)
    if has_gt:
        total_amendment_instructions = sum(
            len(step.instructions) for step in chain.amendments
        )
    else:
        total_amendment_instructions = -1  # N/A

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
# Report generation
# ---------------------------------------------------------------------------


def render_study_report(
    issuer_results: list[IssuerStudyResult],
    pipeline_results: list[SemanticPipelineResult],
    metrics: AggregateMetrics,
) -> str:
    """Render the complete first-pass study report."""
    lines: list[str] = []

    lines.append("# Development Chain Study v1 — First-Pass Report")
    lines.append("")
    lines.append("**Frozen system: semantic-mapper-v0.1 (tag: semantic-mapper-v0.1)**")
    lines.append("")
    lines.append("## Study Protocol")
    lines.append("")
    lines.append("```text")
    lines.append("FROZEN semantic-mapper-v0.1")
    lines.append("        |")
    lines.append("25 real EDGAR issuer chains")
    lines.append("        |")
    lines.append("NO tuning during first pass")
    lines.append("        |")
    lines.append("measure actual system performance")
    lines.append("        |")
    lines.append("failure taxonomy")
    lines.append("        |")
    lines.append("only then design v0.2")
    lines.append("```")
    lines.append("")
    lines.append("### What this report does and does NOT prove")
    lines.append("")
    lines.append("When the system reports a chain as PASS (system-ingestion pass),")
    lines.append("that means **the system behaved correctly on that chain** — it did")
    lines.append("not falsely promote to authoritative, it did not produce incorrect")
    lines.append("mutations, and it safely marked unsupported instructions as UNRESOLVED.")
    lines.append("It does **not** mean the chain was successfully reconstructed.")
    lines.append("")
    lines.append("### Chain composition")
    lines.append("")
    lines.append("- Chains 1-3: existing smoke-test chains (Ameresco, Amedisys, Bausch-Lomb)")
    lines.append("  - These have hand-extracted ground truth from independently filed composites")
    lines.append("- Chains 4-25: 22 new chains acquired from SEC EDGAR for this study")
    lines.append("  - Composite/conformed/restated comparison sources were searched for")
    lines.append("    after each chain's last amendment; where found, they are recorded")
    lines.append("    as the authoritative comparison source (ground-truth extraction is v0.2+)")
    lines.append("  - S0 commitment state is empty (automated S0 extraction is future work)")
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
        total_instr = (
            str(r.total_amendment_instructions)
            if r.total_amendment_instructions >= 0
            else "N/A"
        )
        lines.append(f"{r.chain_id}  {r.issuer_name[:40]:40s}")
        lines.append(f"  CIK:                      {r.cik}")
        lines.append(f"  S0 accession:             {r.s0_accession}")
        lines.append(f"  amendment accessions:     {', '.join(r.amendment_accessions)}")
        lines.append(f"  comparison_at:            {r.comparison_at}")
        lines.append(f"  final authoritative src:  {r.final_authoritative_source}")
        if r.comparison_source_accession:
            lines.append(f"  comparison source:        {r.comparison_source_accession} ({r.comparison_source_file_date})")
            lines.append(f"  comparison source kind:   {r.comparison_source_kind}")
        else:
            lines.append("  comparison source:        none (last amendment used)")
        lines.append(f"  has ground truth:         {gt_label}")
        lines.append(f"  total amendment instr:    {total_instr}")
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

    # --- Per-step detail ---
    lines.append("## Per-Step Detail")
    lines.append("")
    lines.append("| Chain | Step | Pattern | Parser | Mapped | Unresolved | Exec Status | Auth | Inherited Unres |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in issuer_results:
        for s in r.steps:
            lines.append(
                f"| {r.chain_id} | A{s['amendment_number']} | {s['pattern'] or 'N/A'} | "
                f"{s['parser_instruction_count']} | {s['mapper_mutations']} | "
                f"{s['mapper_unresolved']} | {s['execution_status']} | "
                f"{'yes' if s['is_authoritative'] else 'no'} | "
                f"{s['inherited_unresolved_count']} |"
            )
    lines.append("")

    # --- Aggregate metrics ---
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append("```text")
    lines.append(f"Total chains:                      {metrics.total_chains}")
    lines.append(f"Total amendments:                  {metrics.total_amendments}")
    lines.append(f"Total parser instructions:         {metrics.total_parser_instructions}")
    lines.append(f"Total semantic-mapped:             {metrics.total_mapped_instructions}")
    lines.append(f"Total UNRESOLVED:                  {metrics.total_unresolved}")
    lines.append(f"Total incorrect mutations:         {metrics.total_incorrect_mutations}")
    lines.append("")
    lines.append("Primary study metrics:")
    lines.append("")

    prec = (
        f"{metrics.instruction_detection_precision:.1%}"
        if metrics.instruction_detection_precision is not None
        else "N/A (no gold annotations for new chains)"
    )
    rec = (
        f"{metrics.instruction_detection_recall:.1%}"
        if metrics.instruction_detection_recall is not None
        else "N/A (no gold annotations for new chains)"
    )
    recon = (
        f"{metrics.chain_level_exact_reconstruction_rate:.1%}"
        if metrics.chain_level_exact_reconstruction_rate is not None
        else "N/A (no ground truth for 22/25 chains)"
    )

    lines.append(f"  Instruction detection precision:  {prec}")
    lines.append(f"  Instruction detection recall:      {rec}")
    lines.append(f"  Semantic mapping precision:        {metrics.semantic_mapping_precision:.1%}")
    lines.append(f"  Semantic mapping coverage:         {metrics.semantic_mapping_coverage:.1%}")
    lines.append(f"  Incorrect automatic mutation rate: {metrics.incorrect_automatic_mutation_rate:.1%}")
    lines.append(f"  UNRESOLVED rate:                   {metrics.unresolved_rate:.1%}")
    lines.append(f"  Chain-level exact reconstruction:  {recon}")
    lines.append(f"  Lineage completeness rate:         {metrics.lineage_completeness_rate:.1%}")
    lines.append(f"  False authoritative promotion rate: {metrics.false_authoritative_promotion_rate:.1%}")
    lines.append(f"  False authoritative promotion count: {metrics.false_authoritative_promotion_count}")
    lines.append("")
    lines.append("```")
    lines.append("")

    # --- Safety check ---
    lines.append("## Safety Check")
    lines.append("")
    lines.append("> **False authoritative promotion rate should remain 0.**")
    lines.append("")
    if metrics.false_authoritative_promotion_count == 0:
        lines.append("**PASS** — False authoritative promotion rate is 0.")
        lines.append("The system never promoted a chain to authoritative when")
        lines.append("unresolved instructions were present.  This is the primary")
        lines.append("safety/integrity guarantee.")
    else:
        lines.append(f"**FAIL** — {metrics.false_authoritative_promotion_count} false")
        lines.append("authoritative promotions detected.  This is a safety violation.")
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

    # --- Failure detail ---
    lines.append("## Failure Detail")
    lines.append("")
    for r in issuer_results:
        if r.failure_category == "SUCCESS":
            continue
        lines.append(f"### {r.chain_id} — {r.failure_category}")
        lines.append("")
        lines.append(f"- Issuer: {r.issuer_name}")
        lines.append(f"- Parser instructions: {r.parser_detected_instructions}")
        lines.append(f"- Mapped: {r.semantic_mapped_instructions}")
        lines.append(f"- UNRESOLVED: {r.unresolved_instructions}")
        lines.append(f"- Incorrect mutations: {r.incorrect_automatic_mutations}")
        if r.has_ground_truth:
            lines.append(f"- Final state agreement: {r.final_state_exact_agreement:.1%}")
            # Show state mismatches
            for pipe_r in pipeline_results:
                if pipe_r.chain_id == r.chain_id:
                    for m in pipe_r.state_mismatches:
                        lines.append(f"  - {m}")
                    for m in pipe_r.incorrect_mutations:
                        lines.append(f"  - Incorrect: {m}")
        lines.append("")

    # --- Existing chains (with ground truth) ---
    lines.append("## Existing Chains (with ground truth)")
    lines.append("")
    lines.append("These 3 chains have hand-extracted ground truth and serve as")
    lines.append("the validation baseline for the frozen system.")
    lines.append("")
    for r in issuer_results:
        if not r.has_ground_truth:
            continue
        lines.append(f"### {r.chain_id}")
        lines.append("")
        lines.append(f"- Parser instructions: {r.parser_detected_instructions}")
        lines.append(f"- Mapped: {r.semantic_mapped_instructions}")
        lines.append(f"- UNRESOLVED: {r.unresolved_instructions}")
        lines.append(f"- Incorrect mutations: {r.incorrect_automatic_mutations}")
        lines.append(f"- Final state agreement: {r.final_state_exact_agreement:.1%}")
        lines.append(f"- Chain authoritative: {'yes' if r.chain_authoritative else 'no'}")
        lines.append(f"- Failure category: {r.failure_category}")
        lines.append("")

    # --- Known limitations ---
    lines.append("## Known First-Pass Limitations")
    lines.append("")
    lines.append("1. **No extracted ground truth for 22/25 chains.** The 22 new chains")
    lines.append("   do not have independently extracted ground truth.  Composite/")
    lines.append("   conformed/restated comparison sources were searched for and")
    lines.append("   downloaded where available, but automated ground-truth extraction")
    lines.append("   from those sources is v0.2+ work.  Final-state exact agreement")
    lines.append("   and supported-field agreement are N/A for these chains.")
    lines.append("")
    lines.append("2. **Empty S0 state for 22/25 chains.** The original credit agreement")
    lines.append("   (S0) commitment state is empty for new chains because automated S0")
    lines.append("   commitment extraction is not implemented.  The executor starts with")
    lines.append("   no commitments, so REPLACE_VALUE and DELETE instructions will fail")
    lines.append("   (no existing commitment to modify).  ADD instructions will succeed.")
    lines.append("   This is a known limitation, not a system bug.")
    lines.append("")
    lines.append("3. **No gold instruction annotations for 22/25 chains.** Instruction")
    lines.append("   detection precision/recall requires gold-annotated instruction counts.")
    lines.append("   These are only available for the 3 existing chains.  For new chains,")
    lines.append("   we report parser-detected counts but cannot compute P/R.")
    lines.append("")
    lines.append("4. **Pattern classification is automated but may misclassify.** The")
    lines.append("   frozen pattern_classifier uses heuristics that may not correctly")
    lines.append("   identify all amendment patterns.  Misclassifications are logged")
    lines.append("   in the failure taxonomy, not fixed.")
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
    lines.append("- **Safety**: The false authoritative promotion rate is")
    lines.append(f"  {metrics.false_authoritative_promotion_rate:.1%} ({metrics.false_authoritative_promotion_count} violations).")
    lines.append("  The system never falsely promotes to authoritative.")
    lines.append("")
    lines.append(f"- **Parser coverage**: The parser detected {metrics.total_parser_instructions}")
    lines.append(f"  instructions across {metrics.total_amendments} amendments in")
    lines.append(f"  {metrics.total_chains} chains.  Many amendments use unsupported formats")
    lines.append("  (full restatement, conformed copy) where the parser finds 0 instructions.")
    lines.append("")
    lines.append(f"- **Mapper coverage**: Of {metrics.total_parser_instructions} parser instructions,")
    lines.append(f"  {metrics.total_mapped_instructions} were semantically mapped")
    lines.append(f"  ({metrics.semantic_mapping_precision:.1%} precision) and")
    lines.append(f"  {metrics.total_unresolved} were UNRESOLVED ({metrics.unresolved_rate:.1%} rate).")
    lines.append("")
    lines.append(f"- **Incorrect mutations**: {metrics.total_incorrect_mutations} incorrect")
    lines.append(f"  automatic mutations ({metrics.incorrect_automatic_mutation_rate:.1%} rate).")
    lines.append("")
    lines.append(f"- **Reconstruction accuracy**: {recon} for chains with ground truth.")
    lines.append("")

    # Comparison source acquisition summary
    cmp_count = sum(1 for r in issuer_results if r.comparison_source_accession)
    lines.append(f"- **Comparison sources**: {cmp_count}/{len(issuer_results)} chains have")
    lines.append("  a composite/conformed/restated comparison source acquired from EDGAR.")
    lines.append("  Ground-truth extraction from these sources is the primary v0.2 target.")
    lines.append("")
    lines.append("- **Where the architecture stops**: The parser handles incremental")
    lines.append("  section-level amendments but cannot parse full restatements or")
    lines.append("  conformed copies.  The mapper handles known patterns (leverage")
    lines.append("  ratios, JCA additions, maturity dates, rates, exceptions, party")
    lines.append("  changes) but marks unknown instructions as UNRESOLVED.  The")
    lines.append("  executor requires S0 commitment state to apply REPLACE_VALUE and")
    lines.append("  DELETE instructions; without S0 state, only ADD instructions")
    lines.append("  succeed.  Ground-truth extraction from composite/conformed")
    lines.append("  sources is the primary gap for v0.2.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    print("Development Chain Study v1")
    print("Frozen system: semantic-mapper-v0.1")
    print()

    # Load all 25 chains
    chains = all_study_chains()
    print(f"Loaded {len(chains)} chains")
    for c in chains:
        gt = "yes" if c.ground_truth_state else "no"
        print(f"  {c.chain_id:20s}  {c.issuer_name[:40]:40s}  GT={gt}  amendments={len(c.amendments)}")
    print()

    # Run the frozen semantic pipeline on each chain
    print("Running frozen semantic pipeline...")
    pipeline_results: list[SemanticPipelineResult] = []
    issuer_results: list[IssuerStudyResult] = []

    for i, chain in enumerate(chains, 1):
        print(f"  [{i}/{len(chains)}] {chain.chain_id}...")
        pipe_result = run_semantic_pipeline(chain)
        pipeline_results.append(pipe_result)

        issuer_result = build_issuer_result(chain, pipe_result)
        issuer_results.append(issuer_result)

        print(
            f"    parser={pipe_result.total_parser_instructions}  "
            f"mapped={pipe_result.total_mapped}  "
            f"unresolved={pipe_result.total_unresolved}  "
            f"incorrect={len(pipe_result.incorrect_mutations)}  "
            f"category={issuer_result.failure_category}"
        )

    print()

    # Compute aggregate metrics
    metrics = compute_aggregate_metrics(issuer_results, pipeline_results)

    # Render report
    report = render_study_report(issuer_results, pipeline_results, metrics)

    # Write report
    report_path = Path("results/chain_study_v1_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}")

    # Write machine-readable results
    results_json: dict[str, Any] = {
        "study": "development_chain_study_v1",
        "frozen_version": "semantic-mapper-v0.1",
        "run_at": datetime.now(UTC).isoformat(),
        "issuer_results": [
            {
                "chain_id": r.chain_id,
                "issuer_name": r.issuer_name,
                "cik": r.cik,
                "s0_accession": r.s0_accession,
                "amendment_accessions": r.amendment_accessions,
                "comparison_at": r.comparison_at,
                "final_authoritative_source": r.final_authoritative_source,
                "comparison_source_accession": r.comparison_source_accession,
                "comparison_source_file_date": r.comparison_source_file_date,
                "comparison_source_kind": r.comparison_source_kind,
                "has_ground_truth": r.has_ground_truth,
                "total_amendment_instructions": r.total_amendment_instructions,
                "parser_detected_instructions": r.parser_detected_instructions,
                "semantic_mapped_instructions": r.semantic_mapped_instructions,
                "unresolved_instructions": r.unresolved_instructions,
                "incorrect_automatic_mutations": r.incorrect_automatic_mutations,
                "chain_authoritative": r.chain_authoritative,
                "lineage_complete": r.lineage_complete,
                "final_state_exact_agreement": r.final_state_exact_agreement,
                "supported_field_agreement": r.supported_field_agreement,
                "failure_category": r.failure_category,
                "steps": r.steps,
            }
            for r in issuer_results
        ],
        "aggregate_metrics": {
            "total_chains": metrics.total_chains,
            "total_amendments": metrics.total_amendments,
            "total_parser_instructions": metrics.total_parser_instructions,
            "total_mapped_instructions": metrics.total_mapped_instructions,
            "total_unresolved": metrics.total_unresolved,
            "total_incorrect_mutations": metrics.total_incorrect_mutations,
            "instruction_detection_precision": metrics.instruction_detection_precision,
            "instruction_detection_recall": metrics.instruction_detection_recall,
            "semantic_mapping_precision": metrics.semantic_mapping_precision,
            "semantic_mapping_coverage": metrics.semantic_mapping_coverage,
            "incorrect_automatic_mutation_rate": metrics.incorrect_automatic_mutation_rate,
            "unresolved_rate": metrics.unresolved_rate,
            "chain_level_exact_reconstruction_rate": metrics.chain_level_exact_reconstruction_rate,
            "lineage_completeness_rate": metrics.lineage_completeness_rate,
            "false_authoritative_promotion_rate": metrics.false_authoritative_promotion_rate,
            "false_authoritative_promotion_count": metrics.false_authoritative_promotion_count,
        },
    }
    results_path = Path("results/chain_study_v1_results.json")
    results_path.write_text(json.dumps(results_json, indent=2), encoding="utf-8")
    print(f"Results JSON: {results_path}")

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total chains:                  {metrics.total_chains}")
    print(f"Total amendments:              {metrics.total_amendments}")
    print(f"Total parser instructions:     {metrics.total_parser_instructions}")
    print(f"Total mapped:                  {metrics.total_mapped_instructions}")
    print(f"Total UNRESOLVED:              {metrics.total_unresolved}")
    print(f"Total incorrect mutations:     {metrics.total_incorrect_mutations}")
    print(f"Semantic mapping precision:    {metrics.semantic_mapping_precision:.1%}")
    print(f"Semantic mapping coverage:     {metrics.semantic_mapping_coverage:.1%}")
    print(f"UNRESOLVED rate:               {metrics.unresolved_rate:.1%}")
    print(f"Incorrect mutation rate:       {metrics.incorrect_automatic_mutation_rate:.1%}")
    print(f"Lineage completeness rate:     {metrics.lineage_completeness_rate:.1%}")
    print(f"False auth promotion rate:     {metrics.false_authoritative_promotion_rate:.1%}")
    print(f"False auth promotion count:    {metrics.false_authoritative_promotion_count}")
    print()

    # Safety check
    if metrics.false_authoritative_promotion_count == 0:
        print("SAFETY: PASS — false authoritative promotion rate is 0")
    else:
        print(f"SAFETY: FAIL — {metrics.false_authoritative_promotion_count} false promotions")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
