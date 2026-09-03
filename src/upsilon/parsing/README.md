# src/upsilon/parsing/ — Lexical/Structural Parsing

**STATUS: TARGET_SCAFFOLD**

## PURPOSE

Produces structured parse instructions and lexical evidence from agreement and amendment text. Parsing must NOT import execution or authority modules.

## OWNS

- Amendment instruction parsing (REPLACE_VALUE, ADD, DELETE, etc.)
- Pattern classification (INCREMENTAL, FULL_RESTATEMENT, etc.)
- Genre-specific parsing adapters
- Shared extraction engine (used by S0 and GT extractors)

## DOES NOT OWN

- Evidence representation (evidence domain)
- Transformation interpretation (transformations domain)
- Authority (authority domain)

## ALLOWED INPUTS

- Normalized document text (from ingestion domain)

## ALLOWED OUTPUTS

- Structured parse instructions
- Lexical evidence signals
- Pattern classifications

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects)

## FORBIDDEN DEPENDENCIES

- `upsilon.execution`, `upsilon.authority`
- `upsilon.transformations`, `upsilon.conservation`, `upsilon.proof`
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `amendment_parser.py` (root) — parser producing structured instructions; CLEAN; migration target: `src/upsilon/parsing/`
- `commitment_extractor.py` (root) — shared extraction engine; CLEAN; migration target: `src/upsilon/parsing/`
- `pattern_classifier.py` (root) — amendment pattern classification; CLEAN; migration target: `src/upsilon/parsing/`
- `genre_adapters.py` (root) — genre-specific parsing adapters; CLEAN; migration target: `src/upsilon/parsing/`

## CURRENT IMPLEMENTED TARGET MODULES

None (`.gitkeep` only).

## OPERATING STATUS

TARGET_SCAFFOLD — no runtime code yet. Placeholder for future migration.

## MIGRATION PRECONDITIONS

- Legacy `amendment_parser.py` has many dependents (HIGH risk); migration requires updating all callers.
- Legacy `genre_adapters.py` imports several boundary-violation modules; those must be resolved first.
