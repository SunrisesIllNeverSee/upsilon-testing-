# Failure Reclassification

**Step 23M design document — Revised failure census.**

This document reassesses the previously alleged protocol-insufficiency
cases using the three-question test from the Step 23M prompt.  No
runtime code is modified.  No categories are manipulated to improve
projected coverage.

---

## 1. Reclassification framework

For every alleged protocol-insufficiency case, ask:

1. Can `C_{t-1}` be represented?
2. Can the correct `C_t` be represented?
3. Can the semantic difference/transformation between them be
   represented conceptually within the commitment-state model?

If all three are YES, classify:

```
MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP
```

not protocol insufficiency.

Genuine protocol insufficiency requires evidence that the correct
state or transformation cannot be represented by MOSES even in
principle.

### Reclassification categories

```
MOSES_TRUE_PROTOCOL_INSUFFICIENCY
MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP
UPSILON_INTERPRETATION_FAILURE
AMBIGUOUS
```

---

## 2. Original classification (from forensic audit)

The forensic audit (`forensic_qa/001_moses_commitment_theory_audit.md`
Final Output G) classified the 84 non-correct IN_SCOPE instructions
as:

| Classification | Count | % of 84 |
|---|---:|---:|
| Representable but unresolved (interpretation failure) | 17 | 20.2% |
| Representable but misinterpreted (accepted wrong) | 6 | 7.1% |
| Not representable (protocol insufficiency) | 58 | 69.0% |
| Ambiguous | 3 | 3.6% |

The 58 "not representable" cases correspond to the failure families:

| Family | Count |
|---|---:|
| MULTI_FIELD_DECOMPOSITION | 41 |
| DELETE_REQUIRES_MANUAL_REVIEW | 6 |
| TABLE_OR_SCHEDULE_VALUE_EXTRACTION | 6 |
| DEFINED_TERM_RESOLUTION | 5 |
| **Total alleged protocol insufficiency** | **58** |

---

## 3. Reclassification by family

### 3.1 MULTI_FIELD_DECOMPOSITION (41 cases)

**Three-question test:**

1. Can `C_{t-1}` be represented? **YES** — `CommitmentState` has
   `threshold`, `operator`, `unit`, `exceptions`, `scope`, etc.  The
   predecessor state is a multi-field commitment object.
2. Can the correct `C_t` be represented? **YES** — the successor state
   is also a multi-field commitment object with some fields changed.
3. Can the transformation be represented conceptually? **YES** — the
   `MULTI_FIELD_REPLACEMENT` and `IDENTITY_PRESERVING_RESTATEMENT`
   transformation families (see `TRANSFORMATION_ALGEBRA.md`) represent
   exactly this: a delta over multiple fields with identity preserved.

**Reclassification:** All 41 cases are
`MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP`.

The commitment-state model can represent multi-field changes.  The
transformation algebra can represent the delta.  What is missing is
the **implementation**: the `AuthorizedTransformationEngine` that
derives `Δ = semantic_difference(C_prev, C_next_candidate)` from
restated section text.  This is an engine gap, not a protocol
insufficiency.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 41 |
| UPSILON_INTERPRETATION_FAILURE | 0 |
| AMBIGUOUS | 0 |

### 3.2 DELETE / TERMINATION (6 cases)

**Three-question test:**

1. Can `C_{t-1}` be represented? **YES** — the predecessor commitment
   is a `CommitmentState` with `status = ACTIVE`.
2. Can the correct `C_t` be represented? **YES** — the successor state
   is `CommitmentState` with `status = TERMINATED` and `valid_to` set.
3. Can the transformation be represented conceptually? **YES** — the
   `TERMINATE` transformation family (see `TRANSFORMATION_ALGEBRA.md`
   §2.12) represents exactly this: set `status = TERMINATED`,
   set `valid_to`, preserve semantic fields in lineage.

**Reclassification:** All 6 cases are
`MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP`.

The current runtime marks all DELETE operations as UNRESOLVED
(`semantic_resolver_v2.py:492-499`) and the executor rejects
RESTATE_SECTION (`executor.py:174-177`).  This is a safety-preserving
choice, not a protocol limitation.  The `TERMINATE` transformation is
representable; the engine simply does not implement it yet.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 6 |
| UPSILON_INTERPRETATION_FAILURE | 0 |
| AMBIGUOUS | 0 |

### 3.3 TABLE / SCHEDULE (6 cases)

**Three-question test:**

1. Can `C_{t-1}` be represented? **YES** — the predecessor commitment
   has `applicability` (dict) and `scope` (dict) fields that can
   represent schedule references and step schedules.
2. Can the correct `C_t` be represented? **YES** — the successor state
   has the same fields with updated schedule content.
3. Can the transformation be represented conceptually? **YES** — the
   `SCHEDULE_REPLACEMENT` and `TEMPORAL_STEP_CHANGE` transformation
   families (see `TRANSFORMATION_ALGEBRA.md` §2.5, §2.6) represent
   schedule and table changes.

**Reclassification:** All 6 cases are
`MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP`.

The commitment-state model has `applicability` and `scope` dict
fields that can carry schedule data.  The transformation algebra has
dedicated families for schedule replacement.  What is missing is the
implementation: parsing table/schedule structures from amendment text
and mapping them to the `applicability`/`scope` fields.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 6 |
| UPSILON_INTERPRETATION_FAILURE | 0 |
| AMBIGUOUS | 0 |

### 3.4 DEFINED_TERM propagation (5 cases)

**Three-question test:**

1. Can `C_{t-1}` be represented? **YES** — the predecessor commitment
   has `scope`, `exceptions`, and other fields that may reference
   defined terms.
2. Can the correct `C_t` be represented? **YES** — the successor state
   has the same fields with the defined-term expansion applied.
3. Can the transformation be represented conceptually? **YES** — the
   `DEFINED_TERM_PROPAGATION` transformation family (see
   `TRANSFORMATION_ALGEBRA.md` §2.10) represents propagating a
   defined-term change to all referencing commitments.

**Reclassification:** All 5 cases are
`MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP`.

The commitment-state model can represent defined-term-dependent
fields.  The transformation algebra has a dedicated family for
propagation.  What is missing is the implementation: tracking
defined-term dependencies and propagating changes.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 5 |
| UPSILON_INTERPRETATION_FAILURE | 0 |
| AMBIGUOUS | 0 |

### 3.5 TARGET_IDENTIFICATION (16 cases)

These were already classified as `UPSILON_INTERPRETATION_FAILURE` in
the forensic audit.  The three-question test confirms this:

1. Can `C_{t-1}` be represented? **YES**
2. Can `C_t` be represented? **YES**
3. Can the transformation be represented? **YES** (the transformation
   is typically a `SCALAR_REPLACEMENT` or `EXCEPTION_EXPANSION`)

The failure is not that the protocol cannot represent the
transformation — it is that the resolver fails to identify the
correct target commitment from evidence.  This is an interpretation
failure, addressable by the `AuthorizedTransformationEngine` with
predecessor-state bias and agreement-local address maps.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 0 |
| UPSILON_INTERPRETATION_FAILURE | 16 |
| AMBIGUOUS | 0 |

### 3.6 VALUE_EXTRACTION (4 cases)

Already classified as `UPSILON_INTERPRETATION_FAILURE`.  The
three-question test confirms: the protocol can represent the
transformation; the resolver fails to extract the correct value from
text.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 0 |
| UPSILON_INTERPRETATION_FAILURE | 4 |
| AMBIGUOUS | 0 |

### 3.7 Accepted incorrect (6 IN_SCOPE + 4 OUT_OF_SCOPE = 10 cases)

Already classified as `UPSILON_INTERPRETATION_FAILURE` (the 6
IN_SCOPE) and OUT_OF_SCOPE isolation failures (the 4 OUT_OF_SCOPE).
The three-question test confirms: the protocol can represent the
correct state and transformation; the resolver produced a wrong
mutation.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 0 |
| UPSILON_INTERPRETATION_FAILURE | 10 |
| AMBIGUOUS | 0 |

### 3.8 Ambiguous (3 cases)

These remain `AMBIGUOUS`.  The three-question test cannot be
definitively answered because the source text is genuinely ambiguous
about whether a transformation is intended.

**Revised count:**

| Classification | Count |
|---|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | 0 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 0 |
| UPSILON_INTERPRETATION_FAILURE | 0 |
| AMBIGUOUS | 3 |

---

## 4. Revised census summary

### By reclassification category

| Classification | Count | % of 84 non-correct |
|---|---:|---:|
| MOSES_TRUE_PROTOCOL_INSUFFICIENCY | **0** | 0.0% |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | **58** | 69.0% |
| UPSILON_INTERPRETATION_FAILURE | **23** | 27.4% |
| AMBIGUOUS | **3** | 3.6% |
| **Total** | **84** | 100% |

### By failure family (revised)

| Family | Count | Reclassification |
|---|---:|---|
| MULTI_FIELD_DECOMPOSITION | 41 | MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP |
| TARGET_IDENTIFICATION | 16 | UPSILON_INTERPRETATION_FAILURE |
| DELETE_REQUIRES_MANUAL_REVIEW | 6 | MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP |
| TABLE_OR_SCHEDULE_VALUE_EXTRACTION | 6 | MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP |
| DEFINED_TERM_RESOLUTION | 5 | MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP |
| VALUE_EXTRACTION | 4 | UPSILON_INTERPRETATION_FAILURE |
| Accepted incorrect (IN_SCOPE) | 6 | UPSILON_INTERPRETATION_FAILURE |
| Accepted incorrect (OUT_OF_SCOPE) | 4 | UPSILON_INTERPRETATION_FAILURE |
| Ambiguous | 3 | AMBIGUOUS |

### Comparison: original vs. revised

| Classification | Original count | Revised count | Change |
|---|---:|---:|---|
| MOSES_PROTOCOL_INSUFFICIENCY | 58 | 0 | -58 |
| MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP | 0 | 58 | +58 |
| UPSILON_INTERPRETATION_FAILURE | 17 | 23 | +6 |
| Accepted incorrect (IN_SCOPE) | 6 | 6 | 0 (reclassified as interpretation failure) |
| Accepted incorrect (OUT_OF_SCOPE) | 4 | 4 | 0 (reclassified as interpretation failure) |
| AMBIGUOUS | 3 | 3 | 0 |

The 58 cases previously labeled `MOSES_PROTOCOL_INSUFFICIENCY` are
reclassified as `MOSES_EDGAR_ENGINE_IMPLEMENTATION_GAP`.  The
commitment-state model can represent the predecessor state, the
successor state, and the transformation between them.  The gap is in
the engine implementation, not the protocol.

---

## 5. Conceptual diagnosis

**Is current Upsilon predominantly MOSES theory/schema insufficient,
or MOSES EDGAR engine incompletely implemented?**

**Answer: MOSES EDGAR engine incompletely implemented.**

Evidence:

- 0 of 84 non-correct cases are true protocol insufficiency.
- 58 of 84 (69.0%) are engine implementation gaps — the protocol can
  represent the states and transformations, but the engine does not
  implement them.
- 23 of 84 (27.4%) are interpretation failures — the engine has the
  capability but uses it incorrectly (wrong target, wrong value,
  wrong class).
- 3 of 84 (3.6%) are genuinely ambiguous.

The MOSES commitment-state model is sufficient to represent the
EDGAR amendment behaviors observed in the 86-row IN_SCOPE audit.  The
gap is that Upsilon's engine does not use the model as designed.  The
forensic audit's own conclusion supports this:

> "Upsilon is not currently giving MOSES Commitment Theory the
> information and enforcement structure it was designed to use."

This is architectural restoration, not theory extension.

### Scientific precision

The statement `MOSES_TRUE_PROTOCOL_INSUFFICIENCY = 0` applies to
**these 84 observed cases**.  It should not be elevated into a claim
that MOSES has no protocol insufficiencies in general.  The
scientifically precise statement is:

> **No Step 23R non-correct case currently requires a demonstrated
> extension of the MOSES commitment-state or transformation model.**

That leaves the theory falsifiable.  Future corpora may expose a
genuinely unrepresentable legal transformation.  Declaring
theoretical completeness from 84 failures would be unsound.

---

## 6. Expected recovery leverage

Using the independently adjudicated Step 23R diagnostic set,
estimated by transformation family:

| Transformation family | Affected eligible failures | Representable under existing commitment theory? | Current implementation missing? | Downstream dependencies | Maximum directly addressable cases |
|---|---:|---|---|---|---:|
| SCALAR_REPLACEMENT (old-value guard) | 6 | YES | YES (old_value never supplied) | Executor guard exists | 6 |
| OUT_OF_SCOPE isolation | 4 | YES | YES (no scope guard) | Target/reference separation | 4 |
| Authority correctness gate | 1 (false promotion) | YES | YES (completeness-only) | Proof records | 1 |
| TARGET_IDENTIFICATION (predecessor bias) | 16 | YES | YES (predecessor state ignored) | Agreement-local address map | 16 |
| MULTI_FIELD_REPLACEMENT / RESTATEMENT | 41 | YES | YES (RESTATE_SECTION rejected) | AuthorizedTransformationEngine, semantic differencing | 41 |
| TERMINATE | 6 | YES | YES (all DELETE → UNRESOLVED) | TERMINATE transformation family | 6 |
| SCHEDULE_REPLACEMENT | 6 | YES | YES (no schedule parsing) | Table/schedule parser | 6 |
| DEFINED_TERM_PROPAGATION | 5 | YES | YES (no propagation) | Defined-term dependency tracking | 5 |
| **Total potentially addressable** | | | | | **85** |

This is engineering leverage analysis, not a forecast.  Implementing a
transformation family does not guarantee successful end-to-end
mappings — the evidence extraction and target identity layers must
also succeed for each specific case.

---

## 7. References

- `forensic_qa/001_moses_commitment_theory_audit.md` Q9, Q10, Final
  Output D, G, H — failure census, protocol vs. interpretation,
  recoverable failure rate
- `results/step23r_audit.json` — master audit data
- `results/step23r_failure_taxonomy.json` — taxonomy bucket counts
- `TRANSFORMATION_ALGEBRA.md` — transformation families
- `CONSERVATION_INVARIANTS.md` — invariant checks
