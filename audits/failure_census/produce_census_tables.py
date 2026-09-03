"""Produce Table 1 (Corpus structure) and Table 2 (Parser performance by
format) from the 25-document parser-development sample.

Generates two versioned reports:
  - research/DEVELOPMENT_CENSUS_v0.3.1.md  (v0.3.1 baseline)
  - research/DEVELOPMENT_CENSUS_v0.4.md    (v0.4 comparison)

Table 1 — Corpus structure:
  Format | Documents | %

Table 2 — Parser performance by format:
  Format | Precision | Recall | F1 | Unresolved | Docs

Precision = TP / (TP + FP)
Recall = TP / (TP + FN)
F1 = 2 * P * R / (P + R)

Where TP, FP, FN are computed from explicit gold annotations
(data/development/gold_annotations.json), NOT from overlapping regex counts
or parser version differences.

NOTE: This is a 25-document parser-development sample (one document per
issuer), NOT the 25-issuer agreement-chain corpus that the reconstruction
study ultimately requires.
"""
from __future__ import annotations
import csv, json
from pathlib import Path

from upsilon.parsing.amendment_parser import parse_v03, parse_v04
from data.classify_development_corpus import (
    match_instructions_to_gold, compute_metrics, load_gold_annotations,
)

FORMAT_NAMES = {
    "A": "Inline amendment",
    "B": "Composite",
    "C": "Amended/restated",
    "D": "Redline",
    "E": "Referential",
    "F": "Waiver",
    "G": "Mixed",
}

TABLE2_FORMATS = ["Inline", "Composite", "Restated", "Referential", "Waiver", "Mixed"]

FORMAT_TO_TABLE2 = {
    "A": "Inline",
    "B": "Composite",
    "C": "Restated",
    "D": "Composite",
    "E": "Referential",
    "F": "Waiver",
    "G": "Mixed",
}


def _compute_parser_metrics(results, gold_data, parser_fn, parser_label):
    """Compute TP/FP/FN per format and pooled for a given parser function."""
    format_stats = {}
    pooled = {"tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0, "detected": 0, "gold": 0}

    for r in results:
        case_id = r["case_id"]
        fmt = r["document_format"]
        table2_fmt = FORMAT_TO_TABLE2.get(fmt, "Inline")

        if table2_fmt not in format_stats:
            format_stats[table2_fmt] = {
                "tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0, "detected": 0, "gold": 0
            }
        stats = format_stats[table2_fmt]
        stats["docs"] += 1
        pooled["docs"] += 1

        text = Path(f"data/development/{case_id}/source.txt").read_text()
        result = parser_fn(text)
        gold = gold_data.get(case_id, {"expected": []}).get("expected", [])

        tp, fp, fn, _sem = match_instructions_to_gold(result["instructions"], gold)
        unresolved = sum(1 for i in result["instructions"] if i["instruction_type"] == "UNRESOLVED")
        detected = len(result["instructions"])

        stats["tp"] += tp
        stats["fp"] += fp
        stats["fn"] += fn
        stats["unresolved"] += unresolved
        stats["detected"] += detected
        stats["gold"] += len(gold)

        pooled["tp"] += tp
        pooled["fp"] += fp
        pooled["fn"] += fn
        pooled["unresolved"] += unresolved
        pooled["detected"] += detected
        pooled["gold"] += len(gold)

    return format_stats, pooled


def _write_report(path, title, parser_label, tag, results, format_counts, total_docs,
                  format_stats, pooled, gold_total):
    """Write a census report to a markdown file."""
    with open(path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Parser:** {parser_label} (tag: {tag})\n")
        f.write(f"**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)\n")
        f.write(f"**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain\n")
        f.write(f"corpus (original + multiple amendments per issuer) that the reconstruction\n")
        f.write(f"study ultimately requires.\n")
        f.write(f"**Gold annotations:** data/development/gold_annotations.json ({gold_total} total)\n")
        f.write(f"**Methodology:** TP/FP/FN computed from explicit gold annotations.\n")
        f.write(f"Precision = TP / (TP + FP), Recall = TP / (TP + FN), F1 = 2PR / (P + R).\n")
        f.write(f"**Metric type:** Instruction DETECTION. Matching uses span overlap +\n")
        f.write(f"instruction_type (with key-based fallback for gold without spans). Does\n")
        f.write(f"NOT verify extracted old_value, new_value, amount, exception, or actual\n")
        f.write(f"semantic mutation correctness. Full reconstruction accuracy is a separate\n")
        f.write(f"measurement.\n\n")

        # Table 1
        f.write("## Table 1 — Corpus structure\n\n")
        f.write("| Format | Documents | % |\n")
        f.write("|--------|----------|---|\n")
        table1_order = ["A", "B", "C", "D", "E", "F", "G"]
        for fmt in table1_order:
            count = format_counts.get(fmt, 0)
            pct = 100 * count / total_docs if total_docs > 0 else 0
            name = FORMAT_NAMES.get(fmt, fmt)
            f.write(f"| {name} | {count} | {pct:.1f}% |\n")
        f.write(f"| **Total** | **{total_docs}** | **100.0%** |\n\n")

        # Table 2
        f.write("## Table 2 — Instruction-detection performance by format\n\n")
        f.write("| Format | Precision | Recall | F1 | Unresolved | Docs |\n")
        f.write("|--------|-----------|--------|----|------------|------|\n")
        for fmt_name in TABLE2_FORMATS:
            stats = format_stats.get(fmt_name, {"tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0})
            tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
            unresolved, docs = stats["unresolved"], stats["docs"]
            if docs == 0:
                f.write(f"| {fmt_name} | N/A | N/A | N/A | {unresolved} | {docs} |\n")
            else:
                p, r, f1 = compute_metrics(tp, fp, fn)
                f.write(f"| {fmt_name} | {p:.3f} | {r:.3f} | {f1:.3f} | {unresolved} | {docs} |\n")
        total_p, total_r, total_f1 = compute_metrics(pooled["tp"], pooled["fp"], pooled["fn"])
        f.write(f"| **All amendment documents** | **{total_p:.3f}** | **{total_r:.3f}** | **{total_f1:.3f}** | **{pooled['unresolved']}** | **{total_docs}** |\n\n")

        # Summary
        f.write("## Pooled summary\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Gold annotations | {gold_total} |\n")
        f.write(f"| Detected | {pooled['detected']} |\n")
        f.write(f"| True positives | {pooled['tp']} |\n")
        f.write(f"| False positives | {pooled['fp']} |\n")
        f.write(f"| False negatives | {pooled['fn']} |\n")
        f.write(f"| Precision | {total_p:.3f} |\n")
        f.write(f"| Recall | {total_r:.3f} |\n")
        f.write(f"| F1 | {total_f1:.3f} |\n")
        f.write(f"| Unresolved | {pooled['unresolved']} |\n\n")


def main():
    # Load classification results
    results = []
    with open("development_corpus.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    gold_data = load_gold_annotations()
    gold_total = sum(
        len(gold_data.get(r["case_id"], {"expected": []}).get("expected", []))
        for r in results
    )

    # Table 1: Corpus structure
    format_counts = {}
    for r in results:
        fmt = r["document_format"]
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    total_docs = len(results)

    # Compute metrics for v0.3.1 baseline
    v03_format_stats, v03_pooled = _compute_parser_metrics(
        results, gold_data, parse_v03, "v0.3.1"
    )

    # Compute metrics for v0.4
    v04_format_stats, v04_pooled = _compute_parser_metrics(
        results, gold_data, parse_v04, "v0.4"
    )

    # Print console output
    print("=" * 60)
    print("Table 1 — Corpus structure")
    print("=" * 60)
    print(f"{'Format':<25} {'Documents':>10} {'%':>8}")
    print("-" * 60)
    for fmt in ["A", "B", "C", "D", "E", "F", "G"]:
        count = format_counts.get(fmt, 0)
        pct = 100 * count / total_docs if total_docs > 0 else 0
        name = FORMAT_NAMES.get(fmt, fmt)
        print(f"{name:<25} {count:>10} {pct:>7.1f}%")
    print("-" * 60)
    print(f"{'Total':<25} {total_docs:>10} {100.0:>7.1f}%")

    for label, format_stats, pooled in [
        ("v0.3.1 baseline", v03_format_stats, v03_pooled),
        ("v0.4", v04_format_stats, v04_pooled),
    ]:
        print()
        print("=" * 60)
        print(f"Table 2 — {label} instruction-detection by format")
        print("=" * 60)
        print(f"{'Format':<30} {'Precision':>10} {'Recall':>10} {'F1':>8} {'Unr':>6} {'Docs':>6}")
        print("-" * 60)
        for fmt_name in TABLE2_FORMATS:
            stats = format_stats.get(fmt_name, {"tp": 0, "fp": 0, "fn": 0, "unresolved": 0, "docs": 0})
            tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
            unresolved, docs = stats["unresolved"], stats["docs"]
            if docs == 0:
                print(f"{fmt_name:<30} {'N/A':>10} {'N/A':>10} {'N/A':>8} {unresolved:>6} {docs:>6}")
            else:
                p, r, f1 = compute_metrics(tp, fp, fn)
                print(f"{fmt_name:<30} {p:>10.3f} {r:>10.3f} {f1:>8.3f} {unresolved:>6} {docs:>6}")
        print("-" * 60)
        total_p, total_r, total_f1 = compute_metrics(pooled["tp"], pooled["fp"], pooled["fn"])
        print(f"{'All amendment documents':<30} {total_p:>10.3f} {total_r:>10.3f} {total_f1:>8.3f} {pooled['unresolved']:>6} {total_docs:>6}")

    # Write versioned reports
    baseline_path = Path("research/DEVELOPMENT_CENSUS_v0.3.1.md")
    _write_report(
        baseline_path,
        "Parser-Development Sample Census — v0.3.1 Baseline",
        "v0.3.1 (deterministic_baseline_v0.3)",
        "dev-baseline-v0.3.1",
        results, format_counts, total_docs,
        v03_format_stats, v03_pooled, gold_total,
    )
    print(f"\nBaseline census written to {baseline_path}")

    v04_path = Path("research/DEVELOPMENT_CENSUS_v0.4.md")
    _write_report(
        v04_path,
        "Parser-Development Sample Census — v0.4",
        "v0.4 (deterministic_baseline_v0.4)",
        "v0.4",
        results, format_counts, total_docs,
        v04_format_stats, v04_pooled, gold_total,
    )
    print(f"v0.4 census written to {v04_path}")

    # Write comparison report
    comparison_path = Path("research/DEVELOPMENT_CENSUS_comparison.md")
    with open(comparison_path, "w") as f:
        f.write("# Parser-Development Sample Census — v0.3.1 vs v0.4 Comparison\n\n")
        f.write(f"**Sample:** 25-document parser-development sample (DEV-001 through DEV-025)\n")
        f.write(f"**Note:** This is one document per issuer, NOT the 25-issuer agreement-chain\n")
        f.write(f"corpus that the reconstruction study ultimately requires.\n")
        f.write(f"**Gold annotations:** {gold_total} total\n")
        f.write(f"**Metric type:** Instruction DETECTION. Matching uses span overlap +\n")
        f.write(f"instruction_type (with key-based fallback for gold without spans). Does NOT\n")
        f.write(f"verify extracted old_value, new_value, amount, exception, or actual semantic\n")
        f.write(f"mutation correctness.\n\n")

        f.write("## Pooled instruction-detection metrics comparison\n\n")
        f.write("| Metric | v0.3.1 | v0.4 |\n")
        f.write("|--------|--------|------|\n")
        v03_p, v03_r, v03_f1 = compute_metrics(v03_pooled["tp"], v03_pooled["fp"], v03_pooled["fn"])
        v04_p, v04_r, v04_f1 = compute_metrics(v04_pooled["tp"], v04_pooled["fp"], v04_pooled["fn"])
        f.write(f"| Gold annotations | {gold_total} | {gold_total} |\n")
        f.write(f"| Detected | {v03_pooled['detected']} | {v04_pooled['detected']} |\n")
        f.write(f"| True positives | {v03_pooled['tp']} | {v04_pooled['tp']} |\n")
        f.write(f"| False positives | {v03_pooled['fp']} | {v04_pooled['fp']} |\n")
        f.write(f"| False negatives | {v03_pooled['fn']} | {v04_pooled['fn']} |\n")
        f.write(f"| Precision | {v03_p:.3f} | {v04_p:.3f} |\n")
        f.write(f"| Recall | {v03_r:.3f} | {v04_r:.3f} |\n")
        f.write(f"| F1 | {v03_f1:.3f} | {v04_f1:.3f} |\n")
        f.write(f"| Unresolved | {v03_pooled['unresolved']} | {v04_pooled['unresolved']} |\n\n")

        f.write("## Key findings\n\n")
        recall_gain = v04_r - v03_r
        precision_delta = v04_p - v03_p
        f.write(f"- Recall improved from {v03_r:.3f} to {v04_r:.3f} (+{recall_gain:.3f})\n")
        f.write(f"- Precision changed from {v03_p:.3f} to {v04_p:.3f} ({precision_delta:+.3f})\n")
        f.write(f"- F1 improved from {v03_f1:.3f} to {v04_f1:.3f}\n")
        f.write(f"- False positives: {v03_pooled['fp']} → {v04_pooled['fp']}\n")
        f.write(f"- False negatives: {v03_pooled['fn']} → {v04_pooled['fn']}\n")
    print(f"Comparison report written to {comparison_path}")


if __name__ == "__main__":
    main()
