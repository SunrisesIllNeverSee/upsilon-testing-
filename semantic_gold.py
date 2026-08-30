"""Gold semantic mappings for the 3 real EDGAR chains.

These are the EXPECTED outputs of the semantic mapper when given the
real parser instructions from the 3 EDGAR chains.  They serve as
ground truth for testing the mapper independently from the pipeline.

Each gold mapping specifies:
  - chain_id and amendment_number (which amendment)
  - parser_instruction_index (which parser instruction, 0-based)
  - expected StructuredMutation (or expected ambiguity_reason if UNRESOLVED)

The gold mappings were created by reading the real amendment text and
the real parser output, then hand-specifying what the mapper should
produce.  They are NOT derived from the mapper itself — they are
independent expectations.

Chain summary:
  - Ameresco: 14 parser instructions across 3 amendments
    - A1 ins 5 (Section 7.10): MAPPED → leverage ratio schedule change
    - A3 ins 2 (Section 7.01): MAPPED → junior credit agreement addition
    - All others: UNRESOLVED (UNKNOWN_COMMITMENT — not tracked commitments)
  - Amedisys: 0 parser instructions (full restatement, parser finds nothing)
  - Bausch & Lomb: 0 parser instructions (conformed copy, parser finds nothing)

Known parser gap: A2 Section 7.10 leverage ratio change is NOT captured
by the parser (parser found 4 instructions, none for Section 7.10).
The mapper cannot map what the parser does not produce.  This is a
parser limitation, documented here for completeness.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from models import InstructionProvenance, InstructionType
from semantic_mapper import AmbiguityReason, StructuredMutation


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------------------
# Ameresco — gold mappings
# ---------------------------------------------------------------------------


def gold_ameresco_a1() -> list[tuple[int, StructuredMutation]]:
    """Gold mappings for Ameresco A1 (Amendment No. 3, Aug 24, 2023).

    Parser found 5 instructions:
      ins 0: REPLACE_TEXT, Section 6 (SOFR definitions) → UNRESOLVED
      ins 1: ADD, Section 2.12 (repayment installments) → UNRESOLVED
      ins 2: REPLACE_TEXT, Section 3.03 (SOFR determination) → UNRESOLVED
      ins 3: REPLACE_TEXT, Section 3.03 (SOFR paragraphs) → UNRESOLVED
      ins 4: REPLACE_TEXT, Section 7.10 (leverage ratio) → MAPPED
    """
    return [
        (0, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 6",
        )),
        (1, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.ADD,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 2.12",
        )),
        (2, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 3.03",
        )),
        (3, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 3.03",
        )),
        (4, StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="applicability",
            operation=InstructionType.REPLACE_VALUE,
            new_value={
                "step_down_schedule": [
                    {"period_end": "2023-06-30", "threshold": 4.00},
                    {"period_end": "2023-09-30", "threshold": 4.25},
                ],
                "steady_state_threshold": 3.50,
            },
            unit="ratio",
            effective_at=_dt("2023-08-24T00:00:00"),
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.95,
            ambiguity_reason=None,
            citation_section="Section 7.10",
        )),
    ]


def gold_ameresco_a2() -> list[tuple[int, StructuredMutation]]:
    """Gold mappings for Ameresco A2 (Amendment No. 4, Dec 11, 2023).

    Parser found 4 instructions — NONE for Section 7.10 (parser gap).
    All 4 are non-commitment changes:
      ins 0: REPLACE_TEXT, Section 2.05(b)(ii) → UNRESOLVED
      ins 1: ADD, Section 2.09 → UNRESOLVED
      ins 2: ADD, Article VI → UNRESOLVED
      ins 3: REPLACE_TEXT, Section 7.04(c)(xiii) → UNRESOLVED

    NOTE: The A2 Section 7.10 leverage ratio change IS in the amendment
    text but was NOT captured by the parser.  The mapper cannot map it
    because no parser instruction exists for it.  This is a documented
    parser limitation, not a mapper limitation.
    """
    return [
        (0, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 2.05(b)(ii)",
        )),
        (1, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.ADD,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 2.09",
        )),
        (2, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.ADD,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Article VI",
        )),
        (3, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 7.04(c)(xiii)",
        )),
    ]


def gold_ameresco_a3() -> list[tuple[int, StructuredMutation]]:
    """Gold mappings for Ameresco A3 (Amendment No. 6, Jun 28, 2024).

    Parser found 5 instructions:
      ins 0: DELETE, Section 6.16 → UNRESOLVED
      ins 1: ADD, Section 7.01 (Junior Credit Agreement) → MAPPED
      ins 2: REPLACE_TEXT, Section 7.02 (Liens) → UNRESOLVED
      ins 3: REPLACE_TEXT, Section 7.03 (Guarantees) → UNRESOLVED
      ins 4: DELETE, Section 7.13 → UNRESOLVED
    """
    return [
        (0, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.DELETE,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 6.16",
        )),
        (1, StructuredMutation(
            commitment_id="facility.junior_credit_agreement",
            field="amount",
            operation=InstructionType.ADD,
            new_value={
                "canonical_key": "facility.junior_credit_agreement",
                "commitment_type": "facility_commitment",
                "party": ["borrower"],
                "action": "permit",
                "subject": "junior_credit_agreement",
                "threshold": 150_000_000,
                "unit": "usd",
            },
            unit="usd",
            effective_at=_dt("2024-06-28T00:00:00"),
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.90,
            ambiguity_reason=None,
            citation_section="Section 7.01",
        )),
        (2, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 7.02",
        )),
        (3, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 7.03",
        )),
        (4, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.DELETE,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 7.13",
        )),
    ]


def gold_ameresco() -> dict[str, list[tuple[int, StructuredMutation]]]:
    """All gold mappings for the Ameresco chain, keyed by amendment number."""
    return {
        "A1": gold_ameresco_a1(),
        "A2": gold_ameresco_a2(),
        "A3": gold_ameresco_a3(),
    }


# ---------------------------------------------------------------------------
# Amedisys — gold mappings (empty: parser finds 0 instructions)
# ---------------------------------------------------------------------------


def gold_amedisys() -> dict[str, list[tuple[int, StructuredMutation]]]:
    """Gold mappings for Amedisys chain.

    Parser finds 0 instructions on both A1 and A2 (full restatement
    pattern).  There are no parser instructions to map, so the gold
    mapping set is empty for each amendment.
    """
    return {"A1": [], "A2": []}


# ---------------------------------------------------------------------------
# Bausch & Lomb — gold mappings (empty: parser finds 0 instructions)
# ---------------------------------------------------------------------------


def gold_bausch_lomb() -> dict[str, list[tuple[int, StructuredMutation]]]:
    """Gold mappings for Bausch & Lomb chain.

    Parser finds 0 instructions on all 4 amendments (conformed copy
    pattern).  There are no parser instructions to map.
    """
    return {"A1": [], "A2": [], "A3": [], "A4": []}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def all_gold_mappings() -> dict[str, dict[str, list[tuple[int, StructuredMutation]]]]:
    """Return all gold mappings for all 3 EDGAR chains.

    Returns:
        {chain_id: {amendment_label: [(parser_ins_index, gold_mutation), ...]}}
    """
    return {
        "EDGAR-AMERESCO": gold_ameresco(),
        "EDGAR-AMEDISYS": gold_amedisys(),
        "EDGAR-BAUSCH-LOMB": gold_bausch_lomb(),
    }
