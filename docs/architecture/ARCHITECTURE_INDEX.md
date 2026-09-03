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
| [REPOSITORY_MIGRATION_MANIFEST.md](REPOSITORY_MIGRATION_MANIFEST.md) | File-by-file migration plan (all rows `MOVE NOW: NO`); projection of machine-generated dependency graph |
| [../../audits/repository/dependency_graph_report.md](../../audits/repository/dependency_graph_report.md) | Machine-generated dependency graph report (AST analysis) |
| [../moses/CONFORMANCE_CONTRACT.md](../moses/CONFORMANCE_CONTRACT.md) | MO§ES™ invariant families and enforcement status |
| [../moses/MOSES_RUNTIME_CONTRACT.md](../moses/MOSES_RUNTIME_CONTRACT.md) | Step 23M: governing state model, runtime sequence, layer contracts |
| [../moses/COMMITMENT_IDENTITY.md](../moses/COMMITMENT_IDENTITY.md) | Step 23M Component 1: persistent agreement-local commitment identity |
| [../moses/COMMITMENT_KERNEL.md](../moses/COMMITMENT_KERNEL.md) | Step 23M Component 2: canonical commitment kernel and field categories |
| [../moses/TRANSFORMATION_ALGEBRA.md](../moses/TRANSFORMATION_ALGEBRA.md) | Step 23M Component 3: 13 transformation families and AuthorizedTransformationEngine |
| [../moses/CONSERVATION_INVARIANTS.md](../moses/CONSERVATION_INVARIANTS.md) | Step 23M Component 4: 10 conservation invariant families and alias policy |
| [../moses/SEMANTIC_PROOF_RECORD.md](../moses/SEMANTIC_PROOF_RECORD.md) | Step 23M Component 5: semantic transformation proof record schema |
| [../moses/SEMANTIC_AUTHORITY_GATE.md](../moses/SEMANTIC_AUTHORITY_GATE.md) | Step 23M Component 6: semantic authority gate contract |
| [../moses/CONFORMANCE_MATRIX.md](../moses/CONFORMANCE_MATRIX.md) | Step 23M Component 7: 18-test conformance matrix and Conformance Promotion Rule |
| [../moses/FAILURE_RECLASSIFICATION.md](../moses/FAILURE_RECLASSIFICATION.md) | Step 23M: revised failure census (0 true protocol insufficiency, 58 engine gaps) |
| [../moses/STEP24_CONSERVATION_FIRST_DESIGN.md](../moses/STEP24_CONSERVATION_FIRST_DESIGN.md) | Step 23M: Step 23S repair mapping and Step 24 implementation boundary |
| [../methodology/FROZEN_ARTIFACT_POLICY.md](../methodology/FROZEN_ARTIFACT_POLICY.md) | Frozen artifact immutability rules |
| [../../data/ground_truth/frozen/README.md](../../data/ground_truth/frozen/README.md) | Frozen ground-truth artifact inventory (inputs / reference truth) |
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
| `semantic_pipeline.py` | legacy pipeline: orchestration + mapping + execution | BOUNDARY_VIOLATION |
| `executor.py` | execution | CLEAN |
| `chain_reconstruction.py` | lineage + state advancement + authority | BOUNDARY_VIOLATION |
| `commitment_extractor.py` | parsing (shared extraction engine) | CLEAN |
| `persistence.py` | commitment state storage | CLEAN |
| `edgar_chains.py` | ingestion fixtures + frozen chain data + hand-extracted states | BOUNDARY_VIOLATION |

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
├── propagation/     # downstream representation comparison (third integrity domain)
└── models/          # shared data models
```

See `src/upsilon/README.md` and `src/upsilon/lineage/README.md` for
semantic ownership details.

## Three integrity domains

| Domain | Question | Current status |
|--------|----------|----------------|
| Transformation Integrity | Did authorized amendment evidence produce the correct successor state? | TARGET_ACTIVE (implemented in `src/upsilon/`, not yet wired into legacy pipeline) |
| Lineage Integrity | Can the current commitment be traced through valid authorized transformations? | TARGET_ACTIVE (implemented in `src/upsilon/lineage/`, not yet wired into legacy pipeline) |
| Propagation Integrity | Do downstream representations match the current authoritative kernel? | TARGET_SCAFFOLD (domain created at `src/upsilon/propagation/`, no runtime code) |

## Audit surfaces

| Surface | Location |
|---------|----------|
| Repository dependency graph | `audits/repository/` (machine-generated; AST analysis) |
| Step 23R audit | `audits/step23r/` (future home); current scripts at root |
| Failure census | `audits/failure_census/` (future home); current scripts at root |
| Forensic Q&A | `forensic_qa/` (canonical, active); `audits/forensic_qa/` (empty placeholder for future migration) |

## Test surfaces

| Surface | Location | Status |
|---------|----------|--------|
| Unit tests | `tests/unit/` | TARGET_ACTIVE (`test_upsilonsrc.py`, 72 tests); legacy tests still at root |
| Integration tests | `tests/integration/` | TARGET_SCAFFOLD |
| Conservation tests | `tests/conservation/` | TARGET_SCAFFOLD |
| Transformation tests | `tests/transformation/` | TARGET_SCAFFOLD |
| Authority tests | `tests/authority/` | TARGET_SCAFFOLD |
| Regression tests | `tests/regression/` | TARGET_SCAFFOLD |
| Corpus tests | `tests/corpus/` | TARGET_SCAFFOLD |
| Conformance tests | `tests/conformance/` | TARGET_SCAFFOLD (README documents L1-L7 invariants) |

## Static governance

See `docs/architecture/STATIC_GOVERNANCE.md` for the distinction between
the current legacy layout and the target enforced layout, and how CI
enforcement will activate as modules migrate.
