# Archive Index

## Archive policy

Documents and code are **not** moved into `archive/` simply because they
appear old. Before anything is archived, it must be classified.

## Classification categories

| Category | Meaning | Action |
|----------|---------|--------|
| `SUPERSEDED` | Replaced by a newer version that is the current source of truth | May be archived with a pointer to the successor |
| `HISTORICAL_EVIDENCE` | Records a historical state that may be needed for traceability | May be archived; must remain accessible |
| `FROZEN_EXPERIMENTAL_RECORD` | Output of a completed experimental run | Belongs under `results/frozen/`, not `archive/` |
| `LEGACY_RUNTIME` | Runtime code superseded by a newer implementation | May be archived after migration is complete and tests pass |
| `UNKNOWN` | Classification not yet determined | **Stays where it is until adjudicated** |

## Rule

> `UNKNOWN` stays where it is until adjudicated.

No file is archived until its classification is recorded in this index.

## Archive subdirectories

```
archive/
├── legacy_code/       # LEGACY_RUNTIME modules (after migration)
├── superseded_docs/   # SUPERSEDED documents
├── old_results/       # historical results that are not frozen evidence
└── INDEX.md           # this file
```

## Current archive entries

No files have been archived yet. This index will be updated as files are
classified and moved in future steps.

## Proposed future archive entries (not yet moved)

| File | Proposed classification | Reason |
|------|------------------------|--------|
| `CHANGELOG_v0.3.md` | SUPERSEDED | Replaced by current `CHANGELOG.md` |
| `v02_change_spec.py` | LEGACY_RUNTIME | v0.2 change spec; superseded |
| `semantic_pipeline.py` | LEGACY_RUNTIME | Superseded by `semantic_pipeline_v2.py` |

**No files are moved during Step 23G.**
