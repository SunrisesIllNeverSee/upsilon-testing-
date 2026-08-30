# Upsilon — GitHub Testing Protocol

## Repository role

This repository serves four distinct purposes:

1. source control for the Upsilon Financial Commitment Integrity MVP;
2. automated verification of unit/schema/persistence behavior;
3. prospective research protocol versioning;
4. permanent provenance for formal empirical test runs.

Do not treat a passing CI build as evidence for the research hypothesis.
CI verifies implementation behavior. Empirical evidence comes from frozen,
documented runs on real financial documents.

---

## Branch model

### `main`
Stable, reviewable implementation.

### `develop`
Development work before a research freeze.

### research tags
Formal research freezes should be Git tags, e.g.:

```bash
git tag -a research-smoke-v0.1 -m "Frozen Upsilon smoke-test protocol"
git push origin research-smoke-v0.1
```

Later:

```bash
git tag -a research-heldout-v1.0 -m "Frozen held-out validation system"
git push origin research-heldout-v1.0
```

---

## Before any formal empirical run

1. CI must be green.
2. Working tree must be clean.
3. `research/PREREGISTRATION.md` reviewed.
4. `research/ANNOTATION_GUIDE.md` reviewed.
5. `research/SMOKE_TEST_PROTOCOL.md` reviewed where applicable.
6. Run:

```bash
python freeze_study.py
```

7. Commit the generated lock:

```bash
git add research/PREREGISTRATION_LOCK.json
git commit -m "Freeze research protocol"
```

8. Tag the commit.

Only then acquire/run the formal test data.

---

## After a formal run

Create a run record:

```bash
python record_run.py \
  --label <RUN_LABEL> \
  --inputs <INPUT_PATH> \
  --outputs <OUTPUT_PATH>
```

Review the record, then commit it separately:

```bash
git add research/run_records
git commit -m "Record empirical run <RUN_LABEL>"
```

Do not overwrite prior run records.

---

## Deviations

After a protocol freeze, any methodological/code change relevant to the study
must be recorded in:

`research/DEVIATION_LOG.md`

Commit deviations before rerunning whenever possible.

---

## What belongs in Git

Commit:
- source code;
- schema;
- tests;
- research protocol;
- annotation guide;
- hashes/manifests;
- run records;
- aggregate result tables;
- scripts required to reproduce analysis.

Do not commit by default:
- `.env`;
- credentials;
- private customer artifacts;
- restricted legal documents;
- large raw corpora;
- personally identifying internal data.

For public SEC material, preserve accession IDs, source URLs, and hashes even
when raw documents are stored outside Git.

---

## Evidence hierarchy

```text
CI PASS
= implementation behaves as specified

SMOKE TEST
= end-to-end mechanism works on real examples

DEVELOPMENT CORPUS
= parser/schema can be improved on real variation

HELD-OUT VALIDATION
= publishable empirical performance estimate
```

Never collapse these into one claim.
