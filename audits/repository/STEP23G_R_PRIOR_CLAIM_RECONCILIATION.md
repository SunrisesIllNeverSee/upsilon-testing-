# Step 23G-R — Prior Claim Reconciliation

**Date:** 2026-09-03
**Baseline commit:** `035daeb` (Step 24: restore Upsilon conservation-first commitment architecture)
**Prior scaffold commit:** `fad715c` (Step 23G: repository governance + MOSES structural scaffold)
**Step 23G-R commit:** `ef44c84` (Step 23G-R: repository architecture activation and current-state reconciliation)
**Method:** Direct filesystem inspection + Git history (`git log`, `git ls-tree -r --name-only HEAD`)

> **Post-correction note:** Claims 2, 3, 4, 6 described artifacts that did not
> exist at the baseline (`035daeb`). All corrections listed under "CORRECTION
> REQUIRED" have been applied in commit `ef44c84`. The "ACTUAL STATUS" values
> below reflect the baseline state, not the post-correction state.

---

## Summary

The prior Step 23G review report (`audits/step23s/STEP_23G_REVIEW_REPORT.md`) was **largely accurate** about artifacts that existed at commit `fad715c`. The one significant inaccuracy in the broader project record is that `src/upsilon/README.md` still describes the package as a "structural scaffold only" with "no production modules moved here yet" — which became false after Step 24 (`035daeb`) added real runtime code without updating the README.

The user-supplied root map that prompted this step initially appeared to show `.devin/rules.md` as missing. That was an artifact of the map listing directories only at the `.devin/` level. `.devin/rules.md` **does exist** in the working tree and in Git history.

---

## Claim-by-claim reconciliation

### CLAIM 1: `.devin/rules.md` exists and is verified

| Field | Value |
|-------|-------|
| REPORTED STATUS | EXISTS, verified (Step 23G review line 96: "`.devin/rules.md` → lineage layer in quick reference — PASS") |
| ACTUAL STATUS | EXISTS on filesystem and in Git |
| GIT EVIDENCE | Created in `fad715c` (Step 23G). Never removed. `git ls-tree -r --name-only HEAD` includes `.devin/rules.md`. |
| CORRECTION REQUIRED | None. The user-supplied root map that prompted this step listed `.devin/prompts/` but did not enumerate files inside `.devin/`, which created the false impression that `rules.md` was missing. |

### CLAIM 2: `AGENTS.md` exists

| Field | Value |
|-------|-------|
| REPORTED STATUS | Not claimed by the Step 23G review. The Step 23G-R prompt asserted it did not exist. |
| ACTUAL STATUS | DOES NOT EXIST on filesystem or in Git. |
| GIT EVIDENCE | `git log --oneline -- AGENTS.md` returns no commits. `git ls-tree -r --name-only HEAD` does not include `AGENTS.md`. |
| CORRECTION REQUIRED | Create `AGENTS.md` (Step 23G-R §4). |

### CLAIM 3: `REPOSITORY_STRUCTURE.md` exists

| Field | Value |
|-------|-------|
| REPORTED STATUS | Not claimed by the Step 23G review. The Step 23G-R prompt asserted it did not exist. |
| ACTUAL STATUS | DOES NOT EXIST on filesystem or in Git. |
| GIT EVIDENCE | `git log --oneline -- REPOSITORY_STRUCTURE.md` returns no commits. |
| CORRECTION REQUIRED | Create `REPOSITORY_STRUCTURE.md` (Step 23G-R §3). |

### CLAIM 4: `src/upsilon/*/README.md` exists for every target domain

| Field | Value |
|-------|-------|
| REPORTED STATUS | Step 23G review verified `src/upsilon/lineage/README.md` and `src/upsilon/README.md`. Did not claim per-domain READMEs for other domains. |
| ACTUAL STATUS | Only `src/upsilon/README.md` and `src/upsilon/lineage/README.md` exist. The other 10 target domains have no README. |
| GIT EVIDENCE | `git ls-tree -r --name-only HEAD | grep "src/upsilon.*README"` returns exactly two files. |
| CORRECTION REQUIRED | Create READMEs for `authority`, `commitments`, `conservation`, `evidence`, `execution`, `ingestion`, `models`, `parsing`, `pipeline`, `proof`, `transformations` (Step 23G-R §6). |

### CLAIM 5: `src/upsilon/` is a "structural scaffold only" with "no production modules moved here yet"

| Field | Value |
|-------|-------|
| REPORTED STATUS | `src/upsilon/README.md` line 5 states this. The Step 23G review (written at `fad715c`) verified this was true at that commit. |
| ACTUAL STATUS | FALSE as of `035daeb`. Step 24 added 26 runtime `.py` files under `src/upsilon/` implementing identity, kernel, transformations, conservation, proof, lineage, authority, and models. |
| GIT EVIDENCE | `git ls-tree -r --name-only HEAD | grep "src/upsilon.*\.py"` returns 26 files. Commit `035daeb` ("Step 24: restore Upsilon conservation-first commitment architecture") added them. |
| CORRECTION REQUIRED | Update `src/upsilon/README.md` to reflect TARGET_ACTIVE status for implemented domains (Step 23G-R §12). |

### CLAIM 6: `src/upsilon/propagation/` exists as a target domain

| Field | Value |
|-------|-------|
| REPORTED STATUS | Not claimed. The architecture docs list "Propagation Integrity" as a third integrity domain but no `propagation/` directory was ever created. |
| ACTUAL STATUS | DOES NOT EXIST. |
| GIT EVIDENCE | `git ls-tree -r --name-only HEAD | grep "propagation"` returns nothing. |
| CORRECTION REQUIRED | Evaluate whether to create `src/upsilon/propagation/` scaffold (Step 23G-R §6). The MOSES docs (`docs/architecture/DEPENDENCY_DIRECTION.md` line 50: "DOWNSTREAM PROPAGATION / COMPARISON") and `docs/architecture/ARCHITECTURE_INDEX.md` (line 107: "Propagation Integrity — Not yet addressed") confirm propagation is a first-class architectural responsibility. Create scaffold + README. |

### CLAIM 7: `forensic_qa/` and `audits/forensic_qa/` are duplicated

| Field | Value |
|-------|-------|
| REPORTED STATUS | `docs/architecture/ARCHITECTURE_INDEX.md` line 116 states: "Forensic Q&A | `forensic_qa/` (current); `audits/forensic_qa/` (future)". |
| ACTUAL STATUS | Both exist. `forensic_qa/` has 2 files (`001_moses_commitment_theory_audit.md`, `README.md`). `audits/forensic_qa/` has only `.gitkeep`. |
| GIT EVIDENCE | Both paths present in `git ls-tree -r --name-only HEAD`. |
| CORRECTION REQUIRED | Reconcile: `forensic_qa/` is the active location with content; `audits/forensic_qa/` is an empty placeholder. Document that `forensic_qa/` is canonical until migration. Do not delete the placeholder without a migration record. (Step 23G-R §9.) |

### CLAIM 8: `audits/step23s/STEP_23G_REVIEW_REPORT.md` is correctly placed

| Field | Value |
|-------|-------|
| REPORTED STATUS | Not explicitly addressed by prior reports. |
| ACTUAL STATUS | A Step 23G review report sits inside the `audits/step23s/` directory. The directory name suggests Step 23S audits; the file is a Step 23G review. |
| GIT EVIDENCE | `git ls-tree -r --name-only HEAD | grep "STEP_23G_REVIEW"` returns `audits/step23s/STEP_23G_REVIEW_REPORT.md`. Introduced in commit `1878d9c` ("Step 23G: machine-generated dependency graph + frozen ground-truth inventory"). |
| CORRECTION REQUIRED | The placement is historically explicable: the Step 23G review was performed as part of the Step 23S work stream. Do not move it silently. Document the placement as intentional-but-odd and note that future Step 23G audits should live under `audits/repository/` or a dedicated `audits/step23g/` directory. (Step 23G-R §9.) |

### CLAIM 9: `config/sql/` is empty while `queries.sql` and `schema.sql` remain at root

| Field | Value |
|-------|-------|
| REPORTED STATUS | Not explicitly addressed. `config/sql/` was created as a placeholder in Step 23G. |
| ACTUAL STATUS | `config/sql/` contains only `.gitkeep`. `queries.sql` and `schema.sql` remain at repository root. |
| GIT EVIDENCE | `git ls-tree -r --name-only HEAD | grep "config/sql"` returns `config/sql/.gitkeep` only. Root SQL files present in tree. |
| CORRECTION REQUIRED | Do not move in this step. Document the planned migration and preconditions. (Step 23G-R §10.) |

### CLAIM 10: All migration manifest rows state `MOVE NOW: NO`

| Field | Value |
|-------|-------|
| REPORTED STATUS | Step 23G review line 3 and multiple places in the manifest. |
| ACTUAL STATUS | TRUE for the manifest as written. However, the manifest was generated at `fad715c` and does not account for the Step 24 runtime code already added under `src/upsilon/`. The manifest does not inventory `src/upsilon/` files because they did not exist when it was generated. |
| GIT EVIDENCE | `docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md` line 3. |
| CORRECTION REQUIRED | Regenerate the dependency graph and manifest to include `src/upsilon/` files. Add operating-status classification. (Step 23G-R §7, §8, §15.) |

---

## Conclusion

The prior Step 23G review was accurate about the state at commit `fad715c`. The discrepancies are:

1. **`src/upsilon/README.md` is stale** — still says "scaffold only" after Step 24 added real runtime code.
2. **`AGENTS.md` and `REPOSITORY_STRUCTURE.md` never existed** — no prior report claimed they did, but they are required for governance.
3. **Per-domain READMEs are missing** for 10 of 12 target domains.
4. **`src/upsilon/propagation/` does not exist** despite propagation being a documented first-class integrity domain.
5. **The migration manifest does not inventory `src/upsilon/` runtime** because it predates Step 24.
6. **`forensic_qa/` vs `audits/forensic_qa/`** is a documented-but-unresolved duplication.
7. **`audits/step23s/STEP_23G_REVIEW_REPORT.md`** placement is historically explicable but structurally odd.

No prior report made a false claim about `.devin/rules.md`. The user-supplied root map that prompted this step was incomplete (directories only at the `.devin/` level), which created the impression that `rules.md` was missing. It is not missing.
