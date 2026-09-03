"""Step 19B.3: Prepare the complete human annotation handoff package.

Generates a self-contained annotation package for the 5 preregistered
held-out chains.  The package is placed in data/held_out/human_gold_handoff/
and contains everything human annotators need to create verified gold
WITHOUT seeing frozen predictions, reconstruction output, or proxy gold.

For each chain, the package provides:
  - exact source document (text file, copied)
  - accession number and filing metadata
  - relevant commitment scope (classes + fields)
  - annotation template (empty JSON with schema)
  - source-span requirements
  - allowed commitment classes/fields
  - annotator instructions
  - blinded workflow (no system output exposed)
  - disagreement/adjudication workflow

Human annotators must NOT see:
  - frozen predictions (results/held_out_study_results.json)
  - reconstruction outputs (semantic pipeline results)
  - automated proxy annotations (data/held_out/gold/*_gold.json)

Usage:
    python prepare_human_gold_handoff.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

HELD_OUT_MANIFEST = Path("data/held_out/manifest.json")
HANDOFF_DIR = Path("data/held_out/human_gold_handoff")

PREREGISTERED = ["HELD-002", "HELD-004", "HELD-008", "HELD-001", "HELD-005"]

# Commitment classes the system's S0/GT extractors produce.
# Human annotators MUST annotate these classes so gold and system
# output share the same evaluable commitment scope.
#
# This list MUST stay in sync with the canonical commitment IDs the
# extractors actually emit:
#   - commitment_extractor._COVENANT_NAME_MAP (financial_covenant.*)
#   - commitment_extractor._FACILITY_PATTERNS (facility.*)
#   - gold_schema.py "Commitment ID Convention" block
# If the extractor learns a new class, add it here AND in the
# ANNOTATOR_INSTRUCTIONS "Required commitment scope" + "Commitment ID
# convention" blocks below.
SYSTEM_EXTRACTION_SCOPE = [
    # Facility commitments (commitment_extractor._FACILITY_PATTERNS)
    "facility.revolving_facility",
    "facility.term_loan",
    "facility.delayed_draw_term_loan",
    # Financial covenants (commitment_extractor._COVENANT_NAME_MAP)
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
]

# Additional commitment classes that are valid credit-agreement
# commitments but outside the system's extraction scope.  Annotators
# MAY annotate these for completeness, but they will be classified
# GOLD_NOT_IN_SCOPE and not scored as reconstruction errors.
#
# NOTE: every class the extractor produces MUST appear in
# SYSTEM_EXTRACTION_SCOPE above, never here.  Misclassifying an
# extractor-produced class as optional would tell annotators to skip
# it, perpetuating the scope mismatch the human gold is meant to fix.
OPTIONAL_SCOPE = [
    "financial_covenant.coverage_ratio",
    "financial_covenant.collateral_requirement",
    "financial_covenant.indebtedness_limit",
    "financial_covenant.liquidity",
]

# Fields annotators must capture for each commitment
ANNOTATION_FIELDS = [
    "threshold",
    "operator",
    "unit",
    "party",
    "action",
    "subject",
    "frequency",
    "deadline",
    "rate",
    "valid_from",
    "exceptions",
    "applicability",
    "commitment_type",
]

# ---------------------------------------------------------------------------
# Annotation instructions
# ---------------------------------------------------------------------------

ANNOTATOR_INSTRUCTIONS = """\
# Human Gold Annotation Instructions — Step 19B.3

## Overview

You are annotating financial commitments from credit agreement documents
filed on SEC EDGAR.  Your annotations will serve as independent ground
truth for evaluating a frozen automated system's reconstruction accuracy.

This is a BLINDED annotation task.  You must NOT view:
  - The automated system's predictions or extraction output
  - Reconstruction outputs from any pipeline
  - Pre-existing automated proxy annotations
  - Any other annotator's work until both passes are complete

## What you are annotating

For each source document (an original credit agreement or a
composite/conformed restated copy), you will identify and annotate:

1. **Financial covenants** — leverage ratios, coverage ratios, tangible
   net worth requirements, interest coverage, fixed charge coverage,
   current ratio, liquidity requirements, indebtedness limits, etc.
2. **Facility commitments** — revolving credit facilities, term loans,
   delayed draw term loans — including commitment amounts, maturity
   dates, interest rates, parties.
3. **Other commitments** — collateral requirements, reporting
   covenants, affirmative/negative covenants with specific thresholds.

## For each commitment, annotate these fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| threshold | float | if applicable | Numeric threshold (e.g., 4.50 for a 4.50:1 leverage ratio) |
| operator | str | if threshold | Comparison operator: "<=", ">=", "<", ">", "=" |
| unit | str | yes | "ratio", "percent", "usd", "date", "text", "count" |
| party | list[str] | if applicable | Obligated parties: ["borrower"], ["guarantor"] |
| action | str | if applicable | "maintain", "commit", "not_exceed" |
| subject | str | if applicable | What the commitment applies to: "leverage_ratio" |
| frequency | str | if applicable | "quarterly", "continuous", "annually", "fiscal_quarter" |
| deadline | str | if applicable | Maturity or deadline date (YYYY-MM-DD) |
| rate | float | if applicable | Interest rate or margin (e.g., 5.50 for 5.50%) |
| valid_from | str | if applicable | Effective date (YYYY-MM-DD) |
| exceptions | list[str] | if applicable | Exception clauses: ["provided that...", "except for..."] |
| applicability | dict | if applicable | Step-down schedules, tiered thresholds, conditional terms |
| commitment_type | str | yes | Category: "leverage_ratio", "coverage_ratio", "tangible_net_worth", etc. |

## Source spans (CRITICAL)

Each record MUST include `source_span`: the [start, end] character
offset range in the source text file that supports the annotation.

To find character offsets:
  - Open the .txt file in a text editor that shows character positions
  - Or use Python: `text = open("file.txt").read(); text.find("your snippet")`
  - The span should cover the clause or sentence that establishes the
    commitment (not just the threshold value)

Source spans enable verification that annotations are grounded in the
source document.  Records without valid source spans will be rejected.

## Commitment ID convention

Use the canonical_key format (this is the complete list of classes the
system's extractors can produce; all of them are in scope):

  - `facility.revolving_facility`
  - `facility.term_loan`
  - `facility.delayed_draw_term_loan`
  - `financial_covenant.leverage_ratio`
  - `financial_covenant.debt_service_coverage`
  - `financial_covenant.fixed_charge_coverage`
  - `financial_covenant.interest_coverage`
  - `financial_covenant.current_ratio`
  - `financial_covenant.tangible_net_worth`
  - `financial_covenant.tier_1_leverage_ratio`
  - `financial_covenant.risk_based_capital_ratio`
  - `financial_covenant.texas_ratio`
  - `financial_covenant.return_on_average_assets`

If a commitment does not fit any of these, use:
  - `financial_covenant.other` (with commitment_type describing it)
  - `facility.other` (with commitment_type describing it)

## Required commitment scope

The system being evaluated extracts these commitment classes.  You MUST
annotate all instances of these classes in each document:

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

You MAY also annotate other commitment classes for completeness.  These
will be recorded but classified as GOLD_NOT_IN_SCOPE for scoring.

## Annotation file format

Create one JSON file per document using the provided template.  The file
name must be: `{chain_id}_{annotator_id}_gold.json`

Example: `HELD-001_annotator_primary_gold.json`

Each file must follow this structure:

```json
{
  "schema_version": "1.0",
  "chain_id": "HELD-001",
  "issuer": "CADIZ INC",
  "document": "S0",
  "annotator": "annotator_primary",
  "annotation_date": "2026-09-15",
  "verification_status": "single",
  "record_count": 0,
  "records": [
    {
      "issuer": "CADIZ INC",
      "document": "S0",
      "section": "Section 6.07(a)",
      "commitment_id": "financial_covenant.leverage_ratio",
      "field": "threshold",
      "value": 4.50,
      "unit": "ratio",
      "source_span": [12345, 12789],
      "annotator": "annotator_primary",
      "verification_status": "single",
      "notes": "Maximum leverage ratio as of end of each fiscal quarter"
    }
  ]
}
```

## Double-annotation workflow

1. **Primary annotator** creates gold records for all 5 chains.
   - Files: `{chain_id}_annotator_primary_gold.json`
   - verification_status: "single"

2. **Independent second annotator** creates gold records for the same
   5 chains WITHOUT seeing the primary annotator's work.
   - Files: `{chain_id}_annotator_secondary_gold.json`
   - verification_status: "single"

3. **Adjudication**: A third reviewer compares the two annotation sets.
   - Records where both annotators agree → verification_status: "adjudicated"
   - Records where annotators disagree → adjudicator selects the
     correct value, records both values in notes, sets
     verification_status: "adjudicated"
   - Records from only one annotator → verification_status: "single"
     with notes indicating which annotator found it

4. **Locking**: The final adjudicated gold dataset is locked and hashed.
   - verification_status: "locked"
   - A SHA-256 hash of the locked gold dataset is recorded.

## Inter-annotator agreement

After both annotators complete their work, inter-annotator agreement is
calculated as:
  - Agreement rate = agreements / (agreements + disagreements)
  - Only fields found by BOTH annotators are counted in the denominator
  - Fields found by only one annotator are recorded separately

## Quality criteria

- Every record must have a valid source_span grounded in the source text
- Every record must have a commitment_id from the allowed list
- Every record must have the correct unit for its field type
- Thresholds must be numeric (float)
- Dates must be ISO 8601 (YYYY-MM-DD)
- Parties and exceptions must be lists

## Time estimate

Each document is a full credit agreement or composite/restated copy
(ranging from ~42K to ~552K characters).  Expected annotation time:
  - Small documents (~42K chars): 1-2 hours
  - Medium documents (~430-494K chars): 4-8 hours
  - Large documents (~552K chars): 6-10 hours

Total estimated time for 5 documents: 20-40 hours per annotator.
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_annotation_template(chain_id: str, issuer: str, document_id: str) -> dict:
    """Create an empty annotation template for a chain."""
    return {
        "schema_version": "1.0",
        "chain_id": chain_id,
        "issuer": issuer,
        "document": document_id,
        "annotator": "ANNOTATOR_ID_HERE",
        "annotation_date": "YYYY-MM-DD",
        "verification_status": "single",
        "record_count": 0,
        "records": [],
        "_instructions": (
            "Replace ANNOTATOR_ID_HERE with your annotator ID. "
            "Add one record per commitment field.  See "
            "ANNOTATOR_INSTRUCTIONS.md for full instructions."
        ),
    }


def main() -> int:
    print("Step 19B.3: Preparing human gold annotation handoff package")
    print("=" * 60)

    manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
    chains_by_id = {c["chain_id"]: c for c in manifest["chains"]}

    # Clean and create handoff directory
    if HANDOFF_DIR.exists():
        shutil.rmtree(HANDOFF_DIR)
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Write annotator instructions
    instructions_path = HANDOFF_DIR / "ANNOTATOR_INSTRUCTIONS.md"
    instructions_path.write_text(ANNOTATOR_INSTRUCTIONS, encoding="utf-8")
    print(f"  Annotator instructions: {instructions_path}")

    # 2. Write commitment scope reference
    scope = {
        "required_commitment_classes": SYSTEM_EXTRACTION_SCOPE,
        "optional_commitment_classes": OPTIONAL_SCOPE,
        "annotation_fields": ANNOTATION_FIELDS,
        "commitment_id_convention": (
            "Use canonical_key format: financial_covenant.<type> or "
            "facility.<type>.  See ANNOTATOR_INSTRUCTIONS.md for the "
            "full list."
        ),
        "scoring_rule": (
            "Only commitments in required_commitment_classes will be "
            "scored as reconstruction errors.  Optional classes are "
            "recorded for completeness but classified GOLD_NOT_IN_SCOPE."
        ),
    }
    scope_path = HANDOFF_DIR / "COMMITMENT_SCOPE.json"
    scope_path.write_text(json.dumps(scope, indent=2), encoding="utf-8")
    print(f"  Commitment scope: {scope_path}")

    # 3. Per-chain packages
    chain_packages: list[dict] = []
    for chain_id in PREREGISTERED:
        chain = chains_by_id.get(chain_id)
        if not chain:
            print(f"  WARNING: {chain_id} not in manifest, skipping")
            continue

        chain_dir = HANDOFF_DIR / chain_id
        chain_dir.mkdir(parents=True, exist_ok=True)

        docs = chain["documents"]
        s0_doc = next((d for d in docs if d["role"] == "S0"), None)
        cmp_doc = next((d for d in docs if d["role"] == "CMP"), None)

        # Select gold source document (CMP if available, else S0)
        if cmp_doc:
            gold_doc = cmp_doc
            document_id = "CMP"
        elif s0_doc:
            gold_doc = s0_doc
            document_id = "S0"
        else:
            print(f"  WARNING: {chain_id} has no S0 or CMP, skipping")
            continue

        # Copy source text file (NOT the system's extraction output)
        src_text_path = Path(gold_doc["text_path"])
        dst_text_path = chain_dir / f"{document_id}.txt"
        shutil.copy2(src_text_path, dst_text_path)
        text_sha256 = sha256_file(dst_text_path)

        # Chain metadata (no system predictions exposed)
        metadata = {
            "chain_id": chain_id,
            "issuer": chain["issuer"],
            "cik": chain["cik"],
            "document_id": document_id,
            "source_document": f"{document_id}.txt",
            "source_text_sha256": text_sha256,
            "source_text_chars": gold_doc["text_chars"],
            "accession": gold_doc["accession"],
            "file_date": gold_doc["file_date"],
            "exhibit_type": gold_doc["exhibit_type"],
            "exhibit_description": gold_doc["exhibit_description"],
            "sec_url": gold_doc["document_url"],
            "amendment_count": len([d for d in docs if d["role"].startswith("A")]),
            "note": (
                "This is the SOURCE DOCUMENT ONLY.  Annotate from this "
                "file.  Do NOT seek out or view the automated system's "
                "predictions, reconstruction output, or proxy gold "
                "annotations."
            ),
        }
        meta_path = chain_dir / "CHAIN_METADATA.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Annotation template (empty)
        template = create_annotation_template(chain_id, chain["issuer"], document_id)
        template_path = chain_dir / f"{chain_id}_ANNOTATOR_ID_gold.json"
        template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

        chain_packages.append({
            "chain_id": chain_id,
            "issuer": chain["issuer"],
            "document_id": document_id,
            "source_text_chars": gold_doc["text_chars"],
            "text_sha256": text_sha256,
            "accession": gold_doc["accession"],
            "file_date": gold_doc["file_date"],
            "package_dir": str(chain_dir),
            "files": [
                "CHAIN_METADATA.json",
                f"{document_id}.txt",
                f"{chain_id}_ANNOTATOR_ID_gold.json",
            ],
        })

        print(f"  {chain_id}: {chain['issuer'][:35]:35s}  {document_id}  "
              f"{gold_doc['text_chars']:>7} chars  {len(chain_packages)} packages")

    # 4. Write handoff manifest
    handoff_manifest = {
        "package": "human_gold_annotation_handoff",
        "step": "19B.3",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "frozen_system": "v1.0-frozen-operational-build",
        "preregistered_chains": PREREGISTERED,
        "chain_count": len(chain_packages),
        "instructions_file": "ANNOTATOR_INSTRUCTIONS.md",
        "scope_file": "COMMITMENT_SCOPE.json",
        "chain_packages": chain_packages,
        "blinding_requirements": [
            "Annotators must NOT view frozen system predictions",
            "Annotators must NOT view reconstruction outputs",
            "Annotators must NOT view automated proxy annotations",
            "Annotators must NOT view other annotators' work until both passes are complete",
            "Annotators must NOT view the held_out_study_results.json file",
            "Annotators must NOT view the data/held_out/gold/ directory",
        ],
        "workflow": [
            "1. Primary annotator creates gold for all 5 chains from source documents",
            "2. Independent second annotator creates gold for the same 5 chains (blinded from primary)",
            "3. Adjudicator compares both annotation sets, resolves disagreements",
            "4. Final adjudicated gold dataset is locked and hashed",
            "5. Locked gold is used to score EXISTING frozen v1 predictions (no re-run)",
        ],
        "deliverables": [
            "5 primary annotation files: {chain_id}_annotator_primary_gold.json",
            "5 secondary annotation files: {chain_id}_annotator_secondary_gold.json",
            "1 adjudication report: ADJUDICATION_REPORT.md",
            "5 locked gold files: {chain_id}_gold_locked.json",
            "1 gold lock record: GOLD_LOCK_RECORD.json (SHA-256 hashes)",
            "1 inter-annotator agreement report: AGREEMENT_REPORT.md",
        ],
        "estimated_workload": {
            "documents": 5,
            "total_text_chars": sum(p["source_text_chars"] for p in chain_packages),
            "estimated_hours_per_annotator": "20-40 hours",
            "estimated_hours_for_adjudication": "4-8 hours",
            "note": (
                "Time estimates are based on document size.  Large "
                "credit agreements (400K+ chars) contain many "
                "covenants and require careful section-by-section reading."
            ),
        },
    }
    manifest_path = HANDOFF_DIR / "HANDOFF_MANIFEST.json"
    manifest_path.write_text(json.dumps(handoff_manifest, indent=2), encoding="utf-8")
    print(f"\n  Handoff manifest: {manifest_path}")
    print(f"  Total chains: {len(chain_packages)}")
    print(f"  Total text chars: {handoff_manifest['estimated_workload']['total_text_chars']}")
    print(f"  Estimated time per annotator: {handoff_manifest['estimated_workload']['estimated_hours_per_annotator']}")

    print()
    print("=" * 60)
    print("Human gold handoff package complete.")
    print(f"Location: {HANDOFF_DIR}")
    print()
    print("Contents:")
    for item in sorted(HANDOFF_DIR.iterdir()):
        if item.is_file():
            print(f"  {item.name}")
        elif item.is_dir():
            print(f"  {item.name}/")
            for sub in sorted(item.iterdir()):
                print(f"    {sub.name}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
