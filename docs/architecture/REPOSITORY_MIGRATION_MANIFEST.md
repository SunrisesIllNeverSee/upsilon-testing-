# Repository Migration Manifest — Step 23G

**Every row in this manifest states `MOVE NOW: NO`.**

This manifest records the proposed future destination for every root-level file in the repository. It is a mapping, not an execution. No file is moved during Step 23G.

## Provenance

**This manifest is a human-readable projection of machine-generated data.** The imports, dependents, deferred imports, risk, and boundary columns are produced by AST analysis from `audits/repository/generate_dependency_graph.py`. The authoritative machine-readable artifacts are:

- `audits/repository/dependency_graph.json` (full per-module record)
- `audits/repository/dependency_graph.csv` (flat tabular projection)
- `audits/repository/dependency_graph_report.md` (summary report)

Regenerate this manifest with: `python audits/repository/generate_manifest.py`. Do not edit the imports/dependents columns by hand.

## Classification key

- **kind**: `runtime` | `test` | `research` | `audit` | `results` | `config` | `docs` | `data` | `legacy`
- **risk**: `LOW` | `MEDIUM` | `HIGH` — mechanically classified from dependent count (LOW <3, MEDIUM 3-7, HIGH >=8). This is **dependency/migration exposure** (how many callers must be updated when the module moves), **not** semantic criticality. A module can be HIGH risk while being semantically simple, or LOW risk while being semantically central. Future architecture work may distinguish dependency risk from semantic risk, but this manifest does not attempt that.
- **boundary**: `CLEAN` | `BOUNDARY_VIOLATION` — curated semantic judgement (see boundary violations section)
- **imports**: local modules imported at top level; `deferred:` = function/class-scope imports; `ext:` = third-party
- **dependents**: local modules that import this one; `tests:` = test modules

## Summary
```
files inventoried:                121
  Python modules (AST-analyzed):  100
  non-Python files (curated):     21
files with proposed destinations: 121
boundary violations:              7
unclassified:                     0
```

---

## 1. Runtime engine modules (20 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | imports | dependents | reason | move now |
|---|---|---|---|---|---|---|---|---|---|
| `agreement_context.py` | `src/upsilon/evidence/` | evidence | runtime | LOW | CLEAN | commitment_registry, models; deferred: commitment_registry | model_assisted_candidates; tests: test_agreement_context | agreement context and source evidence representation | NO |
| `amendment_parser.py` | `src/upsilon/parsing/` | parsing | runtime | HIGH | CLEAN | (none) | analyze_held_out_mutations, build_step23_audit, build_step23r_audit, build_unresolved_corpus, classify_development_corpus, diagnose_17b_defects, genre_adapters, produce_census_tables, semantic_pipeline, semantic_pipeline_v2; tests: test_parser_v03, test_parser_v04_regression, test_semantic_regression | parser producing structured instructions; core pipeline dependency | NO |
| `chain_reconstruction.py` | `src/upsilon/lineage/` | lineage | runtime | HIGH | BOUNDARY_VIOLATION | models, executor, persistence | analyze_held_out_mutations, chain_study_chains, edgar_chains, run_chain_study, run_chain_study_v2, run_edgar_smoke_test, run_held_out_study, run_operational_preflight, run_smoke_test, run_v2_study, semantic_pipeline, semantic_pipeline_v2, synthetic_chains; tests: test_chain_reconstruction, test_chain_study_v2, test_edgar_chains, test_step_22b_incorrect_mutation_fix | combines lineage graph with execution state advancement and authority propagation; lineage and execution layers are entangled | NO |
| `commitment_extractor.py` | `src/upsilon/parsing/` | parsing | runtime | HIGH | CLEAN | models | genre_adapters, gt_extractor, run_chain_study_v2, run_held_out_study, run_operational_preflight, run_v2_study, s0_extractor; tests: test_chain_study_v2, test_commitment_extractor, test_v02_regression | shared extraction engine used by S0 and GT extractors | NO |
| `commitment_registry.py` | `src/upsilon/commitments/` | commitments | runtime | HIGH | BOUNDARY_VIOLATION | models | agreement_context, build_step23_audit, build_unresolved_corpus, genre_adapters, model_assisted_candidates, semantic_resolver_v2; tests: test_agreement_context, test_commitment_registry | combines commitment identity with evidence alias matching and section-reference resolution; identity and evidence layers are entangled | NO |
| `discovery_validation.py` | `src/upsilon/ingestion/document_discovery/` | ingestion | runtime | LOW | CLEAN | (none) | run_operational_preflight; tests: test_v02_regression | validates acquired S0/GT documents are correct type | NO |
| `edgar_chains.py` | `src/upsilon/ingestion/edgar/` | ingestion | runtime | MEDIUM | BOUNDARY_VIOLATION | models, chain_reconstruction | chain_study_chains, run_edgar_smoke_test, semantic_pipeline; tests: test_edgar_chains, test_semantic_pipeline | combines ingestion fixtures with frozen chain data and hand-extracted states; ingestion and data layers are entangled | NO |
| `executor.py` | `src/upsilon/execution/` | execution | runtime | HIGH | CLEAN | models | analyze_held_out_mutations, build_step23r_audit, chain_reconstruction, run_operational_preflight, semantic_pipeline, semantic_pipeline_v2; tests: test_executor, test_persistence_plan, test_semantic_mapper_v01 | applies structured mutations to commitment state; deep-copies state before amendment | NO |
| `genre_adapters.py` | `src/upsilon/parsing/` | parsing | runtime | MEDIUM | CLEAN | amendment_parser, commitment_extractor, commitment_registry, models, pattern_classifier, semantic_mapper, semantic_resolver_v2 | build_step23_audit, build_step23r_audit, run_v2_study, semantic_pipeline_v2; tests: test_genre_adapters | genre-specific parsing adapters | NO |
| `gold_schema.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | (none) | create_held_out_gold, run_held_out_study; tests: test_gold_schema, test_held_out_study | independent human-verifiable gold schema definitions | NO |
| `gt_extractor.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | commitment_extractor | classify_gold_scope, run_chain_study_v2, run_held_out_study, run_v2_study; tests: test_chain_study_v2, test_commitment_extractor | independent authoritative ground-truth extractor | NO |
| `models.py` | `src/upsilon/models/` | models | runtime | HIGH | CLEAN | ext: pydantic | agreement_context, analyze_held_out_mutations, build_step23_audit, build_step23r_audit, build_unresolved_corpus, chain_reconstruction, commitment_extractor, commitment_registry, edgar_chains, executor, genre_adapters, model_assisted_candidates, persistence, run_operational_preflight, semantic_gold, semantic_mapper, semantic_pipeline, semantic_pipeline_v2, semantic_resolver_v2, synthetic_chains; tests: test_agreement_context, test_chain_reconstruction, test_chain_study, test_chain_study_v2, test_commitment_registry, test_edgar_chains, test_executor, test_false_authoritative_promotion, test_genre_adapters, test_held_out_study, test_model_assisted_candidates, test_operational_preflight, test_parser_v03, test_persistence_plan, test_semantic_mapper, test_semantic_mapper_v01, test_semantic_pipeline, test_semantic_resolver_v2, test_step22f_staged_interpreter, test_step23_audit, test_step_22b_incorrect_mutation_fix | CommitmentState and shared data models; many dependents | NO |
| `pattern_classifier.py` | `src/upsilon/parsing/` | parsing | runtime | HIGH | CLEAN | (none) | build_unresolved_corpus, chain_study_chains, genre_adapters, run_chain_study_v2, run_held_out_study, run_v2_study, semantic_pipeline_v2; tests: test_genre_adapters, test_pattern_classifier | amendment pattern classification (INCREMENTAL, FULL_RESTATEMENT, etc.) | NO |
| `persistence.py` | `src/upsilon/commitments/` | commitments | runtime | MEDIUM | CLEAN | models; ext: psycopg | chain_reconstruction, run_operational_preflight, run_step_17b; tests: test_operational_preflight, test_persistence_plan | commitment state storage and persistence planning | NO |
| `s0_extractor.py` | `src/upsilon/evidence/` | evidence | runtime | MEDIUM | CLEAN | commitment_extractor | classify_gold_scope, run_chain_study_v2, run_held_out_study, run_v2_study; tests: test_chain_study_v2, test_commitment_extractor, test_v02_regression | S0 commitment extractor producing origin state | NO |
| `sec_ingest.py` | `src/upsilon/ingestion/edgar/` | ingestion | runtime | LOW | CLEAN | ext: httpx, bs4 | (none) | SEC EDGAR ingestion logic | NO |
| `semantic_mapper.py` | `src/upsilon/transformations/` | transformations | runtime | HIGH | BOUNDARY_VIOLATION | models | analyze_held_out_mutations, build_unresolved_corpus, genre_adapters, model_assisted_candidates, semantic_gold, semantic_pipeline, semantic_pipeline_v2, semantic_resolver_v2; tests: test_model_assisted_candidates, test_semantic_mapper, test_semantic_mapper_v01 | resolves commitment identity via section-number heuristics (_section_to_commitment_id); transformation layer performs identity resolution | NO |
| `semantic_pipeline.py` | `src/upsilon/pipeline/` | pipeline | runtime | HIGH | BOUNDARY_VIOLATION | amendment_parser, chain_reconstruction, executor, models, semantic_mapper; deferred: edgar_chains | analyze_held_out_mutations, diagnose_17b_defects, run_chain_study, run_chain_study_v2, run_held_out_study, run_operational_preflight, run_step_17b; tests: test_chain_study, test_chain_study_v2, test_semantic_pipeline | legacy v1 pipeline combining orchestration + mapping + execution; superseded by v2 but still referenced by many study runners | NO |
| `semantic_pipeline_v2.py` | `src/upsilon/pipeline/` | pipeline | runtime | MEDIUM | BOUNDARY_VIOLATION | amendment_parser, chain_reconstruction, executor, genre_adapters, models, pattern_classifier, semantic_mapper, semantic_resolver_v2 | run_v2_study; tests: test_false_authoritative_promotion, test_step_22b_incorrect_mutation_fix | combines pipeline orchestration with authority determination; pipeline layer performs authority logic | NO |
| `semantic_resolver_v2.py` | `src/upsilon/transformations/` | transformations | runtime | MEDIUM | BOUNDARY_VIOLATION | commitment_registry, models, semantic_mapper | build_step23_audit, build_step23r_audit, genre_adapters, model_assisted_candidates, semantic_pipeline_v2; tests: test_semantic_resolver_v2, test_step22f_staged_interpreter | re-extracts values from source text, discarding parser-provided old/new values; transformation layer performs evidence extraction | NO |

## 2. Audit and study tooling (40 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | imports | dependents | reason | move now |
|---|---|---|---|---|---|---|---|---|---|
| `acquire_chain_study.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | ext: httpx, bs4 | acquire_comparison_sources; tests: test_chain_study | acquires EDGAR chain data for development study | NO |
| `acquire_comparison_sources.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | acquire_chain_study; ext: httpx | (none) | acquires comparison source documents | NO |
| `acquire_held_out_study.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | ext: httpx, bs4 | tests: test_held_out_study | acquires held-out study documents | NO |
| `analyze_held_out_mutations.py` | `audits/failure_census/` | audit | audit | LOW | CLEAN | run_held_out_study, semantic_pipeline, chain_reconstruction, amendment_parser, semantic_mapper, models, executor; deferred: semantic_pipeline | (none) | analyzes held-out mutation results | NO |
| `build_development_corpus.py` | `data/` | data | research | LOW | CLEAN | ext: httpx, bs4 | (none) | builds development corpus | NO |
| `build_failure_matrix.py` | `audits/failure_census/` | audit | audit | LOW | CLEAN | (none) | tests: test_build_failure_matrix, test_v02_change_spec | builds failure matrix from study results | NO |
| `build_release_package.py` | `results/release_package/` | results | results | LOW | CLEAN | (none) | tests: test_build_release_package | builds release package artifacts | NO |
| `build_step22_taxonomy.py` | `research/methodology/` | research | research | LOW | CLEAN | (none) | tests: test_step22_taxonomy | builds Step 22 taxonomy | NO |
| `build_step23_audit.py` | `audits/` | audit | audit | LOW | CLEAN | amendment_parser, commitment_registry, genre_adapters, models, run_chain_study_v2, run_held_out_study, semantic_resolver_v2 | tests: test_step23_audit | Step 23 audit script | NO |
| `build_step23r_audit.py` | `audits/step23r/` | audit | audit | LOW | CLEAN | amendment_parser, executor, genre_adapters, models, run_chain_study_v2, run_held_out_study, semantic_resolver_v2 | tests: test_step23r_audit | Step 23R record-level safety audit | NO |
| `build_unresolved_corpus.py` | `data/` | data | research | LOW | CLEAN | amendment_parser, commitment_registry, models, pattern_classifier, semantic_mapper; deferred: run_chain_study_v2, run_held_out_study | tests: test_build_unresolved_corpus | builds unresolved corpus | NO |
| `chain_study_chains.py` | `research/` | research | research | MEDIUM | CLEAN | chain_reconstruction, pattern_classifier; deferred: edgar_chains | run_chain_study, run_chain_study_v2, run_operational_preflight; tests: test_chain_study | constructs IssuerChain objects for development study | NO |
| `classify_development_corpus.py` | `data/` | data | research | LOW | CLEAN | amendment_parser | produce_census_tables; tests: test_semantic_regression | classifies development corpus entries | NO |
| `classify_gold_scope.py` | `research/methodology/` | research | research | LOW | CLEAN | deferred: s0_extractor, gt_extractor | (none) | classifies gold annotation scope | NO |
| `create_held_out_gold.py` | `data/` | data | research | LOW | CLEAN | gold_schema; deferred: gold_schema | tests: test_held_out_study | creates held-out gold annotations | NO |
| `diagnose_17b_defects.py` | `audits/` | audit | audit | LOW | CLEAN | amendment_parser, run_chain_study_v2, semantic_pipeline | (none) | diagnoses Step 17B defects | NO |
| `download_smoke_cases.py` | `src/upsilon/ingestion/` | ingestion | research | LOW | CLEAN | ext: httpx, bs4 | (none) | downloads smoke test cases | NO |
| `evaluate_parser.py` | `research/` | research | research | LOW | CLEAN | ext: pandas | (none) | parser evaluation harness | NO |
| `evaluation_layers.py` | `research/methodology/` | research | research | LOW | CLEAN | (none) | tests: test_evaluation_layers | evaluation layer separation definitions; measurement methodology | NO |
| `freeze_step_18.py` | `results/frozen/` | results | results | LOW | CLEAN | (none) | (none) | freezes Step 18 release artifacts | NO |
| `freeze_study.py` | `results/frozen/` | results | results | LOW | CLEAN | (none) | (none) | freezes study results | NO |
| `generate_defect_safety_record.py` | `audits/` | audit | audit | LOW | CLEAN | (none) | (none) | generates defect safety record | NO |
| `generate_step22_final_report.py` | `research/` | research | research | LOW | CLEAN | (none) | (none) | generates Step 22 final report | NO |
| `generate_step23_report.py` | `audits/` | audit | audit | LOW | CLEAN | (none) | tests: test_step23_audit | generates Step 23 report | NO |
| `generate_step23r_deliverables.py` | `audits/step23r/` | audit | audit | LOW | CLEAN | (none) | (none) | generates Step 23R deliverables | NO |
| `generate_step_19b_report.py` | `research/` | research | research | LOW | CLEAN | ext: scipy | tests: test_held_out_study | generates Step 19B report | NO |
| `lock_held_out_run.py` | `results/frozen/` | results | results | LOW | CLEAN | (none) | (none) | locks held-out study run | NO |
| `model_assisted_candidates.py` | `research/` | research | research | LOW | CLEAN | commitment_registry, models, semantic_mapper, semantic_resolver_v2; deferred: agreement_context | tests: test_model_assisted_candidates | model-assisted candidate generation | NO |
| `prepare_human_gold_handoff.py` | `research/` | research | research | LOW | CLEAN | (none) | (none) | prepares human gold handoff materials | NO |
| `produce_census_tables.py` | `audits/failure_census/` | audit | audit | LOW | CLEAN | amendment_parser, classify_development_corpus | (none) | produces census tables from failure data | NO |
| `record_run.py` | `research/run_records/` | research | research | LOW | CLEAN | (none) | (none) | records run metadata | NO |
| `run_chain_study.py` | `research/` | research | research | MEDIUM | CLEAN | chain_reconstruction, chain_study_chains, semantic_pipeline | run_chain_study_v2, run_held_out_study, run_v2_study; tests: test_chain_study, test_chain_study_v2 | runs development chain study | NO |
| `run_chain_study_v2.py` | `research/` | research | research | HIGH | CLEAN | chain_reconstruction, chain_study_chains, commitment_extractor, gt_extractor, run_chain_study, s0_extractor, semantic_pipeline; deferred: pattern_classifier | build_step23_audit, build_step23r_audit, build_unresolved_corpus, diagnose_17b_defects, run_held_out_study, run_operational_preflight, run_step_17b, run_v2_study; tests: test_chain_study_v2 | runs v2 chain study | NO |
| `run_edgar_smoke_test.py` | `research/` | research | research | LOW | CLEAN | chain_reconstruction, edgar_chains | (none) | runs EDGAR smoke test | NO |
| `run_held_out_study.py` | `research/` | research | research | MEDIUM | CLEAN | chain_reconstruction, commitment_extractor, gold_schema, gt_extractor, pattern_classifier, run_chain_study, run_chain_study_v2, s0_extractor, semantic_pipeline | analyze_held_out_mutations, build_step23_audit, build_step23r_audit, build_unresolved_corpus, run_v2_study; tests: test_held_out_study | runs held-out study | NO |
| `run_operational_preflight.py` | `results/preflight/` | results | results | LOW | CLEAN | chain_reconstruction, commitment_extractor, discovery_validation, executor, persistence, run_chain_study_v2, semantic_pipeline; deferred: chain_study_chains, executor, persistence, models; ext: psycopg | tests: test_operational_preflight | runs operational preflight checks | NO |
| `run_smoke_test.py` | `research/` | research | research | LOW | CLEAN | chain_reconstruction, synthetic_chains | (none) | runs smoke test | NO |
| `run_step_17b.py` | `research/` | research | research | LOW | CLEAN | persistence, run_chain_study_v2, semantic_pipeline; ext: psycopg | (none) | runs Step 17B study | NO |
| `run_v2_study.py` | `research/` | research | research | LOW | CLEAN | chain_reconstruction, commitment_extractor, genre_adapters, gt_extractor, pattern_classifier, run_chain_study, run_chain_study_v2, run_held_out_study, s0_extractor, semantic_pipeline_v2; deferred: run_chain_study_v2 | (none) | runs v2 study | NO |
| `v02_change_spec.py` | `archive/legacy_code/` | legacy | legacy | LOW | CLEAN | (none) | tests: test_v02_change_spec | v0.2 change spec derived from observed failures; superseded | NO |

## 3. Test modules (40 files)

| current path | proposed destination | semantic owner | kind | risk | boundary | imports | dependents | reason | move now |
|---|---|---|---|---|---|---|---|---|---|
| `semantic_gold.py` | `tests/corpus/` | evidence | test | LOW | CLEAN | models, semantic_mapper | tests: test_semantic_mapper_v01 | gold semantic mappings for 3 EDGAR chains; test fixture, not runtime | NO |
| `synthetic_chains.py` | `tests/corpus/` | evidence | test | LOW | CLEAN | models, chain_reconstruction | run_smoke_test; tests: test_chain_reconstruction | synthetic oracle fixtures; test data, not runtime | NO |
| `test_agreement_context.py` | `tests/unit/` | evidence | test | LOW | CLEAN | agreement_context, commitment_registry, models | (none) | tests agreement context | NO |
| `test_build_failure_matrix.py` | `tests/unit/` | audit | test | LOW | CLEAN | build_failure_matrix; ext: pytest | (none) | tests failure matrix builder | NO |
| `test_build_release_package.py` | `tests/unit/` | results | test | LOW | CLEAN | build_release_package; ext: pytest | (none) | tests release package builder | NO |
| `test_build_unresolved_corpus.py` | `tests/unit/` | data | test | LOW | CLEAN | build_unresolved_corpus; deferred: build_unresolved_corpus; ext: pytest | (none) | tests unresolved corpus builder | NO |
| `test_chain_reconstruction.py` | `tests/integration/` | lineage | test | LOW | CLEAN | chain_reconstruction, models, synthetic_chains; deferred: models | (none) | tests chain reconstruction and lineage | NO |
| `test_chain_study.py` | `tests/integration/` | research | test | LOW | CLEAN | chain_study_chains, run_chain_study, semantic_pipeline; deferred: run_chain_study, acquire_chain_study, models; ext: pytest | (none) | tests chain study | NO |
| `test_chain_study_v2.py` | `tests/integration/` | research | test | LOW | CLEAN | chain_reconstruction, commitment_extractor, run_chain_study_v2, semantic_pipeline; deferred: s0_extractor, gt_extractor, models, run_chain_study; ext: pytest | (none) | tests v2 chain study | NO |
| `test_commitment_extractor.py` | `tests/unit/` | parsing | test | LOW | CLEAN | commitment_extractor, gt_extractor, s0_extractor; deferred: commitment_extractor; ext: pytest | (none) | tests commitment extractor | NO |
| `test_commitment_registry.py` | `tests/unit/` | commitments | test | LOW | CLEAN | commitment_registry, models; ext: pytest | (none) | tests commitment registry | NO |
| `test_edgar_chains.py` | `tests/unit/` | ingestion | test | LOW | CLEAN | chain_reconstruction, edgar_chains, models | (none) | tests EDGAR chain fixtures | NO |
| `test_evaluation_layers.py` | `tests/unit/` | research | test | LOW | CLEAN | evaluation_layers; ext: pytest | (none) | tests evaluation layers | NO |
| `test_executor.py` | `tests/transformation/` | execution | test | LOW | CLEAN | models, executor | (none) | tests executor behavior | NO |
| `test_false_authoritative_promotion.py` | `tests/authority/` | authority | test | LOW | CLEAN | models, semantic_pipeline_v2; ext: pytest | (none) | tests false authoritative promotion detection | NO |
| `test_frozen_manifest.py` | `tests/governance/` | governance | test | LOW | CLEAN | ext: pytest | (none) | regression test proving frozen-manifest verification is idempotent | NO |
| `test_genre_adapters.py` | `tests/unit/` | parsing | test | LOW | CLEAN | genre_adapters, models, pattern_classifier; deferred: genre_adapters; ext: pytest | (none) | tests genre adapters | NO |
| `test_gitignore_boundary.py` | `tests/governance/` | governance | test | LOW | CLEAN | ext: pytest | (none) | verifies .gitignore frozen-source exceptions admit only .txt source evidence, not derived output | NO |
| `test_gold_schema.py` | `tests/unit/` | evidence | test | LOW | CLEAN | gold_schema | (none) | tests gold schema | NO |
| `test_held_out_study.py` | `tests/integration/` | research | test | LOW | CLEAN | gold_schema; deferred: create_held_out_gold, run_held_out_study, acquire_held_out_study, models, generate_step_19b_report; ext: pytest | (none) | tests held-out study | NO |
| `test_model_assisted_candidates.py` | `tests/unit/` | research | test | LOW | CLEAN | model_assisted_candidates, models, semantic_mapper; ext: pytest | (none) | tests model-assisted candidates | NO |
| `test_operational_preflight.py` | `tests/integration/` | results | test | LOW | CLEAN | deferred: persistence, models, run_operational_preflight; ext: pytest | (none) | tests operational preflight | NO |
| `test_parser_v03.py` | `tests/unit/` | parsing | test | LOW | CLEAN | amendment_parser; deferred: models; ext: pytest | (none) | tests parser v03 | NO |
| `test_parser_v04_regression.py` | `tests/regression/` | parsing | test | LOW | CLEAN | amendment_parser; ext: pytest | (none) | parser v04 regression tests | NO |
| `test_pattern_classifier.py` | `tests/unit/` | parsing | test | LOW | CLEAN | pattern_classifier; ext: pytest | (none) | tests pattern classifier | NO |
| `test_persistence_integration.py` | `tests/integration/` | commitments | test | LOW | CLEAN | ext: pytest | (none) | tests persistence integration | NO |
| `test_persistence_plan.py` | `tests/unit/` | commitments | test | LOW | CLEAN | models, executor, persistence | (none) | tests persistence plan | NO |
| `test_schema.py` | `tests/unit/` | models | test | LOW | CLEAN | (none) | (none) | tests schema definitions | NO |
| `test_semantic_mapper.py` | `tests/transformation/` | transformations | test | LOW | CLEAN | models, semantic_mapper | (none) | tests semantic mapper | NO |
| `test_semantic_mapper_v01.py` | `tests/transformation/` | transformations | test | LOW | CLEAN | models, semantic_mapper, semantic_gold; deferred: executor, models; ext: pytest | (none) | tests semantic mapper v01 | NO |
| `test_semantic_pipeline.py` | `tests/integration/` | pipeline | test | LOW | CLEAN | edgar_chains, models, semantic_pipeline | (none) | tests semantic pipeline | NO |
| `test_semantic_regression.py` | `tests/regression/` | pipeline | test | LOW | CLEAN | amendment_parser; deferred: amendment_parser, classify_development_corpus; ext: pytest | (none) | semantic regression tests | NO |
| `test_semantic_resolver_v2.py` | `tests/transformation/` | transformations | test | LOW | CLEAN | models, semantic_resolver_v2; ext: pytest | (none) | tests semantic resolver v2 | NO |
| `test_step22_taxonomy.py` | `tests/unit/` | research | test | LOW | CLEAN | build_step22_taxonomy | (none) | tests Step 22 taxonomy | NO |
| `test_step22f_staged_interpreter.py` | `tests/unit/` | research | test | LOW | CLEAN | semantic_resolver_v2, models | (none) | tests Step 22F staged interpreter | NO |
| `test_step23_audit.py` | `tests/regression/` | audit | test | LOW | CLEAN | build_step23_audit, generate_step23_report, models; ext: pytest | (none) | tests Step 23 audit | NO |
| `test_step23r_audit.py` | `tests/regression/` | audit | test | LOW | CLEAN | build_step23r_audit; ext: pytest | (none) | tests Step 23R audit | NO |
| `test_step_22b_incorrect_mutation_fix.py` | `tests/conservation/` | conservation | test | LOW | CLEAN | chain_reconstruction, models, semantic_pipeline_v2 | (none) | tests incorrect mutation fix | NO |
| `test_v02_change_spec.py` | `tests/regression/` | legacy | test | LOW | CLEAN | build_failure_matrix, v02_change_spec; ext: pytest | (none) | tests v02 change spec | NO |
| `test_v02_regression.py` | `tests/regression/` | legacy | test | LOW | CLEAN | commitment_extractor, discovery_validation, s0_extractor; ext: pytest | (none) | v02 regression tests | NO |

## 4. Documentation (12 files)

| current path | proposed destination | semantic owner | kind | reason | move now |
|---|---|---|---|---|---|
| `README.md` | `./ (root)` | docs | docs | repository root README; stays at root | NO |
| `CHANGELOG.md` | `./ (root)` | docs | docs | active changelog; stays at root | NO |
| `CHANGELOG_v0.3.md` | `archive/superseded_docs/` | docs | legacy | superseded changelog | NO |
| `AMENDMENT_INSTRUCTION_GRAMMAR.md` | `docs/architecture/` | parsing | docs | amendment instruction grammar specification | NO |
| `BUILD_PLAN_25_ISSUERS.md` | `docs/methodology/` | research | docs | 25-issuer build plan | NO |
| `COMMITMENT_LINEAGE_SCHEMA.md` | `docs/schemas/` | lineage | docs | commitment lineage schema specification | NO |
| `DEVELOPMENT_METHODS_RESULTS.md` | `docs/methodology/` | research | docs | development methods and results | NO |
| `GITHUB_TESTING_PROTOCOL.md` | `docs/runbooks/` | docs | docs | GitHub testing protocol | NO |
| `IP_BOUNDARY.md` | `docs/architecture/` | architecture | docs | intellectual property boundary document | NO |
| `RESEARCH_WORKFLOW_MAC.md` | `docs/runbooks/` | docs | docs | research workflow for macOS | NO |
| `RUNBOOK_PUBLISHABLE_STUDY.md` | `docs/runbooks/` | docs | docs | publishable study runbook | NO |
| `VALIDATOR_INTERFACE.md` | `docs/schemas/` | proof | docs | validator interface specification | NO |

## 5. SQL files (2 files)

| current path | proposed destination | semantic owner | kind | reason | move now |
|---|---|---|---|---|---|
| `schema.sql` | `config/sql/` | commitments | config | PostgreSQL schema definition | NO |
| `queries.sql` | `config/sql/` | commitments | config | PostgreSQL queries | NO |

## 6. Config and data artifacts (7 files)

| current path | proposed destination | semantic owner | kind | reason | move now |
|---|---|---|---|---|---|
| `pyproject.toml` | `./ (root)` | config | config | project configuration; stays at root | NO |
| `docker-compose.yml` | `config/` | config | config | docker compose configuration | NO |
| `development_corpus.csv` | `data/development/` | data | data | development corpus data | NO |
| `gold_annotations.csv` | `data/held_out/` | data | data | gold annotation data | NO |
| `issuers.csv` | `data/` | data | data | issuer list | NO |
| `predictions.csv` | `data/` | data | data | prediction data | NO |
| `smoke_cases.csv` | `data/smoke/` | data | data | smoke test cases | NO |

---

## Boundary violations discovered (7 modules)

These modules currently combine multiple semantic responsibilities. They are **not split** during Step 23G. They are flagged for future migration planning with **per-module migration preconditions**.

Each precondition must be satisfied *before* the module is moved. These are not generic "decompose first" warnings — each violation class requires a different extraction order.

| module | responsibilities combined | target split | migration preconditions |
|---|---|---|---|
| `chain_reconstruction` | lineage graph + execution state advancement + authority propagation | lineage/ (graph) + execution/ (state advancement) + authority/ (propagation) | ☐ authority and execution responsibilities extracted first<br>☐ lineage graph retained as pure graph structure in lineage/ layer |
| `commitment_registry` | commitment identity + evidence alias matching + section-reference resolution | commitments/ (identity) + evidence/ (alias/section evidence) | ☐ new identity interface exists first<br>☐ evidence alias matching extracted to evidence/ layer<br>☐ section-reference resolution extracted to evidence/ layer |
| `edgar_chains` | ingestion fixtures + frozen chain data + hand-extracted states | ingestion/edgar/ (fixtures) + data/ground_truth/frozen/ (data) | ☐ embedded frozen states externalized and hashed first<br>☐ hand-extracted states moved to data/ground_truth/frozen/ with provenance<br>☐ ingestion fixture code retained in ingestion/edgar/ layer |
| `semantic_mapper` | transformation + identity resolution via section heuristics | transformations/ (mapping) + commitments/ (identity) | ☐ commitment identity resolution moved to commitments/ layer<br>☐ transformation mapping retained in transformations/ layer |
| `semantic_pipeline` | legacy pipeline combining orchestration + mapping + execution | archive/legacy_code/ or split as v2; superseded by v2 | ☐ legacy consumers migrated to compatibility facade or retired<br>☐ v2 pipeline confirmed as functional replacement |
| `semantic_pipeline_v2` | pipeline orchestration + authority determination | pipeline/ (orchestration) + authority/ (authority logic) | ☐ authority determination extracted to authority/ layer first<br>☐ pipeline orchestration retained in pipeline/ layer |
| `semantic_resolver_v2` | transformation + evidence re-extraction (discards parser old/new values) | transformations/ (resolver) + evidence/ (value extraction) | ☐ new identity / evidence / transformation interfaces exist first<br>☐ value re-extraction moved to evidence/ layer |

## High-risk modules (mechanically classified: >= 8 dependents)

Risk here means **dependency/migration exposure** — how many callers must be updated when the module moves — **not** semantic criticality. A module can be HIGH risk while being semantically simple, or LOW risk while being semantically central. Future architecture work may distinguish dependency risk from semantic risk, but this manifest does not attempt that.

The following modules have the largest import surface and pose the highest migration risk. Any future move requires updating all dependents simultaneously. **Deferred imports are included** in the dependent count — they are easy to miss in a manual audit.

| module | runtime deps | test deps | total | deferred imports |
|---|---:|---:|---:|---|
| `models` | 20 | 21 | 41 | (none) |
| `chain_reconstruction` | 13 | 4 | 17 | (none) |
| `amendment_parser` | 10 | 3 | 13 | (none) |
| `semantic_mapper` | 8 | 3 | 11 | (none) |
| `commitment_extractor` | 7 | 3 | 10 | (none) |
| `semantic_pipeline` | 7 | 3 | 10 | edgar_chains |
| `executor` | 6 | 3 | 9 | (none) |
| `pattern_classifier` | 7 | 2 | 9 | (none) |
| `run_chain_study_v2` | 8 | 1 | 9 | pattern_classifier |
| `commitment_registry` | 6 | 2 | 8 | (none) |

## Migration execution order (future, not now)

1. Create `src/upsilon/models/` package and move `models.py` first (foundation).
2. Move clean single-responsibility modules (`executor.py`, `parsing/`).
3. Split boundary-violation modules one at a time, satisfying each module's migration preconditions, with full test coverage.
4. Move audit/research scripts last (lowest risk, fewest dependents).
5. Update `pyproject.toml`, imports, CI, and documentation after each batch.
6. At each migration checkpoint, regenerate the dependency graph and verify no new violations are introduced.

**No migration is executed in Step 23G.**
