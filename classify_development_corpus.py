"""Run v0.3 parser across the 25-issuer development corpus and classify
each document into format categories A-G.

Format taxonomy:
  A — inline amendment instructions
  B — amendment + composite Annex
  C — amended & restated agreement
  D — redline/blackline composite
  E — definition-heavy / cross-reference amendment
  F — waiver-only amendment
  G — mixed/other

For each document captures:
  issuer, accession, amendment number, document format, composite present?,
  instruction count, instruction classes detected, UNRESOLVED count,
  false positives, false negatives, parser coverage

Usage:
    set -a && source .env && set +a
    python classify_development_corpus.py
"""
from __future__ import annotations
import csv, json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

from amendment_parser import parse_v03, parse  # v0.3 and v0.2

DEV_DIR = Path("data/development")
OUTPUT_CSV = Path("development_corpus.csv")
OUTPUT_JSON = Path("data/development/classification_results.json")

# ---------------------------------------------------------------------------
# Document format classification heuristics
# ---------------------------------------------------------------------------

def classify_format(text: str, v03_result: dict, v02_result: list) -> str:
    """Classify a document into format A-G based on structural signals.

    This is a heuristic classifier for population prevalence measurement,
    NOT a gold-standard annotation. The classification uses:
    - composite_target presence (from v0.3 segmentation)
    - Annex A markers
    - "amended and restated" language
    - redline/blackline markers (bold, stricken, double-underlined)
    - instruction content patterns
    - waiver-only patterns
    - amendment instruction language (broader than parser regexes)
    """
    composite = v03_result.get("composite_target")
    instructions = v03_result["instructions"]
    segments = v03_result["segments"]

    text_lower = text.lower()

    # Check for composite/redline markers
    has_annex_a = bool(re.search(r'annex\s+a\b', text_lower))
    has_composite_target = composite is not None
    has_redline_markers = bool(
        re.search(r'(?:bold,?\s+)?(?:stricken|strikethrough)\s+text', text_lower)
        or re.search(r'double-underlined', text_lower)
        or re.search(r'blackline|redline', text_lower)
    )
    has_composite_language = bool(
        re.search(r'composite\s+(?:credit\s+)?agreement', text_lower)
    )

    # Check amendment body content
    body_start = segments["amendment_body"]["start"]
    body_end = segments["amendment_body"]["end"]
    body_text = text[body_start:body_end] if body_end > body_start else ""
    body_lower = body_text.lower()

    # Broad amendment instruction detection (broader than parser regexes)
    # These detect the PRESENCE of amendment instructions even if the parser
    # doesn't catch them — this is for format classification, not parsing.
    has_amended_by = bool(re.search(
        r'(?:Section|Article|Schedule|Exhibit)\s+[\w.\-()]+'
        r'.{0,200}?is\s+hereby\s+amended\s+by',
        body_text, re.I | re.S
    ))
    has_amended_to_delete = bool(re.search(
        r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
        r'.{0,200}?is\s+(?:hereby\s+)?amended\s+to\s+(?:delete|add|modify|read)',
        body_text, re.I | re.S
    ))
    has_amended_as_follows = bool(re.search(
        r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
        r'.{0,200}?is\s+(?:hereby\s+)?amended\s+as\s+follows',
        body_text, re.I | re.S
    ))
    has_deleting_replacing = bool(re.search(
        r'deleting.*?(?:replacing|inserting)', body_text, re.I | re.S
    ))
    has_is_hereby_waived = bool(re.search(
        r'is\s+hereby\s+waived', body_text, re.I
    ))
    has_amended_restated_instruction = bool(re.search(
        r'(?:Section|Article)\s+[\w.\-()]+'
        r'.{0,200}?amended\s+and\s+restated\s+in\s+its\s+entirety',
        body_text, re.I | re.S
    ))
    has_is_hereby_deleted = bool(re.search(
        r'is\s+hereby\s+deleted\s+from\s+(?:Section|Article|Schedule)',
        body_text, re.I | re.S
    ))
    # Consent/forbearance: different document type
    has_consent_forbearance = bool(re.search(
        r'consent\s+(?:and\s+forbearance|to)|forbearance\s+agreement',
        text[:2000], re.I
    ))

    # Is this a full amended & restated agreement (not an amendment)?
    # Key signal: the document title/header says "AMENDED AND RESTATED"
    # but there are no "is hereby amended by" instructions in the body
    has_amended_restated_title = bool(re.search(
        r'(?:AMENDED\s+AND\s+RESTATED|RESTATED)\s+(?:CREDIT\s+)?AGREEMENT',
        text[:2000], re.I
    ))
    is_full_restated_agreement = (
        has_amended_restated_title
        and not has_amended_by
        and not has_amended_to_delete
        and not has_deleting_replacing
        and not has_amended_restated_instruction
    )

    # Instruction type analysis (from parser)
    inst_types = [i["instruction_type"] for i in instructions]
    has_waiver_inst = "WAIVE_TEMPORARILY" in inst_types
    has_replace_inst = "REPLACE_TEXT" in inst_types
    has_restate_inst = "RESTATE_SECTION" in inst_types
    has_delete_inst = "DELETE_COMMITMENT" in inst_types
    has_add_inst = "ADD_COMMITMENT" in inst_types

    # Definition-heavy: lots of "means" definitions
    def_count = len(re.findall(r'"[^"]+"\s+(?:means|shall\s+mean)\s', text))
    is_definition_heavy = def_count > 20

    # Waiver-only: the amendment body only contains waiver language
    body_len = len(body_lower)
    only_waiver = has_is_hereby_waived and not has_amended_by and not has_deleting_replacing

    # Has any amendment instruction language (broader than parser)
    has_any_amendment_language = (
        has_amended_by or has_amended_to_delete or has_amended_as_follows
        or has_deleting_replacing or has_amended_restated_instruction
        or has_is_hereby_waived or has_is_hereby_deleted
    )

    # Classification logic (ordered by specificity)
    # D — redline/blackline composite (has redline markers + composite)
    if has_redline_markers and (has_composite_target or has_composite_language):
        return "D"

    # B — amendment + composite Annex (has inline instructions + Annex A composite)
    if has_composite_target and (instructions or has_any_amendment_language):
        return "B"

    # C — amended & restated agreement (full restatement, no inline instructions)
    if is_full_restated_agreement:
        return "C"

    # F — waiver-only amendment (or consent/forbearance)
    if has_consent_forbearance:
        return "F"
    if only_waiver and body_len < 10000:
        return "F"

    # A — inline amendment instructions (has amendment language, no composite)
    if has_any_amendment_language and not has_composite_target:
        if is_definition_heavy and not has_is_hereby_waived and not has_deleting_replacing:
            return "E"
        return "A"

    # E — definition-heavy / cross-reference amendment
    if is_definition_heavy and not has_composite_target and has_any_amendment_language:
        return "E"

    # B — has composite target even without instructions (composite-only)
    if has_composite_target:
        return "B"

    # G — mixed/other (has some amendment signals but doesn't fit above)
    return "G"


def count_amendment_number(text: str) -> str:
    """Try to extract the amendment number from the document."""
    patterns = [
        r'(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+'
        r'AMENDMENT',
        r'AMENDMENT\s+(?:NO\.?\s*)?(\d+)',
        r'(\d+)(?:st|nd|rd|th)\s+AMENDMENT',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            s = m.group(0).strip()
            # Try to extract a number
            num_match = re.search(r'(\d+)', s)
            word_map = {
                "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4",
                "FIFTH": "5", "SIXTH": "6", "SEVENTH": "7", "EIGHTH": "8",
                "NINTH": "9", "TENTH": "10",
            }
            for word, num in word_map.items():
                if word in s.upper():
                    return num
            if num_match:
                return num_match.group(1)
            return s
    return "unknown"


def estimate_false_positives(v02_result: list, v03_result: dict) -> int:
    """Estimate false positives: instructions in v0.2 that are NOT in v0.3
    (i.e., v0.3 removed them via segmentation/waiver tightening)."""
    v02_count = len(v02_result)
    v03_count = len(v03_result["instructions"])
    # The reduction is likely false positives (waivers from composite, etc.)
    # But some could be true positives that v0.3 missed (false negatives)
    return max(0, v02_count - v03_count)


def _count_amendment_patterns(body: str) -> int:
    """Count expected amendment instructions using broader patterns."""
    amended_by_count = len(re.findall(
        r'(?:Section|Article|Schedule|Exhibit)\s+[\w.\-()]+'
        r'.{0,200}?is\s+hereby\s+amended\s+by',
        body, re.I | re.S
    ))
    amended_to_count = len(re.findall(
        r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
        r'.{0,200}?is\s+(?:hereby\s+)?amended\s+to\s+(?:delete|add|modify|read)',
        body, re.I | re.S
    ))
    amended_as_follows_count = len(re.findall(
        r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
        r'.{0,200}?is\s+(?:hereby\s+)?amended\s+as\s+follows',
        body, re.I | re.S
    ))
    replace_count = len(re.findall(
        r'deleting.*?(?:replacing|inserting)', body, re.I | re.S
    ))
    waive_count = len(re.findall(r'is\s+hereby\s+waived', body, re.I))
    restated_count = len(re.findall(
        r'(?:Section|Article)\s+[\w.\-()]+'
        r'.{0,200}?amended\s+and\s+restated\s+in\s+its\s+entirety',
        body, re.I | re.S
    ))
    deleted_count = len(re.findall(
        r'is\s+hereby\s+deleted\s+from\s+(?:Section|Article|Schedule)',
        body, re.I | re.S
    ))
    return (amended_by_count + amended_to_count + amended_as_follows_count
            + replace_count + waive_count + restated_count + deleted_count)


def estimate_false_negatives(text: str, v03_result: dict) -> int:
    """Estimate false negatives: amendment instructions in the text that
    v0.3 did not detect. Uses broader patterns than the parser itself."""
    body = text[v03_result["segments"]["amendment_body"]["start"]:
                v03_result["segments"]["amendment_body"]["end"]]
    expected = _count_amendment_patterns(body)
    detected = len(v03_result["instructions"])
    return max(0, expected - detected)


def estimate_parser_coverage(text: str, v03_result: dict) -> float:
    """Estimate parser coverage as detected/expected using broader patterns."""
    body = text[v03_result["segments"]["amendment_body"]["start"]:
                v03_result["segments"]["amendment_body"]["end"]]
    expected = _count_amendment_patterns(body)
    detected = len(v03_result["instructions"])
    if expected == 0:
        return 1.0  # No expected instructions = full coverage (vacuously)
    return min(1.0, detected / expected)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not DEV_DIR.exists():
        print(f"ERROR: {DEV_DIR} does not exist. Run build_development_corpus.py first.")
        sys.exit(1)

    # Load manifest
    manifest = json.loads((DEV_DIR / "manifest.json").read_text())
    docs = manifest["documents"]

    print(f"Classifying {len(docs)} development corpus documents...")
    print()

    results = []
    for doc in sorted(docs, key=lambda d: d["case_id"]):
        case_id = doc["case_id"]
        text_path = DEV_DIR / case_id / "source.txt"
        text = text_path.read_text(encoding="utf-8", errors="ignore")

        # Run v0.3 parser
        v03_result = parse_v03(text)
        # Run v0.2 parser for comparison
        v02_result = parse(text)

        # Classify
        fmt = classify_format(text, v03_result, v02_result)
        amend_num = count_amendment_number(text)
        composite_present = v03_result["composite_target"] is not None
        inst_count = len(v03_result["instructions"])
        inst_classes = sorted(set(i["instruction_type"] for i in v03_result["instructions"]))
        unresolved_count = sum(1 for i in v03_result["instructions"] if i["instruction_type"] == "UNRESOLVED")
        false_pos = estimate_false_positives(v02_result, v03_result)
        false_neg = estimate_false_negatives(text, v03_result)
        coverage = estimate_parser_coverage(text, v03_result)

        row = {
            "case_id": case_id,
            "issuer": doc["issuer"],
            "cik": doc["cik"],
            "accession": doc["accession"],
            "filing_date": doc["filing_date"],
            "amendment_number": amend_num,
            "document_format": fmt,
            "composite_present": composite_present,
            "instruction_count": inst_count,
            "instruction_classes": ";".join(inst_classes) if inst_classes else "",
            "unresolved_count": unresolved_count,
            "false_positives_est": false_pos,
            "false_negatives_est": false_neg,
            "parser_coverage": round(coverage, 3),
            "text_chars": doc["text_chars"],
            "v02_instruction_count": len(v02_result),
            "exhibit_type": doc["exhibit_type"],
        }
        results.append(row)

        print(f"  {case_id} fmt={fmt} inst={inst_count} v02={len(v02_result)} "
              f"composite={'Y' if composite_present else 'N'} "
              f"coverage={coverage:.2f} amend#{amend_num} {doc['issuer'][:35]}")

    # Write CSV
    fieldnames = [
        "case_id", "issuer", "cik", "accession", "filing_date",
        "amendment_number", "document_format", "composite_present",
        "instruction_count", "instruction_classes", "unresolved_count",
        "false_positives_est", "false_negatives_est", "parser_coverage",
        "text_chars", "v02_instruction_count", "exhibit_type",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Write JSON
    json_output = {
        "classified_at_utc": datetime.now(timezone.utc).isoformat(),
        "document_count": len(results),
        "results": results,
    }
    OUTPUT_JSON.write_text(json.dumps(json_output, indent=2), encoding="utf-8")

    # Summary
    print()
    print("=" * 70)
    print("FORMAT DISTRIBUTION")
    print("=" * 70)
    format_counts = {}
    for r in results:
        fmt = r["document_format"]
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    for fmt in sorted(format_counts):
        count = format_counts[fmt]
        pct = 100 * count / len(results)
        print(f"  {fmt}: {count:2d} ({pct:5.1f}%)")

    print()
    print("=" * 70)
    print("INSTRUCTION STATISTICS")
    print("=" * 70)
    total_inst = sum(r["instruction_count"] for r in results)
    total_v02 = sum(r["v02_instruction_count"] for r in results)
    total_composite = sum(1 for r in results if r["composite_present"])
    total_fp = sum(r["false_positives_est"] for r in results)
    total_fn = sum(r["false_negatives_est"] for r in results)
    avg_coverage = sum(r["parser_coverage"] for r in results) / len(results)
    print(f"  Total v0.3 instructions: {total_inst}")
    print(f"  Total v0.2 instructions: {total_v02}")
    print(f"  Composite targets found:  {total_composite}/{len(results)}")
    print(f"  Est. false positives (v0.2→v0.3 reduction): {total_fp}")
    print(f"  Est. false negatives (missed instructions):  {total_fn}")
    print(f"  Average parser coverage:  {avg_coverage:.3f}")

    print()
    print(f"CSV:  {OUTPUT_CSV}")
    print(f"JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
