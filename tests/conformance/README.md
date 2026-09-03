# tests/conformance/ — MO§ES™ Conformance Test Surface

This directory is the home for conformance tests enforcing the MO§ES™
commitment model invariants defined in
`docs/moses/CONFORMANCE_CONTRACT.md`.

## Current state

**No conformance tests are implemented yet.**

As of Step 23G-R, the target runtime under `src/upsilon/` implements the
conservation invariants (§2.1–§2.10) and lineage graph (L1–L7 support
structures), but conformance tests asserting these invariants against the
real runtime have not yet been written. The 72 unit tests in
`tests/unit/test_upsilonsrc.py` test the runtime directly but are not
formal conformance tests.

This directory is a structural scaffold. It must not contain fake passing
tests or meaningless placeholders.

## Invariant families

The following invariant families must be enforced by future conformance
tests. Each family corresponds to a section of the conformance contract.

| # | Invariant | Status |
|---|-----------|--------|
| 1 | Identity persistence | NOT YET ENFORCED |
| 2 | Target ≠ reference | NOT YET ENFORCED |
| 3 | Old-value consistency | NOT YET ENFORCED |
| 4 | Unchanged-field conservation | PARTIALLY ENFORCED |
| 5 | No unsupported semantic gain | NOT YET ENFORCED |
| 6 | No silent semantic loss | NOT YET ENFORCED |
| 7 | State-lineage continuity | NOT YET ENFORCED |
| 8 | Temporal transformation validity | PARTIALLY ENFORCED |
| 9 | OUT_OF_SCOPE isolation | NOT YET ENFORCED |
| 10 | Semantic proof completeness | NOT YET ENFORCED |
| 11 | Incorrect semantic mutation cannot become authoritative | NOT YET ENFORCED |
| 12 | Restatement preserves identity while deriving delta | NOT YET ENFORCED |
| 13 | Renumbering preserves commitment identity | NOT YET ENFORCED |

## Lineage invariants

| # | Invariant | Status |
|---|-----------|--------|
| L1 | Each accepted transformation creates one traceable lineage edge | NOT YET ENFORCED |
| L2 | Lineage edge references predecessor and successor commitment identity | NOT YET ENFORCED |
| L3 | Lineage edge carries amendment authority/source | NOT YET ENFORCED |
| L4 | Lineage edge carries transformation proof | NOT YET ENFORCED |
| L5 | Current authoritative state is reachable from origin kernel | NOT YET ENFORCED |
| L6 | No authoritative version exists without a validated lineage path | NOT YET ENFORCED |
| L7 | Downstream state cannot become canonical merely by differing from current kernel | NOT YET ENFORCED |

## Rules for future conformance tests

1. Each test must assert the invariant against the **real runtime**, not a mock.
2. If the current system does not satisfy an invariant, the test must **fail**
   or be **skipped with a documented reason** — not pass vacuously.
3. Conformance tests must not be weakened to make the build green.
4. When an invariant transitions from `NOT YET ENFORCED` to `ENFORCED`,
   the conformance contract must be updated to reflect the change.
