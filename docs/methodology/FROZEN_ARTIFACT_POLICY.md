# Frozen Artifact Policy

## Definition

`results/frozen/` is **immutable experimental evidence by convention**.

Frozen artifacts are the recorded output of completed experimental runs.
They exist so that subsequent analyses can reference stable evidence rather
than regenerating it under potentially different conditions.

## Rules

1. **Never overwrite frozen results.** Once an artifact is placed under
   `results/frozen/`, it must not be modified or overwritten.

2. **Never silently regenerate frozen results.** If a frozen result must be
   reproduced (e.g., for verification), the reproduction belongs under
   `results/current/` or `audits/`, not in place of the frozen artifact.

3. **New analyses reference frozen artifacts rather than replacing them.**
   Derived analyses belong under `results/current/`, `audits/`, or
   `research/`, not under `results/frozen/`.

4. **Frozen v1 remains frozen.** The v1 held-out study results are frozen.
   They must not be rerun or reconstructed without explicit authorization.

5. **Step 23R independent diagnostic truth remains traceable.** The Step 23R
   audit artifacts record a blocked diagnostic state. They must remain
   traceable to the exact code state that produced them.

6. **Derived analyses belong under `results/current/`, `audits/`, or
   `research/` rather than `results/frozen/`.** Frozen artifacts are
   evidence; derived work is interpretation.

## Current frozen artifact locations

```
results/frozen/
results/preflight/
results/release_package/
results/step23_legacy/
results/step_17b/
results/step_18_freeze/
```

## Future migration

Existing frozen artifacts under `results/step23_legacy/`, `results/step_17b/`,
and `results/step_18_freeze/` may be consolidated under `results/frozen/`
in a future administrative step. Such a move must be:

- **provably path-safe** (no import or reference breaks);
- **purely administrative** (no content change);
- **documented** in the archive index.

Do not move existing frozen artifacts during Step 23G. Document the future
migration instead.

## Frozen artifact inventory

A future inventory of frozen artifacts should record:

- artifact path
- producing step
- producing commit
- date frozen
- verification status

This inventory does not yet exist. It is a future deliverable.
