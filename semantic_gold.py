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
    - A1 ins 4 (Section 7.10): MAPPED → leverage ratio schedule change
    - A2 ins 3 (Section 7.10): MAPPED → leverage ratio schedule change
    - A3 ins 1 (Section 7.01): MAPPED → junior credit agreement addition
    - All others: UNRESOLVED (UNKNOWN_COMMITMENT — not tracked commitments)
  - Amedisys: 0 parser instructions (full restatement, parser finds nothing)
  - Bausch & Lomb: 0 parser instructions (conformed copy, parser finds nothing)

Parser fix: A2 Section 7.10 was previously missed by the parser due to
a regex bridging bug in REPLACE_V04 (the gap between target and "amended
by" could span across section boundaries).  The fix (tempered group that
stops at another Section/Article reference) now correctly captures the
A2 Section 7.10 leverage ratio change, enabling end-to-end reconstruction
of the Ameresco chain.
"""
from __future__ import annotations

from datetime import datetime

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
      ins 0: REPLACE_TEXT, Section 2.07 (repayment installments) → UNRESOLVED
      ins 1: ADD, Section 2.12 (repayment installments) → UNRESOLVED
      ins 2: REPLACE_TEXT, Section 3.03 (SOFR determination) → UNRESOLVED
      ins 3: REPLACE_TEXT, Section 3.03 (SOFR paragraphs) → UNRESOLVED
      ins 4: REPLACE_TEXT, Section 7.10 (leverage ratio) → MAPPED

    Note: ins 0 was previously Section 6 (a cross-reference that the
    parser incorrectly matched by bridging to Section 2.07's amendment
    language).  The parser regex fix (tempered group in REPLACE_V04)
    now correctly identifies Section 2.07 as the target.
    """
    return [
        (0, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 2.07",
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
            old_value={
                "step_down_schedule": [
                    {"period_end": "2022-03-31", "threshold": 4.50},
                    {"period_end": "2022-06-30", "threshold": 4.25},
                    {"period_end": "2022-09-30", "threshold": 4.00},
                    {"period_end": "2022-12-31", "threshold": 4.00},
                ],
                "steady_state_threshold": 3.50,
            },
            new_value={
                "step_down_schedule": [
                    {"period_end": "2023-06-30", "threshold": 4.00},
                    {"period_end": "2023-09-30", "threshold": 4.25},
                ],
                "steady_state_threshold": 3.50,
            },
            unit="ratio",
            effective_at=_dt("2023-08-24T00:00:00"),
            source_span=(
                "Total Funded Debt to EBITDA Ratio.  The Loan Parties "
                "shall not permit the  Core Leverage Ratio"
            ),
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.95,
            ambiguity_reason=None,
            citation_section="Section 7.10",
        )),
    ]


def gold_ameresco_a2() -> list[tuple[int, StructuredMutation]]:
    """Gold mappings for Ameresco A2 (Amendment No. 4, Dec 11, 2023).

    Parser found 4 instructions:
      ins 0: REPLACE_TEXT, Section 2.07 (repayment installments) → UNRESOLVED
      ins 1: ADD, Section 2.09 → UNRESOLVED
      ins 2: ADD, Article VI → UNRESOLVED
      ins 3: REPLACE_TEXT, Section 7.10 (leverage ratio) → MAPPED

    Note: ins 0 was previously Section 2.05(b)(ii) and ins 3 was
    previously Section 7.04(c)(xiii).  Both were incorrect matches
    caused by the parser's REPLACE_V04 regex bridging across section
    boundaries to adjacent amendment language.  The parser regex fix
    (tempered group in REPLACE_V04) now correctly identifies Section
    2.07 and Section 7.10 as the targets, and the A2 Section 7.10
    leverage ratio change is now captured and mapped.
    """
    return [
        (0, StructuredMutation(
            commitment_id=None,
            field=None,
            operation=InstructionType.REPLACE_TEXT,
            ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
            provenance=InstructionProvenance.MANUAL,
            citation_section="Section 2.07",
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
            commitment_id="financial_covenant.leverage_ratio",
            field="applicability",
            operation=InstructionType.REPLACE_VALUE,
            old_value={
                "step_down_schedule": [
                    {"period_end": "2023-06-30", "threshold": 4.00},
                    {"period_end": "2023-09-30", "threshold": 4.25},
                ],
                "steady_state_threshold": 3.50,
            },
            new_value={
                "step_down_schedule": [
                    {"period_end": "2023-12-31", "threshold": 3.75},
                ],
                "steady_state_threshold": 3.50,
            },
            unit="ratio",
            effective_at=_dt("2023-12-11T00:00:00"),
            source_span=(
                "Section 7.10 of the Credit Agreement is hereby amended "
                "by deleting paragraph (a) in its entirety and replacing "
                "it with the following: (a) Total Funded Debt to EBITDA "
                "Ratio. The Loan Parties shall not permit the Core "
                "Leverage Ratio as of the end of each fiscal quarter "
                "(i) ending on December 31, 2023 to exceed 3.75 to "
                "1.00, and (ii) for any quarter ending thereafter, to "
                "exceed 3.50 to 1.00."
            ),
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.95,
            ambiguity_reason=None,
            citation_section="Section 7.10",
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
            old_value=None,
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
            source_span=(
                "Junior Credit Agreement in an  aggregate amount "
                "not to exceed $150,000,000"
            ),
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
