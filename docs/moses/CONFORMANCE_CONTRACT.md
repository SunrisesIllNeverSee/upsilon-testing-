# MO§ES™ Conformance Contract

This document defines the invariant families that future conformance tests
must enforce for the Upsilon/MO§ES™ commitment model.

**No conformance tests are implemented in Step 23G.**

Each invariant is marked with its current enforcement status:

- `ENFORCED` — the current runtime enforces this invariant
- `NOT YET ENFORCED` — the current runtime does not enforce this invariant
- `PARTIALLY ENFORCED` — the current runtime enforces this invariant in some paths but not all

A conformance directory full of meaningless placeholders is not acceptable.
Where the current system does not satisfy an invariant, it is documented
as `NOT YET ENFORCED` with a reference to the known gap.

---

## Conformance Promotion Rule (Step 23M)

This is a permanent governance rule.  See
[CONFORMANCE_MATRIX.md](CONFORMANCE_MATRIX.md) for the full matrix.

```
ENFORCED(I)
iff
RuntimeGuard(I)
AND PositiveTest(I)
AND ViolationTest(I)
```

An invariant `I` may not be marked `ENFORCED` because documentation
says it exists or because ordinary tests happen to pass.

### Required before promotion to `ENFORCED`

1. **Explicit runtime enforcement** — a runtime guard (code) that
   checks the invariant and blocks violations.
2. **Valid-case test** — a test that confirms the guard allows
   legitimate transformations.
3. **Violation/failure-path test** — a test that confirms the guard
   blocks the prohibited behavior.

### Promotion levels

| Level | Meaning |
|-------|---------|
| `ENFORCED` | All three requirements met: runtime guard + positive test + violation test |
| `PARTIALLY ENFORCED` | Runtime guard exists in some paths but not all, OR positive test exists but violation test does not |
| `NOT YET ENFORCED` | No runtime guard, or guard exists but no tests prove it works |
| `DOCUMENTED` | Invariant is specified in documentation but has no runtime guard and no tests |

An invariant may not skip levels.  `DOCUMENTED` →
`NOT YET ENFORCED` → `PARTIALLY ENFORCED` → `ENFORCED` requires the
corresponding evidence at each step.

### CI behavior

A failed MO§ES™ conformance invariant must be capable of failing CI
**even if hundreds of ordinary unit tests pass**.  Conformance tests
are not advisory.  They are gating.

---

## Invariant families

### 1. Identity persistence

> A commitment's canonical identity persists across authorized transformations.

**Status: NOT YET ENFORCED**

The current runtime has effectively 0 dedicated tests for explicit commitment
identity preservation. `CommitmentState.canonical_key` exists but is not
verified to remain stable across amendment execution. New commitments created
by `ADD` receive default values for omitted fields, which can break identity
continuity when a legal successor is reconstructed as a new object.

### 2. Target ≠ reference

> An amendment's target commitment must not be confused with the reference
> commitment used for evidence lookup.

**Status: NOT YET ENFORCED**

The current resolver does not distinguish target commitment from reference
commitment in a way that is conformance-tested. Section-reference mapping
in `commitment_registry.resolve_commitment_from_text()` can resolve to the
wrong commitment when multiple commitments share a section number.

### 3. Old-value consistency

> The old value recorded in a transformation must match the predecessor
> state's actual value for the targeted field.

**Status: NOT YET ENFORCED**

The resolver discards parser-provided `old_value` and re-extracts values
from source text. There is no predecessor-state old-value check. This is
the highest-leverage safety gap identified in the forensic audit.

### 4. Unchanged-field conservation

> Fields not targeted by an amendment must remain unchanged after execution.

**Status: PARTIALLY ENFORCED**

The executor deep-copies state before amendment execution and mutates
existing commitments in place, so untargeted fields normally remain
unchanged. However, new commitments created by `ADD` receive model defaults
for omitted fields, so information can disappear when a legal successor is
reconstructed as a new object. There is no comprehensive invariant test.

### 5. No unsupported semantic gain

> A transformation must not introduce semantic content not supported by
> amendment evidence.

**Status: NOT YET ENFORCED**

The 4 OUT_OF_SCOPE accepted mutations from HELD-017 demonstrate that the
resolver/mapper can generate facility exception additions from
acquisition/debt-incurrence language that independent eligibility correctly
classifies as ancillary. There are 0 tests asserting no mutation is produced
for OUT_OF_SCOPE instructions.

### 6. No silent semantic loss

> A transformation must not silently drop semantic content from the
> predecessor state.

**Status: NOT YET ENFORCED**

When `ADD` creates a new commitment to represent a legal successor, omitted
fields receive model defaults rather than being inherited from the
predecessor. This can silently drop exceptions, scope, grace periods, or
other fields.

### 7. State-lineage continuity

> The current authoritative state must be reachable from the origin kernel
> through a valid chain of authorized transformations.

**Status: NOT YET ENFORCED**

`chain_reconstruction.py` advances state through amendments, but there is
no conformance test verifying that the final state is reachable from the
origin through valid lineage edges. Lineage is not yet a first-class
enforced domain.

### 8. Temporal transformation validity

> A transformation's effective date must be valid relative to the
> commitment's existing temporal bounds.

**Status: PARTIALLY ENFORCED**

There are 7 temporal transition tests, but they do not comprehensively
cover all temporal validity constraints (e.g., `valid_from`/`valid_to`
consistency, amendment ordering relative to effective dates).

### 9. OUT_OF_SCOPE isolation

> Instructions classified as OUT_OF_SCOPE must not produce accepted mutations.

**Status: NOT YET ENFORCED**

The Step 23R audit recorded 4 OUT_OF_SCOPE accepted mutations from
HELD-017. There are 0 tests asserting that OUT_OF_SCOPE instructions
produce no mutation.

### 10. Semantic proof completeness

> Every accepted transformation must carry complete semantic proof evidence.

**Status: NOT YET ENFORCED**

The current runtime does not produce structured semantic proof records.
The `proof/` domain is a target architectural home with no current
implementation.

### 11. Incorrect semantic mutation cannot become authoritative

> An incorrectly accepted mutation must not result in an authoritative step.

**Status: NOT YET ENFORCED**

The false authoritative promotion in the HELD-017 chain demonstrates this
gap. Authority is currently determined by completion and unresolved counts,
not semantic correctness. There are 5 authority safety tests, but they do
not cover the case where an incorrectly accepted mutation coexists with
an authoritative step.

### 12. Restatement preserves identity while deriving delta

> A restated section must preserve the commitment identity while deriving
> the semantic delta from the restated text.

**Status: NOT YET ENFORCED**

41 of 78 failed IN_SCOPE rows fall into the `MULTI_FIELD_DECOMPOSITION`
failure family. The current runtime lacks a structured delta representation
for multi-field restatements. This is a MO§ES protocol insufficiency.

### 13. Renumbering preserves commitment identity

> Section renumbering must not break commitment identity linkage.

**Status: NOT YET ENFORCED**

The current section-to-commitment mapping in
`semantic_mapper._section_to_commitment_id()` uses exact or prefix matching
over a small section map. Renumbering is not handled.

---

## Lineage conformance invariants (from Step 23G addendum)

The following invariants extend the conformance surface to cover lineage
as a first-class semantic domain.

### L1. Each accepted transformation creates one traceable lineage edge

**Status: NOT YET ENFORCED**

The lineage domain has no current runtime implementation.

### L2. Lineage edge references predecessor and successor commitment identity

**Status: NOT YET ENFORCED**

### L3. Lineage edge carries amendment authority/source

**Status: NOT YET ENFORCED**

### L4. Lineage edge carries transformation proof

**Status: NOT YET ENFORCED**

### L5. Current authoritative state is reachable from origin kernel

**Status: NOT YET ENFORCED**

### L6. No authoritative version exists without a validated lineage path

**Status: NOT YET ENFORCED**

### L7. Downstream state cannot become canonical merely by differing from current kernel

**Status: NOT YET ENFORCED**

---

## Three integrity domains

| Domain | Question | Current status |
|--------|----------|----------------|
| Transformation Integrity | Did authorized amendment evidence produce the correct successor state? | Primary focus of current engineering; 10 incorrect accepted mutations remain |
| Lineage Integrity | Can the current commitment be traced through valid authorized transformations? | NOT YET ENFORCED; lineage domain scaffolded but not implemented |
| Propagation Integrity | Do downstream representations match the current authoritative kernel? | NOT YET ENFORCED; no downstream comparison conformance tests |

---

## Conformance test placement

Future conformance tests belong in:

```
tests/conformance/
```

Each invariant family should have a dedicated test module. Tests must
assert the invariant holds against the real runtime, not against a mock.

If the current system does not satisfy an invariant, the test must fail
(or be skipped with a documented reason), not pass vacuously.
