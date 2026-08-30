# Upsilon Financial Commitment Integrity — Runbook

## What this package can produce now

### Publishable with public EDGAR data
1. Credit-agreement/amendment corpus.
2. Amendment-instruction parser accuracy on a held-out set.
3. Target-resolution accuracy.
4. Structured field-extraction accuracy.
5. Authoritative-state reconstruction accuracy.
6. Commitment-lineage completeness.
7. Agreement reconstruction validation against filed composite or amended/restated agreements.

### Not supportable from EDGAR alone
**Prevalence of downstream propagation failures inside lenders, banks, or companies.**

That claim requires actual downstream artifacts such as:
- covenant trackers,
- risk-model configurations,
- credit memos,
- internal policy representations,
- compliance systems.

Public agreement data can establish the authoritative side of the comparison, but not the private downstream side.

---

# Study design

## Development set
25 issuers / amendment chains.

Use these to:
- write and refine extraction rules;
- define commitment schema;
- debug chain reconstruction;
- create adjudication policy;
- tune any model-assisted extraction.

**Do not report development-set performance as the main scientific result.**

## Held-out validation set
25 additional issuers selected before final evaluation.

Freeze:
- parser version;
- instruction taxonomy;
- normalization rules;
- adjudication policy;
- metrics.

Then run once on the held-out set.

Target total:
- 50 issuers
- ideally 150+ amendment documents
- report exact document and instruction counts rather than promising a number beforehand.

---

# Step 1 — Install

Requirements:
- Python 3.12+
- Docker Desktop or Docker Engine

```bash
unzip UPSILON_FINANCIAL_INTEGRITY_MVP.zip
cd upsilon_financial_integrity_mvp

cp .env.example .env
```

Edit `.env` and replace the SEC user-agent contact.

Create environment:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

Start PostgreSQL:

```bash
docker compose up -d
```

The schema is loaded automatically on the first database creation.

---

# Step 2 — Smoke test the executor

```bash
pytest -q
```

Expected result:
all executor tests pass.

---

# Step 3 — Choose development issuers

Populate `issuers.csv`:

```csv
cik,issuer_name,split
0000123456,Issuer A,development
0000234567,Issuer B,development
```

Select issuers using a written rule before inspecting amendment difficulty.

Recommended inclusion rule:

- U.S. public company;
- original credit agreement available on EDGAR;
- at least 2 later amendments;
- English-language filings;
- documents accessible in machine-readable HTML/text where possible.

Recommended exclusion rule:

- no recoverable original agreement;
- scanned/image-only agreement that cannot be reliably parsed;
- duplicate/superseded filing artifacts;
- chain cannot be ordered from public evidence.

Keep an exclusion log.

---

# Step 4 — Download candidate agreements/amendments

```bash
set -a
source .env
set +a

python sec_ingest.py batch \
  --issuers issuers.csv \
  --start-year 2015 \
  --end-year 2025 \
  --out data/raw
```

For one company:

```bash
python sec_ingest.py company \
  --cik 0000123456 \
  --start-year 2015 \
  --end-year 2025
```

Outputs:
- raw source documents;
- normalized text;
- SHA-256 hashes;
- source URLs;
- accession numbers;
- filing dates;
- candidate-document manifests.

---

# Step 5 — Build the chain manually once

For each development issuer, confirm:

```text
Original
→ Amendment 1
→ Amendment 2
→ ...
→ Amended/Restated or Composite (if available)
```

Record authority and effective dates.

This manual chain is the gold reference for the first study.

Do not automate chain ordering until you understand the failure cases.

---

# Step 6 — Run deterministic amendment baseline

```bash
python amendment_parser.py \
  data/raw/<CIK>/<ACCESSION>/<DOCUMENT>.txt
```

It emits:

```text
<DOCUMENT>.instructions.json
```

Initial instruction classes:
- replace
- delete
- add
- waive
- restate

This intentionally starts simple. It gives the paper a reproducible baseline before any model-assisted system is introduced.

---

# Step 7 — Human annotation

Two reviewers are preferred for the held-out evaluation.

Annotate:
- instruction boundaries;
- instruction type;
- target section;
- old value;
- new value;
- effective dates;
- whether the instruction changes a commitment;
- resulting authoritative state.

Use `gold_annotations.csv`.

Recommended protocol:
1. both reviewers independently annotate a common 20% subset;
2. calculate agreement;
3. adjudicate disagreements;
4. freeze the annotation guide;
5. divide the remaining corpus;
6. adjudicate uncertain cases.

For the paper, report reviewer agreement separately from machine performance.

---

# Step 8 — Reconstruct authoritative state

For each agreement:

```text
K0 = human-validated original kernel
K1 = execute(Amendment 1, K0)
K2 = execute(Amendment 2, K1)
...
Kn = execute(Amendment n, Kn-1)
```

Every automatic transition must retain:
- source span;
- amendment authority;
- prior state;
- new state;
- valid time;
- recorded time.

Ambiguity routes to `UNRESOLVED`.

---

# Step 9 — Best validation target

Prefer chains that later file an:
- amended and restated agreement; or
- composite/conformed agreement.

Then compare:

```text
Upsilon reconstructed Kn
vs.
filed authoritative composite Kn
```

Primary metrics:

### Commitment identification
- precision
- recall
- F1

### State reconstruction
- exact field match
- numeric threshold exact match
- party match
- exception-set match
- status match

### Lineage
- % current commitments with complete authority path
- % amendments applied without unresolved ambiguity
- error count by instruction class

This is the strongest first paper because the ground truth is external to the reconstruction procedure.

---

# Step 10 — Freeze before held-out test

Before touching the 25 validation issuers, record:

- Git commit / package version;
- parser version;
- schema version;
- inclusion/exclusion criteria;
- metrics;
- annotation guide;
- handling of unresolved instructions.

Then run the held-out set without rule changes.

Any rule change after viewing held-out errors creates a new version and requires another untouched evaluation set.

---

# Step 11 — Generate result tables

Convert parser output to `predictions.csv`, then:

```bash
python evaluate_parser.py \
  --gold gold_annotations.csv \
  --pred predictions.csv \
  --out results/heldout_evaluation.json
```

Outputs:
- `heldout_evaluation.json`
- `heldout_evaluation.md`

These values can go directly into the Results section once the data are real and the evaluation set is frozen.

---

# First publishable paper

Working title:

**Reconstructing Commitment Lineage in Amended Credit Agreements: A Falsifiable Framework for Financial Contract State Integrity**

Primary research question:

> Can a structured commitment-lineage system reconstruct the authoritative state of repeatedly amended credit agreements from public filings?

Primary endpoint:

> Agreement between reconstructed commitment state and independently filed amended/restated or composite agreement.

Secondary endpoints:
- amendment instruction detection;
- instruction classification;
- target resolution;
- commitment field reconstruction;
- lineage completeness;
- unresolved rate.

Do not make default-prediction or internal-propagation claims in Paper 1 unless separately measured.

---

# Publication table shell

## Corpus

| Split | Issuers | Agreements | Amendments | Commitments |
|---|---:|---:|---:|---:|
| Development | | | | |
| Held-out validation | | | | |

## Instruction parser

| Metric | Development | Held-out |
|---|---:|---:|
| Precision | | |
| Recall | | |
| F1 | | |
| Type accuracy | | |
| Target accuracy | | |

## State reconstruction

| Field | Exact accuracy |
|---|---:|
| Covenant type | |
| Party | |
| Operator | |
| Threshold | |
| Frequency | |
| Exceptions | |
| Status | |

## Lineage

| Metric | Result |
|---|---:|
| Complete authority path | |
| Automatically resolved | |
| Human review required | |
| Incorrect transitions | |

---

# What counts as success

Do not choose a pass threshold after seeing results.

For a first serious system paper, the result can still be publishable if some instruction classes are difficult, provided:
- the dataset is real;
- the split is held out;
- annotation is reproducible;
- failures are reported;
- the baseline is transparent;
- state reconstruction is independently checked.

A negative result is scientifically usable. Hidden errors are not.


---

# PostgreSQL integration check

After `docker compose up -d`, run:

```bash
export TEST_DATABASE_URL="postgresql://upsilon:upsilon@localhost:5432/upsilon"
pytest -q test_persistence_integration.py
```

This verifies the live PostgreSQL schema before ingesting research data.
