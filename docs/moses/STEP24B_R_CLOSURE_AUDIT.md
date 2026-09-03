# STEP 24B-R — Runtime Activation Closure and Independence Verification

## Phase 0 — Closure Audit

**Audit date:** 2026-09-03
**Audited commit:** `a0e991de08a9b17029647f73022d5ee978eb933e`
**Branch:** `main`

---

## Finding A — spine input is curated

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`semantic_pipeline_v2.py:423` iterates `step.instructions` — manually curated `AmendmentInstruction` objects from `edgar_chains.py`:

```python
for ins in step.instructions:
    if not spine.is_activated(ins):
        spine_routed_away += 1
        continue
    spine_result = spine.process_instruction(ins, ...)
```

`evidence_extractor.py:136-145` copies curated fields directly:

```python
canonical_key_hint = instruction.target_key
target_field = instruction.field
new_value = instruction.new_value
declared_old_value = instruction.old_value
```

`edgar_chains.py:44-48` documents the curation:

> "The commitment-level instructions in this module were manually
> extracted from the real SEC documents by reading the amendment text."

Provenance is `MANUAL_FALLBACK` → `value_provenance = CURATOR_PROVIDED`.

**RUNTIME CONSEQUENCE:**

The spine receives the adjudicated answer (target_key, field, old_value, new_value) as input. The engine's "identity resolution" and "value extraction" are decorative — the correct answer is already supplied. The runtime cannot reconstruct a real amendment without being handed the adjudicated answer.

**REQUIRED FIX:**

The spine must receive parser/source evidence, not curated commitment-level answers. The Ameresco A1/A2 evidence must come from the actual amendment text through the parser path. Curated instructions may remain as test/diagnostic oracles but must not control production interpretation.

---

## Finding B — address-map identity seeded from amendment answers

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`semantic_pipeline_v2.py:320-324`:

```python
section_refs: dict[str, str] = {}
for _step in chain.amendments:
    for _ins in _step.instructions:
        if _ins.target_key and _ins.target_section_ref:
            section_refs.setdefault(_ins.target_key, _ins.target_section_ref)
```

This is passed to `ConservationFirstSpine.__init__()` → `establish_authoritative_kernel()` → `address_map.register()` (`kernel_bridge.py:216-221`).

The engine then "resolves" identity via the address map (`authorized_change.py:325-331`):

```python
return self._identity_resolver.resolve(
    section_ref=evidence.source_section_ref,
    ...
)
```

**RUNTIME CONSEQUENCE:**

Circular identity: amendment says `target_key=leverage_ratio, section=7.10` → address map registers `7.10→leverage_ratio` → engine "resolves" `7.10→leverage_ratio` → claims independent identity. The engine's identity resolution is not independent — it uses the amendment's own target labels to seed the map it later consults.

**REQUIRED FIX:**

Address identity must be established from S0/source authority, not from amendment target labels. The S0 agreement must establish the section→commitment mapping before any amendment is interpreted.

---

## Finding C — value_provenance recorded but not enforced

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`AmendmentEvidence.value_provenance` is set in `evidence_extractor.py:175`:

```python
value_provenance = _determine_value_provenance(instruction.provenance)
```

But the engine (`authorized_change.py`) never checks `value_provenance`. In `_determine_values` (line 464):

```python
if field_name == evidence.target_field:
    new_values[field_name] = evidence.new_value
```

The new value is used directly regardless of whether it is `PARSER_EXTRACTED`, `CURATOR_PROVIDED`, or `UNKNOWN`.

**RUNTIME CONSEQUENCE:**

A curator-provided incorrect new value is authorized without corroboration. The provenance field is metadata, not an operational control.

**REQUIRED FIX:**

`CURATOR_PROVIDED` values must require independent corroboration from source text or deterministic extraction before authorization. `UNKNOWN` values required for execution must fail closed.

---

## Finding D — old-value validation not independently represented

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`authorized_change.py:494-495` — old value is copied FROM predecessor:

```python
if predecessor:
    old_values[field_name] = predecessor.field_value(field_name)
```

`authorized_change.py:286-294` — `AffectedField.old_value` IS the predecessor value:

```python
affected = [
    AffectedField(
        field_name=f,
        old_value=old_values.get(f),  # this is predecessor.field_value(f)
        new_value=new_values.get(f),
        ...
    )
    for f in affected_fields
]
```

`invariants.py:194-195` — conservation validator compares predecessor value against itself:

```python
pred_val = predecessor.field_value(affected.field_name)
if pred_val != affected.old_value:  # predecessor_value != predecessor_value
```

This is tautological: `x == x` always passes.

The engine's `_verify_old_value_consistency` (line 546-553) does compare `evidence.declared_old_value` against `predecessor.field_value(target_field)`, but this check is in the engine, not the conservation validator, and `AffectedField.old_value` does not carry the amendment-declared value.

**RUNTIME CONSEQUENCE:**

The conservation validator's old-value check cannot detect an amendment that declares a wrong old value. The check is `predecessor_value == predecessor_value` — always true. The engine's separate check exists but is a single boolean flag, not independently verifiable by the conservation layer.

**REQUIRED FIX:**

Preserve `amendment_declared_old_value` and `predecessor_actual_value` as distinct values. The conservation validator must compare the amendment-declared old value against the predecessor actual value, not compare the predecessor value against itself.

---

## Finding E — execution advances _current before authority

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`conservation_first_spine.py:357` — `advance()` changes `_current` to successor:

```python
new_version = self.store.advance(
    commitment_id=delta.commitment_id,
    successor=candidate,
    proof_id=proof.proof_id,
    expected_predecessor_version=proof.predecessor_version,
)
```

`conservation_first_spine.py:407` — authority gate evaluated AFTER advance:

```python
authority_decision = self.gate.evaluate(...)
```

`conservation_first_spine.py:420` — rollback if blocked:

```python
if not authority_decision.is_authoritative:
    self.store.rollback(delta.commitment_id, predecessor)
```

`kernel.py:133` — `advance()` sets `_current` to successor:

```python
self._current[commitment_id] = successor
```

**RUNTIME CONSEQUENCE:**

The authoritative-current temporarily becomes the unauthorized successor. If anything reads authoritative-current between `advance()` and `rollback()`, it sees an unauthorized state. The rollback pattern is a recovery mechanism, not a proper authority-gated promotion.

**REQUIRED FIX:**

Separate provisional execution/staging from authority promotion. The candidate should be staged without changing authoritative-current. `AuthorityGate` must be the only mechanism that changes authoritative-current. Blocked candidates must never become authoritative-current.

---

## Finding F — integrated incorrect-mutation measurement ignores spine mutations

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`semantic_pipeline_v2.py:679-701` — `applied_pairs` built only from legacy executor:

```python
for step_idx, step_result in enumerate(steps):
    for ins in step_result.execution_result.applied:
        if ins.target_key:
            applied_keys.add(ins.target_key)
            ...
```

Spine-controlled mutations are filtered out of the legacy executor (`semantic_pipeline_v2.py:477`):

```python
if mut.commitment_id in spine_controlled_ids:
    continue
```

The spine's own applied mutations (tracked in `spine_results`) are not included in `applied_pairs`.

**RUNTIME CONSEQUENCE:**

A wrong spine mutation would be invisible to the incorrect-mutation audit. The safety metric `incorrect_accepted_mutations = 0` does not cover spine-applied transformations. The metric is not execution-path-neutral.

**REQUIRED FIX:**

The incorrect-mutation measurement must include spine-applied transformations. An applied spine delta that disagrees with ground truth must count as an incorrect accepted mutation.

---

## Finding G — proof post-execution lifecycle incomplete

**STATUS: CONFIRMED**

**CODE EVIDENCE:**

`transformation_proof.py:233-246` — `update_post_execution` is defined:

```python
def update_post_execution(
    self,
    proof: SemanticTransformationProof,
    execution_result: ExecutionResultSummary,
    lineage_reference: str,
) -> SemanticTransformationProof:
    proof.execution_result = execution_result
    proof.lineage_reference = lineage_reference
    return proof
```

Grep for `update_post_execution` across `src/`:

```
Found 1 match in transformation_proof.py (definition only)
```

The method is never called. The spine assembles pre-execution proof (`conservation_first_spine.py:322`), executes, creates lineage, evaluates authority, but never calls `update_post_execution`.

**RUNTIME CONSEQUENCE:**

The final proof record lacks the execution result and lineage reference. The proof is incomplete — it has pre-execution justification but no post-execution facts. Authority consumes an incomplete proof.

**REQUIRED FIX:**

Invoke `ProofAssembler.update_post_execution()` after execution + lineage creation, before authority gate evaluation. The authority gate must consume the completed proof.

---

## Finding H — required activation artifact absent

**STATUS: PARTIAL**

**CODE EVIDENCE:**

`results/current/step24b_runtime_activation.json` exists (3205 bytes, dated 2026-09-03).

However, the artifact is missing required fields:
- No source hash
- No parser/evidence provenance
- No predecessor commitment ID / version
- No identity signals / identity provenance
- No amendment-declared old value / predecessor actual old value
- No value provenance
- No conservation results
- No proof ID
- No execution result
- No lineage edge reference
- No authoritative-current before/after

The `acceptance_gates` block contains hand-set `true` values, not values derived from runtime evidence.

**RUNTIME CONSEQUENCE:**

The artifact does not provide reproducible runtime evidence. It cannot independently prove the runtime performed the required behavior.

**REQUIRED FIX:**

Generate the artifact from the actual current runtime, with all required fields populated from runtime results. No hand-entered PASS statuses.

---

## Phase 0 Pass Gate

- [x] All eight findings investigated.
- [x] Production call path inspected.
- [x] No runtime behavior changed yet.
- [x] Every claimed issue supported or refuted with code evidence.
- [x] Existing baseline recorded.

**Findings summary:**

| Finding | Status |
|---|---|
| A — spine input is curated | CONFIRMED |
| B — address-map identity seeded from amendment answers | CONFIRMED |
| C — value_provenance recorded but not enforced | CONFIRMED |
| D — old-value validation not independently represented | CONFIRMED |
| E — execution advances _current before authority | CONFIRMED |
| F — integrated incorrect-mutation measurement ignores spine mutations | CONFIRMED |
| G — proof post-execution lifecycle incomplete | CONFIRMED |
| H — required activation artifact absent | PARTIAL |

**Baseline:**
- Step 24B conformance: 164 passed
- Full suite: 1216 passed, 14 skipped
- All 8 findings confirmed as real gaps requiring fixes.
