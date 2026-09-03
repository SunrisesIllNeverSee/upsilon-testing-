"""Generate a machine-readable dependency graph from AST analysis.

This script is the **authoritative source** for the reverse-dependency
data consumed by ``docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md``.
The Markdown manifest is a human-readable projection of the artifacts
this script produces; it must never be maintained by hand.

Outputs (written to ``audits/repository/``):

- ``dependency_graph.json``  — full per-module record (authoritative)
- ``dependency_graph.csv``   — flat tabular projection
- ``dependency_graph_report.md`` — human-readable summary

Each module record carries:

- ``module``                    — file stem (e.g. ``models``)
- ``imports``                   — all local modules imported (top-level + deferred)
- ``imported_by``               — all local modules that import this one
- ``top_level_imports``         — imports at module scope
- ``deferred_imports``          — imports inside functions / classes / conditionals
- ``test_dependents``           — ``imported_by`` filtered to ``test_*`` modules
- ``runtime_dependents``        — ``imported_by`` filtered to non-test modules
- ``third_party_imports``      — non-local, non-stdlib imports
- ``migration_risk``            — LOW / MEDIUM / HIGH based on dependent count.
                                  This is **dependency/migration exposure**
                                  (how many callers must be updated when the
                                  module moves), **not** semantic criticality.
                                  A module can be HIGH risk (many dependents)
                                  while being semantically simple, or LOW risk
                                  while being semantically central.  Future
                                  architecture work may distinguish dependency
                                  risk from semantic risk, but this graph does
                                  not attempt that.
- ``boundary_status``           — CLEAN / BOUNDARY_VIOLATION (from curated set)
- ``migration_preconditions``   — list of preconditions (boundary violations only)

Run::

    python audits/repository/generate_dependency_graph.py
"""
from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Boundary-violation classification (curated, not inferred from imports)
# ---------------------------------------------------------------------------
#
# Boundary status is a *semantic* judgement about whether a module combines
# multiple MOSES layer responsibilities.  It cannot be derived from the
# import graph alone, so it is maintained as a small curated set.  Every
# other module defaults to CLEAN.
#
# The migration_preconditions field carries the per-violation preconditions
# recommended by the Step 23G review.

BOUNDARY_VIOLATIONS: dict[str, dict] = {
    "commitment_registry": {
        "responsibilities": (
            "commitment identity + evidence alias matching + "
            "section-reference resolution"
        ),
        "target_split": (
            "commitments/ (identity) + evidence/ (alias/section evidence)"
        ),
        "migration_preconditions": [
            "new identity interface exists first",
            "evidence alias matching extracted to evidence/ layer",
            "section-reference resolution extracted to evidence/ layer",
        ],
    },
    "semantic_resolver_v2": {
        "responsibilities": (
            "transformation + evidence re-extraction (discards parser "
            "old/new values)"
        ),
        "target_split": (
            "transformations/ (resolver) + evidence/ (value extraction)"
        ),
        "migration_preconditions": [
            "new identity / evidence / transformation interfaces exist first",
            "value re-extraction moved to evidence/ layer",
        ],
    },
    "semantic_mapper": {
        "responsibilities": (
            "transformation + identity resolution via section heuristics"
        ),
        "target_split": (
            "transformations/ (mapping) + commitments/ (identity)"
        ),
        "migration_preconditions": [
            "commitment identity resolution moved to commitments/ layer",
            "transformation mapping retained in transformations/ layer",
        ],
    },
    "semantic_pipeline_v2": {
        "responsibilities": "pipeline orchestration + authority determination",
        "target_split": "pipeline/ (orchestration) + authority/ (authority logic)",
        "migration_preconditions": [
            "authority determination extracted to authority/ layer first",
            "pipeline orchestration retained in pipeline/ layer",
        ],
    },
    "semantic_pipeline": {
        "responsibilities": (
            "legacy pipeline combining orchestration + mapping + execution"
        ),
        "target_split": "archive/legacy_code/ or split as v2; superseded by v2",
        "migration_preconditions": [
            "legacy consumers migrated to compatibility facade or retired",
            "v2 pipeline confirmed as functional replacement",
        ],
    },
    "chain_reconstruction": {
        "responsibilities": (
            "lineage graph + execution state advancement + authority propagation"
        ),
        "target_split": (
            "lineage/ (graph) + execution/ (state advancement) + "
            "authority/ (propagation)"
        ),
        "migration_preconditions": [
            "authority and execution responsibilities extracted first",
            "lineage graph retained as pure graph structure in lineage/ layer",
        ],
    },
    "edgar_chains": {
        "responsibilities": (
            "ingestion fixtures + frozen chain data + hand-extracted states"
        ),
        "target_split": (
            "ingestion/edgar/ (fixtures) + data/ground_truth/frozen/ (data)"
        ),
        "migration_preconditions": [
            "embedded frozen states externalized and hashed first",
            "hand-extracted states moved to data/ground_truth/frozen/ with provenance",
            "ingestion fixture code retained in ingestion/edgar/ layer",
        ],
    },
}


def _local_module_names() -> set[str]:
    """Return the set of importable local module names (file stems).

    Scans src/upsilon/, tests/, audits/, research/, data/, results/, archive/
    for .py files (excluding __init__.py) and returns their file stems.
    """
    names: set[str] = set()
    scan_dirs = [
        REPO_ROOT / "src" / "upsilon",
        REPO_ROOT / "tests",
        REPO_ROOT / "audits",
        REPO_ROOT / "research",
        REPO_ROOT / "data",
        REPO_ROOT / "results",
        REPO_ROOT / "archive",
    ]
    for d in scan_dirs:
        if d.exists():
            for p in d.rglob("*.py"):
                if p.stem != "__init__":
                    names.add(p.stem)
    return names


def _all_py_files() -> list[Path]:
    """Return all .py files in the scan directories, sorted."""
    py_files: list[Path] = []
    scan_dirs = [
        REPO_ROOT / "src" / "upsilon",
        REPO_ROOT / "tests",
        REPO_ROOT / "audits",
        REPO_ROOT / "research",
        REPO_ROOT / "data",
        REPO_ROOT / "results",
        REPO_ROOT / "archive",
    ]
    for d in scan_dirs:
        if d.exists():
            py_files.extend(p for p in d.rglob("*.py") if p.stem != "__init__")
    return sorted(py_files)


def _extract_imports(source: str) -> tuple[list[str], list[str]]:
    """Parse ``source`` and return (top_level_locals, deferred_locals).

    Only imports of *local* modules are returned.  Third-party and stdlib
    imports are filtered out by the caller using ``LOCAL_MODULES``.

    Handles both bare imports (``import models``) and dotted package imports
    (``import upsilon.models.legacy_models as models``).  For dotted imports,
    the last component of the dotted path is matched against local module names.
    """
    try:
        tree = ast.parse(source, filename="<ast>")
    except SyntaxError:
        return [], []

    top_level: list[str] = []
    deferred: list[str] = []

    def _record(node: ast.Import | ast.ImportFrom, sink: list[str]) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                # For dotted imports like upsilon.models.legacy_models,
                # extract the last component as the module name
                parts = alias.name.split(".")
                sink.append(parts[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                return
            # For `from upsilon.models.legacy_models import X`,
            # the module is upsilon.models.legacy_models, last component is legacy_models
            parts = node.module.split(".")
            sink.append(parts[-1])

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _record(node, top_level)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef, ast.If, ast.With, ast.Try,
                               ast.For, ast.While)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    # Only direct children of this block, not nested defs
                    _record(sub, deferred)

    return top_level, deferred


def _classify_risk(runtime_dependents: int, test_dependents: int) -> str:
    """Classify migration risk from dependent count.

    This is **dependency/migration exposure** — how many callers must be
    updated when the module moves — not semantic criticality.  A module
    can be HIGH risk (many dependents) while being semantically simple,
    or LOW risk while being semantically central.
    """
    total = runtime_dependents + test_dependents
    if total >= 8:
        return "HIGH"
    if total >= 3:
        return "MEDIUM"
    return "LOW"


def build_graph() -> dict[str, dict]:
    """Build the full dependency graph and return per-module records."""
    local_modules = _local_module_names()
    py_files = _all_py_files()

    # module -> {top_level_imports, deferred_imports, third_party_imports}
    raw: dict[str, dict] = {}
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        top, deferred = _extract_imports(source)
        # Filter to local modules only (dedup, preserve order)
        top_local = []
        seen = set()
        for m in top:
            if m in local_modules and m != path.stem and m not in seen:
                top_local.append(m)
                seen.add(m)
        deferred_local = []
        seen_d = set()
        for m in deferred:
            if m in local_modules and m != path.stem and m not in seen_d:
                deferred_local.append(m)
                seen_d.add(m)
        # Third-party (non-local, non-stdlib heuristic)
        stdlib = _stdlib_names()
        third_party = []
        seen_t: set[str] = set()
        for m in top + deferred:
            if (m not in local_modules and m not in stdlib
                    and m not in seen_t and m != path.stem):
                third_party.append(m)
                seen_t.add(m)
        raw[path.stem] = {
            "top_level_imports": top_local,
            "deferred_imports": deferred_local,
            "third_party_imports": third_party,
        }

    # Build reverse map: imported_by
    imported_by: dict[str, list[str]] = {m: [] for m in raw}
    for module, data in raw.items():
        all_imports = data["top_level_imports"] + data["deferred_imports"]
        for imp in all_imports:
            if imp in imported_by and module not in imported_by[imp]:
                imported_by[imp].append(module)

    # Assemble per-module records
    records: dict[str, dict] = {}
    for module, data in raw.items():
        all_imports = sorted(set(data["top_level_imports"]
                                 + data["deferred_imports"]))
        deps = sorted(imported_by[module])
        test_deps = sorted(d for d in deps if d.startswith("test_"))
        runtime_deps = sorted(d for d in deps if not d.startswith("test_"))
        bv = BOUNDARY_VIOLATIONS.get(module)
        boundary_status = "BOUNDARY_VIOLATION" if bv else "CLEAN"
        preconditions = bv["migration_preconditions"] if bv else []
        records[module] = {
            "module": module,
            "imports": all_imports,
            "imported_by": deps,
            "top_level_imports": data["top_level_imports"],
            "deferred_imports": data["deferred_imports"],
            "test_dependents": test_deps,
            "runtime_dependents": runtime_deps,
            "third_party_imports": data["third_party_imports"],
            "migration_risk": _classify_risk(
                len(runtime_deps), len(test_deps)
            ),
            "boundary_status": boundary_status,
            "migration_preconditions": preconditions,
        }
        if bv:
            records[module]["responsibilities_combined"] = bv["responsibilities"]
            records[module]["target_split"] = bv["target_split"]

    return records


# Stdlib module names for filtering third-party imports.  Built lazily.
_STDLIB: set[str] | None = None


def _stdlib_names() -> set[str]:
    global _STDLIB
    if _STDLIB is None:
        _STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {
            "os", "sys", "json", "re", "ast", "csv", "pathlib", "datetime",
            "collections", "itertools", "functools", "typing", "hashlib",
            "base64", "io", "copy", "dataclasses", "enum", "abc", "argparse",
            "logging", "unittest", "tempfile", "shutil", "platform",
            "subprocess", "textwrap", "string", "math", "statistics",
            "warnings", "contextlib", "inspect", "importlib", "uuid",
            "sqlite3", "xml", "html", "urllib", "http", "email",
            "configparser", "tomllib", "zoneinfo", "time", "random",
            "operator", "pprint", "glob", "fnmatch", "concurrent",
            "multiprocessing", "threading", "asyncio", "socket",
            "ssl", "struct", "codecs", "unicodedata", "locale",
        }
    return _STDLIB


def write_json(records: dict[str, dict], out_dir: Path) -> Path:
    path = out_dir / "dependency_graph.json"
    # Sort by module name for deterministic output
    payload = {
        "generated_at": "regenerate via: python audits/repository/generate_dependency_graph.py",
        "module_count": len(records),
        "boundary_violation_count": sum(
            1 for r in records.values()
            if r["boundary_status"] == "BOUNDARY_VIOLATION"
        ),
        "modules": [records[k] for k in sorted(records)],
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def write_csv(records: dict[str, dict], out_dir: Path) -> Path:
    path = out_dir / "dependency_graph.csv"
    fields = [
        "module",
        "boundary_status",
        "migration_risk",
        "imports",
        "imported_by",
        "top_level_imports",
        "deferred_imports",
        "test_dependents",
        "runtime_dependents",
        "third_party_imports",
        "migration_preconditions",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for module in sorted(records):
            r = records[module]
            row = {k: r.get(k, "") for k in fields}
            for list_field in ("imports", "imported_by", "top_level_imports",
                               "deferred_imports", "test_dependents",
                               "runtime_dependents", "third_party_imports",
                               "migration_preconditions"):
                row[list_field] = "; ".join(row[list_field]) if row[list_field] else ""
            writer.writerow(row)
    return path


def write_report(records: dict[str, dict], out_dir: Path) -> Path:
    path = out_dir / "dependency_graph_report.md"
    lines: list[str] = []
    lines.append("# Dependency Graph Report (machine-generated)")
    lines.append("")
    lines.append(
        "This report is generated by "
        "`audits/repository/generate_dependency_graph.py`.  Do not edit by "
        "hand.  The Markdown migration manifest is a projection of this data."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    bv = [r for r in records.values() if r["boundary_status"] == "BOUNDARY_VIOLATION"]
    high = [r for r in records.values() if r["migration_risk"] == "HIGH"]
    lines.append(f"- modules inventoried: {len(records)}")
    lines.append(f"- boundary violations: {len(bv)}")
    lines.append(f"- high migration risk: {len(high)}")
    lines.append("")

    lines.append("## Boundary violations (with migration preconditions)")
    lines.append("")
    lines.append("| module | responsibilities | preconditions |")
    lines.append("|---|---|---|")
    for module in sorted(r["module"] for r in bv):
        r = records[module]
        resp = r.get("responsibilities_combined", "")
        preconds = "<br>".join(r["migration_preconditions"])
        lines.append(f"| `{module}` | {resp} | {preconds} |")
    lines.append("")

    lines.append("## High-risk modules (>= 8 dependents)")
    lines.append("")
    lines.append("| module | runtime deps | test deps | total | deferred imports captured |")
    lines.append("|---|---:|---:|---:|---|")
    for module in sorted(r["module"] for r in high):
        r = records[module]
        total = len(r["runtime_dependents"]) + len(r["test_dependents"])
        deferred = ", ".join(r["deferred_imports"]) or "(none)"
        lines.append(
            f"| `{module}` | {len(r['runtime_dependents'])} | "
            f"{len(r['test_dependents'])} | {total} | {deferred} |"
        )
    lines.append("")

    lines.append("## Deferred imports (modules with function-scope imports)")
    lines.append("")
    lines.append(
        "Deferred imports are imports inside functions, classes, or "
        "conditional blocks.  They are easy to miss in a manual audit "
        "and are the primary reason this graph is machine-generated."
    )
    lines.append("")
    lines.append("| module | deferred imports |")
    lines.append("|---|---|")
    for module in sorted(records):
        r = records[module]
        if r["deferred_imports"]:
            lines.append(
                f"| `{module}` | {', '.join(r['deferred_imports'])} |"
            )
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    out_dir = REPO_ROOT / "audits" / "repository"
    out_dir.mkdir(parents=True, exist_ok=True)
    records = build_graph()
    j = write_json(records, out_dir)
    c = write_csv(records, out_dir)
    r = write_report(records, out_dir)
    print(f"wrote {j.relative_to(REPO_ROOT)}")
    print(f"wrote {c.relative_to(REPO_ROOT)}")
    print(f"wrote {r.relative_to(REPO_ROOT)}")
    print(f"modules: {len(records)}")
    print(f"boundary violations: {sum(1 for v in records.values() if v['boundary_status'] == 'BOUNDARY_VIOLATION')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
