#!/usr/bin/env python3
"""One-shot migration script: move root modules into their target homes and rewrite imports.

This moves every root-level .py module to its target destination (per
generate_manifest.py MODULE_META), creates __init__.py files where needed,
and rewrites all import statements across the entire codebase.

Strategy:
  - Runtime modules -> src/upsilon/<domain>/  : imports become upsilon.<domain>.<module>
  - Audit modules   -> audits/<subdir>/        : imports become audits.<subdir>.<module>
  - Research modules-> research/<subdir>/      : imports become research.<subdir>.<module>
  - Data modules    -> data/                   : imports become data.<module>
  - Test corpus     -> tests/corpus/           : imports become tests.corpus.<module>
  - Test files      -> tests/<category>/       : pytest discovers them; imports rewritten
  - Legacy archive  -> archive/legacy_code/    : imports become archive.legacy_code.<module>

Special case: models.py -> src/upsilon/models/legacy_models.py (avoids package/module clash)
"""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Load MODULE_META from generate_manifest.py
spec = importlib.util.spec_from_file_location("gen", REPO / "audits/repository/generate_manifest.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def get_target_path(module_name: str, meta: dict) -> Path:
    """Return the full destination file path for a module."""
    dest = meta["dest"].rstrip("/") + "/"
    # Special case: models.py clashes with the upsilon.models package name
    if module_name == "models" and "upsilon/models" in dest:
        return REPO / f"{dest}legacy_models.py"
    return REPO / f"{dest}{module_name}.py"


def get_new_import_path(module_name: str, meta: dict) -> str:
    """Return the new dotted import path for a module."""
    dest = meta["dest"].rstrip("/")
    # Special case
    if module_name == "models" and "upsilon/models" in dest:
        return "upsilon.models.legacy_models"
    # Convert path to dotted import: src/upsilon/parsing/ -> upsilon.parsing
    # audits/failure_census/ -> audits.failure_census
    # research/methodology/ -> research.methodology
    # tests/unit/ -> tests.unit
    # data/ -> data
    # archive/legacy_code/ -> archive.legacy_code
    parts = dest.split("/")
    # Drop "src/" prefix
    if parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts) + "." + module_name


def collect_modules_to_move() -> dict[str, tuple[Path, str]]:
    """Return {module_name: (target_path, new_import_path)} for all root .py files."""
    result = {}
    for name, meta in gen.MODULE_META.items():
        src = REPO / f"{name}.py"
        if not src.exists():
            continue
        target = get_target_path(name, meta)
        new_import = get_new_import_path(name, meta)
        result[name] = (target, new_import)
    return result


def ensure_init_files(dir_path: Path):
    """Create __init__.py in directory and all parent dirs up to repo root (for package dirs)."""
    # Only create for directories under src/upsilon/, tests/, audits/, research/, data/, archive/
    pkg_roots = ["src/upsilon", "tests", "audits", "research", "data", "archive"]
    for root in pkg_roots:
        root_path = REPO / root
        try:
            rel = dir_path.relative_to(root_path)
        except ValueError:
            continue
        # Create __init__.py in dir_path and all parents up to (but not including) root
        current = dir_path
        while current != root_path and current.is_relative_to(root_path):
            init_file = current / "__init__.py"
            if not init_file.exists():
                init_file.write_text("")
            current = current.parent
    # Also ensure the root itself has __init__.py if it's a package root
    for root in pkg_roots:
        root_path = REPO / root
        if root_path.exists():
            init_file = root_path / "__init__.py"
            if not init_file.exists() and root in ("tests", "audits", "research", "data", "archive"):
                # Only add __init__.py to tests/, audits/, research/, data/, archive/ if needed
                # Actually, for pytest testpaths, tests/ doesn't need __init__.py
                # For importability, we'll add these to pythonpath instead
                pass


def rewrite_imports_in_file(filepath: Path, import_map: dict[str, str]):
    """Rewrite import statements in a single .py file using the import_map."""
    if not filepath.exists():
        return 0

    content = filepath.read_text()
    lines = content.split("\n")
    changes = 0

    for i, line in enumerate(lines):
        original = line

        # Pattern 1: import X  or  import X as Y
        # Match: ^(\s*)import X(\s+as\s+\w+)?(\s*#.*)?$
        m = re.match(r'^(\s*)import\s+([a-zA-Z_]\w*)(\s+as\s+(\w+))?(\s*#.*)?$', line)
        if m:
            indent, mod_name, _, alias, comment = m.groups()
            if mod_name in import_map:
                new_path = import_map[mod_name]
                if alias:
                    lines[i] = f"{indent}import {new_path} as {alias}{comment or ''}"
                else:
                    # Use 'as' to preserve the original module name for usage
                    lines[i] = f"{indent}import {new_path} as {mod_name}{comment or ''}"
                changes += 1
                continue

        # Pattern 2: import X, Y, Z  (multiple modules on one line)
        m = re.match(r'^(\s*)import\s+(.+)$', line)
        if m and ',' in m.group(2):
            indent, imports_str = m.groups()
            # Split by comma, rewrite each
            parts = [p.strip() for p in imports_str.split(',')]
            new_parts = []
            changed = False
            for part in parts:
                pm = re.match(r'([a-zA-Z_]\w*)(\s+as\s+(\w+))?', part)
                if pm:
                    mod_name = pm.group(1)
                    alias = pm.group(3)
                    if mod_name in import_map:
                        new_path = import_map[mod_name]
                        if alias:
                            new_parts.append(f"{new_path} as {alias}")
                        else:
                            new_parts.append(f"{new_path} as {mod_name}")
                        changed = True
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            if changed:
                lines[i] = f"{indent}import {', '.join(new_parts)}"
                changes += 1
                continue

        # Pattern 3: from X import Y  or  from X import Y, Z
        m = re.match(r'^(\s*)from\s+([a-zA-Z_]\w*)\s+import\s+(.+)$', line)
        if m:
            indent, mod_name, imports_str = m.groups()
            if mod_name in import_map:
                new_path = import_map[mod_name]
                lines[i] = f"{indent}from {new_path} import {imports_str}"
                changes += 1
                continue

        # Pattern 4: from X.Y import Z (dotted module, check if first component is a root module)
        m = re.match(r'^(\s*)from\s+([a-zA-Z_]\w*)\.([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\s+import\s+(.+)$', line)
        if m:
            indent, first_component, rest, imports_str = m.groups()
            if first_component in import_map:
                new_path = import_map[first_component]
                lines[i] = f"{indent}from {new_path}.{rest} import {imports_str}"
                changes += 1
                continue

    if changes > 0:
        filepath.write_text("\n".join(lines))

    return changes


def main():
    print("=== File Migration Script ===")
    print(f"Repository: {REPO}")
    print()

    # Step 1: Collect modules to move
    modules = collect_modules_to_move()
    print(f"Modules to move: {len(modules)}")

    # Build import map: old_name -> new_dotted_path
    import_map = {name: new_import for name, (_, new_import) in modules.items()}
    print(f"Import map entries: {len(import_map)}")
    print()

    # Print the map
    for name in sorted(import_map):
        print(f"  {name} -> {import_map[name]}")
    print()

    # Step 2: Move files
    moved = 0
    for name, (target, new_import) in sorted(modules.items()):
        src = REPO / f"{name}.py"
        if not src.exists():
            print(f"  SKIP (not found): {name}.py")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(target))
        moved += 1
        print(f"  MOVED: {name}.py -> {target.relative_to(REPO)}")

    print(f"\nMoved {moved} files")
    print()

    # Step 3: Create __init__.py files in new directories
    print("Creating __init__.py files...")
    dirs_needing_init = set()
    for name, (target, _) in modules.items():
        d = target.parent
        dirs_needing_init.add(d)

    for d in sorted(dirs_needing_init):
        # Create __init__.py in the target directory and all parent dirs
        # up to the package root, but only for src/upsilon/ paths
        rel = d.relative_to(REPO)
        parts = rel.parts

        if parts[0] == "src" and parts[1] == "upsilon":
            # Create __init__.py in d and all parents from src/upsilon/ down
            current = REPO / "src" / "upsilon"
            for part in parts[2:]:
                current = current / part
                init = current / "__init__.py"
                if not init.exists():
                    init.write_text("")
                    print(f"  CREATED: {init.relative_to(REPO)}")
        elif parts[0] in ("audits", "research", "data", "archive"):
            # For non-src packages, add __init__.py to make them importable
            current = REPO / parts[0]
            init = current / "__init__.py"
            if not init.exists():
                init.write_text("")
                print(f"  CREATED: {init.relative_to(REPO)}")
            for part in parts[1:]:
                current = current / part
                init = current / "__init__.py"
                if not init.exists():
                    init.write_text("")
                    print(f"  CREATED: {init.relative_to(REPO)}")
        elif parts[0] == "tests":
            # tests/ subdirectories — create __init__.py for package imports
            current = REPO / "tests"
            for part in parts[1:]:
                current = current / part
                init = current / "__init__.py"
                if not init.exists():
                    init.write_text("")
                    print(f"  CREATED: {init.relative_to(REPO)}")

    print()

    # Step 4: Rewrite imports in ALL .py files
    print("Rewriting imports...")
    total_changes = 0
    files_changed = 0

    all_py_files = []
    for root, dirs, files in os.walk(REPO):
        # Skip .git, .venv, __pycache__
        dirs[:] = [d for d in dirs if d not in ('.git', '.venv', '__pycache__')]
        for f in files:
            if f.endswith('.py'):
                all_py_files.append(Path(root) / f)

    for pyfile in sorted(all_py_files):
        changes = rewrite_imports_in_file(pyfile, import_map)
        if changes > 0:
            files_changed += 1
            total_changes += changes
            print(f"  {pyfile.relative_to(REPO)}: {changes} import(s) rewritten")

    print(f"\nRewrote {total_changes} imports across {files_changed} files")
    print()

    # Step 5: Update pyproject.toml pythonpath
    print("Updating pyproject.toml pythonpath...")
    pyproject = REPO / "pyproject.toml"
    content = pyproject.read_text()
    # Add audits, research, data, archive, tests to pythonpath
    # Current: pythonpath = ["src"]
    # New: pythonpath = ["src", "audits", "research", "data", "archive", "tests"]
    old = 'pythonpath = ["src"]'
    new = 'pythonpath = ["src", "audits", "research", "data", "archive", "tests"]'
    if old in content:
        content = content.replace(old, new)
        pyproject.write_text(content)
        print(f"  Updated pythonpath: {old} -> {new}")
    else:
        print(f"  WARNING: could not find '{old}' in pyproject.toml")

    print()
    print("=== Migration complete ===")
    print("Next steps:")
    print("  1. Run: pytest -q")
    print("  2. Fix any remaining import errors")
    print("  3. Regenerate dependency graph: python3 audits/repository/generate_dependency_graph.py")


if __name__ == "__main__":
    main()
