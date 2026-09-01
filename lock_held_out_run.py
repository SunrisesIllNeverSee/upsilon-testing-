"""Track B.1: Lock the current held-out run as immutable.

Preserves:
  - raw frozen-system predictions (held_out_study_results.json)
  - chain manifests (data/held_out/manifest.json)
  - document hashes (already in manifest)
  - run records
  - automated proxy annotations (data/held_out/gold/)
  - current provisional report (step_19b_held_out_confirmatory_study.md)
  - mutation defect analysis (step_19b_mutation_defect_analysis.json)

Computes SHA-256 hashes of all artifacts and writes an immutable run
record that can be verified later to detect any tampering.

Usage:
    python lock_held_out_run.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

# Artifacts to lock
ARTIFACTS = [
    Path("results/held_out_study_results.json"),
    Path("data/held_out/manifest.json"),
    Path("data/held_out/gold/preregistration.json"),
    Path("data/held_out/gold/GOLD_ANNOTATION_PROTOCOL.md"),
    Path("data/held_out/gold/HELD-001_gold.json"),
    Path("data/held_out/gold/HELD-002_gold.json"),
    Path("data/held_out/gold/HELD-004_gold.json"),
    Path("data/held_out/gold/HELD-005_gold.json"),
    Path("data/held_out/gold/HELD-008_gold.json"),
    Path("results/step_19b_held_out_confirmatory_study.md"),
    Path("results/step_19b_mutation_defect_analysis.json"),
]

# Also lock all 25 chain document directories
HELD_OUT_DATA = Path("data/held_out")
LOCK_RECORD_PATH = Path("results/step_19b_held_out_run_lock.json")


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_chain_document_hashes() -> list[dict]:
    """Collect SHA-256 hashes of all held-out chain documents."""
    docs = []
    for chain_dir in sorted(HELD_OUT_DATA.iterdir()):
        if not chain_dir.is_dir() or not chain_dir.name.startswith("HELD-"):
            continue
        for f in sorted(chain_dir.iterdir()):
            if f.is_file() and f.suffix in (".html", ".txt"):
                docs.append({
                    "file": str(f),
                    "sha256": sha256_file(f),
                    "bytes": f.stat().st_size,
                })
    return docs


def main() -> int:
    print("Track B.1: Locking held-out run as immutable")
    print("=" * 60)

    artifact_hashes = {}
    for path in ARTIFACTS:
        if not path.exists():
            print(f"  WARNING: {path} does not exist, skipping")
            continue
        h = sha256_file(path)
        artifact_hashes[str(path)] = h
        print(f"  {path}: {h[:16]}...")

    print()
    print("Hashing chain documents...")
    doc_hashes = collect_chain_document_hashes()
    print(f"  {len(doc_hashes)} documents hashed")

    # Compute aggregate hash over all artifact hashes
    all_hash_str = json.dumps(artifact_hashes, sort_keys=True)
    aggregate_hash = hashlib.sha256(all_hash_str.encode("utf-8")).hexdigest()

    lock_record = {
        "lock_type": "held_out_run_immutable_lock",
        "locked_at_utc": datetime.now(UTC).isoformat(),
        "frozen_system": "v1.0-frozen-operational-build",
        "lock_purpose": (
            "Preserve the held-out confirmatory study run as immutable. "
            "Any modification to the locked artifacts will be detectable "
            "by recomputing and comparing hashes.  This lock enables "
            "future confirmatory scoring against human gold without "
            "re-running or altering the frozen system's predictions."
        ),
        "aggregate_hash": aggregate_hash,
        "artifact_hashes": artifact_hashes,
        "chain_document_hashes": doc_hashes,
        "chain_document_count": len(doc_hashes),
        "lock_invariants": [
            "Frozen system code (v1.0-frozen-operational-build) is not modified.",
            "Held-out predictions are not re-run.",
            "No tuning against held-out data.",
            "Automated proxy annotations are NOT human gold.",
            "Provisional held-out metrics are NOT confirmatory evidence.",
        ],
    }

    LOCK_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_RECORD_PATH.write_text(json.dumps(lock_record, indent=2), encoding="utf-8")
    print()
    print(f"Lock record: {LOCK_RECORD_PATH}")
    print(f"Aggregate hash: {aggregate_hash}")
    print(f"Artifacts locked: {len(artifact_hashes)}")
    print(f"Documents locked: {len(doc_hashes)}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
