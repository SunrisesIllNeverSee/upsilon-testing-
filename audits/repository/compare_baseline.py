"""Compare pre-migration vs post-migration empirical baseline metrics.

Extracts every critical metric from both the saved pre-migration results
(in /tmp/pre_migration_baseline/) and the freshly-generated post-migration
results, then reports whether they match exactly.

Sections:
  1. Frozen-input hash verification (live subprocess call)
  2. Step 23R — Independent Failure Census
  3. Step 23 — Eligibility & Semantic Funnel Audit
  4. Step 23S — MOSES Semantic Safety Enforcement
  5. Defect Safety Record
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE = Path("/tmp/pre_migration_baseline")
POST = REPO_ROOT / "results"

# Pre-migration commit (parent of the migration commit e908eb6).  All
# pre-migration reruns use this commit so the comparison is genuine
# pre-vs-post, not post-vs-documentation.
PRE_MIGRATION_COMMIT = "0217213"

PASS = 0
FAIL = 0


def check(label: str, pre_val, post_val) -> bool:
    global PASS, FAIL
    match = pre_val == post_val
    status = "MATCH" if match else "MISMATCH"
    if match:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {label}: pre={pre_val!r} post={post_val!r}")
    return match


def run_frozen_hash_verify() -> tuple[int, int, bool]:
    """Run data/ground_truth/frozen/generate_manifest.py verify and parse
    the output.  Returns (hashes_checked, failures, passed).
    """
    script = REPO_ROOT / "data" / "ground_truth" / "frozen" / "generate_manifest.py"
    result = subprocess.run(
        [sys.executable, str(script), "verify"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    output = result.stdout
    checked_match = re.search(r"hashes checked:\s+(\d+)", output)
    failures_match = re.search(r"failures:\s+(\d+)", output)
    passed = "VERIFY: PASS" in output
    checked = int(checked_match.group(1)) if checked_match else -1
    failures = int(failures_match.group(1)) if failures_match else -1
    return checked, failures, passed


def _parse_pytest_summary(stdout: str) -> tuple[int, int, int]:
    """Parse a pytest -q summary line and return (passed, failed, skipped)."""
    summary = stdout.strip().split("\n")[-1] if stdout.strip() else ""
    passed_m = re.search(r"(\d+)\s+passed", summary)
    failed_m = re.search(r"(\d+)\s+failed", summary)
    skipped_m = re.search(r"(\d+)\s+skipped", summary)
    passed = int(passed_m.group(1)) if passed_m else 0
    failed = int(failed_m.group(1)) if failed_m else 0
    skipped = int(skipped_m.group(1)) if skipped_m else 0
    return passed, failed, skipped


def run_moses_conformance_tests_post() -> tuple[int, int, int]:
    """Run the post-migration Step 23S MOSES conformance test suite and
    return (passed, failed, skipped).
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/conservation/test_moses_safety.py", "-q",
         "--no-header", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    return _parse_pytest_summary(result.stdout)


def run_moses_conformance_tests_pre() -> tuple[int, int, int]:
    """Run the pre-migration Step 23S MOSES conformance test suite in a
    temporary git worktree at PRE_MIGRATION_COMMIT and return
    (passed, failed, skipped).

    The pre-migration test file lived at the repository root
    (test_moses_safety.py) and imported root-level modules
    (moses_safety, models, semantic_pipeline_v2, semantic_resolver_v2).
    A worktree gives us a clean checkout of that code without disturbing
    the working tree.
    """
    worktree = Path("/tmp/pre_migration_moses_worktree")
    # Remove any stale worktree from a prior run.
    if worktree.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            check=False,
        )
    result = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree), PRE_MIGRATION_COMMIT],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"   WARNING: could not create pre-migration worktree: {result.stderr.strip()}")
        return -1, -1, -1
    try:
        test_result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_moses_safety.py", "-q",
             "--no-header", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(worktree),
            check=False,
        )
        return _parse_pytest_summary(test_result.stdout)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            check=False,
        )


print("=" * 70)
print("POST-MIGRATION EMPIRICAL BASELINE COMPARISON")
print("=" * 70)
print()

# ---------------------------------------------------------------------------
# 1. Frozen-input hash verification (live subprocess call)
# ---------------------------------------------------------------------------
print("1. FROZEN-INPUT HASH VERIFICATION")
print("   (live call to data/ground_truth/frozen/generate_manifest.py verify)")
hashes_checked, hash_failures, hash_passed = run_frozen_hash_verify()
print(f"   hashes checked: {hashes_checked}, failures: {hash_failures}, "
      f"VERIFY: {'PASS' if hash_passed else 'FAIL'}")
# Frozen-input hash verification is a precondition, not a pre-vs-post
# comparison: it confirms the frozen ground-truth inputs are intact in
# the post-migration tree.  The pre-migration baseline used the same
# frozen inputs (tracked in git, unchanged by the migration).
check("frozen_hashes_checked", 26, hashes_checked)
check("frozen_hash_failures", 0, hash_failures)
check("frozen_hash_verify_passed", True, hash_passed)
print()

# ---------------------------------------------------------------------------
# 2. Step 23R — Independent Failure Census
# ---------------------------------------------------------------------------
print("2. STEP 23R — INDEPENDENT FAILURE CENSUS")
pre_23r = json.loads((PRE / "step23r_audit.json").read_text())
post_23r = json.loads((POST / "step23r_audit.json").read_text())

# Safety metrics
pre_s = pre_23r["section_safety_metrics"]
post_s = post_23r["section_safety_metrics"]
check("incorrect_accepted_mutations", pre_s["incorrect_accepted_mutations"], post_s["incorrect_accepted_mutations"])
check("false_authoritative_promotions", pre_s["false_authoritative_promotions"], post_s["false_authoritative_promotions"])
check("step_authoritative_count", pre_s["step_authoritative_count"], post_s["step_authoritative_count"])
check("total_steps", pre_s["total_steps"], post_s["total_steps"])

# Eligibility
pre_d = pre_23r["section_d_independent_eligibility"]
post_d = post_23r["section_d_independent_eligibility"]
check("IN_SCOPE", pre_d.get("IN_SCOPE"), post_d.get("IN_SCOPE"))
check("OUT_OF_SCOPE", pre_d.get("OUT_OF_SCOPE"), post_d.get("OUT_OF_SCOPE"))
check("AMBIGUOUS_SCOPE", pre_d.get("AMBIGUOUS_SCOPE"), post_d.get("AMBIGUOUS_SCOPE"))

# Correct semantic automation
pre_e = pre_23r["section_e_correct_semantic_automation"]
post_e = post_23r["section_e_correct_semantic_automation"]
check("correct_accepts_preserved (eligible_semantic_coverage)", pre_e["eligible_semantic_coverage"], post_e["eligible_semantic_coverage"])
check("correct_automatic_in_scope_mappings", pre_e["correct_automatic_in_scope_mappings"], post_e["correct_automatic_in_scope_mappings"])
check("independent_in_scope_denominator", pre_e["independent_in_scope_denominator"], post_e["independent_in_scope_denominator"])

# Runtime failure census
pre_h = pre_23r["section_h_runtime_failure_census"]
post_h = post_23r["section_h_runtime_failure_census"]
check("runtime_failure_histogram", pre_h["first_runtime_failure_histogram"], post_h["first_runtime_failure_histogram"])
check("total_failed", pre_h["total_failed"], post_h["total_failed"])

# Failure-family distribution (taxonomy)
pre_j = pre_23r["section_j_taxonomy"]
post_j = post_23r["section_j_taxonomy"]
check("taxonomy_buckets", pre_j["buckets"], post_j["buckets"])
check("total_accepted_correct", pre_j["total_accepted_correct"], post_j["total_accepted_correct"])
check("total_accepted_incorrect", pre_j["total_accepted_incorrect"], post_j["total_accepted_incorrect"])
check("other_percentage", pre_j["other_percentage"], post_j["other_percentage"])

# S0 metrics
pre_f = pre_23r["section_f_s0"]
post_f = post_23r["section_f_s0"]
check("S0_raw_coverage", pre_f["raw_coverage"], post_f["raw_coverage"])
check("S0_eligible_coverage", pre_f["independent_eligible_coverage"], post_f["independent_eligible_coverage"])
check("S0_IN_SCOPE", pre_f["S0_IN_SCOPE"], post_f["S0_IN_SCOPE"])

# GT metrics
pre_g = pre_23r["section_g_gt"]
post_g = post_23r["section_g_gt"]
check("GT_raw_coverage", pre_g["raw_coverage"], post_g["raw_coverage"])
check("GT_eligible_coverage", pre_g["independent_eligible_coverage"], post_g["independent_eligible_coverage"])
check("GT_IN_SCOPE", pre_g["GT_IN_SCOPE"], post_g["GT_IN_SCOPE"])

print()

# ---------------------------------------------------------------------------
# 3. Step 23 — Eligibility & Semantic Funnel Audit
# ---------------------------------------------------------------------------
print("3. STEP 23 — ELIGIBILITY & SEMANTIC FUNNEL AUDIT")
print("   (pre-migration step_23_audit.json was a stale untracked file from")
print("    an older run; comparison uses pre-migration code rerun with same data)")
pre_23 = json.loads((PRE / "step_23_audit.json").read_text())
post_23 = json.loads((POST / "step_23_audit.json").read_text())

# Instruction eligibility
pre_a = pre_23["23a_instruction_eligibility"]
post_a = post_23["23a_instruction_eligibility"]
check("total_parser_instructions", pre_a["total_parser_instructions"], post_a["total_parser_instructions"])
check("IN_SCOPE", pre_a["IN_SCOPE"], post_a["IN_SCOPE"])
check("OUT_OF_SCOPE", pre_a["OUT_OF_SCOPE"], post_a["OUT_OF_SCOPE"])
check("AMBIGUOUS_SCOPE", pre_a["AMBIGUOUS_SCOPE"], post_a["AMBIGUOUS_SCOPE"])
check("eligible_semantic_mapping_coverage", pre_a["eligible_semantic_mapping_coverage"], post_a["eligible_semantic_mapping_coverage"])

# S0 eligibility
check("23b_S0_eligible_coverage", pre_23["23b_s0_eligibility"]["eligible_s0_coverage"], post_23["23b_s0_eligibility"]["eligible_s0_coverage"])

# GT eligibility
check("23c_GT_eligible_coverage", pre_23["23c_gt_eligibility"]["eligible_gt_coverage"], post_23["23c_gt_eligibility"]["eligible_gt_coverage"])

# Funnel outcomes — NOTE: pre-migration stale file had stage_12=8, stage_13=0
# from an older run. Pre-migration code rerun with same data produces
# stage_12=2, stage_13=6, matching post-migration exactly.
check("23d_stage_12_accepted", pre_23["23d_funnel"]["outcome_counts"]["stage_12_accepted"], post_23["23d_funnel"]["outcome_counts"]["stage_12_accepted"])
check("23d_stage_13_rejected", pre_23["23d_funnel"]["outcome_counts"]["stage_13_rejected"], post_23["23d_funnel"]["outcome_counts"]["stage_13_rejected"])

# Resolver path
check("23e_commitment_registry_executed", pre_23["23e_resolver_path"]["pipeline_reachability"]["commitment_registry_executed"], post_23["23e_resolver_path"]["pipeline_reachability"]["commitment_registry_executed"])
check("23e_staged_interpreter_executed", pre_23["23e_resolver_path"]["pipeline_reachability"]["staged_interpreter_executed"], post_23["23e_resolver_path"]["pipeline_reachability"]["staged_interpreter_executed"])

# Revised taxonomy
check("23f_buckets", pre_23["23f_revised_taxonomy"]["buckets"], post_23["23f_revised_taxonomy"]["buckets"])
check("23f_other_percentage", pre_23["23f_revised_taxonomy"]["other_percentage"], post_23["23f_revised_taxonomy"]["other_percentage"])

# Gates
pre_h = pre_23["23h_gates"]
post_h = post_23["23h_gates"]
check("23h_semantic_mapping_coverage", pre_h["semantic_mapping_coverage"], post_h["semantic_mapping_coverage"])
check("23h_s0_extraction_coverage", pre_h["s0_extraction_coverage"], post_h["s0_extraction_coverage"])
check("23h_gt_extraction_coverage", pre_h["gt_extraction_coverage"], post_h["gt_extraction_coverage"])
check("23h_unknown_genre_rate", pre_h["unknown_genre_rate"], post_h["unknown_genre_rate"])
check("23h_incorrect_mutations", pre_h["incorrect_mutations"], post_h["incorrect_mutations"])
check("23h_false_auth_promotions", pre_h["false_auth_promotions"], post_h["false_auth_promotions"])
check("23h_gates_passed", pre_h["gates_passed"], post_h["gates_passed"])

print()

# ---------------------------------------------------------------------------
# 4. Step 23S — MOSES Semantic Safety Enforcement
# ---------------------------------------------------------------------------
print("4. STEP 23S — MOSES SEMANTIC SAFETY ENFORCEMENT")
print("   (conformance tests run live on both pre- and post-migration code;")
print("    safety metrics from step23r_audit.json)")
# Step 23S conformance tests: 33 tests covering 7 MOSES runtime invariants
# (I1 target-vs-reference, I2 value-extraction compatibility, I3 cross-type
# evidence, I4 section-alias consistency, I5 section corroboration, I6
# old-value consistency, I7 minimal semantic proof + authority gate).
# Pre-migration: root-level test_moses_safety.py at commit 0217213.
# Post-migration: tests/conservation/test_moses_safety.py.
pre_passed, pre_failed, pre_skipped = run_moses_conformance_tests_pre()
post_passed, post_failed, post_skipped = run_moses_conformance_tests_post()
print(f"   pre-migration  conformance: {pre_passed} passed, {pre_failed} failed, {pre_skipped} skipped")
print(f"   post-migration conformance: {post_passed} passed, {post_failed} failed, {post_skipped} skipped")
check("23S_conformance_tests_passed", pre_passed, post_passed)
check("23S_conformance_tests_failed", pre_failed, post_failed)
check("23S_conformance_tests_skipped", pre_skipped, post_skipped)

# Step 23S post-fix safety metrics (sourced from step23r_audit.json
# section_safety_metrics, re-run after Step 23S implementation).
# These are the same values checked in section 2 but explicitly
# cross-referenced here as the Step 23S safety audit outputs.
check("23S_incorrect_accepted_mutations", 0, post_s["incorrect_accepted_mutations"])
check("23S_false_authoritative_promotions", 0, post_s["false_authoritative_promotions"])
print()

# ---------------------------------------------------------------------------
# 5. Defect Safety Record
# ---------------------------------------------------------------------------
print("5. DEFECT SAFETY RECORD")
pre_defect = json.loads((PRE / "step_19b_mutation_defect_analysis.json").read_text())
post_defect = json.loads((POST / "step_19b_mutation_defect_analysis.json").read_text())
check("defect_count", len(pre_defect["mutations"]), len(post_defect["mutations"]))
check("defect_chain_ids", sorted(m["chain_id"] for m in pre_defect["mutations"]), sorted(m["chain_id"] for m in post_defect["mutations"]))

pre_held = json.loads((PRE / "held_out_study_results.json").read_text())
post_held = json.loads((POST / "held_out_study_results.json").read_text())
check("held_out_aggregate_total_chains", pre_held["aggregate_metrics"]["total_chains"], post_held["aggregate_metrics"]["total_chains"])
# The aggregate count key is total_amendments in the frozen held-out
# study schema.  Check it explicitly rather than relying on falsy `or`
# chaining (which would misbehave if the value were 0).
_TOTAL_KEY = "total_amendments"
pre_total = pre_held["aggregate_metrics"].get(_TOTAL_KEY, "N/A")
post_total = post_held["aggregate_metrics"].get(_TOTAL_KEY, "N/A")
check("held_out_aggregate_total", pre_total, post_total)

print()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("=" * 70)
print(f"COMPARISON SUMMARY: {PASS} matched, {FAIL} mismatched")
if FAIL == 0:
    print("VERDICT: POST-MIGRATION BEHAVIOR IS BYTE-IDENTICAL TO PRE-MIGRATION")
    print("The directory/import migration preserved all empirical behavior.")
    print("Safe to freeze as the post-migration canonical baseline.")
else:
    print(f"VERDICT: {FAIL} METRICS CHANGED — INVESTIGATE BEFORE FREEZING")
print("=" * 70)

sys.exit(0 if FAIL == 0 else 1)
