# Module Operating Status Classification — Step 23G-R

**Date:** 2026-09-02
**Baseline commit:** `035daeb`

## Classification keys

### `operating_status`
- `LEGACY_ACTIVE` — root module actively used in the current pipeline; no target replacement wired in yet
- `LEGACY_MAINTENANCE_ONLY` — root module retained for historical reference or compatibility; no new work expected
- `TRANSITIONAL` — root module partially replaced by target code; both exist during migration
- `TARGET_SCAFFOLD` — target domain exists but contains no runtime code
- `TARGET_ACTIVE` — target domain contains real runtime implementation
- `ARCHIVE_BLOCKED` — module flagged for archival but blocked by dependencies or frozen-artifact policy
- `ARCHIVED` — module has been moved to `archive/`

### `migration_action`
- `MOVE_AS_IS` — module can move to target domain without decomposition
- `DECOMPOSE_THEN_MOVE` — module must be split; components go to different domains
- `REPLACE_THEN_ARCHIVE` — target replacement exists; legacy module retires after consumers migrate
- `EXTERNALIZE_DATA_THEN_MOVE` — embedded data/frozen states must be externalized first
- `RETAIN_TEMPORARILY` — module stays at root for now; migration deferred
- `DO_NOT_MIGRATE` — module stays at root permanently (config, scripts, or non-runtime)

---

## 1. Target runtime modules (`src/upsilon/`)

| File | Domain | operating_status | migration_action | migration_preconditions | blocking_dependents | post_migration_validation |
|------|--------|------------------|------------------|------------------------|---------------------|---------------------------|
| `src/upsilon/__init__.py` | root | TARGET_ACTIVE | N/A | N/A (target home) | all src/upsilon modules | N/A |
| `src/upsilon/authority/__init__.py` | authority | TARGET_ACTIVE | N/A | N/A (target home) | promotion_gate.py | N/A |
| `src/upsilon/authority/promotion_gate.py` | authority | TARGET_ACTIVE | N/A | N/A (target home) | authority/__init__.py | 8 tests in TestAuthorityGate pass |
| `src/upsilon/commitments/__init__.py` | commitments | TARGET_ACTIVE | N/A | N/A (target home) | identity.py, kernel.py | N/A |
| `src/upsilon/commitments/identity.py` | commitments | TARGET_ACTIVE | N/A | N/A (target home) | kernel.py, conservation/, lineage/, proof/, transformations/ | 7 tests in TestAgreementAddressMap + TestIdentityResolver pass |
| `src/upsilon/commitments/kernel.py` | commitments | TARGET_ACTIVE | N/A | N/A (target home) | conservation/, lineage/, proof/, transformations/ | 5 tests in TestKernelStore pass |
| `src/upsilon/conservation/__init__.py` | conservation | TARGET_ACTIVE | N/A | N/A (target home) | invariants.py, validator.py | N/A |
| `src/upsilon/conservation/invariants.py` | conservation | TARGET_ACTIVE | N/A | N/A (target home) | validator.py, authority/promotion_gate.py | 6 tests in TestConservationValidator pass |
| `src/upsilon/conservation/loss_detection.py` | conservation | TARGET_ACTIVE | N/A | N/A (target home) | conservation/__init__.py | 2 tests in TestLossDetector pass |
| `src/upsilon/conservation/validator.py` | conservation | TARGET_ACTIVE | N/A | N/A (target home) | proof/transformation_proof.py | 6 tests in TestConservationValidator pass |
| `src/upsilon/lineage/__init__.py` | lineage | TARGET_ACTIVE | N/A | N/A (target home) | graph.py, queries.py | N/A |
| `src/upsilon/lineage/graph.py` | lineage | TARGET_ACTIVE | N/A | N/A (target home) | lineage/__init__.py, queries.py | 12 tests in TestCommitmentLineageGraph pass |
| `src/upsilon/lineage/queries.py` | lineage | TARGET_ACTIVE | N/A | N/A (target home) | lineage/__init__.py | 3 tests in TestLineageQueries pass |
| `src/upsilon/models/__init__.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | all src/upsilon domains | N/A |
| `src/upsilon/models/authority.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | authority/promotion_gate.py | N/A |
| `src/upsilon/models/identity.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | commitments/identity.py | N/A |
| `src/upsilon/models/kernel.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | commitments/kernel.py | N/A |
| `src/upsilon/models/lineage.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | lineage/graph.py | N/A |
| `src/upsilon/models/proof.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | proof/transformation_proof.py | N/A |
| `src/upsilon/models/transformation.py` | models | TARGET_ACTIVE | N/A | N/A (target home) | transformations/, conservation/ | N/A |
| `src/upsilon/proof/__init__.py` | proof | TARGET_ACTIVE | N/A | N/A (target home) | transformation_proof.py | N/A |
| `src/upsilon/proof/transformation_proof.py` | proof | TARGET_ACTIVE | N/A | N/A (target home) | proof/__init__.py | tests in TestProofBuilder pass |
| `src/upsilon/transformations/__init__.py` | transformations | TARGET_ACTIVE | N/A | N/A (target home) | apply.py, authorized_change.py | N/A |
| `src/upsilon/transformations/apply.py` | transformations | TARGET_ACTIVE | N/A | N/A (target home) | transformations/__init__.py | tests in TestApplyTransformation pass |
| `src/upsilon/transformations/authorized_change.py` | transformations | TARGET_ACTIVE | N/A | N/A (target home) | transformations/__init__.py | tests in TestAuthorizedTransformationEngine pass |

**Scaffold domains (no runtime code):**

| Domain | operating_status | Notes |
|--------|------------------|------|
| `src/upsilon/evidence/` | TARGET_SCAFFOLD | `.gitkeep` only |
| `src/upsilon/execution/` | TARGET_SCAFFOLD | `.gitkeep` only |
| `src/upsilon/ingestion/` | TARGET_SCAFFOLD | `.gitkeep` in `document_discovery/`, `edgar/`, `normalization/` |
| `src/upsilon/parsing/` | TARGET_SCAFFOLD | `.gitkeep` only |
| `src/upsilon/pipeline/` | TARGET_SCAFFOLD | `.gitkeep` only |
| `src/upsilon/propagation/` | TARGET_SCAFFOLD | `.gitkeep` only (newly created in Step 23G-R) |

---

## 2. Legacy runtime modules (root)

| Module | Semantic owner | operating_status | migration_action | boundary | migration_preconditions | blocking_dependents | post_migration_validation |
|--------|---------------|------------------|------------------|----------|--------------------------|---------------------|---------------------------|
| `agreement_context.py` | evidence | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | model_assisted_candidates; tests | import path update; test_agreement_context passes |
| `amendment_parser.py` | parsing | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | HIGH dependent count; update all callers | 10+ modules + tests | all callers updated; test_parser_v03 + test_parser_v04_regression pass |
| `chain_reconstruction.py` | lineage | LEGACY_ACTIVE | DECOMPOSE_THEN_MOVE | BOUNDARY_VIOLATION | authority + execution extracted first | 12+ modules + tests | lineage graph, execution, authority modules each have independent tests; test_chain_reconstruction passes against decomposed modules |
| `commitment_extractor.py` | parsing | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | HIGH dependent count | 6+ modules + tests | all callers updated; test_commitment_extractor passes |
| `commitment_registry.py` | commitments | LEGACY_ACTIVE | DECOMPOSE_THEN_MOVE | BOUNDARY_VIOLATION | identity → commitments/, evidence alias → evidence/ | 6+ modules + tests | identity and evidence modules have independent tests; test_commitment_registry + test_agreement_context pass against decomposed modules |
| `discovery_validation.py` | ingestion | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | run_operational_preflight; tests | import path update; test_v02_regression passes |
| `edgar_chains.py` | ingestion | LEGACY_ACTIVE | EXTERNALIZE_DATA_THEN_MOVE | BOUNDARY_VIOLATION | frozen states externalized + hashed first | 4+ modules + tests | frozen data hashes verified; test_edgar_chains passes against externalized data |
| `executor.py` | execution | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | HIGH dependent count | 6+ modules + tests | all callers updated; test_executor + test_persistence_plan pass |
| `genre_adapters.py` | parsing | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | imports boundary-violation modules; resolve first | 4+ modules + tests | boundary-violation dependencies resolved; test_genre_adapters passes |
| `gold_schema.py` | evidence | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | create_held_out_gold; tests | import path update; test_gold_schema passes |
| `gt_extractor.py` | evidence | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | 4+ modules + tests | all callers updated; test_commitment_extractor passes |
| `models.py` | models | TRANSITIONAL | REPLACE_THEN_ARCHIVE | CLEAN | `CommitmentKernel` replaces `CommitmentState`; compatibility layer needed | 20+ modules + tests | compatibility layer passes all legacy tests; no CommitmentState references remain in src/upsilon/ |
| `moses_safety.py` | conservation | TRANSITIONAL | REPLACE_THEN_ARCHIVE | CLEAN | target invariants implemented; reconcile overlap | tests | conservation/validator.py covers all moses_safety cases; test_moses_safety passes against conservation validator |
| `pattern_classifier.py` | parsing | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | 7+ modules + tests | import path update; test_pattern_classifier passes |
| `persistence.py` | commitments | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | chain_reconstruction; tests | import path update; test_persistence_plan + test_persistence_integration pass |
| `s0_extractor.py` | evidence | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | 4+ modules + tests | all callers updated; test_commitment_extractor + test_v02_regression pass |
| `sec_ingest.py` | ingestion | LEGACY_ACTIVE | MOVE_AS_IS | CLEAN | None blocking | None | import path update; no test coverage (LOW risk) |
| `semantic_mapper.py` | transformations | LEGACY_ACTIVE | REPLACE_THEN_ARCHIVE | BOUNDARY_VIOLATION | target `IdentityResolver` + `AuthorizedTransformationEngine` exist; wire pipeline first | 8+ modules + tests | IdentityResolver + AuthorizedTransformationEngine pass all test_semantic_mapper cases; legacy module archived |
| `semantic_pipeline.py` | pipeline | LEGACY_ACTIVE | DECOMPOSE_THEN_MOVE | BOUNDARY_VIOLATION | consumers migrated to facade or retired | 8+ modules + tests | pipeline orchestration in pipeline/; mapping in transformations/; execution in execution/; test_semantic_pipeline passes against decomposed modules |
| `semantic_pipeline_v2.py` | pipeline | LEGACY_ACTIVE | DECOMPOSE_THEN_MOVE | BOUNDARY_VIOLATION | authority logic extracted to `authority/` | run_v2_study; tests | authority in authority/; pipeline orchestration in pipeline/; test_false_authoritative_promotion + test_step_22b pass against decomposed modules |
| `semantic_resolver_v2.py` | transformations | TRANSITIONAL | REPLACE_THEN_ARCHIVE | BOUNDARY_VIOLATION | target `AuthorizedTransformationEngine` exists; wire pipeline first | 5+ modules + tests | AuthorizedTransformationEngine passes all test_semantic_resolver_v2 + test_step22f_staged_interpreter cases; legacy module archived |
| `v02_change_spec.py` | transformations | LEGACY_ACTIVE | RETAIN_TEMPORARILY | CLEAN | None | tests | N/A (retained) |
| `semantic_gold.py` | evidence | LEGACY_ACTIVE | RETAIN_TEMPORARILY | CLEAN | None | None | N/A (retained) |
| `synthetic_chains.py` | ingestion | LEGACY_ACTIVE | RETAIN_TEMPORARILY | CLEAN | None | tests | N/A (retained) |

---

## 3. Legacy research/audit/study modules (root)

These modules are research, audit, or study tooling. They are not runtime and should migrate to `audits/`, `research/`, `data/`, or `results/` — not to `src/upsilon/`.

| Module | Target location | operating_status | migration_action |
|--------|-----------------|------------------|------------------|
| `acquire_chain_study.py` | `src/upsilon/ingestion/` (research kind) | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `acquire_comparison_sources.py` | `src/upsilon/ingestion/` (research kind) | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `acquire_held_out_study.py` | `src/upsilon/ingestion/` (research kind) | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `analyze_held_out_mutations.py` | `audits/failure_census/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_development_corpus.py` | `data/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_failure_matrix.py` | `audits/failure_census/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_release_package.py` | `results/release_package/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_step22_taxonomy.py` | `research/methodology/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_step23_audit.py` | `audits/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_step23r_audit.py` | `audits/step23r/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `build_unresolved_corpus.py` | `data/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `chain_study_chains.py` | `research/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `classify_development_corpus.py` | `data/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `classify_gold_scope.py` | `research/methodology/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `create_held_out_gold.py` | `data/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `diagnose_17b_defects.py` | `audits/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `download_smoke_cases.py` | `data/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `evaluate_parser.py` | `audits/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `evaluation_layers.py` | `audits/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `freeze_step_18.py` | `results/frozen/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `freeze_study.py` | `results/frozen/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `generate_defect_safety_record.py` | `audits/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `generate_step22_final_report.py` | `results/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `generate_step23_report.py` | `results/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `generate_step23r_deliverables.py` | `results/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `generate_step_19b_report.py` | `results/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `lock_held_out_run.py` | `results/frozen/` | ARCHIVE_BLOCKED | DO_NOT_MIGRATE (frozen artifact policy) |
| `model_assisted_candidates.py` | `research/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `prepare_human_gold_handoff.py` | `data/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `produce_census_tables.py` | `audits/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `record_run.py` | `research/run_records/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `run_chain_study.py` | `research/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `run_chain_study_v2.py` | `research/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `run_edgar_smoke_test.py` | `research/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `run_held_out_study.py` | `research/` | ARCHIVE_BLOCKED | DO_NOT_MIGRATE (frozen held-out study) |
| `run_operational_preflight.py` | `research/` | LEGACY_ACTIVE | RETAIN_TEMPORARILY |
| `run_smoke_test.py` | `research/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `run_step_17b.py` | `research/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |
| `run_v2_study.py` | `research/` | LEGACY_MAINTENANCE_ONLY | RETAIN_TEMPORARILY |

---

## 4. Legacy test modules (root)

All 39 root `test_*.py` files are LEGACY_ACTIVE. They test legacy root modules and must remain at root until the modules they test are migrated. No new tests should be created at root (see `REPOSITORY_STRUCTURE.md` §C).

| Test module | Tests | operating_status |
|-------------|-------|------------------|
| `test_agreement_context.py` | agreement_context | LEGACY_ACTIVE |
| `test_build_failure_matrix.py` | build_failure_matrix | LEGACY_ACTIVE |
| `test_build_release_package.py` | build_release_package | LEGACY_ACTIVE |
| `test_build_unresolved_corpus.py` | build_unresolved_corpus | LEGACY_ACTIVE |
| `test_chain_reconstruction.py` | chain_reconstruction | LEGACY_ACTIVE |
| `test_chain_study.py` | run_chain_study | LEGACY_ACTIVE |
| `test_chain_study_v2.py` | run_chain_study_v2 | LEGACY_ACTIVE |
| `test_commitment_extractor.py` | commitment_extractor | LEGACY_ACTIVE |
| `test_commitment_registry.py` | commitment_registry | LEGACY_ACTIVE |
| `test_edgar_chains.py` | edgar_chains | LEGACY_ACTIVE |
| `test_evaluation_layers.py` | evaluation_layers | LEGACY_ACTIVE |
| `test_executor.py` | executor | LEGACY_ACTIVE |
| `test_false_authoritative_promotion.py` | semantic_pipeline_v2 | LEGACY_ACTIVE |
| `test_frozen_manifest.py` | frozen manifest governance | LEGACY_ACTIVE |
| `test_genre_adapters.py` | genre_adapters | LEGACY_ACTIVE |
| `test_gitignore_boundary.py` | .gitignore governance | LEGACY_ACTIVE |
| `test_gold_schema.py` | gold_schema | LEGACY_ACTIVE |
| `test_held_out_study.py` | run_held_out_study | ARCHIVE_BLOCKED (frozen) |
| `test_model_assisted_candidates.py` | model_assisted_candidates | LEGACY_ACTIVE |
| `test_moses_safety.py` | moses_safety | LEGACY_ACTIVE |
| `test_operational_preflight.py` | run_operational_preflight | LEGACY_ACTIVE |
| `test_parser_v03.py` | amendment_parser v0.3 | LEGACY_ACTIVE |
| `test_parser_v04_regression.py` | amendment_parser v0.4 | LEGACY_ACTIVE |
| `test_pattern_classifier.py` | pattern_classifier | LEGACY_ACTIVE |
| `test_persistence_integration.py` | persistence | LEGACY_ACTIVE |
| `test_persistence_plan.py` | persistence | LEGACY_ACTIVE |
| `test_schema.py` | schema.sql | LEGACY_ACTIVE |
| `test_semantic_mapper.py` | semantic_mapper | LEGACY_ACTIVE |
| `test_semantic_mapper_v01.py` | semantic_mapper v0.1 | LEGACY_ACTIVE |
| `test_semantic_pipeline.py` | semantic_pipeline | LEGACY_ACTIVE |
| `test_semantic_regression.py` | classify_development_corpus | LEGACY_ACTIVE |
| `test_semantic_resolver_v2.py` | semantic_resolver_v2 | LEGACY_ACTIVE |
| `test_step22_taxonomy.py` | build_step22_taxonomy | LEGACY_ACTIVE |
| `test_step22f_staged_interpreter.py` | semantic_resolver_v2 | LEGACY_ACTIVE |
| `test_step23_audit.py` | build_step23_audit | LEGACY_ACTIVE |
| `test_step23r_audit.py` | build_step23r_audit | LEGACY_ACTIVE |
| `test_step_22b_incorrect_mutation_fix.py` | semantic_pipeline_v2 | LEGACY_ACTIVE |
| `test_v02_change_spec.py` | v02_change_spec | LEGACY_ACTIVE |
| `test_v02_regression.py` | run_v2_study + discovery_validation | LEGACY_ACTIVE |

---

## 5. Target test modules (`tests/`)

| File | operating_status | Notes |
|------|------------------|-------|
| `tests/unit/test_upsilonsrc.py` | TARGET_ACTIVE | 72 tests for src/upsilon/ runtime |
| `tests/conformance/README.md` | TARGET_SCAFFOLD | Documents L1-L7 conformance invariants |
| All other `tests/*/` | TARGET_SCAFFOLD | `.gitkeep` only |

---

## Summary counts

| Category | Count |
|----------|-------|
| TARGET_ACTIVE runtime modules | 26 |
| TARGET_SCAFFOLD domains | 6 |
| LEGACY_ACTIVE runtime modules | ~24 |
| TRANSITIONAL runtime modules | 3 (models.py, moses_safety.py, semantic_resolver_v2.py) |
| LEGACY_MAINTENANCE_ONLY modules | ~12 |
| ARCHIVE_BLOCKED modules | 2 (lock_held_out_run, run_held_out_study) |
| Legacy test modules at root | 39 |
| Target test modules | 1 |
