# Smoke Test Protocol

## Fixed cases

### SW-001 — Sportsman's Warehouse, Inc.
- CIK: 0001132105
- Filing date: 2026-06-24
- Accession: 0001193125-26-281135
- Exhibit: EX-10.2
- Feature: Third Amendment with Annex A composite credit agreement.

### DKS-001 — DICK'S Sporting Goods, Inc.
- CIK: 0001089063
- Filing date: 2019-06-28
- Accession: 0001089063-19-000053
- Exhibit: EX-10.1
- Feature: Fourth Amendment with Annex A composite credit agreement.

These cases were selected prospectively because each provides an amendment and an independent composite representation useful for reconstruction checking.

## Questions

1. Can each source be downloaded and hashed reproducibly?
2. Can amendment instructions be detected?
3. Which instructions are supported automatically?
4. Which route to `UNRESOLVED`?
5. Can a human validator map instructions to commitment identities?
6. Can the executor create deterministic new state?
7. Does persistence create one state version per affected commitment per amendment?
8. Does each transition retain source authority/lineage?
9. Does reconstructed state match the composite agreement for supported fields?
10. What concrete parser failure classes appear?

## Expected result

The current deterministic parser is expected to recover high-regularity amendment instructions but not the complete agreement without human validation.

Smoke-test success means the full workflow is executable and auditable, not that publication-level parser accuracy is already achieved.
