# STEP 23M EXECUTION CLARIFICATION - SIX CONTROLLING CONSTRAINTS

> **Archived constraints.** These six constraints were supplied as
> controlling additions to the Step 23M prompt.  They govern how the
> design package is produced and what it must contain.  Do not modify
> without explicit user authorization.

Proceed with the full PHASE VI - STEP 23M - MOSES SEMANTIC CONTROL
ARCHITECTURE PACKAGE prompt (archived at `.devin/prompts/STEP_23M.md`)
plus its addendum (`.devin/prompts/STEP_23M_ADDENDUM.md`).

Add these controlling constraints.

## 1. Contracts before migration

Step 23M must define semantic contracts before any Phase-2 source
migration is authorized.

Do NOT turn the next phase into:

```text
move files
-> fix imports
-> green tests
```

The required sequence is:

```text
define semantic ownership/contracts
-> review contracts
-> implement runtime enforcement
-> only then migrate responsibilities into target modules
```

No runtime modules are to be moved during Step 23M.

## 2. Authoritative predecessor objects

The architecture must treat the independently established predecessor
commitment/kernel as a real semantic input.

Do not permit amendment interpretation to reconstruct identity from
amendment text when authoritative predecessor identity already exists.

However:

```text
predecessor state
```

is context and constraint evidence.

It is NOT automatically proof that the amendment targets that
commitment.

## 3. Prohibit tautological old-value validation

Do NOT implement or endorse a design where the resolver simply copies:

```text
old_value = predecessor[field]
```

and then treats an executor check that:

```text
old_value == predecessor[field]
```

as evidence that the semantic interpretation was correct.

That only proves:

```text
x = x
```

It does not prove:

- the amendment targets the commitment;
- the amendment targets the field;
- the extracted transformation is authorized.

Old-value consistency is a conservation check AFTER target/transformation
evidence has been established.

## 4. Evaluation truth must never become production logic

The Step 23R independently adjudicated labels are:

```text
TEST / DIAGNOSTIC ORACLES
```

They must never become production lookup data.

Likewise, future semantic authority must not depend on:

```text
ground_truth_correct = true
```

or any equivalent answer-key information.

Production runtime must establish validity using operational evidence and
MOSES invariants.

## 5. Semantic proof precedes execution

The target architecture must make clear that:

```text
SemanticTransformationProof
```

is not a post-hoc explanation of executor behavior.

It is the precondition that justifies allowing a transformation to
execute.

Conceptually:

```text
Evidence
-> Target Identity
-> Predecessor State
-> Authorized Transformation
-> Semantic Proof
-> Conservation Validation
-> EXECUTION
-> Lineage
-> Authority
```

## 6. Conformance Promotion Rule

Formalize this permanent governance rule:

```text
ENFORCED(I)
iff
RuntimeGuard(I)
AND PositiveTest(I)
AND ViolationTest(I)
```

An invariant may not be marked `ENFORCED` because documentation says it
exists or because ordinary tests happen to pass.

Required before promotion:

1. explicit runtime enforcement;
2. valid-case test;
3. violation/failure-path test proving the guard blocks the prohibited
   behavior.

Include this in the Step 23M conformance design.

---

Proceed with the complete Step 23M prompt after these constraints.

Do not implement runtime code.
