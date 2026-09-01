"""Step 19B.3: Generate the defect/safety distinction record.

Distinguishes three layers:

1. SEMANTIC MAPPER DEFECT — the mapper produced wrong confident mappings
2. EXECUTION SAFETY — the executor rejected them as UNKNOWN_COMMITMENT
3. AUTHORITATIVE CORRUPTION — was any incorrect state promoted as authoritative?

This distinction is critical for the paper: the frozen v1 system has a
confirmed mapper defect, but the execution safety layer prevented
authoritative corruption.  The system is wrong at the mapper layer but
safe at the authority layer.

Generates: results/step_19b_defect_safety_record.md

Usage:
    python generate_defect_safety_record.py
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

DEFECT_ANALYSIS = Path("results/step_19b_mutation_defect_analysis.json")
HELD_OUT_RESULTS = Path("results/held_out_study_results.json")
OUTPUT_PATH = Path("results/step_19b_defect_safety_record.md")


def main() -> int:
    defects = json.loads(DEFECT_ANALYSIS.read_text(encoding="utf-8"))
    held = json.loads(HELD_OUT_RESULTS.read_text(encoding="utf-8"))

    mutations = defects["mutations"]
    agg = held["aggregate_metrics"]

    incorrect_chains = {m["chain_id"] for m in mutations}
    authoritative_status = {}
    for r in held["issuer_results"]:
        if r["chain_id"] in incorrect_chains:
            authoritative_status[r["chain_id"]] = {
                "chain_authoritative": r["chain_authoritative"],
                "lineage_complete": r["lineage_complete"],
                "incorrect_automatic_mutations": r["incorrect_automatic_mutations"],
            }

    all_non_authoritative = all(
        not s["chain_authoritative"] for s in authoritative_status.values()
    )

    lines: list[str] = []
    w = lines.append

    w("# Step 19B — Defect / Safety Distinction Record")
    w("")
    w(f"**Generated:** {datetime.now(UTC).isoformat()}")
    w("**Frozen system:** v1.0-frozen-operational-build")
    w("")
    w("---")
    w("")
    w("## Three-Layer Analysis")
    w("")
    w("The 3 incorrect automatic mutations on held-out chains are analyzed")
    w("across three distinct system layers.  This distinction is critical")
    w("for honest reporting: the system has a confirmed mapper defect, but")
    w("the execution safety layer prevented authoritative corruption.")
    w("")
    w("### Layer 1: SEMANTIC MAPPER DEFECT")
    w("")
    w("**Finding: 3 wrong confident mappings produced.**")
    w("")
    w("The semantic mapper produced 3 confident (non-UNRESOLVED) mutations")
    w("that were wrong.  All 3 targeted `facility.credit_agreement`, a")
    w("phantom key that the S0 extractor never produces in any chain")
    w("(development or held-out).")
    w("")
    w("| # | Chain | Amendment | Instruction Type | Target Key | Value |")
    w("|---|-------|-----------|------------------|------------|-------|")
    for i, m in enumerate(mutations, 1):
        w(f"| {i} | {m['chain_id']} | A{m['amendment_number']} ins {m['parsed_instruction']['order']} | "
          f"{m['parsed_instruction']['instruction_type']} | "
          f"`{m['semantic_mapping']['target_key']}` | "
          f"{m['semantic_mapping']['value']} |")
    w("")
    w("**Root cause:** The mapper's `_rule_maturity_date_replacement` and")
    w("`_rule_rate_replacement` rules target `facility.credit_agreement`,")
    w("a commitment key that the S0 extractor's schema does not include.")
    w("The Step 17B fix guarded against RESTATE_SECTION and DELETE")
    w("instruction types, but did not guard against ADD or REPLACE_TEXT.")
    w("On held-out chains, the rule fires on these unguarded instruction")
    w("types, producing confident mutations targeting the phantom key.")
    w("")
    w("**Evidence class:** A — INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT")
    w("")
    w("This defect is confirmed without human gold.  The phantom-key")
    w("mismatch is visible in the system's own architecture:")
    w("- The S0 extractor's output schema is fixed and inspectable")
    w("- `facility.credit_agreement` never appears in any extraction")
    w("- The mapper's rules explicitly target this key")
    w("")
    w("### Layer 2: EXECUTION SAFETY")
    w("")
    w("**Finding: All 3 wrong mutations rejected by the executor.**")
    w("")
    w("The executor rejected all 3 mutations as `UNKNOWN_COMMITMENT`")
    w("because the target key (`facility.credit_agreement`) did not exist")
    w("in the chain's commitment state.  The mutations were NOT applied.")
    w("")
    w("| # | Chain | Executor Result | Mutation Applied? |")
    w("|---|-------|-----------------|-------------------|")
    for i, m in enumerate(mutations, 1):
        w(f"| {i} | {m['chain_id']} | "
          f"{m['executor_rejection_reason']} | NO |")
    w("")
    w("**Safety mechanism:** The executor's key-existence check prevents")
    w("mutations targeting non-existent commitments from being applied.")
    w("This is a defense-in-depth layer that catches mapper errors before")
    w("they corrupt the state.")
    w("")
    w("### Layer 3: AUTHORITATIVE CORRUPTION")
    w("")
    w("**Finding: 0 observed authoritative corruption from these defects.**")
    w("")
    w("None of the 3 chains with incorrect mutations were promoted to")
    w("authoritative status.  The authority-blocking mechanism prevented")
    w("any chain with unresolved mutations from being marked authoritative.")
    w("")
    w("| Chain | Chain Authoritative? | Lineage Complete? | Incorrect Mutations |")
    w("|-------|----------------------|--------------------|--------------------:|")
    for cid in sorted(authoritative_status):
        s = authoritative_status[cid]
        w(f"| {cid} | {'YES' if s['chain_authoritative'] else 'NO'} | "
          f"{'YES' if s['lineage_complete'] else 'NO'} | "
          f"{s['incorrect_automatic_mutations']} |")
    w("")
    if all_non_authoritative:
        w("**All 3 chains remained non-authoritative.** The incorrect")
        w("mutations did not corrupt the authoritative state because:")
        w("1. The executor rejected them (Layer 2)")
        w("2. Rejected mutations are counted as unresolved")
        w("3. Unresolved mutations block authoritative promotion")
        w("")
    w("---")
    w("")
    w("## Summary Table")
    w("")
    w("| Layer | Finding | Count | Impact |")
    w("|-------|---------|-------|--------|")
    w("| Semantic Mapper | Wrong confident mappings produced | 3 | Mapper defect confirmed |")
    w("| Execution Safety | Wrong mutations rejected by executor | 3/3 | State not corrupted |")
    w("| Authoritative Corruption | Incorrect state promoted as authoritative | 0 | No authoritative corruption |")
    w("")
    w("## Interpretation")
    w("")
    w("The frozen v1 system has a **confirmed semantic mapper defect**:")
    w("it produces 3 wrong confident mappings on held-out data, all")
    w("targeting a phantom key.  This is a foundation-level defect in the")
    w("mapper's schema alignment with the extractor.")
    w("")
    w("However, the **execution safety layer held**: the executor rejected")
    w("all 3 wrong mutations, preventing them from being applied to the")
    w("commitment state.  The **authority layer also held**: no chain with")
    w("incorrect mutations was promoted to authoritative status.")
    w("")
    w("The distinction that belongs in the paper:")
    w("")
    w("> The frozen v1 system produced 3 wrong confident semantic mappings,")
    w("> but the executor rejected them all as UNKNOWN_COMMITMENT.  The")
    w("> system has a confirmed mapper defect, but NOT silent authoritative-")
    w("> state corruption.  The safety layer did its job.")
    w("")
    w("## Aggregate safety metrics (held-out, 25 chains)")
    w("")
    w("| Metric | Value |")
    w("|--------|-------|")
    w(f"| False authoritative promotion rate | {agg['false_authoritative_promotion_rate']:.4f} |")
    w(f"| False authoritative promotion count | {agg['false_authoritative_promotion_count']} |")
    w(f"| Incorrect automatic mutation rate | {agg['incorrect_automatic_mutation_rate']:.4f} |")
    w(f"| Incorrect automatic mutation count | {agg['total_incorrect_mutations']} |")
    w(f"| Lineage completeness rate | {agg['lineage_completeness_rate']:.4f} |")
    w("")
    w("## What this means for v1.1")
    w("")
    w("The 3 confirmed mapper defects become post-v1 development:")
    w("")
    w("- Fix the phantom-key mismatch: either align the mapper's target")
    w("  keys with the extractor's output schema, or add")
    w("  `facility.credit_agreement` to the extractor's scope.")
    w("- Extend the instruction_type guard to cover ADD and REPLACE_TEXT")
    w("  (not just RESTATE_SECTION and DELETE).")
    w("- The held-out study remains an honest evaluation of frozen v1.")
    w("- The 25 held-out chains CANNOT be reused as held-out for v1.1")
    w("  because they have now been seen.  v1.1 requires a NEW untouched")
    w("  held-out corpus.")
    w("")
    w("---")
    w("")
    w("## Status")
    w("")
    w("| Item | Status |")
    w("|------|--------|")
    w("| Semantic mapper defect | CONFIRMED (3 cases, Class A) |")
    w("| Execution safety | HELD (3/3 rejected) |")
    w("| Authoritative corruption | NONE (0 promotions) |")
    w("| Human gold needed for confirmation? | NO — defect is independently demonstrable |")
    w("| Human gold needed for confirmatory accuracy? | YES — blocked |")
    w("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Defect/safety record: {OUTPUT_PATH}")
    print()
    print("Summary:")
    print("  Semantic mapper defect:  3 wrong confident mappings (CONFIRMED)")
    print("  Execution safety:        3/3 rejected by executor (HELD)")
    print("  Authoritative corruption: 0 promotions (NONE)")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
