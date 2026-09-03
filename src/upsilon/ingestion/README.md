# src/upsilon/ingestion/ — EDGAR Acquisition, Document Discovery, Normalization

**STATUS: TARGET_SCAFFOLD**

## PURPOSE

Acquires documents from SEC EDGAR, discovers filing chains, and normalizes text. Ingestion is the entry point of the pipeline. It must NOT import execution or authority modules.

## OWNS

- EDGAR document acquisition
- Filing chain discovery
- Text normalization
- Frozen chain data externalization

## DOES NOT OWN

- Parsing (parsing domain)
- Evidence extraction (evidence domain)
- Transformation interpretation (transformations domain)

## ALLOWED INPUTS

- SEC EDGAR URLs and filing identifiers

## ALLOWED OUTPUTS

- Acquired and normalized document text

## ALLOWED DEPENDENCIES

- `upsilon.models` (shared value objects, if needed)
- Third-party: `httpx`, `bs4`

## FORBIDDEN DEPENDENCIES

- `upsilon.execution`, `upsilon.authority`
- `upsilon.transformations`, `upsilon.conservation`, `upsilon.proof`
- Any root-level legacy module
- `audits/`, `research/`, `results/`

## CURRENT LEGACY SOURCES

- `edgar_chains.py` (root) — ingestion fixtures + frozen chain data + hand-extracted states; BOUNDARY_VIOLATION; migration precondition: embedded frozen states externalized to `data/ground_truth/frozen/` with hashes
- `sec_ingest.py` (root) — SEC EDGAR ingestion logic; CLEAN; migration target: `src/upsilon/ingestion/edgar/`
- `discovery_validation.py` (root) — validates acquired documents; CLEAN; migration target: `src/upsilon/ingestion/document_discovery/`
- `acquire_chain_study.py`, `acquire_comparison_sources.py`, `acquire_held_out_study.py` (root) — acquisition scripts; research kind; migration target: `src/upsilon/ingestion/`

## CURRENT IMPLEMENTED TARGET MODULES

None (`.gitkeep` only in `document_discovery/`, `edgar/`, `normalization/`).

## OPERATING STATUS

TARGET_SCAFFOLD — no runtime code yet. Placeholder for future migration.

## MIGRATION PRECONDITIONS

- Legacy `edgar_chains.py` frozen states must be externalized and hashed before migration.
- Legacy `sec_ingest.py` can move once dependents are updated.
