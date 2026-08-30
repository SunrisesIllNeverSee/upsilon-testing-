"""System smoke test runner.

Runs the end-to-end amendment-chain reconstruction smoke test on all
synthetic issuer chains and produces a markdown report answering the
four questions:

  Q1: Can Upsilon preserve authoritative state across multiple amendments?
  Q2: Can it maintain complete lineage from origin to current state?
  Q3: Does any unresolved instruction block authoritative promotion correctly?
  Q4: Does reconstructed state exactly match an independent authoritative
      document where one exists?

Usage:
    python run_smoke_test.py [--out results/system_smoke_test.md]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chain_reconstruction import ChainReconstructionResult, reconstruct_chain
from synthetic_chains import all_chains


def render_report(results: list[ChainReconstructionResult]) -> str:
    """Render the smoke-test results as a markdown report."""
    lines: list[str] = []
    lines.append("# Upsilon Synthetic System Smoke Test — End-to-End Chain Reconstruction")
    lines.append("")
    lines.append("This is the synthetic system smoke test for the Financial")
    lines.append("Commitment Integrity tester. It exercises the full pipeline:")
    lines.append("")
    lines.append("```text")
    lines.append("S0 original credit agreement")
    lines.append("↓")
    lines.append("A1 amendment  →  reconstruct S1")
    lines.append("↓")
    lines.append("A2 amendment  →  reconstruct S2")
    lines.append("↓")
    lines.append("...")
    lines.append("↓")
    lines.append("compare reconstructed current state")
    lines.append("against oracle ground-truth state at a specified comparison time")
    lines.append("```")
    lines.append("")
    lines.append("**Chains:** 5 synthetic oracle fixtures modeling real amendment-chain")
    lines.append("structure. The ground-truth states are hand-constructed in the same")
    lines.append("fixture module — these are oracle tests, not independent ground truth.")
    lines.append("Real multi-amendment chain acquisition from EDGAR is the next phase")
    lines.append("(25-issuer chain study).")
    lines.append("")
    lines.append("**System under test:** the real `executor.execute_amendment` and")
    lines.append("`persistence.build_persistence_plan` — no mocks.")
    lines.append("")
    lines.append("**Authority model:** chain-aware. A step is authoritative iff its")
    lines.append("own execution is COMPLETE AND no inherited unresolved uncertainty")
    lines.append("from ancestor amendments remains. A later clean amendment does NOT")
    lines.append("automatically erase inherited uncertainty — it must be explicitly")
    lines.append("resolved by targeting the same commitment.")
    lines.append("")

    # Summary table
    lines.append("## Summary")
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
            ("Q4_ground_truth_match", "Q4: Reconstructed state matches ground truth"),
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
                    lines.append("- no ground-truth composite/A&R available")
            lines.append("")

        # Final state
        lines.append("### Reconstructed final state")
        lines.append("")
        lines.append("| Canonical key | Type | Status | Threshold | Exceptions |")
        lines.append("|---|---|---|---|---|")
        for key in sorted(r.final_state.keys()):
            c = r.final_state[key]
            exc = ", ".join(str(e) for e in c.exceptions) if c.exceptions else "—"
            lines.append(
                f"| {key} | {c.commitment_type} | {c.status} | "
                f"{c.threshold} | {exc} |"
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
        lines.append(f"**ALL FOUR QUESTIONS PASS on all {len(results)} chains.**")
        lines.append("")
        lines.append("The synthetic system smoke test succeeds. Upsilon can:")
        lines.append("- preserve authoritative state across multiple amendments (Q1)")
        lines.append("- maintain complete lineage from origin to current state (Q2)")
        lines.append("- block authoritative promotion when instructions are unresolved,")
        lines.append("  including inherited unresolved from ancestor amendments (Q3)")
        lines.append("- reconstruct state that exactly matches the oracle ground truth (Q4)")
        lines.append("")
        lines.append("Authority model: chain-aware. A step is authoritative iff its own")
        lines.append("execution is COMPLETE AND no inherited unresolved uncertainty remains.")
        lines.append("")
        lines.append("Next phase: 25-issuer chain study with real EDGAR multi-amendment chains.")
    else:
        lines.append("**SMOKE TEST FAILED.** One or more questions failed on one or more chains.")
        lines.append("See per-chain detail above.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Upsilon system smoke test runner")
    ap.add_argument(
        "--out",
        default="results/system_smoke_test.md",
        help="Output markdown report path",
    )
    args = ap.parse_args()

    results = [reconstruct_chain(c) for c in all_chains()]
    report = render_report(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    # Print summary to stdout
    print(f"System smoke test: {len(results)} chains")
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
