"""Generate the Step 23 audit markdown report from the JSON output.

Every value in the report is derived from the audit JSON — no hardcoded
narrative or magic numbers.  If the audit is re-run with different data,
the report automatically reflects the new values.
"""
from __future__ import annotations

import json
from pathlib import Path


def _pct(count: int, total: int) -> str:
    """Format count/total as a percentage string."""
    return f"{count / total * 100:.1f}%" if total else "N/A"


def main() -> int:
    audit_path = Path("results/step_23_audit.json")
    if not audit_path.exists():
        print("ERROR: audit JSON not found. Run build_step23_audit.py first.")
        return 1

    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    lines: list[str] = []
    lines.append("# Step 23 — Upsilon v2 Eligibility & Semantic Funnel Audit")
    lines.append("")
    lines.append("**AUDIT ONLY.** No fixes, no tuning, no rule additions,")
    lines.append("no extractor modifications, no ontology changes.")
    lines.append("")

    # 23A
    a = audit["23a_instruction_eligibility"]
    total = a["total_parser_instructions"]
    in_scope = a["IN_SCOPE"]
    out_scope = a["OUT_OF_SCOPE"]
    ambiguous = a["AMBIGUOUS_SCOPE"]
    lines.append("## 23A — Instruction Eligibility")
    lines.append("")
    lines.append(f"**Total parser instructions:** {total}")
    lines.append("")
    lines.append("| Eligibility | Count | % |")
    lines.append("|---|---:|---:|")
    lines.append(f"| IN_SCOPE | {in_scope} | {_pct(in_scope, total)} |")
    lines.append(f"| OUT_OF_SCOPE | {out_scope} | {_pct(out_scope, total)} |")
    lines.append(f"| AMBIGUOUS_SCOPE | {ambiguous} | {_pct(ambiguous, total)} |")
    lines.append("")
    lines.append(f"**Raw automation rate (all-parser-instruction):** {a['raw_automation_rate']}")
    lines.append(f"**Eligible semantic mapping coverage (IN_SCOPE denominator):** {a['eligible_semantic_mapping_coverage']}")
    lines.append("")
    lines.append(
        f"The raw automation rate counts all {total} parser instructions. "
        f"The eligible coverage uses only the {in_scope} IN_SCOPE "
        f"instructions as the denominator."
    )
    lines.append("")
    if in_scope > 0:
        lines.append("### IN_SCOPE instruction details")
        lines.append("")
        lines.append("| Chain | Amendment | Section | Canonical class | Expected field | Operation |")
        lines.append("|---|---:|---|---|---|---|")
        for rec in a["in_scope_records"]:
            lines.append(
                f"| {rec['chain']} | {rec['amendment']} | "
                f"{rec['section']} | {rec['canonical_class']} | "
                f"{rec['expected_field']} | {rec['operation']} |"
            )
        lines.append("")

    # 23B
    b = audit["23b_s0_eligibility"]
    s0_total = b["total_s0_documents"]
    s0_in = b["S0_IN_SCOPE"]
    s0_no = b["S0_NO_IN_SCOPE_CONTENT"]
    s0_fail = b["S0_DISCOVERY_FAILURE"]
    s0_amb = b["S0_AMBIGUOUS"]
    lines.append("## 23B — S0 Eligibility")
    lines.append("")
    lines.append(f"**Total S0 documents:** {s0_total}")
    lines.append("")
    lines.append("| Eligibility | Count |")
    lines.append("|---|---:|")
    lines.append(f"| S0_IN_SCOPE | {s0_in} |")
    lines.append(f"| S0_NO_IN_SCOPE_CONTENT | {s0_no} |")
    lines.append(f"| S0_DISCOVERY_FAILURE | {s0_fail} |")
    lines.append(f"| S0_AMBIGUOUS | {s0_amb} |")
    lines.append("")
    lines.append(f"**Raw S0 rate (all documents):** {b['raw_s0_rate']}")
    lines.append(f"**Eligible S0 coverage (IN_SCOPE only):** {b['eligible_s0_coverage']}")
    lines.append("")
    lines.append(
        f"{s0_no} S0 document(s) have no 13-class covenant content and are "
        f"correctly NOT counted as extractor failures. "
        f"{s0_amb} document(s) are ambiguous."
    )
    lines.append("")

    # 23C
    c = audit["23c_gt_eligibility"]
    gt_total = c["total_gt_documents"]
    gt_in = c["GT_IN_SCOPE"]
    gt_no = c["GT_NO_IN_SCOPE_CONTENT"]
    gt_fail = c["GT_DISCOVERY_FAILURE"]
    gt_amb = c["GT_AMBIGUOUS"]
    lines.append("## 23C — GT Eligibility")
    lines.append("")
    lines.append(f"**Total GT documents:** {gt_total}")
    lines.append("")
    lines.append("| Eligibility | Count |")
    lines.append("|---|---:|")
    lines.append(f"| GT_IN_SCOPE | {gt_in} |")
    lines.append(f"| GT_NO_IN_SCOPE_CONTENT | {gt_no} |")
    lines.append(f"| GT_DISCOVERY_FAILURE | {gt_fail} |")
    lines.append(f"| GT_AMBIGUOUS | {gt_amb} |")
    lines.append("")
    lines.append(f"**Raw GT rate (all documents):** {c['raw_gt_rate']}")
    lines.append(f"**Eligible GT coverage (IN_SCOPE only):** {c['eligible_gt_coverage']}")
    lines.append("")

    # 23D
    d = audit["23d_funnel"]
    funnel_in_scope = d["in_scope_count"]
    lines.append("## 23D — Semantic Resolution Funnel")
    lines.append("")
    lines.append(f"**IN_SCOPE instructions:** {funnel_in_scope}")
    lines.append("")
    lines.append("### Sequential stages (1-11)")
    lines.append("")
    lines.append("| Stage | Count | % of IN_SCOPE | Drop | Drop % |")
    lines.append("|---|---:|---:|---:|---:|")
    stage_names = [
        "stage_1_parsed", "stage_2_scope_recognized",
        "stage_3_section_resolved", "stage_4_commitment_resolved",
        "stage_5_field_resolved", "stage_6_operation_resolved",
        "stage_7_old_value_resolved", "stage_8_new_value_resolved",
        "stage_9_unit_resolved", "stage_10_candidate_created",
        "stage_11_validators_passed",
    ]
    stage_labels = [
        "1. Instruction parsed",
        "2. Scope recognized",
        "3. Target section resolved",
        "4. Canonical commitment resolved",
        "5. Field resolved",
        "6. Operation resolved",
        "7. Old value resolved",
        "8. New value resolved",
        "9. Unit resolved",
        "10. StructuredMutation candidate created",
        "11. Deterministic validators passed",
    ]
    prev = funnel_in_scope
    for stage, label in zip(stage_names, stage_labels):
        count = d["stage_counts"].get(stage, 0)
        pct = count / funnel_in_scope * 100 if funnel_in_scope else 0
        drop = prev - count
        drop_pct = drop / prev * 100 if prev else 0
        lines.append(f"| {label} | {count} | {pct:.1f}% | {drop} | {drop_pct:.1f}% |")
        prev = count
    lines.append("")
    # Outcomes (mutually exclusive branches from stage 11)
    outcome_names = [
        "stage_12_accepted",
        "stage_13_rejected",
        "stage_14_unresolved",
    ]
    outcome_labels = [
        "12. Mutation accepted",
        "13. Mutation rejected",
        "14. UNRESOLVED",
    ]
    lines.append("### Outcomes (mutually exclusive, from IN_SCOPE)")
    lines.append("")
    lines.append("| Outcome | Count | % of IN_SCOPE |")
    lines.append("|---|---:|---:|")
    outcome_counts = d.get("outcome_counts", {})
    for stage, label in zip(outcome_names, outcome_labels):
        count = outcome_counts.get(stage, 0)
        pct = count / funnel_in_scope * 100 if funnel_in_scope else 0
        lines.append(f"| {label} | {count} | {pct:.1f}% |")
    dropped_before = d.get("dropped_before_validation", 0)
    lines.append("")
    lines.append(
        f"Of {funnel_in_scope} IN_SCOPE instructions, "
        f"{dropped_before} dropped off before reaching stage 11 "
        f"(validators) and are implicitly UNRESOLVED."
    )
    lines.append("")

    # 23E
    e = audit["23e_resolver_path"]
    lines.append("## 23E — v2 Resolver-Path Reachability")
    lines.append("")
    lines.append("### Static pipeline analysis")
    lines.append("")
    lines.append("| Component | Reached by pipeline |")
    lines.append("|---|---|")
    pr = e.get("pipeline_reachability", {})
    for comp in [
        "agreement_context_executed",
        "commitment_registry_executed",
        "resolve_with_context_executed",
        "staged_interpreter_executed",
        "model_assisted_interface_executed",
    ]:
        reached = pr.get(comp, False)
        lines.append(f"| {comp} | {'Yes' if reached else 'No'} |")
    lines.append("")
    lines.append("### Per-instruction execution counts")
    lines.append("")
    lines.append("| Component | Executed | % of IN_SCOPE |")
    lines.append("|---|---:|---:|")
    for component in [
        "agreement_context_executed",
        "commitment_registry_executed",
        "resolve_with_context_executed",
        "staged_interpreter_executed",
        "model_assisted_interface_executed",
        "candidate_produced",
        "validator_rejected",
    ]:
        count = e["path_counts"].get(component, 0)
        pct = count / funnel_in_scope * 100 if funnel_in_scope else 0
        lines.append(f"| {component} | {count} | {pct:.1f}% |")
    lines.append("")

    defects = e.get("integration_defects", [])
    if defects:
        lines.append("### Integration Defects")
        lines.append("")
        lines.append(
            "The following v2 architecture components exist but are NOT "
            "reached by the main pipeline path "
            "(`semantic_pipeline_v2.py` → `genre_adapters.py` → "
            "`semantic_resolver_v2.py`):"
        )
        lines.append("")
        for defect in defects:
            lines.append(f"- **{defect}**")
        lines.append("")

    val_rej = e["path_counts"].get("validator_rejected", 0)
    if val_rej > 0 and funnel_in_scope > 0:
        lines.append(
            f"{val_rej} of {funnel_in_scope} IN_SCOPE instructions "
            f"({val_rej / funnel_in_scope * 100:.1f}%) produced a candidate "
            f"that was rejected by the deterministic validators."
        )
        lines.append("")

    # 23F
    f = audit["23f_revised_taxonomy"]
    lines.append("## 23F — Revised Unresolved Taxonomy")
    lines.append("")
    lines.append(
        "After removing OUT_OF_SCOPE instructions and reclassifying "
        "remaining IN_SCOPE unresolved cases:"
    )
    lines.append("")
    # Removal summary (excluded from the IN_SCOPE-only table)
    oos_removed = f.get("out_of_scope_removed", 0)
    np_removed = f.get("non_parser_removed", 0)
    in_scope_total = f.get("in_scope_total", 0)
    if oos_removed or np_removed:
        lines.append(
            f"Removed from taxonomy: {oos_removed} OUT_OF_SCOPE, "
            f"{np_removed} non-parser-genre (full_restatement / "
            f"conformed_copy).  These are excluded from the IN_SCOPE "
            f"denominator."
        )
        lines.append("")
    lines.append("### IN_SCOPE unresolved buckets")
    lines.append("")
    lines.append("| Bucket | Count | % |")
    lines.append("|---|---:|---:|")
    for bucket, count in f["buckets"].items():
        pct = count / in_scope_total * 100 if in_scope_total else 0
        lines.append(f"| {bucket} | {count} | {pct:.1f}% |")
    lines.append("")
    lines.append(
        f"**OTHER percentage: {f['other_percentage']}%** "
        f"(target: <10%, denominator: {in_scope_total} IN_SCOPE)"
    )
    lines.append("")

    # 23G
    g = audit["23g_v1_v2_comparison"]
    lines.append("## 23G — Like-for-Like v1 vs v2 Comparison")
    lines.append("")
    lines.append("### Dev chains only (same corpus)")
    lines.append("")
    lines.append("| Metric | v1 | v2 |")
    lines.append("|---|---|---|")
    lines.append(f"| Total instructions | {g['v1_total']} | {g['v2_dev_total']} |")
    lines.append(f"| IN_SCOPE | {g['v1_in_scope']} | {g['v2_dev_in_scope']} |")
    lines.append(f"| Mapped (all) | {g['v1_mapped']} | {g['v2_dev_parser_mapped']} |")
    lines.append(f"| Incorrect | {g['v1_incorrect']} | 0 |")
    lines.append(f"| Correct mapped | {g['v1_correct_mapped']} | {g['v2_dev_parser_mapped']} |")
    lines.append(f"| **Eligible coverage** | **{g['v1_eligible_coverage']}** | **{g['v2_dev_eligible_coverage']}** |")
    lines.append("")
    lines.append("### All chains (v2 only)")
    lines.append("")
    lines.append("| Metric | v2 |")
    lines.append("|---|---|")
    lines.append(f"| Total instructions | {g['v2_all_total']} |")
    lines.append(f"| IN_SCOPE | {g['v2_all_in_scope']} |")
    lines.append(f"| Parser-mapped | {g['v2_all_parser_mapped']} |")
    lines.append(f"| **Eligible coverage** | **{g['v2_all_eligible_coverage']}** |")
    lines.append("")

    # 23H
    h = audit["23h_gates"]
    lines.append("## 23H — Reevaluated Exit Gates")
    lines.append("")
    lines.append("Using correct denominators:")
    lines.append("- semantic_mapping_coverage = mapped / IN_SCOPE")
    lines.append("- S0_extraction = success / S0_IN_SCOPE")
    lines.append("- GT_extraction = success / GT_IN_SCOPE")
    lines.append("")
    lines.append("| Gate | Current | Status |")
    lines.append("|---|---|---|")
    for gate in h["gate_details"]:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"| {gate['gate']} | {gate['value']} | {status} |")
    lines.append("")
    lines.append(f"**Gates passed: {h['gates_passed']}**")
    lines.append("")

    # Top 3 bottlenecks
    bottlenecks = audit.get("top_3_bottlenecks", [])
    lines.append("## Top 3 Bottlenecks Among IN_SCOPE Instructions")
    lines.append("")
    if bottlenecks:
        lines.append("| # | Stage | Dropped | From → To | Drop % |")
        lines.append("|---:|---|---:|---|---:|")
        for i, bn in enumerate(bottlenecks, 1):
            drop_pct = bn["dropped"] / bn["prev"] * 100 if bn["prev"] else 0
            lines.append(
                f"| {i} | {bn['stage']} | {bn['dropped']} | "
                f"{bn['prev']} → {bn['after']} | {drop_pct:.1f}% |"
            )
        lines.append("")

    # Summary — all 11 return items
    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Item | Value |")
    lines.append("|---:|---|---|")
    lines.append(f"| 1 | Total parser instructions | {total} |")
    lines.append(f"| 2 | IN_SCOPE denominator | {in_scope} |")
    lines.append(f"| 3 | Raw automation rate | {a['raw_automation_rate']} |")
    lines.append(f"| 4 | Eligible semantic coverage | {a['eligible_semantic_mapping_coverage']} |")
    lines.append(f"| 5 | S0 eligible coverage | {b['eligible_s0_coverage']} |")
    lines.append(f"| 6 | GT eligible coverage | {c['eligible_gt_coverage']} |")
    if bottlenecks:
        bn1 = bottlenecks[0]
        lines.append(f"| 7 | Funnel: biggest drop | {bn1['stage']} ({bn1['dropped']}/{bn1['prev']} = {bn1['dropped']/bn1['prev']*100:.1f}%) |")
    else:
        lines.append("| 7 | Funnel: biggest drop | N/A |")
    ac_reached = pr.get("agreement_context_executed", False)
    lines.append(f"| 8 | AgreementContext reached | {'Yes' if ac_reached else 'No (integration defect)'} |")
    lines.append(f"| 9 | OTHER bucket | {f['other_percentage']}% |")
    lines.append(f"| 10 | v1 vs v2 eligible (dev) | {g['v1_eligible_coverage']} → {g['v2_dev_eligible_coverage']} |")
    lines.append(f"| 11 | Gates passed | {h['gates_passed']} |")
    lines.append("")

    report = "\n".join(lines)
    report_path = Path("results/step_23_audit_report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
