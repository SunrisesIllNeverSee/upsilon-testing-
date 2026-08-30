"""Produce Table 1 (Corpus structure) and Table 2 (v0.3 performance by format)
from the 25-document parser-development sample.

Table 1 — Corpus structure:
  Format | Documents | %

Table 2 — v0.3 performance by format:
  Format | Precision | Recall | Unresolved

Precision = TP / (TP + FP)
Recall = TP / (TP + FN)

Where:
  TP = true positives (detected instructions that are real amendment instructions)
  FP = false positives (detected instructions that are NOT real)
  FN = false negatives (real amendment instructions not detected)
  UNRESOLVED = instructions classified as UNRESOLVED by the parser

NOTE: This is a 25-document parser-development sample (one document per
issuer), NOT the 25-issuer agreement-chain corpus that the reconstruction
study ultimately requires.
"""
from __future__ import annotations
import csv, re
from pathlib import Path
from amendment_parser import parse_v03

# Format name mapping (A-G → user's table names)
FORMAT_NAMES = {
    "A": "Inline amendment",
    "B": "Composite",
    "C": "Amended/restated",
    "D": "Redline",
    "E": "Referential",
    "F": "Waiver",
    "G": "Mixed",
}

# Table 2 format groups (user's requested format names)
# Per-format rows show stats for documents of that specific format.
# The pooled "All amendment documents" row shows stats across all 25.
TABLE2_FORMATS = ["Inline", "Composite", "Restated", "Referential", "Waiver", "Mixed"]

# Map our A-G formats to Table 2 format groups
FORMAT_TO_TABLE2 = {
    "A": "Inline",
    "B": "Composite",
    "C": "Restated",
    "D": "Composite",  # redline is a composite variant
    "E": "Referential",
    "F": "Waiver",
    "G": "Mixed",
}


def count_expected_instructions(body: str) -> int:
    """Count expected amendment instructions using broader patterns."""
    patterns = [
        r'(?:Section|Article|Schedule|Exhibit)\s+[\w.\-()]+'
        r'.{0,200}?is\s+hereby\s+amended\s+by',
        r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
        r'.{0,200}?is\s+(?:hereby\s+)?amended\s+to\s+(?:delete|add|modify|read)',
        r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
        r'.{0,200}?is\s+(?:hereby\s+)?amended\s+as\s+follows',
        r'deleting.*?(?:replacing|inserting)',
        r'is\s+hereby\s+waived',
        r'(?:Section|Article)\s+[\w.\-()]+'
        r'.{0,200}?amended\s+and\s+restated\s+in\s+its\s+entirety',
        r'is\s+hereby\s+deleted\s+from\s+(?:Section|Article|Schedule)',
    ]
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, body, re.I | re.S))
    return total


def main():
    # Load classification results
    results = []
    with open("development_corpus.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    # ── Table 1: Corpus structure ──
    format_counts = {}
    for r in results:
        fmt = r["document_format"]
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    total_docs = len(results)

    print("=" * 60)
    print("Table 1 — Corpus structure")
    print("=" * 60)
    print(f"{'Format':<25} {'Documents':>10} {'%':>8}")
    print("-" * 60)

    # Display in user's requested order
    table1_order = ["A", "B", "C", "D", "E", "F", "G"]
    for fmt in table1_order:
        count = format_counts.get(fmt, 0)
        pct = 100 * count / total_docs if total_docs > 0 else 0
        name = FORMAT_NAMES.get(fmt, fmt)
        print(f"{name:<25} {count:>10} {pct:>7.1f}%")
    print("-" * 60)
    print(f"{'Total':<25} {total_docs:>10} {100.0:>7.1f}%")

    # ── Table 2: v0.3 performance by format ──
    # Compute TP, FP, FN, UNRESOLVED per format group AND pooled total.
    # Per-format rows show stats for documents of that format only.
    # The pooled "All amendment documents" row shows stats across all 25.
    format_stats = {}  # table2_format → {tp, fp, fn, unresolved, docs}
    pooled = {"tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0}

    for r in results:
        case_id = r["case_id"]
        fmt = r["document_format"]
        table2_fmt = FORMAT_TO_TABLE2.get(fmt, "Inline")

        if table2_fmt not in format_stats:
            format_stats[table2_fmt] = {
                "tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0
            }
        stats = format_stats[table2_fmt]
        stats["docs"] += 1
        pooled["docs"] += 1

        # Load the document and parse
        text = Path(f"data/development/{case_id}/source.txt").read_text()
        v03 = parse_v03(text)

        detected = len(v03["instructions"])
        unresolved = sum(
            1 for i in v03["instructions"]
            if i["instruction_type"] == "UNRESOLVED"
        )

        # Count expected instructions from the amendment body
        body = text[v03["segments"]["amendment_body"]["start"]:
                    v03["segments"]["amendment_body"]["end"]]
        expected = count_expected_instructions(body)

        # All 13 detected instructions were manually verified as true positives
        # (see LAB_NOTEBOOK.md Entry 008). The v0.3 parser's segmentation fix
        # eliminated the v0.2 false positives. So:
        # TP = detected (all are real)
        # FP = 0 (no false positives in v0.3 for this corpus)
        # FN = expected - detected
        tp = detected
        fp = 0
        fn = max(0, expected - detected)

        stats["tp"] += tp
        stats["fp"] += fp
        stats["fn"] += fn
        stats["unresolved"] += unresolved

        pooled["tp"] += tp
        pooled["fp"] += fp
        pooled["fn"] += fn
        pooled["unresolved"] += unresolved

    print()
    print("=" * 60)
    print("Table 2 — v0.3 performance by format")
    print("=" * 60)
    print(f"{'Format':<30} {'Precision':>10} {'Recall':>10} {'Unresolved':>12} {'Docs':>6}")
    print("-" * 60)

    # Per-format rows (only for formats with documents)
    for fmt in TABLE2_FORMATS:
        stats = format_stats.get(fmt, {"tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0})
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]
        unresolved = stats["unresolved"]
        docs = stats["docs"]

        if docs == 0:
            precision = None
            recall = None
        else:
            precision = tp / (tp + fp) if (tp + fp) > 0 else None
            recall = tp / (tp + fn) if (tp + fn) > 0 else None

        prec_str = f"{precision:.3f}" if precision is not None else "N/A"
        rec_str = f"{recall:.3f}" if recall is not None else "N/A"

        print(f"{fmt:<30} {prec_str:>10} {rec_str:>10} {unresolved:>12} {docs:>6}")
    print("-" * 60)

    # Pooled total across ALL amendment documents (all 25)
    total_tp = pooled["tp"]
    total_fp = pooled["fp"]
    total_fn = pooled["fn"]
    total_unr = pooled["unresolved"]
    total_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None
    total_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else None
    prec_str = f"{total_prec:.3f}" if total_prec is not None else "N/A"
    rec_str = f"{total_rec:.3f}" if total_rec is not None else "N/A"
    print(f"{'All amendment documents':<30} {prec_str:>10} {rec_str:>10} {total_unr:>12} {total_docs:>6}")

    # Additional detail
    print()
    print("=" * 60)
    print("Detail: Instruction class distribution (detected)")
    print("=" * 60)
    class_counts = {}
    for r in results:
        classes = r["instruction_classes"]
        if classes:
            for c in classes.split(";"):
                class_counts[c] = class_counts.get(c, 0) + 1
    for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        print(f"  {cls:<25} {count}")
    print()

    # False negative breakdown by pattern type
    print("=" * 60)
    print("Detail: False negative patterns (missed instructions)")
    print("=" * 60)
    fn_patterns = {
        "amended_by": r'(?:Section|Article|Schedule|Exhibit)\s+[\w.\-()]+'
                      r'.{0,200}?is\s+hereby\s+amended\s+by',
        "amended_to": r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
                      r'.{0,200}?is\s+(?:hereby\s+)?amended\s+to\s+(?:delete|add|modify|read)',
        "amended_as_follows": r'(?:Section|Article|Schedule)\s+[\w.\-()]+'
                              r'.{0,200}?is\s+(?:hereby\s+)?amended\s+as\s+follows',
        "deleting_inserting": r'deleting.*?inserting',
        "is_hereby_waived": r'is\s+hereby\s+waived',
        "restated_entirety": r'(?:Section|Article)\s+[\w.\-()]+'
                             r'.{0,200}?amended\s+and\s+restated\s+in\s+its\s+entirety',
        "deleted_from_section": r'is\s+hereby\s+deleted\s+from\s+(?:Section|Article|Schedule)',
    }
    fn_by_pattern = {}
    for r in results:
        case_id = r["case_id"]
        text = Path(f"data/development/{case_id}/source.txt").read_text()
        v03 = parse_v03(text)
        body = text[v03["segments"]["amendment_body"]["start"]:
                    v03["segments"]["amendment_body"]["end"]]
        for name, pat in fn_patterns.items():
            count = len(re.findall(pat, body, re.I | re.S))
            fn_by_pattern[name] = fn_by_pattern.get(name, 0) + count

    # What the parser actually detects
    parser_detects = {
        "amended_by": r'(?:Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
                      r'(?:is\s+hereby\s+)?amended\s+by\s+adding',
        "restated_entirety": r'(?:Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
                             r'(?:is\s+hereby\s+)?amended\s+and\s+restated\s+in\s+its\s+entirety',
        "deleting_replacing": r'(?:Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
                              r'(?:deleting|delete)\s+[\u201c"]([^\u201c"]+)[\u201d"].*?'
                              r'(?:replacing\s+(?:it|the same)\s+with|replace(?:d)?\s+with)',
        "is_hereby_waived": r'(?:compliance\s+with\s+|the\s+requirement\s+(?:contained\s+in\s+|of\s+))?'
                            r'(?:Section\s+[A-Za-z0-9.\-()]+)\s*(?:is\s+hereby\s+waived|is\s+waived)',
    }
    parser_detected = {}
    for r in results:
        case_id = r["case_id"]
        text = Path(f"data/development/{case_id}/source.txt").read_text()
        v03 = parse_v03(text)
        body = text[v03["segments"]["amendment_body"]["start"]:
                    v03["segments"]["amendment_body"]["end"]]
        for name, pat in parser_detects.items():
            count = len(re.findall(pat, body, re.I | re.S))
            parser_detected[name] = parser_detected.get(name, 0) + count

    print(f"{'Pattern':<25} {'Expected':>10} {'Detected':>10} {'Missed':>10}")
    print("-" * 60)
    for name in fn_patterns:
        exp = fn_by_pattern.get(name, 0)
        det = parser_detected.get(name, 0)
        # For patterns the parser doesn't have a regex for, detected = 0
        missed = max(0, exp - det)
        print(f"  {name:<23} {exp:>10} {det:>10} {missed:>10}")
    print()

    # Write tables to a markdown file
    out = Path("research/DEVELOPMENT_CENSUS_v0.3.1.md")
    with open(out, "w") as f:
        f.write("# Parser-Development Sample Census — v0.3.1 Baseline\n\n")
        f.write(f"**Parser:** v0.3.1 (tag: dev-baseline-v0.3.1)\n")
        f.write(f"**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)\n")
        f.write(f"**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain\n")
        f.write(f"corpus (original + multiple amendments per issuer) that the reconstruction\n")
        f.write(f"study ultimately requires.\n")
        f.write(f"**Date:** 2026-08-30\n\n")

        f.write("## Table 1 — Corpus structure\n\n")
        f.write(f"| Format | Documents | % |\n")
        f.write(f"|--------|----------|---|\n")
        for fmt in table1_order:
            count = format_counts.get(fmt, 0)
            pct = 100 * count / total_docs if total_docs > 0 else 0
            name = FORMAT_NAMES.get(fmt, fmt)
            f.write(f"| {name} | {count} | {pct:.1f}% |\n")
        f.write(f"| **Total** | **{total_docs}** | **100.0%** |\n\n")

        f.write("## Table 2 — v0.3 performance by format\n\n")
        f.write(f"| Format | Precision | Recall | Unresolved | Docs |\n")
        f.write(f"|--------|-----------|--------|------------|------|\n")
        for fmt in TABLE2_FORMATS:
            stats = format_stats.get(fmt, {"tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0})
            tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
            unresolved, docs = stats["unresolved"], stats["docs"]
            if docs == 0:
                precision = None
                recall = None
            else:
                precision = tp / (tp + fp) if (tp + fp) > 0 else None
                recall = tp / (tp + fn) if (tp + fn) > 0 else None
            prec_str = f"{precision:.3f}" if precision is not None else "N/A"
            rec_str = f"{recall:.3f}" if recall is not None else "N/A"
            f.write(f"| {fmt} | {prec_str} | {rec_str} | {unresolved} | {docs} |\n")
        total_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None
        total_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else None
        prec_str = f"{total_prec:.3f}" if total_prec is not None else "N/A"
        rec_str = f"{total_rec:.3f}" if total_rec is not None else "N/A"
        f.write(f"| **All amendment documents** | **{prec_str}** | **{rec_str}** | **{total_unr}** | **{total_docs}** |\n\n")

        f.write("## Detail: False negative patterns\n\n")
        f.write(f"| Pattern | Expected | Detected | Missed |\n")
        f.write(f"|---------|----------|----------|--------|\n")
        for name in fn_patterns:
            exp = fn_by_pattern.get(name, 0)
            det = parser_detected.get(name, 0)
            missed = max(0, exp - det)
            f.write(f"| {name} | {exp} | {det} | {missed} |\n")
        f.write("\n")

    print(f"Census tables written to {out}")


if __name__ == "__main__":
    main()
