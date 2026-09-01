# Step 19B — Defect / Safety Distinction Record

**Generated:** 2026-09-01T11:49:04.639377+00:00
**Frozen system:** v1.0-frozen-operational-build

---

## Three-Layer Analysis

The 3 incorrect automatic mutations on held-out chains are analyzed
across three distinct system layers.  This distinction is critical
for honest reporting: the system has a confirmed mapper defect, but
the execution safety layer prevented authoritative corruption.

### Layer 1: SEMANTIC MAPPER DEFECT

**Finding: 3 wrong confident mappings produced.**

The semantic mapper produced 3 confident (non-UNRESOLVED) mutations
that were wrong.  All 3 targeted `facility.credit_agreement`, a
phantom key that the S0 extractor never produces in any chain
(development or held-out).

| # | Chain | Amendment | Instruction Type | Target Key | Value |
|---|-------|-----------|------------------|------------|-------|
| 1 | HELD-009 | A2 ins 1 | ADD | `facility.credit_agreement` | 0.075 |
| 2 | HELD-012 | A10 ins 1 | ADD | `facility.credit_agreement` | 1.0 |
| 3 | HELD-016 | A9 ins 1 | REPLACE_TEXT | `facility.credit_agreement` | 2025-08-12 |

**Root cause:** The mapper's `_rule_maturity_date_replacement` and
`_rule_rate_replacement` rules target `facility.credit_agreement`,
a commitment key that the S0 extractor's schema does not include.
The Step 17B fix guarded against RESTATE_SECTION and DELETE
instruction types, but did not guard against ADD or REPLACE_TEXT.
On held-out chains, the rule fires on these unguarded instruction
types, producing confident mutations targeting the phantom key.

**Evidence class:** A — INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT

This defect is confirmed without human gold.  The phantom-key
mismatch is visible in the system's own architecture:
- The S0 extractor's output schema is fixed and inspectable
- `facility.credit_agreement` never appears in any extraction
- The mapper's rules explicitly target this key

### Layer 2: EXECUTION SAFETY

**Finding: All 3 wrong mutations rejected by the executor.**

The executor rejected all 3 mutations as `UNKNOWN_COMMITMENT`
because the target key (`facility.credit_agreement`) did not exist
in the chain's commitment state.  The mutations were NOT applied.

| # | Chain | Executor Result | Mutation Applied? |
|---|-------|-----------------|-------------------|
| 1 | HELD-009 | UNKNOWN_COMMITMENT | NO |
| 2 | HELD-012 | UNKNOWN_COMMITMENT | NO |
| 3 | HELD-016 | UNKNOWN_COMMITMENT | NO |

**Safety mechanism:** The executor's key-existence check prevents
mutations targeting non-existent commitments from being applied.
This is a defense-in-depth layer that catches mapper errors before
they corrupt the state.

### Layer 3: AUTHORITATIVE CORRUPTION

**Finding: 0 observed authoritative corruption from these defects.**

None of the 3 chains with incorrect mutations were promoted to
authoritative status.  The authority-blocking mechanism prevented
any chain with unresolved mutations from being marked authoritative.

| Chain | Chain Authoritative? | Lineage Complete? | Incorrect Mutations |
|-------|----------------------|--------------------|--------------------:|
| HELD-009 | NO | NO | 1 |
| HELD-012 | NO | NO | 1 |
| HELD-016 | NO | NO | 1 |

**All 3 chains remained non-authoritative.** The incorrect
mutations did not corrupt the authoritative state because:
1. The executor rejected them (Layer 2)
2. Rejected mutations are counted as unresolved
3. Unresolved mutations block authoritative promotion

---

## Summary Table

| Layer | Finding | Count | Impact |
|-------|---------|-------|--------|
| Semantic Mapper | Wrong confident mappings produced | 3 | Mapper defect confirmed |
| Execution Safety | Wrong mutations rejected by executor | 3/3 | State not corrupted |
| Authoritative Corruption | Incorrect state promoted as authoritative | 0 | No authoritative corruption |

## Interpretation

The frozen v1 system has a **confirmed semantic mapper defect**:
it produces 3 wrong confident mappings on held-out data, all
targeting a phantom key.  This is a foundation-level defect in the
mapper's schema alignment with the extractor.

However, the **execution safety layer held**: the executor rejected
all 3 wrong mutations, preventing them from being applied to the
commitment state.  The **authority layer also held**: no chain with
incorrect mutations was promoted to authoritative status.

The distinction that belongs in the paper:

> The frozen v1 system produced 3 wrong confident semantic mappings,
> but the executor rejected them all as UNKNOWN_COMMITMENT.  The
> system has a confirmed mapper defect, but NOT silent authoritative-
> state corruption.  The safety layer did its job.

## Aggregate safety metrics (held-out, 25 chains)

| Metric | Value |
|--------|-------|
| False authoritative promotion rate | 0.0000 |
| False authoritative promotion count | 0 |
| Incorrect automatic mutation rate | 1.0000 |
| Incorrect automatic mutation count | 3 |
| Lineage completeness rate | 0.8800 |

## What this means for v1.1

The 3 confirmed mapper defects become post-v1 development:

- Fix the phantom-key mismatch: either align the mapper's target
  keys with the extractor's output schema, or add
  `facility.credit_agreement` to the extractor's scope.
- Extend the instruction_type guard to cover ADD and REPLACE_TEXT
  (not just RESTATE_SECTION and DELETE).
- The held-out study remains an honest evaluation of frozen v1.
- The 25 held-out chains CANNOT be reused as held-out for v1.1
  because they have now been seen.  v1.1 requires a NEW untouched
  held-out corpus.

---

## Status

| Item | Status |
|------|--------|
| Semantic mapper defect | CONFIRMED (3 cases, Class A) |
| Execution safety | HELD (3/3 rejected) |
| Authoritative corruption | NONE (0 promotions) |
| Human gold needed for confirmation? | NO — defect is independently demonstrable |
| Human gold needed for confirmatory accuracy? | YES — blocked |
