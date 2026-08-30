# Research Lab Notebook

Append entries chronologically. Never rewrite earlier entries after results are known.

## Entry template

**Timestamp:**  
**Researcher:**  
**Study phase:** Smoke / Development / Freeze / Held-out  
**Case / corpus:**  
**Git commit:**  
**Protocol hash:**  

### Objective
### Inputs
### Exact procedure / commands
### Observations
### Raw results
### Interpretation
### Decision
### Prospective expectation before next run
### Artifacts produced / hashes

---

## Entry 001 — Environment setup and pre-test baseline

**Timestamp:** 2026-08-30T02:15:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Smoke
**Case / corpus:** N/A (environment setup)
**Git commit:** 466f7b0088fad939bd5e532c4aecf5de73e639d7
**Protocol hash:** (pre-freeze)

### Objective
Establish the pre-test code state, Python environment, SEC access configuration, and verify the software test suite passes before any contact with real SEC documents.

### Inputs
- UPSILON_GITHUB_READY_v0.4.zip (unzipped to upsilon_financial_integrity/)
- Python 3.14.6 (system)
- Docker/OrbStack 29.4.0
- macOS 26.5.2 (arm64)

### Exact procedure / commands
```bash
cd ~/Downloads
unzip UPSILON_GITHUB_READY_v0.4.zip
cd upsilon_financial_integrity

git init
git add .
git commit -m "Initial Upsilon Financial Integrity research build"
git branch -M main
git remote add origin https://github.com/SunrisesIllNeverSee/upsilon-testing-.git
git push -u origin main

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest

cp .env.example .env
# Edited .env: SEC_USER_AGENT="Ello Cello LLC burnmydays@proton.me"
set -a && source .env && set +a

pytest -q
```

### Observations
- Git repo initialized and pushed to GitHub successfully (commit 466f7b0).
- Python venv created with all dependencies: fastapi 0.141.1, pydantic 2.13.5, sqlalchemy 2.0.52, psycopg 3.3.4, alembic 1.19.1, httpx 0.28.1, beautifulsoup4 4.15.0, pandas 3.0.5, pytest 9.1.1.
- .env file required quoting the SEC_USER_AGENT value because it contains spaces. `source .env` with unquoted spaces fails silently (bash interprets "Cello" as a command).
- Unit tests: 17 passed, 1 skipped in 0.14s. The skipped test is `test_database_schema_is_temporal_and_has_reference_changes` (requires live PostgreSQL).

### Raw results
```
17 passed, 1 skipped in 0.14s
```

### Interpretation
The pre-test code state is verified. The deterministic executor, schema validation, and persistence plan tests all pass without a database. The system is ready for database integration testing and SEC document acquisition.

### Decision
Proceed to PostgreSQL integration test and protocol freeze.

### Prospective expectation before next run
Expect the DB integration test to pass once PostgreSQL is running, since the schema.sql is mounted into the Docker init directory. Expect the freeze to produce a clean lock file with stable hashes.

### Artifacts produced / hashes
- Git commit: 466f7b0088fad939bd5e532c4aecf5de73e639d7
- .env configured (gitignored, not committed)

---

## Entry 002 — PostgreSQL persistence integration test

**Timestamp:** 2026-08-30T02:19:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Smoke
**Case / corpus:** N/A (infrastructure test)
**Git commit:** 466f7b0088fad939bd5e532c4aecf5de73e639d7
**Protocol hash:** (pre-freeze)

### Objective
Verify the PostgreSQL persistence layer works end-to-end with the temporal schema, including reference change tracking.

### Inputs
- Docker/OrbStack (started via `open -a OrbStack`)
- docker-compose.yml (postgres:16, port 5432, schema.sql mounted as init script)
- TEST_DATABASE_URL=postgresql://upsilon:upsilon@localhost:5432/upsilon

### Exact procedure / commands
```bash
open -a OrbStack
docker compose up -d
export TEST_DATABASE_URL="postgresql://upsilon:upsilon@localhost:5432/upsilon"
pytest -v test_persistence_integration.py
pytest -q  # full suite with DB
```

### Observations
- OrbStack started in ~2 seconds.
- postgres:16 image pulled (~111MB download). First `docker compose up -d` triggered the pull.
- First test attempt failed: `psycopg.OperationalError: server closed the connection unexpectedly`. The PostgreSQL container was still in its init phase (running schema.sql). This is a race condition, not a code bug.
- After waiting ~5 seconds for the DB to report "database system is ready to accept connections", the test passed.
- Full suite with DB: 18 passed in 0.13s (17 unit + 1 DB integration).

### Raw results
```
test_persistence_integration.py::test_database_schema_is_temporal_and_has_reference_changes PASSED
18 passed in 0.13s
```

### Interpretation
The persistence bridge (`persistence.py`) correctly connects to PostgreSQL, the temporal schema (`schema.sql`) initializes properly via Docker entrypoint, and the reference-change dedicated structure is present. The database layer is verified and ready for real data ingestion.

### Decision
Proceed to protocol freeze. No code changes needed.

### Prospective expectation before next run
Expect the freeze to capture stable file hashes. No protocol edits are needed — the preregistration, smoke-test protocol, and annotation guide are all sound for the two fixed cases.

### Artifacts produced / hashes
- Docker container: upsilon_financial_integrity-postgres-1 (running)
- No new git artifacts

---

## Entry 003 — Protocol freeze

**Timestamp:** 2026-08-30T02:20:24Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Smoke (freeze)
**Case / corpus:** Protocol definition
**Git commit:** 47f64b2940549eda93b8f7673cb2825b2d56455a (after freeze commit)
**Protocol hash:** see PREREGISTRATION_LOCK.json

### Objective
Freeze the prospective study protocol before any contact with SEC test documents. This creates an immutable record of what was planned before results were known.

### Inputs
- research/PREREGISTRATION.md (v0.1, 2026-08-29)
- research/SMOKE_TEST_PROTOCOL.md
- research/ANNOTATION_GUIDE.md (v0.1)
- research/RESULTS_TEMPLATE.md
- research/REPRODUCIBILITY_CHECKLIST.md
- smoke_cases.csv

### Exact procedure / commands
```bash
python freeze_study.py
git add research/PREREGISTRATION_LOCK.json
git commit -m "Freeze smoke-test protocol before EDGAR acquisition"
```

### Observations
- Reviewed all three protocol documents before freezing. No edits were needed.
- The primary hypothesis (H1: amendment-aware reconstruction > carry-forward baseline) is well-defined and scoped to changed fields only.
- Secondary hypotheses H2-H5 cover complexity gradient, conservative execution, lineage completeness, and error concentration.
- The annotation guide's complexity classes (L1-L5) and ambiguity rule are appropriate.
- The freeze captured: UTC timestamp, Python version, platform, git commit, git status, and SHA-256 hashes for all 6 protocol files.

### Raw results
```json
{
  "frozen_at_utc": "2026-08-30T02:20:24.321008+00:00",
  "git_commit": "466f7b0088fad939bd5e532c4aecf5de73e639d7",
  "files": {
    "research/PREREGISTRATION.md": "3bb202333ec97eb728a7542358de43afff2703a62bd0539650121f8cd5ecc911",
    "research/SMOKE_TEST_PROTOCOL.md": "7a3f00c38df9dc2c9418f8ff1dd4b309b139f8aca4a3fa4fc4d0a08be2fe9c9e",
    "research/ANNOTATION_GUIDE.md": "b94d879515e8f885742ee1fbda723e4007c6c9be73fcfc4291aecda4666f36b0",
    "research/RESULTS_TEMPLATE.md": "69e28e0ef25a38d9621d5340bfa13dd344f11d6d668c02e6729abfa676a4c785",
    "research/REPRODUCIBILITY_CHECKLIST.md": "46081463ad76f8d5e42e07efea3a866a2476ecd5b337e800705031c363500ad2",
    "smoke_cases.csv": "ffacb0ae83dbeedba4b857ac95a384d1ee10b08287efe977e8127a6158f971bf"
  }
}
```

### Interpretation
The protocol is now frozen. Any post-freeze changes must be logged in DEVIATION_LOG.md with timing, reason, whether results were already viewed, and expected bias direction. This is the academic integrity boundary.

### Decision
Proceed to SEC document acquisition. No protocol changes.

### Prospective expectation before next run
Expect both SEC documents to download cleanly. The documents are large (credit agreements with Annex A composites), so the parser will need to handle substantial text. Expect the deterministic baseline parser to detect some instructions but produce false positives due to the composite agreement format.

### Artifacts produced / hashes
- research/PREREGISTRATION_LOCK.json (committed)
- Git commit: 47f64b2940549eda93b8f7673cb2825b2d56455a

---

## Entry 004 — SEC smoke-case acquisition

**Timestamp:** 2026-08-30T02:21:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Smoke
**Case / corpus:** SW-001, DKS-001
**Git commit:** 47f64b2940549eda93b8f7673cb2825b2d56455a
**Protocol hash:** 3bb202333ec97eb728a7542358de43afff2703a62bd0539650121f8cd5ecc911 (PREREGISTRATION.md)

### Objective
Download the two fixed SEC smoke-test filings directly from EDGAR, hash them for reproducibility, and record the acquisition as a machine-readable provenance trail.

### Inputs
- smoke_cases.csv (two rows: SW-001, DKS-001)
- SEC_USER_AGENT="Ello Cello LLC burnmydays@proton.me"
- download_smoke_cases.py

### Exact procedure / commands
```bash
python download_smoke_cases.py
mkdir -p results
python record_run.py --label smoke_acquisition --inputs data/smoke --outputs results
```

### Observations
- Both documents downloaded successfully from SEC EDGAR on first attempt.
- SW-001 (Sportsman's Warehouse, 2026-06-24, EX-10.2): 2,239,710 bytes HTML, 686,123 chars text. SHA-256: ef77effbc10f...
- DKS-001 (DICK'S Sporting Goods, 2019-06-28, EX-10.1): 1,218,986 bytes HTML, 527,173 chars text. SHA-256: a3e3271652e5...
- Each case directory contains: source.html (raw SEC bytes), source.txt (BeautifulSoup-extracted text), source_meta.json (case metadata + SHA-256 + byte count).
- The record_run.py output captured: timestamp, git commit, pip freeze, protocol lock, and all input file hashes.

### Raw results
```
SW-001 Sportsman's Warehouse Inc. ef77effbc10f 2239710
DKS-001 DICK'S Sporting Goods Inc. a3e3271652e5 1218986
```

### Interpretation
The SEC acquisition pipeline works end-to-end. Documents are hashed at acquisition time, preserving exactly what was tested. The provenance record (research/run_records/20260830T022123Z_smoke_acquisition.json) ties the downloaded files to the frozen protocol, git commit, and exact dependency versions.

### Decision
Proceed to run the deterministic parser on both cases. No changes to the parser before running — this is the pre-modification baseline.

### Prospective expectation before next run
The deterministic baseline parser (v0.2) uses regex patterns for REPLACE_TEXT, DELETE_SECTION, RESTATE_SECTION, WAIVE_TEMPORARILY, and ADD_COMMITMENT. Both filings use the "Composite Credit Agreement" format (Annex A), which means the actual amendment instructions are embedded in a large conformed document rather than simple inline delete/replace language. Expect:
- The RESTATE_SECTION regex may match broadly across the composite agreement.
- The WAIVE regex may produce false positives where "waived" appears in body text (e.g., ERISA notice periods, conditions precedent).
- The REPLACE_TEXT regex may find zero matches because these amendments use the Annex A format rather than inline quoted-text replacement.
- The parser is parsing the entire document (amendment + Annex A composite), not isolating the amendment instruction section.

### Artifacts produced / hashes
- data/smoke/SW-001/source.html (ef77effbc10f...)
- data/smoke/SW-001/source.txt (331a70ec9fd6...)
- data/smoke/SW-001/source_meta.json (1ec59e10aa68...)
- data/smoke/DKS-001/source.html (a3e3271652e5...)
- data/smoke/DKS-001/source.txt (d0704de7e83f...)
- data/smoke/DKS-001/source_meta.json (ecbd7a04bc8d...)
- research/run_records/20260830T022123Z_smoke_acquisition.json

---

## Entry 005 — Deterministic parser baseline run (pre-modification)

**Timestamp:** 2026-08-30T02:22:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Smoke
**Case / corpus:** SW-001, DKS-001
**Git commit:** 47f64b2940549eda93b8f7673cb2825b2d56455a
**Protocol hash:** 3bb202333ec97eb728a7542358de43afff2703a62bd0539650121f8cd5ecc911

### Objective
Run the existing deterministic baseline parser (v0.2) on both SEC smoke cases WITHOUT modifying it first. This establishes what the system detects before any improvement work, which is the engineering evidence we need.

### Inputs
- data/smoke/SW-001/source.txt (686,123 chars)
- data/smoke/DKS-001/source.txt (527,173 chars)
- amendment_parser.py (deterministic_baseline_v0.2)

### Exact procedure / commands
```bash
python amendment_parser.py data/smoke/SW-001/source.txt
python amendment_parser.py data/smoke/DKS-001/source.txt
```

### Observations

#### SW-001 (Sportsman's Warehouse) — 12 instructions detected
| # | Type | Target Section | Notes |
|---|------|---------------|-------|
| 1 | RESTATE_SECTION | Section 6.13 | Span: 41,223 chars. Matches "amended and restated in its entirety" but captures enormous context. |
| 2 | WAIVE_TEMPORARILY | Section 6.13 | FALSE POSITIVE — "waived" in conditions precedent context. |
| 3 | WAIVE_TEMPORARILY | Section\nPage | FALSE POSITIVE — matched table of contents header. |
| 4 | WAIVE_TEMPORARILY | Section 951(b) | FALSE POSITIVE — IRC reference in CFC definition. |
| 5 | WAIVE_TEMPORARILY | Section 10.03 | FALSE POSITIVE — "waived as provided in Section 10.03" in Event of Default definition. |
| 6 | WAIVE_TEMPORARILY | Section 9.12(b) | FALSE POSITIVE — cross-reference in "Reports" definition. |
| 7 | WAIVE_TEMPORARILY | Section 10.01 | FALSE POSITIVE — "waived in accordance with Section 10.01" in conditions precedent. |
| 8 | WAIVE_TEMPORARILY | Section headings | FALSE POSITIVE — "Section headings herein... for convenience of reference." |
| 9 | WAIVE_TEMPORARILY | Section 4.02 | FALSE POSITIVE — cross-reference in lender obligations. |
| 10 | WAIVE_TEMPORARILY | Section 8.01(f) | FALSE POSITIVE — "Event of Default... Section 8.01(f)" in remedies. |
| 11 | WAIVE_TEMPORARILY | Section 552 | FALSE POSITIVE — Bankruptcy Code section reference. |
| 12 | WAIVE_TEMPORARILY | Section 9.16 | FALSE POSITIVE — Defaulting Lender provisions. |

Instruction type counts: RESTATE_SECTION=1, WAIVE_TEMPORARILY=11, REPLACE_TEXT=0, DELETE_COMMITMENT=0, ADD_COMMITMENT=0.

#### DKS-001 (DICK'S Sporting Goods) — 9 instructions detected
| # | Type | Target Section | Notes |
|---|------|---------------|-------|
| 1 | RESTATE_SECTION | Section 2.15 | Span: 22,401 chars. Matches "amended and restated in its entirety" but captures large context. |
| 2 | WAIVE_TEMPORARILY | Section 2.15 | FALSE POSITIVE — same span overlap as #1. |
| 3 | WAIVE_TEMPORARILY | Section 957 | FALSE POSITIVE — IRC reference in CFC definition. |
| 4 | WAIVE_TEMPORARILY | Section 10.01 | FALSE POSITIVE — "waived in accordance with Section 10.01". |
| 5 | WAIVE_TEMPORARILY | Section 9.12(b) | FALSE POSITIVE — cross-reference in "Reports" definition. |
| 6 | WAIVE_TEMPORARILY | Section 4.02 | FALSE POSITIVE — conditions precedent cross-reference. |
| 7 | WAIVE_TEMPORARILY | Section 8.01(f) | FALSE POSITIVE — Event of Default cross-reference. |
| 8 | WAIVE_TEMPORARILY | Section 9.16 | FALSE POSITIVE — Defaulting Lender provisions. |
| 9 | WAIVE_TEMPORARILY | Section 9.16 | FALSE POSITIVE — duplicate match in same section. |

Instruction type counts: RESTATE_SECTION=1, WAIVE_TEMPORARILY=8, REPLACE_TEXT=0, DELETE_COMMITMENT=0, ADD_COMMITMENT=0.

### Raw results
```json
SW-001: {"instructions": 12, "out": "data/smoke/SW-001/source.instructions.json"}
DKS-001: {"instructions": 9, "out": "data/smoke/DKS-001/source.instructions.json"}
```

### Interpretation

**The parser is producing predominantly false positives.** Of the 21 total detected instructions across both cases, at most 2 (the RESTATE_SECTION matches) have any plausible connection to actual amendment instructions, and even those have unbounded spans that capture the entire composite agreement rather than the specific amendment instruction.

**Root causes identified:**

1. **WAIVE_TEMPORARILY regex is too permissive.** The pattern `(?:is hereby )?waived` matches any occurrence of "waived" in the document body. In credit agreements, "waived" appears frequently in non-instruction contexts: ERISA notice periods ("events for which the 30 day notice period has been waived"), conditions precedent ("satisfied or waived in accordance with Section 10.01"), Event of Default definitions, and Defaulting Lender provisions. These are not amendment waiver instructions.

2. **The parser does not isolate the amendment instruction section.** Both filings contain the amendment instruction at the top (a few pages) followed by the full Annex A composite credit agreement (hundreds of pages). The parser runs regex over the entire document, so it matches references inside the composite agreement body rather than the actual amendment instructions.

3. **The Composite Credit Agreement format is not handled.** Both amendments use the "Composite Credit Agreement" approach: "The Credit Agreement is hereby amended to delete the bold, stricken text... and to add the bold, double-underlined text... as set forth in the pages of the Credit Agreement attached as Annex A hereto." This is a single restatement instruction that incorporates the entire Annex A as the new authoritative state. The REPLACE_TEXT regex expects inline "deleting X, replacing with Y" patterns, which do not appear in these filings.

4. **RESTATE_SECTION spans are unbounded.** The regex `Section\s+[A-Za-z0-9.\-()]+.*?amended\s+and\s+restated\s+in\s+its\s+entirety` with `re.S` (dotall) matches across enormous text spans because `.*?` is lazy but the document is very long. The SW-001 match spans 41,223 characters; the DKS-001 match spans 22,401 characters. These are not useful instruction boundaries.

5. **No REPLACE_TEXT, DELETE_COMMITMENT, or ADD_COMMITMENT instructions detected.** The regex patterns for these types expect specific quoted-text replacement language that does not appear in the composite-agreement format. This is expected — these amendment types are expressed through the Annex A redline rather than inline instructions.

**Relationship to hypotheses:**
- H2 (complexity gradient): Confirmed prospectively. The composite-agreement format is effectively an L4 (Restatement) instruction for the entire agreement. The parser cannot decompose it into individual field-level changes.
- H3 (conservative execution): The parser's false positives are all WAIVE_TEMPORARILY, which would route to validation. This is "wrong but safe" — the system would not silently mutate authoritative state based on these matches. However, the precision is extremely low.
- H5 (error concentration): Errors concentrate in cross-references and body-text matches, exactly as predicted.

### Decision
This is the pre-modification baseline. No parser changes are made at this point. The results are recorded as exploratory engineering evidence. The parser needs substantial work before the development corpus phase:

1. **Document segmentation**: Isolate the amendment instruction section from the Annex A composite agreement before running instruction-detection regexes.
2. **WAIVE regex tightening**: Require "is hereby waived" (not just "waived") and exclude cross-reference contexts ("waived in accordance with", "waived as provided in").
3. **Composite-agreement instruction type**: Add a new instruction type or detection pattern for "Composite Credit Agreement" / "Annex A" format restatements.
4. **Span bounding**: Limit RESTATE_SECTION match context to a reasonable window (e.g., 500 chars) rather than allowing `.*?` to span the entire document.

These changes will be logged in DEVIATION_LOG.md if they modify the frozen protocol, or simply committed as parser improvements if they do not change the study design.

### Prospective expectation before next run
After implementing document segmentation and regex tightening, expect:
- WAIVE_TEMPORARILY false positives to drop to near zero.
- The composite-agreement restatement to be detected as a single RESTATE_SECTION or new COMPOSITE_RESTATEMENT instruction.
- REPLACE_TEXT to still detect zero matches (these filings don't use inline quoted-text replacement).
- The parser to produce a small number of high-precision instructions rather than a large number of low-precision ones.
- Overall instruction count to decrease significantly (from 12/9 to perhaps 1-3 per case), but precision to increase dramatically.

### Artifacts produced / hashes
- data/smoke/SW-001/source.instructions.json (12 instructions)
- data/smoke/DKS-001/source.instructions.json (9 instructions)
- Git commit: 47f64b2940549eda93b8f7673cb2825b2d56455a (no new commit yet — parser output is in gitignored data/ directory)

---
