# Step 23G Review Report — Parts A and B

**Reviewer:** Devin (GLM-5.2 High)
**Date:** 2026-09-02
**Scope:** Part A (governance artifact accuracy + machine-generated dependency graph) and Part B (lineage as first-class semantic domain — addendum)
**Baseline commit:** `fad715c` (Step 23G scaffold)
**Working-tree changes:** Part A corrections (dependency graph, manifest projection, frozen artifact inventory, pytest config)

---

## Verdict

**ACCEPT** — both Part A and Part B are correctly implemented and ready to merge.

Part A fixed the one legitimate governance defect (manually maintained dependency data) by replacing it with machine-generated AST analysis. Part B was already fully implemented in the original Step 23G scaffold (`fad715c`); this review verifies completeness and cross-reference integrity.

---

## Part A — Governance Artifact Accuracy

### What was implemented

1. **Machine-generated dependency graph** (`audits/repository/generate_dependency_graph.py`)
   - AST analysis of all 98 root-level Python modules
   - Captures top-level imports, deferred imports (function/class/conditional scope), third-party imports
   - Builds reverse-dependency map (imported_by)
   - Classifies risk mechanically: LOW (<3 dependents), MEDIUM (3-7), HIGH (>=8)
   - Curated boundary-violation set (7 modules) with per-module migration preconditions
   - Outputs: `dependency_graph.json` (authoritative), `dependency_graph.csv`, `dependency_graph_report.md`

2. **Manifest as projection** (`audits/repository/generate_manifest.py`)
   - Reads `dependency_graph.json` and writes `REPOSITORY_MIGRATION_MANIFEST.md`
   - Regenerates byte-identically — the manifest is truly a projection, not a second truth source
   - Curated semantic mappings (destination, owner, kind, reason) are separate from machine-generated data (imports, dependents, risk, boundary)

3. **Per-module migration preconditions** (all 7 boundary violations)
   - Each violation class has distinct preconditions matching the review's recommendations:
     - `semantic_resolver_v2`: new identity/evidence/transformation interfaces exist first
     - `chain_reconstruction`: authority and execution responsibilities extracted first
     - `edgar_chains`: embedded frozen states externalized and hashed first
     - `semantic_pipeline`: legacy consumers migrated to compatibility facade or retired
   - These are not generic "decompose first" warnings — each requires a different extraction order

4. **Frozen ground-truth artifact inventory** (`data/ground_truth/frozen/`)
   - Separated from `results/frozen/` (inputs vs outputs)
   - 11-field schema per artifact: artifact_path, target_path, sha256, artifact_type, producer, producer_commit, source_corpus_version, created_at, frozen_at, supersedes, superseded_by, mutable
   - Source documents (14 EDGAR .txt files) hashed with SHA-256 for CI verification
   - 4 embedded states inventoried with externalization preconditions
   - `.gitignore` exceptions narrowly scoped to frozen artifact paths and source corpus

5. **Staged pytest configuration** (`pyproject.toml`)
   - Phase 0: `python_files = ["test_*.py"]` (no `testpaths = ["."]`)
   - Documented migration path: Phase 1 → `testpaths = ["tests", "."]`, Phase 2 → `testpaths = ["tests"]`
   - Collection boundary changes deliberately and is tested at each checkpoint

### Verification results

| Check | Result |
|-------|--------|
| `generate_dependency_graph.py` regenerates byte-identical JSON/CSV/MD | PASS |
| `generate_manifest.py` regenerates byte-identical manifest | PASS |
| `generate_manifest.py` (frozen) regenerates with stable SHA-256 hashes (timestamps differ, expected) | PASS |
| Test baseline: 919 passed, 14 skipped | PASS (matches documented baseline) |
| Conformance status: 18 NOT YET ENFORCED, 2 PARTIALLY ENFORCED, 0 ENFORCED | PASS (not superficially improved) |
| All 11 required frozen-manifest fields present, `mutable=false` for all entries | PASS |
| `.gitignore` exceptions correctly un-ignore frozen artifacts and source corpus | PASS |
| All 10 required per-module dependency-graph fields present | PASS |

### Minor observations (not rejection-worthy)

- The `.gitignore` exceptions for `data/edgar_chains/{ameresco,amedisys,bausch_lomb}/` track all files in those directories (including `.html` and `.v04.json` derived artifacts), not just the `.txt` source documents the manifest hashes. This is a minor over-inclusion but does not compromise hash verification — the manifest only hashes `.txt` files.
- The frozen manifest uses `datetime.now(UTC)` for `created_at`/`frozen_at`, so the manifest file changes on every regeneration. The source document SHA-256 hashes (the actual verification content) are stable. Acceptable for Phase 1.

---

## Part B — Lineage as First-Class Semantic Domain (Addendum)

### Implementation status

Part B was implemented in the original Step 23G scaffold (commit `fad715c`). The commit message explicitly states: "Lineage added as first-class semantic domain per addendum." This review verifies all 6 addendum requirements are fully satisfied.

### Requirement-by-requirement verification

#### 1. Lineage as first-class semantic domain — SATISFIED

- `src/upsilon/lineage/` exists with `.gitkeep` and `README.md`
- README documents all 5 conceptual ownership areas:
  - `graph.py` — commitment lineage graph
  - `nodes.py` — commitment identity nodes
  - `edges.py` — authorized transformation edges
  - `authority.py` — authority/source linkage on edges
  - `queries.py` — commitment history queries
- No runtime code implemented (correct per "Do NOT move or implement runtime code during Step 23G")
- `src/upsilon/README.md` semantic subdomains table includes lineage with full ownership description
- `STATIC_GOVERNANCE.md` import-linter contract includes `upsilon.lineage` in the layers list
- `.devin/rules.md` semantic layer quick reference includes lineage: "owns commitment history graph, may not invent transformations"

#### 2. Updated dependency direction — SATISFIED

`docs/architecture/DEPENDENCY_DIRECTION.md` contains the full semantic direction chain:

```
INGESTION → PARSING → EVIDENCE → COMMITMENT IDENTITY + KERNEL →
AUTHORIZED TRANSFORMATION → CONSERVATION VALIDATION → SEMANTIC PROOF →
EXECUTION → LINEAGE EDGE / SUCCESSOR STATE → AUTHORITY →
DOWNSTREAM PROPAGATION / COMPARISON
```

- "Lineage is not merely logging" statement present
- Lineage positioned between EXECUTION and AUTHORITY (correct: execution produces the successor state, lineage records the edge, authority consumes the result)
- Per-layer import/ownership rules include a `lineage` section:
  - owns: append-only authoritative history of transformations
  - records: predecessor/successor identity, authority/source, transformation proof
  - may not: invent transformations or grant authority independently

#### 3. Three integrity domains preserved — SATISFIED

All three domains are documented in three locations with consistent wording:

| Document | Location |
|----------|----------|
| `docs/architecture/ARCHITECTURE_INDEX.md` | "Three integrity domains" section with status column |
| `src/upsilon/README.md` | "Three integrity domains" section |
| `docs/moses/CONFORMANCE_CONTRACT.md` | "Three integrity domains" section with current status |

- Transformation Integrity: "Did authorized amendment evidence produce the correct successor state?" — Primary focus
- Lineage Integrity: "Can the current commitment be traced through valid authorized transformations?" — Scaffolded, not implemented
- Propagation Integrity: "Do downstream representations match the current authoritative kernel?" — Not yet addressed

#### 4. Commitment identity means durable lineage — SATISFIED

`src/upsilon/lineage/README.md` contains:

- The FC-001 conceptual example (amendment chain producing threshold changes and exception expansions)
- The stronger model statement: "maintain an append-only authoritative history of transformations applied to a persistent commitment identity"
- Explicit contrast with the weaker "remember which commitment this was" model

The migration manifest identifies `chain_reconstruction.py` as the existing module with lineage/state/version logic:
- Mapped to `src/upsilon/lineage/` as proposed destination
- Flagged as BOUNDARY_VIOLATION (combines lineage graph + execution state advancement + authority propagation)
- Migration preconditions: "authority and execution responsibilities extracted first" + "lineage graph retained as pure graph structure in lineage/ layer"
- The lineage README cross-references this: "The migration manifest identifies `chain_reconstruction.py` as a current module containing lineage-relevant state advancement logic."

#### 5. Original architectural anchor — SATISFIED

The original conceptual pipeline is documented in two locations:

- `docs/architecture/DEPENDENCY_DIRECTION.md` — "Original architectural anchor" section with the full pipeline:
  ```
  EDGAR → Agreement Chain → Parser → Commitment Extractor →
  Authoritative / validated Kernel → Amendment Parser →
  Authorized Change Engine → Commitment Lineage Graph →
  Current Authoritative Kernel
  ```
- `docs/architecture/ARCHITECTURE_INDEX.md` — "Original architectural anchor" section with the same pipeline and the statement: "The target architecture makes each stage an explicit semantic home with enforced ownership boundaries. Lineage is a first-class semantic domain, not a logging utility."

Both documents frame the scaffold as restoring an earlier intended structure, not inventing a new architecture.

#### 6. Conformance planning updated — SATISFIED

`docs/moses/CONFORMANCE_CONTRACT.md` contains all 7 lineage conformance invariants (L1-L7), matching the addendum exactly:

| # | Invariant (addendum) | Contract section | Status |
|---|----------------------|------------------|--------|
| L1 | each accepted transformation creates one traceable lineage edge | L1 | NOT YET ENFORCED |
| L2 | lineage edge references predecessor and successor commitment identity | L2 | NOT YET ENFORCED |
| L3 | lineage edge carries amendment authority/source | L3 | NOT YET ENFORCED |
| L4 | lineage edge carries transformation proof | L4 | NOT YET ENFORCED |
| L5 | current authoritative state is reachable from origin kernel | L5 | NOT YET ENFORCED |
| L6 | no authoritative version exists without a validated lineage path | L6 | NOT YET ENFORCED |
| L7 | downstream state cannot become canonical merely by differing from current kernel | L7 | NOT YET ENFORCED |

- All 7 invariants marked NOT YET ENFORCED (no runtime implementation, correct per addendum)
- `tests/conformance/README.md` mirrors the L1-L7 table with the same status
- Conformance test placement rules documented: tests must assert against real runtime, not mocks; failing tests must fail or skip with documented reason, not pass vacuously

### Cross-reference integrity (Part A ↔ Part B)

| Link | Verified |
|------|----------|
| Manifest `chain_reconstruction` row → `src/upsilon/lineage/` destination | PASS |
| Manifest boundary-violation preconditions → lineage README "Existing modules" section | PASS |
| Dependency graph report → boundary violations with lineage preconditions | PASS |
| Lineage README → conformance contract L1-L7 | PASS |
| Conformance contract → `tests/conformance/` placement | PASS |
| `ARCHITECTURE_INDEX.md` → lineage README + dependency graph report + frozen README | PASS |
| `STATIC_GOVERNANCE.md` → dependency graph artifacts + 7 boundary violations (includes lineage) | PASS |
| `.devin/rules.md` → lineage layer in quick reference | PASS |
| `src/upsilon/README.md` → lineage README + three integrity domains | PASS |

---

## Combined judgment

### Part A
The Phase 1 architecture is acceptable after the manifest was regenerated from machine-generated data. The governance defect (manually maintained dependency counts) is fixed. The frozen artifact inventory with SHA-256 hashes and the `data/ground_truth/frozen/` vs `results/frozen/` separation are correct and enforceable via CI.

### Part B
The addendum is fully implemented. Lineage is a first-class semantic domain in the target architecture, the dependency direction includes it between execution and authority, the three integrity domains are preserved, the durable-lineage model is documented, the original architectural anchor is referenced, and all 7 lineage conformance invariants (L1-L7) are planned with honest NOT YET ENFORCED status.

### Phase 2 readiness

The combined Part A + Part B state establishes clear preconditions for Phase 2:

1. **Before moving `edgar_chains.py`**: externalize frozen states to `data/ground_truth/frozen/` with hashes (Part A inventory + Part B preconditions)
2. **Before moving `chain_reconstruction.py`**: extract authority and execution responsibilities, retain pure lineage graph (Part A preconditions + Part B lineage domain)
3. **Before moving `semantic_resolver_v2.py`**: new identity/evidence/transformation interfaces (Part A preconditions + Part B lineage integrity)
4. **Before any migration checkpoint**: regenerate dependency graph, verify no new violations (Part A manifest projection)
5. **Before any invariant becomes ENFORCED**: runtime enforcement + dedicated conformance test + failure-path test (Part A conformance discipline + Part B L1-L7)

No restart or redesign is needed. This is a sound Phase 1 with one fixed governance defect and a complete lineage domain scaffold.
