# Repository Migration Manifest — Step 23G

**Every row in this manifest states `MOVE NOW: NO`.**

This manifest records the proposed future destination for every root-level
file in the repository. It is a mapping, not an execution. No file is moved
during Step 23G.

## Classification key

- **kind**: `runtime` | `test` | `research` | `audit` | `results` | `config` | `docs` | `data` | `legacy`
- **risk**: `LOW` | `MEDIUM` | `HIGH` — based on number of dependents and import surface
- **boundary**: `CLEAN` | `BOUNDARY_VIOLATION` — whether the module combines multiple semantic responsibilities

## Summary

```
files inventoried:              119
files with proposed destinations: 119
boundary violations:              7
unclassified:                     0
```

---

## 1. Runtime engine modules (62 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | reason | move now |
|---|---|---|---|---|---|---|---|
| `models.py` | `src/upsilon/models/` | models | runtime | HIGH | CLEAN | `CommitmentState` and shared data models; many dependents | NO |
| `amendment_parser.py` | `src/upsilon/parsing/` | parsing | runtime | HIGH | CLEAN | parser producing structured instructions; core pipeline dependency | NO |
| `commitment_registry.py` | `src/upsilon/commitments/` | commitments | runtime | HIGH | BOUNDARY_VIOLATION | combines commitment identity with evidence alias matching and section-reference resolution; identity and evidence layers are entangled | NO |
| `semantic_resolver_v2.py` | `src/upsilon/transformations/` | transformations | runtime | HIGH | BOUNDARY_VIOLATION | re-extracts values from source text, discarding parser-provided old/new values; transformation layer performs evidence extraction | NO |
| `semantic_mapper.py` | `src/upsilon/transformations/` | transformations | runtime | HIGH | BOUNDARY_VIOLATION | resolves commitment identity via section-number heuristics (`_section_to_commitment_id`); transformation layer performs identity resolution | NO |
| `semantic_pipeline_v2.py` | `src/upsilon/pipeline/` | pipeline | runtime | HIGH | BOUNDARY_VIOLATION | combines pipeline orchestration with authority determination; pipeline layer performs authority logic | NO |
| `semantic_pipeline.py` | `src/upsilon/pipeline/` | pipeline | runtime | MEDIUM | CLEAN | legacy v1 pipeline; superseded by v2 but still referenced | NO |
| `executor.py` | `src/upsilon/execution/` | execution | runtime | HIGH | CLEAN | applies structured mutations to commitment state; deep-copies state before amendment | NO |
| `genre_adapters.py` | `src/upsilon/parsing/` | parsing | runtime | MEDIUM | CLEAN | genre-specific parsing adapters | NO |
| `commitment_extractor.py` | `src/upsilon/parsing/` | parsing | runtime | HIGH | CLEAN | shared extraction engine used by S0 and GT extractors | NO |
| `chain_reconstruction.py` | `src/upsilon/lineage/` | lineage | runtime | HIGH | BOUNDARY_VIOLATION | combines lineage graph with execution state advancement and authority propagation; lineage and execution layers are entangled | NO |
| `persistence.py` | `src/upsilon/commitments/` | commitments | runtime | MEDIUM | CLEAN | commitment state storage and persistence planning | NO |
| `agreement_context.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | agreement context and source evidence representation | NO |
| `pattern_classifier.py` | `src/upsilon/parsing/` | parsing | runtime | MEDIUM | CLEAN | amendment pattern classification (INCREMENTAL, FULL_RESTATEMENT, etc.) | NO |
| `gold_schema.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | independent human-verifiable gold schema definitions | NO |
| `semantic_gold.py` | `tests/corpus/` | evidence | test | MEDIUM | CLEAN | gold semantic mappings for 3 EDGAR chains; test fixture, not runtime | NO |
| `gt_extractor.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | independent authoritative ground-truth extractor | NO |
| `s0_extractor.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | S0 commitment extractor producing origin state | NO |
| `v02_change_spec.py` | `archive/legacy_code/` | legacy | legacy | LOW | CLEAN | v0.2 change spec derived from observed failures; superseded | NO |
| `evaluation_layers.py` | `research/methodology/` | research | research | LOW | CLEAN | evaluation layer separation definitions; measurement methodology | NO |
| `edgar_chains.py` | `src/upsilon/ingestion/edgar/` | ingestion | runtime | MEDIUM | CLEAN | frozen EDGAR chain fixtures for chains 1-3 | NO |
| `sec_ingest.py` | `src/upsilon/ingestion/edgar/` | ingestion | runtime | MEDIUM | CLEAN | SEC EDGAR ingestion logic | NO |
| `discovery_validation.py` | `src/upsilon/ingestion/document_discovery/` | ingestion | runtime | LOW | CLEAN | validates acquired S0/GT documents are correct type | NO |
| `synthetic_chains.py` | `tests/corpus/` | evidence | test | MEDIUM | CLEAN | synthetic oracle fixtures; test data, not runtime | NO |

## 2. Audit and study tooling (38 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | reason | move now |
|---|---|---|---|---|---|---|---|
| `acquire_chain_study.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | acquires EDGAR chain data for development study | NO |
| `acquire_comparison_sources.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | acquires comparison source documents | NO |
| `acquire_held_out_study.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | acquires held-out study documents | NO |
| `analyze_held_out_mutations.py` | `audits/failure_census/` | audit | audit | LOW | CLEAN | analyzes held-out mutation results | NO |
| `build_development_corpus.py` | `data/` | data | research | LOW | CLEAN | builds development corpus | NO |
| `build_failure_matrix.py` | `audits/failure_census/` | audit | audit | LOW | CLEAN | builds failure matrix from study results | NO |
| `build_release_package.py` | `results/release_package/` | results | results | LOW | CLEAN | builds release package artifacts | NO |
| `build_step22_taxonomy.py` | `research/methodology/` | research | research | LOW | CLEAN | builds Step 22 taxonomy | NO |
| `build_step23_audit.py` | `audits/` | audit | audit | LOW | CLEAN | Step 23 audit script | NO |
| `build_step23r_audit.py` | `audits/step23r/` | audit | audit | LOW | CLEAN | Step 23R record-level safety audit | NO |
| `build_unresolved_corpus.py` | `data/` | data | research | LOW | CLEAN | builds unresolved corpus | NO |
| `chain_study_chains.py` | `research/` | research | research | LOW | CLEAN | constructs IssuerChain objects for development study | NO |
| `classify_development_corpus.py` | `data/` | data | research | LOW | CLEAN | classifies development corpus entries | NO |
| `classify_gold_scope.py` | `research/methodology/` | research | research | LOW | CLEAN | classifies gold annotation scope | NO |
| `create_held_out_gold.py` | `data/` | data | research | LOW | CLEAN | creates held-out gold annotations | NO |
| `diagnose_17b_defects.py` | `audits/` | audit | audit | LOW | CLEAN | diagnoses Step 17B defects | NO |
| `download_smoke_cases.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | downloads smoke test cases | NO |
| `evaluate_parser.py` | `research/` | research | research | LOW | CLEAN | parser evaluation harness | NO |
| `freeze_step_18.py` | `results/frozen/` | results | results | LOW | CLEAN | freezes Step 18 release artifacts | NO |
| `freeze_study.py` | `results/frozen/` | results | results | LOW | CLEAN | freezes study results | NO |
| `generate_defect_safety_record.py` | `audits/` | audit | audit | LOW | CLEAN | generates defect safety record | NO |
| `generate_step22_final_report.py` | `research/` | research | research | LOW | CLEAN | generates Step 22 final report | NO |
| `generate_step23_report.py` | `audits/` | audit | audit | LOW | CLEAN | generates Step 23 report | NO |
| `generate_step23r_deliverables.py` | `audits/step23r/` | audit | audit | LOW | CLEAN | generates Step 23R deliverables | NO |
| `generate_step_19b_report.py` | `research/` | research | research | LOW | CLEAN | generates Step 19B report | NO |
| `lock_held_out_run.py` | `results/frozen/` | results | results | LOW | CLEAN | locks held-out study run | NO |
| `model_assisted_candidates.py` | `research/` | research | research | LOW | CLEAN | model-assisted candidate generation | NO |
| `prepare_human_gold_handoff.py` | `research/` | research | research | LOW | CLEAN | prepares human gold handoff materials | NO |
| `produce_census_tables.py` | `audits/failure_census/` | audit | audit | LOW | CLEAN | produces census tables from failure data | NO |
| `record_run.py` | `research/run_records/` | research | research | LOW | CLEAN | records run metadata | NO |
| `run_chain_study.py` | `research/` | research | research | LOW | CLEAN | runs development chain study | NO |
| `run_chain_study_v2.py` | `research/` | research | research | LOW | CLEAN | runs v2 chain study | NO |
| `run_edgar_smoke_test.py` | `research/` | research | research | LOW | CLEAN | runs EDGAR smoke test | NO |
| `run_held_out_study.py` | `research/` | research | research | LOW | CLEAN | runs held-out study | NO |
| `run_operational_preflight.py` | `results/preflight/` | results | results | LOW | CLEAN | runs operational preflight checks | NO |
| `run_smoke_test.py` | `research/` | research | research | LOW | CLEAN | runs smoke test | NO |
| `run_step_17b.py` | `research/` | research | research | LOW | CLEAN | runs Step 17B study | NO |
| `run_v2_study.py` | `research/` | research | research | LOW | CLEAN | runs v2 study | NO |

## 3. Test modules (36 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | reason | move now |
|---|---|---|---|---|---|---|---|
| `test_agreement_context.py` | `tests/unit/` | evidence | test | LOW | CLEAN | tests agreement context | NO |
| `test_build_failure_matrix.py` | `tests/unit/` | audit | test | LOW | CLEAN | tests failure matrix builder | NO |
| `test_build_release_package.py` | `tests/unit/` | results | test | LOW | CLEAN | tests release package builder | NO |
| `test_build_unresolved_corpus.py` | `tests/unit/` | data | test | LOW | CLEAN | tests unresolved corpus builder | NO |
| `test_chain_reconstruction.py` | `tests/integration/` | lineage | test | MEDIUM | CLEAN | tests chain reconstruction and lineage | NO |
| `test_chain_study.py` | `tests/integration/` | research | test | LOW | CLEAN | tests chain study | NO |
| `test_chain_study_v2.py` | `tests/integration/` | research | test | LOW | CLEAN | tests v2 chain study | NO |
| `test_commitment_extractor.py` | `tests/unit/` | parsing | test | LOW | CLEAN | tests commitment extractor | NO |
| `test_commitment_registry.py` | `tests/unit/` | commitments | test | LOW | CLEAN | tests commitment registry | NO |
| `test_edgar_chains.py` | `tests/unit/` | ingestion | test | LOW | CLEAN | tests EDGAR chain fixtures | NO |
| `test_evaluation_layers.py` | `tests/unit/` | research | test | LOW | CLEAN | tests evaluation layers | NO |
| `test_executor.py` | `tests/transformation/` | execution | test | MEDIUM | CLEAN | tests executor behavior | NO |
| `test_false_authoritative_promotion.py` | `tests/authority/` | authority | test | MEDIUM | CLEAN | tests false authoritative promotion detection | NO |
| `test_genre_adapters.py` | `tests/unit/` | parsing | test | LOW | CLEAN | tests genre adapters | NO |
| `test_gold_schema.py` | `tests/unit/` | evidence | test | LOW | CLEAN | tests gold schema | NO |
| `test_held_out_study.py` | `tests/integration/` | research | test | LOW | CLEAN | tests held-out study | NO |
| `test_model_assisted_candidates.py` | `tests/unit/` | research | test | LOW | CLEAN | tests model-assisted candidates | NO |
| `test_operational_preflight.py` | `tests/integration/` | results | test | LOW | CLEAN | tests operational preflight | NO |
| `test_parser_v03.py` | `tests/unit/` | parsing | test | LOW | CLEAN | tests parser v03 | NO |
| `test_parser_v04_regression.py` | `tests/regression/` | parsing | test | LOW | CLEAN | parser v04 regression tests | NO |
| `test_pattern_classifier.py` | `tests/unit/` | parsing | test | LOW | CLEAN | tests pattern classifier | NO |
| `test_persistence_integration.py` | `tests/integration/` | commitments | test | LOW | CLEAN | tests persistence integration | NO |
| `test_persistence_plan.py` | `tests/unit/` | commitments | test | LOW | CLEAN | tests persistence plan | NO |
| `test_schema.py` | `tests/unit/` | models | test | LOW | CLEAN | tests schema definitions | NO |
| `test_semantic_mapper.py` | `tests/transformation/` | transformations | test | MEDIUM | CLEAN | tests semantic mapper | NO |
| `test_semantic_mapper_v01.py` | `tests/transformation/` | transformations | test | MEDIUM | CLEAN | tests semantic mapper v01 | NO |
| `test_semantic_pipeline.py` | `tests/integration/` | pipeline | test | MEDIUM | CLEAN | tests semantic pipeline | NO |
| `test_semantic_regression.py` | `tests/regression/` | pipeline | test | MEDIUM | CLEAN | semantic regression tests | NO |
| `test_semantic_resolver_v2.py` | `tests/transformation/` | transformations | test | MEDIUM | CLEAN | tests semantic resolver v2 | NO |
| `test_step22_taxonomy.py` | `tests/unit/` | research | test | LOW | CLEAN | tests Step 22 taxonomy | NO |
| `test_step22f_staged_interpreter.py` | `tests/unit/` | research | test | LOW | CLEAN | tests Step 22F staged interpreter | NO |
| `test_step23_audit.py` | `tests/regression/` | audit | test | LOW | CLEAN | tests Step 23 audit | NO |
| `test_step23r_audit.py` | `tests/regression/` | audit | test | LOW | CLEAN | tests Step 23R audit | NO |
| `test_step_22b_incorrect_mutation_fix.py` | `tests/conservation/` | conservation | test | MEDIUM | CLEAN | tests incorrect mutation fix | NO |
| `test_v02_change_spec.py` | `tests/regression/` | legacy | test | LOW | CLEAN | tests v02 change spec | NO |
| `test_v02_regression.py` | `tests/regression/` | legacy | test | LOW | CLEAN | v02 regression tests | NO |

## 4. Documentation (12 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | reason | move now |
|---|---|---|---|---|---|---|---|
| `README.md` | `./` (root) | docs | docs | LOW | CLEAN | repository root README; stays at root | NO |
| `CHANGELOG.md` | `./` (root) | docs | docs | LOW | CLEAN | active changelog; stays at root | NO |
| `CHANGELOG_v0.3.md` | `archive/superseded_docs/` | docs | legacy | LOW | CLEAN | superseded changelog | NO |
| `AMENDMENT_INSTRUCTION_GRAMMAR.md` | `docs/architecture/` | parsing | docs | LOW | CLEAN | amendment instruction grammar specification | NO |
| `BUILD_PLAN_25_ISSUERS.md` | `docs/methodology/` | research | docs | LOW | CLEAN | 25-issuer build plan | NO |
| `COMMITMENT_LINEAGE_SCHEMA.md` | `docs/schemas/` | lineage | docs | LOW | CLEAN | commitment lineage schema specification | NO |
| `DEVELOPMENT_METHODS_RESULTS.md` | `docs/methodology/` | research | docs | LOW | CLEAN | development methods and results | NO |
| `GITHUB_TESTING_PROTOCOL.md` | `docs/runbooks/` | docs | docs | LOW | CLEAN | GitHub testing protocol | NO |
| `IP_BOUNDARY.md` | `docs/architecture/` | architecture | docs | LOW | CLEAN | intellectual property boundary document | NO |
| `RESEARCH_WORKFLOW_MAC.md` | `docs/runbooks/` | docs | docs | LOW | CLEAN | research workflow for macOS | NO |
| `RUNBOOK_PUBLISHABLE_STUDY.md` | `docs/runbooks/` | docs | docs | LOW | CLEAN | publishable study runbook | NO |
| `VALIDATOR_INTERFACE.md` | `docs/schemas/` | proof | docs | LOW | CLEAN | validator interface specification | NO |

## 5. SQL files (2 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | reason | move now |
|---|---|---|---|---|---|---|---|
| `schema.sql` | `config/sql/` | commitments | config | LOW | CLEAN | PostgreSQL schema definition | NO |
| `queries.sql` | `config/sql/` | commitments | config | LOW | CLEAN | PostgreSQL queries | NO |

## 6. Config and data artifacts (7 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | reason | move now |
|---|---|---|---|---|---|---|---|
| `pyproject.toml` | `./` (root) | config | config | LOW | CLEAN | project configuration; stays at root | NO |
| `docker-compose.yml` | `config/` | config | config | LOW | CLEAN | docker compose configuration | NO |
| `development_corpus.csv` | `data/development/` | data | data | LOW | CLEAN | development corpus data | NO |
| `gold_annotations.csv` | `data/held_out/` | data | data | LOW | CLEAN | gold annotation data | NO |
| `issuers.csv` | `data/` | data | data | LOW | CLEAN | issuer list | NO |
| `predictions.csv` | `data/` | data | data | LOW | CLEAN | prediction data | NO |
| `smoke_cases.csv` | `data/smoke/` | data | data | LOW | CLEAN | smoke test cases | NO |

---

## Boundary violations discovered (7 modules)

These modules currently combine multiple semantic responsibilities.
They are **not split** during Step 23G. They are flagged for future
migration planning.

| module | responsibilities combined | target split |
|---|---|---|
| `commitment_registry.py` | commitment identity + evidence alias matching + section-reference resolution | `commitments/` (identity) + `evidence/` (alias/section evidence) |
| `semantic_resolver_v2.py` | transformation + evidence re-extraction (discards parser old/new values) | `transformations/` (resolver) + `evidence/` (value extraction) |
| `semantic_mapper.py` | transformation + identity resolution via section heuristics | `transformations/` (mapping) + `commitments/` (identity) |
| `semantic_pipeline_v2.py` | pipeline orchestration + authority determination | `pipeline/` (orchestration) + `authority/` (authority logic) |
| `chain_reconstruction.py` | lineage graph + execution state advancement + authority propagation | `lineage/` (graph) + `execution/` (state advancement) + `authority/` (propagation) |
| `edgar_chains.py` | ingestion fixtures + frozen chain data + hand-extracted states | `ingestion/edgar/` (fixtures) + `data/edgar_chains/` (data) |
| `semantic_pipeline.py` | legacy pipeline combining orchestration + mapping + execution | `archive/legacy_code/` or split as v2; superseded by v2 |

## Known import dependencies (high-risk modules)

The following modules have the largest import surface and pose the highest
migration risk. Any future move requires updating all dependents
simultaneously.

- `models.py` — imported by nearly every runtime and test module
- `amendment_parser.py` — imported by pipeline, resolver, tests
- `executor.py` — imported by pipeline, chain reconstruction, tests
- `commitment_registry.py` — imported by resolver, mapper, pipeline
- `semantic_resolver_v2.py` — imported by pipeline, tests
- `semantic_mapper.py` — imported by pipeline, resolver, tests
- `semantic_pipeline_v2.py` — imported by study runners, tests
- `chain_reconstruction.py` — imported by study runners, tests
- `commitment_extractor.py` — imported by s0_extractor, gt_extractor, tests

## Migration execution order (future, not now)

1. Create `src/upsilon/models/` package and move `models.py` first (foundation).
2. Move clean single-responsibility modules (`executor.py`, `parsing/`).
3. Split boundary-violation modules one at a time with full test coverage.
4. Move audit/research scripts last (lowest risk, fewest dependents).
5. Update `pyproject.toml`, imports, CI, and documentation after each batch.

**No migration is executed in Step 23G.**
