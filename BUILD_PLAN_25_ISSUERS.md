# 25-Issuer Build Plan

## Milestone 0 — Infrastructure
- PostgreSQL schema
- object storage
- EDGAR filing manifest
- deterministic document hashing
- source-span model
- audit log

## Milestone 1 — Agreement Chain Builder
Input:
- issuer CIK
- accession/exhibit metadata

Output:
- original agreement
- ordered amendment chain
- amended/restated/composite versions where available

Pass condition:
- human reviewer agrees with chain ordering and authority.

## Milestone 2 — Kernel Extraction
Start with:
- financial covenants
- events of default
- affirmative covenants
- negative covenants
- mandatory prepayments

Pass condition:
- commitment identification and key field extraction scored against human-reviewed gold set.

## Milestone 3 — Amendment Instruction Parser
Implement grammar in this order:
1. scalar replacement
2. delete
3. add
4. temporal waiver
5. exception modification
6. restate section
7. renumber/cross-reference

Pass condition:
- instruction-level exact-match and field-level accuracy on reviewed amendments.

## Milestone 4 — Formal Executor + Lineage
- prior-state guards
- atomic application
- commitment version creation
- authority link
- lineage edge
- unresolved routing

Pass condition:
- reconstructed state matches filed composite/amended-restated agreement where available.

## Milestone 5 — Propagation Engine
Represent at least one downstream artifact class:
- covenant tracker, or
- credit memo, or
- risk model configuration.

Pass condition:
- known stale representation is detected and exact mismatch is explainable.

## Milestone 6 — Upsilon UI
Views:
1. portfolio
2. commitment kernel
3. amendment impact
4. lineage
5. propagation
6. validation queue

## Initial research outputs
- reconstruction accuracy
- instruction parser accuracy
- lineage completeness
- propagation-failure prevalence

Do not lead with default prediction until these are established.
