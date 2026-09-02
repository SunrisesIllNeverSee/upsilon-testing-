"""Project the machine-generated dependency graph into the Markdown manifest.

This script reads ``audits/repository/dependency_graph.json`` (produced by
``generate_dependency_graph.py``) and writes
``docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md`` as a human-readable
projection.  The manifest must never be edited by hand; regenerate it with::

    python audits/repository/generate_manifest.py

The proposed-destination, semantic-owner, kind, and reason columns are
curated mappings (semantic judgements that cannot be derived from the import
graph).  The imports/dependents/risk/boundary columns are projections of the
machine-generated data.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPO_ROOT / "audits" / "repository" / "dependency_graph.json"
MANIFEST_PATH = REPO_ROOT / "docs" / "architecture" / "REPOSITORY_MIGRATION_MANIFEST.md"

# ---------------------------------------------------------------------------
# Curated semantic mappings (not derivable from imports)
# ---------------------------------------------------------------------------

MODULE_META: dict[str, dict] = {
    # --- runtime engine ---
    "models": {"dest": "src/upsilon/models/", "owner": "models", "kind": "runtime", "reason": "CommitmentState and shared data models; many dependents"},
    "amendment_parser": {"dest": "src/upsilon/parsing/", "owner": "parsing", "kind": "runtime", "reason": "parser producing structured instructions; core pipeline dependency"},
    "commitment_registry": {"dest": "src/upsilon/commitments/", "owner": "commitments", "kind": "runtime", "reason": "combines commitment identity with evidence alias matching and section-reference resolution; identity and evidence layers are entangled"},
    "semantic_resolver_v2": {"dest": "src/upsilon/transformations/", "owner": "transformations", "kind": "runtime", "reason": "re-extracts values from source text, discarding parser-provided old/new values; transformation layer performs evidence extraction"},
    "semantic_mapper": {"dest": "src/upsilon/transformations/", "owner": "transformations", "kind": "runtime", "reason": "resolves commitment identity via section-number heuristics (_section_to_commitment_id); transformation layer performs identity resolution"},
    "semantic_pipeline_v2": {"dest": "src/upsilon/pipeline/", "owner": "pipeline", "kind": "runtime", "reason": "combines pipeline orchestration with authority determination; pipeline layer performs authority logic"},
    "semantic_pipeline": {"dest": "src/upsilon/pipeline/", "owner": "pipeline", "kind": "runtime", "reason": "legacy v1 pipeline combining orchestration + mapping + execution; superseded by v2 but still referenced by many study runners"},
    "executor": {"dest": "src/upsilon/execution/", "owner": "execution", "kind": "runtime", "reason": "applies structured mutations to commitment state; deep-copies state before amendment"},
    "genre_adapters": {"dest": "src/upsilon/parsing/", "owner": "parsing", "kind": "runtime", "reason": "genre-specific parsing adapters"},
    "commitment_extractor": {"dest": "src/upsilon/parsing/", "owner": "parsing", "kind": "runtime", "reason": "shared extraction engine used by S0 and GT extractors"},
    "chain_reconstruction": {"dest": "src/upsilon/lineage/", "owner": "lineage", "kind": "runtime", "reason": "combines lineage graph with execution state advancement and authority propagation; lineage and execution layers are entangled"},
    "persistence": {"dest": "src/upsilon/commitments/", "owner": "commitments", "kind": "runtime", "reason": "commitment state storage and persistence planning"},
    "agreement_context": {"dest": "src/upsilon/evidence/", "owner": "evidence", "kind": "runtime", "reason": "agreement context and source evidence representation"},
    "pattern_classifier": {"dest": "src/upsilon/parsing/", "owner": "parsing", "kind": "runtime", "reason": "amendment pattern classification (INCREMENTAL, FULL_RESTATEMENT, etc.)"},
    "gold_schema": {"dest": "src/upsilon/evidence/", "owner": "evidence", "kind": "runtime", "reason": "independent human-verifiable gold schema definitions"},
    "semantic_gold": {"dest": "tests/corpus/", "owner": "evidence", "kind": "test", "reason": "gold semantic mappings for 3 EDGAR chains; test fixture, not runtime"},
    "gt_extractor": {"dest": "src/upsilon/evidence/", "owner": "evidence", "kind": "runtime", "reason": "independent authoritative ground-truth extractor"},
    "s0_extractor": {"dest": "src/upsilon/evidence/", "owner": "evidence", "kind": "runtime", "reason": "S0 commitment extractor producing origin state"},
    "v02_change_spec": {"dest": "archive/legacy_code/", "owner": "legacy", "kind": "legacy", "reason": "v0.2 change spec derived from observed failures; superseded"},
    "evaluation_layers": {"dest": "research/methodology/", "owner": "research", "kind": "research", "reason": "evaluation layer separation definitions; measurement methodology"},
    "edgar_chains": {"dest": "src/upsilon/ingestion/edgar/", "owner": "ingestion", "kind": "runtime", "reason": "combines ingestion fixtures with frozen chain data and hand-extracted states; ingestion and data layers are entangled"},
    "sec_ingest": {"dest": "src/upsilon/ingestion/edgar/", "owner": "ingestion", "kind": "runtime", "reason": "SEC EDGAR ingestion logic"},
    "discovery_validation": {"dest": "src/upsilon/ingestion/document_discovery/", "owner": "ingestion", "kind": "runtime", "reason": "validates acquired S0/GT documents are correct type"},
    "synthetic_chains": {"dest": "tests/corpus/", "owner": "evidence", "kind": "test", "reason": "synthetic oracle fixtures; test data, not runtime"},
    # --- audit and study tooling ---
    "acquire_chain_study": {"dest": "src/upsilon/ingestion/", "owner": "ingestion", "kind": "research", "reason": "acquires EDGAR chain data for development study"},
    "acquire_comparison_sources": {"dest": "src/upsilon/ingestion/", "owner": "ingestion", "kind": "research", "reason": "acquires comparison source documents"},
    "acquire_held_out_study": {"dest": "src/upsilon/ingestion/", "owner": "ingestion", "kind": "research", "reason": "acquires held-out study documents"},
    "analyze_held_out_mutations": {"dest": "audits/failure_census/", "owner": "audit", "kind": "audit", "reason": "analyzes held-out mutation results"},
    "build_development_corpus": {"dest": "data/", "owner": "data", "kind": "research", "reason": "builds development corpus"},
    "build_failure_matrix": {"dest": "audits/failure_census/", "owner": "audit", "kind": "audit", "reason": "builds failure matrix from study results"},
    "build_release_package": {"dest": "results/release_package/", "owner": "results", "kind": "results", "reason": "builds release package artifacts"},
    "build_step22_taxonomy": {"dest": "research/methodology/", "owner": "research", "kind": "research", "reason": "builds Step 22 taxonomy"},
    "build_step23_audit": {"dest": "audits/", "owner": "audit", "kind": "audit", "reason": "Step 23 audit script"},
    "build_step23r_audit": {"dest": "audits/step23r/", "owner": "audit", "kind": "audit", "reason": "Step 23R record-level safety audit"},
    "build_unresolved_corpus": {"dest": "data/", "owner": "data", "kind": "research", "reason": "builds unresolved corpus"},
    "chain_study_chains": {"dest": "research/", "owner": "research", "kind": "research", "reason": "constructs IssuerChain objects for development study"},
    "classify_development_corpus": {"dest": "data/", "owner": "data", "kind": "research", "reason": "classifies development corpus entries"},
    "classify_gold_scope": {"dest": "research/methodology/", "owner": "research", "kind": "research", "reason": "classifies gold annotation scope"},
    "create_held_out_gold": {"dest": "data/", "owner": "data", "kind": "research", "reason": "creates held-out gold annotations"},
    "diagnose_17b_defects": {"dest": "audits/", "owner": "audit", "kind": "audit", "reason": "diagnoses Step 17B defects"},
    "download_smoke_cases": {"dest": "src/upsilon/ingestion/", "owner": "ingestion", "kind": "research", "reason": "downloads smoke test cases"},
    "evaluate_parser": {"dest": "research/", "owner": "research", "kind": "research", "reason": "parser evaluation harness"},
    "freeze_step_18": {"dest": "results/frozen/", "owner": "results", "kind": "results", "reason": "freezes Step 18 release artifacts"},
    "freeze_study": {"dest": "results/frozen/", "owner": "results", "kind": "results", "reason": "freezes study results"},
    "generate_defect_safety_record": {"dest": "audits/", "owner": "audit", "kind": "audit", "reason": "generates defect safety record"},
    "generate_step22_final_report": {"dest": "research/", "owner": "research", "kind": "research", "reason": "generates Step 22 final report"},
    "generate_step23_report": {"dest": "audits/", "owner": "audit", "kind": "audit", "reason": "generates Step 23 report"},
    "generate_step23r_deliverables": {"dest": "audits/step23r/", "owner": "audit", "kind": "audit", "reason": "generates Step 23R deliverables"},
    "generate_step_19b_report": {"dest": "research/", "owner": "research", "kind": "research", "reason": "generates Step 19B report"},
    "lock_held_out_run": {"dest": "results/frozen/", "owner": "results", "kind": "results", "reason": "locks held-out study run"},
    "model_assisted_candidates": {"dest": "research/", "owner": "research", "kind": "research", "reason": "model-assisted candidate generation"},
    "prepare_human_gold_handoff": {"dest": "research/", "owner": "research", "kind": "research", "reason": "prepares human gold handoff materials"},
    "produce_census_tables": {"dest": "audits/failure_census/", "owner": "audit", "kind": "audit", "reason": "produces census tables from failure data"},
    "record_run": {"dest": "research/run_records/", "owner": "research", "kind": "research", "reason": "records run metadata"},
    "run_chain_study": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs development chain study"},
    "run_chain_study_v2": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs v2 chain study"},
    "run_edgar_smoke_test": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs EDGAR smoke test"},
    "run_held_out_study": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs held-out study"},
    "run_operational_preflight": {"dest": "results/preflight/", "owner": "results", "kind": "results", "reason": "runs operational preflight checks"},
    "run_smoke_test": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs smoke test"},
    "run_step_17b": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs Step 17B study"},
    "run_v2_study": {"dest": "research/", "owner": "research", "kind": "research", "reason": "runs v2 study"},
    # --- test modules ---
    "test_agreement_context": {"dest": "tests/unit/", "owner": "evidence", "kind": "test", "reason": "tests agreement context"},
    "test_build_failure_matrix": {"dest": "tests/unit/", "owner": "audit", "kind": "test", "reason": "tests failure matrix builder"},
    "test_build_release_package": {"dest": "tests/unit/", "owner": "results", "kind": "test", "reason": "tests release package builder"},
    "test_build_unresolved_corpus": {"dest": "tests/unit/", "owner": "data", "kind": "test", "reason": "tests unresolved corpus builder"},
    "test_chain_reconstruction": {"dest": "tests/integration/", "owner": "lineage", "kind": "test", "reason": "tests chain reconstruction and lineage"},
    "test_chain_study": {"dest": "tests/integration/", "owner": "research", "kind": "test", "reason": "tests chain study"},
    "test_chain_study_v2": {"dest": "tests/integration/", "owner": "research", "kind": "test", "reason": "tests v2 chain study"},
    "test_commitment_extractor": {"dest": "tests/unit/", "owner": "parsing", "kind": "test", "reason": "tests commitment extractor"},
    "test_commitment_registry": {"dest": "tests/unit/", "owner": "commitments", "kind": "test", "reason": "tests commitment registry"},
    "test_edgar_chains": {"dest": "tests/unit/", "owner": "ingestion", "kind": "test", "reason": "tests EDGAR chain fixtures"},
    "test_evaluation_layers": {"dest": "tests/unit/", "owner": "research", "kind": "test", "reason": "tests evaluation layers"},
    "test_executor": {"dest": "tests/transformation/", "owner": "execution", "kind": "test", "reason": "tests executor behavior"},
    "test_false_authoritative_promotion": {"dest": "tests/authority/", "owner": "authority", "kind": "test", "reason": "tests false authoritative promotion detection"},
    "test_genre_adapters": {"dest": "tests/unit/", "owner": "parsing", "kind": "test", "reason": "tests genre adapters"},
    "test_gold_schema": {"dest": "tests/unit/", "owner": "evidence", "kind": "test", "reason": "tests gold schema"},
    "test_held_out_study": {"dest": "tests/integration/", "owner": "research", "kind": "test", "reason": "tests held-out study"},
    "test_model_assisted_candidates": {"dest": "tests/unit/", "owner": "research", "kind": "test", "reason": "tests model-assisted candidates"},
    "test_operational_preflight": {"dest": "tests/integration/", "owner": "results", "kind": "test", "reason": "tests operational preflight"},
    "test_parser_v03": {"dest": "tests/unit/", "owner": "parsing", "kind": "test", "reason": "tests parser v03"},
    "test_parser_v04_regression": {"dest": "tests/regression/", "owner": "parsing", "kind": "test", "reason": "parser v04 regression tests"},
    "test_pattern_classifier": {"dest": "tests/unit/", "owner": "parsing", "kind": "test", "reason": "tests pattern classifier"},
    "test_persistence_integration": {"dest": "tests/integration/", "owner": "commitments", "kind": "test", "reason": "tests persistence integration"},
    "test_persistence_plan": {"dest": "tests/unit/", "owner": "commitments", "kind": "test", "reason": "tests persistence plan"},
    "test_schema": {"dest": "tests/unit/", "owner": "models", "kind": "test", "reason": "tests schema definitions"},
    "test_semantic_mapper": {"dest": "tests/transformation/", "owner": "transformations", "kind": "test", "reason": "tests semantic mapper"},
    "test_semantic_mapper_v01": {"dest": "tests/transformation/", "owner": "transformations", "kind": "test", "reason": "tests semantic mapper v01"},
    "test_semantic_pipeline": {"dest": "tests/integration/", "owner": "pipeline", "kind": "test", "reason": "tests semantic pipeline"},
    "test_semantic_regression": {"dest": "tests/regression/", "owner": "pipeline", "kind": "test", "reason": "semantic regression tests"},
    "test_semantic_resolver_v2": {"dest": "tests/transformation/", "owner": "transformations", "kind": "test", "reason": "tests semantic resolver v2"},
    "test_step22_taxonomy": {"dest": "tests/unit/", "owner": "research", "kind": "test", "reason": "tests Step 22 taxonomy"},
    "test_step22f_staged_interpreter": {"dest": "tests/unit/", "owner": "research", "kind": "test", "reason": "tests Step 22F staged interpreter"},
    "test_step23_audit": {"dest": "tests/regression/", "owner": "audit", "kind": "test", "reason": "tests Step 23 audit"},
    "test_step23r_audit": {"dest": "tests/regression/", "owner": "audit", "kind": "test", "reason": "tests Step 23R audit"},
    "test_step_22b_incorrect_mutation_fix": {"dest": "tests/conservation/", "owner": "conservation", "kind": "test", "reason": "tests incorrect mutation fix"},
    "test_v02_change_spec": {"dest": "tests/regression/", "owner": "legacy", "kind": "test", "reason": "tests v02 change spec"},
    "test_v02_regression": {"dest": "tests/regression/", "owner": "legacy", "kind": "test", "reason": "v02 regression tests"},
    # --- Step 23G.1 governance tests ---
    "test_frozen_manifest": {"dest": "tests/governance/", "owner": "governance", "kind": "test", "reason": "regression test proving frozen-manifest verification is idempotent"},
    "test_gitignore_boundary": {"dest": "tests/governance/", "owner": "governance", "kind": "test", "reason": "verifies .gitignore frozen-source exceptions admit only .txt source evidence, not derived output"},
}

# Non-Python files (curated, not in the dependency graph)
NON_PY_FILES: list[dict] = [
    # Documentation
    {"path": "README.md", "dest": "./ (root)", "owner": "docs", "kind": "docs", "reason": "repository root README; stays at root"},
    {"path": "CHANGELOG.md", "dest": "./ (root)", "owner": "docs", "kind": "docs", "reason": "active changelog; stays at root"},
    {"path": "CHANGELOG_v0.3.md", "dest": "archive/superseded_docs/", "owner": "docs", "kind": "legacy", "reason": "superseded changelog"},
    {"path": "AMENDMENT_INSTRUCTION_GRAMMAR.md", "dest": "docs/architecture/", "owner": "parsing", "kind": "docs", "reason": "amendment instruction grammar specification"},
    {"path": "BUILD_PLAN_25_ISSUERS.md", "dest": "docs/methodology/", "owner": "research", "kind": "docs", "reason": "25-issuer build plan"},
    {"path": "COMMITMENT_LINEAGE_SCHEMA.md", "dest": "docs/schemas/", "owner": "lineage", "kind": "docs", "reason": "commitment lineage schema specification"},
    {"path": "DEVELOPMENT_METHODS_RESULTS.md", "dest": "docs/methodology/", "owner": "research", "kind": "docs", "reason": "development methods and results"},
    {"path": "GITHUB_TESTING_PROTOCOL.md", "dest": "docs/runbooks/", "owner": "docs", "kind": "docs", "reason": "GitHub testing protocol"},
    {"path": "IP_BOUNDARY.md", "dest": "docs/architecture/", "owner": "architecture", "kind": "docs", "reason": "intellectual property boundary document"},
    {"path": "RESEARCH_WORKFLOW_MAC.md", "dest": "docs/runbooks/", "owner": "docs", "kind": "docs", "reason": "research workflow for macOS"},
    {"path": "RUNBOOK_PUBLISHABLE_STUDY.md", "dest": "docs/runbooks/", "owner": "docs", "kind": "docs", "reason": "publishable study runbook"},
    {"path": "VALIDATOR_INTERFACE.md", "dest": "docs/schemas/", "owner": "proof", "kind": "docs", "reason": "validator interface specification"},
    # SQL
    {"path": "schema.sql", "dest": "config/sql/", "owner": "commitments", "kind": "config", "reason": "PostgreSQL schema definition"},
    {"path": "queries.sql", "dest": "config/sql/", "owner": "commitments", "kind": "config", "reason": "PostgreSQL queries"},
    # Config and data
    {"path": "pyproject.toml", "dest": "./ (root)", "owner": "config", "kind": "config", "reason": "project configuration; stays at root"},
    {"path": "docker-compose.yml", "dest": "config/", "owner": "config", "kind": "config", "reason": "docker compose configuration"},
    {"path": "development_corpus.csv", "dest": "data/development/", "owner": "data", "kind": "data", "reason": "development corpus data"},
    {"path": "gold_annotations.csv", "dest": "data/held_out/", "owner": "data", "kind": "data", "reason": "gold annotation data"},
    {"path": "issuers.csv", "dest": "data/", "owner": "data", "kind": "data", "reason": "issuer list"},
    {"path": "predictions.csv", "dest": "data/", "owner": "data", "kind": "data", "reason": "prediction data"},
    {"path": "smoke_cases.csv", "dest": "data/smoke/", "owner": "data", "kind": "data", "reason": "smoke test cases"},
]


def _fmt_imports(record: dict) -> str:
    top = record["top_level_imports"]
    deferred = record["deferred_imports"]
    third = record["third_party_imports"]
    parts = []
    if top:
        parts.append(", ".join(top))
    if deferred:
        parts.append("deferred: " + ", ".join(deferred))
    if third:
        parts.append("ext: " + ", ".join(third))
    if not parts:
        return "(none)"
    return "; ".join(parts)


def _fmt_dependents(record: dict) -> str:
    runtime = record["runtime_dependents"]
    tests = record["test_dependents"]
    parts = []
    if runtime:
        parts.append(", ".join(runtime))
    if tests:
        parts.append(f"tests: {', '.join(tests)}")
    if not parts:
        return "(none)"
    return "; ".join(parts)


def _fmt_preconditions(record: dict) -> str:
    pre = record.get("migration_preconditions", [])
    if not pre:
        return "—"
    return " ; ".join(pre)


def generate_manifest() -> str:
    data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    modules = {m["module"]: m for m in data["modules"]}

    lines: list[str] = []
    lines.append("# Repository Migration Manifest — Step 23G")
    lines.append("")
    lines.append("**Every row in this manifest states `MOVE NOW: NO`.**")
    lines.append("")
    lines.append(
        "This manifest records the proposed future destination for every "
        "root-level file in the repository. It is a mapping, not an "
        "execution. No file is moved during Step 23G."
    )
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(
        "**This manifest is a human-readable projection of machine-generated "
        "data.** The imports, dependents, deferred imports, risk, and "
        "boundary columns are produced by AST analysis from "
        "`audits/repository/generate_dependency_graph.py`. The authoritative "
        "machine-readable artifacts are:"
    )
    lines.append("")
    lines.append("- `audits/repository/dependency_graph.json` (full per-module record)")
    lines.append("- `audits/repository/dependency_graph.csv` (flat tabular projection)")
    lines.append("- `audits/repository/dependency_graph_report.md` (summary report)")
    lines.append("")
    lines.append(
        "Regenerate this manifest with: "
        "`python audits/repository/generate_manifest.py`. "
        "Do not edit the imports/dependents columns by hand."
    )
    lines.append("")
    lines.append("## Classification key")
    lines.append("")
    lines.append("- **kind**: `runtime` | `test` | `research` | `audit` | `results` | `config` | `docs` | `data` | `legacy`")
    lines.append("- **risk**: `LOW` | `MEDIUM` | `HIGH` — mechanically classified from dependent count (LOW <3, MEDIUM 3-7, HIGH >=8). This is **dependency/migration exposure** (how many callers must be updated when the module moves), **not** semantic criticality. A module can be HIGH risk while being semantically simple, or LOW risk while being semantically central. Future architecture work may distinguish dependency risk from semantic risk, but this manifest does not attempt that.")
    lines.append("- **boundary**: `CLEAN` | `BOUNDARY_VIOLATION` — curated semantic judgement (see boundary violations section)")
    lines.append("- **imports**: local modules imported at top level; `deferred:` = function/class-scope imports; `ext:` = third-party")
    lines.append("- **dependents**: local modules that import this one; `tests:` = test modules")
    lines.append("")

    # Summary
    py_count = len(modules)
    non_py_count = len(NON_PY_FILES)
    total = py_count + non_py_count
    bv_count = sum(1 for m in modules.values() if m["boundary_status"] == "BOUNDARY_VIOLATION")
    lines.append("## Summary")
    lines.append("```")
    lines.append(f"files inventoried:                {total}")
    lines.append(f"  Python modules (AST-analyzed):  {py_count}")
    lines.append(f"  non-Python files (curated):     {non_py_count}")
    lines.append(f"files with proposed destinations: {total}")
    lines.append(f"boundary violations:              {bv_count}")
    lines.append("unclassified:                     0")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Categorize Python modules — each module in exactly one category.
    # kind is the primary discriminator; the test_ prefix is a fallback so
    # that test modules missing from MODULE_META are still classified.
    runtime_modules: list[str] = []
    test_modules: list[str] = []
    audit_research: list[str] = []
    uncategorized: list[str] = []
    for m in sorted(modules):
        kind = MODULE_META.get(m, {}).get("kind")
        if kind == "runtime":
            runtime_modules.append(m)
        elif kind == "test" or m.startswith("test_"):
            test_modules.append(m)
        elif kind in ("research", "audit", "results", "data", "legacy"):
            audit_research.append(m)
        else:
            uncategorized.append(m)
    if uncategorized:
        raise ValueError(
            f"Uncategorized Python modules (add to MODULE_META): {uncategorized}"
        )
    # Sanity: categorized count must match module count (no overlaps, no gaps)
    categorized_count = len(runtime_modules) + len(test_modules) + len(audit_research)
    assert categorized_count == len(modules), (
        f"Module categorization mismatch: {categorized_count} categorized "
        f"vs {len(modules)} total (overlaps or gaps in section filters)"
    )

    # Section 1: Runtime engine
    lines.append(f"## 1. Runtime engine modules ({len(runtime_modules)} files)")
    lines.append("")
    lines.append("| current path | proposed destination | semantic owner | kind | risk | boundary | imports | dependents | reason | move now |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for name in runtime_modules:
        r = modules[name]
        meta = MODULE_META[name]
        lines.append(
            f"| `{name}.py` | `{meta['dest']}` | {meta['owner']} | {meta['kind']} | "
            f"{r['migration_risk']} | {r['boundary_status']} | "
            f"{_fmt_imports(r)} | {_fmt_dependents(r)} | {meta['reason']} | NO |"
        )
    lines.append("")

    # Section 2: Audit and study tooling
    lines.append(f"## 2. Audit and study tooling ({len(audit_research)} files)")
    lines.append("")
    lines.append("| current path | proposed destination | semantic owner | kind | risk | boundary | imports | dependents | reason | move now |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for name in audit_research:
        r = modules[name]
        meta = MODULE_META[name]
        lines.append(
            f"| `{name}.py` | `{meta['dest']}` | {meta['owner']} | {meta['kind']} | "
            f"{r['migration_risk']} | {r['boundary_status']} | "
            f"{_fmt_imports(r)} | {_fmt_dependents(r)} | {meta['reason']} | NO |"
        )
    lines.append("")

    # Section 3: Test modules
    lines.append(f"## 3. Test modules ({len(test_modules)} files)")
    lines.append("")
    lines.append("| current path | proposed destination | semantic owner | kind | risk | boundary | imports | dependents | reason | move now |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for name in test_modules:
        r = modules[name]
        meta = MODULE_META[name]
        lines.append(
            f"| `{name}.py` | `{meta['dest']}` | {meta['owner']} | {meta['kind']} | "
            f"{r['migration_risk']} | {r['boundary_status']} | "
            f"{_fmt_imports(r)} | {_fmt_dependents(r)} | {meta['reason']} | NO |"
        )
    lines.append("")

    # Non-Python file sections — each file in exactly one section.
    docs = [f for f in NON_PY_FILES if f["path"].endswith(".md")]
    sqls = [f for f in NON_PY_FILES if f["path"].endswith(".sql")]
    configs = [f for f in NON_PY_FILES if f["kind"] in ("config", "data") and not f["path"].endswith(".sql")]
    non_py_sectioned = len(docs) + len(sqls) + len(configs)
    assert non_py_sectioned == len(NON_PY_FILES), (
        f"Non-Python file sectioning mismatch: {non_py_sectioned} sectioned "
        f"vs {len(NON_PY_FILES)} total (duplication or gaps in section filters)"
    )

    # Section 4: Documentation (all .md files)
    lines.append(f"## 4. Documentation ({len(docs)} files)")
    lines.append("")
    lines.append("| current path | proposed destination | semantic owner | kind | reason | move now |")
    lines.append("|---|---|---|---|---|---|")
    for f in docs:
        lines.append(f"| `{f['path']}` | `{f['dest']}` | {f['owner']} | {f['kind']} | {f['reason']} | NO |")
    lines.append("")

    # Section 5: SQL
    lines.append(f"## 5. SQL files ({len(sqls)} files)")
    lines.append("")
    lines.append("| current path | proposed destination | semantic owner | kind | reason | move now |")
    lines.append("|---|---|---|---|---|---|")
    for f in sqls:
        lines.append(f"| `{f['path']}` | `{f['dest']}` | {f['owner']} | {f['kind']} | {f['reason']} | NO |")
    lines.append("")

    # Section 6: Config and data (exclude SQL — shown in section 5)
    lines.append(f"## 6. Config and data artifacts ({len(configs)} files)")
    lines.append("")
    lines.append("| current path | proposed destination | semantic owner | kind | reason | move now |")
    lines.append("|---|---|---|---|---|---|")
    for f in configs:
        lines.append(f"| `{f['path']}` | `{f['dest']}` | {f['owner']} | {f['kind']} | {f['reason']} | NO |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Boundary violations section with preconditions
    bv_modules = sorted(
        (m for m in modules.values() if m["boundary_status"] == "BOUNDARY_VIOLATION"),
        key=lambda r: r["module"]
    )
    lines.append(f"## Boundary violations discovered ({len(bv_modules)} modules)")
    lines.append("")
    lines.append(
        "These modules currently combine multiple semantic responsibilities. "
        "They are **not split** during Step 23G. They are flagged for future "
        "migration planning with **per-module migration preconditions**."
    )
    lines.append("")
    lines.append("Each precondition must be satisfied *before* the module is moved. "
                 "These are not generic \"decompose first\" warnings — each "
                 "violation class requires a different extraction order.")
    lines.append("")
    lines.append("| module | responsibilities combined | target split | migration preconditions |")
    lines.append("|---|---|---|---|")
    for r in bv_modules:
        resp = r.get("responsibilities_combined", "")
        split = r.get("target_split", "")
        preconds = "<br>".join(f"☐ {p}" for p in r["migration_preconditions"])
        lines.append(f"| `{r['module']}` | {resp} | {split} | {preconds} |")
    lines.append("")

    # High-risk modules section
    high_risk = sorted(
        (m for m in modules.values() if m["migration_risk"] == "HIGH"),
        key=lambda r: -(len(r["imported_by"]))
    )
    lines.append("## High-risk modules (mechanically classified: >= 8 dependents)")
    lines.append("")
    lines.append(
        "Risk here means **dependency/migration exposure** — how many callers "
        "must be updated when the module moves — **not** semantic criticality. "
        "A module can be HIGH risk while being semantically simple, or LOW "
        "risk while being semantically central. Future architecture work may "
        "distinguish dependency risk from semantic risk, but this manifest "
        "does not attempt that."
    )
    lines.append("")
    lines.append(
        "The following modules have the largest import surface and pose the "
        "highest migration risk. Any future move requires updating all "
        "dependents simultaneously. **Deferred imports are included** in the "
        "dependent count — they are easy to miss in a manual audit."
    )
    lines.append("")
    lines.append("| module | runtime deps | test deps | total | deferred imports |")
    lines.append("|---|---:|---:|---:|---|")
    for r in high_risk:
        total = len(r["runtime_dependents"]) + len(r["test_dependents"])
        deferred = ", ".join(r["deferred_imports"]) or "(none)"
        lines.append(
            f"| `{r['module']}` | {len(r['runtime_dependents'])} | "
            f"{len(r['test_dependents'])} | {total} | {deferred} |"
        )
    lines.append("")

    # Migration execution order
    lines.append("## Migration execution order (future, not now)")
    lines.append("")
    lines.append("1. Create `src/upsilon/models/` package and move `models.py` first (foundation).")
    lines.append("2. Move clean single-responsibility modules (`executor.py`, `parsing/`).")
    lines.append("3. Split boundary-violation modules one at a time, satisfying each module's migration preconditions, with full test coverage.")
    lines.append("4. Move audit/research scripts last (lowest risk, fewest dependents).")
    lines.append("5. Update `pyproject.toml`, imports, CI, and documentation after each batch.")
    lines.append("6. At each migration checkpoint, regenerate the dependency graph and verify no new violations are introduced.")
    lines.append("")
    lines.append("**No migration is executed in Step 23G.**")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    manifest = generate_manifest()
    MANIFEST_PATH.write_text(manifest, encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
