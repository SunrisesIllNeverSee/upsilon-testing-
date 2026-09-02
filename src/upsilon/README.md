# src/upsilon/ — Upsilon Engine Package (Target Architecture)

This is the **target home** for Upsilon runtime engine code.

As of Step 23G, this package is a **structural scaffold only**.
No production modules have been moved here yet.

See:
- `docs/architecture/ARCHITECTURE_INDEX.md` — navigation entry point
- `docs/architecture/DEPENDENCY_DIRECTION.md` — semantic authority direction
- `docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md` — file-by-file migration plan (all rows `MOVE NOW: NO`)

## Semantic subdomains

| Subdomain | Owns | May not |
|-----------|------|---------|
| `ingestion/` | EDGAR acquisition, document discovery, normalization | import execution or authority |
| `parsing/` | lexical/structural parsing of agreements and amendments | import execution or authority |
| `evidence/` | source evidence representation | grant semantic identity or authority |
| `commitments/` | commitment identity and canonical commitment state | depend on authority |
| `transformations/` | operations over commitment state consuming evidence | grant authority |
| `conservation/` | validation of transformation/state continuity | perform raw EDGAR parsing |
| `proof/` | validated semantic transformation evidence records | invent semantic interpretation |
| `execution/` | application of already-validated structured transformations | contain EDGAR lexical heuristics |
| `authority/` | consumes execution + proof + conservation status | inspect raw EDGAR text to infer meaning |
| `lineage/` | commitment history graph, nodes, edges, authority/source linkage, history queries | (see lineage README) |
| `pipeline/` | orchestration of layers | duplicate layer semantics |
| `models/` | shared data models / value objects | contain layer-specific logic |

## Lineage as a first-class domain

`src/upsilon/lineage/` is a first-class semantic domain, not a logging utility.
It owns the append-only authoritative history of transformations applied to
persistent commitment identities. See `src/upsilon/lineage/README.md`.

## Three integrity domains

| Domain | Question |
|--------|----------|
| Transformation Integrity | Did authorized amendment evidence produce the correct successor state? |
| Lineage Integrity | Can the current commitment be traced through valid authorized transformations? |
| Propagation Integrity | Do downstream representations match the current authoritative kernel? |

Current engineering work primarily addresses Transformation Integrity.
The repository preserves architectural homes for all three.
