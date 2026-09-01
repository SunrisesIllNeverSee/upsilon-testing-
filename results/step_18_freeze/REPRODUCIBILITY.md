# Reproducibility Instructions — Step 18 Freeze

## Frozen Reference

- **System**: Upsilon Financial Commitment Integrity v1
- **Tag**: `v1.0-frozen-operational-build`
- **Commit**: `9771fe5db5f672c3d653ef2a9ba1fc54ffd08900`
- **Frozen at UTC**: 2026-09-01T05:48:44.147775+00:00

## Prerequisites

- Python 3.12+
- PostgreSQL 14+ (for integrity checks)
- git
- internet access (for SEC EDGAR fetching)

## Step 1: Clone and checkout the frozen commit

```bash
git clone <repo-url> upsilon
cd upsilon
git checkout 9771fe5db5f672c3d653ef2a9ba1fc54ffd08900
```

## Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

## Step 3: Set up PostgreSQL

```bash
# Create the upsilon database and user
createdb upsilon
createuser upsilon
psql -c "ALTER USER upsilon WITH PASSWORD 'upsilon';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE upsilon TO upsilon;"

# Set the DATABASE_URL environment variable
export DATABASE_URL="postgresql+psycopg://upsilon:upsilon@localhost:5432/upsilon"
```

## Step 4: Acquire the development corpus

The 25 development chains are acquired from SEC EDGAR. The accession
numbers and URLs are recorded in `results/release_package/accessions.json`.

```bash
# Acquire the 22 new study chains
python acquire_chain_study.py

# Acquire the 3 existing EDGAR chains
python download_smoke_cases.py
```

## Step 5: Verify document integrity

Verify that the SHA-256 hashes of the downloaded documents match the
hashes recorded in `results/step_18_freeze/input_manifest.json`.

## Step 6: Run the Step 17B measurement

```bash
set -a && source .env && set +a
python run_step_17b.py
```

This produces `results/step_17b/step_17b_results.json` with all 10
deliverables.

## Step 7: Verify the freeze artifacts

Compare your output SHA-256 hashes against the hashes in
`results/step_18_freeze/freeze_record.json`:

```bash
python -c "
import json, hashlib
from pathlib import Path

with open('results/step_18_freeze/freeze_record.json') as f:
    record = json.load(f)

for name, expected in record['artifact_hashes'].items():
    path = Path('results/step_18_freeze') / name
    if path.exists():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        status = 'OK' if actual == expected else 'MISMATCH'
        print(f'{name}: {status}')
    else:
        print(f'{name}: MISSING')
"
```

## Expected Results (Frozen Baseline)

- Incorrect automatic mutations: 0
- False authoritative promotions: 0
- PostgreSQL/lineage/temporal integrity: ALL PASS (25/25)
- Full test suite: 662 passed, 2 skipped, 0 failed
- Step 18 freeze gate: YES

## Notes

- The SEC EDGAR documents are NOT included in the freeze package.
  They are fetched on-demand using the recorded accessions and URLs.
- The frozen baseline is the development set (25 chains). The held-out
  confirmatory study (Step 19) uses completely new issuers not in this
  freeze.
- No v0.3 changes are implemented in this freeze.
