# Static Governance — Import Boundary Enforcement

This document distinguishes the **current legacy layout** from the
**target enforced layout** and describes how CI enforcement will activate
as modules migrate.

## Current legacy layout

The repository currently uses a flat layout with all runtime Python files
at the repository root. Import boundaries are **not enforced**.

Enforcing import rules against the current flat layout would immediately
break the build because:

- all modules are in the same directory (no package boundaries exist);
- `commitment_registry`, `semantic_resolver_v2`, `semantic_mapper`, and
  `semantic_pipeline_v2` are known boundary violations that would fail
  any layer-based import check;
- migration has not yet occurred.

**No static governance is enforced against the current legacy layout.**

## Target enforced layout

Once modules migrate to `src/upsilon/<layer>/`, import boundaries can be
enforced using:

- `import-linter` (Python import dependency checker)
- or a custom lint script checking `importlib` / AST import statements

### Proposed import-linter contract

```ini
[importlinter]
root_package = upsilon

[importlinter:contract:layered]
name = Upsilon layered architecture
type = layers
layers =
    upsilon.ingestion
    upsilon.parsing
    upsilon.evidence
    upsilon.commitments
    upsilon.transformations
    upsilon.conservation
    upsilon.proof
    upsilon.execution
    upsilon.lineage
    upsilon.authority
    upsilon.pipeline
```

### Activation plan

1. **Phase 0 (current):** No enforcement. Document the target.
2. **Phase 1:** After `models.py` and clean single-responsibility modules
   migrate, enable `import-linter` in **advisory mode** (warnings only).
3. **Phase 2:** After boundary-violation modules are split, enable
   `import-linter` in **enforcing mode** (CI failure on violations).
4. **Phase 3:** Add conformance test gates from
   `docs/moses/CONFORMANCE_CONTRACT.md` to CI.

## Current status

```
ENFORCEMENT STATUS: PHASE 0 (documented, not enforced)
```

No `import-linter` configuration is installed in Step 23G. This document
records the plan for future activation.
