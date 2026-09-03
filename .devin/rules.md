# Agent Governance Rules — Upsilon/MO§ES™

These rules govern agent behavior when modifying the Upsilon repository.

## Mandatory decision rule

> Before modifying runtime code, identify which semantic layer owns the
> problem.

Agents must not solve semantic problems by defaulting to the nearest
existing file. The semantic layers and their ownership are defined in
`docs/architecture/DEPENDENCY_DIRECTION.md`.

## Prohibited actions

The following actions are explicitly prohibited:

1. **Adding lexical rules inside the executor.** The executor applies
   already-validated structured transformations. It must not contain EDGAR
   lexical heuristics or text-based semantic interpretation.

2. **Granting semantic identity from raw section number alone.** Global
   section numbers and aliases are evidence mechanisms, not semantic
   authority. Section numbers may supply evidence upward but may not, by
   themselves, establish authoritative commitment identity.

3. **Using audit truth as production lookup data.** Audit and research
   modules may import runtime code, but runtime code must never import
   audit or research modules.

4. **Importing research/audit modules into runtime.** Runtime code must
   not depend on `audits/`, `research/`, or `results/` modules.

5. **Bypassing conservation validation.** Transformations must pass
   through conservation validation before execution. No path may skip
   this step.

6. **Broadening the frozen ontology without explicit authorization.** The
   13 commitment classes are frozen. No agent may add, remove, or rename
   classes without explicit user authorization.

## Dependency direction reporting

When a requested change appears to violate the dependency direction defined
in `docs/architecture/DEPENDENCY_DIRECTION.md`, the agent must:

1. **stop** before implementing the change;
2. **report** which dependency direction rule would be violated;
3. **propose** an alternative that respects the boundary, or ask for
   clarification.

## Semantic layer quick reference

| Layer | Owns | May not |
|-------|------|---------|
| ingestion | document acquisition | import execution/authority |
| parsing | lexical/structural parsing | import execution/authority |
| evidence | source evidence representation | grant identity/authority |
| commitments | identity and canonical state | depend on authority |
| transformations | operations over commitment state | grant authority |
| conservation | transformation validation | perform raw EDGAR parsing |
| proof | validated transformation evidence | invent interpretation |
| execution | apply validated transformations | contain EDGAR heuristics |
| authority | consume execution+proof+conservation | inspect raw EDGAR text |
| lineage | commitment history graph | invent transformations |
| pipeline | orchestrate layers | duplicate layer semantics |

## Frozen artifact rules

See `docs/methodology/FROZEN_ARTIFACT_POLICY.md`. Agents must not:

- overwrite frozen results;
- silently regenerate frozen results;
- modify the frozen v1 held-out study;
- modify Step 23R diagnostic artifacts.

## Repository operating model

The repository is MIXED TRANSITIONAL. See `REPOSITORY_STRUCTURE.md` for the
full operating model.

- `src/upsilon/**` is the authoritative target runtime architecture.
- Root-level Python modules are legacy/transitional surfaces, not default
  homes for new architecture.
- `tests/**` is the authoritative target test architecture.

> New runtime modules must not be created at repository root.

> Legacy root modules are maintenance/transitional surfaces, not default
> homes for new architecture.

> Absence of automated enforcement does not authorize a boundary violation.

## Migration rules

See `docs/architecture/REPOSITORY_MIGRATION_MANIFEST.md`. As of Step 23G-R:

- seven target domains under `src/upsilon/` contain real runtime
  implementation (TARGET_ACTIVE): authority, commitments, conservation,
  lineage, models, proof, transformations;
- five domains remain TARGET_SCAFFOLD: evidence, execution, ingestion,
  parsing, pipeline;
- one domain is newly scaffolded: propagation;
- legacy root modules have not been moved;
- agents must not move files without explicit authorization;
- agents must not split boundary-violation modules without explicit
  authorization;
- agents must not add new semantic responsibility to a legacy root module
  when a target `src/upsilon/` domain already owns that responsibility,
  except through an explicitly documented temporary compatibility change.

## Test preservation

See `REPOSITORY_STRUCTURE.md` §C for the test architecture and collection
policy.

- the test collection baseline must not fall unexpectedly because tests
  stopped being collected;
- new tests for target runtime code (`src/upsilon/`) must live in the
  appropriate `tests/<category>/` directory, not at repository root;
- legacy root tests must not be mass-moved without explicit authorization;
- a migration checkpoint must fail if the collected test count drops below
  the recorded baseline without an explicit accounting.

## Conformance promotion

See `docs/moses/CONFORMANCE_CONTRACT.md` for the L1–L7 lineage invariants
and `docs/moses/CONSERVATION_INVARIANTS.md` for the §2.1–§2.10 conservation
invariants.

- a conformance status may not be promoted to ENFORCED without the
  required conformance tests under `tests/conformance/`;
- target runtime code that implements an invariant must be backed by a
  formal conformance test before its status is promoted;
- absence of a conformance test does not authorize claiming an invariant
  is enforced.

## Static governance enforcement status

See `docs/architecture/STATIC_GOVERNANCE.md` for the import-linter contract
and the enforcement activation plan, and
`audits/repository/STATIC_GOVERNANCE_ENFORCEMENT_MATRIX.md` for the
rule-by-rule enforcement state.

As of Step 23G-R, no static governance is enforced via CI. All rules are
documented. Enforcement activation is planned for Phase 2 (advisory) and
Phase 3 (enforcing).
