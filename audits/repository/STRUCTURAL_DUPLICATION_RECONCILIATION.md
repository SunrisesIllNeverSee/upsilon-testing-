# Structural Duplication and Misplacement Reconciliation — Step 23G-R

**Date:** 2026-09-02
**Baseline commit:** `035daeb`

---

## 1. Forensic QA duplication

### Current state

| Path | Contents | In Git |
|------|----------|-------|
| `forensic_qa/` | `001_moses_commitment_theory_audit.md`, `README.md` | Yes |
| `audits/forensic_qa/` | `.gitkeep` only | Yes |

### Analysis

`docs/architecture/ARCHITECTURE_INDEX.md` line 116 documents: "Forensic Q&A | `forensic_qa/` (current); `audits/forensic_qa/` (future)". This was the intended migration path: forensic QA content lives at `forensic_qa/` now and would eventually move to `audits/forensic_qa/`.

### Decision

- `forensic_qa/` is the **canonical active location**. It contains real content.
- `audits/forensic_qa/` is an **empty placeholder** for a future migration that has not occurred.
- **No files are moved in this step.**
- The placeholder `.gitkeep` in `audits/forensic_qa/` is retained to preserve the directory structure for future migration.
- `REPOSITORY_STRUCTURE.md` §D documents `forensic_qa/` as canonical and `audits/forensic_qa/` as an empty placeholder.
- **When migration occurs:** move `forensic_qa/*` content to `audits/forensic_qa/`, update `ARCHITECTURE_INDEX.md`, and record the move in `REPOSITORY_MIGRATION_MANIFEST.md`. Do not leave two active locations with the same responsibility.

### Status: RECONCILED (documented, not yet migrated)

---

## 2. Step 23G review report placement

### Current state

| Path | Contents |
|------|----------|
| `audits/step23s/STEP_23G_REVIEW_REPORT.md` | Step 23G review report (211 lines) |

### Analysis

A Step 23G review report sits inside the `audits/step23s/` directory. The directory name suggests Step 23S audits. The file is a Step 23G review.

This placement is historically explicable: the Step 23G review was performed as part of the Step 23S work stream. The commit that introduced it (`1878d9c` "Step 23G: machine-generated dependency graph + frozen ground-truth inventory") was part of the Step 23S audit phase.

### Decision

- **Do not move the file silently.** Moving historical evidence without recording lineage would break Git history references.
- The placement is documented as **intentional-but-odd**: the Step 23G review was performed during the Step 23S work stream, so it lives in the Step 23S audit directory.
- Future Step 23G audits should live under `audits/repository/` (where this Step 23G-R reconciliation report lives) or a dedicated `audits/step23g/` directory.
- `REPOSITORY_STRUCTURE.md` does not need to change — `audits/` is the audit domain and subdirectory placement is a historical artifact, not an architectural violation.

### Status: DOCUMENTED (placement explained, not moved)

---

## 3. `config/sql/` vs root SQL files

### Current state

| Path | Contents |
|------|----------|
| `config/sql/` | `.gitkeep` only |
| `queries.sql` (root) | SQL queries |
| `schema.sql` (root) | Database schema |

### Analysis

`config/sql/` was created as a placeholder in Step 23G. The SQL files remain at root because they have not been migrated.

### Decision

- **Do not move in this step.** SQL file migration is not blocking any runtime work.
- `REPOSITORY_STRUCTURE.md` §A documents the planned migration with preconditions.
- When migration occurs: move `queries.sql` and `schema.sql` to `config/sql/`, update any references, and record in the migration manifest.

### Status: DOCUMENTED (planned, not yet migrated)

---

## 4. Root Markdown documents

### Current state

Multiple Markdown documents remain at root (see `REPOSITORY_STRUCTURE.md` §A for the full table).

### Decision

- **Do not move any Markdown documents in this step.**
- Each document has a target location and move precondition documented in `REPOSITORY_STRUCTURE.md` §A.
- Reference checks must be performed before any move to avoid breaking cross-references.
- `COMMITMENT_LINEAGE_SCHEMA.md` is the highest-priority candidate for migration to `docs/moses/` because it is referenced by target runtime code documentation.

### Status: DOCUMENTED (classified, not yet migrated)
