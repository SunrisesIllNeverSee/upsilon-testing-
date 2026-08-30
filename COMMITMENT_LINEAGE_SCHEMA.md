# Commitment Lineage Graph — Formal Schema

## Node classes

### Agreement
Stable legal relationship / agreement identity.

### AgreementVersion
A filed or otherwise authoritative legal document event:
- original
- amendment
- amended and restated
- composite

### Commitment
Stable semantic identity across versions.

Example:
`financial_covenant.total_leverage_ratio`

### CommitmentVersion
One effective state of a commitment.

Key temporal fields:
- `valid_from`
- `valid_to`
- `recorded_at`
- `applicability`

### DownstreamRepresentation
A risk model, covenant tracker, credit memo, policy system, AI-generated summary, or other projection.

---

## Edge classes

- `ORIGINATES_FROM`
- `MODIFIES`
- `SUPERSEDES`
- `WAIVES`
- `REINSTATES`
- `DERIVES_FROM`
- `PROPAGATES_TO`

Every state-changing lineage edge must point to the `authority_version_id` that legally supports it.

---

## Identity rule

A `Commitment` is stable across amendments if the legal obligation remains recognizably the same obligation.

A new `Commitment` is created when the amendment creates a distinct obligation rather than modifying an existing one.

This distinction is human-reviewable and must not be silently inferred when confidence is low.

---

## Temporal authority rule

For agreement A at time T, the authoritative kernel is:

```text
K(A,T) =
all commitment versions
whose valid_from <= T
and (valid_to is null or valid_to > T)
and whose source authority is effective by T
```

Conditional terms additionally require their `applicability` predicate to hold.

---

## Propagation failure

For downstream representation R observed at T:

```text
PF(A,R,T) = Diff( K(A,T), R(T) )
```

A propagation failure exists where:
1. the authoritative commitment state changed;
2. the downstream representation is expected to carry that commitment;
3. the representation does not reflect the applicable state at T;
4. the mismatch cannot be explained by an authorized exception or timing rule.
```

---

## Example query

> Show agreements where the leverage covenant was relaxed in Amendment >= 2 but the risk model was never updated.

Execution path:

```text
Agreement
→ Commitment(total_leverage_ratio)
→ CommitmentVersion(previous)
→ MODIFIES
→ CommitmentVersion(relaxed threshold)
→ authority Amendment >= 2
→ expected downstream RiskModel
→ PropagationCheck(STALE | MISSING | PARTIAL)
```

This is directly executable in PostgreSQL with recursive CTEs and joins. Neo4j is not required for MVP correctness.
