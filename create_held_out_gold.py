"""Create proxy gold annotations for the preregistered evaluation
subset of the Step 19B held-out confirmatory study.

PREREGISTERED SUBSET:
  - HELD-002 (Wheeler Real Estate) — has CMP
  - HELD-004 (Raymond James) — has CMP
  - HELD-008 (Purple Innovation) — has CMP
  - HELD-001 (Cadiz Inc) — gold from S0
  - HELD-005 (Flexsteel Industries) — gold from S0

GOLD PROTOCOL:
  The Step 19B prompt requires HUMAN GOLD: independent structured gold
  commitments created by human annotators, with source spans, annotator
  identity, verification status, and double-annotation with adjudication
  for the preregistered subset.  Reconstruction output must NOT be used
  to create the gold state.

  This script produces an AUTOMATED PROXY SCAFFOLD, NOT verified human
  gold.  It uses two independent automated annotators that read the
  source documents directly:

    1. Annotator A (annotator_a_regex): regex-heavy strategy requiring
       explicit Section/ARTICLE prefixes, aggressive TOC filtering, and
       "shall not" phrasing for threshold extraction.
    2. Annotator B (annotator_b_keyword): keyword-scan strategy that
       accepts bare-number headers, uses simpler regex patterns, and
       does not require "shall not" phrasing.

  The two annotators use genuinely different strategies (different
  section detection, different clause extraction, different value
  parsing) to provide automated cross-validation.  They are NOT the
  frozen system's extractors — they are separate functions that read
  source documents independently of the reconstruction pipeline.

  Double-annotation with adjudication is performed via double_annotate():
    - Agreements → verification_status "adjudicated"
    - Disagreements → adjudicator selects Annotator A's value (more
      specific regex strategy) and records the disagreement in notes
    - Single-annotator records → verification_status "single"

  All gold records include source_span (character offsets in the source
  text), annotator identity, and verification status.

LIMITATION — NOT HUMAN GOLD:
  The Step 19B protocol requires HUMAN GOLD.  Automated annotators
  cannot substitute for human verification because they share the
  system's rule-based paradigm and may share blind spots.  The output
  of this script is a PROXY SCAFFOLD that human annotators can verify,
  correct, and lock.  The preregistration status is
  "pending_human_annotation" until human annotators populate and verify
  the gold files.  All gold-agreement statistics derived from this
  scaffold are provisional and must not be reported as final human-gold
  agreement.

CRITICAL: Gold annotations are created from the SOURCE DOCUMENTS ONLY.
Reconstruction output is NOT used to create the gold state.

Usage:
    python create_held_out_gold.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from gold_schema import GoldRecord, save_gold_file, validate_gold_record

GOLD_DIR = Path("data/held_out/gold")
HELD_OUT_MANIFEST = Path("data/held_out/manifest.json")

# Annotator identities
ANNOTATOR_A = "annotator_a_regex"
ANNOTATOR_B = "annotator_b_keyword"
ADJUDICATOR = "adjudicator_1"


# ---------------------------------------------------------------------------
# Independent annotators
# ---------------------------------------------------------------------------
# The annotator functions below use genuinely different strategies to
# provide independent cross-validation.  Annotator A is regex-heavy and
# conservative; Annotator B is keyword-scan and permissive.  Both read
# the source document directly and do NOT use reconstruction output.
# ---------------------------------------------------------------------------


def _classify_commitment_type(name: str) -> str:
    """Classify a covenant clause name into a commitment type."""
    name_lower = name.lower()
    if "leverage" in name_lower:
        return "leverage_ratio"
    if "coverage" in name_lower:
        return "coverage_ratio"
    if "tangible net worth" in name_lower or "net worth" in name_lower:
        return "tangible_net_worth"
    if "liquidity" in name_lower:
        return "liquidity"
    if "indebtedness" in name_lower:
        return "indebtedness_limit"
    if "collateral" in name_lower or "properties" in name_lower:
        return "collateral_requirement"
    if "debt service" in name_lower:
        return "debt_service_coverage"
    return "other"


def _make_records_from_values(
    values: dict,
    clause: dict,
    document_id: str,
    issuer: str,
    annotator: str,
    verification_status: str = "single",
) -> list[GoldRecord]:
    """Build GoldRecord objects from a parsed values dict."""
    records: list[GoldRecord] = []
    commitment_id = f"financial_covenant.{values.get('commitment_type', 'unknown')}"
    for field_name in [
        "threshold", "operator", "unit", "party",
        "frequency", "commitment_type",
    ]:
        if field_name in values and values[field_name]:
            record = GoldRecord(
                issuer=issuer,
                document=document_id,
                section=clause["clause_ref"],
                commitment_id=commitment_id,
                field=field_name,
                value=values[field_name],
                unit=values.get("unit", ""),
                source_span=(clause["start_offset"], clause["end_offset"]),
                annotator=annotator,
                verification_status=verification_status,
            )
            errors = validate_gold_record(record)
            if not errors:
                records.append(record)
    return records


# ---------------------------------------------------------------------------
# Annotator A: regex-heavy approach (precise section detection)
# ---------------------------------------------------------------------------


def _annotator_a_find_sections(text: str) -> list[tuple[int, int, str]]:
    """Find financial covenant sections using precise regex patterns.

    Uses multiple patterns with TOC-entry filtering and multi-line
    header support.  This is the more conservative annotator — it
    requires explicit "Section"/"ARTICLE" prefixes and filters out
    table-of-contents entries aggressively.
    """
    sections: list[tuple[int, int, str]] = []

    # Pattern 1: "Section X.Y Financial Covenants" with explicit prefix
    for m in re.finditer(
        r"(?:§|Section|SECTION|ARTICLE)\s*([\d.]+|[IVX]+)\s*\.?\s*[\xa0 ]*\n?\s*"
        r"(?:Certain\s+)?Financial\s+Covenants",
        text, re.IGNORECASE,
    ):
        after = text[m.end():m.end() + 20]
        if re.match(r"\s*\d+\s*\n", after):
            next_100 = text[m.end():m.end() + 100]
            if re.search(r"(?:§|Section|[\d.]+\s*\n)", next_100):
                continue
        start = m.start()
        top_num = re.match(r"([\d.]+)", m.group(1)).group(1).split(".")[0]
        search_text = text[m.end():m.end() + 20000]
        next_section = None
        for sm in re.finditer(
            r"(?:§|Section|SECTION|ARTICLE)\s*(\d[\d.]*)\s*\.?\s*[\xa0 ]*\n?\s*[A-Z]",
            search_text,
        ):
            next_top = sm.group(1).split(".")[0]
            if next_top != top_num:
                next_section = sm
                break
        end = m.end() + next_section.start() if next_section else m.end() + 10000
        sections.append((start, end, m.group()))

    # Pattern 2: "Financial Condition" sections
    if not sections:
        for m in re.finditer(
            r"(?:§|Section|SECTION|ARTICLE)\s*([\d.]+|[IVX]+)\s*\.?\s*[\xa0 ]*\n?\s*"
            r"(?:Certain\s+)?Financial\s+Condition",
            text, re.IGNORECASE,
        ):
            after = text[m.end():m.end() + 20]
            if re.match(r"\s*\d+\s*\n", after):
                next_100 = text[m.end():m.end() + 100]
                if re.search(r"(?:§|Section|[\d.]+\s*\n)", next_100):
                    continue
            start = m.start()
            top_num = re.match(r"([\d.]+)", m.group(1)).group(1).split(".")[0]
            search_text = text[m.end():m.end() + 20000]
            next_section = None
            for sm in re.finditer(
                r"(?:§|Section|SECTION|ARTICLE)\s*(\d[\d.]*)\s*\.?\s*[\xa0 ]*\n?\s*[A-Z]",
                search_text,
            ):
                next_top = sm.group(1).split(".")[0]
                if next_top != top_num:
                    next_section = sm
                    break
            end = m.end() + next_section.start() if next_section else m.end() + 10000
            sections.append((start, end, m.group()))

    return sections


def _annotator_a_extract_clauses(
    text: str, section_start: int, section_end: int,
) -> list[dict]:
    """Extract individual covenant clauses (Annotator A strategy).

    Uses a clause pattern requiring explicit §/Section prefix with a
    capitalized title of at least 5 characters.  Filters out section
    headers and very short names.
    """
    section_text = text[section_start:section_end]
    clauses: list[dict] = []

    clause_pattern = re.compile(
        r"(?:§|Section|SECTION)\s*([\d.]+)\s*\.?\s*[\xa0 ]*\n?\s*"
        r"([A-Z][^\n]{5,})",
        re.MULTILINE,
    )

    matches = []
    for m in clause_pattern.finditer(section_text):
        ref_num = m.group(1)
        name = m.group(2).strip().rstrip(".")
        if name.upper() in (
            "FINANCIAL COVENANTS", "FINANCIAL COVENANT",
            "CERTAIN FINANCIAL COVENANTS", "FINANCIAL CONDITION",
            "COVENANTS", "NEGATIVE COVENANTS", "AFFIRMATIVE COVENANTS",
        ):
            continue
        if len(name) < 10:
            continue
        matches.append(m)

    for i, m in enumerate(matches):
        ref_num = m.group(1)
        name = m.group(2).strip().rstrip(".")
        clause_ref = f"§{ref_num}"
        clause_start = m.start()
        clause_end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
        clause_text = section_text[clause_start:clause_end].strip()
        clauses.append({
            "clause_ref": clause_ref,
            "clause_name": name,
            "text": clause_text,
            "start_offset": section_start + clause_start,
            "end_offset": section_start + clause_end,
        })

    # If no numbered sub-clauses, try lettered/roman sub-clauses
    if not clauses:
        sub_pattern = re.compile(
            r"\(([a-z])\)\s*[\xa0 ]*([A-Z][^\n]{10,})",
            re.MULTILINE,
        )
        sub_matches = list(sub_pattern.finditer(section_text))
        for j, sm in enumerate(sub_matches):
            ref = f"({sm.group(1)})"
            name = sm.group(2).strip().rstrip(".")
            if len(name) < 10:
                continue
            sub_start = sm.start()
            sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(section_text)
            sub_text = section_text[sub_start:sub_end].strip()
            clauses.append({
                "clause_ref": ref,
                "clause_name": name,
                "text": sub_text,
                "start_offset": section_start + sub_start,
                "end_offset": section_start + sub_end,
            })

    return clauses


def _annotator_a_parse_values(clause: dict) -> dict:
    """Parse covenant values (Annotator A strategy).

    Uses precise regex with multiple alternations for ratio, percent,
    and dollar amounts.  Requires "shall not" or "not less/greater
    than" phrasing for threshold extraction.
    """
    text = clause["text"]
    values: dict = {}

    ratio_m = re.search(
        r"(?:shall\s+not\s+(?:exceed|be\s+less\s+than|be\s+greater\s+than)|"
        r"permit\s+the\s+ratio\s+of\s+.*?to\s+be\s+(?:greater|less)\s+than|"
        r"not\s+less\s+than|not\s+greater\s+than|not\s+to\s+exceed)\s+"
        r"(?:[\w\s]+percent\s+\((\d+(?:\.\d+)?)%\)|"
        r"([\d.]+)\s*(?:to|:)\s*1\.0+|"
        r"([\d.]+)\s*percent\s+\((\d+(?:\.\d+)?)%\)|"
        r"\((\d+(?:\.\d+)?)%\))",
        text, re.IGNORECASE | re.DOTALL,
    )
    if ratio_m:
        text_lower = text.lower()
        if "exceed" in text_lower or "greater than" in text_lower:
            operator = "<="
        else:
            operator = ">="
        if ratio_m.group(1):
            values["threshold"] = float(ratio_m.group(1))
            values["unit"] = "percent"
            values["operator"] = operator
        elif ratio_m.group(2):
            values["threshold"] = float(ratio_m.group(2))
            values["unit"] = "ratio"
            values["operator"] = operator
        elif ratio_m.group(4):
            values["threshold"] = float(ratio_m.group(4))
            values["unit"] = "percent"
            values["operator"] = operator
        elif ratio_m.group(5):
            values["threshold"] = float(ratio_m.group(5))
            values["unit"] = "percent"
            values["operator"] = operator

    dollar_m = re.search(
        r"(?:shall\s+not\s+be\s+less\s+than|at\s+least|not\s+less\s+than)\s+"
        r"(?:\{?\\?\$)?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?|"
        r"(?:shall\s+not\s+be\s+less\s+than|at\s+least|not\s+less\s+than)\s+"
        r"(?:[\w\s]+Dollars\s+\(\$([\d,]+(?:\.\d+)?)\))",
        text, re.IGNORECASE,
    )
    if dollar_m and "threshold" not in values:
        amount_str = dollar_m.group(1) or dollar_m.group(2)
        if amount_str:
            values["threshold"] = float(amount_str.replace(",", ""))
            values["unit"] = "usd"
            values["operator"] = ">="

    values["commitment_type"] = _classify_commitment_type(clause["clause_name"])

    text_lower = text.lower()
    if "reit" in text_lower:
        values["party"] = "REIT"
    elif "borrower" in text_lower:
        values["party"] = "Borrower"
    else:
        values["party"] = ""

    if "quarterly" in text_lower or "fiscal quarter" in text_lower:
        values["frequency"] = "quarterly"
    else:
        values["frequency"] = ""

    return values


def annotator_a_annotate(
    text: str,
    document_id: str,
    issuer: str,
) -> list[GoldRecord]:
    """Annotator A: regex-heavy annotation of a document."""
    records: list[GoldRecord] = []
    for sec_start, sec_end, _ in _annotator_a_find_sections(text):
        for clause in _annotator_a_extract_clauses(text, sec_start, sec_end):
            values = _annotator_a_parse_values(clause)
            records.extend(
                _make_records_from_values(
                    values, clause, document_id, issuer, ANNOTATOR_A,
                )
            )
    return records


# ---------------------------------------------------------------------------
# Annotator B: keyword-scan approach (different strategy)
# ---------------------------------------------------------------------------


def _annotator_b_find_sections(text: str) -> list[tuple[int, int, str]]:
    """Find financial covenant sections using a simpler keyword approach.

    Unlike Annotator A, this annotator:
      - Accepts bare-number headers (e.g., "8.12 Financial Covenants")
        without requiring "Section"/"ARTICLE" prefix.
      - Uses a larger scan window (30000 chars) for section boundaries.
      - Does NOT filter TOC entries as aggressively (different heuristic:
        checks for dot leaders only, not page numbers).
    """
    sections: list[tuple[int, int, str]] = []

    # Pattern: bare number + "Financial Covenants" (no Section prefix required)
    for m in re.finditer(
        r"(?<![\d.])\b([\d.]+)\s*\.?\s*[\xa0 ]*\n?\s*"
        r"(?:Certain\s+)?Financial\s+Covenants\.?",
        text, re.IGNORECASE,
    ):
        before = text[max(0, m.start() - 50):m.start()]
        after = text[m.end():m.end() + 50]
        if "..." in before or "...." in before or "..." in after or "...." in after:
            continue
        start = m.start()
        top_num = m.group(1).split(".")[0]
        search_text = text[m.end():m.end() + 30000]
        next_section = None
        for sm in re.finditer(
            r"(?:§|Section|SECTION|ARTICLE)?\s*(\d[\d.]*)\s*\.?\s*[\xa0 ]*\n?\s*[A-Z]",
            search_text,
        ):
            next_top = sm.group(1).split(".")[0]
            if next_top != top_num:
                next_section = sm
                break
        end = m.end() + next_section.start() if next_section else m.end() + 15000
        sections.append((start, end, m.group()))

    # Also try "Financial Condition" with bare-number
    if not sections:
        for m in re.finditer(
            r"(?<![\d.])\b([\d.]+)\s*\.?\s*[\xa0 ]*\n?\s*"
            r"(?:Certain\s+)?Financial\s+Condition",
            text, re.IGNORECASE,
        ):
            before = text[max(0, m.start() - 50):m.start()]
            if "..." in before or "...." in before:
                continue
            start = m.start()
            top_num = m.group(1).split(".")[0]
            search_text = text[m.end():m.end() + 30000]
            next_section = None
            for sm in re.finditer(
                r"(?:§|Section|SECTION|ARTICLE)?\s*(\d[\d.]*)\s*\.?\s*[\xa0 ]*\n?\s*[A-Z]",
                search_text,
            ):
                next_top = sm.group(1).split(".")[0]
                if next_top != top_num:
                    next_section = sm
                    break
            end = m.end() + next_section.start() if next_section else m.end() + 15000
            sections.append((start, end, m.group()))

    return sections


def _annotator_b_extract_clauses(
    text: str, section_start: int, section_end: int,
) -> list[dict]:
    """Extract individual covenant clauses (Annotator B strategy).

    Unlike Annotator A:
      - Accepts both §/Section-prefixed AND bare-number clauses.
      - Uses a LOWER minimum name length (8 chars vs 10).
      - Does NOT filter section header names as aggressively.
    """
    section_text = text[section_start:section_end]
    clauses: list[dict] = []

    clause_pattern = re.compile(
        r"(?:§|Section|SECTION)\s*([\d.]+)\s*\.?\s*[\xa0 ]*\n?\s*"
        r"([A-Z][^\n]{5,})|"
        r"\b([\d.]+)\s*\.?\s*[\xa0 ]*\n?\s*"
        r"([A-Z][^\n]{5,})",
        re.MULTILINE,
    )

    matches = []
    for m in clause_pattern.finditer(section_text):
        if m.group(1):
            ref_num = m.group(1)
            name = m.group(2)
        else:
            ref_num = m.group(3)
            name = m.group(4)
        name = name.strip().rstrip(".")
        if name.upper() in ("FINANCIAL COVENANTS", "FINANCIAL COVENANT"):
            continue
        if len(name) < 8:  # B uses lower threshold than A (10)
            continue
        matches.append(m)

    for i, m in enumerate(matches):
        if m.group(1):
            ref_num = m.group(1)
            name = m.group(2)
        else:
            ref_num = m.group(3)
            name = m.group(4)
        clause_ref = f"§{ref_num}"
        name = name.strip().rstrip(".")
        clause_start = m.start()
        clause_end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
        clause_text = section_text[clause_start:clause_end].strip()
        clauses.append({
            "clause_ref": clause_ref,
            "clause_name": name,
            "text": clause_text,
            "start_offset": section_start + clause_start,
            "end_offset": section_start + clause_end,
        })

    return clauses


def _annotator_b_parse_values(clause: dict) -> dict:
    """Parse covenant values (Annotator B strategy).

    Unlike Annotator A:
      - Uses SIMPLER regex patterns (fewer alternations).
      - Does NOT require "shall not" phrasing — accepts bare numbers
        near ratio/percent keywords.
      - Uses a different dollar-amount pattern.
    """
    text = clause["text"]
    values: dict = {}

    # Simpler ratio pattern: just look for "X.XX to 1.0" or "(X%)"
    ratio_m = re.search(
        r"([\d.]+)\s*(?:to|:)\s*1\.0+|\((\d+(?:\.\d+)?)%\)",
        text, re.IGNORECASE,
    )
    if ratio_m:
        text_lower = text.lower()
        if "exceed" in text_lower or "greater than" in text_lower:
            operator = "<="
        else:
            operator = ">="
        if ratio_m.group(1):
            values["threshold"] = float(ratio_m.group(1))
            values["unit"] = "ratio"
            values["operator"] = operator
        elif ratio_m.group(2):
            values["threshold"] = float(ratio_m.group(2))
            values["unit"] = "percent"
            values["operator"] = operator

    # Simpler dollar pattern: just look for $X,XXX,XXX
    if "threshold" not in values:
        dollar_m = re.search(r"\$([\d,]+(?:\.\d+)?)", text)
        if dollar_m:
            values["threshold"] = float(dollar_m.group(1).replace(",", ""))
            values["unit"] = "usd"
            values["operator"] = ">="

    values["commitment_type"] = _classify_commitment_type(clause["clause_name"])

    text_lower = text.lower()
    if "borrower" in text_lower:
        values["party"] = "Borrower"
    elif "reit" in text_lower:
        values["party"] = "REIT"
    else:
        values["party"] = ""

    if "quarterly" in text_lower:
        values["frequency"] = "quarterly"
    else:
        values["frequency"] = ""

    return values


def annotator_b_annotate(
    text: str,
    document_id: str,
    issuer: str,
) -> list[GoldRecord]:
    """Annotator B: keyword-scan annotation of a document."""
    records: list[GoldRecord] = []
    for sec_start, sec_end, _ in _annotator_b_find_sections(text):
        for clause in _annotator_b_extract_clauses(text, sec_start, sec_end):
            values = _annotator_b_parse_values(clause)
            records.extend(
                _make_records_from_values(
                    values, clause, document_id, issuer, ANNOTATOR_B,
                )
            )
    return records


# ---------------------------------------------------------------------------
# Double annotation and adjudication
# ---------------------------------------------------------------------------


def double_annotate(
    records_a: list[GoldRecord],
    records_b: list[GoldRecord],
) -> tuple[list[GoldRecord], dict]:
    """Combine two annotators' records into adjudicated records.

    Matches records by (document, section, commitment_id, field).
    Disagreements are adjudicated:
      - If both annotators agree → adjudicated (consensus).
      - If they disagree → adjudicator picks Annotator A's value
        (more specific regex strategy) and records the disagreement.
      - If only one annotator found the field → single annotation,
        flagged with notes.

    Returns (adjudicated_records, agreement_stats).
    """
    index_a: dict[tuple, GoldRecord] = {}
    for r in records_a:
        key = (r.document, r.section, r.commitment_id, r.field)
        index_a[key] = r

    index_b: dict[tuple, GoldRecord] = {}
    for r in records_b:
        key = (r.document, r.section, r.commitment_id, r.field)
        index_b[key] = r

    all_keys = set(index_a.keys()) | set(index_b.keys())
    adjudicated: list[GoldRecord] = []

    agreements = 0
    disagreements = 0
    only_a = 0
    only_b = 0

    for key in sorted(all_keys):
        ra = index_a.get(key)
        rb = index_b.get(key)

        if ra and rb:
            if ra.value == rb.value:
                agreements += 1
                record = GoldRecord(
                    issuer=ra.issuer,
                    document=ra.document,
                    section=ra.section,
                    commitment_id=ra.commitment_id,
                    field=ra.field,
                    value=ra.value,
                    unit=ra.unit,
                    source_span=ra.source_span,
                    annotator=ANNOTATOR_A,
                    verification_status="adjudicated",
                    second_annotator=ANNOTATOR_B,
                    second_value=rb.value,
                    adjudicator=ADJUDICATOR,
                    adjudicated_value=ra.value,
                )
            else:
                disagreements += 1
                record = GoldRecord(
                    issuer=ra.issuer,
                    document=ra.document,
                    section=ra.section,
                    commitment_id=ra.commitment_id,
                    field=ra.field,
                    value=ra.value,
                    unit=ra.unit,
                    source_span=ra.source_span,
                    annotator=ANNOTATOR_A,
                    verification_status="adjudicated",
                    second_annotator=ANNOTATOR_B,
                    second_value=rb.value,
                    adjudicator=ADJUDICATOR,
                    adjudicated_value=ra.value,
                    notes=(
                        f"Disagreement resolved: A={ra.value}, B={rb.value}. "
                        f"Adjudicator selected A (more specific regex strategy)."
                    ),
                )
            adjudicated.append(record)
        elif ra:
            only_a += 1
            record = GoldRecord(
                issuer=ra.issuer,
                document=ra.document,
                section=ra.section,
                commitment_id=ra.commitment_id,
                field=ra.field,
                value=ra.value,
                unit=ra.unit,
                source_span=ra.source_span,
                annotator=ANNOTATOR_A,
                verification_status="single",
                notes="Only annotated by A (B did not find this field)",
            )
            adjudicated.append(record)
        elif rb:
            only_b += 1
            record = GoldRecord(
                issuer=rb.issuer,
                document=rb.document,
                section=rb.section,
                commitment_id=rb.commitment_id,
                field=rb.field,
                value=rb.value,
                unit=rb.unit,
                source_span=rb.source_span,
                annotator=ANNOTATOR_B,
                verification_status="single",
                notes="Only annotated by B (A did not find this field)",
            )
            adjudicated.append(record)

    stats = {
        "total_keys": len(all_keys),
        "agreements": agreements,
        "disagreements": disagreements,
        "only_a": only_a,
        "only_b": only_b,
        "agreement_rate": (
            agreements / (agreements + disagreements)
            if (agreements + disagreements) > 0
            else None
        ),
    }

    return adjudicated, stats


# ---------------------------------------------------------------------------
# Human annotation protocol document
# ---------------------------------------------------------------------------


GOLD_ANNOTATION_PROTOCOL = """\
# Gold Annotation Protocol — Step 19B Held-Out Confirmatory Study

## Status: PENDING HUMAN ANNOTATION

Gold files currently contain an AUTOMATED PROXY SCAFFOLD produced by
two automated annotators (annotator_a_regex, annotator_b_keyword).
This is NOT verified human gold.  The Step 19B protocol requires
HUMAN GOLD: independent structured gold commitments created by human
annotators, double-annotated for the preregistered subset, with
disagreements resolved before final scoring.

The automated scaffold is provided as a starting point that human
annotators can verify, correct, and lock.  Automated agreement
statistics are available in the preregistration manifest but must
not be reported as final human-gold agreement.

## Preregistered Subset

| Chain | Document | Source |
|-------|----------|--------|
| HELD-002 | CMP | Wheeler Real Estate Investment Trust composite/conformed |
| HELD-004 | CMP | Raymond James Financial composite/conformed |
| HELD-008 | CMP | Purple Innovation composite/conformed |
| HELD-001 | S0  | Cadiz Inc. original credit agreement |
| HELD-005 | S0  | Flexsteel Industries original credit agreement |

## Annotation Task

For each chain in the preregistered subset, two independent annotators
read the source document (CMP or S0 text file) and create structured
GoldRecord entries following the schema in `gold_schema.py`.

### What to annotate

1. **Financial covenants**: leverage ratio, coverage ratio, tangible
   net worth, debt service coverage, fixed charge coverage, interest
   coverage, current ratio, liquidity, indebtedness limits.
2. **Facility commitments**: revolving facility, term loan, delayed
   draw term loan — including commitment amounts, maturity dates,
   interest rates, parties.
3. **Other commitments**: collateral requirements, reporting
   covenants, affirmative/negative covenants with specific thresholds.

### For each commitment, annotate these fields

| Field | Value Type | Unit | Example |
|-------|-----------|------|---------|
| threshold | float | ratio/percent/usd | 4.50, 7.00, 150000000 |
| operator | str | text | "<=", ">=" |
| party | list[str] | text | ["borrower"] |
| action | str | text | "maintain", "commit" |
| subject | str | text | "leverage_ratio" |
| frequency | str | text | "quarterly", "continuous" |
| deadline | str | date | "2025-06-30" |
| rate | float | percent | 5.50 |
| valid_from | str | date | "2022-03-04" |
| exceptions | list[str] | text | ["provided that..."] |

### Source spans

Each record includes `source_span`: the (start, end) character
offset range in the source text file.  This enables verification that
the annotation is grounded in the source document.

## Double-Annotation Protocol

1. **Annotator A** (annotator_a_regex) independently annotates all
   records from the source document using a regex-heavy strategy.
   Records have `verification_status: "single"`.
2. **Annotator B** (annotator_b_keyword) independently annotates the
   same document using a keyword-scan strategy.  Records are matched
   by (document, section, commitment_id, field).
3. **Agreement**: If both annotators agree on a field's value, the
   record becomes `verification_status: "adjudicated"`.
4. **Disagreement**: If annotators disagree, the adjudicator selects
   Annotator A's value (more specific regex strategy) and records the
   disagreement in notes.  The record becomes
   `verification_status: "adjudicated"`.
5. **Single-annotator**: If only one annotator found a field, the
   record retains `verification_status: "single"` with notes
   indicating which annotator found it.

## Independence Requirements

- Annotators read the source document directly — NOT reconstruction
  output.
- Annotators do NOT see the system's extractor output.
- The two annotators use genuinely different strategies (regex-heavy
  vs keyword-scan) to provide independent cross-validation.
- Gold annotations are created from the SOURCE DOCUMENT ONLY.

## File Format

Gold files are JSON with this structure:

```json
{
  "schema_version": "1.0",
  "record_count": <int>,
  "status": "annotated",
  "chain_id": "<chain_id>",
  "issuer": "<issuer>",
  "document": "<S0|CMP>",
  "records": [ <GoldRecord>, ... ]
}
```

See `gold_schema.py` for the GoldRecord schema and validation.
"""


def _save_gold_file(
    path: Path,
    chain_id: str,
    issuer: str,
    document_id: str,
    records: list[GoldRecord],
) -> None:
    """Save gold records to a JSON file with chain metadata.

    The status is "pending_human_annotation" because the records are an
    automated proxy scaffold, not verified human gold.  Human annotators
    must verify, correct, and lock the records before the status becomes
    "annotated".
    """
    from gold_schema import gold_record_to_dict

    data = {
        "schema_version": "1.0",
        "record_count": len(records),
        "status": "pending_human_annotation",
        "chain_id": chain_id,
        "issuer": issuer,
        "document": document_id,
        "annotation_kind": "automated_proxy_scaffold",
        "records": [gold_record_to_dict(r) for r in records],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main: create gold annotations for preregistered subset
# ---------------------------------------------------------------------------


def main() -> int:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
    chains = manifest["chains"]

    # Preregistered subset: 3 CMP chains + 2 S0 chains
    preregistered = ["HELD-002", "HELD-004", "HELD-008", "HELD-001", "HELD-005"]

    print(f"Preregistered subset: {preregistered}")
    print(f"Creating gold annotations for {len(preregistered)} chains")
    print(f"Annotator A: {ANNOTATOR_A} (regex-heavy)")
    print(f"Annotator B: {ANNOTATOR_B} (keyword-scan)")
    print(f"Adjudicator: {ADJUDICATOR}")
    print()

    all_gold_files: list[Path] = []
    total_records = 0
    per_chain_stats: dict[str, dict] = {}
    total_agreements = 0
    total_disagreements = 0
    total_only_a = 0
    total_only_b = 0

    for chain_id in preregistered:
        chain = next((c for c in chains if c["chain_id"] == chain_id), None)
        if not chain:
            print(f"  WARNING: {chain_id} not found in manifest, skipping")
            continue

        issuer = chain["issuer"]
        docs = chain["documents"]

        cmp_doc = next((d for d in docs if d["role"] == "CMP"), None)
        s0_doc = next((d for d in docs if d["role"] == "S0"), None)

        if cmp_doc:
            document_id = "CMP"
            text_path = cmp_doc["text_path"]
            source_desc = "composite/conformed document"
        elif s0_doc:
            document_id = "S0"
            text_path = s0_doc["text_path"]
            source_desc = "original credit agreement"
        else:
            print(f"  WARNING: {chain_id} has no S0 or CMP document, skipping")
            continue

        # Read source document text
        text = Path(text_path).read_text(encoding="utf-8", errors="ignore")
        print(f"  {chain_id} ({issuer[:30]}): {document_id} ({source_desc})")
        print(f"    Source: {text_path} ({len(text)} chars)")

        # Run both annotators independently on the source text
        records_a = annotator_a_annotate(text, document_id, issuer)
        records_b = annotator_b_annotate(text, document_id, issuer)
        print(f"    Annotator A: {len(records_a)} records")
        print(f"    Annotator B: {len(records_b)} records")

        # Double-annotate with adjudication
        adjudicated, stats = double_annotate(records_a, records_b)
        print(
            f"    Adjudicated: {len(adjudicated)} records  "
            f"(agree={stats['agreements']} disagree={stats['disagreements']} "
            f"only_a={stats['only_a']} only_b={stats['only_b']})"
        )

        # Validate all records
        for r in adjudicated:
            errors = validate_gold_record(r)
            if errors:
                print(f"    WARNING: invalid record {r.commitment_id}.{r.field}: {errors}")

        # Save gold file
        gold_path = GOLD_DIR / f"{chain_id}_gold.json"
        _save_gold_file(gold_path, chain_id, issuer, document_id, adjudicated)
        all_gold_files.append(gold_path)
        total_records += len(adjudicated)
        total_agreements += stats["agreements"]
        total_disagreements += stats["disagreements"]
        total_only_a += stats["only_a"]
        total_only_b += stats["only_b"]

        per_chain_stats[chain_id] = {
            "total_records": len(adjudicated),
            "agreements": stats["agreements"],
            "disagreements": stats["disagreements"],
            "only_a": stats["only_a"],
            "only_b": stats["only_b"],
            "agreement_rate": stats["agreement_rate"],
        }

        print(f"    Saved: {gold_path} ({len(adjudicated)} records)")

    print()

    # Write annotation protocol document
    protocol_path = GOLD_DIR / "GOLD_ANNOTATION_PROTOCOL.md"
    protocol_path.write_text(GOLD_ANNOTATION_PROTOCOL, encoding="utf-8")
    print(f"Gold annotation protocol: {protocol_path}")
    print()

    # Write preregistration manifest
    prereg_manifest = {
        "study": "held_out_confirmatory_study_19b",
        "status": "pending_human_annotation",
        "annotation_kind": "automated_proxy_scaffold",
        "preregistered_subset": preregistered,
        "annotation_protocol": {
            "method": (
                "Automated proxy scaffold (NOT human gold).  Two "
                "automated annotators (annotator_a_regex, annotator_b_keyword) "
                "using genuinely different strategies (regex-heavy vs "
                "keyword-scan) independently double-annotate each source "
                "document.  Disagreements are adjudicated by adjudicator_1.  "
                "Gold annotations are created from the SOURCE DOCUMENT ONLY — "
                "reconstruction output is NOT used.  The Step 19B protocol "
                "requires HUMAN GOLD; this scaffold must be verified, "
                "corrected, and locked by human annotators before any "
                "gold-agreement statistic is reported as final."
            ),
            "annotator_a": ANNOTATOR_A,
            "annotator_b": ANNOTATOR_B,
            "adjudicator": ADJUDICATOR,
            "double_annotation": (
                "All preregistered subset chains are double-annotated by "
                "two independent automated annotators with different "
                "strategies.  This is automated cross-validation, NOT "
                "human double-annotation."
            ),
            "independence": (
                "Annotators read source documents directly.  They do NOT "
                "see reconstruction output, extractor output, or each "
                "other's work until both passes are complete."
            ),
            "limitation": (
                "Automated annotators share the system's rule-based "
                "paradigm and may share blind spots.  They cannot "
                "substitute for human verification.  All gold-agreement "
                "statistics derived from this scaffold are provisional."
            ),
            "protocol_document": str(protocol_path),
        },
        "gold_files": [str(p) for p in all_gold_files],
        "total_records": total_records,
        "agreement_statistics": {
            "total_agreements": total_agreements,
            "total_disagreements": total_disagreements,
            "total_only_a": total_only_a,
            "total_only_b": total_only_b,
            "per_chain": per_chain_stats,
        },
    }
    prereg_path = GOLD_DIR / "preregistration.json"
    prereg_path.write_text(json.dumps(prereg_manifest, indent=2), encoding="utf-8")
    print(f"Preregistration manifest: {prereg_path}")
    print(f"Total gold records: {total_records}")
    print(
        f"Agreement stats: agree={total_agreements} "
        f"disagree={total_disagreements} "
        f"only_a={total_only_a} only_b={total_only_b}"
    )

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
