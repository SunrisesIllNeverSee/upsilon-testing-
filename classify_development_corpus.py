"""Run v0.3 and v0.4 parsers across the 25-document parser-development
sample and classify each document into format categories A-G.

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
  instruction count (v0.3 and v0.4), instruction classes detected,
  TP/FP/FN against gold annotations, precision, recall, F1.

This script uses explicit gold annotations (data/development/gold_annotations.json)
as ground truth. It does NOT estimate expected instructions from overlapping
regex counts, and it does NOT estimate false positives from parser version
differences.

Usage:
    python classify_development_corpus.py
"""
from __future__ import annotations
import csv, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

from amendment_parser import parse_v03, parse_v04, parse  # v0.3, v0.4, v0.2

DEV_DIR = Path("data/development")
GOLD_PATH = DEV_DIR / "gold_annotations.json"
OUTPUT_CSV = Path("development_corpus.csv")
OUTPUT_JSON = Path("data/development/classification_results.json")


# ---------------------------------------------------------------------------
# Gold annotation matching
# ---------------------------------------------------------------------------

def _normalize_ref(ref: str | None) -> str:
    """Normalize a section reference for matching: collapse whitespace,
    strip trailing punctuation, lowercase."""
    if not ref:
        return ""
    return re.sub(r"\s+", " ", ref).strip().rstrip(".").lower()


def load_gold_annotations() -> dict:
    """Load gold annotations from the JSON file."""
    return json.loads(GOLD_PATH.read_text())


def match_instructions_to_gold(
    detected: list[dict], gold: list[dict]
) -> tuple[int, int, int]:
    """Match detected instructions to gold annotations.

    Returns (tp, fp, fn) where:
      tp = true positives (detected instructions that match a gold annotation)
      fp = false positives (detected instructions that don't match any gold annotation)
      fn = false negatives (gold annotations not matched by any detected instruction)

    Matching is by (normalized target_ref, instruction_type). Each gold annotation
    can be matched at most once, and each detected instruction can match at most
    one gold annotation.
    """
    # Build gold list with match flags
    gold_remaining = []
    for g in gold:
        gold_remaining.append({
            "ref": _normalize_ref(g["target_ref"]),
            "type": g["instruction_type"],
            "matched": False,
        })

    tp = 0
    fp = 0
    for inst in detected:
        ref = _normalize_ref(inst.get("target_section_ref"))
        typ = inst["instruction_type"]
        # Try to find an unmatched gold annotation
        matched = False
        for g in gold_remaining:
            if not g["matched"] and g["ref"] == ref and g["type"] == typ:
                g["matched"] = True
                tp += 1
                matched = True
                break
        if not matched:
            fp += 1

    fn = sum(1 for g in gold_remaining if not g["matched"])
    return tp, fp, fn


def compute_metrics(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Compute precision, recall, F1."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


# ---------------------------------------------------------------------------
# Document format classification heuristics
# ---------------------------------------------------------------------------

def classify_format(text: str, v04_result: dict, v02_result: list) -> str:
    """Classify a document into format A-G based on structural signals."""
    composite = v04_result.get("composite_target")
    instructions = v04_result["instructions"]
    segments = v04_result["segments"]

    text_lower = text.lower()

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

    body_start = segments["amendment_body"]["start"]
    body_end = segments["amendment_body"]["end"]
    body_text = text[body_start:body_end] if body_end > body_start else ""
    body_lower = body_text.lower()

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
    has_consent_forbearance = bool(re.search(
        r'consent\s+(?:and\s+forbearance|to)|forbearance\s+agreement',
        text[:2000], re.I
    ))

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

    inst_types = [i["instruction_type"] for i in instructions]
    has_waiver_inst = "WAIVE_TEMPORARILY" in inst_types

    def_count = len(re.findall(r'"[^"]+"\s+(?:means|shall\s+mean)\s', text))
    is_definition_heavy = def_count > 20

    body_len = len(body_lower)
    only_waiver = has_is_hereby_waived and not has_amended_by and not has_deleting_replacing

    has_any_amendment_language = (
        has_amended_by or has_amended_to_delete or has_amended_as_follows
        or has_deleting_replacing or has_amended_restated_instruction
        or has_is_hereby_waived or has_is_hereby_deleted
    )

    if has_redline_markers and (has_composite_target or has_composite_language):
        return "D"
    if has_composite_target and (instructions or has_any_amendment_language):
        return "B"
    if is_full_restated_agreement:
        return "C"
    if has_consent_forbearance:
        return "F"
    if only_waiver and body_len < 10000:
        return "F"
    if has_any_amendment_language and not has_composite_target:
        if is_definition_heavy and not has_is_hereby_waived and not has_deleting_replacing:
            return "E"
        return "A"
    if is_definition_heavy and not has_composite_target and has_any_amendment_language:
        return "E"
    if has_composite_target:
        return "B"
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not DEV_DIR.exists():
        print(f"ERROR: {DEV_DIR} does not exist. Run build_development_corpus.py first.")
        sys.exit(1)

    manifest = json.loads((DEV_DIR / "manifest.json").read_text())
    docs = manifest["documents"]
    gold_data = load_gold_annotations()

    print(f"Classifying {len(docs)} development corpus documents...")
    print(f"Gold annotations loaded from {GOLD_PATH}")
    print()

    results = []
    for doc in sorted(docs, key=lambda d: d["case_id"]):
        case_id = doc["case_id"]
        text_path = DEV_DIR / case_id / "source.txt"
        text = text_path.read_text(encoding="utf-8", errors="ignore")

        # Run all three parser versions
        v03_result = parse_v03(text)
        v04_result = parse_v04(text)
        v02_result = parse(text)

        # Classify format using v0.4 result
        fmt = classify_format(text, v04_result, v02_result)
        amend_num = count_amendment_number(text)
        composite_present = v04_result["composite_target"] is not None

        # Get gold annotations for this document
        gold_entry = gold_data.get(case_id, {"expected": []})
        gold = gold_entry.get("expected", [])

        # Compute metrics for v0.3 (baseline)
        v03_tp, v03_fp, v03_fn = match_instructions_to_gold(
            v03_result["instructions"], gold
        )
        v03_prec, v03_rec, v03_f1 = compute_metrics(v03_tp, v03_fp, v03_fn)

        # Compute metrics for v0.4
        v04_tp, v04_fp, v04_fn = match_instructions_to_gold(
            v04_result["instructions"], gold
        )
        v04_prec, v04_rec, v04_f1 = compute_metrics(v04_tp, v04_fp, v04_fn)

        v03_inst_count = len(v03_result["instructions"])
        v04_inst_count = len(v04_result["instructions"])
        v03_classes = sorted(set(i["instruction_type"] for i in v03_result["instructions"]))
        v04_classes = sorted(set(i["instruction_type"] for i in v04_result["instructions"]))
        v03_unresolved = sum(1 for i in v03_result["instructions"] if i["instruction_type"] == "UNRESOLVED")
        v04_unresolved = sum(1 for i in v04_result["instructions"] if i["instruction_type"] == "UNRESOLVED")

        row = {
            "case_id": case_id,
            "issuer": doc["issuer"],
            "cik": doc["cik"],
            "accession": doc["accession"],
            "filing_date": doc["filing_date"],
            "amendment_number": amend_num,
            "document_format": fmt,
            "composite_present": composite_present,
            "gold_count": len(gold),
            "v03_instruction_count": v03_inst_count,
            "v04_instruction_count": v04_inst_count,
            "v03_tp": v03_tp,
            "v03_fp": v03_fp,
            "v03_fn": v03_fn,
            "v03_precision": round(v03_prec, 3),
            "v03_recall": round(v03_rec, 3),
            "v03_f1": round(v03_f1, 3),
            "v04_tp": v04_tp,
            "v04_fp": v04_fp,
            "v04_fn": v04_fn,
            "v04_precision": round(v04_prec, 3),
            "v04_recall": round(v04_rec, 3),
            "v04_f1": round(v04_f1, 3),
            "v04_instruction_classes": ";".join(v04_classes) if v04_classes else "",
            "v04_unresolved_count": v04_unresolved,
            "v02_instruction_count": len(v02_result),
            "text_chars": doc["text_chars"],
            "exhibit_type": doc["exhibit_type"],
        }
        results.append(row)

        print(f"  {case_id} fmt={fmt} gold={len(gold):2d} "
              f"v03={v03_inst_count}(P={v03_prec:.2f} R={v03_rec:.2f}) "
              f"v04={v04_inst_count}(P={v04_prec:.2f} R={v04_rec:.2f}) "
              f"{'Y' if composite_present else 'N'} {doc['issuer'][:30]}")

    # Write CSV
    fieldnames = [
        "case_id", "issuer", "cik", "accession", "filing_date",
        "amendment_number", "document_format", "composite_present",
        "gold_count",
        "v03_instruction_count", "v03_tp", "v03_fp", "v03_fn",
        "v03_precision", "v03_recall", "v03_f1",
        "v04_instruction_count", "v04_tp", "v04_fp", "v04_fn",
        "v04_precision", "v04_recall", "v04_f1",
        "v04_instruction_classes", "v04_unresolved_count",
        "v02_instruction_count", "text_chars", "exhibit_type",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Write JSON
    json_output = {
        "classified_at_utc": datetime.now(timezone.utc).isoformat(),
        "document_count": len(results),
        "dataset_description": "25-document parser-development sample (not the eventual 25-issuer agreement-chain corpus)",
        "gold_annotation_source": str(GOLD_PATH),
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
    print("POOLED METRICS (All amendment documents)")
    print("=" * 70)
    # Pool TP/FP/FN across all documents
    v03_tp_total = sum(r["v03_tp"] for r in results)
    v03_fp_total = sum(r["v03_fp"] for r in results)
    v03_fn_total = sum(r["v03_fn"] for r in results)
    v04_tp_total = sum(r["v04_tp"] for r in results)
    v04_fp_total = sum(r["v04_fp"] for r in results)
    v04_fn_total = sum(r["v04_fn"] for r in results)
    gold_total = sum(r["gold_count"] for r in results)

    v03_p, v03_r, v03_f = compute_metrics(v03_tp_total, v03_fp_total, v03_fn_total)
    v04_p, v04_r, v04_f = compute_metrics(v04_tp_total, v04_fp_total, v04_fn_total)

    print(f"  Gold annotations:           {gold_total}")
    print()
    print(f"  v0.3.1 baseline:")
    print(f"    Detected:  {v03_tp_total + v03_fp_total}")
    print(f"    TP:        {v03_tp_total}")
    print(f"    FP:        {v03_fp_total}")
    print(f"    FN:        {v03_fn_total}")
    print(f"    Precision: {v03_p:.3f}")
    print(f"    Recall:    {v03_r:.3f}")
    print(f"    F1:        {v03_f:.3f}")
    print()
    print(f"  v0.4:")
    print(f"    Detected:  {v04_tp_total + v04_fp_total}")
    print(f"    TP:        {v04_tp_total}")
    print(f"    FP:        {v04_fp_total}")
    print(f"    FN:        {v04_fn_total}")
    print(f"    Precision: {v04_p:.3f}")
    print(f"    Recall:    {v04_r:.3f}")
    print(f"    F1:        {v04_f:.3f}")

    print()
    print(f"CSV:  {OUTPUT_CSV}")
    print(f"JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
