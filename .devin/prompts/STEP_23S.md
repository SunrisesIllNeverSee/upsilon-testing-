# PHASE VI — STEP 23S
# MO§ES™ SEMANTIC SAFETY ENFORCEMENT

## Objective

Implement the minimum runtime MO§ES™ enforcement necessary to eliminate the concrete safety failures exposed by Step 23R.

This is the first runtime implementation step after Step 23G governance and Step 23M semantic-control design.

The current independently adjudicated diagnostic baseline is:

```text
393 parser instructions

86 IN_SCOPE
266 OUT_OF_SCOPE
41 AMBIGUOUS_SCOPE

2 accepted correct
6 IN_SCOPE accepted incorrect
4 OUT_OF_SCOPE accepted incorrect

10 incorrect accepted mutations total
1 false authoritative promotion
```

Step 23S passes only when:

```text
incorrect accepted mutations = 0
false authoritative promotions = 0
```

on the same frozen diagnostic population.

Do NOT optimize broad semantic coverage yet.

Do NOT implement the full Step 24 Conservation-First Resolver.

---

# 1. CONTROLLING ARCHITECTURE

Use the accepted Step 23M documents as controlling implementation contracts.

The semantic direction is:

```text
Evidence
→ Target Identity
→ Authoritative Predecessor Commitment
→ Authorized Transformation
→ Semantic Proof
→ Conservation Validation
→ Execution
→ Lineage
→ Authority
```

Do not continue the legacy effective pattern:

```text
Text → Alias → Field → Value → Mutation → Executor
```

except where those mechanisms serve as subordinate evidence extraction.

---

# 2. PRESERVE THE STEP 23R TRUTH SET

The independently adjudicated Step 23R ledger is the test oracle.

Do NOT:

- regenerate eligibility using current resolver output;
- modify labels to make tests pass;
- use truth labels as production lookup data;
- hardcode diagnostic instruction IDs into runtime behavior.

The diagnostic truth evaluates the runtime.

It must not drive the runtime directly.

---

# 3. IMPLEMENT ONLY THE SAFETY-CRITICAL MO§ES™ BOUNDARY

Step 23S should implement the smallest coherent subset of Step 23M required to block unsupported semantic transformations.

Required safety path:

```text
Amendment Evidence
      ↓
Target Identity Assessment
      ↓
Predecessor Commitment
      ↓
Candidate Authorized Transformation
      ↓
Minimal Semantic Transformation Proof
      ↓
Applicable Conservation Guards
      ↓
Executor
      ↓
Semantic Authority Guard
```

This does not require the complete Step 24 transformation algebra.

It does require explicit interfaces sufficient to enforce the safety invariants below.

---

# 4. TARGET ≠ REFERENCE

Implement the controlling invariant:

```text
REFERENCE TO COMMITMENT != TRANSFORMATION TARGET OF COMMITMENT
```

A provision mentioning:

```text
Revolving Loans
Term Facility
Leverage Ratio
```

is not sufficient evidence that the provision modifies that commitment.

A candidate transformation may proceed only when target evidence establishes that the amendment actually operates on the conserved commitment.

Insufficient target evidence must fail closed as:

```text
UNRESOLVED
VALIDATION_REQUIRED
NO_CANDIDATE
```

as appropriate.

## Critical restriction

Do NOT implement lexical patches such as:

```text
if debt-incurrence words + facility mention:
    reject
```

or equivalent.

The HELD-017 failures must be solved through generalized target-vs-reference semantics and OUT_OF_SCOPE isolation.

---

# 5. OUT_OF_SCOPE ISOLATION

Implement runtime protection ensuring that source provisions not establishing an in-scope commitment transformation cannot mutate frozen commitment state.

Required invariant:

```text
OUT_OF_SCOPE / unsupported semantic evidence
→ cannot produce an executable authoritative transformation
```

Again:

The production runtime does NOT know the Step 23R `OUT_OF_SCOPE` answer label.

It must reach fail-closed behavior from operational semantic evidence.

Use the frozen truth set only to prove the generalized behavior is correct.

---

# 6. PREDECESSOR STATE IS CONTEXT, NOT PROOF

Use the authoritative predecessor commitment as semantic context.

However, do NOT create tautological validation.

Forbidden pattern:

```text
old_value = predecessor[field]
```

followed by:

```text
assert old_value == predecessor[field]
```

and treating that as evidence the amendment was interpreted correctly.

That proves only:

```text
x == x
```

The amendment evidence must independently justify:

```text
target commitment
affected field
transformation type
new semantic value
```

where applicable.

Predecessor state may then constrain and validate that interpretation.

---

# 7. OLD-VALUE CONSISTENCY

Where amendment evidence actually expresses or implies an old-state replacement relationship, enforce:

```text
evidence-supported old value
==
authoritative predecessor value
```

If inconsistent:

```text
FAIL CLOSED
```

Do not manufacture the evidence-supported old value from predecessor state.

If the amendment does not provide enough evidence for an old-value check, mark that conservation check:

```text
NOT_APPLICABLE
```

or equivalent rather than fabricating proof.

---

# 8. MINIMAL SEMANTIC TRANSFORMATION PROOF

Implement the minimum executable subset of the Step 23M `SemanticTransformationProof`.

For every candidate allowed to reach execution, require at minimum:

```text
commitment_id
predecessor_version/state reference

source_document
source_span

target_identity_evidence
transformation_type

affected_fields
proposed successor values

applicable conservation checks
proof_status
```

The proof must exist BEFORE execution.

Possible proof status:

```text
COMPLETE
INCOMPLETE
INVALID
```

Only `COMPLETE` may proceed to execution.

Do not implement every optional Step 23M proof field if it is not required for Step 23S safety.

---

# 9. CONSERVATION GUARDS REQUIRED IN STEP 23S

Implement the safety-critical subset:

## A. Target/reference separation

```text
target established before mutation
```

## B. OUT_OF_SCOPE isolation

```text
unsupported semantic evidence cannot mutate state
```

## C. Old-value consistency

when independently supported by amendment evidence.

## D. No unsupported semantic gain

A candidate cannot acquire commitment semantics unsupported by source evidence.

## E. Transformation completeness sufficient for safe execution

If the engine only understands part of a transformation and applying that subset could misrepresent the amendment:

```text
FAIL CLOSED
```

Do not solve broad multi-field/restatement coverage yet.

---

# 10. SEMANTIC EQUIVALENCE / ALIAS SAFETY

Review the incorrect accepted cases involving alias priority or semantic collapse.

An alias may establish identity only when it represents genuine semantic equivalence.

Do NOT allow related-but-distinct financial concepts to collapse into one of the frozen 13 classes merely because doing so produces a mapping.

When equivalence cannot be demonstrated:

```text
UNSUPPORTED
OUT_OF_SCOPE
AMBIGUOUS
```

as appropriate.

Do not broaden the 13-class ontology.

---

# 11. TRACE THE 10 INCORRECT ACCEPTS

Use the Step 23M root-cause table as the initial case list:

```text
EDGAR-AMERESCO:A1:I5
EDGAR-AMERESCO:A2:I4
STUDY-007:A2:I2
STUDY-016:A2:I1
STUDY-016:A2:I2
HELD-010:A11:I6
HELD-017:A1:I1
HELD-017:A4:I1
HELD-017:A4:I2
HELD-017:A4:I3
```

For each report:

```text
source evidence
predecessor commitment
legacy resolver decision
incorrect candidate
violated MOSES invariant
new guard/proof behavior
post-fix outcome
```

The desired post-fix outcome does NOT have to be a correct automatic mapping.

Safe unresolved/rejection is acceptable.

---

# 12. FALSE AUTHORITATIVE PROMOTION

Trace the exact false authoritative promotion.

Determine whether the existing authority propagation machinery behaved correctly given the bad semantic input.

Then add the minimum semantic authority guard required by Step 23M:

```text
Authority may not be granted unless:

SemanticTransformationProof == COMPLETE
AND
required conservation checks == PASS
AND
execution == successful
AND
no blocking inherited/own unresolved state
```

Do NOT use diagnostic correctness labels at runtime.

## Foundation rule

If the existing authority propagation system behaved correctly given its prior contract, do NOT redesign it.

Add the semantic proof/conservation precondition ahead of promotion.

---

# 13. LINEAGE

Do not implement the full Step 24 lineage architecture.

But if a successful validated transformation produces a successor state during Step 23S, ensure existing lineage behavior remains intact.

Do not grant authority to a successor that cannot be associated with its predecessor and amendment evidence.

Any new lineage representation added here should be the minimum required to support semantic proof/authority safety.

---

# 14. CONFORMANCE PROMOTION RULE

For every MO§ES™ invariant implemented during Step 23S, apply:

```text
ENFORCED(I)
iff

RuntimeGuard(I)
AND
PositiveTest(I)
AND
ViolationTest(I)
```

Update the conformance matrix honestly.

An invariant may move:

```text
NOT YET ENFORCED
→ PARTIALLY ENFORCED
→ ENFORCED
```

only when evidence supports the status.

Do not promote unrelated invariants.

---

# 15. REQUIRED CONFORMANCE TESTS

At minimum add dedicated tests proving:

```text
reference_is_not_target
out_of_scope_instruction_cannot_mutate_state
unsupported_alias_cannot_create_false_identity
wrong_old_value_blocks_when_evidence_supplies_old_value
predecessor_state_alone_does_not_prove_target
incomplete_semantic_proof_cannot_execute
invalid_semantic_proof_cannot_execute
incorrect_semantic_transformation_cannot_be_authoritative
valid_existing_correct_mapping_can_still_execute
```

Every enforced invariant requires:

```text
positive case
+
violation case
```

---

# 16. PRESERVE THE TWO CORRECT ACCEPTS

Current independently correct automatic accepts:

```text
2
```

Try to preserve both.

Required goal:

```text
accepted incorrect = 0
accepted correct >= 2
```

If a necessary generalized safety guard causes one of the two to become unresolved, report it explicitly.

Do NOT weaken a valid safety guard solely to preserve coverage.

But do investigate whether the guard is overbroad.

---

# 17. RE-RUN THE FROZEN DIAGNOSTIC POPULATION

After implementation:

Do NOT change independent eligibility.

Rejoin runtime output to the same Step 23R truth rows.

Produce:

```text
before outcome
after outcome
expected semantics
actual semantics
correctness
proof status
conservation status
authority status
```

for every changed instruction.

---

# 18. SAFETY ACCEPTANCE CRITERIA

Step 23S passes only if:

```text
incorrect accepted mutations = 0
false authoritative promotions = 0
```

and the entire current suite passes.

Also report:

```text
OUT_OF_SCOPE accepted mutations
IN_SCOPE accepted-correct
IN_SCOPE accepted-incorrect
IN_SCOPE unresolved/rejected
```

Do not optimize eligible semantic coverage yet.

---

# 19. UPDATED FAILURE CENSUS

After safety is restored, rerun the first-runtime-failure census against the unchanged independently adjudicated IN_SCOPE population.

This becomes the clean input to Step 24.

Report:

```text
first failure family
count
% of eligible failures
engine implementation gap vs interpretation failure
transformation family involved
```

Do NOT implement those coverage fixes.

---

# 20. STEP 24 TARGET ANALYSIS

Using the clean post-safety census, recommend exactly one Step 24 implementation target.

The Step 23M design strongly suggests likely families such as:

```text
MULTI_FIELD_DECOMPOSITION / RESTATEMENT
TARGET_IDENTIFICATION
TABLE/SCHEDULE
DEFINED_TERM
DELETE/TERMINATION
VALUE_EXTRACTION
```

Do not assume the largest before rerunning.

Rank based on:

```text
affected cases
expected direct recoverability
downstream dependencies
ability to improve correct end-to-end transformations
```

---

# 21. TESTING

Run:

```bash
pytest -q
```

Complete suite.

Report:

```text
passed:
failed:
skipped:
```

No targeted-only acceptance.

---

# 22. FINAL REPORT

## A. Repository

```text
branch:
HEAD:
working tree:
```

## B. Tests

```text
passed:
failed:
skipped:
```

## C. Pre-fix safety

```text
incorrect accepted: 10
false authoritative promotions: 1
```

## D. Implemented MOSES runtime invariants

For each:

```text
runtime guard:
positive test:
violation test:
conformance status:
```

## E. Ten-case transition table

All 10 prior incorrect accepts.

## F. Post-fix safety

```text
incorrect accepted:
false authoritative promotions:
OUT_OF_SCOPE accepted:
```

## G. Correct automation

```text
IN_SCOPE total:
accepted correct:
accepted incorrect:
unresolved/rejected:
eligible correct automation rate:
```

## H. Authority determination

```text
AUTHORITY FOUNDATION DEFECT: YES / NO
```

Explain with evidence.

## I. Updated first-failure census

Exact counts.

## J. Step 24 ranked leverage

Top families.

## K. Verdict

Choose exactly one:

```text
STEP 23S PASS — MOSES semantic safety baseline restored
```

or:

```text
STEP 23S BLOCKED — unsupported semantic transformations can still execute or become authoritative
```

If PASS, provide exactly one:

```text
PHASE VI — STEP 24 TARGET:
<one failure family>
```

Do not implement Step 24.

---

# NON-NEGOTIABLES

- Do not broaden the 13 classes.
- Do not redesign frozen v1.
- Do not use Step 23R labels as production runtime logic.
- Do not hardcode the 10 diagnostic IDs.
- Do not substitute lexical rejection heuristics for target semantics.
- Do not treat predecessor state as proof of target identity.
- Do not use tautological old-value checks.
- Do not optimize coverage yet.
- Do not implement broad restatement/multi-field support yet.
- Do not weaken fail-closed behavior.
- Do not modify authority foundation unless a concrete authority defect is demonstrated.

The goal is:

> **Make every currently accepted semantic transformation defensible under the recovered MO§ES™ runtime contract before expanding automation coverage.**
