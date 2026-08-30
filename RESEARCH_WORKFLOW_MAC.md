# MacBook: Exact First Run

## 0. Install prerequisites once

Open Terminal.

```bash
python3 --version
git --version
```

Install Docker Desktop for Mac and open it.

## 1. Unzip and enter the project

```bash
cd ~/Downloads
unzip UPSILON_FINANCIAL_INTEGRITY_MVP_v0.4_RESEARCH.zip
cd upsilon_financial_integrity_mvp
```

## 2. Create the pre-test Git history

```bash
git init
git add .
git commit -m "Upsilon Financial Integrity pre-test baseline"
```

## 3. Create Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
```

## 4. Configure SEC identity

```bash
cp .env.example .env
nano .env
```

Set:

```text
SEC_USER_AGENT=Ello Cello LLC your-real-email@example.com
```

Save nano with Control-O, Return, Control-X.

Then:

```bash
set -a
source .env
set +a
```

## 5. Run unit tests

```bash
pytest -q
```

Do not proceed if required tests fail.

## 6. Start PostgreSQL

```bash
docker compose up -d
export TEST_DATABASE_URL="postgresql://upsilon:upsilon@localhost:5432/upsilon"
pytest -q test_persistence_integration.py
```

## 7. Read the prospective protocol before data

```bash
open research/PREREGISTRATION.md
open research/SMOKE_TEST_PROTOCOL.md
open research/ANNOTATION_GUIDE.md
```

Make any final prospective edits now.

## 8. Freeze the protocol

```bash
python freeze_study.py
git add .
git commit -m "Freeze smoke-test protocol before EDGAR acquisition"
```

After this point, protocol changes go into `research/DEVIATION_LOG.md`.

## 9. Download the fixed SEC smoke cases

```bash
python download_smoke_cases.py
```

The package pulls the two selected SEC exhibits automatically. No manual document hunting is required.

## 10. Record acquisition

```bash
mkdir -p results
python record_run.py --label smoke_acquisition --inputs data/smoke --outputs results
```

## 11. Run the deterministic parser

```bash
python amendment_parser.py data/smoke/SW-001/source.txt
python amendment_parser.py data/smoke/DKS-001/source.txt
```

The generated instruction JSON is the machine prediction, not the gold annotation.

## 12. Record observations before changing anything

```bash
open research/LAB_NOTEBOOK.md
```

Record:
- what was detected;
- what was missed;
- what became unresolved;
- what you expected before any fix.

If a material change is required, log it in:

```bash
open research/DEVIATION_LOG.md
```

Then commit the change separately.

## 13. Human gold annotation

For each fixed case, use the amendment and its Annex A composite agreement to annotate:

- instruction boundaries;
- affected commitments;
- prior state;
- resulting state;
- effective date/interval;
- composite ground-truth state.

Follow `research/ANNOTATION_GUIDE.md`.

## 14. End-to-end target

```text
SEC source
→ instruction parser
→ human-validated structured instruction
→ executor
→ PostgreSQL persistence
→ commitment lineage
→ reconstructed authoritative state
→ comparison against composite ground truth
```

## 15. After smoke-test success

```text
25 development issuers
→ refine parser/annotation
→ freeze v1.0
→ 25 untouched validation issuers
→ final metrics
→ paper
```

The held-out validation results are the primary publishable evidence. Smoke-test results are exploratory engineering evidence.
