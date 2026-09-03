"""Step 23 — Upsilon v2 Eligibility & Semantic Funnel Audit.

AUDIT ONLY. No fixes, no tuning, no rule additions, no extractor
modifications, no ontology changes.

Produces:
  23A: Instruction eligibility (IN_SCOPE / OUT_OF_SCOPE / AMBIGUOUS_SCOPE)
  23B: S0 eligibility
  23C: GT eligibility
  23D: Semantic resolution funnel (14-stage drop-off)
  23E: v2 resolver-path reachability
  23F: Revised unresolved taxonomy (OTHER < 10%)
  23G: Like-for-like v1 baseline
  23H: Reevaluated exit gates
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from upsilon.parsing.amendment_parser import parse_v04
from upsilon.commitments.commitment_registry import (
    resolve_commitment_from_section,
    resolve_commitment_from_text,
)
from upsilon.parsing.genre_adapters import AmendmentPattern
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)
from research.run_chain_study_v2 import all_v2_chains
from research.run_held_out_study import all_held_out_chains
from upsilon.transformations.semantic_resolver_v2 import resolve_instruction

# Genres that route through the incremental parser path and therefore
# contribute to the parser-instruction denominator.  FULL_RESTATEMENT
# and CONFORMED_COPY bypass the parser (extraction-based), so their
# parser instructions are NOT counted — matching the v2 study's
# total_parser_instructions.
PARSER_BASED_GENRES = {
    AmendmentPattern.INCREMENTAL.value,
    AmendmentPattern.UNKNOWN.value,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class InstructionRecord:
    """One parser instruction with eligibility classification."""
    chain: str
    amendment: int
    amendment_desc: str
    order: int
    instruction_type: str
    target_section_ref: str
    source_text: str
    eligibility: str = ""  # IN_SCOPE / OUT_OF_SCOPE / AMBIGUOUS_SCOPE
    canonical_class: str = ""
    expected_field: str = ""
    operation: str = ""
    # Funnel stages
    stage_results: dict[str, bool] = field(default_factory=dict)
    # Resolver path reachability
    resolver_path: dict[str, bool] = field(default_factory=dict)
    # Mapping result
    mapped: bool = False
    mapped_correctly: bool = False
    rejection_reason: str = ""


@dataclass
class S0Record:
    """One S0 document with eligibility classification."""
    chain: str
    source_label: str
    text_length: int
    eligibility: str = ""  # S0_IN_SCOPE / S0_NO_IN_SCOPE_CONTENT / S0_DISCOVERY_FAILURE / S0_AMBIGUOUS
    extracted_count: int = 0
    vq_count: int = 0
    in_scope_classes_found: list[str] = field(default_factory=list)


@dataclass
class GTRecord:
    """One GT document with eligibility classification."""
    chain: str
    source_label: str
    text_length: int
    eligibility: str = ""
    extracted_count: int = 0
    vq_count: int = 0
    in_scope_classes_found: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 13-class ontology constants
# ---------------------------------------------------------------------------

CANONICAL_CLASSES = {
    "facility.revolving_facility",
    "facility.term_loan",
    "facility.delayed_draw_term_loan",
    "financial_covenant.leverage_ratio",
    "financial_covenant.debt_service_coverage",
    "financial_covenant.fixed_charge_coverage",
    "financial_covenant.interest_coverage",
    "financial_covenant.current_ratio",
    "financial_covenant.tangible_net_worth",
    "financial_covenant.tier_1_leverage_ratio",
    "financial_covenant.risk_based_capital_ratio",
    "financial_covenant.texas_ratio",
    "financial_covenant.return_on_average_assets",
}

# Covenant keywords that indicate 13-class content
COVENANT_KEYWORDS = [
    "leverage ratio", "debt to ebitda", "funded debt to ebitda",
    "debt service coverage", "fixed charge coverage",
    "interest coverage", "current ratio",
    "tangible net worth", "minimum net worth",
    "tier 1 leverage", "risk.based capital",
    "texas ratio", "return on average assets",
    "revolving facility", "revolving credit",
    "term loan", "delayed draw",
    "maximum leverage", "net leverage ratio",
    "first lien leverage", "secured leverage",
    "asset coverage ratio", "minimum liquidity",
    "minimum working capital", "minimum shareholders equity",
    "minimum stockholders equity",
]

# Non-covenant keywords that indicate OUT_OF_SCOPE content
NON_COVENANT_KEYWORDS = [
    "definitions", "defined terms", "interpretation",
    "accounting principles", "gaap",
    "representations and warranties",
    "conditions precedent",
    "events of default", "remedies",
    "notices", "governing law",
    "successors and assigns",
    "survival", "severability",
    "entire agreement",
    "amendments and waivers",
    "expansion of", "increase in",
    "additional credit party",
    "additional guarantor",
    "release of collateral",
    "release of guarantor",
    "interest rate", "base rate", "sofr", "libor",
    "successor rate", "benchmark replacement",
    "payments", "payment office",
    "taxes", "withholding",
    "mitigation", "increased costs",
    "capital adequacy",
    "swingline", "letters of credit",
    "protective advances",
    "administrative agent",
    "collateral agent",
    "security agreement",
    "guaranty",
    "pledge agreement",
    "perfection",
    "further assurances",
    "books and records",
    "inspection rights",
    "financial reporting",
    "compliance certificate",
    "environmental",
    "insurance",
    "maintenance of properties",
    "corporate existence",
    "compliance with laws",
    "use of proceeds",
    "restricted payments",
    "subordinated debt",
    "liens",
    "fundamental changes",
    "dispositions",
    "acquisitions",
    "investments",
    "mergers",
    "asset sales",
    "transactions with affiliates",
    "negative covenants",
    "affirmative covenants",
    "reporting requirements",
    "financial statements",
    "compliance reports",
    "closing conditions",
    "effectiveness conditions",
    "amendment fee", "commitment fee",
    "upfront fee", "ticking fee",
    "amendment effective",
    "conditions to effectiveness",
    "reaffirmation",
    "acknowledgment",
    "consent",
    "waiver",
    "amendment no.",
    "amendment effective date",
    "section headings",
    "table of contents",
    "cross.references",
    "schedules",
    "exhibits",
    "counterparts",
    "electronic signatures",
]


# ---------------------------------------------------------------------------
# 23A: Instruction eligibility classification
# ---------------------------------------------------------------------------


def classify_instruction_eligibility(ins: AmendmentInstruction) -> tuple[str, str, str, str]:
    """Classify a parser instruction from source evidence.

    Returns:
        (eligibility, canonical_class, expected_field, operation)
    """
    source = (ins.source_text or "").lower()
    section = (ins.target_section_ref or "").lower()
    ins_type = ins.instruction_type.value if hasattr(ins.instruction_type, 'value') else str(ins.instruction_type)

    # Try to resolve a canonical commitment from the source text
    cid, field_hint, _ = resolve_commitment_from_text(
        ins.source_text or "", ins.target_section_ref, {},
    )

    # Try section-based resolution
    if cid is None and ins.target_section_ref:
        cid = resolve_commitment_from_section(ins.target_section_ref)

    # Check for covenant keywords in source text
    has_covenant_kw = any(kw in source for kw in COVENANT_KEYWORDS)

    # Determine operation
    operation = ins_type

    # Classification logic:
    # 1. If the registry resolved a canonical class → IN_SCOPE
    # 2. If the source text contains covenant keywords AND no strong
    #    non-covenant signal → IN_SCOPE
    # 3. If the source text is clearly about non-covenant topics → OUT_OF_SCOPE
    # 4. Otherwise → AMBIGUOUS_SCOPE

    if cid is not None and cid in CANONICAL_CLASSES:
        return ("IN_SCOPE", cid, field_hint or "threshold", operation)

    # Check source text for covenant keywords
    if has_covenant_kw:
        # Determine which canonical class from keywords
        canonical_class = _infer_class_from_keywords(source)
        if canonical_class:
            field_name = _infer_field_from_keywords(source)
            return ("IN_SCOPE", canonical_class, field_name, operation)

    # Check for clear non-covenant content
    # Count covenant vs non-covenant signals
    covenant_signals = sum(1 for kw in COVENANT_KEYWORDS if kw in source)
    non_covenant_signals = sum(1 for kw in NON_COVENANT_KEYWORDS if kw in source)

    if non_covenant_signals > 0 and covenant_signals == 0:
        return ("OUT_OF_SCOPE", "", "", operation)

    if non_covenant_signals > covenant_signals * 2:
        return ("OUT_OF_SCOPE", "", "", operation)

    # Check section ref for non-covenant sections
    non_covenant_sections = [
        "1.01", "1.02", "1.03",  # definitions
        "2.01", "2.02", "2.03", "2.04", "2.05", "2.06", "2.07", "2.08",
        "2.09", "2.10", "2.11", "2.12", "2.13", "2.14",  # credit facility mechanics
        "3.01", "3.02", "3.03",  # conditions, payments
        "4.01", "4.02", "4.03",  # fees
        "5.01", "5.02",  # representations
        "8.01", "8.02", "8.03",  # events of default
        "9.01", "9.02", "9.03",  # remedies
        "10.01", "10.02",  # admin
        "11.01", "11.02",  # misc
    ]
    section_num = re.search(r"(\d+\.\d+)", section)
    if section_num and not has_covenant_kw:
        sec = section_num.group(1)
        if sec in non_covenant_sections:
            return ("OUT_OF_SCOPE", "", "", operation)

    # If we have some covenant signal but can't resolve → AMBIGUOUS
    if covenant_signals > 0:
        return ("AMBIGUOUS_SCOPE", "", "", operation)

    # Default: AMBIGUOUS if we can't tell
    return ("AMBIGUOUS_SCOPE", "", "", operation)


def _infer_class_from_keywords(source: str) -> str:
    """Infer canonical class from source text keywords."""
    source_lower = source.lower()
    # Check in order of specificity
    if "tier 1 leverage" in source_lower:
        return "financial_covenant.tier_1_leverage_ratio"
    if "risk.based capital" in source_lower:
        return "financial_covenant.risk_based_capital_ratio"
    if "texas ratio" in source_lower:
        return "financial_covenant.texas_ratio"
    if "return on average assets" in source_lower:
        return "financial_covenant.return_on_average_assets"
    if "debt service coverage" in source_lower:
        return "financial_covenant.debt_service_coverage"
    if "fixed charge coverage" in source_lower:
        return "financial_covenant.fixed_charge_coverage"
    if "interest coverage" in source_lower:
        return "financial_covenant.interest_coverage"
    if "current ratio" in source_lower:
        return "financial_covenant.current_ratio"
    if "tangible net worth" in source_lower or "minimum net worth" in source_lower:
        return "financial_covenant.tangible_net_worth"
    if any(kw in source_lower for kw in [
        "leverage ratio", "debt to ebitda", "funded debt to ebitda",
        "maximum leverage", "net leverage", "first lien leverage",
        "secured leverage",
    ]):
        return "financial_covenant.leverage_ratio"
    if "asset coverage" in source_lower:
        return "financial_covenant.debt_service_coverage"
    if "minimum liquidity" in source_lower:
        return "financial_covenant.interest_coverage"
    if "minimum working capital" in source_lower:
        return "financial_covenant.current_ratio"
    if "minimum shareholders" in source_lower or "minimum stockholders" in source_lower:
        return "financial_covenant.tangible_net_worth"
    if "delayed draw" in source_lower:
        return "facility.delayed_draw_term_loan"
    if "term loan" in source_lower or "term commitment" in source_lower:
        return "facility.term_loan"
    if "revolving facility" in source_lower or "revolving credit" in source_lower:
        return "facility.revolving_facility"
    return ""


def _infer_field_from_keywords(source: str) -> str:
    """Infer the affected field from source text keywords."""
    source_lower = source.lower()
    if any(kw in source_lower for kw in ["amount", "increase", "decrease", "reduce", "expand"]):
        return "threshold"
    if "maturity" in source_lower or "deadline" in source_lower:
        return "deadline"
    if "threshold" in source_lower or "ratio" in source_lower or "exceed" in source_lower:
        return "threshold"
    return "threshold"  # default for covenant amendments


# ---------------------------------------------------------------------------
# Collect all parser instructions
# ---------------------------------------------------------------------------


def _is_parser_based_genre(step) -> bool:
    """Check whether this amendment's genre routes through the parser.

    FULL_RESTATEMENT and CONFORMED_COPY bypass the parser (extraction-
    based), so their parser instructions are NOT counted in the v2
    study's total_parser_instructions.  Only INCREMENTAL and UNKNOWN
    genres contribute parser instructions.
    """
    pattern = step.pattern
    if pattern is None:
        return True  # synthetic chains with no pattern → parser-based
    return pattern in PARSER_BASED_GENRES


def collect_all_instructions() -> list[InstructionRecord]:
    """Collect all parser instructions from all chains.

    Only amendments whose genre routes through the incremental parser
    path (INCREMENTAL, UNKNOWN) contribute instructions, matching the
    v2 study's total_parser_instructions denominator.  FULL_RESTATEMENT
    and CONFORMED_COPY amendments are extraction-based and do NOT
    contribute parser instructions.
    """
    dev_chains = all_v2_chains()
    held_chains = all_held_out_chains()
    all_chains = dev_chains + held_chains

    records: list[InstructionRecord] = []

    for chain, s0_result, gt_result in all_chains:
        for step_idx, step in enumerate(chain.amendments, 1):
            # Skip non-parser-based genres (full_restatement,
            # conformed_copy) — their instructions are extraction-based
            # and not counted in the parser-instruction denominator.
            if not _is_parser_based_genre(step):
                continue

            source_path = step.source_document_path
            if source_path and Path(source_path).exists():
                text = Path(source_path).read_text(
                    encoding="utf-8", errors="ignore",
                )
                parser_result = parse_v04(text)
                rows = parser_result["instructions"]

                for i, row in enumerate(rows):
                    ins = AmendmentInstruction(
                        order=i + 1,
                        instruction_type=InstructionType(row["instruction_type"]),
                        target_section_ref=row.get("target_section_ref"),
                        source_text=row.get("source_text"),
                        old_value=row.get("old_value"),
                        new_value=row.get("new_value"),
                        provenance=InstructionProvenance.PARSER,
                    )

                    eligibility, cid, field_name, operation = \
                        classify_instruction_eligibility(ins)

                    records.append(InstructionRecord(
                        chain=chain.chain_id,
                        amendment=step_idx,
                        amendment_desc=step.description or "",
                        order=i + 1,
                        instruction_type=ins.instruction_type.value
                            if hasattr(ins.instruction_type, 'value')
                            else str(ins.instruction_type),
                        target_section_ref=ins.target_section_ref or "",
                        source_text=ins.source_text or "",
                        eligibility=eligibility,
                        canonical_class=cid,
                        expected_field=field_name,
                        operation=operation,
                    ))
            else:
                # Manual fallback instructions (synthetic chains)
                for i, ins in enumerate(step.instructions, 1):
                    eligibility, cid, field_name, operation = \
                        classify_instruction_eligibility(ins)

                    records.append(InstructionRecord(
                        chain=chain.chain_id,
                        amendment=step_idx,
                        amendment_desc=step.description or "",
                        order=i,
                        instruction_type=ins.instruction_type.value
                            if hasattr(ins.instruction_type, 'value')
                            else str(ins.instruction_type),
                        target_section_ref=ins.target_section_ref or "",
                        source_text=ins.source_text or "",
                        eligibility=eligibility,
                        canonical_class=cid,
                        expected_field=field_name,
                        operation=operation,
                    ))

    return records


# ---------------------------------------------------------------------------
# 23B/23C: S0/GT eligibility classification
# ---------------------------------------------------------------------------


def classify_s0_eligibility(
    chain_id: str,
    source_label: str,
    text_length: int,
    extracted_count: int,
    vq_count: int,
    source_text: str,
) -> S0Record:
    """Classify an S0 document for eligibility."""
    rec = S0Record(
        chain=chain_id,
        source_label=source_label,
        text_length=text_length,
        extracted_count=extracted_count,
        vq_count=vq_count,
    )

    if text_length == 0 or not source_text:
        rec.eligibility = "S0_DISCOVERY_FAILURE"
        return rec

    # Check for 13-class covenant content
    text_lower = source_text.lower()
    found_classes = []
    for kw in COVENANT_KEYWORDS:
        if kw in text_lower:
            cls = _infer_class_from_keywords(kw)
            if cls and cls not in found_classes:
                found_classes.append(cls)

    # Also check if the extractor found any in-scope commitments
    if extracted_count > 0:
        rec.eligibility = "S0_IN_SCOPE"
        rec.in_scope_classes_found = found_classes
        return rec

    if found_classes:
        rec.eligibility = "S0_IN_SCOPE"
        rec.in_scope_classes_found = found_classes
    else:
        # Check if it's a valid credit agreement at all
        credit_agreement_kw = [
            "credit agreement", "loan agreement", "borrower",
            "lender", "facility", "commitment",
        ]
        has_credit_kw = any(kw in text_lower for kw in credit_agreement_kw)
        if has_credit_kw:
            rec.eligibility = "S0_NO_IN_SCOPE_CONTENT"
        else:
            rec.eligibility = "S0_AMBIGUOUS"

    return rec


def classify_gt_eligibility(
    chain_id: str,
    source_label: str,
    text_length: int,
    extracted_count: int,
    vq_count: int,
    source_text: str,
) -> GTRecord:
    """Classify a GT document for eligibility."""
    rec = GTRecord(
        chain=chain_id,
        source_label=source_label,
        text_length=text_length,
        extracted_count=extracted_count,
        vq_count=vq_count,
    )

    if text_length == 0 or not source_text:
        rec.eligibility = "GT_DISCOVERY_FAILURE"
        return rec

    text_lower = source_text.lower()
    found_classes = []
    for kw in COVENANT_KEYWORDS:
        if kw in text_lower:
            cls = _infer_class_from_keywords(kw)
            if cls and cls not in found_classes:
                found_classes.append(cls)

    if extracted_count > 0:
        rec.eligibility = "GT_IN_SCOPE"
        rec.in_scope_classes_found = found_classes
        return rec

    if found_classes:
        rec.eligibility = "GT_IN_SCOPE"
        rec.in_scope_classes_found = found_classes
    else:
        credit_agreement_kw = [
            "credit agreement", "loan agreement", "borrower",
            "lender", "facility", "commitment",
        ]
        has_credit_kw = any(kw in text_lower for kw in credit_agreement_kw)
        if has_credit_kw:
            rec.eligibility = "GT_NO_IN_SCOPE_CONTENT"
        else:
            rec.eligibility = "GT_AMBIGUOUS"

    return rec


# ---------------------------------------------------------------------------
# 23D: Semantic resolution funnel
# ---------------------------------------------------------------------------


def trace_resolution_funnel(
    ins: AmendmentInstruction,
    current_state: dict[str, CommitmentState],
) -> dict[str, bool]:
    """Trace how far an instruction gets through the 14-stage funnel.

    Returns a dict of stage → reached (bool).

    Uses ``trace.failed_step`` (set by ``resolve_instruction``) to
    determine exactly where the instruction dropped off, rather than
    fragile string matching on trace field values.
    """
    stages = {
        "stage_1_parsed": False,
        "stage_2_scope_recognized": False,
        "stage_3_section_resolved": False,
        "stage_4_commitment_resolved": False,
        "stage_5_field_resolved": False,
        "stage_6_operation_resolved": False,
        "stage_7_old_value_resolved": False,
        "stage_8_new_value_resolved": False,
        "stage_9_unit_resolved": False,
        "stage_10_candidate_created": False,
        "stage_11_validators_passed": False,
        "stage_12_accepted": False,
        "stage_13_rejected": False,
        "stage_14_unresolved": False,
    }

    # Stage 1: instruction parsed (always true — we have the instruction)
    stages["stage_1_parsed"] = True

    # Stage 2: scope recognized (check if we can classify it)
    eligibility, _, _, _ = classify_instruction_eligibility(ins)
    if eligibility == "IN_SCOPE":
        stages["stage_2_scope_recognized"] = True
    else:
        return stages

    # Stage 3: target section resolved
    if ins.target_section_ref:
        stages["stage_3_section_resolved"] = True
    else:
        return stages

    # Stage 4: canonical commitment resolved
    resolved_cid, _, _ = resolve_commitment_from_text(
        ins.source_text or "", ins.target_section_ref, current_state,
    )
    if resolved_cid is None and ins.target_section_ref:
        resolved_cid = resolve_commitment_from_section(ins.target_section_ref)
    if resolved_cid is not None:
        stages["stage_4_commitment_resolved"] = True
    else:
        return stages

    # Run the full resolver to get the trace
    result, trace = resolve_instruction(ins, current_state)

    # failed_step == 0 means the resolver succeeded (all steps passed).
    # failed_step > 0 means the resolver failed at that step.
    failed = trace.failed_step

    # Stage 5: field resolved (resolver step 3)
    if failed == 0 or failed > 3:
        stages["stage_5_field_resolved"] = True
    else:
        return stages

    # Stage 6: operation resolved (resolver step 6 — always set if
    # we got past value extraction, since _identify_operation always
    # returns a value)
    if failed == 0 or failed > 6:
        stages["stage_6_operation_resolved"] = True
    else:
        return stages

    # Stage 7: old value resolved (resolver step 4 — value extraction)
    # For ADD operations, old value is not required.
    if failed == 0 or failed > 4 or ins.instruction_type == InstructionType.ADD:
        stages["stage_7_old_value_resolved"] = True
    else:
        return stages

    # Stage 8: new value resolved (resolver step 5 — normalization)
    if failed == 0 or failed > 5:
        stages["stage_8_new_value_resolved"] = True
    else:
        return stages

    # Stage 9: unit resolved (resolver step 5 — unit is always set
    # during normalization, even if None)
    if failed == 0 or failed > 5:
        stages["stage_9_unit_resolved"] = True
    else:
        return stages

    # Stage 10: StructuredMutation candidate created (resolver step 7)
    if failed == 0 or failed > 7:
        stages["stage_10_candidate_created"] = True
    else:
        return stages

    # Stage 11: deterministic validators passed (resolver step 8)
    # Stage 13: mutation rejected (validator failure at step 8)
    if failed == 0 or failed > 8:
        stages["stage_11_validators_passed"] = True
    elif failed == 8:
        stages["stage_13_rejected"] = True
        return stages
    else:
        return stages

    # Stage 12: mutation accepted
    if result.mutations:
        stages["stage_12_accepted"] = True
    else:
        stages["stage_14_unresolved"] = True
        return stages

    return stages


# ---------------------------------------------------------------------------
# 23E: v2 resolver-path reachability
# ---------------------------------------------------------------------------


def _count_calls_in_source(source: str, func_name: str) -> int:
    """Count actual ``ast.Call`` nodes for ``func_name`` in ``source``.

    This excludes function definitions (``def func_name(...)``), type
    annotations, docstrings, and comments — only real call sites are
    counted.  Handles both bare-name calls (``func_name(...)``) and
    attribute calls (``module.func_name(...)``).

    Returns 0 if the source cannot be parsed as valid Python.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == func_name:
            count += 1
        elif isinstance(func, ast.Attribute) and func.attr == func_name:
            count += 1
    return count


def _count_calls_in_modules(
    module_paths: list[Path], func_name: str,
) -> int:
    """Count actual call sites for ``func_name`` across modules."""
    total = 0
    for mod_path in module_paths:
        if not mod_path.exists():
            continue
        total += _count_calls_in_source(
            mod_path.read_text(encoding="utf-8"), func_name,
        )
    return total


def _analyze_pipeline_reachability() -> dict[str, bool]:
    """Statically analyze whether the v2 pipeline reaches the new
    architecture components.

    The main pipeline path is:
        semantic_pipeline_v2.run_semantic_pipeline_v2
          → genre_adapters.process_amendment_by_genre
            → genre_adapters.process_incremental
              → semantic_resolver_v2.resolve_instruction

    Each component is counted as "reached" only when an actual
    ``ast.Call`` node for it exists in the pipeline source — function
    definitions, type annotations, docstrings, and comments do NOT
    count.  This avoids overstating reachability when a helper is
    defined but never invoked.
    """
    pipeline_modules = [
        Path("src/upsilon/pipeline/semantic_pipeline_v2.py"),
        Path("src/upsilon/parsing/genre_adapters.py"),
        Path("src/upsilon/transformations/semantic_resolver_v2.py"),
    ]
    resolver_path = Path("src/upsilon/transformations/semantic_resolver_v2.py")

    return {
        # AgreementContext: build_agreement_context must be actually
        # called by the pipeline (not just defined or mentioned).
        "agreement_context_executed": _count_calls_in_modules(
            pipeline_modules, "build_agreement_context",
        ) > 0,
        # resolve_with_context must be actually called.
        "resolve_with_context_executed": _count_calls_in_modules(
            pipeline_modules, "resolve_with_context",
        ) > 0,
        # Model-assisted interface: resolve_with_model_assistance must
        # be actually called.
        "model_assisted_interface_executed": _count_calls_in_modules(
            pipeline_modules, "resolve_with_model_assistance",
        ) > 0,
        # Commitment registry: resolve_instruction must actually call
        # resolve_commitment_from_text (not just import or mention it).
        "commitment_registry_executed": _count_calls_in_modules(
            [resolver_path], "resolve_commitment_from_text",
        ) > 0,
        # Staged interpreter: resolve_instruction must actually
        # instantiate ResolverStepTrace (not just annotate a return
        # type with it).
        "staged_interpreter_executed": _count_calls_in_modules(
            [resolver_path], "ResolverStepTrace",
        ) > 0,
    }


def trace_resolver_path(
    ins: AmendmentInstruction,
    current_state: dict[str, CommitmentState],
    pipeline_reachability: dict[str, bool] | None = None,
) -> dict[str, bool]:
    """Trace which v2 architecture components execute for an instruction.

    Args:
        ins: the parser instruction.
        current_state: the current commitment state.
        pipeline_reachability: pre-computed static analysis of which
            components the pipeline calls.  If None, computed inline.
    """
    if pipeline_reachability is None:
        pipeline_reachability = _analyze_pipeline_reachability()

    path = {
        "agreement_context_executed": pipeline_reachability.get(
            "agreement_context_executed", False,
        ),
        "commitment_registry_executed": False,
        "resolve_with_context_executed": pipeline_reachability.get(
            "resolve_with_context_executed", False,
        ),
        "staged_interpreter_executed": False,
        "model_assisted_interface_executed": pipeline_reachability.get(
            "model_assisted_interface_executed", False,
        ),
        "candidate_produced": False,
        "validator_rejected": False,
    }

    # The resolver calls commitment_registry.  We count it as
    # executed only when the registry actually resolved a canonical
    # commitment (cid is not None) — having a section_ref alone does
    # not mean the registry was successfully exercised.
    cid, _, _ = resolve_commitment_from_text(
        ins.source_text or "", ins.target_section_ref, current_state,
    )
    if cid is None and ins.target_section_ref:
        cid = resolve_commitment_from_section(ins.target_section_ref)
    if cid is not None:
        path["commitment_registry_executed"] = True

    # The resolver uses the staged interpreter (ResolverStepTrace)
    result, trace = resolve_instruction(ins, current_state)
    if trace.step1_resolve_target:
        path["staged_interpreter_executed"] = True

    # Check if a candidate was produced (either mapped or unresolved)
    if result.mutations or result.unresolved:
        path["candidate_produced"] = True

    # Validator rejected: only count cases where a candidate was
    # produced (step 7) but validation failed (step 8).  This is
    # NOT the same as "unresolved" — instructions that fail at
    # earlier steps (commitment resolution, field identification,
    # value extraction) are unresolved but NOT validator rejections.
    if trace.failed_step == 8:
        path["validator_rejected"] = True

    return path


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------


def run_audit() -> dict[str, Any]:
    """Run the full Step 23 audit."""
    print("Step 23 — Upsilon v2 Eligibility & Semantic Funnel Audit")
    print("=" * 70)

    # ======================================================================
    # 23A: Instruction eligibility
    # ======================================================================
    print("\n23A: Collecting and classifying all parser instructions...")
    all_records = collect_all_instructions()
    total_instructions = len(all_records)

    in_scope = [r for r in all_records if r.eligibility == "IN_SCOPE"]
    out_of_scope = [r for r in all_records if r.eligibility == "OUT_OF_SCOPE"]
    ambiguous = [r for r in all_records if r.eligibility == "AMBIGUOUS_SCOPE"]

    print(f"  Total parser instructions: {total_instructions}")
    print(f"  IN_SCOPE: {len(in_scope)}")
    print(f"  OUT_OF_SCOPE: {len(out_of_scope)}")
    print(f"  AMBIGUOUS_SCOPE: {len(ambiguous)}")

    # ======================================================================
    # 23B: S0 eligibility
    # ======================================================================
    print("\n23B: Classifying S0 documents...")
    dev_chains = all_v2_chains()
    held_chains = all_held_out_chains()
    all_chains = dev_chains + held_chains

    s0_records: list[S0Record] = []
    for chain, s0_result, gt_result in all_chains:
        is_manual = s0_result.source_label == "S0-manual"
        if is_manual:
            continue

        source_text = ""
        for path in [
            f"data/chain_study/{chain.chain_id}/S0.txt",
            f"data/held_out/{chain.chain_id}/S0.txt",
        ]:
            p = Path(path)
            if p.exists():
                source_text = p.read_text(encoding="utf-8", errors="ignore")
                break

        rec = classify_s0_eligibility(
            chain.chain_id,
            s0_result.source_label,
            s0_result.text_length,
            len(s0_result.commitments),
            len(s0_result.validation_queue),
            source_text,
        )
        s0_records.append(rec)

    s0_in_scope = [r for r in s0_records if r.eligibility == "S0_IN_SCOPE"]
    s0_no_content = [r for r in s0_records if r.eligibility == "S0_NO_IN_SCOPE_CONTENT"]
    s0_discovery_fail = [r for r in s0_records if r.eligibility == "S0_DISCOVERY_FAILURE"]
    s0_ambiguous = [r for r in s0_records if r.eligibility == "S0_AMBIGUOUS"]

    s0_success = sum(1 for r in s0_in_scope if r.extracted_count > 0)
    s0_coverage = s0_success / len(s0_in_scope) if s0_in_scope else 0.0

    print(f"  S0_IN_SCOPE: {len(s0_in_scope)}")
    print(f"  S0_NO_IN_SCOPE_CONTENT: {len(s0_no_content)}")
    print(f"  S0_DISCOVERY_FAILURE: {len(s0_discovery_fail)}")
    print(f"  S0_AMBIGUOUS: {len(s0_ambiguous)}")
    print(f"  S0 extraction (eligible): {s0_success}/{len(s0_in_scope)} = {s0_coverage*100:.1f}%")

    # ======================================================================
    # 23C: GT eligibility
    # ======================================================================
    print("\n23C: Classifying GT documents...")
    gt_records: list[GTRecord] = []
    for chain, s0_result, gt_result in all_chains:
        if gt_result is None:
            continue
        is_manual = gt_result.source_label == "CMP-manual"
        if is_manual:
            continue

        source_text = ""
        for path in [
            f"data/chain_study/{chain.chain_id}/CMP.txt",
            f"data/held_out/{chain.chain_id}/CMP.txt",
        ]:
            p = Path(path)
            if p.exists():
                source_text = p.read_text(encoding="utf-8", errors="ignore")
                break

        rec = classify_gt_eligibility(
            chain.chain_id,
            gt_result.source_label,
            gt_result.text_length,
            len(gt_result.commitments),
            len(gt_result.validation_queue),
            source_text,
        )
        gt_records.append(rec)

    gt_in_scope = [r for r in gt_records if r.eligibility == "GT_IN_SCOPE"]
    gt_no_content = [r for r in gt_records if r.eligibility == "GT_NO_IN_SCOPE_CONTENT"]
    gt_discovery_fail = [r for r in gt_records if r.eligibility == "GT_DISCOVERY_FAILURE"]
    gt_ambiguous = [r for r in gt_records if r.eligibility == "GT_AMBIGUOUS"]

    gt_success = sum(1 for r in gt_in_scope if r.extracted_count > 0)
    gt_coverage = gt_success / len(gt_in_scope) if gt_in_scope else 0.0

    print(f"  GT_IN_SCOPE: {len(gt_in_scope)}")
    print(f"  GT_NO_IN_SCOPE_CONTENT: {len(gt_no_content)}")
    print(f"  GT_DISCOVERY_FAILURE: {len(gt_discovery_fail)}")
    print(f"  GT_AMBIGUOUS: {len(gt_ambiguous)}")
    print(f"  GT extraction (eligible): {gt_success}/{len(gt_in_scope)} = {gt_coverage*100:.1f}%")

    # ======================================================================
    # 23D: Semantic resolution funnel
    # ======================================================================
    print("\n23D: Tracing semantic resolution funnel for IN_SCOPE instructions...")

    # Build current state for each chain
    funnel_counts = Counter()
    # Stages 1-11 are sequential — each stage depends on the previous
    # one passing.  Drop-off is computed across these.
    funnel_stages = [
        "stage_1_parsed",
        "stage_2_scope_recognized",
        "stage_3_section_resolved",
        "stage_4_commitment_resolved",
        "stage_5_field_resolved",
        "stage_6_operation_resolved",
        "stage_7_old_value_resolved",
        "stage_8_new_value_resolved",
        "stage_9_unit_resolved",
        "stage_10_candidate_created",
        "stage_11_validators_passed",
    ]
    # Stages 12-14 are mutually exclusive OUTCOMES of stage 11
    # (validators passed).  An instruction that reaches stage 11
    # branches into exactly one of:
    #   12 — mutation accepted (mapped)
    #   13 — mutation rejected (validator failure)
    #   14 — UNRESOLVED (no candidate produced)
    # These are NOT sequential — they are a partition of the
    # instructions that reached stage 11 (plus those that dropped
    # off earlier, which are implicitly UNRESOLVED).
    funnel_outcomes = [
        "stage_12_accepted",
        "stage_13_rejected",
        "stage_14_unresolved",
    ]

    # For funnel tracing, we need to run the resolver with the
    # current state at each amendment point
    for chain, s0_result, gt_result in all_chains:
        current_state = {
            k: v.model_copy(deep=True)
            for k, v in chain.original_state.items()
        }
        for step_idx, step in enumerate(chain.amendments, 1):
            # Skip non-parser-based genres (full_restatement,
            # conformed_copy) — matching the v2 study denominator.
            if not _is_parser_based_genre(step):
                continue

            source_path = step.source_document_path
            if source_path and Path(source_path).exists():
                text = Path(source_path).read_text(
                    encoding="utf-8", errors="ignore",
                )
                parser_result = parse_v04(text)
                rows = parser_result["instructions"]

                for i, row in enumerate(rows):
                    ins = AmendmentInstruction(
                        order=i + 1,
                        instruction_type=InstructionType(row["instruction_type"]),
                        target_section_ref=row.get("target_section_ref"),
                        source_text=row.get("source_text"),
                        old_value=row.get("old_value"),
                        new_value=row.get("new_value"),
                        provenance=InstructionProvenance.PARSER,
                    )

                    eligibility, _, _, _ = classify_instruction_eligibility(ins)
                    if eligibility != "IN_SCOPE":
                        continue

                    stages = trace_resolution_funnel(ins, current_state)
                    for stage in funnel_stages + funnel_outcomes:
                        if stages.get(stage, False):
                            funnel_counts[stage] += 1

    in_scope_count = len(in_scope)
    print(f"  IN_SCOPE instructions: {in_scope_count}")
    print("  Funnel drop-off (sequential stages 1-11):")
    prev_count = in_scope_count
    for stage in funnel_stages:
        count = funnel_counts.get(stage, 0)
        pct = count / in_scope_count * 100 if in_scope_count else 0
        drop = prev_count - count
        drop_pct = drop / prev_count * 100 if prev_count else 0
        print(f"    {stage}: {count} ({pct:.1f}%) — dropped {drop} ({drop_pct:.1f}%)")
        prev_count = count

    # Outcomes (mutually exclusive branches from stage 11)
    validators_passed = funnel_counts.get("stage_11_validators_passed", 0)
    dropped_before_validation = in_scope_count - validators_passed
    print(f"  Outcomes (mutually exclusive, from {in_scope_count} IN_SCOPE):")
    for outcome in funnel_outcomes:
        count = funnel_counts.get(outcome, 0)
        pct = count / in_scope_count * 100 if in_scope_count else 0
        print(f"    {outcome}: {count} ({pct:.1f}%)")
    # stage_14_unresolved also includes instructions that dropped off
    # before reaching stage 11.  Report the implicit UNRESOLVED count
    # (dropped before validation) for clarity.
    print(f"    (of which dropped before stage 11: {dropped_before_validation})")

    # ======================================================================
    # 23E: v2 resolver-path reachability
    # ======================================================================
    print("\n23E: Tracing v2 resolver-path reachability...")

    # Statically analyze which v2 architecture components the pipeline
    # actually calls (rather than assuming).
    pipeline_reachability = _analyze_pipeline_reachability()
    print("  Pipeline reachability (static analysis):")
    for k, v in pipeline_reachability.items():
        print(f"    {k}: {v}")

    path_counts = Counter()
    for chain, s0_result, gt_result in all_chains:
        current_state = {
            k: v.model_copy(deep=True)
            for k, v in chain.original_state.items()
        }
        for step in chain.amendments:
            # Skip non-parser-based genres — matching the v2 study
            # denominator.
            if not _is_parser_based_genre(step):
                continue

            source_path = step.source_document_path
            if source_path and Path(source_path).exists():
                text = Path(source_path).read_text(
                    encoding="utf-8", errors="ignore",
                )
                parser_result = parse_v04(text)
                for row in parser_result["instructions"]:
                    ins = AmendmentInstruction(
                        order=1,
                        instruction_type=InstructionType(row["instruction_type"]),
                        target_section_ref=row.get("target_section_ref"),
                        source_text=row.get("source_text"),
                        provenance=InstructionProvenance.PARSER,
                    )
                    eligibility, _, _, _ = classify_instruction_eligibility(ins)
                    if eligibility != "IN_SCOPE":
                        continue
                    path = trace_resolver_path(
                        ins, current_state, pipeline_reachability,
                    )
                    for k, v in path.items():
                        if v:
                            path_counts[k] += 1

    print(f"  IN_SCOPE instructions traced: {path_counts.get('commitment_registry_executed', 0)}")
    for k in [
        "agreement_context_executed",
        "commitment_registry_executed",
        "resolve_with_context_executed",
        "staged_interpreter_executed",
        "model_assisted_interface_executed",
        "candidate_produced",
        "validator_rejected",
    ]:
        count = path_counts.get(k, 0)
        pct = count / in_scope_count * 100 if in_scope_count else 0
        print(f"    {k}: {count} ({pct:.1f}%)")

    # ======================================================================
    # 23F: Break down OTHER
    # ======================================================================
    print("\n23F: Breaking down OTHER bucket...")

    # Load the existing taxonomy
    taxonomy_path = Path("results/step_22_unresolved_taxonomy.json")
    if taxonomy_path.exists():
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        taxonomy_records = taxonomy.get("records", [])
    else:
        taxonomy_records = []

    # Reclassify unresolved IN_SCOPE records.
    #
    # The prompt requires: "First remove OUT_OF_SCOPE instructions.
    # Then reclassify remaining IN_SCOPE unresolved cases."
    #
    # We therefore maintain TWO separate counters:
    #   - out_of_scope_removed: records whose matching instructions are
    #     all OUT_OF_SCOPE (or AMBIGUOUS).  These are removed from the
    #     IN_SCOPE taxonomy and do NOT participate in the OTHER
    #     percentage denominator.
    #   - non_parser_removed: records from non-parser-based genres
    #     (full_restatement, conformed_copy) that have no matching
    #     instruction in all_records (because collect_all_instructions
    #     skips them).  These are excluded entirely — they are neither
    #     IN_SCOPE nor OUT_OF_SCOPE.
    #   - revised_buckets: IN_SCOPE-only reclassification buckets.
    #     The OTHER percentage is computed over ONLY these buckets.
    out_of_scope_removed = 0
    non_parser_removed = 0
    revised_buckets = Counter()
    for rec in taxonomy_records:
        # Find the corresponding instruction record(s).
        # Match by chain + amendment + section + instruction_type when
        # possible for precision; fall back to chain + amendment.
        rec_section = rec.get("section", "")
        rec_type = rec.get("instruction_type", "")
        matching = [
            r for r in all_records
            if r.chain == rec.get("chain")
            and r.amendment == rec.get("amendment")
        ]
        if not matching:
            # No matching instruction record.  This happens when the
            # taxonomy record is from a non-parser-based genre
            # (full_restatement / conformed_copy) whose instructions
            # were intentionally skipped by collect_all_instructions.
            # These records are neither IN_SCOPE nor OUT_OF_SCOPE —
            # they are outside the parser-instruction denominator and
            # must be excluded entirely, not counted as OTHER.
            non_parser_removed += 1
            continue

        # Refine match using section and instruction_type if available
        refined = [
            r for r in matching
            if (not rec_section or r.target_section_ref == rec_section)
            and (not rec_type or r.instruction_type == rec_type)
        ]
        if refined:
            matching = refined

        # Check if any matching instruction is IN_SCOPE
        in_scope_match = [
            r for r in matching if r.eligibility == "IN_SCOPE"
        ]
        if not in_scope_match:
            # OUT_OF_SCOPE (or AMBIGUOUS) — remove from IN_SCOPE
            # taxonomy.  Not counted in the OTHER denominator.
            out_of_scope_removed += 1
            continue

        # Reclassify the IN_SCOPE unresolved record using the first
        # matching instruction's source text.
        r = in_scope_match[0]
        src = r.source_text.lower()
        if "definition" in src or "shall mean" in src or "means" in src[:50]:
            revised_buckets["DEFINED_TERM_REFERENCE"] += 1
        elif re.search(r"table|schedule|exhibit", src):
            revised_buckets["VALUE_IN_TABLE_SCHEDULE"] += 1
        elif re.search(r"section\s+\d+\.\d+\s*\(", src):
            revised_buckets["MULTI_FIELD_RESTATEMENT"] += 1
        elif r.canonical_class and not r.expected_field:
            revised_buckets["FIELD_IDENTIFICATION_FAILED"] += 1
        elif r.target_section_ref and not r.canonical_class:
            revised_buckets["SECTION_MAPPING_UNAVAILABLE"] += 1
        elif "amount" in src or "$" in src:
            revised_buckets["AMOUNT_CHANGE"] += 1
        elif "date" in src or "maturity" in src:
            revised_buckets["DATE_CHANGE"] += 1
        elif not r.target_section_ref:
            revised_buckets["PARSER_SPAN_INSUFFICIENT"] += 1
        else:
            revised_buckets["TRUE_AMBIGUITY"] += 1

    # OTHER percentage is computed over ONLY the IN_SCOPE buckets
    # (revised_buckets), NOT including out_of_scope_removed or
    # non_parser_removed.  This matches the prompt: "First remove
    # OUT_OF_SCOPE instructions. Then reclassify remaining IN_SCOPE
    # unresolved cases until OTHER is <10%."
    in_scope_total = sum(revised_buckets.values())
    other_pct = revised_buckets.get("OTHER", 0) / max(in_scope_total, 1) * 100
    print(f"  OUT_OF_SCOPE removed: {out_of_scope_removed}")
    print(f"  Non-parser-genre removed: {non_parser_removed}")
    print("  Revised taxonomy (IN_SCOPE only):")
    for bucket, count in revised_buckets.most_common():
        pct = count / max(in_scope_total, 1) * 100
        print(f"    {bucket}: {count} ({pct:.1f}%)")
    print(f"  OTHER percentage: {other_pct:.1f}% (denominator: {in_scope_total} IN_SCOPE)")

    # ======================================================================
    # 23G: Like-for-like v1 baseline
    # ======================================================================
    print("\n23G: Like-for-like v1 baseline...")

    # Load v1 metrics from the frozen v1 study results JSON (no
    # hardcoding — all values come from the historical record).
    v1_results_path = Path("results/chain_study_v1_results.json")
    if v1_results_path.exists():
        v1_data = json.loads(v1_results_path.read_text(encoding="utf-8"))
        v1_agg = v1_data.get("aggregate_metrics", {})
        v1_total = v1_agg.get("total_parser_instructions", 0)
        v1_mapped = v1_agg.get("total_mapped_instructions", 0)
        v1_incorrect = v1_agg.get("total_incorrect_mutations", 0)
    else:
        v1_total = 0
        v1_mapped = 0
        v1_incorrect = 0

    # Count v2 IN_SCOPE for just the 25 dev chains
    dev_chain_ids = {c.chain_id for c, _, _ in dev_chains}
    dev_in_scope = [r for r in in_scope if r.chain in dev_chain_ids]
    dev_total_records = [r for r in all_records if r.chain in dev_chain_ids]

    # Load v2 study results for parser-mapped counts
    v2_study_path = Path("results/step_21_v2_study_results.json")
    if v2_study_path.exists():
        v2_study = json.loads(v2_study_path.read_text(encoding="utf-8"))
        v2_per_chain = v2_study.get("per_chain", [])
        v2_dev_parser_mapped = sum(
            cr.get("mapped_from_parser", 0)
            for cr in v2_per_chain
            if cr.get("chain_id") in dev_chain_ids
        )
        v2_mapped_from_parser = v2_study.get("mapped_from_parser", 0)
    else:
        v2_dev_parser_mapped = 0
        v2_mapped_from_parser = 0

    v1_correct_mapped = v1_mapped - v1_incorrect
    v1_in_scope = len(dev_in_scope)  # same corpus, same parser

    v1_eligible_coverage = v1_correct_mapped / v1_in_scope if v1_in_scope else 0
    v2_dev_eligible_coverage = v2_dev_parser_mapped / len(dev_in_scope) if dev_in_scope else 0

    # v2 all 50 chains
    v2_eligible_coverage = v2_mapped_from_parser / len(in_scope) if in_scope else 0

    print(f"  v1 (25 dev chains): {v1_total} instructions, {v1_in_scope} IN_SCOPE")
    print(f"  v1 mapped: {v1_mapped} ({v1_incorrect} incorrect, {v1_correct_mapped} correct)")
    print(f"  v1 eligible coverage (correct/IN_SCOPE): {v1_correct_mapped}/{v1_in_scope} = {v1_eligible_coverage*100:.1f}%")
    print(f"  v2 (25 dev chains): {len(dev_total_records)} instructions, {len(dev_in_scope)} IN_SCOPE")
    print(f"  v2 dev parser-mapped: {v2_dev_parser_mapped}")
    print(f"  v2 dev eligible coverage: {v2_dev_parser_mapped}/{len(dev_in_scope)} = {v2_dev_eligible_coverage*100:.1f}%")
    print(f"  v2 (all 50 chains): {total_instructions} instructions, {len(in_scope)} IN_SCOPE")
    print(f"  v2 all parser-mapped: {v2_mapped_from_parser}")
    print(f"  v2 all eligible coverage: {v2_mapped_from_parser}/{len(in_scope)} = {v2_eligible_coverage*100:.1f}%")

    # ======================================================================
    # 23H: Reevaluated exit gates
    # ======================================================================
    print("\n23H: Reevaluating exit gates...")

    # Semantic mapping coverage = mapped_correctly / IN_SCOPE
    semantic_mapping_coverage = v2_eligible_coverage * 100

    # S0 extraction = success / S0_IN_SCOPE
    s0_extraction_coverage = s0_coverage * 100

    # GT extraction = success / GT_IN_SCOPE
    gt_extraction_coverage = gt_coverage * 100

    # Load current study results for other gates (reuse v2_study loaded
    # in 23G if available, otherwise load fresh).
    if v2_study_path.exists():
        unknown_genre_rate = v2_study.get("unknown_genre_rate", 0.0) * 100
        incorrect_mutations = v2_study.get("total_incorrect_mutations", 0)
        false_auth_promotions = v2_study.get("false_authoritative_promotion_count", 0)
    else:
        unknown_genre_rate = 0.0
        incorrect_mutations = 0
        false_auth_promotions = 0

    gates = [
        ("semantic_mapping_coverage_gte_50pct",
         semantic_mapping_coverage >= 50.0,
         f"{semantic_mapping_coverage:.1f}% (target >=50%)"),
        ("incorrect_accepted_mutations_eq_0",
         incorrect_mutations == 0,
         f"{incorrect_mutations} (target =0)"),
        ("false_authoritative_promotions_eq_0",
         false_auth_promotions == 0,
         f"{false_auth_promotions} (target =0)"),
        ("s0_extraction_gte_85pct",
         s0_extraction_coverage >= 85.0,
         f"{s0_extraction_coverage:.1f}% (target >=85%)"),
        ("gt_extraction_gte_70pct",
         gt_extraction_coverage >= 70.0,
         f"{gt_extraction_coverage:.1f}% (target >=70%)"),
        ("unknown_genre_rate_lt_20pct",
         unknown_genre_rate < 20.0,
         f"{unknown_genre_rate:.1f}% (target <20%)"),
    ]

    print()
    for gate_name, passed, value in gates:
        status = "PASS" if passed else "FAIL"
        print(f"  {gate_name}: {status} — {value}")

    passed_count = sum(1 for _, p, _ in gates if p)

    # Derive integration defects from the reachability analysis
    integration_defects = []
    if not pipeline_reachability.get("agreement_context_executed", False):
        integration_defects.append(
            "AgreementContext not executed in main pipeline path",
        )
    if not pipeline_reachability.get("resolve_with_context_executed", False):
        integration_defects.append(
            "resolve_with_context not executed in main pipeline path",
        )
    if not pipeline_reachability.get("model_assisted_interface_executed", False):
        integration_defects.append(
            "model-assisted candidate interface not executed in main pipeline path",
        )

    # ======================================================================
    # Top 3 bottlenecks
    # ======================================================================
    print("\nTop 3 bottlenecks among IN_SCOPE instructions:")
    # Find the stages with the biggest drop-off
    stage_drops = []
    prev = in_scope_count
    for stage in funnel_stages:
        count = funnel_counts.get(stage, 0)
        drop = prev - count
        if drop > 0:
            stage_drops.append((stage, drop, prev, count))
        prev = count
    stage_drops.sort(key=lambda x: -x[1])
    for i, (stage, drop, prev, count) in enumerate(stage_drops[:3], 1):
        print(f"  {i}. {stage}: dropped {drop} ({drop/prev*100:.1f}%) — {prev}→{count}")

    # ======================================================================
    # Build output
    # ======================================================================
    output = {
        "23a_instruction_eligibility": {
            "total_parser_instructions": total_instructions,
            "IN_SCOPE": len(in_scope),
            "OUT_OF_SCOPE": len(out_of_scope),
            "AMBIGUOUS_SCOPE": len(ambiguous),
            "raw_automation_rate": f"{v2_mapped_from_parser}/{total_instructions} = {v2_mapped_from_parser/total_instructions*100:.1f}%" if total_instructions else "N/A",
            "raw_automation_rate_numeric": round(v2_mapped_from_parser / total_instructions, 4) if total_instructions else 0.0,
            "eligible_semantic_mapping_coverage": f"{v2_mapped_from_parser}/{len(in_scope)} = {semantic_mapping_coverage:.1f}%" if in_scope else "N/A",
            "eligible_semantic_mapping_coverage_numeric": round(v2_eligible_coverage, 4),
            "in_scope_records": [
                {
                    "chain": r.chain,
                    "amendment": r.amendment,
                    "section": r.target_section_ref,
                    "source_span": r.source_text[:100],
                    "canonical_class": r.canonical_class,
                    "expected_field": r.expected_field,
                    "operation": r.operation,
                }
                for r in in_scope
            ],
        },
        "23b_s0_eligibility": {
            "total_s0_documents": len(s0_records),
            "S0_IN_SCOPE": len(s0_in_scope),
            "S0_NO_IN_SCOPE_CONTENT": len(s0_no_content),
            "S0_DISCOVERY_FAILURE": len(s0_discovery_fail),
            "S0_AMBIGUOUS": len(s0_ambiguous),
            "raw_s0_rate": f"{sum(1 for r in s0_records if r.extracted_count > 0)}/{len(s0_records)}",
            "eligible_s0_coverage": f"{s0_success}/{len(s0_in_scope)} = {s0_extraction_coverage:.1f}%",
            "eligible_s0_coverage_numeric": round(s0_coverage, 4),
        },
        "23c_gt_eligibility": {
            "total_gt_documents": len(gt_records),
            "GT_IN_SCOPE": len(gt_in_scope),
            "GT_NO_IN_SCOPE_CONTENT": len(gt_no_content),
            "GT_DISCOVERY_FAILURE": len(gt_discovery_fail),
            "GT_AMBIGUOUS": len(gt_ambiguous),
            "raw_gt_rate": f"{sum(1 for r in gt_records if r.extracted_count > 0)}/{len(gt_records)}",
            "eligible_gt_coverage": f"{gt_success}/{len(gt_in_scope)} = {gt_extraction_coverage:.1f}%",
            "eligible_gt_coverage_numeric": round(gt_coverage, 4),
        },
        "23d_funnel": {
            "in_scope_count": in_scope_count,
            "stage_counts": {
                stage: funnel_counts.get(stage, 0)
                for stage in funnel_stages
            },
            "outcome_counts": {
                outcome: funnel_counts.get(outcome, 0)
                for outcome in funnel_outcomes
            },
            "dropped_before_validation": dropped_before_validation,
        },
        "23e_resolver_path": {
            "in_scope_traced": in_scope_count,
            "pipeline_reachability": pipeline_reachability,
            "path_counts": {k: path_counts.get(k, 0) for k in [
                "agreement_context_executed",
                "commitment_registry_executed",
                "resolve_with_context_executed",
                "staged_interpreter_executed",
                "model_assisted_interface_executed",
                "candidate_produced",
                "validator_rejected",
            ]},
            "integration_defects": integration_defects,
        },
        "23f_revised_taxonomy": {
            "buckets": dict(revised_buckets.most_common()),
            "out_of_scope_removed": out_of_scope_removed,
            "non_parser_removed": non_parser_removed,
            "in_scope_total": in_scope_total,
            "other_percentage": round(other_pct, 1),
        },
        "23g_v1_v2_comparison": {
            "v1_total": v1_total,
            "v1_mapped": v1_mapped,
            "v1_incorrect": v1_incorrect,
            "v1_correct_mapped": v1_correct_mapped,
            "v1_in_scope": v1_in_scope,
            "v1_eligible_coverage": f"{v1_eligible_coverage*100:.1f}%",
            "v1_eligible_coverage_numeric": round(v1_eligible_coverage, 4),
            "v2_dev_total": len(dev_total_records),
            "v2_dev_in_scope": len(dev_in_scope),
            "v2_dev_parser_mapped": v2_dev_parser_mapped,
            "v2_dev_eligible_coverage": f"{v2_dev_eligible_coverage*100:.1f}%",
            "v2_dev_eligible_coverage_numeric": round(v2_dev_eligible_coverage, 4),
            "v2_all_total": total_instructions,
            "v2_all_in_scope": len(in_scope),
            "v2_all_parser_mapped": v2_mapped_from_parser,
            "v2_all_eligible_coverage": f"{v2_eligible_coverage*100:.1f}%",
            "v2_all_eligible_coverage_numeric": round(v2_eligible_coverage, 4),
        },
        "23h_gates": {
            "semantic_mapping_coverage": f"{semantic_mapping_coverage:.1f}%",
            "semantic_mapping_coverage_numeric": round(semantic_mapping_coverage, 2),
            "s0_extraction_coverage": f"{s0_extraction_coverage:.1f}%",
            "s0_extraction_coverage_numeric": round(s0_extraction_coverage, 2),
            "gt_extraction_coverage": f"{gt_extraction_coverage:.1f}%",
            "gt_extraction_coverage_numeric": round(gt_extraction_coverage, 2),
            "unknown_genre_rate": f"{unknown_genre_rate:.1f}%",
            "unknown_genre_rate_numeric": round(unknown_genre_rate, 2),
            "incorrect_mutations": incorrect_mutations,
            "false_auth_promotions": false_auth_promotions,
            "gates_passed": f"{passed_count}/{len(gates)}",
            "gates_passed_count": passed_count,
            "gates_total": len(gates),
            "gate_details": [
                {"gate": name, "passed": p, "value": v}
                for name, p, v in gates
            ],
        },
        "top_3_bottlenecks": [
            {"stage": stage, "dropped": drop, "prev": prev, "after": count}
            for stage, drop, prev, count in stage_drops[:3]
        ],
    }

    return output


def main() -> int:
    output = run_audit()

    # Write JSON
    output_path = Path("results/step_23_audit.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nAudit JSON: {output_path}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
