"""Independent human-verifiable gold schemas for S0 and GT commitments.

Defines the structured schema for human-annotated gold records. Each gold
record represents a single commitment field-value pair extracted by a
human annotator from the source document, independent of the automated
extractor.

This schema is used to:
  1. Measure extractor quality (precision/recall against gold)
  2. Provide independent ground truth for the held-out study
  3. Enable double-annotation for the preregistered subset

Schema fields:
    issuer              — issuer name
    document            — document identifier (e.g., "S0", "CMP", "A1")
    section             — section reference (e.g., "Section 6.07(a)")
    commitment_id       — canonical commitment key
    field               — field name (threshold, party, deadline, etc.)
    value               — field value (typed)
    unit                — unit (ratio, percent, usd, date, etc.)
    effective_at        — effective date (ISO 8601)
    source_span         — character offset range in source text
    annotator           — annotator identifier
    verification_status — single / double_annotated / adjudicated / locked

Usage:
    # Validate a gold record
    from gold_schema import GoldRecord, validate_gold_record
    record = GoldRecord(...)
    errors = validate_gold_record(record)
    if errors:
        raise ValueError(f"Invalid gold record: {errors}")

    # Load a gold file
    from gold_schema import load_gold_file
    records = load_gold_file("gold/STUDY-015_S0_gold.json")
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Verification status
# ---------------------------------------------------------------------------

VERIFICATION_STATUSES = {
    "single": "Annotated by one annotator. Not yet verified.",
    "double_annotated": "Annotated by two independent annotators. "
                        "Disagreements flagged but not yet adjudicated.",
    "adjudicated": "Disagreements resolved by a third annotator or "
                   "discussion. Ready for locking.",
    "locked": "Final gold state. No further changes without explicit "
              "protocol amendment.",
}


# ---------------------------------------------------------------------------
# Gold record schema
# ---------------------------------------------------------------------------


@dataclass
class GoldRecord:
    """A single human-annotated commitment field-value pair.

    Each record represents ONE field of ONE commitment. A commitment with
    5 fields (threshold, party, operator, unit, frequency) produces 5
    gold records. This granularity enables field-level precision/recall
    measurement, not just commitment-level.
    """

    # --- Required fields ---
    issuer: str                        # issuer name (e.g., "Ameresco, Inc.")
    document: str                      # document id (e.g., "S0", "CMP")
    section: str                       # section ref (e.g., "Section 6.07(a)")
    commitment_id: str                 # canonical key (e.g., "financial_covenant.leverage_ratio")
    field: str                         # field name (e.g., "threshold", "party")
    value: Any                         # field value (typed: float, str, list, etc.)
    unit: str                          # unit (e.g., "ratio", "percent", "usd", "date")
    source_span: tuple[int, int]       # (start, end) character offsets in source text
    annotator: str                     # annotator identifier

    # --- Verification ---
    verification_status: str = "single"  # single / double_annotated / adjudicated / locked

    # --- Optional fields ---
    effective_at: str | None = None    # ISO 8601 date (YYYY-MM-DD)
    notes: str = ""                    # annotator notes
    second_annotator: str = ""         # second annotator identifier (if double-annotated)
    second_value: Any = None           # second annotator's value (if different)
    adjudicator: str = ""              # adjudicator identifier (if adjudicated)
    adjudicated_value: Any = None      # final adjudicated value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_gold_record(record: GoldRecord) -> list[str]:
    """Validate a gold record. Returns a list of error messages (empty if valid)."""
    errors: list[str] = []

    if not record.issuer:
        errors.append("issuer is required")
    if not record.document:
        errors.append("document is required")
    if not record.section:
        errors.append("section is required")
    if not record.commitment_id:
        errors.append("commitment_id is required")
    if not record.field:
        errors.append("field is required")
    if record.value is None:
        errors.append("value is required (use empty string/list for empty values)")
    if not record.unit:
        errors.append("unit is required")
    if not record.annotator:
        errors.append("annotator is required")

    if record.verification_status not in VERIFICATION_STATUSES:
        errors.append(f"verification_status must be one of: {list(VERIFICATION_STATUSES)}")

    if record.verification_status == "double_annotated" and not record.second_annotator:
        errors.append("second_annotator required for double_annotated status")
    if record.verification_status == "adjudicated" and not record.adjudicator:
        errors.append("adjudicator required for adjudicated status")

    if not isinstance(record.source_span, (tuple, list)) or len(record.source_span) != 2:
        errors.append("source_span must be a (start, end) tuple")
    elif record.source_span[0] < 0 or record.source_span[1] < record.source_span[0]:
        errors.append("source_span must have 0 <= start < end")

    return errors


# ---------------------------------------------------------------------------
# Gold file format
# ---------------------------------------------------------------------------


def gold_record_to_dict(record: GoldRecord) -> dict:
    """Convert a GoldRecord to a JSON-serializable dict."""
    d = {
        "issuer": record.issuer,
        "document": record.document,
        "section": record.section,
        "commitment_id": record.commitment_id,
        "field": record.field,
        "value": record.value,
        "unit": record.unit,
        "source_span": list(record.source_span),
        "annotator": record.annotator,
        "verification_status": record.verification_status,
    }
    if record.effective_at is not None:
        d["effective_at"] = record.effective_at
    if record.notes:
        d["notes"] = record.notes
    if record.second_annotator:
        d["second_annotator"] = record.second_annotator
        d["second_value"] = record.second_value
    if record.adjudicator:
        d["adjudicator"] = record.adjudicator
        d["adjudicated_value"] = record.adjudicated_value
    return d


def dict_to_gold_record(d: dict) -> GoldRecord:
    """Convert a dict to a GoldRecord."""
    return GoldRecord(
        issuer=d["issuer"],
        document=d["document"],
        section=d["section"],
        commitment_id=d["commitment_id"],
        field=d["field"],
        value=d["value"],
        unit=d["unit"],
        source_span=tuple(d["source_span"]),
        annotator=d["annotator"],
        verification_status=d.get("verification_status", "single"),
        effective_at=d.get("effective_at"),
        notes=d.get("notes", ""),
        second_annotator=d.get("second_annotator", ""),
        second_value=d.get("second_value"),
        adjudicator=d.get("adjudicator", ""),
        adjudicated_value=d.get("adjudicated_value"),
    )


def save_gold_file(path: str | Path, records: list[GoldRecord]) -> None:
    """Save gold records to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": "1.0",
        "record_count": len(records),
        "records": [gold_record_to_dict(r) for r in records],
    }
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_gold_file(path: str | Path) -> list[GoldRecord]:
    """Load gold records from a JSON file."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return [dict_to_gold_record(d) for d in data["records"]]


# ---------------------------------------------------------------------------
# Schema documentation (for annotators)
# ---------------------------------------------------------------------------


SCHEMA_DOCUMENTATION = """\
# Gold Record Schema v1.0

## Purpose

Each gold record represents a single commitment field-value pair,
annotated by a human from the source document. This is the independent
ground truth used to measure extractor quality and to validate
reconstruction accuracy.

## Schema Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| issuer | str | yes | Issuer name (e.g., "Ameresco, Inc.") |
| document | str | yes | Document identifier: "S0" (origin), "CMP" (composite), "A1" (amendment 1) |
| section | str | yes | Section reference in the source document (e.g., "Section 6.07(a)") |
| commitment_id | str | yes | Canonical commitment key (e.g., "financial_covenant.leverage_ratio") |
| field | str | yes | Field name: threshold, party, operator, unit, frequency, deadline, rate, valid_from, exceptions, action, subject |
| value | any | yes | Field value (typed: float for thresholds, str for dates, list for parties/exceptions) |
| unit | str | yes | Unit: ratio, percent, usd, date, text, count |
| source_span | [int, int] | yes | Character offset range [start, end] in the source text file |
| annotator | str | yes | Annotator identifier (e.g., "annotator_a") |
| verification_status | str | yes | One of: single, double_annotated, adjudicated, locked |
| effective_at | str | no | Effective date (ISO 8601: YYYY-MM-DD) |
| notes | str | no | Annotator notes |
| second_annotator | str | no | Second annotator identifier (for double_annotated) |
| second_value | any | no | Second annotator's value (if different from first) |
| adjudicator | str | no | Adjudicator identifier (for adjudicated) |
| adjudicated_value | any | no | Final adjudicated value |

## Verification Workflow

1. **single**: One annotator creates the record.
2. **double_annotated**: A second independent annotator annotates the
   same field. If values agree, status becomes double_annotated. If
   they disagree, both values are kept and the record is flagged.
3. **adjudicated**: A third annotator (or discussion) resolves
   disagreements. The adjudicated_value is the final value.
4. **locked**: The gold state is final. No further changes without
   explicit protocol amendment.

## Commitment ID Convention

Commitment IDs follow the existing canonical_key convention.  This is
the complete list of classes the system's S0/GT extractors can produce;
all of them are in scope for human annotation:

  - facility.revolving_facility
  - facility.term_loan
  - facility.delayed_draw_term_loan
  - financial_covenant.leverage_ratio
  - financial_covenant.debt_service_coverage
  - financial_covenant.fixed_charge_coverage
  - financial_covenant.interest_coverage
  - financial_covenant.current_ratio
  - financial_covenant.tangible_net_worth
  - financial_covenant.tier_1_leverage_ratio
  - financial_covenant.risk_based_capital_ratio
  - financial_covenant.texas_ratio
  - financial_covenant.return_on_average_assets

This list MUST stay in sync with:
  - commitment_extractor._COVENANT_NAME_MAP (financial_covenant.*)
  - commitment_extractor._FACILITY_PATTERNS (facility.*)
  - prepare_human_gold_handoff.py SYSTEM_EXTRACTION_SCOPE

## Field Names

| Field | Value Type | Unit | Example |
|-------|-----------|------|---------|
| threshold | float | ratio / percent / usd | 4.50 (ratio), 7.00 (percent), 150000000 (usd) |
| operator | str | text | "<=", ">=" |
| party | list[str] | text | ["borrower"], ["loan_parties"] |
| action | str | text | "maintain", "commit" |
| subject | str | text | "leverage_ratio", "term_loan" |
| frequency | str | text | "quarterly", "continuous", "annually" |
| deadline | str | date | "2025-06-30" |
| rate | float | percent | 5.50 |
| valid_from | str | date | "2022-03-04" |
| exceptions | list[str] | text | ["provided that..."] |
| applicability | dict | text | {"step_down_schedule": [...]} |

## File Naming Convention

Gold files are named: `{chain_id}_{document}_gold.json`

Examples:
  - gold/STUDY-015_S0_gold.json
  - gold/STUDY-015_CMP_gold.json
  - gold/EDGAR-AMERESCO_S0_gold.json

## Preregistered Subset

For the held-out study, at least 20% of gold records must be
double-annotated independently. The preregistered subset is selected
BEFORE annotation begins and covers:
  - All financial covenant thresholds (highest-impact fields)
  - All facility commitment amounts
  - All maturity/deadline dates
  - A random sample of 10% of remaining fields
"""


def write_schema_documentation(path: str | Path) -> None:
    """Write the schema documentation to a file."""
    Path(path).write_text(SCHEMA_DOCUMENTATION, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Write schema documentation
    doc_path = Path("results/gold_schema_documentation.md")
    write_schema_documentation(doc_path)
    print(f"Gold schema documentation: {doc_path}")

    # Write schema as JSON
    schema = {
        "schema_version": "1.0",
        "verification_statuses": VERIFICATION_STATUSES,
        "required_fields": [
            "issuer", "document", "section", "commitment_id",
            "field", "value", "unit", "source_span", "annotator",
            "verification_status",
        ],
        "optional_fields": [
            "effective_at", "notes", "second_annotator",
            "second_value", "adjudicator", "adjudicated_value",
        ],
        "commitment_ids": [
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
        ],
        "field_names": [
            "threshold", "operator", "party", "action", "subject",
            "frequency", "deadline", "rate", "valid_from",
            "exceptions", "applicability",
        ],
        "units": ["ratio", "percent", "usd", "date", "text", "count"],
    }
    schema_path = Path("results/gold_schema.json")
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Gold schema JSON: {schema_path}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
