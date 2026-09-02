# src/upsilon/lineage/ — Commitment Lineage (First-Class Semantic Domain)

Lineage is a **first-class semantic domain** in the Upsilon/MO§ES™ commitment
model, not a logging utility.

## Conceptual model

```
FC-001
  ├── Amendment 1 → threshold change
  ├── Amendment 2 → exception expansion
  └── Amendment 3 → threshold change
```

The intended model is stronger than "remember which commitment this was."
It is:

> maintain an append-only authoritative history of transformations applied
> to a persistent commitment identity

## Suggested future modules

```
src/upsilon/lineage/
├── graph.py        # commitment lineage graph
├── nodes.py        # commitment identity nodes
├── edges.py        # authorized transformation edges
├── authority.py    # authority/source linkage on edges
└── queries.py      # commitment history queries
```

**No runtime code is implemented here during Step 23G.**

## Lineage integrity

> Can the current commitment be traced through valid authorized transformations?

This is one of the three integrity domains. See `src/upsilon/README.md`.

## Conformance invariants (future)

See `docs/moses/CONFORMANCE_CONTRACT.md` for the lineage invariants that
future conformance tests must enforce, including:

- each accepted transformation creates one traceable lineage edge
- lineage edge references predecessor and successor commitment identity
- lineage edge carries amendment authority/source
- lineage edge carries transformation proof
- current authoritative state is reachable from origin kernel
- no authoritative version exists without a validated lineage path
- downstream state cannot become canonical merely by differing from current kernel

## Existing modules with lineage/state/version logic

The migration manifest identifies `chain_reconstruction.py` as a current
module containing lineage-relevant state advancement logic. It is flagged
as a candidate for migration toward this domain. No move occurs in Step 23G.
