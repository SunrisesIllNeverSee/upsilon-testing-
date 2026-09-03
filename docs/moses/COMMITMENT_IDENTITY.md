# Commitment Identity

**Step 23M design document — Component 1: Persistent Commitment
Identity.**

This document specifies the agreement-local commitment identity layer
that MOSES governs.  No runtime code is modified.

---

## 1. Core invariant

```
ID(C_t) = ID(C_{t-1})
```

unless affirmative evidence establishes one of:

```
CREATE
TERMINATE
SPLIT
MERGE
REDEFINE
RENUMBER / READDRESS
```

Once S0 (the source agreement) establishes commitment identity, later
amendments inherit it unless evidence establishes a legitimate
identity-changing transformation.  Identity is not rediscovered from
amendment text at every step.

---

## 2. Current behavior (forensic finding)

The forensic audit (`forensic_qa/001_moses_commitment_theory_audit.md`
Q15) found:

> Upsilon does NOT persist commitment identity across amendments.
> Every amendment independently rediscovers the commitment from
> language/section heuristics.

`resolve_instruction` (`semantic_resolver_v2.py:482-484`) calls
`resolve_commitment_from_text(source_text, section_ref, current_state)`
every time.  There is no cache, no "previously resolved" lookup, no
identity persistence.  `current_state` is used only for key-set
membership validation.

At least **40+ instructions** in the 86-row IN_SCOPE audit refer to
commitments whose identity was already established earlier in the
same chain, yet every one independently re-resolves.

### Section-number heuristics are global, not agreement-local

`_SECTION_MAP` (`commitment_registry.py:330-366`) and
`_SECTION_COMMITMENT_MAP` (`semantic_mapper.py:876-884`) both map
section numbers to commitment classes **globally**.  The same
`Section 7.10 → leverage_ratio` mapping is used for all chains.  There
is no per-issuer or per-agreement section mapping.

This caused at least **3 of the 10 incorrect accepted mutations**:

- `EDGAR-AMERESCO:A1:I5` and `A2:I4`: `Section 7.10 → leverage_ratio`
  overrode the absence of "leverage ratio" in the source text.
- `STUDY-016:A2:I2`: `Section 9.01 → leverage_ratio` overrode the
  textual "current ratio" evidence.

---

## 3. Identity data structure

Commitment identity is a structured object, not a bare string:

```python
class CommitmentIdentity:
    # The stable semantic identifier within an agreement
    commitment_id: str

    # The agreement this identity belongs to
    agreement_identity: str

    # The agreement-local address (section, schedule, annex)
    local_address: AddressBinding

    # How this identity was established
    provenance: IdentityProvenance

    # Confidence in the identity assignment [0.0, 1.0]
    confidence: float

    # The lineage of identity transformations (CREATE, RENUMBER, etc.)
    identity_lineage: list[IdentityEvent]
```

### AddressBinding

```python
class AddressBinding:
    # Section/schedule/annex reference within this agreement
    section_ref: str

    # The agreement version at which this address was established
    established_at_version: str

    # Whether the address has been renumbered and from what
    renumbered_from: str | None
```

### IdentityProvenance

```python
class IdentityProvenance(str, Enum):
    S0_ORIGIN = "s0_origin"           # established at source agreement
    AMENDMENT_CREATE = "amendment_create"
    AMENDMENT_RENUMBER = "amendment_renumber"
    HUMAN_VALIDATED = "human_validated"
```

---

## 4. Agreement-local address map

Identity is resolved via:

```
(agreement_identity, section/address, time) → commitment_identity
```

NOT:

```
Section 7.10 → leverage_ratio globally
```

Each agreement maintains its own address map.  The same section number
can mean different things in different agreements.  Section numbers
are agreement-local addresses, not global semantic identifiers.

### Address map lifecycle

1. **S0 establishment**: When the source agreement is processed, the
   address map is populated from the extracted commitments.  Each
   commitment gets a `commitment_id` and an `AddressBinding`.

2. **Amendment inheritance**: Later amendments look up commitments by
   `commitment_id` first.  Section references are resolved through the
   agreement-local address map, not through a global section map.

3. **Renumbering**: If an amendment renumbers a section, the address
   map is updated with a `renumbered_from` field.  The `commitment_id`
   does NOT change.  Both the old and new addresses resolve to the
   same identity.

4. **Global section mappings**: May remain as weak discovery evidence
   only.  They may supply a candidate identity to the interpretation
   layer, but they may not, by themselves, establish authoritative
   commitment identity (`.devin/rules.md` prohibited action #2).

---

## 5. Identity lineage

Every identity-changing event is recorded:

```python
class IdentityEvent:
    event_type: str  # CREATE, TERMINATE, SPLIT, MERGE, REDEFINE, RENUMBER
    amendment_id: str
    predecessor_id: str | None
    successor_id: str | None
    evidence_span: str
    proof_id: str
    effective_date: datetime
```

The identity lineage makes it possible to trace any current commitment
back to its origin through the chain of identity events.

### Link to Commitment Lineage Graph

The identity lineage is a projection of the Commitment Lineage Graph
(see `COMMITMENT_LINEAGE_SCHEMA.md`).  The lineage graph records
`ORIGINATES_FROM`, `MODIFIES`, `SUPERSEDES`, and other edge classes.
Identity events are the subset of lineage edges that change identity.

---

## 6. Renumbering behavior

When an amendment renumbers a section:

1. The `commitment_id` does NOT change.
2. The `AddressBinding` is updated: `section_ref` becomes the new
   number, `renumbered_from` records the old number.
3. Both old and new addresses resolve to the same `commitment_id`.
4. A `RENUMBER` identity event is recorded.

Renumbering is an `IDENTITY_PRESERVING` transformation.  It does not
create a new commitment.  See `TRANSFORMATION_ALGEBRA.md` for the
`RENUMBER` operator specification.

### Current gap

The current `semantic_mapper._section_to_commitment_id()`
(`semantic_mapper.py:887-902`) uses exact or prefix matching over a
small section map.  Renumbering is not handled.  This is a
`MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP`, not a protocol insufficiency
— the commitment-state model can represent renumbering (the
`commitment_id` is stable; only the address changes).

---

## 7. Identity confidence and provenance

Identity is not always certain.  The `confidence` field records how
confident the system is in the identity assignment.

### Confidence levels

| Level | Meaning | Action |
|-------|---------|--------|
| 1.0 | Human-validated or S0-origin | Proceed normally |
| 0.8–0.99 | Strong evidence (multiple corroborating signals) | Proceed with proof record |
| 0.5–0.79 | Moderate evidence (single signal, no contradiction) | Route to VALIDATION_REQUIRED; do not auto-promote |
| < 0.5 | Weak or contradictory evidence | Route to UNRESOLVED; fail closed |

### Provenance

Identity provenance records how the identity was established.  S0
origin and human-validated identities carry the highest trust.
Amendment-derived identities (CREATE, RENUMBER) carry proof records
that must be validated.

---

## 8. Rules for creation and termination

### CREATE

A new `commitment_id` is assigned when:

- The amendment creates a distinct obligation rather than modifying an
  existing one.
- No predecessor commitment in `current_state` matches the target.
- The source text contains affirmative creation language ("shall
  establish", "hereby creates", "adds a new covenant").

CREATE is an identity-changing transformation.  It produces a new
entry in the identity lineage with `event_type = CREATE` and
`predecessor_id = None`.

### TERMINATE

A `commitment_id` is marked terminated when:

- The amendment explicitly terminates, removes, or extinguishes the
  commitment.
- The source text contains affirmative termination language ("is
  hereby terminated", "shall no longer apply", "deleted in its
  entirety").

TERMINATE is an identity-changing transformation.  The commitment's
`valid_to` is set.  The commitment remains in the lineage graph but
is no longer in the authoritative kernel `K(A,T)` for `T > valid_to`.

### SPLIT / MERGE / REDEFINE

These are identity-changing transformations that require explicit
evidence and human review when confidence is below threshold:

- **SPLIT**: One commitment becomes two or more.  The original
  `commitment_id` is terminated; new IDs are created.
- **MERGE**: Two or more commitments become one.  The original IDs
  are terminated; a new ID is created.
- **REDEFINE**: The commitment's semantic identity changes
  fundamentally (e.g., a leverage ratio is redefined to include
  previously excluded debt).  The `commitment_id` may persist or
  change depending on whether the obligation remains recognizably the
  same.

See `TRANSFORMATION_ALGEBRA.md` for the full operator specifications.

---

## 9. Authoritative predecessor objects (Constraint #2)

The architecture must treat the independently established predecessor
commitment/kernel as a real semantic input.  The amendment interpreter
must not reconstruct identity from amendment text when authoritative
predecessor identity already exists.

However, predecessor state is **context and constraint evidence**.  It
is NOT automatically proof that the amendment targets that commitment.

The resolution flow is:

```
1. Retrieve predecessor commitments from current_state
2. Use amendment evidence to establish target identity
   - Section references resolve through the agreement-local address map
   - Alias/text matches supply evidence, not authority
   - Predecessor state biases resolution toward existing commitments
3. If target identity is established with sufficient confidence:
   - Inherit the predecessor commitment_id (identity persistence)
   - Proceed to transformation interpretation
4. If target identity cannot be established:
   - Fail closed (UNRESOLVED)
   - Do NOT default to a guess
```

Predecessor state biases resolution but does not determine it.  The
amendment must still affirmatively target the commitment.

---

## 10. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q12, Q15 — section
  heuristics audit, identity persistence audit
- `COMMITMENT_LINEAGE_SCHEMA.md` — existing lineage schema
- `docs/architecture/DEPENDENCY_DIRECTION.md` — evidence vs. authority
- `.devin/rules.md` — prohibited action #2 (section numbers as
  semantic authority)
