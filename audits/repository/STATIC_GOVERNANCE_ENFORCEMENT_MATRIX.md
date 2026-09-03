# Static Governance Enforcement Matrix — Step 23G-R

**Date:** 2026-09-02
**Baseline commit:** `035daeb`

This matrix records the enforcement state of each governance rule. It distinguishes what is **documented** from what is **actually enforced** and plans the activation path.

See `docs/architecture/STATIC_GOVERNANCE.md` for the enforcement activation plan and `docs/architecture/DEPENDENCY_DIRECTION.md` for the controlling semantic direction.

---

## Enforcement matrix

| # | Rule | Documented? | Currently enforced? | Enforcement mechanism | Activation phase | Failure behavior |
|---|------|-------------|---------------------|----------------------|------------------|-----------------|
| G1 | Runtime may not import audit/research | Yes (`.devin/rules.md` §4, `DEPENDENCY_DIRECTION.md` §"audits and research") | NO | `import-linter` forbidden contract (planned) | Phase 2 | CI failure |
| G2 | No new root runtime modules | Yes (`REPOSITORY_STRUCTURE.md` §A, `.devin/rules.md` §"Repository operating model") | NO (manual review only) | PR review checklist + CI lint (planned) | Phase 1 (manual) → Phase 2 (CI) | PR rejection / CI failure |
| G3 | Frozen artifacts immutable | Yes (`docs/methodology/FROZEN_ARTIFACT_POLICY.md`, `.devin/rules.md` §"Frozen artifact rules") | PARTIALLY — SHA-256 hashes in `data/ground_truth/frozen/` manifest; `.gitignore` exceptions scoped; no CI gate yet | CI hash verification (planned) | Phase 2 | CI failure on hash mismatch |
| G4 | Dependency direction (layered architecture) | Yes (`DEPENDENCY_DIRECTION.md`, `STATIC_GOVERNANCE.md` import-linter contract) | NO | `import-linter` layers contract (planned) | Phase 2 (advisory) → Phase 3 (enforcing) | CI failure on layer violation |
| G5 | Test collection baseline | Yes (`REPOSITORY_STRUCTURE.md` §C) | NO (manual check) | CI test-count assertion (planned) | Phase 2 | CI failure if count drops below baseline (1066) |
| G6 | Target-domain forbidden imports | Yes (each `src/upsilon/<domain>/README.md` FORBIDDEN DEPENDENCIES section) | NO | `import-linter` per-domain contracts (planned) | Phase 2 (advisory) → Phase 3 (enforcing) | CI failure on forbidden import |
| G7 | Generated dependency manifest synchronized | Yes (`docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md` provenance section) | PARTIALLY — `generate_dependency_graph.py` + `generate_manifest.py` exist; no CI gate to detect drift | CI regeneration check (planned) | Phase 2 | CI failure if manifest is stale |
| G8 | Conformance status cannot be promoted without required tests | Yes (`docs/moses/CONFORMANCE_CONTRACT.md`, `tests/conformance/README.md`) | NO | CI conformance gate (planned) | Phase 3 | CI failure if invariant marked ENFORCED without test |
| G9 | No new tests at root | Yes (`REPOSITORY_STRUCTURE.md` §C) | NO (manual review only) | PR review checklist + CI lint (planned) | Phase 1 (manual) → Phase 2 (CI) | PR rejection / CI failure |
| G10 | Legacy module modification requires responsibility statement | Yes (`AGENTS.md` §"Before modifying runtime code") | NO (manual review only) | PR template (planned) | Phase 1 (manual) | PR rejection |
| G11 | 13 commitment classes frozen | Yes (`.devin/rules.md` §6) | NO (manual review only) | CI ontology check (planned) | Phase 3 | CI failure on ontology change |
| G12 | Conservation validation before execution | Yes (`.devin/rules.md` §5, `DEPENDENCY_DIRECTION.md`) | NO (target runtime enforces internally; legacy pipeline does not) | `import-linter` + runtime gate | Phase 3 | CI failure / runtime rejection |
| G13 | Propagation domain isolation | Yes (`src/upsilon/propagation/README.md`) | NO | `import-linter` (planned) | Phase 3 | CI failure on forbidden import |

---

## Current enforcement summary

| Status | Count |
|--------|-------|
| Documented, NOT enforced | 9 |
| Documented, PARTIALLY enforced | 2 (G3 frozen artifacts, G7 manifest sync) |
| Documented, enforced via runtime (not CI) | 1 (G12 conservation validation in target runtime) |
| Total rules | 13 |

**No static governance is enforced via CI as of Step 23G-R.** All rules are documented. Enforcement activation is planned for Phase 2 (advisory) and Phase 3 (enforcing) per `docs/architecture/STATIC_GOVERNANCE.md`.

---

## Activation path

### Phase 1 (current — manual)
- Rules G2, G9, G10 enforced via PR review and `AGENTS.md` responsibility statement
- No CI gates active
- `import-linter` not installed

### Phase 2 (advisory — after clean modules migrate)
- Install `import-linter` in advisory mode (warnings only)
- Activate G1, G4, G6 (layered architecture + forbidden imports)
- Activate G3 (frozen artifact hash verification in CI)
- Activate G5 (test collection baseline assertion)
- Activate G7 (manifest synchronization check)
- Activate G9 (no new root tests — CI lint)

### Phase 3 (enforcing — after boundary violations resolved)
- `import-linter` in enforcing mode (CI failure on violations)
- Activate G8 (conformance gate)
- Activate G11 (ontology freeze check)
- Activate G12 (conservation validation gate in CI)
- Activate G13 (propagation isolation)
