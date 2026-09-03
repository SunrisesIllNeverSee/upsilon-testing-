# src/upsilon/lineage/ — Commitment Lineage Graph (First-Class Semantic Domain)

**STATUS: TARGET_ACTIVE**

## PURPOSE

Lineage is a first-class semantic domain, not a logging utility. It owns the append-only authoritative history of transformations applied to persistent commitment identities. Every accepted transformation produces a lineage edge recording what changed, why it changed, what authorized it, and what survived.

## Conceptual model

```
FC-001
  ├── Amendment 1 → threshold change
  ├── Amendment 2 → exception expansion
  └── Amendment 3 → threshold change
```

The intended model is stronger than "remember which commitment this was." It is:

> maintain an append-only authoritative history of transformations applied to a persistent commitment identity

## OWNS

- `CommitmentLineageGraph` — append-only graph of lineage edges
- `LineageEdge` records (predecessor, successor, amendment authority, transformation type, affected fields, old/new values, proof reference, validation status)
- Lineage queries (history, amendments affecting, affected fields history)
- Trace-to-origin and reachability-from-origin checks

## DOES NOT OWN

- Transformation interpretation (transformations domain)
- Authority decisions (authority domain)
- Kernel state storage (commitments domain)
- Execution (execution domain)

## ALLOWED INPUTS

- `LineageEdge` objects (from the transformation/execution pipeline)

## ALLOWED OUTPUTS

- Lineage edge retrieval and query results
- Trace-to-origin chains
- Reachability-from-origin boolean

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects, `LineageEdge`, `TransformationFamily`, `ValidationStatus`, `EdgeClass`)

## FORBIDDEN DEPENDENCIES

- `upsilon.authority` (lineage records edges; authority consumes the result)
- `upsilon.execution` (execution produces the successor state; lineage records the edge)
- `upsilon.transformations` (transformation interpretation)
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `chain_reconstruction.py` (root) — combines lineage graph with execution state advancement and authority propagation; BOUNDARY_VIOLATION; migration precondition: authority and execution responsibilities extracted first; lineage graph retained as pure graph structure

## CURRENT IMPLEMENTED TARGET MODULES

- `__init__.py` — exports `CommitmentLineageGraph`, `LineageQueries`
- `graph.py` — `CommitmentLineageGraph` (append-only, validate/reject edges, trace-to-origin, reachability)
- `queries.py` — `LineageQueries` (history, transformations-by-type, amendments-affecting, validated-history, affected-fields-history)

## CONFORMANCE INVARIANTS TOUCHED

- Lineage continuity (CONSERVATION_INVARIANTS.md §2.7): every accepted successor traces to predecessor + amendment evidence
- L1–L7 lineage conformance invariants (CONFORMANCE_CONTRACT.md)

## OPERATING STATUS

TARGET_ACTIVE — runtime implemented, 72 tests pass, not yet wired into the legacy pipeline.

## MIGRATION PRECONDITIONS

- Legacy `chain_reconstruction.py` must be decomposed: lineage graph logic → `src/upsilon/lineage/`; execution state advancement → `src/upsilon/execution/`; authority propagation → `src/upsilon/authority/`.
- Conformance tests for L1–L7 must be added under `tests/conformance/`.

## Suggested future modules

```
src/upsilon/lineage/
├── graph.py        # commitment lineage graph (IMPLEMENTED)
├── nodes.py        # commitment identity nodes (future)
├── edges.py        # authorized transformation edges (future)
├── authority.py    # authority/source linkage on edges (future)
└── queries.py      # commitment history queries (IMPLEMENTED)
```
