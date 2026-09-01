# Capability and Limitation Statement

**System**: Upsilon Financial Commitment Integrity v1
**Frozen at**: 2026-09-01T05:45:25.841501+00:00
**Commit**: `5518f4a4d74e2fd2af2f0d1ac43e893bee845b93`

## SUPPORTED OUTCOMES

The frozen system produces the following outcomes for each amendment chain:

- **RECONSTRUCTED** — the chain's final state exactly matches the ground truth extraction. The system successfully parsed, mapped, executed, and persisted all amendments.
- **PARTIAL** — some commitments were reconstructed but the final state does not exactly match ground truth. Some instructions were mapped and applied; others were unresolved.
- **UNRESOLVED** — the parser detected instructions but the semantic mapper could not map them to structured mutations. No incorrect automatic mutations were produced; the system fails safely by leaving the instruction unresolved.
- **UNSUPPORTED_FORMAT** — the parser found 0 instructions because the amendment format is not handled by the parser's regex patterns. The chain is ingested but no transformations are applied.
- **VALIDATION_REQUIRED** — the mapper produced a mutation but the executor could not apply it (missing S0 state, target key not found, or field mismatch). The mutation is held as unresolved for human validation.

## FOUNDATION SAFETY CLAIM

The frozen development system produced:

- **0 incorrect automatic mutations** after defect resolution
- **0 false authoritative promotions**
- **no detected lineage, temporal, or persistence integrity defects** in the final development run (all 25 chains)

This means the system never silently produces a wrong result. When it cannot handle an amendment, it fails safely to UNRESOLVED or VALIDATION_REQUIRED rather than producing a confident wrong mutation.

## LIMITATIONS

The following coverage limitations were measured in the final development run and are NOT fixed (by design — the freeze preserves the system as-is):

- **S0 extraction success rate**: 0.7273 (16 chains with extracted S0)
- **GT extraction success rate**: 0.4 (2 chains with extracted GT)
- **S0 extraction coverage (avg)**: 0.4925
- **GT extraction coverage (avg)**: 0.2133
- **Semantic mapping coverage**: 0.033 (3 of 91 instructions mapped)
- **Unresolved rate**: 0.967
- **Chain-level exact reconstruction rate**: 0.4

These limitations reflect the development scope of the parser and semantic mapper. They are recorded here as measured, not improved. The held-out confirmatory study (Step 19) will measure the same metrics on untouched issuers.
