# src/upsilon/evidence/ — Source Evidence Representation

**STATUS: TARGET_SCAFFOLD**

## PURPOSE

Represents source evidence extracted from agreements and amendments: section references, aliases, text spans, extracted values. Evidence supplies signals upward to identity resolution and transformation interpretation. Evidence does NOT grant semantic identity or authority.

## OWNS

- Source evidence structures (section refs, aliases, spans, extracted values)
- Evidence-level classification (SUFFICIENT, CORROBORATED, WEAK, INSUFFICIENT)

## DOES NOT OWN

- Semantic identity (commitments domain)
- Transformation interpretation (transformations domain)
- Authority (authority domain)

## ALLOWED INPUTS

- Parsed amendment/agreement text (from parsing domain)

## ALLOWED OUTPUTS

- Evidence structures consumed by `IdentityResolver` and `AuthorizedTransformationEngine`

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)

## FORBIDDEN DEPENDENCIES

- `upsilon.commitments` (evidence supplies signals; commitments resolve identity)
- `upsilon.transformations` (evidence is input to transformations, not a dependency)
- `upsilon.authority`, `upsilon.execution`
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `agreement_context.py` (root) — agreement context and source evidence; CLEAN; migration target: `src/upsilon/evidence/`
- `gold_schema.py` (root) — gold schema definitions; CLEAN; migration target: `src/upsilon/evidence/`
- `gt_extractor.py` (root) — ground-truth extractor; CLEAN; migration target: `src/upsilon/evidence/`
- `s0_extractor.py` (root) — S0 commitment extractor; CLEAN; migration target: `src/upsilon/evidence/`
- `commitment_registry.py` (root) — evidence alias matching entangled with identity; BOUNDARY_VIOLATION; evidence alias matching extracts to this domain

## CURRENT IMPLEMENTED TARGET MODULES

None (`.gitkeep` only).

## OPERATING STATUS

TARGET_SCAFFOLD — no runtime code yet. Placeholder for future migration.

## MIGRATION PRECONDITIONS

- Legacy `agreement_context.py` can move once its dependents are updated.
- Legacy `commitment_registry.py` must be decomposed first: identity → `commitments/`, evidence alias matching → `evidence/`.
