"""Derive the v0.2 change list from observed development failures.

Every proposed v0.2 change MUST trace to at least one failure in the
failure matrix. No change is added because it "sounds useful."

Priority order (per user instruction):
  1. S0 and GT extraction coverage (the publication bottleneck)
  2. Parser format support (only if extraction is fixed and parser
     blocks the pipeline)
  3. Semantic mapper expansion (only if the failure matrix proves it
     is responsible as a primary bottleneck)

Output:
    results/v02_change_spec.md — human-readable change spec for review
    results/v02_change_spec.json — machine-readable change spec
"""
from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# v0.2 change spec — derived from failure matrix evidence
# ---------------------------------------------------------------------------

V02_CHANGES = [
    # ===================================================================
    # PRIORITY 1: S0/GT extraction coverage (the publication bottleneck)
    # ===================================================================
    {
        "id": "V02-001",
        "title": "Expand section detection to non-'Financial Covenants' headers",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["S0_EXTRACTION_FAILURE"],
        "affected_chains": [
            "STUDY-004", "STUDY-008", "STUDY-020", "STUDY-031",
        ],
        "evidence": (
            "4 chains have covenants under 'Negative Covenants', 'Financial "
            "Condition', or other non-standard section names. The extractor "
            "only searches for 'Financial Covenants' headers. STUDY-008 has "
            "'SECTION 4.9. FINANCIAL CONDITION' with EBIT-to-Interest ratio "
            "covenants. STUDY-004 has covenants in 'Section 7. Negative "
            "Covenants'. STUDY-031 has 407K chars with covenants under "
            "non-standard headers."
        ),
        "change": (
            "Add section detection patterns for: 'Financial Condition', "
            "'Negative Covenants' (when they contain ratio/percent "
            "thresholds), 'Affirmative Covenants' (when they contain "
            "maintain-language covenants). Use content-based detection: "
            "if a section contains ratio thresholds ('X.XX to 1.00') or "
            "percentage thresholds with covenant language ('shall not "
            "permit', 'shall maintain'), treat it as a covenant section "
            "even if the header doesn't say 'Financial Covenants'."
        ),
        "risk": (
            "May increase false positives if non-covenant sections contain "
            "ratio language. Mitigation: require covenant verb language "
            "('shall not permit', 'shall maintain', 'may not exceed') in "
            "addition to threshold values."
        ),
        "regression_test": (
            "All 4 affected chains should extract ≥1 commitment. Existing "
            "chains (Ameresco, Amedisys, Bausch-Lomb) should produce "
            "identical results. No new false positives in the 12 currently-"
            "succeeding chains."
        ),
        "touches": ["commitment_extractor.py"],
    },
    {
        "id": "V02-002",
        "title": "Fix TOC-skip logic for page numbers on separate lines",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["S0_EXTRACTION_FAILURE"],
        "affected_chains": ["STUDY-021"],
        "evidence": (
            "STUDY-021 has 'SECTION 10\\nFINANCIAL COVENANTS.\\n38' in the "
            "TOC (page number '38' on a separate line after the header). "
            "The TOC-skip logic only checks for dot leaders (3+ dots) "
            "within 20 chars after the match. Page numbers on separate "
            "lines are not caught. The extractor binds to the TOC entry "
            "instead of the actual section body at 79.8% through the "
            "document, extracting 0 clauses from the TOC text."
        ),
        "change": (
            "Expand TOC-skip logic: if a match is in the first 15% of the "
            "document AND is followed by a page number (1-3 digits on a "
            "separate line) within 10 chars, skip it. Also: if multiple "
            "matches exist for the same section number, prefer the last "
            "one (the actual body, not the TOC entry)."
        ),
        "risk": "Low. Only affects TOC detection, not extraction logic.",
        "regression_test": (
            "STUDY-021 should extract ≥1 commitment from the SECTION 10 "
            "body (Fixed Charge Coverage Ratio, Senior Funded Debt to "
            "EBITDA Ratio, Minimum Tangible Net Worth). No regression in "
            "existing chains."
        ),
        "touches": ["commitment_extractor.py"],
    },
    {
        "id": "V02-003",
        "title": "Add numbered-subsection clause extraction (10.1, 10.2 format)",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["S0_EXTRACTION_FAILURE"],
        "affected_chains": ["STUDY-021", "STUDY-029"],
        "evidence": (
            "STUDY-021 SECTION 10 uses '10.1 Fixed Charge Coverage Ratio.  "
            "Beginning with...' format. STUDY-029 Section 5.03 has a "
            "single covenant without subsections. The clause extraction "
            "regex only matches '(a) Name.  body' format. Numbered "
            "subsections (10.1, 10.2) are not recognized."
        ),
        "change": (
            "Add a second clause extraction pattern for numbered "
            "subsections: '(\\d+\\.\\d+)\\s+([A-Z][^.]{3,80}?)\\s*\\.\\s+' "
            "followed by the clause body. Apply this pattern when the "
            "(a)/(b) pattern finds 0 clauses. Also: for sections with no "
            "subsections at all (like STUDY-029's single-covenant section), "
            "treat the entire section body as one clause if it contains "
            "threshold language."
        ),
        "risk": (
            "May match non-clause numbered items (definitions, "
            "representations). Mitigation: only apply within sections "
            "already identified as covenant sections."
        ),
        "regression_test": (
            "STUDY-021 should extract 3 commitments (Fixed Charge Coverage, "
            "Senior Funded Debt to EBITDA, Minimum Tangible Net Worth). "
            "STUDY-029 should extract 1 commitment (Leverage Ratio ≤ 2.50)."
        ),
        "touches": ["commitment_extractor.py"],
    },
    {
        "id": "V02-004",
        "title": "Expand fallback covenant-language pattern",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["S0_EXTRACTION_FAILURE"],
        "affected_chains": ["STUDY-029"],
        "evidence": (
            "STUDY-029's covenant text: 'Borrower shall have and maintain, "
            "on a consolidated basis, a Leverage Ratio less than or equal "
            "to 2.50 to 1.00'. The fallback pattern matches 'shall\\s+"
            "maintain' but NOT 'shall have and maintain' (there's 'have "
            "and' between 'shall' and 'maintain'). The clause is not "
            "extracted."
        ),
        "change": (
            "Expand the fallback covenant-language regex to match: "
            "'shall\\s+(?:\\w+\\s+)*maintain', 'may\\s+not\\s+(?:be\\s+)?"
            "(?:less|greater)\\s+than', 'shall\\s+(?:not\\s+)?be\\s+"
            "(?:less|greater)\\s+than', 'shall\\s+have\\s+and\\s+maintain'. "
            "The pattern should match any covenant verb form that "
            "constrains a financial metric."
        ),
        "risk": "Low. Only affects fallback clause detection.",
        "regression_test": (
            "STUDY-029 should extract the Leverage Ratio covenant. No "
            "regression in existing chains."
        ),
        "touches": ["commitment_extractor.py"],
    },
    {
        "id": "V02-005",
        "title": "Add S0 discovery validation (document type checking)",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["S0_DISCOVERY_FAILURE"],
        "affected_chains": ["STUDY-006", "STUDY-012", "STUDY-014"],
        "evidence": (
            "3 chains acquired documents that are not full credit "
            "agreements as S0: STUDY-006 (6.9K chars), STUDY-012 (14K "
            "chars), STUDY-014 (93K chars, no 'credit agreement' language). "
            "These are likely exhibit covers, summaries, or wrong exhibits "
            "selected by the acquisition pipeline."
        ),
        "change": (
            "Add S0 discovery validation in the acquisition pipeline: "
            "check that the acquired document (a) is > 20K chars, (b) "
            "contains 'credit agreement' language, (c) contains covenant-"
            "like content (ratio thresholds, dollar amounts with 'Term "
            "Loan'/'Revolving' language). If validation fails, flag the "
            "chain as S0_DISCOVERY_FAILURE and attempt re-acquisition. "
            "This is an acquisition pipeline fix, not an extractor fix."
        ),
        "risk": (
            "May exclude valid short credit agreements. Mitigation: set "
            "the threshold conservatively (15K chars) and allow manual "
            "override."
        ),
        "regression_test": (
            "The 3 affected chains should be flagged as "
            "S0_DISCOVERY_FAILURE at acquisition time, not misattributed "
            "to the extractor."
        ),
        "touches": ["acquire_chain_study.py", "build_development_corpus.py"],
    },
    {
        "id": "V02-006",
        "title": "Add GT discovery validation (CMP document type checking)",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["GT_DISCOVERY_FAILURE"],
        "affected_chains": ["STUDY-016"],
        "evidence": (
            "STUDY-016's CMP document is actually 'FIFTH AMENDMENT TO "
            "SECOND AMENDED AND RESTATED CREDIT AGREEMENT' — an amendment "
            "document, not a composite/conformed copy. The acquisition "
            "pipeline selected the wrong exhibit as the comparison source."
        ),
        "change": (
            "Add CMP discovery validation: check that the acquired "
            "document is NOT an amendment (does not start with 'AMENDMENT "
            "TO ... AGREEMENT' in the first 500 chars). If it is an "
            "amendment, flag as GT_DISCOVERY_FAILURE and attempt "
            "re-acquisition of the actual composite/conformed document."
        ),
        "risk": "Low. Only affects acquisition validation.",
        "regression_test": (
            "STUDY-016 should be flagged as GT_DISCOVERY_FAILURE at "
            "acquisition time."
        ),
        "touches": ["acquire_chain_study.py", "acquire_comparison_sources.py"],
    },
    {
        "id": "V02-007",
        "title": "Add schedule/exhibit-based covenant extraction",
        "priority": 1,
        "layer": "extraction",
        "failure_causes": ["S0_EXTRACTION_FAILURE"],
        "affected_chains": ["STUDY-020"],
        "evidence": (
            "STUDY-020 has 'Financial Covenants' in SCHEDULE 1 (a schedule "
            "attachment, not a numbered section). The extractor only "
            "searches for numbered sections, not schedules. The actual "
            "covenant content is in a schedule table."
        ),
        "change": (
            "Add schedule-based covenant detection: search for "
            "'SCHEDULE N\\nFinancial Covenants' or 'SCHEDULE N\\n"
            "Financial Covenant' patterns. Extract covenant content from "
            "schedule tables (which may use table format rather than "
            "prose). This is a lower-priority fix since schedule-based "
            "covenants are less common."
        ),
        "risk": (
            "Schedule tables have different structure than prose "
            "covenants. May require table parsing logic. Medium "
            "complexity."
        ),
        "regression_test": (
            "STUDY-020 should extract ≥1 commitment from SCHEDULE 1."
        ),
        "touches": ["commitment_extractor.py"],
    },

    # ===================================================================
    # PRIORITY 2: Parser format support (only if extraction is fixed)
    # ===================================================================
    {
        "id": "V02-008",
        "title": "Add redline/composite amendment format support",
        "priority": 2,
        "layer": "transformation",
        "failure_causes": ["UNSUPPORTED_DOCUMENT_FORMAT", "PARSER_FAILURE"],
        "affected_chains": ["STUDY-010", "STUDY-027", "STUDY-028"],
        "evidence": (
            "3 chains use redline/composite amendment format: 'the Credit "
            "Agreement is hereby amended to delete the stricken text and "
            "to add the double-underlined text'. The parser expects "
            "section-by-section 'amended to read as follows' patterns and "
            "finds 0 instructions in these amendments."
        ),
        "change": (
            "Add a redline-format parser path: when the amendment uses "
            "global redline instructions ('delete stricken text, add "
            "underlined text'), detect the stricken and underlined text "
            "spans and convert each to a REPLACE_TEXT instruction with "
            "the section reference inferred from the nearest preceding "
            "section header. This is a parser extension, not a mapper "
            "change."
        ),
        "risk": (
            "Redline text detection requires HTML formatting analysis "
            "(strikethrough, underline tags). The .txt files may have "
            "lost this formatting. May need to re-acquire HTML versions. "
            "High complexity."
        ),
        "regression_test": (
            "STUDY-010, STUDY-027, STUDY-028 should produce ≥1 parser "
            "instruction per amendment."
        ),
        "touches": ["amendment_parser.py"],
    },
    {
        "id": "V02-009",
        "title": "Add full-restatement amendment format support",
        "priority": 2,
        "layer": "transformation",
        "failure_causes": ["UNSUPPORTED_DOCUMENT_FORMAT", "PARSER_FAILURE"],
        "affected_chains": ["STUDY-013"],
        "evidence": (
            "STUDY-013's amendment is a 'JOINDER AND SECOND AMENDMENT' "
            "that restates the entire credit agreement (starts with "
            "'ARTICLE I DEFINITIONS' after the NOW THEREFORE clause). "
            "The parser expects section-level amendment instructions, "
            "not a full restatement."
        ),
        "change": (
            "Add a full-restatement detection path: when an amendment "
            "contains 'AMENDED AND RESTATED' in the title AND restates "
            "the entire agreement body, flag it as a RESTATE_SECTION "
            "instruction covering the entire credit agreement. The "
            "reconstruction pipeline should treat this as a full state "
            "replacement, not an incremental amendment."
        ),
        "risk": (
            "Full restatement handling requires the extractor to process "
            "the restated agreement as a new S0, not as an amendment. "
            "This changes the pipeline architecture. Medium-high "
            "complexity."
        ),
        "regression_test": (
            "STUDY-013 should be handled as a full restatement, with the "
            "restated agreement processed by the S0 extractor."
        ),
        "touches": ["amendment_parser.py", "run_chain_study_v2.py"],
    },

    # ===================================================================
    # PRIORITY 3: Semantic mapper (only if proven responsible as primary)
    # ===================================================================
    {
        "id": "V02-010",
        "title": "Add definition-amendment mapping support",
        "priority": 3,
        "layer": "transformation",
        "failure_causes": ["SEMANTIC_MAPPING_FAILURE"],
        "affected_chains": ["STUDY-007"],
        "evidence": (
            "STUDY-007's amendment uses definition-amendment format: "
            "'The definition of Applicable Margin set forth in Section "
            "1.1 is hereby amended and restated in its entirety to read "
            "as follows'. The parser detects 18 instructions but the "
            "mapper maps 0 because it cannot translate definition "
            "changes (Applicable Margin, Excluded Taxes, FATCA, Maturity "
            "Date) into commitment-state mutations. These are definition "
            "changes, not covenant changes — the mapper correctly "
            "rejects them, but the unresolved rate is 89% (16/18)."
        ),
        "change": (
            "Add definition-amendment classification in the mapper: "
            "when a parsed instruction targets a definition (not a "
            "covenant section), classify it as DEFINITION_CHANGE "
            "domain effect and route to the unresolved queue with a "
            "'definition change — not a commitment mutation' reason. "
            "This does NOT expand the mapper to handle definition "
            "changes — it correctly classifies them as out-of-scope "
            "so the unresolved rate is not misleadingly high."
        ),
        "risk": "Low. Only affects classification, not mapping logic.",
        "regression_test": (
            "STUDY-007's unresolved instructions should be classified "
            "as 'definition change — out of scope' rather than generic "
            "UNRESOLVED. The unresolved count stays the same but the "
            "reason is more informative."
        ),
        "touches": ["semantic_mapper.py"],
        "note": (
            "DO NOT implement unless the failure matrix review confirms "
            "this is a priority. The mapper is correctly rejecting "
            "definition changes — this change only improves the "
            "classification label, not the mapping capability."
        ),
    },
    {
        "id": "V02-011",
        "title": "Add consent/waiver amendment classification",
        "priority": 3,
        "layer": "transformation",
        "failure_causes": ["SEMANTIC_MAPPING_FAILURE"],
        "affected_chains": ["STUDY-005", "STUDY-015", "STUDY-017", "STUDY-026"],
        "evidence": (
            "4 chains have amendments where the parser finds instructions "
            "but the mapper maps 0. These amendments may contain consent/"
            "waiver language or other non-mutation instructions that the "
            "mapper correctly rejects but cannot classify. The unresolved "
            "rate for these chains is 100% of parser-detected instructions."
        ),
        "change": (
            "Add consent/waiver classification: when a parsed instruction "
            "contains 'consent', 'waive', 'waiver', or 'permit' language "
            "without a value change, classify as CONSENT_WAIVER domain "
            "effect and route to unresolved with a descriptive reason."
        ),
        "risk": "Low. Only affects classification.",
        "regression_test": (
            "Affected chains should have consent/waiver instructions "
            "classified as such, not generic UNRESOLVED."
        ),
        "touches": ["semantic_mapper.py"],
        "note": (
            "DO NOT implement unless the failure matrix review confirms "
            "this is a priority. Same rationale as V02-010."
        ),
    },
]


# ---------------------------------------------------------------------------
# Change spec report
# ---------------------------------------------------------------------------


def render_change_spec() -> str:
    """Render the v0.2 change spec as a human-readable document."""
    lines: list[str] = []

    lines.append("# Upsilon v0.2 Change Specification")
    lines.append("")
    lines.append("**Derived from**: Development Chain Study v2 failure matrix")
    lines.append("**Frozen reference**: tag `chain-study-v2-development` (commit fb0862d)")
    lines.append("")
    lines.append("## Design Principle")
    lines.append("")
    lines.append("Every v0.2 change MUST trace to at least one observed failure")
    lines.append("in the 25-chain development set. No change is added because it")
    lines.append("\"sounds useful.\" The failure matrix is the sole evidence source.")
    lines.append("")
    lines.append("## Priority Order")
    lines.append("")
    lines.append("1. **S0/GT extraction coverage** — the publication bottleneck.")
    lines.append("   S0: 12/22 (54.5%), GT: 2/5 (40.0%).")
    lines.append("2. **Parser format support** — only if extraction is fixed and")
    lines.append("   the parser blocks the pipeline.")
    lines.append("3. **Semantic mapper** — only if the failure matrix proves it")
    lines.append("   is responsible as a PRIMARY bottleneck (not secondary to")
    lines.append("   extraction failure).")
    lines.append("")

    # Group by priority
    for priority in (1, 2, 3):
        changes = [c for c in V02_CHANGES if c["priority"] == priority]
        if not changes:
            continue

        priority_names = {1: "S0/GT Extraction Coverage", 2: "Parser Format Support", 3: "Semantic Mapper"}
        lines.append(f"## Priority {priority}: {priority_names[priority]}")
        lines.append("")

        for change in changes:
            lines.append(f"### {change['id']}: {change['title']}")
            lines.append("")
            lines.append(f"**Layer**: {change['layer']}")
            lines.append(f"**Failure causes**: {', '.join(change['failure_causes'])}")
            lines.append(f"**Affected chains**: {', '.join(change['affected_chains'])} "
                         f"({len(change['affected_chains'])} chains)")
            lines.append("")
            lines.append("**Evidence:**")
            lines.append(f"  {change['evidence']}")
            lines.append("")
            lines.append("**Proposed change:**")
            lines.append(f"  {change['change']}")
            lines.append("")
            lines.append("**Risk:**")
            lines.append(f"  {change['risk']}")
            lines.append("")
            lines.append("**Regression test:**")
            lines.append(f"  {change['regression_test']}")
            lines.append("")
            lines.append(f"**Touches**: `{', '.join(change['touches'])}`")
            if "note" in change:
                lines.append("")
                lines.append(f"**NOTE**: {change['note']}")
            lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| ID | Priority | Layer | Title | Affected Chains |")
    lines.append("|----|----------|-------|-------|-----------------|")
    for change in V02_CHANGES:
        lines.append(
            f"| {change['id']} | {change['priority']} | {change['layer']} | "
            f"{change['title'][:60]} | {len(change['affected_chains'])} |"
        )
    lines.append("")

    # Expected impact
    lines.append("## Expected Impact (if all Priority 1 changes are implemented)")
    lines.append("")
    lines.append("```text")
    lines.append("S0 extraction success rate:")
    lines.append("  Current:  12/22 (54.5%)")
    lines.append("  Target:   18/22 (81.8%) — +6 from V02-001, V02-002, V02-003,")
    lines.append("            V02-004, V02-007")
    lines.append("  Remaining 4 failures: 3 discovery (V02-005) + 1 other (STUDY-030)")
    lines.append("")
    lines.append("GT extraction success rate:")
    lines.append("  Current:  2/5 (40.0%)")
    lines.append("  Target:   3/5 (60.0%) — +1 from V02-006 (STUDY-016)")
    lines.append("  Remaining 2: STUDY-018 (no ratio covenants), 1 other")
    lines.append("")
    lines.append("Conditional reconstruction rate:")
    lines.append("  Current:  40.0% (2/5 measurable chains)")
    lines.append("  Target:   depends on extraction improvement + mapper coverage")
    lines.append("  More chains become measurable → denominator increases")
    lines.append("```")
    lines.append("")
    lines.append("## What v0.2 Does NOT Include")
    lines.append("")
    lines.append("- No new covenant types beyond the existing v0.1 scope")
    lines.append("- No machine learning / LLM-based extraction")
    lines.append("- No changes to the authority/lineage/persistence components")
    lines.append("- No changes to the executor (it is behaving correctly)")
    lines.append("- No mapper expansion to handle definition changes (V02-010,")
    lines.append("  V02-011 are classification improvements only, not mapping")
    lines.append("  capability expansion)")
    lines.append("- No held-out issuer changes")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Write human-readable spec
    report = render_change_spec()
    report_path = Path("results/v02_change_spec.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"v0.2 change spec: {report_path}")

    # Write machine-readable spec
    spec_data = {
        "spec": "upsilon_v02_change_spec",
        "derived_from": "chain-study-v2-development",
        "frozen_commit": "fb0862d",
        "principle": "Every change must trace to an observed failure in the 25-chain development set.",
        "changes": V02_CHANGES,
        "priority_order": [
            "S0/GT extraction coverage",
            "Parser format support",
            "Semantic mapper (only if proven primary bottleneck)",
        ],
    }
    json_path = Path("results/v02_change_spec.json")
    json_path.write_text(json.dumps(spec_data, indent=2), encoding="utf-8")
    print(f"v0.2 change spec JSON: {json_path}")

    # Print summary
    print()
    print("=" * 60)
    print("v0.2 CHANGE SPEC SUMMARY")
    print("=" * 60)
    print()
    for priority in (1, 2, 3):
        changes = [c for c in V02_CHANGES if c["priority"] == priority]
        priority_names = {1: "Extraction", 2: "Parser", 3: "Mapper"}
        print(f"Priority {priority} ({priority_names[priority]}): {len(changes)} changes")
        for c in changes:
            print(f"  {c['id']}: {c['title'][:70]}")
        print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
