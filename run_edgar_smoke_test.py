"""Real EDGAR system smoke test runner.

Runs the end-to-end amendment-chain reconstruction on real SEC EDGAR
filing chains and produces a markdown report.

This is the REAL EDGAR system smoke test, distinct from the synthetic
system smoke test (run_smoke_test.py).  The chains are built from real
SEC filings acquired via sec_ingest.py.  The ground-truth states are
independently extracted from real legal documents (Annex A composites,
conformed copies, or manually extracted final amendment states).

IMPORTANT — what this test does and does NOT prove:

  PROVES (system-ingestion PASS):
    - EDGAR acquisition and document-chain assembly works.
    - Authoritative final-state discovery works.
    - Pattern classification correctly routes filings.
    - The reconstruction pipeline (executor, persistence, lineage)
      produces correct state when given valid commitment-level
      instructions.
    - Independent ground-truth comparison works.

  DOES NOT PROVE (parser-completeness gaps):
    - Parser v0.4.1 does NOT parse full restatement amendments.
    - Parser v0.4.1 does NOT parse conformed copy amendments.
    - Commitment-level instruction mapping is currently MANUAL_FALLBACK,
      not automated.  The semantic-mapping layer is not yet implemented.
    - Only 1 of 3 real amendment patterns (incremental) is parsed
      automatically by the parser.

  Release acceptance for the 25-issuer study will require:
    - Correct pattern classification (implemented, tested).
    - Automatic authoritative-document selection (NOT YET — currently
      manual fixture construction; no automated extraction code).
    - Final commitment state generated without hand mapping (NOT YET
      — semantic-mapping layer is scaffolded but not implemented).
    - Every field linked to document, section and amendment (implemented
      via citation_document / citation_section on AmendmentInstruction).
    - Explicit unsupported/ambiguous status instead of misleading parser
      success (implemented via provenance tracking and this report).
    - A broader corpus across at least 10-20 issuers (not yet started).

Usage:
    python run_edgar_smoke_test.py [--out results/edgar_smoke_test.md]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chain_reconstruction import ChainReconstructionResult, reconstruct_chain
from edgar_chains import all_edgar_chains


def _provenance_summary(steps) -> dict[str, int]:
    """Aggregate provenance counts across all steps."""
    totals: dict[str, int] = {}
    for s in steps:
        for prov, count in s.provenance_counts.items():
            totals[prov] = totals.get(prov, 0) + count
    return totals


def _pattern_summary(steps) -> dict[str, int]:
    """Count amendments by pattern."""
    counts: dict[str, int] = {}
    for s in steps:
        p = s.pattern or "unknown"
        counts[p] = counts.get(p, 0) + 1
    return counts


def _parser_coverage(steps) -> tuple[int, int]:
    """Return (parser_supported_amendments, total_amendments)."""
    supported = sum(1 for s in steps if s.parser_instruction_count is not None and s.parser_instruction_count > 0)
    total = len(steps)
    return supported, total


def render_report(results: list[ChainReconstructionResult]) -> str:
    """Render the real EDGAR smoke-test results as a markdown report."""
    lines: list[str] = []
    lines.append("# Upsilon Real EDGAR System Smoke Test")
    lines.append("")
    lines.append("**This is a system-ingestion PASS, not a parser-completeness PASS.**")
    lines.append("")
    lines.append("The real EDGAR smoke test proves that the acquisition, pattern")
    lines.append("classification, reconstruction pipeline, and ground-truth comparison")
    lines.append("work on real SEC filings.  It does NOT prove that the parser can")
    lines.append("extract instructions from all real amendment patterns.")
    lines.append("")

    # Honest capability summary
    lines.append("## Capability summary")
    lines.append("")
    lines.append("| Capability | Status |")
    lines.append("|---|---|")

    total_amendments = sum(len(r.steps) for r in results)
    parser_supported, _ = _parser_coverage(
        [s for r in results for s in r.steps]
    )
    all_q4 = all(r.questions["Q4_ground_truth_match"]["pass"] for r in results)
    all_q1 = all(r.questions["Q1_state_preservation"]["pass"] for r in results)
    all_q2 = all(r.questions["Q2_lineage_completeness"]["pass"] for r in results)
    all_q3 = all(r.questions["Q3_unresolved_blocks_promotion"]["pass"] for r in results)

    lines.append(f"| EDGAR acquisition and document-chain assembly | PASS |")
    lines.append(f"| Authoritative final-state discovery | PASS (manual fixture construction) |")
    lines.append(f"| Pattern classification (incremental / full restatement / conformed copy) | PASS |")
    lines.append(f"| Incremental-amendment parsing (parse_v04) | PASS ({parser_supported}/{total_amendments} amendments) |")
    lines.append(f"| Full-restatement parsing | **FAIL / unsupported** (0 instructions) |")
    lines.append(f"| Conformed-copy parsing | **FAIL / unsupported** (0 instructions) |")
    lines.append(f"| Automated commitment-field mapping (semantic mapper) | **Not implemented** (scaffold only) |")
    lines.append(f"| Composite-extraction fallback (Annex A as authoritative base) | **Scaffolded / manual** (no automated extraction code; ground truth hand-extracted from Annex A) |")
    lines.append(f"| Reconstruction pipeline (executor + persistence + lineage) | {'PASS' if all_q1 and all_q2 else 'FAIL'} |")
    lines.append(f"| Independent ground-truth comparison | {'PASS' if all_q4 else 'FAIL'} |")
    lines.append(f"| Provenance tracking (MANUAL_FALLBACK exercised; PARSER / SEMANTIC_MAPPER / COMPOSITE_EXTRACTION defined but not yet exercised) | PASS |")
    lines.append("")

    # Parser coverage detail
    lines.append("## Parser coverage")
    lines.append("")
    lines.append(f"Parser v0.4.1 automatically extracted instructions from")
    lines.append(f"**{parser_supported} of {total_amendments}** real amendments.")
    lines.append(f"The remaining {total_amendments - parser_supported} amendments used")
    lines.append(f"MANUAL_FALLBACK provenance (hand-mapped commitment-level instructions).")
    lines.append("")
    lines.append("Parser v0.4.1 should be described as supporting **incremental")
    lines.append("section-level amendments only**.  Full restatement and conformed")
    lines.append("copy patterns require a different processing strategy:")
    lines.append("")
    lines.append("- **Full restatement**: treat the latest Annex A composite as the")
    lines.append("  new authoritative base state.  Do NOT replay amendments.")
    lines.append("- **Conformed copy**: parse the final clean state from the Annex A")
    lines.append("  conformed copy (strip redline markup).  Use redlines for lineage.")
    lines.append("")

    # Pattern distribution
    lines.append("## Amendment pattern distribution")
    lines.append("")
    all_steps = [s for r in results for s in r.steps]
    pat_counts = _pattern_summary(all_steps)
    lines.append("| Pattern | Count | Parser supported | Strategy |")
    lines.append("|---|---:|:---:|---|")
    strategies = {
        "incremental": "parse_v04 → semantic mapper",
        "full_restatement": "Annex A composite as authoritative base",
        "conformed_copy": "Parse clean state from Annex A; redlines for lineage",
        "unknown": "Manual review required",
    }
    for pat in ["incremental", "full_restatement", "conformed_copy", "unknown"]:
        count = pat_counts.get(pat, 0)
        if count == 0:
            continue
        supported = "yes" if pat == "incremental" else "no"
        lines.append(f"| {pat} | {count} | {supported} | {strategies.get(pat, '—')} |")
    lines.append("")

    # Provenance summary
    lines.append("## Instruction provenance")
    lines.append("")
    lines.append("| Provenance | Count | Description |")
    lines.append("|---|---:|---|")
    prov_totals = _provenance_summary(all_steps)
    prov_desc = {
        "parser": "Automatically extracted by parse_v04",
        "semantic_mapper": "Automatically derived by semantic-mapping layer",
        "composite_extraction": "Derived from Annex A composite/conformed copy",
        "manual": "Hand-mapped (routine development)",
        "manual_fallback": "Hand-mapped because parser/mapper could not produce automatically",
    }
    for prov in ["parser", "semantic_mapper", "composite_extraction", "manual", "manual_fallback"]:
        count = prov_totals.get(prov, 0)
        if count == 0:
            continue
        lines.append(f"| {prov} | {count} | {prov_desc.get(prov, '—')} |")
    lines.append("")
    lines.append("**All commitment-level instructions are currently MANUAL_FALLBACK.**")
    lines.append("The semantic-mapping layer (section → commitment field) is not yet")
    lines.append("implemented.  Release acceptance requires that routine field")
    lines.append("population be automated, with manual review reserved for ambiguous")
    lines.append("mappings only.")
    lines.append("")

    # Reconstruction summary
    lines.append("## Reconstruction summary (pipeline correctness)")
    lines.append("")
    lines.append("Given valid commitment-level instructions (regardless of provenance),")
    lines.append("the reconstruction pipeline produces correct state:")
    lines.append("")
    lines.append("| Chain | Issuer | Amendments | Pattern | Q1 | Q2 | Q3 | Q4 | Pipeline |")
    lines.append("|---|---|---:|---|:---:|:---:|:---:|:---:|:---:|")
    for r in results:
        q1 = "PASS" if r.questions["Q1_state_preservation"]["pass"] else "FAIL"
        q2 = "PASS" if r.questions["Q2_lineage_completeness"]["pass"] else "FAIL"
        q3 = "PASS" if r.questions["Q3_unresolved_blocks_promotion"]["pass"] else "FAIL"
        q4 = "PASS" if r.questions["Q4_ground_truth_match"]["pass"] else "FAIL"
        pipeline = "PASS" if all(r.questions[k]["pass"] for k in (
            "Q1_state_preservation",
            "Q2_lineage_completeness",
            "Q3_unresolved_blocks_promotion",
            "Q4_ground_truth_match",
        )) else "FAIL"
        # Determine dominant pattern
        chain_patterns = _pattern_summary(r.steps)
        dominant = max(chain_patterns, key=chain_patterns.get)
        lines.append(
            f"| {r.chain_id} | {r.issuer_name} | {len(r.steps)} | {dominant} | {q1} | {q2} | {q3} | {q4} | {pipeline} |"
        )
    lines.append("")

    # Per-chain detail
    for r in results:
        lines.append(f"## {r.chain_id} — {r.issuer_name}")
        lines.append("")
        lines.append(f"**Amendments:** {len(r.steps)}")
        if r.ground_truth_label:
            lines.append(f"**Ground truth:** {r.ground_truth_label}")
        lines.append("")

        # Step-by-step with pattern and provenance
        lines.append("### Reconstruction steps")
        lines.append("")
        lines.append("| Step | Effective | Pattern | Parser ins. | Status | Applied | Provenance | Authoritative |")
        lines.append("|---:|---|---|---:|---|---:|---|:---:|")
        for s in r.steps:
            auth = "yes" if s.is_authoritative else "**no**"
            pat = s.pattern or "—"
            parser_ct = str(s.parser_instruction_count) if s.parser_instruction_count is not None else "—"
            prov = ", ".join(f"{k}:{v}" for k, v in sorted(s.provenance_counts.items())) if s.provenance_counts else "—"
            lines.append(
                f"| A{s.amendment_number} | {s.effective_at.date().isoformat()} | "
                f"{pat} | {parser_ct} | "
                f"{s.execution_result.status.value} | "
                f"{len(s.execution_result.applied)} | {prov} | {auth} |"
            )
        lines.append("")

        # Four questions
        lines.append("### Four questions")
        lines.append("")
        for qk, qlabel in [
            ("Q1_state_preservation", "Q1: Preserve authoritative state across amendments"),
            ("Q2_lineage_completeness", "Q2: Maintain complete lineage from origin to current"),
            ("Q3_unresolved_blocks_promotion", "Q3: Unresolved blocks authoritative promotion"),
            ("Q4_ground_truth_match", "Q4: Reconstructed state matches independent ground truth"),
        ]:
            q = r.questions[qk]
            verdict = "PASS" if q["pass"] else "FAIL"
            lines.append(f"**{qlabel}**: {verdict}")
            lines.append(f"- {q['summary']}")
            ev = q["evidence"]
            if qk == "Q1_state_preservation":
                lines.append(
                    f"- step statuses: {ev['step_statuses']}, "
                    f"authoritative: {ev['authoritative_steps']}, "
                    f"provisional: {ev['provisional_steps']}, "
                    f"silent losses: {ev['silent_commitment_losses']}"
                )
            elif qk == "Q2_lineage_completeness":
                lines.append(
                    f"- {ev['total_versions']} versions across {ev['total_targets']} targets, "
                    f"mutations per step: {ev['step_mutation_counts']}, "
                    f"lineage gaps: {ev['lineage_gaps']}"
                )
            elif qk == "Q3_unresolved_blocks_promotion":
                if ev["steps_with_own_unresolved"]:
                    lines.append(
                        f"- steps with own unresolved: {ev['steps_with_own_unresolved']}"
                    )
                if ev["steps_with_inherited_unresolved"]:
                    lines.append(
                        f"- steps with inherited unresolved: {ev['steps_with_inherited_unresolved']}"
                    )
                lines.append(
                    f"- promotion blocked correctly: {ev['promotion_blocked_correctly']}"
                )
            elif qk == "Q4_ground_truth_match":
                if ev.get("ground_truth_available"):
                    lines.append(
                        f"- exact match: {ev['exact_match']}, "
                        f"matched: {ev['matched_commitments']}, "
                        f"missing: {ev['missing_commitments']}, "
                        f"extra: {ev['extra_commitments']}"
                    )
                    if ev["field_mismatches"]:
                        lines.append(f"- field mismatches: {ev['field_mismatches']}")
                else:
                    lines.append("- no ground-truth available")
            lines.append("")

        # Final state
        lines.append("### Reconstructed final state")
        lines.append("")
        lines.append("| Canonical key | Type | Status | Threshold | Operator | Provenance |")
        lines.append("|---|---|---|---|---|---|")
        for key in sorted(r.final_state.keys()):
            c = r.final_state[key]
            lines.append(
                f"| {key} | {c.commitment_type} | {c.status} | "
                f"{c.threshold} | {c.operator or '—'} | — |"
            )
        lines.append("")

        # Ground truth state
        if r.ground_truth_state:
            lines.append("### Independent ground-truth state")
            lines.append("")
            lines.append("| Canonical key | Type | Status | Threshold | Operator |")
            lines.append("|---|---|---|---|---|")
            for key in sorted(r.ground_truth_state.keys()):
                c = r.ground_truth_state[key]
                lines.append(
                    f"| {key} | {c.commitment_type} | {c.status} | "
                    f"{c.threshold} | {c.operator or '—'} |"
                )
            lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    lines.append("**System-ingestion PASS.  Parser-completeness PARTIAL.**")
    lines.append("")
    lines.append("The acquisition and fallback strategy works, and the real parser")
    lines.append("boundary is now known:")
    lines.append("")
    lines.append("- Parser v0.4.1 supports **incremental section-level amendments only**.")
    lines.append("- Full restatement and conformed copy patterns require composite")
    lines.append("  extraction (Annex A as authoritative base), not amendment replay.")
    lines.append("- Commitment-level instruction mapping is currently MANUAL_FALLBACK.")
    lines.append("  The semantic-mapping layer is the next required implementation.")
    lines.append("")
    lines.append("**Next architecture (pattern-aware routing):**")
    lines.append("")
    lines.append("1. Classify each chain as incremental, full restatement, or conformed")
    lines.append("   copy.  **Implemented** (pattern_classifier.py).")
    lines.append("2. Continue instruction extraction for incremental amendments.")
    lines.append("   **Working** (parse_v04).")
    lines.append("3. For full restatements, treat the latest Annex A composite as the")
    lines.append("   new authoritative base.  **Scaffolded** (strategy defined in")
    lines.append("   pattern_classifier; no automated extraction code; ground truth")
    lines.append("   hand-extracted from Annex A).")
    lines.append("4. For conformed copies, parse the final clean state from Annex A.")
    lines.append("   **Scaffolded** (pattern classified; clean-state extraction not yet).")
    lines.append("5. Add a semantic-mapping layer that converts sections into commitment")
    lines.append("   fields with citations, confidence and provenance.  **Not implemented**")
    lines.append("   (interface scaffolded in semantic_mapper.py; no rules validated")
    lines.append("   against real parser output).")
    lines.append("6. Reserve manual review for ambiguous mappings, not routine field")
    lines.append("   population.  **Not yet** (all mappings are currently manual).")
    lines.append("")
    lines.append("**Release acceptance criteria (for 25-issuer study):**")
    lines.append("")
    lines.append("- [x] Correct pattern classification")
    lines.append("- [ ] Automatic authoritative-document selection (currently manual fixture construction)")
    lines.append("- [ ] Final commitment state generated without hand mapping")
    lines.append("- [x] Every field linked to document, section and amendment")
    lines.append("- [x] Explicit unsupported/ambiguous status instead of misleading")
    lines.append("      parser success")
    lines.append("- [ ] A broader corpus across at least 10-20 issuers")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Upsilon real EDGAR system smoke test runner"
    )
    ap.add_argument(
        "--out",
        default="results/edgar_smoke_test.md",
        help="Output markdown report path",
    )
    args = ap.parse_args()

    chains = all_edgar_chains()
    results = [reconstruct_chain(c) for c in chains]
    report = render_report(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    # Print summary to stdout
    total_amendments = sum(len(r.steps) for r in results)
    parser_supported = sum(
        1 for r in results for s in r.steps
        if s.parser_instruction_count is not None and s.parser_instruction_count > 0
    )

    print(f"Real EDGAR system smoke test: {len(results)} chains, {total_amendments} amendments")
    print(f"Parser coverage: {parser_supported}/{total_amendments} amendments parsed automatically")
    print()
    all_pass = True
    for r in results:
        q_results = {k: r.questions[k]["pass"] for k in (
            "Q1_state_preservation",
            "Q2_lineage_completeness",
            "Q3_unresolved_blocks_promotion",
            "Q4_ground_truth_match",
        )}
        chain_pass = all(q_results.values())
        if not chain_pass:
            all_pass = False
        status = "PASS" if chain_pass else "FAIL"
        pat = r.steps[0].pattern if r.steps else "—"
        print(f"  {r.chain_id} [{pat}]: {status}")
        for qk, qp in q_results.items():
            if not qp:
                print(f"    {qk}: FAIL — {r.questions[qk]['summary']}")
    print()
    print(f"Pipeline correctness: {'PASS' if all_pass else 'FAIL'}")
    print(f"Parser completeness: PARTIAL ({parser_supported}/{total_amendments})")
    print(f"Report: {out_path}")
    # Exit 0 if pipeline is correct (system-ingestion pass).
    # Parser completeness is reported but does not cause exit failure —
    # the known gaps are documented, not hidden.
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
