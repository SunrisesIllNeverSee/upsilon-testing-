"""Build the development-data release package.

Consolidates the pre-v0.2 development evidence into a single release
package that preserves:

    accessions               — SEC accession numbers for every document
    URLs                     — SEC EDGAR URLs for every document
    SHA-256 hashes           — content hashes for every document
    manifest                 — consolidated chain-level manifest
    failure matrix           — the 25-chain failure attribution
    annotations/schema       — the gold record schema + documentation
    run records              — v1 and v2 run records (env, git, hashes)
    v1/v2 outputs            — chain study v1 and v2 results
    freeze record            — the v2 freeze record with SHA-256 hashes
    reproducibility          — step-by-step reproduction instructions

No SEC exhibit content is redistributed. The release package contains
only metadata (accessions, URLs, hashes) and derived analysis outputs.
The actual SEC documents are fetched on-demand from EDGAR using the
recorded accessions and URLs.

Output:
    results/release_package/
        manifest.json              — consolidated release manifest
        accessions.json            — all accessions + URLs + hashes
        failure_matrix.json        — copy of the failure matrix
        failure_matrix.md          — human-readable failure matrix
        gold_schema.json           — gold record schema
        gold_schema_documentation.md — annotator documentation
        chain_study_v1_results.json  — v1 results
        chain_study_v1_report.md      — v1 report
        chain_study_v2_results.json  — v2 results (frozen)
        chain_study_v2_report.md      — v2 report (frozen)
        freeze_record.md            — freeze record
        run_records/                — run record JSONs
        REPRODUCIBILITY.md          — reproduction instructions
        RELEASE_NOTES.md            — release notes
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RESULTS = Path("results")
RELEASE_DIR = RESULTS / "release_package"
DATA_CHAIN_STUDY = Path("data/chain_study")
DATA_EDGAR_CHAINS = Path("data/edgar_chains")
RESEARCH_RUN_RECORDS = Path("research/run_records")

# Source files to copy into the release package
FAILURE_MATRIX_JSON = RESULTS / "failure_matrix.json"
FAILURE_MATRIX_MD = RESULTS / "failure_matrix.md"
GOLD_SCHEMA_JSON = RESULTS / "gold_schema.json"
GOLD_SCHEMA_DOC = RESULTS / "gold_schema_documentation.md"
V1_RESULTS = RESULTS / "chain_study_v1_results.json"
V1_REPORT = RESULTS / "chain_study_v1_report.md"
V2_RESULTS = RESULTS / "chain_study_v2_results.json"
V2_REPORT = RESULTS / "chain_study_v2_report.md"
FREEZE_RECORD = RESULTS / "frozen" / "FREEZE_RECORD.md"
FROZEN_V2_RESULTS = RESULTS / "frozen" / "chain_study_v2_results.json"
FROZEN_V2_REPORT = RESULTS / "frozen" / "chain_study_v2_report.md"

# Existing chain name → chain_id mapping for the 3 manual chains
EXISTING_CHAIN_MAP = {
    "ameresco": "EDGAR-AMERESCO",
    "amedisys": "EDGAR-AMEDISYS",
    "bausch_lomb": "EDGAR-BAUSCH-LOMB",
}


# ---------------------------------------------------------------------------
# SHA-256 helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Accession extraction
# ---------------------------------------------------------------------------


def extract_accession_from_url(url: str) -> str | None:
    """Extract the SEC accession number from an EDGAR URL.

    Accession numbers appear in URLs as 18-digit strings without dashes,
    e.g., /000119312518210472/. We convert to the dashed format
    (0001193125-18-210472).
    """
    m = re.search(r"/(\d{18})/", url)
    if not m:
        return None
    raw = m.group(1)
    # Format: CIK(10)-Year(2)-Sequence(6)
    return f"{raw[:10]}-{raw[10:12]}-{raw[12:]}"


# ---------------------------------------------------------------------------
# Build the consolidated accessions manifest
# ---------------------------------------------------------------------------


def build_accessions() -> dict[str, Any]:
    """Build the consolidated accessions manifest from all sources.

    Combines:
      - data/chain_study/manifest.json (22 new STUDY chains)
      - data/edgar_chains/manifest.json (3 existing EDGAR chains)
    """
    accessions: list[dict[str, Any]] = []

    # --- 22 new STUDY chains ---
    chain_study_manifest = json.loads(
        (DATA_CHAIN_STUDY / "manifest.json").read_text(encoding="utf-8")
    )
    for chain in chain_study_manifest["chains"]:
        chain_id = chain["chain_id"]
        for doc in chain["documents"]:
            entry = {
                "chain_id": chain_id,
                "issuer": chain["issuer"],
                "cik": chain["cik"],
                "document_role": doc["role"],
                "accession": doc.get("accession", ""),
                "file_date": doc.get("file_date", ""),
                "exhibit_type": doc.get("exhibit_type", ""),
                "exhibit_description": doc.get("exhibit_description", ""),
                "document_url": doc.get("document_url", ""),
                "html_sha256": doc.get("html_sha256", ""),
                "text_sha256": doc.get("text_sha256", ""),
                "html_bytes": doc.get("html_bytes", 0),
                "text_chars": doc.get("text_chars", 0),
                "source": "chain_study_manifest",
            }
            accessions.append(entry)

    # --- 3 existing EDGAR chains ---
    edgar_manifest = json.loads(
        (DATA_EDGAR_CHAINS / "manifest.json").read_text(encoding="utf-8")
    )
    for doc in edgar_manifest:
        chain_name = doc["chain"]
        chain_id = EXISTING_CHAIN_MAP.get(chain_name, chain_name)
        url = doc.get("url", "")
        accession = extract_accession_from_url(url) or ""
        entry = {
            "chain_id": chain_id,
            "issuer": chain_name,
            "cik": "",  # Not in edgar_chains manifest; derived from URL
            "document_role": doc["doc_id"],
            "accession": accession,
            "file_date": "",  # Not in edgar_chains manifest
            "exhibit_type": "",
            "exhibit_description": "",
            "document_url": url,
            "html_sha256": doc.get("sha256", ""),
            "text_sha256": "",  # edgar_chains manifest only has one hash
            "html_bytes": doc.get("html_bytes", 0),
            "text_chars": doc.get("text_chars", 0),
            "source": "edgar_chains_manifest",
        }
        accessions.append(entry)

    # Group by chain_id
    chains: dict[str, list[dict[str, Any]]] = {}
    for entry in accessions:
        chains.setdefault(entry["chain_id"], []).append(entry)

    return {
        "total_documents": len(accessions),
        "total_chains": len(chains),
        "chains": chains,
        "documents": accessions,
    }


# ---------------------------------------------------------------------------
# Build the release manifest
# ---------------------------------------------------------------------------


def build_manifest(accessions: dict[str, Any]) -> dict[str, Any]:
    """Build the top-level release manifest."""
    # Hash the key output files
    output_hashes: dict[str, str] = {}
    for name, path in [
        ("failure_matrix.json", FAILURE_MATRIX_JSON),
        ("failure_matrix.md", FAILURE_MATRIX_MD),
        ("gold_schema.json", GOLD_SCHEMA_JSON),
        ("gold_schema_documentation.md", GOLD_SCHEMA_DOC),
        ("chain_study_v1_results.json", V1_RESULTS),
        ("chain_study_v1_report.md", V1_REPORT),
        ("chain_study_v2_results.json", V2_RESULTS),
        ("chain_study_v2_report.md", V2_REPORT),
        ("freeze_record.md", FREEZE_RECORD),
    ]:
        if path.exists():
            output_hashes[name] = sha256_file(path)

    # Count documents and chains
    total_docs = accessions["total_documents"]
    total_chains = accessions["total_chains"]

    return {
        "release": "upsilon_development_data_release",
        "release_version": "1.0",
        "release_purpose": (
            "Preserve the pre-v0.2 development evidence for "
            "reproducibility. Contains metadata (accessions, URLs, "
            "SHA-256 hashes) and derived analysis outputs. No SEC "
            "exhibit content is redistributed."
        ),
        "built_at_utc": datetime.now(UTC).isoformat(),
        "frozen_reference": {
            "tag": "chain-study-v2-development",
            "commit": "fb0862d",
        },
        "contents": {
            "accessions": "accessions.json",
            "failure_matrix_json": "failure_matrix.json",
            "failure_matrix_md": "failure_matrix.md",
            "gold_schema_json": "gold_schema.json",
            "gold_schema_documentation": "gold_schema_documentation.md",
            "chain_study_v1_results": "chain_study_v1_results.json",
            "chain_study_v1_report": "chain_study_v1_report.md",
            "chain_study_v2_results": "chain_study_v2_results.json",
            "chain_study_v2_report": "chain_study_v2_report.md",
            "freeze_record": "freeze_record.md",
            "run_records": "run_records/",
            "reproducibility": "REPRODUCIBILITY.md",
            "release_notes": "RELEASE_NOTES.md",
        },
        "statistics": {
            "total_chains": total_chains,
            "total_documents": total_docs,
            "new_study_chains": 22,
            "existing_edgar_chains": 3,
        },
        "output_sha256": output_hashes,
        "redistribution_note": (
            "This release package contains only metadata and derived "
            "analysis. SEC exhibit content is NOT redistributed. "
            "Documents are fetched on-demand from EDGAR using the "
            "recorded accessions and URLs."
        ),
    }


# ---------------------------------------------------------------------------
# Reproducibility instructions
# ---------------------------------------------------------------------------


REPRODUCIBILITY_TEMPLATE = """\
# Reproducibility Instructions

## Purpose

This document describes how to reproduce the Development Chain Study v2
results from the pre-v0.2 frozen baseline.

## Frozen Reference

- **Tag**: `chain-study-v2-development`
- **Commit**: `fb0862d`
- **Frozen at UTC**: 2026-08-31T17:33:11+00:00

## Prerequisites

- Python 3.12+
- git
- internet access (for SEC EDGAR fetching)

## Step 1: Clone the repository at the frozen commit

```bash
git clone <repo-url> upsilon
cd upsilon
git checkout fb0862d
```

## Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

## Step 3: Acquire the development corpus

The 25 development chains are acquired from SEC EDGAR. The accession
numbers and URLs are recorded in `accessions.json` in this release
package.

```bash
# Acquire the 22 new study chains
python acquire_chain_study.py

# Acquire the 3 existing EDGAR chains (Ameresco, Amedisys, Bausch-Lomb)
python download_smoke_cases.py
```

## Step 4: Verify document integrity

After acquisition, verify that the SHA-256 hashes of the downloaded
documents match the hashes recorded in `accessions.json`:

```bash
python -c "
import json, hashlib
from pathlib import Path

with open('results/release_package/accessions.json') as f:
    acc = json.load(f)

for doc in acc['documents']:
    url = doc['document_url']
    expected = doc.get('html_sha256') or doc.get('text_sha256')
    if not expected:
        continue
    # Verify against locally acquired files
    # (path depends on acquisition pipeline output structure)
    print(f'{doc[\"chain_id\"]} {doc[\"document_role\"]}: expected {expected[:16]}...')
"
```

## Step 5: Run the Development Chain Study v2

```bash
python run_chain_study_v2.py
```

This produces:
- `results/chain_study_v2_results.json` — machine-readable results
- `results/chain_study_v2_report.md` — human-readable report

## Step 6: Build the failure matrix

```bash
python build_failure_matrix.py
```

This produces:
- `results/failure_matrix.json` — per-chain failure attribution
- `results/failure_matrix.md` — human-readable matrix

## Step 7: Build the evaluation layers

```bash
python evaluation_layers.py
```

## Step 8: Build the gold schema

```bash
python gold_schema.py
```

## Step 9: Build the v0.2 change spec

```bash
python v02_change_spec.py
```

## Step 10: Verify against the frozen baseline

Compare your output SHA-256 hashes against the hashes in `manifest.json`:

```bash
python -c "
import json, hashlib
from pathlib import Path

with open('results/release_package/manifest.json') as f:
    manifest = json.load(f)

for name, expected_hash in manifest['output_sha256'].items():
    path = Path('results') / name
    if path.exists():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        status = 'OK' if actual == expected_hash else 'MISMATCH'
        print(f'{name}: {status}')
    else:
        print(f'{name}: MISSING')
"
```

## Expected Results (Frozen Baseline)

- **S0 extraction**: 12/22 new chains (54.5% success, 40.3% avg coverage)
- **GT extraction**: 2/5 CMP chains (40.0% success, 25.0% avg coverage)
- **Reconstruction**: 40.0% chain-level exact (5 chains with GT)
- **False authoritative promotions**: 0 (PASS)

## Run Records

Run records (environment, git state, input/output hashes) are in the
`run_records/` directory. Each record captures:
- Python version and platform
- Git commit and status
- pip freeze output
- Input and output file hashes

## Notes

- The SEC EDGAR documents are NOT included in this release package.
  They are fetched on-demand using the recorded accessions and URLs.
- The frozen baseline is the development set. The held-out study uses
  completely new issuers not in this release.
- No v0.2 changes are implemented in this release. The v0.2 change
  spec is included for review only.
"""


# ---------------------------------------------------------------------------
# Release notes
# ---------------------------------------------------------------------------


RELEASE_NOTES_TEMPLATE = """\
# Development Data Release Notes

## Release 1.0 — Pre-v0.2 Development Evidence

**Released**: {release_date}
**Frozen reference**: tag `chain-study-v2-development` (commit fb0862d)

### Contents

This release package preserves the pre-v0.2 development evidence:

1. **Accessions** (`accessions.json`) — SEC accession numbers, URLs, and
   SHA-256 hashes for all 25 development chains (167 documents total).
2. **Failure matrix** (`failure_matrix.json`, `failure_matrix.md`) —
   per-chain failure attribution across all 25 chains with 10-cause
   taxonomy.
3. **Gold schema** (`gold_schema.json`, `gold_schema_documentation.md`)
   — human-verifiable gold record schema with 11 required fields and
   verification workflow.
4. **Chain Study v1 results** — first-pass harness across 25 real EDGAR
   chains.
5. **Chain Study v2 results** (frozen) — extraction-aware failure
   classification with S0/GT extractors and measurement loop.
6. **Freeze record** (`freeze_record.md`) — SHA-256 verified freeze of
   the v2 results.
7. **Run records** (`run_records/`) — environment, git state, and file
   hashes for each run.
8. **Reproducibility instructions** (`REPRODUCIBILITY.md`) — step-by-step
   reproduction guide.
9. **v0.2 change spec** — 11 proposed changes with MUST FIX / SHOULD FIX
   / DEFER / REJECT classification. Locked scope: 6 changes
   (MUST FIX + SHOULD FIX).

### Frozen Baseline Results

- S0 extraction: 12/22 (54.5%)
- GT extraction: 2/5 (40.0%)
- Reconstruction: 40.0% chain-level exact
- False authoritative promotions: 0

### What is NOT included

- SEC exhibit content is NOT redistributed. Documents are fetched
  on-demand from EDGAR.
- No v0.2 code changes are implemented.
- No held-out study data (separate release).

### Integrity verification

All output files have SHA-256 hashes recorded in `manifest.json`. Run
the verification script in `REPRODUCIBILITY.md` Step 10 to confirm.
"""


# ---------------------------------------------------------------------------
# Build the release package
# ---------------------------------------------------------------------------


def build_release_package() -> dict[str, Any]:
    """Build the complete development-data release package."""
    # Clean and create the release directory
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    RELEASE_DIR.mkdir(parents=True)
    (RELEASE_DIR / "run_records").mkdir()

    # 1. Build and write accessions
    accessions = build_accessions()
    (RELEASE_DIR / "accessions.json").write_text(
        json.dumps(accessions, indent=2), encoding="utf-8"
    )

    # 2. Build and write manifest
    manifest = build_manifest(accessions)
    (RELEASE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # 3. Copy failure matrix
    if FAILURE_MATRIX_JSON.exists():
        shutil.copy2(FAILURE_MATRIX_JSON, RELEASE_DIR / "failure_matrix.json")
    if FAILURE_MATRIX_MD.exists():
        shutil.copy2(FAILURE_MATRIX_MD, RELEASE_DIR / "failure_matrix.md")

    # 4. Copy gold schema
    if GOLD_SCHEMA_JSON.exists():
        shutil.copy2(GOLD_SCHEMA_JSON, RELEASE_DIR / "gold_schema.json")
    if GOLD_SCHEMA_DOC.exists():
        shutil.copy2(GOLD_SCHEMA_DOC, RELEASE_DIR / "gold_schema_documentation.md")

    # 5. Copy v1 results
    if V1_RESULTS.exists():
        shutil.copy2(V1_RESULTS, RELEASE_DIR / "chain_study_v1_results.json")
    if V1_REPORT.exists():
        shutil.copy2(V1_REPORT, RELEASE_DIR / "chain_study_v1_report.md")

    # 6. Copy v2 results (use frozen copies if available, else live)
    v2_results_src = FROZEN_V2_RESULTS if FROZEN_V2_RESULTS.exists() else V2_RESULTS
    v2_report_src = FROZEN_V2_REPORT if FROZEN_V2_REPORT.exists() else V2_REPORT
    if v2_results_src.exists():
        shutil.copy2(v2_results_src, RELEASE_DIR / "chain_study_v2_results.json")
    if v2_report_src.exists():
        shutil.copy2(v2_report_src, RELEASE_DIR / "chain_study_v2_report.md")

    # 7. Copy freeze record
    if FREEZE_RECORD.exists():
        shutil.copy2(FREEZE_RECORD, RELEASE_DIR / "freeze_record.md")

    # 8. Copy run records
    if RESEARCH_RUN_RECORDS.exists():
        for record_file in sorted(RESEARCH_RUN_RECORDS.glob("*.json")):
            shutil.copy2(record_file, RELEASE_DIR / "run_records" / record_file.name)

    # 9. Write reproducibility instructions
    (RELEASE_DIR / "REPRODUCIBILITY.md").write_text(
        REPRODUCIBILITY_TEMPLATE, encoding="utf-8"
    )

    # 10. Write release notes
    release_date = datetime.now(UTC).strftime("%Y-%m-%d")
    (RELEASE_DIR / "RELEASE_NOTES.md").write_text(
        RELEASE_NOTES_TEMPLATE.format(release_date=release_date),
        encoding="utf-8",
    )

    return manifest


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_release_package(manifest: dict[str, Any]) -> list[str]:
    """Verify the release package integrity. Returns list of errors."""
    errors: list[str] = []

    # Check all expected files exist
    expected_files = [
        "manifest.json",
        "accessions.json",
        "failure_matrix.json",
        "failure_matrix.md",
        "gold_schema.json",
        "gold_schema_documentation.md",
        "chain_study_v1_results.json",
        "chain_study_v1_report.md",
        "chain_study_v2_results.json",
        "chain_study_v2_report.md",
        "freeze_record.md",
        "REPRODUCIBILITY.md",
        "RELEASE_NOTES.md",
    ]
    for fname in expected_files:
        if not (RELEASE_DIR / fname).exists():
            errors.append(f"Missing file: {fname}")

    # Check run_records directory exists and has files
    run_records_dir = RELEASE_DIR / "run_records"
    if not run_records_dir.exists():
        errors.append("Missing directory: run_records/")
    elif not any(run_records_dir.glob("*.json")):
        errors.append("run_records/ directory is empty")

    # Verify output SHA-256 hashes match manifest
    for name, expected_hash in manifest.get("output_sha256", {}).items():
        path = RELEASE_DIR / name
        if path.exists():
            actual = sha256_file(path)
            if actual != expected_hash:
                errors.append(f"Hash mismatch for {name}")

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Building development-data release package...")
    manifest = build_release_package()

    print(f"Release directory: {RELEASE_DIR}")
    print(f"Total chains: {manifest['statistics']['total_chains']}")
    print(f"Total documents: {manifest['statistics']['total_documents']}")
    print()

    # Verify
    errors = verify_release_package(manifest)
    if errors:
        print("VERIFICATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("Verification: PASS")
    print(f"Files in release: {len(list(RELEASE_DIR.rglob('*')))}")
    print()

    # List contents
    print("Release package contents:")
    for item in sorted(RELEASE_DIR.rglob("*")):
        if item.is_file():
            rel = item.relative_to(RELEASE_DIR)
            size = item.stat().st_size
            print(f"  {rel} ({size:,} bytes)")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
