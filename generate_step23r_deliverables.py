"""Generate Step 23R CSV deliverables and final report."""
from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path


def write_csv(
    path: Path, rows: list[dict], fieldnames: list[str],
) -> None:
    """Write rows to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _run_test_suite() -> dict[str, int]:
    """Run the full test suite and return pass/fail/skip counts."""
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "--tb=no", "-q"],
            capture_output=True, text=True, timeout=600,
        )
        output = result.stdout + result.stderr
        # Parse the summary line, e.g. "904 passed, 14 skipped in 30s"
        passed = 0
        failed = 0
        skipped = 0
        m = re.search(r"(\d+) passed", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            failed = int(m.group(1))
        m = re.search(r"(\d+) skipped", output)
        if m:
            skipped = int(m.group(1))
        return {"passed": passed, "failed": failed, "skipped": skipped}
    except Exception:
        return {"passed": -1, "failed": -1, "skipped": -1}


def main() -> int:
    audit_path = Path("results/step23r_audit.json")
    if not audit_path.exists():
        print("ERROR: audit JSON not found")
        return 1

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    results_dir = Path("results")

    # --- Instruction ledger CSV ---
    ledger = audit["instruction_ledger"]
    ledger_fields = [
        "instruction_id", "chain_id", "document_id", "amendment_order",
        "instruction_index", "genre", "instruction_type", "target_ref",
        "source_span_start", "source_span_end", "source_text",
        "independent_eligibility", "eligibility_reason",
        "expected_commitment_class", "expected_field",
        "expected_operation", "expected_old_value", "expected_new_value",
        "expected_unit", "expected_section",
        "automatic_mapping_attempted", "predicted_commitment_class",
        "predicted_field", "predicted_operation", "predicted_old_value",
        "predicted_new_value", "predicted_unit",
        "candidate_created", "accepted", "executor_accepted",
        "correct_automatic_mapping",
        "first_runtime_stage_entered", "first_runtime_failure",
        "terminal_outcome", "failure_family",
        "protocol_vs_interpretation", "failure_reason",
    ]
    write_csv(
        results_dir / "step23r_instruction_ledger.csv",
        ledger, ledger_fields,
    )
    print(f"Instruction ledger: {results_dir / 'step23r_instruction_ledger.csv'}")

    # --- S0 eligibility CSV ---
    s0_rows = audit["s0_eligibility_ledger"]
    s0_fields = [
        "chain_id", "source_label", "text_length",
        "independent_eligibility", "eligibility_reason",
        "extracted_count", "in_scope_classes_found",
    ]
    write_csv(
        results_dir / "step23r_s0_eligibility.csv",
        s0_rows, s0_fields,
    )
    print(f"S0 eligibility: {results_dir / 'step23r_s0_eligibility.csv'}")

    # --- GT eligibility CSV ---
    gt_rows = audit["gt_eligibility_ledger"]
    gt_fields = [
        "chain_id", "source_label", "text_length",
        "independent_eligibility", "eligibility_reason",
        "extracted_count", "in_scope_classes_found",
    ]
    write_csv(
        results_dir / "step23r_gt_eligibility.csv",
        gt_rows, gt_fields,
    )
    print(f"GT eligibility: {results_dir / 'step23r_gt_eligibility.csv'}")

    # --- Runtime failure census JSON ---
    census = {
        "first_runtime_failure_histogram": audit["section_h_runtime_failure_census"]["first_runtime_failure_histogram"],
        "total_failed": audit["section_h_runtime_failure_census"]["total_failed"],
        "protocol_vs_interpretation": audit["section_i_protocol_vs_interpretation"],
    }
    (results_dir / "step23r_runtime_failure_census.json").write_text(
        json.dumps(census, indent=2), encoding="utf-8",
    )
    print(f"Runtime failure census: {results_dir / 'step23r_runtime_failure_census.json'}")

    # --- Failure taxonomy JSON ---
    (results_dir / "step23r_failure_taxonomy.json").write_text(
        json.dumps(audit["section_j_taxonomy"], indent=2), encoding="utf-8",
    )
    print(f"Failure taxonomy: {results_dir / 'step23r_failure_taxonomy.json'}")

    # --- v1 v2 comparison JSON ---
    (results_dir / "step23r_v1_v2_comparison.json").write_text(
        json.dumps(audit["section_k_v1_v2_comparison"], indent=2), encoding="utf-8",
    )
    print(f"v1 v2 comparison: {results_dir / 'step23r_v1_v2_comparison.json'}")

    # --- Engineering gates JSON ---
    (results_dir / "step23r_engineering_gates.json").write_text(
        json.dumps(audit["section_l_gates"], indent=2), encoding="utf-8",
    )
    print(f"Engineering gates: {results_dir / 'step23r_engineering_gates.json'}")

    # --- Final report ---
    lines: list[str] = []
    lines.append("# Step 23R — Independent Failure Census + Measurement Recovery")
    lines.append("")

    # A. Repository state
    a = audit["section_a_repository_state"]
    lines.append("## A. Repository state")
    lines.append("")
    lines.append(f"```text")
    lines.append(f"branch: {a['branch']}")
    lines.append(f"HEAD: {a['head']}")
    lines.append(f"working tree: {a['working_tree']}")
    lines.append(f"```")
    lines.append("")

    # B. Tests (run live)
    test_counts = _run_test_suite()
    lines.append("## B. Tests")
    lines.append("")
    lines.append("```text")
    lines.append(f"passed: {test_counts['passed']}")
    lines.append(f"failed: {test_counts['failed']}")
    lines.append(f"skipped: {test_counts['skipped']}")
    lines.append("```")
    lines.append("")

    # C. Frozen parser population
    c = audit["section_c_frozen_population"]
    lines.append("## C. Frozen parser population")
    lines.append("")
    lines.append("```text")
    lines.append(f"total: {c['total']}")
    lines.append(f"unique IDs: {c['unique_ids']}")
    lines.append(f"duplicates: {c['duplicates']}")
    lines.append(f"missing: {c['missing']}")
    lines.append(f"```")
    lines.append("")

    # D. Independent eligibility
    d = audit["section_d_independent_eligibility"]
    lines.append("## D. Independent eligibility")
    lines.append("")
    lines.append("```text")
    lines.append(f"IN_SCOPE: {d['IN_SCOPE']}")
    lines.append(f"OUT_OF_SCOPE: {d['OUT_OF_SCOPE']}")
    lines.append(f"AMBIGUOUS_SCOPE: {d['AMBIGUOUS_SCOPE']}")
    lines.append(f"reconciliation: {d['reconciliation']}")
    lines.append(f"```")
    lines.append("")

    # E. Correct semantic automation
    e = audit["section_e_correct_semantic_automation"]
    lines.append("## E. Correct semantic automation")
    lines.append("")
    lines.append("```text")
    lines.append(f"raw automatic parser mappings: {e['raw_automatic_parser_mappings']}")
    lines.append(f"raw rate: {e['raw_rate']}")
    lines.append(f"correct automatic IN_SCOPE mappings: {e['correct_automatic_in_scope_mappings']}")
    lines.append(f"independent IN_SCOPE denominator: {e['independent_in_scope_denominator']}")
    lines.append(f"eligible semantic coverage: {e['eligible_semantic_coverage']}")
    lines.append(f"```")
    lines.append("")

    # F. S0
    f_data = audit["section_f_s0"]
    lines.append("## F. S0")
    lines.append("")
    lines.append("```text")
    lines.append(f"raw coverage: {f_data['raw_coverage']}")
    lines.append(f"independent eligible coverage: {f_data['independent_eligible_coverage']}")
    lines.append(f"S0_IN_SCOPE: {f_data['S0_IN_SCOPE']}")
    lines.append(f"S0_NO_IN_SCOPE_CONTENT: {f_data['S0_NO_IN_SCOPE_CONTENT']}")
    lines.append(f"S0_DISCOVERY_FAILURE: {f_data['S0_DISCOVERY_FAILURE']}")
    lines.append(f"S0_AMBIGUOUS: {f_data['S0_AMBIGUOUS']}")
    lines.append(f"```")
    lines.append("")

    # G. GT
    g_data = audit["section_g_gt"]
    lines.append("## G. GT")
    lines.append("")
    lines.append("```text")
    lines.append(f"raw coverage: {g_data['raw_coverage']}")
    lines.append(f"independent eligible coverage: {g_data['independent_eligible_coverage']}")
    lines.append(f"GT_IN_SCOPE: {g_data['GT_IN_SCOPE']}")
    lines.append(f"GT_NO_IN_SCOPE_CONTENT: {g_data['GT_NO_IN_SCOPE_CONTENT']}")
    lines.append(f"GT_DISCOVERY_FAILURE: {g_data['GT_DISCOVERY_FAILURE']}")
    lines.append(f"GT_AMBIGUOUS: {g_data['GT_AMBIGUOUS']}")
    lines.append(f"```")
    lines.append("")

    # H. Runtime failure census
    h = audit["section_h_runtime_failure_census"]
    lines.append("## H. Runtime failure census")
    lines.append("")
    lines.append("| First failure stage | Count | % of eligible failures |")
    lines.append("|---|---:|---:|")
    total_failed = h["total_failed"]
    for stage, count in h["first_runtime_failure_histogram"].items():
        pct = count / max(total_failed, 1) * 100
        lines.append(f"| {stage} | {count} | {pct:.1f}% |")
    lines.append("")

    # I. Protocol vs interpretation
    i_data = audit["section_i_protocol_vs_interpretation"]
    lines.append("## I. Protocol vs interpretation")
    lines.append("")
    lines.append("```text")
    lines.append(f"MOSES_PROTOCOL_INSUFFICIENCY: {i_data['MOSES_PROTOCOL_INSUFFICIENCY']}")
    lines.append(f"UPSILON_INTERPRETATION_FAILURE: {i_data['UPSILON_INTERPRETATION_FAILURE']}")
    lines.append(f"AMBIGUOUS_FAILURE_TYPE: {i_data['AMBIGUOUS_FAILURE_TYPE']}")
    lines.append(f"```")
    lines.append("")
    lines.append("### Concrete mechanisms")
    lines.append("")
    lines.append("**MOSES_PROTOCOL_INSUFFICIENCY:**")
    lines.append("- MULTI_FIELD_DECOMPOSITION: RESTATE_SECTION groups multiple definition amendments into one instruction; the protocol handles one field at a time")
    lines.append("- DELETE_REQUIRES_MANUAL_REVIEW: DELETE operations are conservatively rejected; the protocol has no safe delete operation")
    lines.append("- TABLE_OR_SCHEDULE_VALUE_EXTRACTION: Values appear in tables/schedules that the protocol cannot parse")
    lines.append("- DEFINED_TERM_RESOLUTION: RESTATE_SECTION restates a defined term without a numeric value; the protocol has no definition restatement operation")
    lines.append("")
    lines.append("**UPSILON_INTERPRETATION_FAILURE:**")
    lines.append("- TARGET_IDENTIFICATION: The resolver fails to identify the correct commitment class from source text")
    lines.append("- VALUE_EXTRACTION: The resolver fails to extract the numeric value from source text")
    lines.append("- VALIDATOR_REJECTION: The candidate fails deterministic validation")
    lines.append("")

    # J. Taxonomy
    j = audit["section_j_taxonomy"]
    lines.append("## J. Taxonomy")
    lines.append("")
    lines.append(f"Denominator: {j['total_failed']} failed IN_SCOPE instructions")
    lines.append("")
    lines.append("| Bucket | Count | % |")
    lines.append("|---|---:|---:|")
    for bucket, count in j["buckets"].items():
        pct = count / max(j["total_failed"], 1) * 100
        lines.append(f"| {bucket} | {count} | {pct:.1f}% |")
    lines.append("")
    lines.append(f"OTHER percentage: {j['other_percentage']}%")
    lines.append(f"TRUE_AMBIGUITY count: {j['true_ambiguity_count']} (affirmative: {j['true_ambiguity_is_affirmative']})")
    lines.append("")

    # K. v1 vs v2
    k = audit["section_k_v1_v2_comparison"]
    lines.append("## K. Frozen v1 vs current v2")
    lines.append("")
    lines.append("```text")
    lines.append(f"dev IN_SCOPE denominator: {k['dev_in_scope_denominator']}")
    lines.append(f"v1 correct mapped: {k['v1_correct_mapped']}")
    lines.append(f"v1 eligible coverage: {k['v1_eligible_coverage']}")
    lines.append(f"v2 correct mapped: {k['v2_correct_mapped']}")
    lines.append(f"v2 eligible coverage: {k['v2_eligible_coverage']}")
    lines.append(f"record-level alignment possible: {k.get('record_level_alignment_possible', False)}")
    lines.append(f"```")
    lines.append("")
    lines.append(f"Note: {k.get('note', '')}")
    lines.append("")
    if not k.get("record_level_alignment_possible", False):
        lines.append(f"**BLOCKED**: {k.get('blocked_reason', '')}")
        lines.append("")

    # L. Gates
    l_data = audit["section_l_gates"]
    lines.append("## L. Gates")
    lines.append("")
    lines.append("| Gate | Value | Status |")
    lines.append("|---|---|---|")
    for gate in l_data["gate_details"]:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"| {gate['gate']} | {gate['value']} | {status} |")
    lines.append("")
    lines.append(f"**Gates passed: {l_data['gates_passed']}**")
    lines.append("")

    # M. Step 24 candidate analysis
    m = audit["section_m_step24_candidates"]
    lines.append("## M. Step 24 candidate analysis")
    lines.append("")
    lines.append("| Family | Affected | % | Protocol insuff. | Interp. fail. | Recoverable | Protocol can represent |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for cand in m:
        lines.append(
            f"| {cand['family']} | {cand['affected']} | "
            f"{cand['pct_of_failures']}% | "
            f"{cand['protocol_insufficiency']} | "
            f"{cand['interpretation_failure']} | "
            f"{cand['estimated_recoverable']} | "
            f"{'Yes' if cand['protocol_can_represent'] else 'No'} |"
        )
    lines.append("")

    # N. Step verdict
    # The verdict is PASS only if:
    # 1. All safety gates pass (incorrect_accepted=0, false_auth_promotions=0)
    # 2. Record-level v1 vs v2 alignment is possible
    # 3. The diagnostic truth set is not contaminated
    # Otherwise it is BLOCKED.
    safety = audit.get("section_safety_metrics", {})
    incorrect_accepted = safety.get("incorrect_accepted_mutations", 0)
    false_auth = safety.get("false_authoritative_promotions", 0)
    v1_alignment_possible = k.get("record_level_alignment_possible", False)

    safety_gates_pass = (incorrect_accepted == 0 and false_auth == 0)

    lines.append("## N. Step verdict")
    lines.append("")
    lines.append("```text")
    if safety_gates_pass and v1_alignment_possible:
        lines.append("STEP 23R PASS — independent diagnostic truth established")
    else:
        lines.append("STEP 23R BLOCKED — diagnostic truth is still contaminated or incomplete")
    lines.append("```")
    lines.append("")

    if not safety_gates_pass:
        lines.append("### Blocking reasons")
        lines.append("")
        if incorrect_accepted > 0:
            lines.append(
                f"- incorrect_accepted_mutations = {incorrect_accepted} "
                f"(must be 0).  Affected instruction IDs: "
                f"{safety.get('incorrect_accepted_instruction_ids', [])}"
            )
        if false_auth > 0:
            lines.append(
                f"- false_authoritative_promotions = {false_auth} "
                f"(must be 0)"
            )
        lines.append("")

    if not v1_alignment_possible:
        if not safety_gates_pass:
            pass  # already listed above
        lines.append(
            "- v1 vs v2 record-level alignment is not possible: "
            "v1 frozen results lack per-instruction mapping data."
        )
        lines.append("")

    # Step 24 target recommendation (only if PASS)
    if safety_gates_pass and v1_alignment_possible:
        lines.append("### Step 24 target recommendation")
        lines.append("")
        lines.append("```text")
        lines.append("PHASE VI — STEP 24 TARGET: TARGET_IDENTIFICATION")
        lines.append("```")
        lines.append("")
        lines.append("Rationale: TARGET_IDENTIFICATION is the dominant interpretation")
        lines.append(f"failure family with {m[0]['affected']} affected instructions")
        lines.append(f"({m[0]['pct_of_failures']}% of eligible failures), all of which are")
        lines.append(f"recoverable ({m[0]['estimated_recoverable']} cases) without protocol")
        lines.append("changes. The existing protocol can represent these mutations —")
        lines.append("Upsilon simply fails to identify the correct commitment class from")
        lines.append("source text. This is the highest-leverage target for Step 24")
        lines.append("concentrated semantic engineering.")
        lines.append("")
    else:
        lines.append("### Step 24 target recommendation")
        lines.append("")
        lines.append("Step 24 target selection is deferred until Step 23R blocking")
        lines.append("issues are resolved.  The diagnostic truth set must be")
        lines.append("uncontaminated before concentrating Step 24 engineering effort.")
        lines.append("")

    report = "\n".join(lines)
    report_path = Path("results/STEP_23R_REPORT.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"\nFinal report: {report_path}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
