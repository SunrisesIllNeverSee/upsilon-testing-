# Architecture Index — Upsilon/MO§ES™

This is the **navigation entry point** for agents working in the Upsilon
repository.

## Original architectural anchor

This hardening restores an earlier intended Upsilon/MO§ES™ structure rather
than replacing working foundations with a novel architecture. The original
conceptual pipeline was approximately:

```
EDGAR
→ Agreement Chain
→ Parser
→ Commitment Extractor
→ Authoritative / validated Kernel
→ Amendment Parser
→ Authorized Change Engine
→ Commitment Lineage Graph
→ Current Authoritative Kernel
```

The target architecture makes each stage an explicit semantic home with
enforced ownership boundaries. Lineage is a first-class semantic domain,
not a logging utility.

## Architecture documents

| Document | Purpose |
|----------|---------|
| [DEPENDENCY_DIRECTION.md](DEPENDENCY_DIRECTION.md) | Controlling semantic direction and per-layer import rules |
| [REPOSITORY_MIGRATION_MANIFEST.md](REPOSITORY_MIGRATION_MANIFEST.md) | File-by-file migration plan (all rows `MOVE NOW: NO`) |
| [../moses/CONFORMANCE_CONTRACT.md](../moses/CONFORMANCE_CONTRACT.md) | MO§ES™ invariant families and enforcement status |
| [../methodology/FROZEN_ARTIFACT_POLICY.md](../methodology/FROZEN_ARTIFACT_POLICY.md) | Frozen artifact immutability rules |
| [../../.devin/rules.md](../../.devin/rules.md) | Agent governance rules |

## Current legacy architecture

The repository currently uses a **flat layout** with approximately:

- 62 runtime Python files at root
- 36 test files at root
- 12 Markdown documents at root
- 2 SQL files at root
- 7 config/data artifacts at root

This is the **CURRENT LEGACY LAYOUT**. It is not the target. See the
migration manifest for the proposed future destinations.

### Key runtime modules (legacy)

| Module | Semantic role | Boundary |
|--------|--------------|----------|
| `models.py` | shared data models (`CommitmentState`) | CLEAN |
| `amendment_parser.py` | parsing | CLEAN |
| `commitment_registry.py` | commitment identity + evidence alias matching | BOUNDARY_VIOLATION |
| `semantic_resolver_v2.py` | transformation + evidence re-extraction | BOUNDARY_VIOLATION |
| `semantic_mapper.py` | transformation + identity via section heuristics | BOUNDARY_VIOLATION |
| `semantic_pipeline_v2.py` | pipeline + authority determination | BOUNDARY_VIOLATION |
| `executor.py` | execution | CLEAN |
| `chain_reconstruction.py` | lineage + state advancement + authority | BOUNDARY_VIOLATION |
| `commitment_extractor.py` | parsing (shared extraction engine) | CLEAN |
| `persistence.py` | commitment state storage | CLEAN |

## Target architecture

```
src/upsilon/
├── ingestion/       # EDGAR acquisition, document discovery, normalization
├── parsing/         # lexical/structural parsing
├── evidence/        # source evidence representation
├── commitments/     # identity and canonical commitment state
├── transformations/ # operations over commitment state
├── conservation/    # transformation validation
├── proof/           # validated transformation evidence
├── execution/       # apply validated transformations
├── authority/       # consume execution+proof+conservation
├── lineage/         # commitment history graph (first-class domain)
├── pipeline/        # orchestration
└── models/          # shared data models
```

See `src/upsilon/README.md` and `src/upsilon/lineage/README.md` for
semantic ownership details.

## Three integrity domains

| Domain | Question | Current status |
|--------|----------|----------------|
| Transformation Integrity | Did authorized amendment evidence produce the correct successor state? | Primary focus |
| Lineage Integrity | Can the current commitment be traced through valid authorized transformations? | Scaffolded, not implemented |
| Propagation Integrity | Do downstream representations match the current authoritative kernel? | Not yet addressed |

## Audit surfaces

| Surface | Location |
|---------|----------|
| Step 23R audit | `audits/step23r/` (future home); current scripts at root |
| Failure census | `audits/failure_census/` (future home); current scripts at root |
| Forensic Q&A | `forensic_qa/` (current); `audits/forensic_qa/` (future) |

## Test surfaces

| Surface | Location |
|---------|----------|
| Unit tests | `tests/unit/` (future); current tests at root |
| Integration tests | `tests/integration/` (future) |
| Conservation tests | `tests/conservation/` (future) |
| Transformation tests | `tests/transformation/` (future) |
| Authority tests | `tests/authority/` (future) |
| Regression tests | `tests/regression/` (future) |
| Corpus tests | `tests/corpus/` (future) |
| Conformance tests | `tests/conformance/` (future) |

## Static governance

See `docs/architecture/STATIC_GOVERNANCE.md` for the distinction between
the current legacy layout and the target enforced layout, and how CI
enforcement will activate as modules migrate.
