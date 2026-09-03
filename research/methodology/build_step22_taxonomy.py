"""Step 22C — Unresolved taxonomy builder.

Classifies every unresolved record from the Step 21 corpus into one of
14 mutually-exclusive engineering buckets, identifies the smallest
mechanism set covering >=80% of unresolved records, and writes a
machine-readable JSON + markdown report.

Buckets:
  1. TARGET_RESOLUTION          — commitment target not identified
  2. COMMITMENT_ALIAS           — alias not in registry
  3. FIELD_IDENTIFICATION       — field not identified
  4. OLD_VALUE_EXTRACTION       — old value not extracted
  5. NEW_VALUE_EXTRACTION       — new value not extracted
  6. UNIT_NORMALIZATION         — unit mismatch
  7. OPERATION_INTERPRETATION   — operation unclear
  8. DEFINED_TERM_RESOLUTION    — defined term not resolved
  9. CROSS_REFERENCE_RESOLUTION — cross-ref not resolved
 10. S0_STATE_MISSING           — S0 state not extracted
 11. DOCUMENT_STRUCTURE         — document structure issue
 12. UNSUPPORTED_COMMITMENT     — commitment not in 13-class ontology
 13. TRUE_AMBIGUITY             — genuinely ambiguous
 14. OTHER                      — catch-all

Usage:
    python build_step22_taxonomy.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Bucket constants
# ---------------------------------------------------------------------------

TARGET_RESOLUTION = "TARGET_RESOLUTION"
COMMITMENT_ALIAS = "COMMITMENT_ALIAS"
FIELD_IDENTIFICATION = "FIELD_IDENTIFICATION"
OLD_VALUE_EXTRACTION = "OLD_VALUE_EXTRACTION"
NEW_VALUE_EXTRACTION = "NEW_VALUE_EXTRACTION"
UNIT_NORMALIZATION = "UNIT_NORMALIZATION"
OPERATION_INTERPRETATION = "OPERATION_INTERPRETATION"
DEFINED_TERM_RESOLUTION = "DEFINED_TERM_RESOLUTION"
CROSS_REFERENCE_RESOLUTION = "CROSS_REFERENCE_RESOLUTION"
S0_STATE_MISSING = "S0_STATE_MISSING"
DOCUMENT_STRUCTURE = "DOCUMENT_STRUCTURE"
UNSUPPORTED_COMMITMENT = "UNSUPPORTED_COMMITMENT"
TRUE_AMBIGUITY = "TRUE_AMBIGUITY"
OTHER = "OTHER"

ALL_BUCKETS = [
    TARGET_RESOLUTION,
    COMMITMENT_ALIAS,
    FIELD_IDENTIFICATION,
    OLD_VALUE_EXTRACTION,
    NEW_VALUE_EXTRACTION,
    UNIT_NORMALIZATION,
    OPERATION_INTERPRETATION,
    DEFINED_TERM_RESOLUTION,
    CROSS_REFERENCE_RESOLUTION,
    S0_STATE_MISSING,
    DOCUMENT_STRUCTURE,
    UNSUPPORTED_COMMITMENT,
    TRUE_AMBIGUITY,
    OTHER,
]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

# Root-cause cluster → bucket mapping
_RC_TO_BUCKET = {
    "RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT": TARGET_RESOLUTION,
    "RC-02: RESTATE_SECTION_AMBIGUOUS_VALUE": NEW_VALUE_EXTRACTION,
    "RC-03: ADD_UNKNOWN_COMMITMENT": TARGET_RESOLUTION,
    "RC-04: REPLACE_TEXT_UNKNOWN_COMMITMENT": TARGET_RESOLUTION,
    "RC-05: DELETE_UNKNOWN_COMMITMENT": TARGET_RESOLUTION,
    "RC-06: DEFINITION_SECTION_NO_COVENANT": DEFINED_TERM_RESOLUTION,
    "RC-07: NON_COVENANT_SECTION": OTHER,
    "RC-08: COVENANT_IDENTIFIED_VALUE_EXTRACTION_FAILED": NEW_VALUE_EXTRACTION,
    "RC-09: OTHER": OTHER,
}


def classify_record(record: dict[str, Any]) -> str:
    """Classify an unresolved record into one of 14 buckets.

    Uses the root_cause_cluster as the primary signal, then refines
    based on candidate_commitment and instruction_type.
    """
    rc = record.get("root_cause_cluster", "")
    candidate = record.get("candidate_canonical_commitment")
    ins_type = record.get("instruction_type", "")
    section = record.get("section", "")
    source = (record.get("source_span", "") or "").lower()

    # Base bucket from root cause
    bucket = _RC_TO_BUCKET.get(rc, OTHER)

    # Refinement: RC-07 NON_COVENANT_SECTION
    if rc.startswith("RC-07"):
        # If the text contains covenant keywords but no candidate was
        # resolved, the commitment may be unsupported (not in the
        # 13-class ontology).
        covenant_kw = [
            "leverage", "ebitda", "covenant", "threshold", "ratio",
            "interest coverage", "tangible net worth", "current ratio",
            "debt service", "fixed charge", "term loan", "revolving",
            "maturity", "facility", "texas ratio", "tier 1",
            "risk.based capital", "return on average assets",
            "asset coverage", "shareholders equity", "working capital",
            "liquidity", "net worth",
        ]
        has_covenant_kw = any(kw in source for kw in covenant_kw)
        if has_covenant_kw and candidate is None:
            bucket = UNSUPPORTED_COMMITMENT
        elif has_covenant_kw and candidate is not None:
            bucket = NEW_VALUE_EXTRACTION
        else:
            bucket = OTHER

    # Refinement: records with a candidate commitment but value
    # extraction failed
    if candidate is not None and bucket == TARGET_RESOLUTION:
        bucket = NEW_VALUE_EXTRACTION

    # Refinement: definitions section with covenant keywords
    if rc.startswith("RC-06") and candidate is not None:
        bucket = DEFINED_TERM_RESOLUTION

    # Refinement: RESTATE_SECTION with no candidate and definitions
    # section
    if rc.startswith("RC-01") and "1.01" in section or "1.1" in section:
        if "definition" in source[:200]:
            bucket = DEFINED_TERM_RESOLUTION

    return bucket


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def build_taxonomy(corpus_json: dict[str, Any]) -> dict[str, Any]:
    """Build the full taxonomy from the corpus JSON."""
    records = corpus_json.get("records", [])
    classified: list[dict[str, Any]] = []

    for rec in records:
        bucket = classify_record(rec)
        classified.append({
            "chain": rec.get("chain", ""),
            "amendment": rec.get("amendment_number", 0),
            "section": rec.get("section", ""),
            "instruction_type": rec.get("instruction_type", ""),
            "bucket": bucket,
            "root_cause_cluster": rec.get("root_cause_cluster", ""),
            "candidate_commitment": rec.get("candidate_canonical_commitment"),
        })

    counts = Counter(c["bucket"] for c in classified)
    total = len(classified)
    percentages = {
        b: round(counts.get(b, 0) / total * 100, 2) if total else 0.0
        for b in ALL_BUCKETS
    }

    # Smallest mechanism set covering >=80%
    sorted_buckets = sorted(counts.items(), key=lambda x: -x[1])
    cumulative = 0
    mechanism_set: list[str] = []
    for bucket, count in sorted_buckets:
        cumulative += count
        mechanism_set.append(bucket)
        if cumulative / total * 100 >= 80 if total else False:
            break

    return {
        "total_records": total,
        "bucket_distribution": dict(sorted(counts.items(), key=lambda x: -x[1])),
        "bucket_percentages": percentages,
        "mechanism_set_80pct": mechanism_set,
        "mechanism_set_coverage": round(
            sum(counts[b] for b in mechanism_set) / total * 100, 2,
        ) if total else 0.0,
        "records": classified,
    }


def render_report(taxonomy: dict[str, Any]) -> str:
    """Render the taxonomy as markdown."""
    lines: list[str] = []
    lines.append("# Step 22C — Unresolved Taxonomy")
    lines.append("")
    lines.append(f"**Total records:** {taxonomy['total_records']}")
    lines.append("")

    lines.append("## Bucket distribution")
    lines.append("")
    lines.append("| Bucket | Count | % |")
    lines.append("|---|---:|---:|")
    for bucket in ALL_BUCKETS:
        count = taxonomy["bucket_distribution"].get(bucket, 0)
        pct = taxonomy["bucket_percentages"].get(bucket, 0.0)
        lines.append(f"| {bucket} | {count} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Smallest mechanism set covering >=80%")
    lines.append("")
    lines.append(f"**Coverage:** {taxonomy['mechanism_set_coverage']:.1f}%")
    lines.append("")
    lines.append("| # | Bucket | Count | Cumulative % |")
    lines.append("|---:|---|---:|---:|")
    sorted_buckets = sorted(
        taxonomy["bucket_distribution"].items(), key=lambda x: -x[1],
    )
    total = taxonomy["total_records"]
    cum = 0
    for bucket, count in sorted_buckets:
        cum += count
        cum_pct = cum / total * 100 if total else 0
        in_set = "✓" if bucket in taxonomy["mechanism_set_80pct"] else ""
        lines.append(
            f"| {in_set} | {bucket} | {count} | {cum_pct:.1f}% |",
        )
    lines.append("")

    lines.append("## Build priority")
    lines.append("")
    lines.append("The following mechanisms should be built first to cover")
    lines.append("at least 80% of unresolved records:")
    lines.append("")
    for bucket in taxonomy["mechanism_set_80pct"]:
        count = taxonomy["bucket_distribution"].get(bucket, 0)
        lines.append(f"1. **{bucket}** — {count} records")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    corpus_path = Path("results/step_21_unresolved_corpus.json")
    if not corpus_path.exists():
        print(f"ERROR: {corpus_path} not found. Run build_unresolved_corpus.py first.")
        return 1

    corpus_json = json.loads(corpus_path.read_text(encoding="utf-8"))
    taxonomy = build_taxonomy(corpus_json)

    # Write JSON
    output_json = Path("results/step_22_unresolved_taxonomy.json")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(taxonomy, indent=2), encoding="utf-8")
    print(f"Taxonomy JSON: {output_json} ({taxonomy['total_records']} records)")

    # Write report
    report = render_report(taxonomy)
    report_path = Path("results/step_22_unresolved_taxonomy_report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}")

    # Print summary
    print()
    print("=" * 60)
    print("UNRESOLVED TAXONOMY SUMMARY")
    print("=" * 60)
    print(f"Total records: {taxonomy['total_records']}")
    print(f"Mechanism set (>=80%): {taxonomy['mechanism_set_coverage']:.1f}%")
    print()
    print("Bucket distribution:")
    for bucket, count in sorted(
        taxonomy["bucket_distribution"].items(), key=lambda x: -x[1],
    ):
        pct = taxonomy["bucket_percentages"].get(bucket, 0.0)
        print(f"  {bucket}: {count} ({pct:.1f}%)")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
