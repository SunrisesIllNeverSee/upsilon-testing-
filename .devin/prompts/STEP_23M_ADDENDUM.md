# ADDENDUM TO STEP 23M - ORIGINAL MOSES COMMITMENT ARCHITECTURE AS CONTROLLING ANCHOR

> **Archived addendum.** This is the Step 23M addendum, preserved alongside
> the base prompt at `.devin/prompts/STEP_23M.md`.  Do not modify without
> explicit user authorization.

Use the recovered original Upsilon/MOSES commitment framework as primary historical architectural evidence.

The current conservation-first direction should be treated as a restoration/completion of the intended system, not as an unrelated replacement architecture.

Incorporate the following into the Step 23M design package.

## 1. Formal governing state model

The preferred formulation is:

```text
C_t = C_{t-1} + delta_t_authorized
```

subject to:

```text
delta_t_actual = delta_t_authorized
```

and, for every field outside the authorized transformation:

```text
C_t[f] = C_{t-1}[f]
for all f not in affected(delta_t)
```

Conservation does NOT mean preventing legitimate amendment changes.

It means:

```text
no unauthorized semantic change
no unexplained semantic loss
no unsupported semantic gain
```

## 2. Introduce an explicit AuthorizedTransformationEngine

The design should contain a first-class semantic component equivalent to the original Authorized Change Engine.

Its contract should be conceptually:

```text
(C_{t-1}, E_t, A_t) -> delta_t
```

where:

```text
C_{t-1} = authoritative predecessor commitment
E_t     = amendment evidence
A_t     = authority / lineage context
delta_t = authorized semantic transformation
```

Then:

```text
C_t = Apply(C_{t-1}, delta_t)
```

This component must be distinct from evidence extraction.

It owns transformation interpretation and authorization reasoning, not raw document parsing.

## 3. Make Commitment Lineage Graph first-class

Step 23M must specify a durable lineage model.

Every accepted authoritative transformation should create a lineage edge containing at minimum:

```text
predecessor_commitment_id
successor_commitment_id
amendment_id
authority_source
transformation_type
affected_fields
old_values
new_values
effective_date
source_span
proof_id
validation_status
```

The lineage graph should make the current authoritative kernel traceable to the origin kernel through authorized transformations.

## 4. Clarify the role of the frozen 13 classes

Do NOT broaden the 13-class experimental scope.

However, do NOT treat the 13 classes as the complete semantic content of a commitment.

Treat them as:

```text
experimental canonical commitment families
```

while the Commitment Kernel carries richer legal semantics such as:

```text
party
action
subject
operator
threshold
unit
frequency
exceptions
scope
trigger
effective dates
status
cure/grace semantics where represented
source section/span
parent identity
provenance
```

Transformation richness does not require expanding commitment-family scope.

## 5. Restore the Origin Kernel / Current Kernel distinction

The architecture must explicitly distinguish:

```text
C0 = AUTHORITATIVE ORIGIN KERNEL

C*t = AUTHORITATIVE CURRENT KERNEL

D_t = DOWNSTREAM REPRESENTATION
```

This yields three distinct integrity questions:

```text
Transformation Integrity
Lineage Integrity
Propagation Integrity
```

Do not collapse them.

Current Step 23/24 work is primarily Transformation Integrity.

## 6. Human-validated / independently established kernel principle

The original framework placed a validated starting kernel upstream of amendment application.

Reflect that principle in the design:

The amendment interpreter should begin with an authoritative predecessor object whenever one is available.

It should not rediscover the complete commitment from amendment text at every step.

Amendment evidence should primarily establish:

```text
what changed
what authorized that change
what remained conserved
```

rather than reconstructing the entire commitment identity from scratch.

## 7. Update the target runtime architecture

Use this as the controlling target:

```text
SOURCE AGREEMENT
      |
AUTHORITATIVE ORIGIN KERNEL C0
      |
PERSISTENT COMMITMENT IDENTITIES
      |
AMENDMENT EVIDENCE
      |
AUTHORIZED TRANSFORMATION ENGINE
      |
TRANSFORMATION PROOF
      |
CONSERVATION VALIDATION
      |
LINEAGE EDGE
      |
AUTHORITATIVE SUCCESSOR KERNEL C*
      |
PROPAGATION / DOWNSTREAM COMPARISON
```

This should supersede any design that treats the core runtime as merely:

```text
Text -> Alias -> Field -> Value -> Mutation
```

## 8. Architectural interpretation

In the final Step 23M report explicitly answer:

> Does the forensic evidence indicate that Upsilon abandoned an adequate original MOSES architecture, or that the original architecture itself was insufficient?

Do not answer based on current implementation limitations.

Use:

- the recovered original framework;
- Step 23R evidence;
- representability of predecessor/successor states;
- representability of authorized transformations.

The purpose is to distinguish architectural restoration from genuine MOSES theory/schema extension.

No runtime code changes are authorized by this addendum.
