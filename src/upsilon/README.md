# src/upsilon/ — Upsilon Engine Package (Target Architecture)

This is the **target home** for Upsilon runtime engine code.

As of Step 24 (`035daeb`), seven domains contain real runtime
implementation. Six domains remain scaffolds. One domain (`propagation/`)
is newly scaffolded in Step 23G-R.

See:
- `docs/architecture/ARCHITECTURE_INDEX.md` — navigation entry point
- `docs/architecture/DEPENDENCY_DIRECTION.md` — semantic authority direction
- `docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md` — file-by-file migration plan
- `REPOSITORY_STRUCTURE.md` — repository operating model
- `AGENTS.md` — agent entry point

## Domain status

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
| `ingestion/` | TARGET_SCAFFOLD | (`.gitkeep` only in subdirectories) |
| `parsing/` | TARGET_SCAFFOLD | (`.gitkeep` only) |
| `pipeline/` | TARGET_SCAFFOLD | (`.gitkeep` only) |
| `propagation/` | TARGET_SCAFFOLD | (`.gitkeep` only — newly created in Step 23G-R) |

Each domain has a `README.md` defining its ownership contract.

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
| `propagation/` | downstream representation comparison and propagation integrity | invent transformations or grant authority |
| `models/` | shared data models / value objects | contain layer-specific logic |

## Lineage as a first-class domain

`src/upsilon/lineage/` is a first-class semantic domain, not a logging utility.
It owns the append-only authoritative history of transformations applied to
persistent commitment identities. See `src/upsilon/lineage/README.md`.

## Three integrity domains

| Domain | Question | Current status |
|--------|----------|----------------|
| Transformation Integrity | Did authorized amendment evidence produce the correct successor state? | TARGET_ACTIVE (implemented, not yet wired into legacy pipeline) |
| Lineage Integrity | Can the current commitment be traced through valid authorized transformations? | TARGET_ACTIVE (implemented, not yet wired into legacy pipeline) |
| Propagation Integrity | Do downstream representations match the current authoritative kernel? | TARGET_SCAFFOLD (domain created, no runtime code) |

## Governing equations

```
C_t = C_{t-1} ⊕ Δ_t_authorized
```

subject to:

```
Δ_t_actual = Δ_t_authorized
C_t[f] = C_{t-1}[f]  for all f ∉ affected(Δ_t)
```

See `src/upsilon/__init__.py` for the full architecture docstring.
