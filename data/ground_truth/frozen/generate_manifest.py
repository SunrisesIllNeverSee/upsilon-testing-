"""Generate and verify the frozen ground-truth artifact manifest.

This script inventories the frozen reference-truth artifacts that are
currently embedded in runtime Python modules (``edgar_chains.py`` and
``semantic_gold.py``) and produces a machine-readable manifest with
SHA-256 hashes and provenance.

The report's key distinction:

- ``results/frozen/``  — outputs produced by runs (experimental evidence)
- ``data/ground_truth/frozen/`` — inputs / reference truth (frozen states,
  gold annotations, hand-extracted reference data)

Frozen ground-truth states are **inputs** to experiments, not outputs.
Coupling them to runtime Python modules means source refactoring and
experimental-data mutation are entangled in the same Git history.  This
manifest is the first step toward separating them: it records what exists,
where it lives now, where it should move, and hashes the source documents
so that future extraction can be verified against unchanged inputs.

## Freeze vs. verify (Step 23G.1)

This script supports two operations, kept strictly separate so that
**verification never mutates the frozen manifest**:

``freeze`` (default)
    Create or refresh ``manifest.json``.  If a manifest already exists,
    persisted ``created_at`` / ``frozen_at`` values are reused for every
    artifact that already appears in the manifest (matched by
    ``artifact_path`` for source documents, ``artifact_id`` for embedded
    states).  Only genuinely new artifacts receive fresh timestamps.
    ``generated_at`` is updated to the current time (manifest metadata,
    not artifact identity).

``verify``
    Load the existing manifest, recompute SHA-256 hashes for every source
    document, and compare against the stored values.  Report PASS/FAIL.
    **Does not write to ``manifest.json``.**  A non-authoritative
    ``verification_at`` timestamp appears only in the stdout report, never
    in the manifest itself.

Required principle::

    Verify(FrozenArtifact) must not mutate FrozenManifest

Running ``verify`` twice against unchanged inputs produces zero manifest
changes by construction — ``verify`` never writes.

Outputs (freeze mode only)::

    data/ground_truth/frozen/manifest.json

Run::

    python data/ground_truth/frozen/generate_manifest.py freeze
    python data/ground_truth/frozen/generate_manifest.py verify
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_DIR = REPO_ROOT / "data" / "ground_truth" / "frozen"
EDGAR_CHAINS_DIR = REPO_ROOT / "data" / "edgar_chains"
MANIFEST_PATH = FROZEN_DIR / "manifest.json"

# The producer commit is the Step 23G scaffold commit.  These frozen states
# were embedded in edgar_chains.py prior to this commit; the manifest records
# the commit at which the inventory was created.
PRODUCER_COMMIT = "fad715c"

# Source corpus version: the data/edgar_chains manifest version.
SOURCE_CORPUS_VERSION = "edgar_chains_v1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_size(path: Path) -> int:
    return path.stat().st_size


def _load_existing_manifest() -> dict | None:
    """Return the existing manifest dict, or ``None`` if it does not exist."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _existing_timestamps(
    existing: dict | None,
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Build lookup maps from an existing manifest for stable timestamps.

    Returns ``(source_ts, embedded_ts)`` where each map is keyed by the
    artifact identifier (``artifact_path`` for source documents,
    ``artifact_id`` for embedded states) and contains the persisted
    ``created_at`` and ``frozen_at`` values.
    """
    source_ts: dict[str, dict] = {}
    embedded_ts: dict[str, dict] = {}
    if existing is None:
        return source_ts, embedded_ts
    for entry in existing.get("source_documents", []):
        key = entry.get("artifact_path", "")
        if key:
            source_ts[key] = {
                "created_at": entry.get("created_at", ""),
                "frozen_at": entry.get("frozen_at", ""),
            }
    for entry in existing.get("embedded_states", []):
        key = entry.get("artifact_id", "")
        if key:
            embedded_ts[key] = {
                "created_at": entry.get("created_at", ""),
                "frozen_at": entry.get("frozen_at", ""),
            }
    return source_ts, embedded_ts


def _inventory_edgar_chain_sources(
    source_ts: dict[str, dict],
) -> list[dict]:
    """Inventory the source documents for the 3 EDGAR chains.

    ``created_at`` / ``frozen_at`` are reused from ``source_ts`` when the
    artifact already appears in the existing manifest.  New artifacts
    receive fresh timestamps.
    """
    entries = []
    if not EDGAR_CHAINS_DIR.exists():
        return entries

    # Read the existing data/edgar_chains/manifest.json for URL provenance
    existing_manifest_path = EDGAR_CHAINS_DIR / "manifest.json"
    url_map: dict[str, str] = {}
    if existing_manifest_path.exists():
        for entry in json.loads(existing_manifest_path.read_text(encoding="utf-8")):
            key = f"{entry['chain']}/{entry['doc_id']}"
            url_map[key] = entry.get("url", "")

    now = datetime.now(UTC).isoformat()

    for chain_dir in sorted(EDGAR_CHAINS_DIR.iterdir()):
        if not chain_dir.is_dir():
            continue
        chain_name = chain_dir.name
        for txt_file in sorted(chain_dir.glob("*.txt")):
            doc_id = txt_file.stem
            url = url_map.get(f"{chain_name}/{doc_id}", "")
            artifact_path = str(txt_file.relative_to(REPO_ROOT))
            ts = source_ts.get(artifact_path, {})
            created_at = ts.get("created_at", now)
            frozen_at = ts.get("frozen_at", now)
            entries.append({
                "artifact_path": artifact_path,
                "sha256": _sha256(txt_file),
                "artifact_type": "edgar_source_document",
                "producer": "SEC EDGAR acquisition (sec_ingest.py)",
                "producer_commit": PRODUCER_COMMIT,
                "source_corpus_version": SOURCE_CORPUS_VERSION,
                "created_at": created_at,
                "frozen_at": frozen_at,
                "supersedes": "",
                "superseded_by": "",
                "mutable": False,
                "chain": chain_name,
                "doc_id": doc_id,
                "url": url,
                "file_size_bytes": _file_size(txt_file),
            })
    return entries


def _inventory_embedded_states(
    embedded_ts: dict[str, dict],
) -> list[dict]:
    """Record the frozen states currently embedded in runtime Python modules.

    These are not yet externalized to data files.  The manifest records their
    existence, the module they are embedded in, and the source documents they
    were extracted from.  Externalization is a Phase 2 precondition for
    moving edgar_chains.py.

    ``created_at`` / ``frozen_at`` are reused from ``embedded_ts`` when the
    artifact already appears in the existing manifest.
    """
    semantic_gold_path = REPO_ROOT / "tests" / "corpus" / "semantic_gold.py"

    now = datetime.now(UTC).isoformat()
    embedded = []

    # EDGAR chain ground-truth states (3 chains)
    chains = [
        {
            "artifact_id": "edgar_chain_state_ameresco",
            "chain": "ameresco",
            "embedded_in": "edgar_chains.py::chain_ameresco",
            "ground_truth_label": "Manually extracted from final amendment state (A3 = Amendment No. 6, June 28, 2024)",
            "source_documents": [
                "data/edgar_chains/ameresco/S0_fifth_AR_2022.txt",
                "data/edgar_chains/ameresco/A1_amend_2023_08.txt",
                "data/edgar_chains/ameresco/A2_amend_2023_12.txt",
                "data/edgar_chains/ameresco/A3_sixth_amend_2024.txt",
            ],
            "comparison_at": "2024-06-28T00:00:00",
        },
        {
            "artifact_id": "edgar_chain_state_amedisys",
            "chain": "amedisys",
            "embedded_in": "edgar_chains.py::chain_amedisys",
            "ground_truth_label": "Hand-extracted from A2 Annex A composite (independently filed full restated credit agreement)",
            "source_documents": [
                "data/edgar_chains/amedisys/S0_AR_2018.txt",
                "data/edgar_chains/amedisys/A1_first_amend_2019.txt",
                "data/edgar_chains/amedisys/A2_second_amend_2021.txt",
            ],
            "comparison_at": "2021-07-30T00:00:00",
        },
        {
            "artifact_id": "edgar_chain_state_bausch_lomb",
            "chain": "bausch_lomb",
            "embedded_in": "edgar_chains.py::chain_bausch_lomb",
            "ground_truth_label": "Hand-extracted from A4 Annex A conformed copy (independently filed full restated credit agreement)",
            "source_documents": [
                "data/edgar_chains/bausch_lomb/S0_credit_agreement_2022.txt",
                "data/edgar_chains/bausch_lomb/A1_first_incremental_2023.txt",
                "data/edgar_chains/bausch_lomb/A2_second_incremental_2024.txt",
                "data/edgar_chains/bausch_lomb/A3_third_amend_2025.txt",
                "data/edgar_chains/bausch_lomb/A4_fourth_amend_2026.txt",
            ],
            "comparison_at": "2026-01-02T00:00:00",
        },
    ]

    for c in chains:
        # Hash the source documents so the manifest can verify inputs unchanged
        source_hashes = []
        for src_path in c["source_documents"]:
            full = REPO_ROOT / src_path
            if full.exists():
                source_hashes.append({
                    "path": src_path,
                    "sha256": _sha256(full),
                })
        ts = embedded_ts.get(c["artifact_id"], {})
        created_at = ts.get("created_at", now)
        frozen_at = ts.get("frozen_at", now)
        embedded.append({
            "artifact_id": c["artifact_id"],
            "artifact_path": c["embedded_in"],  # current location (in-code)
            "target_path": f"data/ground_truth/frozen/edgar_chain_states/{c['artifact_id']}.json",
            "sha256": "",  # not yet externalized; hash applies once extracted
            "artifact_type": "edgar_chain_ground_truth_state",
            "producer": "manual extraction from SEC EDGAR filings",
            "producer_commit": PRODUCER_COMMIT,
            "source_corpus_version": SOURCE_CORPUS_VERSION,
            "created_at": created_at,
            "frozen_at": frozen_at,
            "supersedes": "",
            "superseded_by": "",
            "mutable": False,
            "chain": c["chain"],
            "ground_truth_label": c["ground_truth_label"],
            "comparison_at": c["comparison_at"],
            "source_documents": source_hashes,
            "externalization_status": "embedded_in_runtime_module",
            "externalization_precondition": (
                "Must be extracted to JSON before edgar_chains.py can be "
                "moved.  See migration preconditions in "
                "docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md."
            ),
        })

    # Semantic gold mappings (semantic_gold.py)
    if semantic_gold_path.exists():
        artifact_id = "semantic_gold_mappings"
        ts = embedded_ts.get(artifact_id, {})
        created_at = ts.get("created_at", now)
        frozen_at = ts.get("frozen_at", now)
        embedded.append({
            "artifact_id": artifact_id,
            "artifact_path": "semantic_gold.py",
            "target_path": "data/ground_truth/frozen/semantic_gold/semantic_gold_mappings.json",
            "sha256": "",
            "artifact_type": "semantic_gold_mapping",
            "producer": "manual annotation",
            "producer_commit": PRODUCER_COMMIT,
            "source_corpus_version": SOURCE_CORPUS_VERSION,
            "created_at": created_at,
            "frozen_at": frozen_at,
            "supersedes": "",
            "superseded_by": "",
            "mutable": False,
            "chain": "ameresco, amedisys, bausch_lomb",
            "ground_truth_label": "Gold semantic mappings for 3 EDGAR chains",
            "comparison_at": "",
            "source_documents": [],
            "externalization_status": "embedded_in_runtime_module",
            "externalization_precondition": (
                "Must be extracted to JSON before semantic_gold.py can be "
                "moved to tests/corpus/."
            ),
        })

    return embedded


# ---------------------------------------------------------------------------
# freeze
# ---------------------------------------------------------------------------


def freeze() -> int:
    """Create or refresh ``manifest.json``.

    If a manifest already exists, persisted ``created_at`` / ``frozen_at``
    values are reused for every artifact that already appears in the
    manifest.  Only genuinely new artifacts receive fresh timestamps.
    """
    existing = _load_existing_manifest()
    source_ts, embedded_ts = _existing_timestamps(existing)

    source_docs = _inventory_edgar_chain_sources(source_ts)
    embedded_states = _inventory_embedded_states(embedded_ts)

    manifest = {
        "manifest_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "description": (
            "Frozen ground-truth artifact inventory.  These are inputs / "
            "reference truth, not outputs.  See "
            "docs/methodology/FROZEN_ARTIFACT_POLICY.md for the distinction "
            "between results/frozen/ (outputs) and data/ground_truth/frozen/ "
            "(inputs)."
        ),
        "schema": {
            "artifact_path": "current location of the artifact",
            "target_path": "future location once externalized",
            "sha256": "SHA-256 hash of the externalized artifact (empty if not yet externalized)",
            "artifact_type": "edgar_source_document | edgar_chain_ground_truth_state | semantic_gold_mapping",
            "producer": "what produced the artifact",
            "producer_commit": "git commit at which the artifact was frozen",
            "source_corpus_version": "version of the source corpus",
            "created_at": "ISO timestamp when the artifact was created (stable; reuse on re-freeze)",
            "frozen_at": "ISO timestamp when the artifact was frozen (stable; reuse on re-freeze)",
            "supersedes": "artifact_id this artifact supersedes (if any)",
            "superseded_by": "artifact_id that supersedes this artifact (if any)",
            "mutable": "false for all frozen artifacts",
        },
        "source_documents": source_docs,
        "embedded_states": embedded_states,
        "counts": {
            "source_documents": len(source_docs),
            "embedded_states": len(embedded_states),
            "externalized": sum(1 for e in embedded_states if e["externalization_status"] == "externalized"),
            "still_embedded": sum(1 for e in embedded_states if e["externalization_status"] == "embedded_in_runtime_module"),
        },
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    print(f"  source documents: {len(source_docs)}")
    print(f"  embedded states:  {len(embedded_states)}")
    print(f"  still embedded:   {manifest['counts']['still_embedded']}")
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def verify() -> int:
    """Verify the existing manifest without mutating it.

    Recomputes SHA-256 hashes for every source document and compares
    against the stored values.  Reports PASS/FAIL.  **Does not write to
    ``manifest.json``.**
    """
    existing = _load_existing_manifest()
    if existing is None:
        print(f"FAIL: manifest not found at {MANIFEST_PATH.relative_to(REPO_ROOT)}")
        return 1

    verification_at = datetime.now(UTC).isoformat()
    failures: list[str] = []
    checked = 0

    # Verify source document hashes
    for entry in existing.get("source_documents", []):
        artifact_path = entry.get("artifact_path", "")
        stored_hash = entry.get("sha256", "")
        full = REPO_ROOT / artifact_path
        if not full.exists():
            failures.append(f"MISSING: {artifact_path}")
            continue
        actual_hash = _sha256(full)
        checked += 1
        if actual_hash != stored_hash:
            failures.append(
                f"HASH MISMATCH: {artifact_path}\n"
                f"  manifest: {stored_hash}\n"
                f"  actual:   {actual_hash}"
            )

    # Verify embedded state source document hashes
    for entry in existing.get("embedded_states", []):
        for src in entry.get("source_documents", []):
            src_path = src.get("path", "")
            stored_hash = src.get("sha256", "")
            full = REPO_ROOT / src_path
            if not full.exists():
                failures.append(f"MISSING (embedded source): {src_path}")
                continue
            actual_hash = _sha256(full)
            checked += 1
            if actual_hash != stored_hash:
                failures.append(
                    f"HASH MISMATCH (embedded source): {src_path}\n"
                    f"  manifest: {stored_hash}\n"
                    f"  actual:   {actual_hash}"
                )

    # Verify mutability invariant
    all_artifacts = (
        existing.get("source_documents", [])
        + existing.get("embedded_states", [])
    )
    for entry in all_artifacts:
        if entry.get("mutable") is not False:
            failures.append(
                f"MUTABLE: {entry.get('artifact_path', entry.get('artifact_id', '?'))}"
            )

    print(f"verification_at: {verification_at}")
    print(f"hashes checked:   {checked}")
    print(f"failures:         {len(failures)}")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        print("\nVERIFY: FAIL")
        return 1
    print("\nVERIFY: PASS")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "freeze"
    if mode == "freeze":
        return freeze()
    if mode == "verify":
        return verify()
    print(f"unknown mode: {mode!r} (expected 'freeze' or 'verify')", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
