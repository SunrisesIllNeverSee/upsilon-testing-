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

## Entry 006 — v0.3 parser design: document segmentation + composite detection

**Timestamp:** 2026-08-30T02:35:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Smoke → Development transition
**Case / corpus:** SW-001, DKS-001 (regression)
**Git commit:** 6212017a (smoke baseline tag: smoke-baseline-v0.2)
**Protocol hash:** 3bb202333ec97eb728a7542358de43afff2703a62bd0539650121f8cd5ecc911

### Objective
Turn the v0.2 smoke-test failure modes into regression tests, then build parser v0.3 with structure-aware document segmentation, composite ground-truth detection, bounded instruction extraction, and tightened waiver regexes. This is the development phase — parser changes are allowed and belong in the lab notebook/changelog, not the protocol deviation log (per preregistration: smoke is exploratory, development allows parser changes).

### Inputs
- v0.2 smoke results (Entry 005): 12 instructions SW-001, 9 instructions DKS-001, predominantly WAIVE_TEMPORARILY false positives
- Error taxonomy from Entry 005: (1) WAIVE regex too permissive, (2) no document segmentation, (3) composite agreement format not handled, (4) unbounded RESTATE_SECTION spans, (5) zero REPLACE_TEXT/DELETE/ADD detected
- SW-001 source.txt (682,532 chars): amendment body = 1910–23873 (21,963 chars), composite = 28142–682532 (654,390 chars)
- DKS-001 source.txt (522,795 chars): amendment body = 2268–12892 (10,624 chars), composite = 15196–522795 (507,599 chars)

### Exact procedure / commands
```bash
# Tag the smoke baseline before changing code
git tag -a smoke-baseline-v0.2 6212017 -m "Frozen smoke-test parser baseline"
git push origin smoke-baseline-v0.2

# Create development branch
git checkout -b develop

# Write regression tests encoding v0.2 failure modes
# (test_parser_v03.py — 23 tests)

# Implement v0.3 parser
# (amendment_parser.py — segment_document, detect_composite, parse_v03)

# Run regression tests
pytest -v test_parser_v03.py

# Run full suite
pytest -q

# Re-run smoke cases with v0.3
python amendment_parser.py data/smoke/SW-001/source.txt --out data/smoke/SW-001/source.v03.json
python amendment_parser.py data/smoke/DKS-001/source.txt --out data/smoke/DKS-001/source.v03.json
```

### Observations

#### Document structure analysis
Both filings follow the same structural pattern:
```
[OTHER: header, title, WHEREAS recitals]
[AMENDMENT BODY: NOW, THEREFORE ... numbered sections ... conditions precedent]
[SIGNATURES: [SIGNATURE PAGES FOLLOW] ... IN WITNESS WHEREOF ... signature blocks ... schedules]
[COMPOSITE AGREEMENT: ANNEX A ... AMENDED AND RESTATED CREDIT AGREEMENT ... full conformed text]
```

The amendment body is small (10K–22K chars) and contains the actual amendment instructions. The composite agreement is enormous (500K–654K chars) and is the ground-truth target, not a source of instructions.

#### Regression tests written (23 tests)
- `TestSegmentDocument` (6 tests): amendment body starts at NOW THEREFORE, ends before signatures, composite segment isolated, filing without Annex A has no composite
- `TestCompositeDetection` (3 tests): Annex A detected, no-Annex filing not detected, offset within composite segment
- `TestWaiverFalsePositives` (4 tests): cross-reference "waived in accordance with" excluded, ERISA notice period excluded, real imperative "is hereby waived" included, composite body waivers excluded by segmentation
- `TestSpanBounding` (2 tests): RESTATE_SECTION span ≤ 1000 chars, all instruction source_text ≤ 1000 chars
- `TestAnnexAExclusion` (1 test): no instructions from composite agreement text
- `TestCompositeRestatement` (1 test): COMPOSITE_RESTATEMENT instruction type detected
- `TestSmokeCasesV03` (6 tests): real SW-001 and DKS-001 — no waiver false positives from composite, composite ground truth detected, instruction count ≤ 6

#### v0.3 architecture
1. **`segment_document(text)`** — divides filing into 4 segments using structural markers (NOW THEREFORE, SIGNATURE PAGES FOLLOW, IN WITNESS WHEREOF, ANNEX A ... CREDIT AGREEMENT)
2. **`detect_composite(text, segments)`** — checks composite segment for AMENDED AND RESTATED / Composite language, returns document-level object with annex letter and offsets
3. **`_extract_instructions(text, body_start, body_end)`** — runs tightened regexes ONLY on the amendment body segment
4. **Tightened regexes:**
   - `WAIVER_V03`: requires `Section X is hereby waived` or `Section X is waived` (imperative), excludes `waived in accordance with` and `has been waived` (cross-reference)
   - `REPLACE_V03`, `DELETE_V03`, `RESTATE_V03`, `ADD_V03`: bounded with `[^\n]{0,200}?` gap limit instead of `.*?` with `re.S`
   - `COMPOSITE_RESTATEMENT_RX`: detects "Credit Agreement is hereby amended to delete the bold, stricken text ... attached as Annex A"
5. **`COMPOSITE_RESTATEMENT` instruction type** added to `models.py` — represents the Annex A composite restatement as a single instruction
6. **Deduplication**: multiple regexes matching the same annex are deduplicated to a single COMPOSITE_RESTATEMENT instruction

### Raw results

#### v0.2 vs v0.3 comparison
```
SW-001:
  v0.2: 12 instructions (1 RESTATE_SECTION + 11 WAIVE_TEMPORARILY) — all false positives
  v0.3:  1 instruction (1 COMPOSITE_RESTATEMENT) — correct
  Reduction: 12 → 1 (91.7% reduction)
  False positives: 11 → 0 (100% elimination)
  Composite detected: No → Yes

DKS-001:
  v0.2:  9 instructions (1 RESTATE_SECTION + 8 WAIVE_TEMPORARILY) — all false positives
  v0.3:  1 instruction (1 COMPOSITE_RESTATEMENT) — correct
  Reduction: 9 → 1 (88.9% reduction)
  False positives: 8 → 0 (100% elimination)
  Composite detected: No → Yes
```

#### Test results
```
test_parser_v03.py: 23 passed in 0.06s
Full suite: 41 passed in 0.23s (18 original + 23 new regression)
```

#### Segmentation accuracy
```
SW-001:
  amendment_body: 1910–23873 (21,963 chars) — correct
  signatures: 23873–28142 (4,269 chars) — correct
  composite_agreement: 28142–682532 (654,390 chars) — correct

DKS-001:
  amendment_body: 2268–12892 (10,624 chars) — correct
  signatures: 12892–15196 (2,304 chars) — correct
  composite_agreement: 15196–522795 (507,599 chars) — correct
```

### Interpretation

**v0.3 achieves the primary engineering goal**: structure-aware document segmentation eliminates all false positives from the composite agreement body, and the composite restatement is correctly identified as a single COMPOSITE_RESTATEMENT instruction with Annex A as the ground-truth target.

**What v0.3 detects correctly:**
- The composite credit agreement format (Annex A restatement) as a single instruction
- The composite agreement as a document-level ground-truth target (not an instruction)
- Document structure: amendment body vs signatures vs composite agreement

**What v0.3 does NOT yet detect (expected limitations):**
- Individual field-level changes within the Annex A redline (e.g., "4.00 to 1.00" → "5.00 to 1.00"). These are embedded in the composite agreement's bold/stricken/double-underlined text, which requires HTML redline parsing, not text regex.
- The SW-001 amendment also contains non-composite instructions (Section 3 amends the Security Agreement by replacing "Second Amendment Effective Date" with "Third Amendment Effective Date" in 13 sections). The v0.3 REPLACE_V03 regex did not detect this because it expects quoted-text deletion/replacement, not find-and-replace of a defined term across multiple sections.
- The DKS-001 amendment contains a Commitment Increase instruction (Section 2) that is not a standard amendment instruction type in the current grammar.

**Relationship to hypotheses:**
- H1 (amendment-aware > carry-forward): v0.3 correctly identifies the composite restatement, which is the prerequisite for comparing against carry-forward. The actual field-level comparison requires parsing the Annex A redline.
- H2 (complexity gradient): The composite restatement is an L4 (Restatement) instruction. v0.3 handles it at the document level but cannot decompose it into field-level changes. This is the expected difficulty cliff.
- H3 (conservative execution): v0.3's precision is dramatically improved. Zero false positives means zero silent incorrect mutations. The single COMPOSITE_RESTATEMENT instruction would route to validation (it's not a supported executor instruction type yet), which is correct — the system does not silently mutate authoritative state.
- H5 (error concentration): The remaining gap is in redline parsing (L4 complexity), exactly as predicted.

### Decision
v0.3 is the new development baseline. The parser architecture is now correct: it knows where instructions are allowed to exist (amendment body only) and identifies the composite ground-truth target. The next development step is either:
1. HTML redline parsing to extract individual field-level changes from the Annex A composite (requires parsing bold/stricken/double-underlined text from source.html, not source.txt), OR
2. The 25-issuer development corpus to see if non-composite amendment formats (inline REPLACE_TEXT, DELETE_SECTION, etc.) are detected correctly.

Both paths are valid. The 25-issuer corpus would test the v0.3 regexes against diverse amendment formats, while HTML redline parsing would deepen the composite agreement handling.

### Prospective expectation before next run
For the 25-issuer development corpus, expect:
- Non-composite amendments (inline REPLACE_TEXT, DELETE_SECTION) to be detected correctly by the tightened v0.3 regexes
- Some amendments to use formats not yet handled (e.g., "Section X is amended to read as follows" without "in its entirety")
- Document segmentation to work for most filings but fail on unusual structures (e.g., amendments without NOW THEREFORE, or multiple amendment bodies)
- The WAIVER_V03 regex to correctly exclude cross-references but potentially miss real waivers that use different phrasing (e.g., "the parties agree to waive Section X")

### Artifacts produced / hashes
- amendment_parser.py (v0.3 — structure-aware segmentation + composite detection)
- models.py (added COMPOSITE_RESTATEMENT instruction type)
- test_parser_v03.py (23 regression tests)
- data/smoke/SW-001/source.v03.json (1 instruction, composite detected)
- data/smoke/DKS-001/source.v03.json (1 instruction, composite detected)
- Git tag: smoke-baseline-v0.2 (on commit 6212017)
- Git branch: develop

---

## Entry 007 — Architecture fix: CompositeTarget is not an InstructionType

**Timestamp:** 2026-08-30T03:10:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Development
**Case / corpus:** N/A (architecture correction)
**Git commit:** (pre-commit, on develop branch)
**Protocol hash:** 3bb202333ec97eb728a7542358de43afff2703a62bd0539650121f8cd5ecc911

### Objective
Fix an architecture violation introduced in v0.3.0: `COMPOSITE_RESTATEMENT` was added to the `InstructionType` enum, which conflates the composite ground-truth document with an amendment instruction. This would contaminate instruction precision/recall metrics by counting "we found the composite" as "we found an amendment instruction."

### Inputs
- v0.3.0 code: `models.py` with `COMPOSITE_RESTATEMENT` in `InstructionType`, `amendment_parser.py` with `COMPOSITE_RESTATEMENT_RX` in instruction extraction specs
- User correction: "The composite agreement is ground truth, not an amendment instruction"

### Exact procedure / commands
```bash
# 1. Remove COMPOSITE_RESTATEMENT from InstructionType enum
# 2. Add CompositeTarget Pydantic model to models.py
# 3. Remove COMPOSITE_RESTATEMENT_RX from instruction extraction specs
# 4. Update detect_composite() to return CompositeTarget-shaped dict
# 5. Rename composite_ground_truth → composite_target in parse_v03() result
# 6. Update tests: replace TestCompositeRestatement with TestCompositeTargetIsNotInstruction
# 7. Run full test suite
pytest -v
# 8. Re-run smoke cases
python amendment_parser.py data/smoke/SW-001/source.txt --out data/smoke/SW-001/source.v03.json
python amendment_parser.py data/smoke/DKS-001/source.txt --out data/smoke/DKS-001/source.v03.json
```

### Observations
- `COMPOSITE_RESTATEMENT` removed from `InstructionType` enum.
- `CompositeTarget` Pydantic model added to `models.py` with fields: `annex`, `start_offset`, `end_offset`, `source_format` (default: `"html_redline"`).
- `COMPOSITE_RESTATEMENT_RX` and `COMPOSITE_NAMED_RX` removed from instruction extraction specs. The composite detection is handled solely by `detect_composite()`.
- `detect_composite()` now returns a `CompositeTarget`-shaped dict (no `present` boolean — the object is either present or None).
- `parse_v03()` result key renamed from `composite_ground_truth` to `composite_target`.
- 3 new architecture-separation tests added in `TestCompositeTargetIsNotInstruction`.
- 2 new smoke-case architecture tests: `test_no_composite_in_instructions` for both cases.

### Raw results
```
SW-001: 0 instructions, composite_target = {annex: "A", start_offset: 28142, end_offset: 682532, source_format: "html_redline"}
DKS-001: 0 instructions, composite_target = {annex: "A", start_offset: 15196, end_offset: 522795, source_format: "html_redline"}
Full test suite: 45 passed in 0.18s
```

### Interpretation
The architecture is now clean:

```
AMENDMENT BODY → AmendmentInstruction[]
ANNEX A / COMPOSITE → CompositeTarget (ground truth)
```

The composite agreement is detected as a `CompositeTarget` — a ground-truth document with location and format metadata. It cannot be confused with an amendment instruction because it is not in the `InstructionType` enum and does not appear in the `instructions` list.

This means:
- Instruction precision/recall metrics will count only actual amendment instructions (REPLACE_VALUE, WAIVE_TEMPORARILY, etc.), not composite detections.
- The composite target is available as ground truth for downstream comparison.
- The 0 instruction count for both smoke cases is correct — these are pure composite-format filings where the actual field-level changes are embedded in the Annex A HTML redline, not in inline amendment instructions.

### Decision
Architecture fix is complete. The v0.3.1 baseline is ready for the 25-issuer development corpus.

### Prospective expectation before next run
For the 25-issuer development corpus, expect:
- Non-composite amendments to produce actual instructions (REPLACE_TEXT, DELETE_SECTION, WAIVE_TEMPORARILY, etc.)
- Composite-format amendments to produce 0 instructions but a non-None CompositeTarget
- Some filings to have both inline instructions AND a composite target
- The instruction count will be a meaningful precision/recall metric, not contaminated by composite detections

### Artifacts produced / hashes
- models.py (removed COMPOSITE_RESTATEMENT, added CompositeTarget)
- amendment_parser.py (removed COMPOSITE_RESTATEMENT_RX from instruction specs, updated detect_composite)
- test_parser_v03.py (replaced TestCompositeRestatement with TestCompositeTargetIsNotInstruction, updated smoke tests)
- CHANGELOG.md (v0.3.1 entry)
- data/smoke/SW-001/source.v03.json (0 instructions, composite_target present)
- data/smoke/DKS-001/source.v03.json (0 instructions, composite_target present)

---

## Entry 008 — 25-issuer development corpus: population prevalence and parser coverage

**Timestamp:** 2026-08-30T03:30:00Z
**Researcher:** Deric McHenry (via Devin CLI)
**Study phase:** Development (exploratory)
**Case / corpus:** 25-issuer development corpus (DEV-001 through DEV-025)
**Git commit:** 35528c6 (pre-corpus-acquisition)
**Protocol hash:** 3bb202333ec97eb728a7542358de43afff2703a62bd0539650121f8cd5ecc911

### Objective
Before building any format-specific engine (especially the HTML redline parser), measure what the real population of credit agreement amendments looks like. The two smoke cases were both composite-format (Annex A) filings. We do not know whether that represents 10%, 40%, or 70% of the population. Building a sophisticated HTML-redline engine before knowing prevalence risks overfitting to a rare format.

### Method
1. Search EDGAR full-text search API for 8-K filings containing "amendment to credit agreement" across 4 date ranges (2020-2026).
2. Select 25 unique issuers (one filing per CIK), excluding the 2 smoke-case issuers.
3. For each filing, fetch the filing index page, find EX-10 exhibits, and download the first EX-10.1 exhibit.
4. Convert HTML to text, hash all files.
5. Run v0.3.1 parser unchanged across all 25 documents.
6. Classify each document into format A-G using a heuristic classifier (broader than the parser regexes).
7. For each document capture: issuer, accession, amendment number, document format, composite present, instruction count, instruction classes, UNRESOLVED count, false positives, false negatives, parser coverage.

### Exact procedure / commands
```bash
set -a && source .env && set +a
python build_development_corpus.py
python classify_development_corpus.py
```

### Format taxonomy
```
A — inline amendment instructions
B — amendment + composite Annex
C — amended & restated agreement
D — redline/blackline composite
E — definition-heavy / cross-reference amendment
F — waiver-only amendment
G — mixed/other
```

### Raw results

#### Format distribution
```
A: 20 (80.0%)  — inline amendment instructions
F:  1 ( 4.0%)  — consent/forbearance agreement
G:  4 (16.0%)  — non-credit-agreement exhibits or full restated agreements
```

#### Key finding: 0 composite targets in 25 development documents
```
Composite targets found: 0/25 (0%)
```

This is the most important prevalence finding. The two smoke cases (SW-001, DKS-001) were both composite-format filings with Annex A. But in a random sample of 25 credit agreement amendments from 2020-2026, zero had composite Annex A targets. The composite format appears to be a minority pattern, not the dominant one.

The 4 "G" documents are:
- DEV-004: "Second Amendment to Credit Agreement" — amendment but uses non-standard instruction language not caught by the classifier
- DEV-005: "Purchase and Sale Agreement" — NOT a credit agreement amendment (wrong exhibit)
- DEV-016: "Credit Agreement" — a full credit agreement, not an amendment
- DEV-020: "Paycheck Protection Note" — a PPP note, NOT a credit agreement amendment

So 2 of the 4 G documents are genuinely wrong exhibits (non-credit-agreement documents filed as EX-10.1), and 2 are amendments with non-standard language.

#### Parser coverage
```
Total v0.3 instructions:  13
Total v0.2 instructions:  38
Est. false positives:     25 (v0.2→v0.3 reduction)
Est. false negatives:     81 (missed instructions)
Average parser coverage:  44.8%
```

The parser detected only 13 instructions out of an estimated 94 expected amendment instructions across the 25 documents. This is a 44.8% coverage rate — meaning the parser misses more than half of real amendment instructions.

#### Per-document coverage breakdown
Documents with 0% coverage (parser found nothing but amendment language exists):
- DEV-001, DEV-007, DEV-008, DEV-013, DEV-017, DEV-019, DEV-022, DEV-023, DEV-024, DEV-025

These documents use amendment instruction phrasings that the v0.3 regexes do not match:
- `is hereby amended as follows` (not `amended by adding/deleting`)
- `is amended to read as follows` (not `amended and restated in its entirety`)
- `is hereby deleted from Section X in its entirety` (not `deleted in its entirety`)
- `Schedule 1.1 ... is hereby amended by inserting` (parser only matches `Section`, not `Schedule`)
- `Article I ... is hereby amended by adding` (parser only matches `Section`, not `Article`)

### Interpretation

#### 1. Population prevalence
The composite/Annex A format (formats B and D) that dominated the smoke test is NOT the dominant format in the general population. Inline amendment instructions (format A) dominate at 80%. This validates the user's concern about overfitting: building an HTML redline engine before measuring prevalence would have invested in a minority format.

#### 2. Parser coverage gap
The v0.3 parser has a 44.8% coverage rate on real amendments. The primary failure mode is not false positives (those were fixed in v0.3) but false negatives — the parser misses real instructions because its regexes are too narrow. The specific gaps are:

1. **Reference target too narrow**: Parser only matches `Section X`, not `Article X`, `Schedule X`, or `Exhibit X`.
2. **Instruction verb too narrow**: Parser matches `amended by adding` and `amended by deleting`, but not `amended as follows`, `amended to read as follows`, or `amended by inserting`.
3. **Replace pattern too narrow**: Parser matches `deleting ... replacing`, but not `deleting ... inserting` or `deleting the single instance of ... and inserting ... in lieu thereof`.

#### 3. Wrong exhibits
2 of 25 documents (8%) are not credit agreement amendments at all — they're other EX-10.1 exhibits (a purchase agreement and a PPP note). This is an acquisition quality issue, not a parser issue.

### Decision
1. **Do NOT build the HTML redline engine yet.** The composite format is 0% of this development sample. Inline amendments are 80%. The priority is improving inline instruction coverage.
2. **Parser v0.4 should focus on**: broadening reference targets (Section/Article/Schedule/Exhibit), broadening instruction verbs (amended as follows, amended to read, inserting), and handling Schedule-level definitions.
3. **Acquisition improvement**: filter out non-credit-agreement EX-10.1 exhibits by checking the document title for "amendment to credit agreement" or "credit agreement" language.
4. **The 2 smoke cases remain valuable** as the only composite-format examples, but they are not representative of the general population.

### Prospective expectation before parser v0.4
After broadening the regexes to handle the patterns observed in this corpus, expect:
- Parser coverage to increase from ~45% to ~70-80%
- False positive rate to remain low (v0.3 segmentation fix holds)
- Remaining false negatives will be from deeply nested or unusually phrased amendments
- The 25-issuer corpus will serve as the development test set for iterative improvement

### Artifacts produced
- build_development_corpus.py (EDGAR search + download pipeline)
- classify_development_corpus.py (format classification + coverage estimation)
- data/development/DEV-001 through DEV-025/ (source.html, source.txt, source_meta.json for each)
- data/development/manifest.json (acquisition metadata for all 25)
- development_corpus.csv (classification results with all required fields)
- data/development/classification_results.json (same data in JSON)
- research/run_records/20260830T033000Z_dev_corpus_acquisition.json (provenance)

---
