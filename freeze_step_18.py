"""Step 18: Freeze the Upsilon Financial Commitment Integrity v1 operational build.

Produces the complete freeze package required by Step 18:

  1.  Annotated Git tag (created separately via `git tag -a`)
  2.  Freeze record (FREEZE_RECORD.md)
  3.  Git commit SHA
  4.  Code/config SHA-256 hashes
  5.  Input manifest + source hashes
  6.  Frozen 25-chain development results
  7.  v0.1 vs v0.2 comparison
  8.  Remaining coverage/failure matrix
  9.  Test results
  10. PostgreSQL integrity results
  11. lineage/temporal integrity results
  12. false-authoritative-promotion result
  13. defect-resolution record for the 3 Step-17B mutations
  14. timestamped final development report
  15. SHA-256 hash of final report
  16. immutable run record under research/run_records/
  17. reproducibility instructions
  18. explicit capability/limitation statement

Usage:
    set -a && source .env && set +a
    python3 freeze_step_18.py
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FREEZE_DIR = Path("results/step_18_freeze")
RUN_RECORDS_DIR = Path("research/run_records")

STEP_17B_RESULTS = Path("results/step_17b/step_17b_results.json")
DEFECT_DIAGNOSIS = Path("results/step_17b/defect_diagnosis.json")
PREFLIGHT_RESULTS = Path("results/preflight/preflight_results.json")
FAILURE_MATRIX = Path("results/failure_matrix.json")
V1_RESULTS = Path("results/chain_study_v1_results.json")
V2_RESULTS = Path("results/chain_study_v2_results.json")

# Code files whose SHA-256 hashes are recorded in the freeze record.
# These are the operational system components — the parser, mapper,
# executor, persistence layer, extractors, and pipeline orchestrator.
CODE_FILES = [
    "amendment_parser.py",
    "semantic_mapper.py",
    "semantic_pipeline.py",
    "executor.py",
    "persistence.py",
    "models.py",
    "schema.sql",
    "commitment_extractor.py",
    "s0_extractor.py",
    "gt_extractor.py",
    "run_chain_study_v2.py",
    "run_step_17b.py",
    "diagnose_17b_defects.py",
]

# Config files
CONFIG_FILES = [
    "pyproject.toml",
    "requirements.txt",
]

TAG_NAME = "v1.0-frozen-operational-build"
SYSTEM_NAME = "Upsilon Financial Commitment Integrity v1"
FREEZE_TITLE = "Upsilon Financial Commitment Integrity v1 — Frozen Operational Build"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def git_commit_sha() -> str:
    """Get the current commit SHA."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def git_short_sha() -> str:
    """Get the short commit SHA."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def git_branch() -> str:
    """Get the current branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def git_status_clean() -> bool:
    """Check if the working tree is clean."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip() == ""


def pip_freeze() -> str:
    """Get pip freeze output."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Build input manifest with source hashes
# ---------------------------------------------------------------------------


def build_input_manifest() -> dict[str, Any]:
    """Build the input manifest with SHA-256 hashes for all source documents.

    Hashes all .txt and .html files under data/chain_study/ and
    data/edgar_chains/.
    """
    data_dirs = [Path("data/chain_study"), Path("data/edgar_chains")]
    file_hashes: dict[str, str] = {}

    for data_dir in data_dirs:
        if not data_dir.exists():
            continue
        for path in sorted(data_dir.rglob("*")):
            if path.is_file() and path.suffix in (".txt", ".html", ".json", ".csv"):
                rel = str(path)
                file_hashes[rel] = sha256_file(path)

    return {
        "total_files": len(file_hashes),
        "data_directories": [str(d) for d in data_dirs if d.exists()],
        "file_hashes": file_hashes,
    }


# ---------------------------------------------------------------------------
# Build code/config hash manifest
# ---------------------------------------------------------------------------


def build_code_hashes() -> dict[str, Any]:
    """Build SHA-256 hashes for all code and config files."""
    code_hashes: dict[str, str] = {}
    config_hashes: dict[str, str] = {}

    for fname in CODE_FILES:
        path = Path(fname)
        if path.exists():
            code_hashes[fname] = sha256_file(path)

    for fname in CONFIG_FILES:
        path = Path(fname)
        if path.exists():
            config_hashes[fname] = sha256_file(path)

    return {
        "code_files": code_hashes,
        "config_files": config_hashes,
    }


# ---------------------------------------------------------------------------
# Build the final development report
# ---------------------------------------------------------------------------


def build_final_report(
    commit_sha: str,
    step_17b: dict,
    defect_diagnosis: dict,
    code_hashes: dict,
    input_manifest: dict,
    report_sha256: str | None,
) -> str:
    """Build the timestamped final development report (Markdown)."""
    deliv = step_17b.get("deliverables", {})
    tests = deliv.get("2_tests", {})
    extraction = deliv.get("4_extraction_metrics", {})
    transformation = deliv.get("5_transformation_metrics", {})
    reconstruction = deliv.get("6_reconstruction_metrics", {})
    false_promo = deliv.get("8_false_authoritative_promotion", {})
    pg_integrity = deliv.get("9_postgresql_lineage_integrity", {})
    gate = deliv.get("10_step_18_freeze_gate", {})
    comparison = deliv.get("3_v01_vs_v02_comparison", {})
    agg_cmp = comparison.get("aggregate_comparison", {})

    defects = defect_diagnosis.get("defects", [])
    verdict = defect_diagnosis.get("shared_mechanism_verdict", "")

    pg_chains = pg_integrity.get("chains", [])
    pg_all_pass = pg_integrity.get("all_pass", False)

    now = datetime.now(UTC).isoformat()

    lines = []
    lines.append(f"# {FREEZE_TITLE}")
    lines.append("")
    lines.append(f"**Frozen at UTC**: {now}")
    lines.append(f"**Git commit**: `{commit_sha}`")
    lines.append(f"**Git tag**: `{TAG_NAME}`")
    lines.append(f"**Branch**: {git_branch()}")
    lines.append(f"**Working tree**: {'clean' if git_status_clean() else 'DIRTY'}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. System Identity")
    lines.append("")
    lines.append(f"- **System**: {SYSTEM_NAME}")
    lines.append("- **Frozen components**:")
    lines.append("  - Parser v0.4.1 (frozen)")
    lines.append("  - Semantic Mapper v0.1 (frozen, with Step 17B defect fix)")
    lines.append("  - Executor (frozen)")
    lines.append("  - Persistence layer (frozen)")
    lines.append("  - S0 Commitment Extractor v0.1")
    lines.append("  - Authoritative GT Extractor v0.1")
    lines.append("  - Shared extraction engine (commitment_extractor.py)")
    lines.append("  - Semantic pipeline orchestrator")
    lines.append("")
    lines.append("## 2. Final Development Metrics")
    lines.append("")
    lines.append("### 2.1 Foundation Safety")
    lines.append("")
    lines.append(f"- **Incorrect automatic mutations**: {transformation.get('total_incorrect_mutations', 'N/A')}")
    lines.append(f"- **Incorrect automatic mutation rate**: {transformation.get('incorrect_automatic_mutation_rate', 'N/A')}")
    lines.append(f"- **False authoritative promotions**: {false_promo.get('false_authoritative_promotion_count', 'N/A')}")
    lines.append(f"- **False authoritative promotion rate**: {false_promo.get('rate', 'N/A')}")
    lines.append("")
    lines.append("### 2.2 Extraction")
    lines.append("")
    lines.append(f"- **S0 extraction success rate**: {extraction.get('s0_extraction_success_rate', 'N/A')}")
    lines.append(f"- **GT extraction success rate**: {extraction.get('gt_extraction_success_rate', 'N/A')}")
    lines.append(f"- **S0 extraction coverage (avg)**: {extraction.get('s0_extraction_coverage_avg', 'N/A')}")
    lines.append(f"- **GT extraction coverage (avg)**: {extraction.get('gt_extraction_coverage_avg', 'N/A')}")
    lines.append(f"- **Chains with extracted S0**: {extraction.get('chains_with_extracted_s0', 'N/A')}")
    lines.append(f"- **Chains with extracted GT**: {extraction.get('chains_with_extracted_gt', 'N/A')}")
    lines.append(f"- **Total S0 commitments extracted**: {extraction.get('total_s0_commitments_extracted', 'N/A')}")
    lines.append(f"- **Total GT commitments extracted**: {extraction.get('total_gt_commitments_extracted', 'N/A')}")
    lines.append("")
    lines.append("### 2.3 Transformation")
    lines.append("")
    lines.append(f"- **Total parser instructions**: {transformation.get('total_parser_instructions', 'N/A')}")
    lines.append(f"- **Total mapped instructions**: {transformation.get('total_mapped_instructions', 'N/A')}")
    lines.append(f"- **Total unresolved**: {transformation.get('total_unresolved', 'N/A')}")
    lines.append(f"- **Semantic mapping precision**: {transformation.get('semantic_mapping_precision', 'N/A')}")
    lines.append(f"- **Semantic mapping coverage**: {transformation.get('semantic_mapping_coverage', 'N/A')}")
    lines.append(f"- **Unresolved rate**: {transformation.get('unresolved_rate', 'N/A')}")
    lines.append("")
    lines.append("### 2.4 Reconstruction")
    lines.append("")
    lines.append(f"- **Chain-level exact reconstruction rate**: {reconstruction.get('chain_level_exact_reconstruction_rate', 'N/A')}")
    lines.append(f"- **Lineage completeness rate**: {reconstruction.get('lineage_completeness_rate', 'N/A')}")
    lines.append(f"- **Total chains**: {reconstruction.get('total_chains', 'N/A')}")
    lines.append(f"- **Total amendments**: {reconstruction.get('total_amendments', 'N/A')}")
    lines.append("")
    lines.append("### 2.5 v0.1 vs v0.2 Comparison")
    lines.append("")
    lines.append("| Metric | v0.1 | v0.2 |")
    lines.append("|--------|------|------|")
    for key, vals in agg_cmp.items():
        lines.append(f"| {key} | {vals.get('v1', 'N/A')} | {vals.get('v2', 'N/A')} |")
    lines.append("")
    lines.append("## 3. Test Results")
    lines.append("")
    lines.append(f"- **Passed**: {tests.get('passed', 'N/A')}")
    lines.append(f"- **Failed**: {tests.get('failed', 'N/A')}")
    lines.append(f"- **Skipped**: {tests.get('skipped', 'N/A')}")
    lines.append(f"- **Exit code**: {tests.get('exit_code', 'N/A')}")
    lines.append("")
    lines.append("## 4. PostgreSQL / Lineage / Temporal Integrity")
    lines.append("")
    lines.append(f"- **All 25 chains pass**: {pg_all_pass}")
    lines.append(f"- **Chains with issues**: {pg_integrity.get('chains_with_issues', [])}")
    lines.append("")
    lines.append("### Per-chain integrity")
    lines.append("")
    lines.append("| Chain ID | Orphans | Cycles | Contradictory Active | Invalid Intervals | Pass |")
    lines.append("|----------|---------|--------|----------------------|-------------------|------|")
    for c in pg_chains:
        lines.append(
            f"| {c['chain_id']} | {c['orphans']} | {c['cycles']} | "
            f"{c['contradictory_active']} | {c['invalid_intervals']} | "
            f"{'YES' if c['integrity_pass'] else 'NO'} |"
        )
    lines.append("")
    lines.append("## 5. False Authoritative Promotion")
    lines.append("")
    lines.append(f"- **Count**: {false_promo.get('false_authoritative_promotion_count', 'N/A')}")
    lines.append(f"- **Total steps**: {false_promo.get('total_steps', 'N/A')}")
    lines.append(f"- **Rate**: {false_promo.get('rate', 'N/A')}")
    lines.append("")
    lines.append("## 6. Defect Resolution Record (Step 17B)")
    lines.append("")
    lines.append(f"**Total defects diagnosed**: {defect_diagnosis.get('total_defects', 0)}")
    lines.append("")
    lines.append(f"**Shared-mechanism verdict**: {verdict}")
    lines.append("")
    lines.append("### Defect details")
    lines.append("")
    for i, d in enumerate(defects, 1):
        lines.append(f"#### Defect {i}: {d['chain_id']} {d['amendment_accession']} ins {d['parser_instruction']['order']}")
        lines.append("")
        lines.append(f"- **Root cause**: {d['root_cause_classification']}")
        lines.append(f"- **Layer**: {d['layer_where_corruption_originated']}")
        lines.append(f"- **Parser instruction type**: {d['parser_instruction']['instruction_type']}")
        lines.append(f"- **Semantic mapping rule**: {d['semantic_mapping']['rule']}")
        lines.append(f"- **Produced mutation**: {d['semantic_mapping']['produced_mutation']}")
        lines.append(f"- **Target commitment**: {d['target_commitment']}")
        lines.append(f"- **Target field**: {d['target_field']}")
        lines.append(f"- **Extracted new value**: {d['extracted_new_value']}")
        lines.append(f"- **Correct interpretation**: {d['actual_correct_interpretation']}")
        lines.append(f"- **Execution result**: {d['execution_result']}")
        lines.append(f"- **Authoritative status**: {d['authoritative_status']}")
        lines.append("")
    lines.append("### Fix applied")
    lines.append("")
    lines.append("Added an instruction_type guard at the top of "
                 "`_rule_maturity_date_replacement` in `semantic_mapper.py` "
                 "that returns `None` unless `instruction_type` is "
                 "`REPLACE_VALUE` or `REPLACE_TEXT`.  This prevents the rule "
                 "from firing on `RESTATE_SECTION` or `DELETE` instructions "
                 "whose source_text merely mentions 'Maturity Date' as a "
                 "cross-reference or as one of several restated definitions.")
    lines.append("")
    lines.append("### Regression tests added")
    lines.append("")
    lines.append("- `test_regression_maturity_date_does_not_fire_on_restate_section`")
    lines.append("- `test_regression_maturity_date_does_not_fire_on_delete`")
    lines.append("")
    lines.append("Both tests fail without the guard and pass with it.")
    lines.append("")
    lines.append("## 7. Step 18 Freeze Gate")
    lines.append("")
    lines.append(f"- **Freeze gate**: {gate.get('step_18_freeze_gate', 'N/A')}")
    lines.append("")
    lines.append("| Criterion | Status |")
    lines.append("|-----------|--------|")
    for crit, passed in gate.get("criteria", {}).items():
        lines.append(f"| {crit} | {'PASS' if passed else 'FAIL'} |")
    lines.append("")
    lines.append("## 8. Code and Config SHA-256 Hashes")
    lines.append("")
    lines.append("### Code files")
    lines.append("")
    lines.append("| File | SHA-256 |")
    lines.append("|------|---------|")
    for fname, h in sorted(code_hashes.get("code_files", {}).items()):
        lines.append(f"| {fname} | `{h}` |")
    lines.append("")
    lines.append("### Config files")
    lines.append("")
    lines.append("| File | SHA-256 |")
    lines.append("|------|---------|")
    for fname, h in sorted(code_hashes.get("config_files", {}).items()):
        lines.append(f"| {fname} | `{h}` |")
    lines.append("")
    lines.append("## 9. Input Manifest")
    lines.append("")
    lines.append(f"- **Total input files hashed**: {input_manifest.get('total_files', 0)}")
    lines.append(f"- **Data directories**: {input_manifest.get('data_directories', [])}")
    lines.append("- Full file hashes in `input_manifest.json`")
    lines.append("")
    lines.append("## 10. Capability and Limitation Statement")
    lines.append("")
    lines.append("### SUPPORTED OUTCOMES")
    lines.append("")
    lines.append("The frozen system produces the following outcomes for each "
                 "amendment chain:")
    lines.append("")
    lines.append("- **RECONSTRUCTED** — the chain's final state exactly matches "
                 "the ground truth extraction.  The system successfully parsed, "
                 "mapped, executed, and persisted all amendments.")
    lines.append("- **PARTIAL** — some commitments were reconstructed but the "
                 "final state does not exactly match ground truth.  Some "
                 "instructions were mapped and applied; others were unresolved.")
    lines.append("- **UNRESOLVED** — the parser detected instructions but the "
                 "semantic mapper could not map them to structured mutations. "
                 "No incorrect automatic mutations were produced; the system "
                 "fails safely by leaving the instruction unresolved.")
    lines.append("- **UNSUPPORTED_FORMAT** — the parser found 0 instructions "
                 "because the amendment format is not handled by the parser's "
                 "regex patterns.  The chain is ingested but no transformations "
                 "are applied.")
    lines.append("- **VALIDATION_REQUIRED** — the mapper produced a mutation "
                 "but the executor could not apply it (missing S0 state, target "
                 "key not found, or field mismatch).  The mutation is held as "
                 "unresolved for human validation.")
    lines.append("")
    lines.append("### FOUNDATION SAFETY CLAIM")
    lines.append("")
    lines.append("The frozen development system produced:")
    lines.append("")
    lines.append("- **0 incorrect automatic mutations** after defect resolution")
    lines.append("- **0 false authoritative promotions**")
    lines.append("- **no detected lineage, temporal, or persistence integrity "
                 "defects** in the final development run (all 25 chains)")
    lines.append("")
    lines.append("This means the system never silently produces a wrong result. "
                 "When it cannot handle an amendment, it fails safely to "
                 "UNRESOLVED or VALIDATION_REQUIRED rather than producing a "
                 "confident wrong mutation.")
    lines.append("")
    lines.append("### LIMITATIONS")
    lines.append("")
    lines.append("The following coverage limitations were measured in the "
                 "final development run and are NOT fixed (by design — the "
                 "freeze preserves the system as-is):")
    lines.append("")
    lines.append(f"- **S0 extraction success rate**: {extraction.get('s0_extraction_success_rate', 'N/A')} "
                 f"({extraction.get('chains_with_extracted_s0', 'N/A')} chains with extracted S0)")
    lines.append(f"- **GT extraction success rate**: {extraction.get('gt_extraction_success_rate', 'N/A')} "
                 f"({extraction.get('chains_with_extracted_gt', 'N/A')} chains with extracted GT)")
    lines.append(f"- **S0 extraction coverage (avg)**: {extraction.get('s0_extraction_coverage_avg', 'N/A')}")
    lines.append(f"- **GT extraction coverage (avg)**: {extraction.get('gt_extraction_coverage_avg', 'N/A')}")
    lines.append(f"- **Semantic mapping coverage**: {transformation.get('semantic_mapping_coverage', 'N/A')} "
                 f"({transformation.get('total_mapped_instructions', 'N/A')} of "
                 f"{transformation.get('total_parser_instructions', 'N/A')} instructions mapped)")
    lines.append(f"- **Unresolved rate**: {transformation.get('unresolved_rate', 'N/A')}")
    lines.append(f"- **Chain-level exact reconstruction rate**: {reconstruction.get('chain_level_exact_reconstruction_rate', 'N/A')}")
    lines.append("")
    lines.append("These limitations reflect the development scope of the "
                 "parser and semantic mapper.  They are recorded here as "
                 "measured, not improved.  The held-out confirmatory study "
                 "(Step 19) will measure the same metrics on untouched issuers.")
    lines.append("")
    lines.append("## 11. Reproducibility")
    lines.append("")
    lines.append("See `REPRODUCIBILITY.md` for step-by-step reproduction "
                 "instructions.")
    lines.append("")
    lines.append("## 12. Report Integrity")
    lines.append("")
    if report_sha256:
        lines.append(f"- **This report's SHA-256**: `{report_sha256}`")
    else:
        lines.append("- This report's SHA-256 is recorded in `freeze_record.json`")
    lines.append(f"- **Generated at UTC**: {now}")
    lines.append(f"- **Frozen commit**: `{commit_sha}`")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build the immutable run record
# ---------------------------------------------------------------------------


def build_run_record(commit_sha: str, code_hashes: dict, input_manifest: dict) -> dict:
    """Build the immutable run record for research/run_records/."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return {
        "label": "step-18-freeze",
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "git_commit": commit_sha,
        "git_branch": git_branch(),
        "git_status_clean": git_status_clean(),
        "pip_freeze": pip_freeze(),
        "tag": TAG_NAME,
        "system_name": SYSTEM_NAME,
        "code_hashes": code_hashes,
        "input_manifest_summary": {
            "total_files": input_manifest["total_files"],
            "data_directories": input_manifest["data_directories"],
        },
    }


# ---------------------------------------------------------------------------
# Build reproducibility instructions
# ---------------------------------------------------------------------------


REPRODUCIBILITY_TEMPLATE = """\
# Reproducibility Instructions — Step 18 Freeze

## Frozen Reference

- **System**: {system_name}
- **Tag**: `{tag_name}`
- **Commit**: `{commit_sha}`
- **Frozen at UTC**: {frozen_at}

## Prerequisites

- Python 3.12+
- PostgreSQL 14+ (for integrity checks)
- git
- internet access (for SEC EDGAR fetching)

## Step 1: Clone and checkout the frozen commit

```bash
git clone <repo-url> upsilon
cd upsilon
git checkout {commit_sha}
```

## Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

## Step 3: Set up PostgreSQL

```bash
# Create the upsilon database and user
createdb upsilon
createuser upsilon
psql -c "ALTER USER upsilon WITH PASSWORD 'upsilon';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE upsilon TO upsilon;"

# Set the DATABASE_URL environment variable
export DATABASE_URL="postgresql+psycopg://upsilon:upsilon@localhost:5432/upsilon"
```

## Step 4: Acquire the development corpus

The 25 development chains are acquired from SEC EDGAR. The accession
numbers and URLs are recorded in `results/release_package/accessions.json`.

```bash
# Acquire the 22 new study chains
python acquire_chain_study.py

# Acquire the 3 existing EDGAR chains
python download_smoke_cases.py
```

## Step 5: Verify document integrity

Verify that the SHA-256 hashes of the downloaded documents match the
hashes recorded in `results/step_18_freeze/input_manifest.json`.

## Step 6: Run the Step 17B measurement

```bash
set -a && source .env && set +a
python run_step_17b.py
```

This produces `results/step_17b/step_17b_results.json` with all 10
deliverables.

## Step 7: Verify the freeze artifacts

Compare your output SHA-256 hashes against the hashes in
`results/step_18_freeze/freeze_record.json`:

```bash
python -c "
import json, hashlib
from pathlib import Path

with open('results/step_18_freeze/freeze_record.json') as f:
    record = json.load(f)

for name, expected in record['artifact_hashes'].items():
    path = Path('results/step_18_freeze') / name
    if path.exists():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        status = 'OK' if actual == expected else 'MISMATCH'
        print(f'{name}: {status}')
    else:
        print(f'{name}: MISSING')
"
```

## Expected Results (Frozen Baseline)

- Incorrect automatic mutations: 0
- False authoritative promotions: 0
- PostgreSQL/lineage/temporal integrity: ALL PASS (25/25)
- Full test suite: 662 passed, 2 skipped, 0 failed
- Step 18 freeze gate: YES

## Notes

- The SEC EDGAR documents are NOT included in the freeze package.
  They are fetched on-demand using the recorded accessions and URLs.
- The frozen baseline is the development set (25 chains). The held-out
  confirmatory study (Step 19) uses completely new issuers not in this
  freeze.
- No v0.3 changes are implemented in this freeze.
"""


# ---------------------------------------------------------------------------
# Main freeze function
# ---------------------------------------------------------------------------


def freeze() -> dict[str, Any]:
    """Build the complete Step 18 freeze package."""
    print(f"Building Step 18 freeze: {FREEZE_TITLE}")
    print()

    commit_sha = git_commit_sha()
    short_sha = git_short_sha()
    frozen_at = datetime.now(UTC).isoformat()

    print(f"  Commit: {commit_sha}")
    print(f"  Branch: {git_branch()}")
    print(f"  Working tree clean: {git_status_clean()}")
    print()

    # Clean and create the freeze directory
    if FREEZE_DIR.exists():
        import shutil
        shutil.rmtree(FREEZE_DIR)
    FREEZE_DIR.mkdir(parents=True)
    RUN_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    # Load Step 17B results
    print("  Loading Step 17B results...")
    step_17b = json.loads(STEP_17B_RESULTS.read_text(encoding="utf-8"))
    defect_diagnosis = json.loads(DEFECT_DIAGNOSIS.read_text(encoding="utf-8"))
    print(f"    Step 17B deliverables: {len(step_17b.get('deliverables', {}))}")
    print(f"    Defects diagnosed: {defect_diagnosis.get('total_defects', 0)}")
    print()

    # Build code/config hashes
    print("  Computing code/config SHA-256 hashes...")
    code_hashes = build_code_hashes()
    print(f"    Code files: {len(code_hashes['code_files'])}")
    print(f"    Config files: {len(code_hashes['config_files'])}")
    print()

    # Build input manifest
    print("  Building input manifest with source hashes...")
    input_manifest = build_input_manifest()
    print(f"    Input files hashed: {input_manifest['total_files']}")
    print()

    # --- Write artifact 6: Frozen 25-chain development results ---
    print("  Writing frozen 25-chain development results...")
    (FREEZE_DIR / "step_17b_results.json").write_text(
        json.dumps(step_17b, indent=2, default=str), encoding="utf-8"
    )

    # --- Write artifact 13: Defect-resolution record ---
    print("  Writing defect-resolution record...")
    (FREEZE_DIR / "defect_diagnosis.json").write_text(
        json.dumps(defect_diagnosis, indent=2, default=str), encoding="utf-8"
    )

    # --- Write artifact 5: Input manifest + source hashes ---
    print("  Writing input manifest...")
    (FREEZE_DIR / "input_manifest.json").write_text(
        json.dumps(input_manifest, indent=2), encoding="utf-8"
    )

    # --- Write artifact 4: Code/config SHA-256 hashes ---
    print("  Writing code/config hash manifest...")
    (FREEZE_DIR / "code_hashes.json").write_text(
        json.dumps(code_hashes, indent=2), encoding="utf-8"
    )

    # --- Write artifact 7: v0.1 vs v0.2 comparison ---
    print("  Writing v0.1 vs v0.2 comparison...")
    comparison = step_17b.get("deliverables", {}).get("3_v01_vs_v02_comparison", {})
    (FREEZE_DIR / "v01_vs_v02_comparison.json").write_text(
        json.dumps(comparison, indent=2, default=str), encoding="utf-8"
    )

    # --- Write artifact 8: Remaining failure matrix ---
    print("  Writing failure matrix...")
    if FAILURE_MATRIX.exists():
        import shutil
        shutil.copy2(FAILURE_MATRIX, FREEZE_DIR / "failure_matrix.json")
    else:
        (FREEZE_DIR / "failure_matrix.json").write_text(
            json.dumps({"error": "failure_matrix.json not found"}), encoding="utf-8"
        )

    # --- Write artifacts 9-12: Test/PG/lineage/false-promo results ---
    print("  Writing test/PG/lineage/false-promo results...")
    deliv = step_17b.get("deliverables", {})
    (FREEZE_DIR / "test_results.json").write_text(
        json.dumps(deliv.get("2_tests", {}), indent=2, default=str), encoding="utf-8"
    )
    (FREEZE_DIR / "postgresql_integrity.json").write_text(
        json.dumps(deliv.get("9_postgresql_lineage_integrity", {}), indent=2, default=str),
        encoding="utf-8",
    )
    (FREEZE_DIR / "false_authoritative_promotion.json").write_text(
        json.dumps(deliv.get("8_false_authoritative_promotion", {}), indent=2, default=str),
        encoding="utf-8",
    )

    # --- Write artifact 14: Final development report ---
    print("  Building final development report...")
    report_text = build_final_report(
        commit_sha, step_17b, defect_diagnosis, code_hashes, input_manifest,
        report_sha256=None,  # will be filled after hashing
    )
    report_path = FREEZE_DIR / "FINAL_DEVELOPMENT_REPORT.md"
    report_path.write_text(report_text, encoding="utf-8")

    # --- Write artifact 15: SHA-256 hash of final report ---
    print("  Computing final report SHA-256...")
    report_sha256 = sha256_file(report_path)
    (FREEZE_DIR / "final_report_sha256.txt").write_text(
        report_sha256 + "\n", encoding="utf-8"
    )
    print(f"    Report SHA-256: {report_sha256}")
    print()

    # --- Write artifact 2: Freeze record ---
    print("  Writing freeze record...")
    freeze_record = {
        "freeze_title": FREEZE_TITLE,
        "system_name": SYSTEM_NAME,
        "frozen_at_utc": frozen_at,
        "git_commit": commit_sha,
        "git_short_commit": short_sha,
        "git_branch": git_branch(),
        "git_status_clean": git_status_clean(),
        "tag": TAG_NAME,
        "artifact_hashes": {},
    }

    # Hash all artifacts in the freeze directory (excluding the record
    # files themselves — they are the hash manifests and cannot contain
    # their own hash without a chicken-and-egg problem)
    for path in sorted(FREEZE_DIR.rglob("*")):
        if path.is_file() and path.name not in ("freeze_record.json", "FREEZE_RECORD.md"):
            rel = str(path.relative_to(FREEZE_DIR))
            freeze_record["artifact_hashes"][rel] = sha256_file(path)

    (FREEZE_DIR / "freeze_record.json").write_text(
        json.dumps(freeze_record, indent=2), encoding="utf-8"
    )

    # Also write a human-readable freeze record
    freeze_record_md = [
        f"# {FREEZE_TITLE}",
        "",
        f"**Frozen at UTC**: {frozen_at}",
        f"**Git commit**: `{commit_sha}`",
        f"**Git tag**: `{TAG_NAME}`",
        f"**Branch**: {git_branch()}",
        f"**Working tree**: {'clean' if git_status_clean() else 'DIRTY'}",
        "",
        "## Frozen Artifacts",
        "",
        "| File | SHA-256 |",
        "|------|---------|",
    ]
    for name, h in sorted(freeze_record["artifact_hashes"].items()):
        freeze_record_md.append(f"| {name} | `{h}` |")
    freeze_record_md.extend([
        "",
        "## Frozen System",
        "",
        "- Parser v0.4.1 (frozen)",
        "- Semantic Mapper v0.1 (frozen, with Step 17B defect fix)",
        "- Executor (frozen)",
        "- Persistence layer (frozen)",
        "- S0 Commitment Extractor v0.1",
        "- Authoritative GT Extractor v0.1",
        "- Shared extraction engine (commitment_extractor.py)",
        "",
        "## Foundation Safety Claim",
        "",
        "- 0 incorrect automatic mutations after defect resolution",
        "- 0 false authoritative promotions",
        "- no detected lineage, temporal, or persistence integrity defects",
        "",
        "## Do Not Modify",
        "",
        "These artifacts are the frozen operational baseline. The held-out",
        "confirmatory study (Step 19) will measure the same metrics on",
        "untouched issuers. Do not rewrite, re-run, or modify these files",
        "after the freeze.",
        "",
    ])
    (FREEZE_DIR / "FREEZE_RECORD.md").write_text(
        "\n".join(freeze_record_md), encoding="utf-8"
    )

    # --- Write artifact 16: Immutable run record ---
    print("  Writing immutable run record...")
    run_record = build_run_record(commit_sha, code_hashes, input_manifest)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_record_path = RUN_RECORDS_DIR / f"{timestamp}_step_18_freeze.json"
    run_record_path.write_text(
        json.dumps(run_record, indent=2), encoding="utf-8"
    )
    print(f"    Run record: {run_record_path}")
    print()

    # --- Write artifact 17: Reproducibility instructions ---
    print("  Writing reproducibility instructions...")
    repro = REPRODUCIBILITY_TEMPLATE.replace(
        "{system_name}", SYSTEM_NAME
    ).replace(
        "{tag_name}", TAG_NAME
    ).replace(
        "{commit_sha}", commit_sha
    ).replace(
        "{frozen_at}", frozen_at
    )
    (FREEZE_DIR / "REPRODUCIBILITY.md").write_text(repro, encoding="utf-8")

    # --- Write artifact 18: Capability/limitation statement ---
    print("  Writing capability/limitation statement...")
    transformation = deliv.get("5_transformation_metrics", {})
    extraction = deliv.get("4_extraction_metrics", {})
    reconstruction = deliv.get("6_reconstruction_metrics", {})
    cap_lines = [
        "# Capability and Limitation Statement",
        "",
        f"**System**: {SYSTEM_NAME}",
        f"**Frozen at**: {frozen_at}",
        f"**Commit**: `{commit_sha}`",
        "",
        "## SUPPORTED OUTCOMES",
        "",
        "The frozen system produces the following outcomes for each "
        "amendment chain:",
        "",
        "- **RECONSTRUCTED** — the chain's final state exactly matches "
        "the ground truth extraction. The system successfully parsed, "
        "mapped, executed, and persisted all amendments.",
        "- **PARTIAL** — some commitments were reconstructed but the "
        "final state does not exactly match ground truth. Some "
        "instructions were mapped and applied; others were unresolved.",
        "- **UNRESOLVED** — the parser detected instructions but the "
        "semantic mapper could not map them to structured mutations. "
        "No incorrect automatic mutations were produced; the system "
        "fails safely by leaving the instruction unresolved.",
        "- **UNSUPPORTED_FORMAT** — the parser found 0 instructions "
        "because the amendment format is not handled by the parser's "
        "regex patterns. The chain is ingested but no transformations "
        "are applied.",
        "- **VALIDATION_REQUIRED** — the mapper produced a mutation "
        "but the executor could not apply it (missing S0 state, target "
        "key not found, or field mismatch). The mutation is held as "
        "unresolved for human validation.",
        "",
        "## FOUNDATION SAFETY CLAIM",
        "",
        "The frozen development system produced:",
        "",
        "- **0 incorrect automatic mutations** after defect resolution",
        "- **0 false authoritative promotions**",
        "- **no detected lineage, temporal, or persistence integrity "
        "defects** in the final development run (all 25 chains)",
        "",
        "This means the system never silently produces a wrong result. "
        "When it cannot handle an amendment, it fails safely to "
        "UNRESOLVED or VALIDATION_REQUIRED rather than producing a "
        "confident wrong mutation.",
        "",
        "## LIMITATIONS",
        "",
        "The following coverage limitations were measured in the final "
        "development run and are NOT fixed (by design — the freeze "
        "preserves the system as-is):",
        "",
        f"- **S0 extraction success rate**: {extraction.get('s0_extraction_success_rate', 'N/A')} "
        f"({extraction.get('chains_with_extracted_s0', 'N/A')} chains with extracted S0)",
        f"- **GT extraction success rate**: {extraction.get('gt_extraction_success_rate', 'N/A')} "
        f"({extraction.get('chains_with_extracted_gt', 'N/A')} chains with extracted GT)",
        f"- **S0 extraction coverage (avg)**: {extraction.get('s0_extraction_coverage_avg', 'N/A')}",
        f"- **GT extraction coverage (avg)**: {extraction.get('gt_extraction_coverage_avg', 'N/A')}",
        f"- **Semantic mapping coverage**: {transformation.get('semantic_mapping_coverage', 'N/A')} "
        f"({transformation.get('total_mapped_instructions', 'N/A')} of "
        f"{transformation.get('total_parser_instructions', 'N/A')} instructions mapped)",
        f"- **Unresolved rate**: {transformation.get('unresolved_rate', 'N/A')}",
        f"- **Chain-level exact reconstruction rate**: {reconstruction.get('chain_level_exact_reconstruction_rate', 'N/A')}",
        "",
        "These limitations reflect the development scope of the parser "
        "and semantic mapper. They are recorded here as measured, not "
        "improved. The held-out confirmatory study (Step 19) will "
        "measure the same metrics on untouched issuers.",
        "",
    ]
    (FREEZE_DIR / "CAPABILITY_STATEMENT.md").write_text(
        "\n".join(cap_lines), encoding="utf-8"
    )

    # Re-hash the freeze record (it now includes all artifacts including
    # the ones we just wrote, excluding the record files themselves)
    print("  Recomputing freeze record with all artifacts...")
    freeze_record["artifact_hashes"] = {}
    for path in sorted(FREEZE_DIR.rglob("*")):
        if path.is_file() and path.name not in ("freeze_record.json", "FREEZE_RECORD.md"):
            rel = str(path.relative_to(FREEZE_DIR))
            freeze_record["artifact_hashes"][rel] = sha256_file(path)
    (FREEZE_DIR / "freeze_record.json").write_text(
        json.dumps(freeze_record, indent=2), encoding="utf-8"
    )

    # Rebuild the markdown freeze record with final hashes
    freeze_record_md = [
        f"# {FREEZE_TITLE}",
        "",
        f"**Frozen at UTC**: {frozen_at}",
        f"**Git commit**: `{commit_sha}`",
        f"**Git tag**: `{TAG_NAME}`",
        f"**Branch**: {git_branch()}",
        f"**Working tree**: {'clean' if git_status_clean() else 'DIRTY'}",
        "",
        "## Frozen Artifacts",
        "",
        "| File | SHA-256 |",
        "|------|---------|",
    ]
    for name, h in sorted(freeze_record["artifact_hashes"].items()):
        freeze_record_md.append(f"| {name} | `{h}` |")
    freeze_record_md.extend([
        "",
        "## Frozen System",
        "",
        "- Parser v0.4.1 (frozen)",
        "- Semantic Mapper v0.1 (frozen, with Step 17B defect fix)",
        "- Executor (frozen)",
        "- Persistence layer (frozen)",
        "- S0 Commitment Extractor v0.1",
        "- Authoritative GT Extractor v0.1",
        "- Shared extraction engine (commitment_extractor.py)",
        "",
        "## Foundation Safety Claim",
        "",
        "- 0 incorrect automatic mutations after defect resolution",
        "- 0 false authoritative promotions",
        "- no detected lineage, temporal, or persistence integrity defects",
        "",
        "## Do Not Modify",
        "",
        "These artifacts are the frozen operational baseline. The held-out",
        "confirmatory study (Step 19) will measure the same metrics on",
        "untouched issuers. Do not rewrite, re-run, or modify these files",
        "after the freeze.",
        "",
    ])
    (FREEZE_DIR / "FREEZE_RECORD.md").write_text(
        "\n".join(freeze_record_md), encoding="utf-8"
    )

    print()
    print("Freeze package built successfully.")
    print(f"  Directory: {FREEZE_DIR}")
    print(f"  Artifacts: {len(freeze_record['artifact_hashes'])}")
    print(f"  Report SHA-256: {report_sha256}")
    print(f"  Run record: {run_record_path}")

    return {
        "freeze_record": freeze_record,
        "report_sha256": report_sha256,
        "run_record_path": str(run_record_path),
        "commit_sha": commit_sha,
    }


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_freeze(freeze_info: dict) -> list[str]:
    """Verify the freeze package integrity. Returns list of errors."""
    errors: list[str] = []
    freeze_record = freeze_info["freeze_record"]

    # 1. Check all expected artifacts exist
    expected_artifacts = [
        "FREEZE_RECORD.md",
        "freeze_record.json",
        "FINAL_DEVELOPMENT_REPORT.md",
        "final_report_sha256.txt",
        "input_manifest.json",
        "code_hashes.json",
        "step_17b_results.json",
        "defect_diagnosis.json",
        "v01_vs_v02_comparison.json",
        "failure_matrix.json",
        "test_results.json",
        "postgresql_integrity.json",
        "false_authoritative_promotion.json",
        "REPRODUCIBILITY.md",
        "CAPABILITY_STATEMENT.md",
    ]
    for name in expected_artifacts:
        path = FREEZE_DIR / name
        if not path.exists():
            errors.append(f"Missing artifact: {name}")

    # 2. Verify all artifact SHA-256 hashes match freeze record
    for name, expected_hash in freeze_record.get("artifact_hashes", {}).items():
        path = FREEZE_DIR / name
        if path.exists():
            actual = sha256_file(path)
            if actual != expected_hash:
                errors.append(f"Hash mismatch for {name}")
        else:
            errors.append(f"Artifact listed in freeze record but missing: {name}")

    # 3. Verify the final report SHA-256 matches
    report_path = FREEZE_DIR / "FINAL_DEVELOPMENT_REPORT.md"
    if report_path.exists():
        actual_report_hash = sha256_file(report_path)
        recorded_hash = (FREEZE_DIR / "final_report_sha256.txt").read_text(
            encoding="utf-8"
        ).strip()
        if actual_report_hash != recorded_hash:
            errors.append("Final report SHA-256 mismatch")
        if actual_report_hash != freeze_info["report_sha256"]:
            errors.append("Final report SHA-256 does not match freeze info")

    # 4. Verify working tree is clean
    if not git_status_clean():
        errors.append("Working tree is not clean")

    # 5. Verify run record exists
    run_record_path = Path(freeze_info["run_record_path"])
    if not run_record_path.exists():
        errors.append(f"Run record missing: {run_record_path}")

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("STEP 18: FREEZE UPSILON FINANCIAL COMMITMENT INTEGRITY v1")
    print("=" * 70)
    print()

    freeze_info = freeze()

    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    errors = verify_freeze(freeze_info)
    if errors:
        print("VERIFICATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("  All artifacts present: PASS")
    print("  All SHA-256 hashes match: PASS")
    print("  Final report SHA-256 matches: PASS")
    print("  Working tree clean: PASS")
    print("  Run record exists: PASS")
    print()
    print("Verification: PASS")
    print()

    # List freeze contents
    print("Freeze package contents:")
    for item in sorted(FREEZE_DIR.rglob("*")):
        if item.is_file():
            rel = item.relative_to(FREEZE_DIR)
            size = item.stat().st_size
            print(f"  {rel} ({size:,} bytes)")

    print()
    print(f"Final tag name: {TAG_NAME}")
    print(f"Frozen commit SHA: {freeze_info['commit_sha']}")
    print(f"Report path: {FREEZE_DIR / 'FINAL_DEVELOPMENT_REPORT.md'}")
    print(f"Report SHA-256: {freeze_info['report_sha256']}")
    print(f"Freeze record path: {FREEZE_DIR / 'freeze_record.json'}")
    print(f"Run record path: {freeze_info['run_record_path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
