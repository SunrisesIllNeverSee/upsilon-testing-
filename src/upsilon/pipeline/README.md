# src/upsilon/pipeline/ — Layer Orchestration

**STATUS: TARGET_SCAFFOLD**

## PURPOSE

Orchestrates the semantic layers: ingestion → parsing → evidence → commitments → transformations → conservation → proof → execution → lineage → authority → propagation. The pipeline must NOT duplicate layer semantics.

## OWNS

- Orchestration of the full transformation pipeline
- Step sequencing and data flow between layers

## DOES NOT OWN

- Any layer-specific semantics (each layer owns its own)
- Transformation interpretation (transformations domain)
- Authority decisions (authority domain)
- Conservation validation (conservation domain)

## ALLOWED INPUTS

- All layer outputs

## ALLOWED OUTPUTS

- Pipeline-level orchestration results

## ALLOWED DEPENDENCIES

- All `upsilon.*` subdomains (pipeline orchestrates them)

## FORBIDDEN DEPENDENCIES

- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `semantic_pipeline.py` (root) — legacy v1 pipeline combining orchestration + mapping + execution; BOUNDARY_VIOLATION; migration precondition: legacy consumers migrated to compatibility facade or retired
- `semantic_pipeline_v2.py` (root) — combines pipeline orchestration with authority determination; BOUNDARY_VIOLATION; migration precondition: authority logic extracted to `src/upsilon/authority/`

## CURRENT IMPLEMENTED TARGET MODULES

None (`.gitkeep` only).

## OPERATING STATUS

TARGET_SCAFFOLD — no runtime code yet. The target pipeline will orchestrate the implemented layers. Placeholder for future migration.

## MIGRATION PRECONDITIONS

- Legacy `semantic_pipeline.py` consumers must be migrated to a compatibility facade or retired.
- Legacy `semantic_pipeline_v2.py` authority logic must be extracted to `src/upsilon/authority/` first.
- The target pipeline must orchestrate the implemented `src/upsilon/` layers, not re-implement their logic.
