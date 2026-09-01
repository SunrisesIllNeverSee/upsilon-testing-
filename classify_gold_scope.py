"""Track B.4: Gold scope classification.

Gold and system output must share the same evaluable commitment scope.
For every candidate record, classify:

  GOLD_ELIGIBLE       — the record is in a commitment class that both
                        the gold annotation and the system's extractor
                        can produce.  These records CAN be scored.
  GOLD_NOT_IN_SCOPE   — the record is a valid commitment but outside
                        the system's scope (e.g., a covenant type the
                        extractor does not target).
  SYSTEM_UNSUPPORTED  — the system produces a commitment class that
                        gold does not cover (e.g., facility.* keys
                        when gold only annotates financial_covenant.*).
  GOLD_PENDING        — the record awaits human annotation.

This script compares:
  - The commitment keys the system's S0/GT extractors produce
  - The commitment IDs the automated proxy gold annotators produce
  - The commitment keys the semantic mapper targets

and classifies each candidate record.

Usage:
    python classify_gold_scope.py
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

HELD_OUT_MANIFEST = Path("data/held_out/manifest.json")
HELD_OUT_RESULTS = Path("results/held_out_study_results.json")
PREREG_MANIFEST = Path("data/held_out/gold/preregistration.json")
GOLD_DIR = Path("data/held_out/gold")
OUTPUT_PATH = Path("results/step_19b_gold_scope_classification.json")


def main() -> int:
    print("Track B.4: Gold scope classification")
    print("=" * 60)

    # 1. Collect all system-produced commitment keys
    from s0_extractor import extract_s0_state_for_chain
    from gt_extractor import extract_ground_truth_for_chain

    manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
    system_keys: dict[str, set[str]] = {"s0": set(), "gt": set(), "mapper_targets": set()}

    for c in manifest["chains"]:
        for doc in c["documents"]:
            if doc["role"] == "S0":
                result = extract_s0_state_for_chain(c["chain_id"], doc["text_path"])
                system_keys["s0"].update(result.commitments.keys())
            elif doc["role"] == "CMP":
                if Path(doc["text_path"]).exists():
                    result = extract_ground_truth_for_chain(c["chain_id"], doc["text_path"])
                    system_keys["gt"].update(result.commitments.keys())

    # Mapper target keys (from the defect analysis)
    defect_data = json.loads(Path("results/step_19b_mutation_defect_analysis.json").read_text())
    for m in defect_data["mutations"]:
        system_keys["mapper_targets"].add(m["semantic_mapping"]["target_key"])

    print(f"System S0 extractor keys: {sorted(system_keys['s0'])}")
    print(f"System GT extractor keys: {sorted(system_keys['gt'])}")
    print(f"Mapper target keys: {sorted(system_keys['mapper_targets'])}")

    # 2. Collect all gold-produced commitment IDs
    gold_ids: set[str] = set()
    gold_records_by_chain: dict[str, list] = {}
    prereg = json.loads(PREREG_MANIFEST.read_text(encoding="utf-8"))
    for gold_file_str in prereg["gold_files"]:
        gold_file = Path(gold_file_str)
        data = json.loads(gold_file.read_text(encoding="utf-8"))
        chain_id = data["chain_id"]
        records = data.get("records", [])
        gold_records_by_chain[chain_id] = records
        for r in records:
            gold_ids.add(r["commitment_id"])

    print(f"Gold commitment IDs: {sorted(gold_ids)}")

    # 3. Classify each candidate record
    all_candidate_keys = system_keys["s0"] | system_keys["gt"] | system_keys["mapper_targets"] | gold_ids

    classifications: list[dict] = []

    # System extractor keys (S0 + GT)
    system_extractor_keys = system_keys["s0"] | system_keys["gt"]

    for key in sorted(all_candidate_keys):
        in_s0 = key in system_keys["s0"]
        in_gt = key in system_keys["gt"]
        in_gold = key in gold_ids
        is_mapper_target = key in system_keys["mapper_targets"]

        # Classification logic:
        #
        # GOLD_ELIGIBLE: Both the system extractor AND the gold annotators
        #   can produce this key.  These records CAN be scored.
        #
        # GOLD_NOT_IN_SCOPE: The gold annotator produces this key but the
        #   system's extractor does not.  The system doesn't extract this
        #   commitment class, so it cannot be scored as a reconstruction
        #   error — it's a scope limitation.
        #
        # SYSTEM_UNSUPPORTED: The system's extractor produces this key but
        #   the gold annotator does not.  The gold doesn't cover this
        #   commitment class, so system output in this class cannot be
        #   verified against gold.
        #
        # GOLD_PENDING: The key is a mapper target that neither the
        #   extractor nor the gold annotator produces.  It awaits human
        #   review to determine if it should be in scope.

        if in_s0 or in_gt:
            if in_gold:
                classification = "GOLD_ELIGIBLE"
            else:
                classification = "SYSTEM_UNSUPPORTED"
        elif in_gold:
            classification = "GOLD_NOT_IN_SCOPE"
        elif is_mapper_target:
            classification = "GOLD_PENDING"
        else:
            classification = "GOLD_PENDING"

        classifications.append({
            "commitment_id": key,
            "classification": classification,
            "in_s0_extractor": in_s0,
            "in_gt_extractor": in_gt,
            "in_gold": in_gold,
            "is_mapper_target": is_mapper_target,
        })

    # Count classifications
    counts = {}
    for c in classifications:
        counts[c["classification"]] = counts.get(c["classification"], 0) + 1

    print()
    print("Classification summary:")
    for cls in ["GOLD_ELIGIBLE", "GOLD_NOT_IN_SCOPE", "SYSTEM_UNSUPPORTED", "GOLD_PENDING"]:
        print(f"  {cls}: {counts.get(cls, 0)}")

    # 4. Per-chain gold record classification
    per_chain: list[dict] = []
    for chain_id, records in gold_records_by_chain.items():
        chain_classes = []
        for r in records:
            cid = r["commitment_id"]
            cls = next((c for c in classifications if c["commitment_id"] == cid), None)
            chain_classes.append({
                "commitment_id": cid,
                "field": r["field"],
                "classification": cls["classification"] if cls else "GOLD_PENDING",
            })
        per_chain.append({
            "chain_id": chain_id,
            "total_records": len(records),
            "classifications": chain_classes,
        })

    output = {
        "analysis": "step_19b_gold_scope_classification",
        "analysis_timestamp": datetime.now(UTC).isoformat(),
        "frozen_system": "v1.0-frozen-operational-build",
        "system_extractor_keys": {
            "s0": sorted(system_keys["s0"]),
            "gt": sorted(system_keys["gt"]),
            "mapper_targets": sorted(system_keys["mapper_targets"]),
        },
        "gold_commitment_ids": sorted(gold_ids),
        "classification_counts": counts,
        "classifications": classifications,
        "per_chain": per_chain,
        "scoring_rule": (
            "Only GOLD_ELIGIBLE records (keys produced by BOTH the system "
            "extractor AND the gold annotator) can be scored as "
            "reconstruction errors.  GOLD_NOT_IN_SCOPE and "
            "SYSTEM_UNSUPPORTED records represent scope mismatches, not "
            "reconstruction errors.  GOLD_PENDING records await human "
            "review."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nOutput: {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
