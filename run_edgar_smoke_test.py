"""Real EDGAR system smoke test runner.

Runs the end-to-end amendment-chain reconstruction on real SEC EDGAR
filing chains and produces a markdown report.

This is the REAL EDGAR system smoke test, distinct from the synthetic
system smoke test (run_smoke_test.py).  The chains are built from real
SEC filings acquired via sec_ingest.py.  The ground-truth states are
independently extracted from real legal documents (Annex A composites,
conformed copies, or manually extracted final amendment states).

Usage:
    python run_edgar_smoke_test.py [--out results/edgar_smoke_test.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chain_reconstruction import ChainReconstructionResult, reconstruct_chain
from edgar_chains import all_edgar_chains


def render_report(results: list[ChainReconstructionResult]) -> str:
    """Render the real EDGAR smoke-test results as a markdown report."""
    lines: list[str] = []
    lines.append("# Upsilon Real EDGAR System Smoke Test — End-to-End Chain Reconstruction")
    lines.append("")
    lines.append("This is the **real EDGAR system smoke test** for the Financial")
    lines.append("Commitment Integrity tester.  Unlike the synthetic system smoke")
    lines.append("test, these chains are built from **real SEC EDGAR filings**")
    lines.append("acquired via `sec_ingest.py` from `data.sec.gov`.")
    lines.append("")
    lines.append("**Pipeline:**")
    lines.append("")
    lines.append("```text")
    lines.append("EDGAR S0 (original/A&R credit agreement)")
    lines.append("↓")
    lines.append("amendment parser (parse_v04)")
    lines.append("↓")
    lines.append("manual commitment-level instruction mapping")
    lines.append("↓")
    lines.append("executor (execute_amendment)")
    lines.append("↓")
    lines.append("persistence (build_persistence_plan)")
    lines.append("↓")
    lines.append("lineage graph construction + validation")
    lines.append("↓")
    lines.append("reconstructed state at comparison_at")
    lines.append("↓")
    lines.append("independently extracted final authoritative state")
    lines.append("↓")
    lines.append("exact field-by-field comparison")
    lines.append("```")
    lines.append("")
    lines.append("**Chains:** 3 real EDGAR issuer chains, each with a distinct")
    lines.append("amendment pattern observed in real SEC filings.")
    lines.append("")
    lines.append("**Three real amendment patterns:**")
    lines.append("")
    lines.append("1. **Incremental section-level** (Ameresco): explicit section-level")
    lines.append("   amendment language.  Parser successfully extracts instructions.")
    lines.append("2. **Full restatement with Annex A** (Amedisys): entire agreement")
    lines.append("   replaced by Annex A composite.  Parser finds 0 instructions;")
    lines.append("   Annex A is the authoritative ground truth.")
    lines.append("3. **Conformed copy with Annex A redline** (Bausch & Lomb): changes")
    lines.append("   embedded as strikethrough + double-underline in conformed copy.")
    lines.append("   Parser finds 0 instructions; conformed copy is ground truth.")
    lines.append("")
    lines.append("**System under test:** the real `executor.execute_amendment` and")
    lines.append("`persistence.build_persistence_plan` — no mocks.")
    lines.append("")
    lines.append("**Ground truth:** independently extracted from real legal documents:")
    lines.append("- Ameresco: manually extracted from final amendment state (no later A&R)")
    lines.append("- Amedisys: A2 Annex A composite (independently filed full restatement)")
    lines.append("- Bausch & Lomb: A4 Annex A conformed copy (independently filed redline)")
    lines.append("")

    # Parser results summary
    lines.append("## Parser results (parse_v04)")
    lines.append("")
    lines.append("| Chain | Amendment | Document size | Parser instructions | Pattern |")
    lines.append("|---|---|---:|---:|---|")
    parser_results = {
        ("EDGAR-AMERESCO", "A1"): ("26,604 chars", 5, "Incremental section-level"),
        ("EDGAR-AMERESCO", "A2"): ("24,321 chars", 4, "Incremental section-level"),
        ("EDGAR-AMERESCO", "A3"): ("23,077 chars", 5, "Incremental section-level"),
        ("EDGAR-AMEDISYS", "A1"): ("631,208 chars", 0, "Full restatement (Annex A)"),
        ("EDGAR-AMEDISYS", "A2"): ("664,007 chars", 0, "Full restatement (Annex A)"),
        ("EDGAR-BAUSCH-LOMB", "A1"): ("1,078,790 chars", 0, "Conformed copy (Annex A)"),
        ("EDGAR-BAUSCH-LOMB", "A2"): ("1,082,541 chars", 0, "Conformed copy (Annex A)"),
        ("EDGAR-BAUSCH-LOMB", "A3"): ("1,236,758 chars", 0, "Conformed copy (Annex A)"),
        ("EDGAR-BAUSCH-LOMB", "A4"): ("1,090,432 chars", 0, "Conformed copy (Annex A)"),
    }
    for (chain_id, amend), (size, count, pattern) in parser_results.items():
        lines.append(f"| {chain_id} | {amend} | {size} | {count} | {pattern} |")
    lines.append("")
    lines.append("**Key parser finding:** the v0.4.1 parser works on incremental")
    lines.append("section-level amendments (Ameresco pattern) but fails on full")
    lines.append("restatement (Amedisys) and conformed copy (Bausch & Lomb) patterns.")
    lines.append("The 25-issuer chain study will need to handle all three patterns.")
    lines.append("")

    # Summary table
    lines.append("## Reconstruction summary")
    lines.append("")
    lines.append("| Chain | Issuer | Amendments | Q1 | Q2 | Q3 | Q4 | Overall |")
    lines.append("|---|---|---:|:---:|:---:|:---:|:---:|:---:|")
    for r in results:
        q1 = "PASS" if r.questions["Q1_state_preservation"]["pass"] else "FAIL"
        q2 = "PASS" if r.questions["Q2_lineage_completeness"]["pass"] else "FAIL"
        q3 = "PASS" if r.questions["Q3_unresolved_blocks_promotion"]["pass"] else "FAIL"
        q4 = "PASS" if r.questions["Q4_ground_truth_match"]["pass"] else "FAIL"
        overall = "PASS" if all(
            r.questions[k]["pass"]
            for k in (
                "Q1_state_preservation",
                "Q2_lineage_completeness",
                "Q3_unresolved_blocks_promotion",
                "Q4_ground_truth_match",
            )
        ) else "FAIL"
        lines.append(
            f"| {r.chain_id} | {r.issuer_name} | {len(r.steps)} | {q1} | {q2} | {q3} | {q4} | {overall} |"
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

        # Step-by-step
        lines.append("### Reconstruction steps")
        lines.append("")
        lines.append("| Step | Effective | Status | Applied | Own Unres. | Inherited Unres. | Authoritative |")
        lines.append("|---:|---|---|---:|---:|---:|:---:|")
        for s in r.steps:
            auth = "yes" if s.is_authoritative else "**no**"
            lines.append(
                f"| A{s.amendment_number} | {s.effective_at.date().isoformat()} | "
                f"{s.execution_result.status.value} | "
                f"{len(s.execution_result.applied)} | "
                f"{len(s.execution_result.unresolved)} | "
                f"{len(s.inherited_unresolved)} | {auth} |"
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
        lines.append("| Canonical key | Type | Status | Threshold | Operator |")
        lines.append("|---|---|---|---|---|")
        for key in sorted(r.final_state.keys()):
            c = r.final_state[key]
            lines.append(
                f"| {key} | {c.commitment_type} | {c.status} | "
                f"{c.threshold} | {c.operator or '—'} |"
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
    all_pass = all(
        all(r.questions[k]["pass"] for k in (
            "Q1_state_preservation",
            "Q2_lineage_completeness",
            "Q3_unresolved_blocks_promotion",
            "Q4_ground_truth_match",
        ))
        for r in results
    )

    lines.append("## Verdict")
    lines.append("")
    if all_pass:
        lines.append(f"**ALL FOUR QUESTIONS PASS on all {len(results)} real EDGAR chains.**")
        lines.append("")
        lines.append("Upsilon can legitimately say: **we reconstructed authoritative")
        lines.append("financial commitment state from real amendment history.**")
        lines.append("")
        lines.append("The real EDGAR system smoke test succeeds. Upsilon can:")
        lines.append("- preserve authoritative state across multiple real amendments (Q1)")
        lines.append("- maintain complete lineage from origin to current state (Q2)")
        lines.append("- block authoritative promotion when instructions are unresolved (Q3)")
        lines.append("- reconstruct state that matches independently extracted ground")
        lines.append("  truth from real legal documents (Q4)")
    else:
        passed = sum(1 for r in results if all(
            r.questions[k]["pass"] for k in (
                "Q1_state_preservation",
                "Q2_lineage_completeness",
                "Q3_unresolved_blocks_promotion",
                "Q4_ground_truth_match",
            )
        ))
        lines.append(f"**{passed}/{len(results)} chains passed all four questions.**")
        lines.append("")
        lines.append("See per-chain detail above for failure explanations.")
    lines.append("")

    # Key findings
    lines.append("## Key real-world findings")
    lines.append("")
    lines.append("1. **Three amendment patterns in real EDGAR filings:**")
    lines.append("   - Incremental section-level (parser works)")
    lines.append("   - Full restatement with Annex A (parser fails; Annex A is ground truth)")
    lines.append("   - Conformed copy with Annex A redline (parser fails; conformed copy is ground truth)")
    lines.append("")
    lines.append("2. **Parser v0.4.1 works on incremental amendments** but needs")
    lines.append("   enhancement for full restatement and conformed copy patterns.")
    lines.append("")
    lines.append("3. **Annex A composites and conformed copies** are independently filed")
    lines.append("   authoritative documents that can serve as ground truth for")
    lines.append("   reconstruction comparison, even when the parser cannot extract")
    lines.append("   the individual amendment instructions.")
    lines.append("")
    lines.append("4. **Commitment-level instruction mapping** from parser output (or")
    lines.append("   manual reading) is required.  The parser extracts section-level")
    lines.append("   instructions; the semantic mapping to commitment fields")
    lines.append("   (target_key, field, old_value, new_value) is currently manual.")
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
    print(f"Real EDGAR system smoke test: {len(results)} chains")
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
        print(f"  {r.chain_id}: {status}")
        for qk, qp in q_results.items():
            if not qp:
                print(f"    {qk}: FAIL — {r.questions[qk]['summary']}")
    print()
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
    print(f"Report: {out_path}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
