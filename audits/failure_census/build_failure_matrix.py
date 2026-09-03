"""Build the complete 25-chain failure matrix with per-cause attribution.

For every chain in the Development Chain Study v2, attributes the failure
to one or more of:

    S0_DISCOVERY_FAILURE       — wrong/short document acquired as S0
    S0_EXTRACTION_FAILURE      — S0 document exists but extractor returns 0
    GT_DISCOVERY_FAILURE       — wrong document acquired as CMP
    GT_EXTRACTION_FAILURE      — CMP document exists but extractor returns 0
    PARSER_FAILURE             — parser finds 0 instructions (unsupported format)
    SEMANTIC_MAPPING_FAILURE   — parser found instructions but mapper mapped <50%
    EXECUTION_FAILURE          — executor could not apply mapped instructions
    LINEAGE_FAILURE            — lineage incomplete (steps missing)
    STATE_COMPARISON_FAILURE   — reconstructed state does not match GT
    UNSUPPORTED_DOCUMENT_FORMAT — document format not handled by parser/extractor

This is the evidence base for v0.2. Every v0.2 change must trace to at
least one failure in this matrix.

Output:
    results/failure_matrix.json   — machine-readable per-chain attribution
    results/failure_matrix.md     — human-readable matrix + aggregate counts
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Failure cause taxonomy
# ---------------------------------------------------------------------------

FAILURE_CAUSES = {
    "S0_DISCOVERY_FAILURE": (
        "Wrong or incomplete document acquired as S0 (too short, not a credit "
        "agreement, or missing covenant sections entirely). The acquisition "
        "pipeline selected the wrong exhibit."
    ),
    "S0_EXTRACTION_FAILURE": (
        "S0 document exists and contains covenant content, but the extractor "
        "returns 0 commitments. Cause is in the extraction engine: section "
        "detection, clause extraction, or covenant classification."
    ),
    "GT_DISCOVERY_FAILURE": (
        "Wrong document acquired as CMP (e.g., an amendment document instead "
        "of a composite/conformed/restated copy). The acquisition pipeline "
        "selected the wrong exhibit as the comparison source."
    ),
    "GT_EXTRACTION_FAILURE": (
        "CMP document exists and is the right type, but the extractor returns "
        "0 commitments. Cause is in the extraction engine."
    ),
    "PARSER_FAILURE": (
        "Parser finds 0 instructions across all amendments. The amendment "
        "format is not handled by the parser's regex patterns."
    ),
    "SEMANTIC_MAPPING_FAILURE": (
        "Parser found instructions but the mapper mapped <50% of them. The "
        "mapper cannot translate the instruction type into a commitment-state "
        "mutation (e.g., definition amendments, consent/waiver language)."
    ),
    "EXECUTION_FAILURE": (
        "Executor could not apply mapped instructions (missing S0 state, "
        "target key not found, or field mismatch)."
    ),
    "LINEAGE_FAILURE": (
        "Lineage incomplete: not all amendment steps have COMPLETE execution "
        "status, or the number of pipeline steps != number of amendments."
    ),
    "STATE_COMPARISON_FAILURE": (
        "Reconstructed final state does not match ground truth exactly. This "
        "is a reconstruction error, not an extraction error — but only "
        "meaningful when S0 and GT extraction are both complete."
    ),
    "UNSUPPORTED_DOCUMENT_FORMAT": (
        "Document format not handled by the parser or extractor (redline/"
        "composite amendments, restated agreements, schedule-based covenants)."
    ),
}


@dataclass
class ChainFailureAttribution:
    """Per-chain failure attribution."""

    chain_id: str
    issuer_name: str
    v2_failure_category: str
    extraction_status: str

    # Per-cause flags (True = this cause contributed to the failure)
    causes: dict[str, bool] = field(default_factory=dict)

    # Evidence (specific observations supporting each cause)
    evidence: dict[str, str] = field(default_factory=dict)

    # Raw metrics from v2 results
    s0_extraction_commitments: int = 0
    s0_extraction_validation_queue: int = 0
    s0_extraction_text_length: int = 0
    gt_extraction_commitments: int = 0
    gt_extraction_validation_queue: int = 0
    gt_extraction_text_length: int = 0
    parser_detected_instructions: int = 0
    semantic_mapped_instructions: int = 0
    unresolved_instructions: int = 0
    incorrect_automatic_mutations: int = 0
    chain_authoritative: bool = False
    lineage_complete: bool = True
    final_state_exact_agreement: float | None = None
    supported_field_agreement: float | None = None
    has_ground_truth: bool = False
    gt_extraction_source: str = ""

    # Evaluation layer assignment (extraction / transformation / reconstruction)
    primary_layer: str = ""


# ---------------------------------------------------------------------------
# S0 document analysis — determine discovery vs extraction failure
# ---------------------------------------------------------------------------


def _analyze_s0_document(chain_id: str) -> tuple[str, str]:
    """Analyze the S0 document for a chain.

    Returns (cause, evidence) where cause is one of:
      - S0_DISCOVERY_FAILURE
      - S0_EXTRACTION_FAILURE
      - "" (no S0 failure)

    Heuristics:
      - File missing → S0_DISCOVERY_FAILURE
      - < 15K chars → S0_DISCOVERY_FAILURE (likely not a full credit agreement)
      - No "credit agreement" language → S0_DISCOVERY_FAILURE
      - Has "Financial Covenants" section header but extractor returns 0
        → S0_EXTRACTION_FAILURE (section detection works but clause
        extraction or classification fails)
      - Has covenants under different section name (Negative Covenants,
        Financial Condition) → S0_EXTRACTION_FAILURE (section detection
        too narrow)
      - No recognizable covenant section → S0_EXTRACTION_FAILURE
    """
    s0_path = Path(f"data/chain_study/{chain_id}/S0.txt")
    if not s0_path.exists():
        return "S0_DISCOVERY_FAILURE", "S0.txt file missing"

    text = s0_path.read_text(encoding="utf-8", errors="ignore")
    chars = len(text)

    if chars < 15000:
        return (
            "S0_DISCOVERY_FAILURE",
            (f"Document too short ({chars} chars) — likely not a full "
            f"credit agreement. May be an exhibit cover, summary, or "
            f"incorrectly acquired document."),
        )

    has_credit_agreement = bool(re.search(r"(?i)credit agreement", text))
    if not has_credit_agreement:
        return (
            "S0_DISCOVERY_FAILURE",
            ("No 'credit agreement' language found — likely the wrong "
            "document type acquired as S0."),
        )

    # Check for covenant section headers
    has_fin_covenant_section = bool(
        re.search(r"(?i)(?:section|article)\s+[\d.]+\s+financial\s+covenant", text)
    )
    has_covenant_section = bool(
        re.search(r"(?i)(?:section|article)\s+[\d.]+\s+covenant", text)
    )
    has_negative_covenant = bool(re.search(r"(?i)negative\s+covenant", text))
    has_financial_condition = bool(re.search(r"(?i)financial\s+condition", text))

    if has_fin_covenant_section:
        return (
            "S0_EXTRACTION_FAILURE",
            ("Financial Covenants section header exists in S0 but extractor "
            "returns 0 commitments. Cause: clause extraction fails because "
            "the section uses numbered subsections (10.1, 10.2) instead of "
            "(a)/(b) format, or the fallback covenant-language pattern "
            "('shall not permit' / 'shall maintain') does not match the "
            "actual verb form ('shall have and maintain', 'may not be less "
            "than'). TOC entries with page numbers on separate lines are "
            "also not skipped, causing the extractor to bind to the TOC "
            "entry instead of the actual section body."),
        )

    if has_covenant_section or has_negative_covenant or has_financial_condition:
        section_names = []
        if has_negative_covenant:
            section_names.append("Negative Covenants")
        if has_financial_condition:
            section_names.append("Financial Condition")
        return (
            "S0_EXTRACTION_FAILURE",
            (f"Covenant content exists under non-standard section name(s): "
            f"{', '.join(section_names)}. The extractor only searches for "
            f"'Financial Covenants' section headers. Covenants in "
            f"'Negative Covenants', 'Financial Condition', or other "
            f"section structures are not found."),
        )

    return (
        "S0_EXTRACTION_FAILURE",
        ("No recognizable covenant section header found. The document may "
        "use a non-standard structure or covenants may be in schedules/"
        "exhibits rather than numbered sections."),
    )


# ---------------------------------------------------------------------------
# GT document analysis — determine discovery vs extraction failure
# ---------------------------------------------------------------------------


def _analyze_gt_document(chain_id: str) -> tuple[str, str]:
    """Analyze the GT (CMP) document for a chain.

    Returns (cause, evidence) where cause is one of:
      - GT_DISCOVERY_FAILURE
      - GT_EXTRACTION_FAILURE
      - "" (no GT failure or no CMP document)
    """
    cmp_path = Path(f"data/chain_study/{chain_id}/CMP.txt")
    if not cmp_path.exists():
        return "", "No CMP document acquired"

    text = cmp_path.read_text(encoding="utf-8", errors="ignore")
    chars = len(text)

    # Check if this is actually an amendment document (wrong acquisition).
    # Matches "AMENDMENT TO CREDIT AGREEMENT", "FIFTH AMENDMENT TO SECOND
    # AMENDED AND RESTATED CREDIT AGREEMENT", etc. The key signal is
    # "AMENDMENT TO ... AGREEMENT" in the first 500 chars — a composite/
    # conformed/restated copy would not have "AMENDMENT TO" in its title.
    # The [^.] character class matches newlines, so this handles titles
    # that wrap across lines (e.g. "FIFTH AMENDMENT TO\nSECOND AMENDED
    # AND RESTATED CREDIT AGREEMENT").
    is_amendment = bool(
        re.search(
            r"(?i)\bamendment\s+to\s+[^.]{0,120}?\bagreement\b",
            text[:500],
        )
    )

    if is_amendment:
        return (
            "GT_DISCOVERY_FAILURE",
            ("CMP document appears to be an amendment document (title "
            "contains 'AMENDMENT TO ... AGREEMENT' in first 500 chars), "
            "not a composite/conformed/restated copy. The acquisition "
            "pipeline selected the wrong exhibit as the comparison source."),
        )

    # Check for covenant content
    has_fin_covenant = bool(re.search(r"(?i)financial\s+covenant", text))
    has_ratios = bool(re.search(r"[\d.]+\s+to\s+1\.0", text))
    has_covenant_section = bool(
        re.search(r"(?i)(?:section|article)\s+[\d.]+\s+covenant", text)
    )

    if not has_fin_covenant and not has_ratios and not has_covenant_section:
        return (
            "GT_EXTRACTION_FAILURE",
            (f"CMP document ({chars} chars) does not contain recognizable "
            f"financial covenant content (no 'Financial Covenants' header, "
            f"no ratio thresholds, no covenant sections). The document may "
            f"use a non-standard structure or may not contain ratio-based "
            f"financial covenants."),
        )

    return (
        "GT_EXTRACTION_FAILURE",
        (f"CMP document ({chars} chars) contains covenant-like content but "
        f"extractor returns 0 commitments. Cause: same extraction engine "
        f"limitations as S0 (section detection, clause extraction format)."),
    )


# ---------------------------------------------------------------------------
# Amendment format analysis — determine parser failure cause
# ---------------------------------------------------------------------------


def _analyze_amendment_format(chain_id: str) -> tuple[str, str]:
    """Analyze amendment documents for parser failure cause.

    Returns (cause, evidence) where cause is one of:
      - PARSER_FAILURE
      - UNSUPPORTED_DOCUMENT_FORMAT
      - "" (no parser failure)
    """
    chain_dir = Path(f"data/chain_study/{chain_id}")
    if not chain_dir.exists():
        return "", "No chain directory"

    amendment_files = sorted(chain_dir.glob("A*.txt"))
    if not amendment_files:
        return "", "No amendment files"

    # Check the first amendment for format
    text = amendment_files[0].read_text(encoding="utf-8", errors="ignore")

    # Redline/composite format: "delete the stricken text ... add the
    # double-underlined text"
    is_redline = bool(re.search(r"(?i)stricken|double.underlin", text))

    # Section-by-section format: "Section X is hereby amended to read"
    is_section_amend = bool(
        re.search(r"(?i)section\s+[\d.]+\s+(?:is\s+)?(?:hereby\s+)?amended\s+to\s+read", text)
    )

    # Full restatement: amendment restates the entire agreement.
    # Two signals:
    #   (a) "amended and restated" in the title area (first 1000 chars)
    #   (b) structural: "NOW THEREFORE ... ARTICLE I ... DEFINITIONS" pattern,
    #       which indicates the amendment restates the entire agreement body
    #       (some restatements don't have "amended and restated" in the title
    #       but still contain the full restated agreement after NOW THEREFORE)
    is_full_restate_title = bool(re.search(r"(?i)amended\s+and\s+restated", text[:1000]))
    is_full_restate_structural = bool(
        re.search(
            r"(?is)now\s+therefore.{0,500}?article\s+i\b.{0,100}?definitions",
            text,
        )
    )
    is_full_restate = is_full_restate_title or is_full_restate_structural

    # Definition amendment format: "Section X.Y of the Credit Agreement is
    # hereby amended and restated in its entirety to read as follows"
    is_definition_amend = bool(
        re.search(r"(?i)definition\s+of\s+\w+\s+set\s+forth\s+in\s+section", text)
    )

    if is_redline:
        return (
            "UNSUPPORTED_DOCUMENT_FORMAT",
            ("Amendment uses redline/composite format ('delete stricken text, "
            "add double-underlined text'). The parser expects section-by-"
            "section 'amended to read as follows' patterns and cannot handle "
            "global redline instructions."),
        )

    if is_full_restate and not is_section_amend:
        if is_full_restate_title:
            evidence = (
                "Amendment is a full amended-and-restated agreement (title "
                "contains 'amended and restated'). The parser expects "
                "section-level amendment instructions, not a full "
                "restatement."
            )
        else:
            evidence = (
                "Amendment restates the entire credit agreement body "
                "(structural signal: 'ARTICLE I / DEFINITIONS' appears "
                "after 'NOW THEREFORE', indicating the full agreement is "
                "restated within the amendment document). The parser "
                "expects section-level amendment instructions, not a full "
                "restatement."
            )
        return ("UNSUPPORTED_DOCUMENT_FORMAT", evidence)

    if is_definition_amend and not is_section_amend:
        return (
            "UNSUPPORTED_DOCUMENT_FORMAT",
            ("Amendment uses definition-amendment format ('definition of X "
            "set forth in Section Y is hereby amended and restated to read "
            "as follows'). The parser may detect these as instructions but "
            "the mapper cannot translate definition changes into commitment-"
            "state mutations."),
        )

    if not is_section_amend:
        return (
            "PARSER_FAILURE",
            ("Amendment does not use 'Section X is hereby amended to read as "
            "follows' format. The parser's regex patterns do not match this "
            "amendment structure."),
        )

    return "", "Amendment format appears supported"


# ---------------------------------------------------------------------------
# Main attribution logic
# ---------------------------------------------------------------------------


def attribute_chain_failure(
    result: dict[str, Any],
) -> ChainFailureAttribution:
    """Attribute a chain's failure to specific root causes.

    Examines the v2 result, the actual S0/CMP documents, and the amendment
    format to determine which failure cause(s) apply.
    """
    chain_id = result["chain_id"]
    # Get text lengths from actual files (not in v2 JSON)
    s0_path = Path(f"data/chain_study/{chain_id}/S0.txt")
    cmp_path = Path(f"data/chain_study/{chain_id}/CMP.txt")
    s0_text_len = len(s0_path.read_text(encoding="utf-8", errors="ignore")) if s0_path.exists() else 0
    gt_text_len = len(cmp_path.read_text(encoding="utf-8", errors="ignore")) if cmp_path.exists() else 0

    attr = ChainFailureAttribution(
        chain_id=chain_id,
        issuer_name=result["issuer_name"],
        v2_failure_category=result["failure_category"],
        extraction_status=result["extraction_status"],
        s0_extraction_commitments=result["s0_extraction_commitments"],
        s0_extraction_validation_queue=result["s0_extraction_validation_queue"],
        s0_extraction_text_length=s0_text_len,
        gt_extraction_commitments=result["gt_extraction_commitments"],
        gt_extraction_validation_queue=result["gt_extraction_validation_queue"],
        gt_extraction_text_length=gt_text_len,
        parser_detected_instructions=result["parser_detected_instructions"],
        semantic_mapped_instructions=result["semantic_mapped_instructions"],
        unresolved_instructions=result["unresolved_instructions"],
        incorrect_automatic_mutations=result["incorrect_automatic_mutations"],
        chain_authoritative=result["chain_authoritative"],
        lineage_complete=result["lineage_complete"],
        final_state_exact_agreement=result["final_state_exact_agreement"],
        supported_field_agreement=result["supported_field_agreement"],
        has_ground_truth=result["has_ground_truth"],
        gt_extraction_source=result["gt_extraction_source"],
    )

    causes: dict[str, bool] = {k: False for k in FAILURE_CAUSES}
    evidence: dict[str, str] = {}

    # Skip manual chains (they use hand-extracted states)
    is_manual = result["gt_extraction_source"] == "manual"

    if is_manual:
        # For manual chains, only check parser/mapper/lineage/comparison
        if result["parser_detected_instructions"] == 0:
            causes["PARSER_FAILURE"] = True
            fmt_cause, fmt_ev = _analyze_amendment_format(chain_id)
            if fmt_cause:
                causes[fmt_cause] = True
                evidence[fmt_cause] = fmt_ev
            else:
                evidence["PARSER_FAILURE"] = (
                    "Parser found 0 instructions. Amendment format may not "
                    "match parser patterns."
                )

        if result["parser_detected_instructions"] > 0 and result["failure_category"] != "SUCCESS":
            mapped = result["semantic_mapped_instructions"]
            parser = result["parser_detected_instructions"]
            if parser > 0 and mapped / parser < 0.5:
                causes["SEMANTIC_MAPPING_FAILURE"] = True
                evidence["SEMANTIC_MAPPING_FAILURE"] = (
                    f"Mapper mapped {mapped}/{parser} instructions "
                    f"({mapped / parser:.0%}). The mapper cannot translate "
                    f"the instruction types into commitment-state mutations."
                )

        if (
            result["has_ground_truth"]
            and result["final_state_exact_agreement"] is not None
            and result["final_state_exact_agreement"] < 1.0
        ):
            causes["STATE_COMPARISON_FAILURE"] = True
            evidence["STATE_COMPARISON_FAILURE"] = (
                f"Final state agreement = {result['final_state_exact_agreement']:.0%}. "
                f"Reconstructed state does not match ground truth."
            )

        if not result["lineage_complete"]:
            causes["LINEAGE_FAILURE"] = True
            evidence["LINEAGE_FAILURE"] = "Lineage incomplete."

        attr.causes = causes
        attr.evidence = evidence
        attr.primary_layer = _assign_primary_layer(causes)
        return attr

    # --- New chains (automated extraction) ---

    # 1. S0 analysis
    if result["s0_extraction_commitments"] == 0:
        s0_cause, s0_ev = _analyze_s0_document(chain_id)
        if s0_cause:
            causes[s0_cause] = True
            evidence[s0_cause] = s0_ev

    # 2. GT analysis
    if result["gt_extraction_source"] == "CMP" and result["gt_extraction_commitments"] == 0:
        gt_cause, gt_ev = _analyze_gt_document(chain_id)
        if gt_cause:
            causes[gt_cause] = True
            evidence[gt_cause] = gt_ev
    elif result["gt_extraction_source"] == "none":
        # No CMP document acquired — this is a GT discovery gap
        # (not counted as a failure cause since many chains simply
        # don't have composite/conformed documents)
        pass

    # 3. Parser analysis
    # Only flag as parser failure if S0 extraction succeeded
    # (if S0 failed, the chain is already blocked at extraction)
    if (
        result["parser_detected_instructions"] == 0
        and result["s0_extraction_commitments"] > 0
    ):
        causes["PARSER_FAILURE"] = True
        fmt_cause, fmt_ev = _analyze_amendment_format(chain_id)
        if fmt_cause:
            causes[fmt_cause] = True
            evidence[fmt_cause] = fmt_ev
        else:
            evidence["PARSER_FAILURE"] = (
                "Parser found 0 instructions. Amendment format may not "
                "match parser patterns."
            )

    # 4. Mapper analysis
    # Skip for SUCCESS chains — the mapper may have low coverage but
    # the chain still reconstructed correctly (unresolved instructions
    # were on out-of-model fields that don't affect the measured state).
    if result["parser_detected_instructions"] > 0 and result["failure_category"] != "SUCCESS":
        mapped = result["semantic_mapped_instructions"]
        parser = result["parser_detected_instructions"]
        if mapped / parser < 0.5:
            causes["SEMANTIC_MAPPING_FAILURE"] = True
            evidence["SEMANTIC_MAPPING_FAILURE"] = (
                f"Mapper mapped {mapped}/{parser} instructions "
                f"({mapped / parser:.0%}). The mapper cannot translate "
                f"the instruction types (definition amendments, consent/"
                f"waiver language, redline instructions) into commitment-"
                f"state mutations."
            )

    # 5. Execution analysis
    if result["incorrect_automatic_mutations"] > 0:
        causes["EXECUTION_FAILURE"] = True
        evidence["EXECUTION_FAILURE"] = (
            f"{result['incorrect_automatic_mutations']} incorrect automatic "
            f"mutations. The executor rejected mapped mutations (target key "
            f"not found or field mismatch)."
        )

    # 6. Lineage analysis
    if not result["lineage_complete"]:
        causes["LINEAGE_FAILURE"] = True
        evidence["LINEAGE_FAILURE"] = (
            "Lineage incomplete: not all amendment steps have COMPLETE "
            "execution status."
        )

    # 7. State comparison analysis
    # Only attribute to reconstruction if extraction was OK
    if (
        result["has_ground_truth"]
        and result["final_state_exact_agreement"] is not None
        and result["final_state_exact_agreement"] < 1.0
        and result["extraction_status"] in ("ok", "s0_incomplete", "gt_incomplete")
    ):
        causes["STATE_COMPARISON_FAILURE"] = True
        evidence["STATE_COMPARISON_FAILURE"] = (
            f"Final state agreement = {result['final_state_exact_agreement']:.0%}. "
            f"Reconstructed state does not match ground truth. "
            f"(extraction_status={result['extraction_status']} — "
            f"mismatch could have extraction-error contribution)"
        )

    attr.causes = causes
    attr.evidence = evidence
    attr.primary_layer = _assign_primary_layer(causes)
    return attr


def _assign_primary_layer(causes: dict[str, bool]) -> str:
    """Assign the primary evaluation layer for a chain.

    Priority:
      1. extraction — if S0/GT discovery or extraction failure
      2. transformation — if parser/mapper/executor failure
      3. reconstruction — if lineage or state comparison failure
      4. none — if no failures (SUCCESS)
    """
    if any(
        causes.get(c, False)
        for c in (
            "S0_DISCOVERY_FAILURE",
            "S0_EXTRACTION_FAILURE",
            "GT_DISCOVERY_FAILURE",
            "GT_EXTRACTION_FAILURE",
        )
    ):
        return "extraction"
    if any(
        causes.get(c, False)
        for c in (
            "PARSER_FAILURE",
            "SEMANTIC_MAPPING_FAILURE",
            "EXECUTION_FAILURE",
            "UNSUPPORTED_DOCUMENT_FORMAT",
        )
    ):
        return "transformation"
    if any(
        causes.get(c, False)
        for c in ("LINEAGE_FAILURE", "STATE_COMPARISON_FAILURE")
    ):
        return "reconstruction"
    return "none"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def render_failure_matrix_report(
    attributions: list[ChainFailureAttribution],
) -> str:
    """Render the failure matrix as a human-readable report."""
    lines: list[str] = []

    lines.append("# Development Chain Study v2 — Failure Matrix")
    lines.append("")
    lines.append("**Frozen reference**: tag `chain-study-v2-development` (commit fb0862d)")
    lines.append("")
    lines.append("## Failure Cause Taxonomy")
    lines.append("")
    lines.append("| Cause | Description |")
    lines.append("|-------|-------------|")
    for cause, desc in FAILURE_CAUSES.items():
        lines.append(f"| {cause} | {desc} |")
    lines.append("")

    # --- Aggregate counts ---
    lines.append("## Aggregate Cause Counts")
    lines.append("")
    cause_counts: dict[str, int] = {k: 0 for k in FAILURE_CAUSES}
    for attr in attributions:
        for cause, flagged in attr.causes.items():
            if flagged:
                cause_counts[cause] = cause_counts.get(cause, 0) + 1

    lines.append("| Cause | Count | Chains |")
    lines.append("|-------|-------|--------|")
    for cause in sorted(cause_counts, key=lambda c: -cause_counts[c]):
        count = cause_counts[cause]
        chains = [a.chain_id for a in attributions if a.causes.get(cause, False)]
        lines.append(f"| {cause} | {count} | {', '.join(chains)} |")
    lines.append("")

    # --- Evaluation layer distribution ---
    lines.append("## Evaluation Layer Distribution")
    lines.append("")
    layer_counts: dict[str, int] = {}
    for attr in attributions:
        layer = attr.primary_layer
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    lines.append("| Layer | Count | Chains |")
    lines.append("|-------|-------|--------|")
    for layer in ("extraction", "transformation", "reconstruction", "none"):
        count = layer_counts.get(layer, 0)
        chains = [a.chain_id for a in attributions if a.primary_layer == layer]
        lines.append(f"| {layer} | {count} | {', '.join(chains)} |")
    lines.append("")

    # --- Per-chain matrix ---
    lines.append("## Per-Chain Failure Matrix")
    lines.append("")
    header_causes = list(FAILURE_CAUSES.keys())
    header = "| Chain | V2 Category | Layer | " + " | ".join(
        c.replace("_FAILURE", "").replace("_DISCOVERY", "_DISC")
        .replace("_EXTRACTION", "_EXT").replace("_DOCUMENT_FORMAT", "_FMT")
        .replace("_COMPARISON", "_CMP").replace("_MAPPING", "_MAP")
        for c in header_causes
    ) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (3 + len(header_causes)))

    for attr in attributions:
        row = f"| {attr.chain_id} | {attr.v2_failure_category} | {attr.primary_layer} |"
        for cause in header_causes:
            row += " Y |" if attr.causes.get(cause, False) else "  |"
        lines.append(row)
    lines.append("")

    # --- Per-chain evidence ---
    lines.append("## Per-Chain Evidence")
    lines.append("")
    for attr in attributions:
        lines.append(f"### {attr.chain_id} — {attr.issuer_name}")
        lines.append("")
        lines.append(f"- V2 category: {attr.v2_failure_category}")
        lines.append(f"- Extraction status: {attr.extraction_status}")
        lines.append(f"- Primary layer: {attr.primary_layer}")
        lines.append(f"- S0: {attr.s0_extraction_commitments} commitments, "
                     f"{attr.s0_extraction_validation_queue} VQ, "
                     f"{attr.s0_extraction_text_length} chars")
        lines.append(f"- GT: {attr.gt_extraction_commitments} commitments, "
                     f"{attr.gt_extraction_validation_queue} VQ, "
                     f"{attr.gt_extraction_text_length} chars "
                     f"(source: {attr.gt_extraction_source})")
        lines.append(f"- Parser: {attr.parser_detected_instructions} instructions")
        lines.append(f"- Mapper: {attr.semantic_mapped_instructions} mapped, "
                     f"{attr.unresolved_instructions} unresolved")
        lines.append(f"- Incorrect mutations: {attr.incorrect_automatic_mutations}")
        lines.append(f"- Lineage complete: {attr.lineage_complete}")
        if attr.final_state_exact_agreement is not None:
            lines.append(f"- Final state agreement: "
                         f"{attr.final_state_exact_agreement:.0%}")
        lines.append("")

        flagged_causes = [c for c, v in attr.causes.items() if v]
        if flagged_causes:
            lines.append("**Attributed causes:**")
            lines.append("")
            for cause in flagged_causes:
                lines.append(f"- **{cause}**: {attr.evidence.get(cause, '')}")
            lines.append("")
        else:
            lines.append("**No failures attributed.**")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Load v2 results
    with open("results/chain_study_v2_results.json", encoding="utf-8") as f:
        v2_data = json.load(f)

    # Attribute each chain
    attributions: list[ChainFailureAttribution] = []
    for result in v2_data["issuer_results"]:
        attr = attribute_chain_failure(result)
        attributions.append(attr)

    # Write machine-readable matrix
    matrix_data = {
        "study": "development_chain_study_v2_failure_matrix",
        "frozen_tag": "chain-study-v2-development",
        "frozen_commit": "fb0862d",
        "causes": FAILURE_CAUSES,
        "chains": [asdict(a) for a in attributions],
        "aggregate_cause_counts": {
            cause: sum(1 for a in attributions if a.causes.get(cause, False))
            for cause in FAILURE_CAUSES
        },
        "layer_counts": {
            layer: sum(1 for a in attributions if a.primary_layer == layer)
            for layer in ("extraction", "transformation", "reconstruction", "none")
        },
    }

    matrix_path = Path("results/failure_matrix.json")
    matrix_path.write_text(json.dumps(matrix_data, indent=2), encoding="utf-8")
    print(f"Failure matrix JSON: {matrix_path}")

    # Write human-readable report
    report = render_failure_matrix_report(attributions)
    report_path = Path("results/failure_matrix.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Failure matrix report: {report_path}")

    # Print summary
    print()
    print("=" * 60)
    print("FAILURE MATRIX SUMMARY")
    print("=" * 60)
    print()
    print("Aggregate cause counts:")
    for cause in sorted(FAILURE_CAUSES, key=lambda c: -matrix_data["aggregate_cause_counts"][c]):
        count = matrix_data["aggregate_cause_counts"][cause]
        if count > 0:
            print(f"  {cause}: {count}")
    print()
    print("Layer distribution:")
    for layer in ("extraction", "transformation", "reconstruction", "none"):
        print(f"  {layer}: {matrix_data['layer_counts'][layer]}")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
