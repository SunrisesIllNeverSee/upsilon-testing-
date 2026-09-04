# Step 25B — Locked Metric Definitions

**Version:** 1.0  
**Locked at:** Step 25B reconciliation  
**Source of truth:** This file  
**Purpose:** Prevent Step 26 or future held-out runs from changing denominators without explicitly versioning the metric definition.

---

## Metric vocabulary

These terms are NOT interchangeable. Each has a specific meaning and population.

### `mapped`

A semantic interpretation/mapping was produced. The genre adapter produced a `StructuredMutation` with `is_resolved=True`. This is the population of all candidates that entered an execution/control path.

### `candidate`

A mapped interpretation entered a specific execution/control path (MOSES spine or legacy executor). Every mapped candidate becomes exactly one candidate.

### `accepted`

The relevant semantic/runtime gate approved the candidate for execution. For MOSES spine candidates, this means the spine promoted the candidate. For legacy candidates, this means the executor applied the instruction. **Accepted ≠ mapped.** A mapped candidate may be rejected or routed away without being accepted.

### `applied`

A state mutation was actually executed. This means either:
- The MOSES spine promoted the candidate (spine `promote()` was called), OR
- The legacy executor applied the instruction (appears in `execution_result.applied`)

**Applied ≠ accepted.** An accepted candidate may fail to apply if the executor's guards catch a mismatch.

### `promoted`

The resulting successor state became authoritative. This means the step was marked `is_authoritative=True` by the authority gate. **Promoted ≠ applied.** A step may be authoritative without any mutations being applied (e.g., a no-op step).

### `rejected`

The candidate reached the MOSES control path and failed validation. The spine returned `rejected=True`. The candidate was NOT applied.

### `routed`

The candidate was intentionally sent outside the currently activated MOSES transformation path. The spine returned `routed_away=True` because the transformation family is not `SCALAR_REPLACEMENT`. Routed candidates go to the legacy executor.

### `unresolved`

The attempted processing ended without a resolved state transition. This includes:
- Candidates from the genre adapter with `is_resolved=False`
- Legacy executor instructions in `execution_result.unresolved`
- Spine-rejected candidates (they end without a state transition)

---

## Population invariants

```
TOTAL CANDIDATES = PROMOTED + REJECTED + ROUTED + OTHER_TERMINAL
```

No candidate may:
- disappear
- be double counted
- occupy multiple terminal categories

```
mapped = total candidates
applied ⊆ candidates (actual state mutations)
promoted ⊆ steps (authority decisions, not candidate-level)
```

---

## Chain-level metrics

### `s0_established`

A chain has ≥1 commitment in its `original_state` (extracted from S0).  
**Denominator:** total chains  
**Numerator:** chains with `len(original_state) > 0`

### `instruction_detected`

An amendment step has ≥1 parser instruction detected by the genre adapter.  
**Denominator:** total amendments  
**Numerator:** amendment steps with `parser_instruction_count > 0`

### `lineage_complete`

All amendment steps have `COMPLETE` execution status AND the chain has an origin state (S0 established).  
**Denominator:** total chains  
**Numerator:** chains where all steps have `COMPLETE` status and `len(original_state) > 0`  
**Note:** This is the same definition as Step 19B. The change from 88% to 60% is a real regression caused by spine rejections and routed-away candidates producing `UNRESOLVED` execution status.

### `gt_scorable`

A chain has `ground_truth_state` with ≥1 commitment that can be compared to reconstructed state.  
**Denominator:** total chains  
**Numerator:** chains with `len(ground_truth_state) > 0`  
**Note:** GT availability is NOT a runtime failure. A chain can execute successfully and still be unscorable.

### `exact_reconstruction`

All GT commitments match the reconstructed state exactly on compared fields (`threshold`, `rate`, `party`, `exceptions`, `applicability`, `status`, `unit`).  
**Denominator (GT-scorable):** GT-scorable chains  
**Denominator (overall):** total chains  
**Note:** Overall exact reconstruction = GT exact reconstruction / total chains. These answer different questions and must not be substituted for one another.

---

## Safety metrics

### `incorrect_mutation`

A state mutation that was applied AND disagrees with independent ground truth.  
**Denominator:** actual applied mutations (NOT mapped)  
**Numerator:** applied mutations where the target commitment/field disagrees with GT  
**If applied = 0:** rate is N/A (no denominator)

### `false_authoritative_promotion`

A step marked authoritative AND an incorrect mutation was applied at or before that step in the same chain.  
**Denominator:** total chains  
**Numerator:** chains with ≥1 false authoritative promotion

---

## Precision metrics

### `precision`

```
precision = verified_correct / (verified_correct + verified_incorrect)
```

**Denominator:** independently scorable predictions (mapped candidates that were applied AND have GT)  
**If denominator = 0:** precision is N/A  
**Do NOT infer precision from absence of known errors.**

Reported separately:
- `parser_derived_precision`: precision over parser-derived scorable predictions
- `extraction_derived_precision`: precision over extraction-derived scorable predictions
- `overall_precision`: precision over all scorable predictions

---

## Comparison with Step 19B

If any Step 19B metric cannot be compared like-for-like under the locked current definition, report:

```
NOT DIRECTLY COMPARABLE
```

rather than manufacturing a delta.

Known non-comparable metrics:
- **Mapping precision:** Step 19B measured 0/3 = 0% over parser-derived applied mutations. Current run has 0 applied mutations, so precision is N/A.
- **Incorrect accepted mutation rate:** Step 19B measured 3/3 = 100% over applied mutations. Current run has 0 applied mutations, so the rate is N/A.

---

## Recoverability evidence levels

### `DIRECTLY_OBSERVED`

The row-level evidence establishes that resolving this single failure would allow the case to reach the next measured stage, with no currently known blocker before that stage.

### `BOUNDED_UPPER_LIMIT`

The count is the maximum population exposed to the failure family, but downstream success is unknown.

### `INFERRED`

Recoverability depends on assumptions not directly demonstrated by the current run.

### `UNKNOWN`

The existing evidence cannot support a useful recovery estimate.

Do not rank an `INFERRED` 40-case opportunity above a `DIRECTLY_OBSERVED` 20-case opportunity without explicitly explaining the uncertainty.
