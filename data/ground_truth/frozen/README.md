# Frozen Ground-Truth Artifacts

This directory holds **inputs / reference truth**, not outputs.

## Distinction from `results/frozen/`

| Directory | Holds | Examples |
|-----------|-------|----------|
| `data/ground_truth/frozen/` | Inputs and reference truth | hand-extracted commitment states, gold semantic mappings, frozen source-document hashes |
| `results/frozen/` | Outputs produced by runs | study results, release packages, preflight outputs |

Coupling frozen reference truth to runtime Python modules (as
`edgar_chains.py` currently does) means source refactoring and
experimental-data mutation are entangled in the same Git history. Git
cannot distinguish "refactored Python" from "changed the experimental
answer key." This directory separates them.

## Current state (Phase 1)

The frozen states are **not yet externalized**. They are still embedded in:

- `edgar_chains.py` — 3 EDGAR chain ground-truth states (ameresco, amedisys, bausch_lomb)
- `semantic_gold.py` — gold semantic mappings for 3 EDGAR chains

The `manifest.json` in this directory inventories what exists, where it
lives now, where it should move, and hashes the source documents so that
future extraction can be verified against unchanged inputs.

## Externalization (Phase 2 precondition)

Externalizing the embedded states is a **migration precondition** for
moving `edgar_chains.py`. See the per-module migration preconditions in
`docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md`.

The externalization process:

1. Extract each ground-truth state to a JSON file under
   `edgar_chain_states/` or `semantic_gold/`.
2. Compute the SHA-256 hash of the extracted JSON.
3. Update `manifest.json` with the hash and set `externalization_status`
   to `externalized`.
4. Verify that the source document hashes in `manifest.json` match the
   current `data/edgar_chains/` files (inputs unchanged).
5. Replace the embedded Python objects with loaders that read from the
   JSON files.

## CI verification

Once externalized, CI can verify the hash set:

- source document hashes match `data/edgar_chains/`
- externalized state hashes match `data/ground_truth/frozen/`
- `mutable` is `false` for all entries
- no entry is modified after `frozen_at`

This turns "frozen" into something enforceable instead of ceremonial.

## Regenerating the manifest

```
python data/ground_truth/frozen/generate_manifest.py
```
