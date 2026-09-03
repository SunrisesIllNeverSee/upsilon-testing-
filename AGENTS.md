# AGENTS.md — Upsilon/MO§ES™ Agent Entry Point

Every coding agent working in this repository must read the following documents in order before modifying runtime code:

1. **`AGENTS.md`** — this document
2. **`REPOSITORY_STRUCTURE.md`** — what belongs where, current operating model
3. **`.devin/rules.md`** — prohibited actions, dependency direction, frozen artifact rules
4. **`docs/architecture/ARCHITECTURE_INDEX.md`** — navigation entry point for architecture
5. **`docs/architecture/DEPENDENCY_DIRECTION.md`** — controlling semantic direction and per-layer import rules
6. The README for the target semantic domain being modified (see `src/upsilon/<domain>/README.md`)
7. **`docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md`** — for any legacy module being touched

---

## Before modifying runtime code

State the following in your plan or commit message:

```
RESPONSIBILITY:
TARGET DOMAIN:
CURRENT MODULE:
CURRENT OPERATING STATUS:
WHY THIS MODULE MUST CHANGE:
MIGRATION / REMOVAL CONDITION:
```

Do not infer architectural ownership from an existing legacy filename. A root-level module named `semantic_resolver_v2.py` does not establish that transformation interpretation belongs at root. Ownership is defined in `docs/architecture/DEPENDENCY_DIRECTION.md` and `REPOSITORY_STRUCTURE.md`.

---

## Quick rules

1. **New runtime code goes in `src/upsilon/<domain>/`.** Not at root.
2. **New tests go in `tests/<category>/`.** Not at root.
3. **Runtime may not import audit, research, or results modules.** See `.devin/rules.md` §4.
4. **Do not broaden the frozen ontology.** The 13 commitment classes are frozen without explicit user authorization.
5. **Do not bypass conservation validation.** Transformations must pass through conservation validation before execution.
6. **Do not overwrite or silently regenerate frozen artifacts.** See `docs/methodology/FROZEN_ARTIFACT_POLICY.md`.
7. **Do not move files without explicit authorization.** See `docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md`.
8. **Absence of automated enforcement does not authorize a boundary violation.**

---

## Current repository state

The repository is **MIXED TRANSITIONAL**: partially implemented target runtime (`src/upsilon/`) sitting beside an overwhelmingly legacy-flat operating repository (~80 root `.py` files). See `REPOSITORY_STRUCTURE.md` for the full operating model and `src/upsilon/README.md` for target domain statuses.
