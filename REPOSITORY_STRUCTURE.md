# Repository Structure — Upsilon/MO§ES™

**Current operating model:** MIXED TRANSITIONAL — partially implemented target runtime sitting beside an overwhelmingly legacy-flat operating repository.

This document is the authoritative declaration of what belongs where in the Upsilon repository. It is read by every coding agent before modifying runtime code (see `AGENTS.md`).

---

## Controlling rules

> Existing code location describes historical implementation, not architectural authority.

> No new semantic responsibility may be added to a legacy root module when a target `src/upsilon/` domain already owns that responsibility, except through an explicitly documented temporary compatibility change.

> New runtime modules must not be created at repository root.

> Legacy root modules are maintenance/transitional surfaces, not default homes for new architecture.

> Absence of automated enforcement does not authorize a boundary violation.

---

## A. Legacy / transitional root

Existing root-level Python modules (approximately 80 files) are historical runtime, study, audit, acquisition, and research code. Their current location does NOT establish architectural ownership.

### What belongs at root

- `pyproject.toml` — Python project configuration (root is the conventional location)
- `Makefile` — build/run shortcuts
- `docker-compose.yml` — container orchestration
- `.env`, `.env.example` — environment configuration
- `.gitignore` — Git ignore rules
- `README.md` — project entry point
- `AGENTS.md` — agent entry point (governance)
- `REPOSITORY_STRUCTURE.md` — this document
- `CHANGELOG.md`, `CHANGELOG_v0.3.md` — release history
- `LICENSE` (if present)

### What must no longer be created at root

- New runtime Python modules
- New test files (see §C below)
- New semantic responsibility modules
- New SQL files (target: `config/sql/`)
- New architecture documentation (target: `docs/architecture/`)

### Root files pending classification

| File | Current location | Target location | Operating status | Move precondition | Archive status |
|------|------------------|----------------|------------------|-------------------|----------------|
| `queries.sql` | root | `config/sql/` | LEGACY_ACTIVE | None blocking; move when SQL migration phase begins | NOT_ARCHIVED |
| `schema.sql` | root | `config/sql/` | LEGACY_ACTIVE | None blocking; move when SQL migration phase begins | NOT_ARCHIVED |
| `AMENDMENT_INSTRUCTION_GRAMMAR.md` | root | `docs/moses/` or `docs/architecture/` | LEGACY_ACTIVE | Reference check before move | NOT_ARCHIVED |
| `BUILD_PLAN_25_ISSUERS.md` | root | `docs/runbooks/` or `research/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `COMMITMENT_LINEAGE_SCHEMA.md` | root | `docs/moses/` | LEGACY_ACTIVE | Reference check; cross-link from `docs/moses/` | NOT_ARCHIVED |
| `DEVELOPMENT_METHODS_RESULTS.md` | root | `research/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `GITHUB_TESTING_PROTOCOL.md` | root | `docs/runbooks/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `IP_BOUNDARY.md` | root | `docs/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `RESEARCH_WORKFLOW_MAC.md` | root | `research/` or `docs/runbooks/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `RUNBOOK_PUBLISHABLE_STUDY.md` | root | `docs/runbooks/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `VALIDATOR_INTERFACE.md` | root | `docs/moses/` or `docs/architecture/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `TEST_RESULTS_v0.3.txt` | root | `results/` or `archive/` | LEGACY_MAINTENANCE_ONLY | Historical; consider archive | ARCHIVE_CANDIDATE |
| `TEST_RESULTS_v0.4.txt` | root | `results/` or `archive/` | LEGACY_MAINTENANCE_ONLY | Historical; consider archive | ARCHIVE_CANDIDATE |
| `gold_annotations.csv` | root | `data/ground_truth/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `issuers.csv` | root | `data/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `predictions.csv` | root | `results/` | LEGACY_MAINTENANCE_ONLY | Historical; consider archive | ARCHIVE_CANDIDATE |
| `smoke_cases.csv` | root | `data/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |
| `development_corpus.csv` | root | `data/` | LEGACY_ACTIVE | Reference check | NOT_ARCHIVED |

---

## B. Target runtime — `src/upsilon/**`

This is the authoritative target runtime architecture. As of Step 24 (`035daeb`), seven domains contain real runtime implementation; five remain scaffolds; one (`propagation/`) is newly created as a scaffold.

| Domain | Status | Implemented modules |
|--------|--------|---------------------|
| `authority/` | TARGET_ACTIVE | `promotion_gate.py` |
| `commitments/` | TARGET_ACTIVE | `identity.py`, `kernel.py` |
| `conservation/` | TARGET_ACTIVE | `invariants.py`, `loss_detection.py`, `validator.py` |
| `lineage/` | TARGET_ACTIVE | `graph.py`, `queries.py` |
| `models/` | TARGET_ACTIVE | `authority.py`, `identity.py`, `kernel.py`, `lineage.py`, `proof.py`, `transformation.py` |
| `proof/` | TARGET_ACTIVE | `transformation_proof.py` |
| `transformations/` | TARGET_ACTIVE | `apply.py`, `authorized_change.py` |
| `evidence/` | TARGET_SCAFFOLD | (`.gitkeep` only) |
| `execution/` | TARGET_SCAFFOLD | (`.gitkeep` only) |
| `ingestion/` | TARGET_SCAFFOLD | (`.gitkeep` only in `document_discovery/`, `edgar/`, `normalization/`) |
| `parsing/` | TARGET_SCAFFOLD | (`.gitkeep` only) |
| `pipeline/` | TARGET_SCAFFOLD | (`.gitkeep` only) |
| `propagation/` | TARGET_SCAFFOLD | (newly created in Step 23G-R) |

See `src/upsilon/README.md` for the semantic subdomain table and `docs/architecture/ARCHITECTURE_INDEX.md` for navigation.

### Where new runtime code belongs

New runtime code belongs in the appropriate `src/upsilon/<domain>/` directory. If the domain does not exist, create it with a README defining ownership before adding runtime code.

---

## C. Test target — `tests/**`

This is the authoritative target test architecture.

| Directory | Purpose | Current contents |
|-----------|---------|------------------|
| `tests/unit/` | Unit tests for target runtime | `test_upsilonsrc.py` (72 tests) |
| `tests/integration/` | Integration tests | `.gitkeep` only |
| `tests/conservation/` | Conservation invariant tests | `.gitkeep` only |
| `tests/transformation/` | Transformation engine tests | `.gitkeep` only |
| `tests/authority/` | Authority gate tests | `.gitkeep` only |
| `tests/regression/` | Regression tests | `.gitkeep` only |
| `tests/corpus/` | Corpus tests | `.gitkeep` only |
| `tests/conformance/` | Conformance tests | `README.md` only |

### Current test collection state

- Approximately 36 `test_*.py` files remain at repository root (legacy tests).
- One test file (`tests/unit/test_upsilonsrc.py`) lives in the target tree.
- `pyproject.toml` is at Phase 1: `testpaths = ["tests", "."]` so both locations are collected.
- Baseline: 1052 passed, 14 skipped (as of `035daeb`).

### Test policy

> No new tests should be created at project root unless explicitly required for compatibility during the staged migration.

New tests for target runtime code (`src/upsilon/`) must live in the appropriate `tests/<category>/` directory.

A migration checkpoint must fail if test count falls unexpectedly because tests stopped being collected.

---

## D. Audit / research / results / data

These are non-runtime domains. They must not be imported by runtime code (see `.devin/rules.md` §4 and `docs/architecture/DEPENDENCY_DIRECTION.md`).

| Domain | Location | Purpose |
|--------|----------|---------|
| Audit | `audits/` | Audit scripts, dependency graphs, review reports |
| Research | `research/` | Research methodology, notebooks, preregistration, run records |
| Results | `results/` | Generated study results, benchmarks, frozen outputs |
| Data | `data/` | Corpora, ground truth, EDGAR chains, smoke cases |
| Archive | `archive/` | Superseded docs, legacy code, old results |
| Forensic QA | `forensic_qa/` | Forensic quality audit documents (canonical; `audits/forensic_qa/` is an empty placeholder) |

### Where ground truth belongs

Ground truth belongs under `data/ground_truth/`. Frozen artifacts are governed by `docs/methodology/FROZEN_ARTIFACT_POLICY.md` and inventoried in `data/ground_truth/frozen/`.

### Where generated results belong

Generated results belong under `results/`. Frozen results are under `results/frozen/` and must not be overwritten or silently regenerated.

### Where audits belong

Audit scripts and reports belong under `audits/`. The machine-generated dependency graph lives in `audits/repository/`.

### Where research tooling belongs

Research tooling belongs under `research/`. Run records live in `research/run_records/`.

---

## Migration phase

**Current phase:** Phase 1 (transitional)

- Phase 0 (complete): Target scaffold created, all migration rows `MOVE NOW: NO`.
- Phase 1 (current): Step 24 added target runtime implementation. Test discovery advanced to `testpaths = ["tests", "."]`. Governance documents being reconciled (Step 23G-R).
- Phase 2 (future): Legacy root modules migrate to `src/upsilon/` domains. Boundary-violation modules are decomposed first. `import-linter` activates in advisory mode.
- Phase 3 (future): All runtime under `src/upsilon/`. `testpaths = ["tests"]`. `import-linter` in enforcing mode. Conformance gates in CI.

See `docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md` for the file-by-file migration plan and `docs/architecture/STATIC_GOVERNANCE.md` for enforcement activation.
