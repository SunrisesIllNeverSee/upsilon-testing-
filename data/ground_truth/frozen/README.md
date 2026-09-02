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

## Freeze vs. verify (Step 23G.1)

The manifest generator supports two operations, kept strictly separate so
that **verification never mutates the frozen manifest**:

```
python data/ground_truth/frozen/generate_manifest.py freeze
python data/ground_truth/frozen/generate_manifest.py verify
```

**freeze** creates or refreshes `manifest.json`.  If a manifest already
exists, persisted `created_at` / `frozen_at` values are reused for every
artifact that already appears in the manifest.  Only genuinely new
artifacts receive fresh timestamps.  `generated_at` is updated (manifest
metadata, not artifact identity).

**verify** loads the existing manifest, recomputes SHA-256 hashes for
every source document, and compares against the stored values.  It
reports PASS/FAIL and **does not write to `manifest.json`**.  A
non-authoritative `verification_at` timestamp appears only in the stdout
report, never in the manifest itself.

Required principle:

```
Verify(FrozenArtifact) must not mutate FrozenManifest
```

Running `verify` twice against unchanged inputs produces zero manifest
changes by construction — `verify` never writes.  See
`test_frozen_manifest.py` for the regression test proving this.
