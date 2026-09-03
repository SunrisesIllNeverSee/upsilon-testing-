# Step 19B.2 — Track B: Held-Out Confirmatory Validation Status

**Frozen system:** `v1.0-frozen-operational-build`
**Track B status:** PARTIALLY EXECUTED — BLOCKED ON HUMAN GOLD + DEFECT VERIFICATION

---

## 1. Immutable Held-Out Run Record / Hash

The held-out run has been locked as immutable.

| Item | Value |
|------|-------|
| Lock record | `results/step_19b_held_out_run_lock.json` |
| Aggregate hash | `8a06d9325067c3d87ade8cd2b948581088fce9c532d70dac80e9b0120da0c4a4` |
| Artifacts locked | 11 |
| Chain documents locked | 372 |
| Locked at UTC | `2026-09-01` (Step 19B.2) |

### Locked artifacts

| Artifact | SHA-256 (first 16) |
|----------|---------------------|
| results/held_out_study_results.json | `5820b59f34b83b48` |
| data/held_out/manifest.json | `3c39a08bd9a841c6` |
| data/held_out/gold/preregistration.json | `b9ffa23230641407` |
| data/held_out/gold/GOLD_ANNOTATION_PROTOCOL.md | `dbf3c0888556e3b2` |
| data/held_out/gold/HELD-001_gold.json | `5a49b1b093b9bb21` |
| data/held_out/gold/HELD-002_gold.json | `065b985a841bd703` |
| data/held_out/gold/HELD-004_gold.json | `0e6b36d125100549` |
| data/held_out/gold/HELD-005_gold.json | `87d93bdbd69969b1` |
| data/held_out/gold/HELD-008_gold.json | `209c74de928efa3f` |
| results/step_19b_held_out_confirmatory_study.md | `377f17d2f6a6ac28` |
| results/step_19b_mutation_defect_analysis.json | `30a12a4ba14bb14a` |

### Lock invariants

1. Frozen system code (v1.0-frozen-operational-build) is not modified.
2. Held-out predictions are not re-run.
3. No tuning against held-out data.
4. Automated proxy annotations are NOT human gold.
5. Provisional held-out metrics are NOT confirmatory evidence.

---

## 2. Mutation-by-Mutation Provisional Defect Analysis

Full analysis: `results/step_19b_mutation_defect_analysis.json`

### Summary

| Metric | Value |
|--------|-------|
| Total incorrect mutations | 3 |
| Evidence class A (independently demonstrable) | 3 |
| Evidence class B (depends on proxy gold) | 0 |
| Evidence class C (ambiguous until human) | 0 |

### Mutation details

#### Mutation 1: HELD-009 A2 ins 1

| Field | Value |
|-------|-------|
| Chain | HELD-009 |
| Issuer | Kayne Anderson BDC, Inc. (KBDC) |
| CIK | 0001747172 |
| Amendment | A2 |
| Accession | 0001213900-24-001581 |
| Parsed instruction | ADD, Section 1.1 |
| Source excerpt | "amended by amending and restating the following definitions... Applicable Margin means from and after the Fourth Amendment Effective Date..." |
| Semantic mapping | REPLACE_VALUE → `facility.credit_agreement` (value: 0.075) |
| Executor result | REJECTED — target key not in state |
| Target key in state | NO (state is empty — S0 extraction failed) |
| Basis | `facility.credit_agreement` is a PHANTOM KEY: the S0 extractor never produces this key in any chain (development or held-out). The mapper's rule targets a commitment that the system's own extractor cannot create. |
| Evidence class | **A — INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT** |

#### Mutation 2: HELD-012 A10 ins 1

| Field | Value |
|-------|-------|
| Chain | HELD-012 |
| Issuer | HighPeak Energy, Inc. (HPK, HPKEW) |
| CIK | 0001792849 |
| Amendment | A10 |
| Accession | 0001437749-25-024452 |
| Parsed instruction | ADD, Section 1.02 |
| Source excerpt | "Applicable Margin means the rate per annum set forth on the grid when the Utilization Percentage is at its highest level..." |
| Semantic mapping | REPLACE_VALUE → `facility.credit_agreement` (value: 1.0) |
| Executor result | REJECTED — target key not in state |
| Target key in state | NO (state is empty — S0 extraction failed) |
| Basis | `facility.credit_agreement` is a PHANTOM KEY (same as Mutation 1). |
| Evidence class | **A — INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT** |

#### Mutation 3: HELD-016 A9 ins 1

| Field | Value |
|-------|-------|
| Chain | HELD-016 |
| Issuer | BOSTON OMAHA Corp (BOC) |
| CIK | 0001494582 |
| Amendment | A9 |
| Accession | 0001437749-24-004563 |
| Parsed instruction | REPLACE_TEXT, Section 3.01(a) |
| Source excerpt | "WHEREAS, the parties desire to amend the Credit Agreement as set forth in this Amendment..." |
| Semantic mapping | REPLACE_VALUE → `facility.credit_agreement` (value: 2025-08-12) |
| Executor result | REJECTED — target key not in state |
| Target key in state | NO (state is empty — S0 extraction failed) |
| Basis | `facility.credit_agreement` is a PHANTOM KEY (same as Mutations 1-2). |
| Evidence class | **A — INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT** |

### Root cause (all 3 mutations)

All 3 incorrect mutations share one root cause: the semantic mapper's rules target `facility.credit_agreement`, a commitment key that the S0 extractor **never produces** in any chain (development or held-out). The S0 extractor produces keys like `facility.revolving_facility`, `facility.term_loan`, and `financial_covenant.*` — but never `facility.credit_agreement`.

This is a **schema mismatch between the mapper and the extractor**: the mapper's rules were written to target a commitment class that the extractor does not create. On the development set, this did not produce incorrect mutations because:
1. The Step 17B fix guarded the maturity-date rule against RESTATE_SECTION and DELETE instructions
2. The development chains where the rule fired happened to have REPLACE_VALUE/REPLACE_TEXT instructions that the executor could reject

On held-out chains, the rule fires on ADD and REPLACE_TEXT instructions (which pass the instruction_type guard), producing confident mutations targeting the phantom key. The executor rejects them, but they are still counted as incorrect automatic mutations because the mapper produced a confident (non-UNRESOLVED) mapping that was wrong.

### Why this is Class A (independently demonstrable)

The defect is independently demonstrable from the system's own architecture — no gold required:
1. The S0 extractor's output schema is fixed and inspectable
2. `facility.credit_agreement` never appears in the extractor's output across all 50 chains (25 development + 25 held-out)
3. The mapper's rules explicitly target this key (visible in `semantic_mapper.py`)
4. The executor rejects the mutation because the target key does not exist in the state

This is not a proxy-gold disagreement (Class B) or an ambiguity requiring human review (Class C). It is an architectural mismatch between two frozen system components.

---

## 3. Evidence Classification Counts

| Class | Count | Description |
|-------|-------|-------------|
| A — Independently demonstrable | 3 | Phantom key: mapper targets `facility.credit_agreement`, extractor never produces it |
| B — Depends on proxy gold | 0 | No mutation's "incorrect" label depends on automated proxy gold |
| C — Ambiguous until human | 0 | No mutation requires human review to classify |
| **Total** | **3** | |

---

## 4. Human Annotation Package Status

| Item | Status |
|------|--------|
| Preregistered subset | 5 chains (HELD-001, HELD-002, HELD-004, HELD-005, HELD-008) |
| Automated proxy scaffold | Complete (49 proxy records, double-annotated) |
| Human annotation | **PENDING** |
| Annotation protocol document | `data/held_out/gold/GOLD_ANNOTATION_PROTOCOL.md` |
| Preregistration manifest | `data/held_out/gold/preregistration.json` |
| Gold files | 5 files (automated proxy scaffold, status: `pending_human_annotation`) |
| Inter-annotator agreement (automated) | 89.74% (35 agree, 4 disagree, 1 only-A, 9 only-B) |

### What human annotators must do

1. Read each source document (CMP or S0 text file) independently
2. Create structured GoldRecord entries following the schema in `gold_schema.py`
3. Double-annotate the preregistered subset (two independent human annotators)
4. Adjudicate disagreements
5. Lock the final gold dataset
6. Hash the final gold dataset

### What human annotators must NOT see

- Frozen system predictions
- Reconstruction output
- Proxy-gold answers

---

## 5. Gold Scope Classification

Full analysis: `results/step_19b_gold_scope_classification.json`

| Classification | Count | Description |
|----------------|-------|-------------|
| GOLD_ELIGIBLE | 1 | `financial_covenant.leverage_ratio` — produced by both system and gold |
| GOLD_NOT_IN_SCOPE | 6 | Gold produces these but system extractor does not |
| SYSTEM_UNSUPPORTED | 4 | System extractor produces these but gold does not |
| GOLD_PENDING | 1 | `facility.credit_agreement` — phantom key, neither produces it |

### Scoring rule

Only GOLD_ELIGIBLE records (keys produced by BOTH the system extractor AND the gold annotator) can be scored as reconstruction errors. GOLD_NOT_IN_SCOPE and SYSTEM_UNSUPPORTED records represent scope mismatches, not reconstruction errors. GOLD_PENDING records await human review.

### Critical implication

The current gold-system scope overlap is only **1 commitment class** (`financial_covenant.leverage_ratio`). The automated proxy gold annotators target `financial_covenant.*` IDs (collateral_requirement, coverage_ratio, indebtedness_limit, leverage_ratio, liquidity, other, tangible_net_worth), while the system extractor produces `facility.*` and a different set of `financial_covenant.*` keys (fixed_charge_coverage, interest_coverage, leverage_ratio, current_ratio, etc.).

This means most gold records cannot be scored against system output — they are in disjoint commitment classes. Human annotators must align the gold scope with the system's extraction scope before confirmatory scoring can produce meaningful accuracy metrics.

---

## 6. Foundation Defect Decision

### Rule

> WRONG + CONFIDENT + VERIFIED = CONFIRMED FOUNDATION DEFECT
>
> UNKNOWN / UNSUPPORTED / UNRESOLVED = VALID BOUNDED OUTPUT
>
> PROXY-GOLD DISAGREEMENT = NOT YET A CONFIRMED DEFECT

### Decision

**3 mutations are independently confirmed as foundation defects without human gold.**

All 3 incorrect mutations are Class A (independently demonstrable from source text / system architecture):
- The mapper produces confident mutations targeting `facility.credit_agreement`
- The S0 extractor never produces this key in any chain
- The executor rejects the mutations as UNKNOWN_COMMITMENT
- This is an architectural mismatch between the mapper and extractor, not a proxy-gold disagreement

### Confirmed foundation defects

| # | Chain | Mutation | Defect | Verified without gold? |
|---|-------|----------|--------|------------------------|
| 1 | HELD-009 | A2 ins 1 | Phantom key: `facility.credit_agreement` | YES (Class A) |
| 2 | HELD-012 | A10 ins 1 | Phantom key: `facility.credit_agreement` | YES (Class A) |
| 3 | HELD-016 | A9 ins 1 | Phantom key: `facility.credit_agreement` | YES (Class A) |

### What this means

The frozen v1 system has a confirmed foundation defect: the semantic mapper targets a commitment key (`facility.credit_agreement`) that the system's own S0 extractor never produces. This was not detected during development because:
1. The Step 17B fix guarded the maturity-date rule against RESTATE_SECTION and DELETE
2. On development chains, the rule either didn't fire or fired on instructions that were already unresolved
3. The phantom-key mismatch only manifests on held-out chains where the rule fires on ADD/REPLACE_TEXT instructions

### What is NOT a confirmed defect

- S0 extraction failure on held-out chains (72% failure rate) — this is a coverage limitation, not a wrong+confident defect. The system correctly reports 0 commitments extracted (honest failure).
- Low mapping coverage (0.96%) — this is a scope limitation. The system correctly reports UNRESOLVED (honest failure).
- Gold-vs-reconstruction agreement (0 matched commitments) — this is a scope mismatch between proxy gold and system output, not a confirmed defect. Pending human gold.

---

## 7. Confirmatory Scoring Status

**BLOCKED — pending human gold.**

Confirmatory scoring cannot proceed until:
1. Human annotators create verified gold for the preregistered subset
2. Gold scope is aligned with system extraction scope
3. Gold dataset is locked and hashed

### What confirmatory scoring will compute (once unblocked)

- Extraction precision/coverage (against human gold)
- Semantic mapping precision/coverage (against human gold)
- Incorrect automatic mutation rate (against human gold)
- UNRESOLVED rate
- Supported-field agreement
- Whole-commitment agreement
- Exact reconstruction rate
- Lineage integrity
- False authoritative promotion rate
- 95% confidence intervals

### What will NOT be re-run

- The frozen system. The existing held-out predictions (locked in `results/held_out_study_results.json`) will be scored against human gold. The system is not re-run or altered.

---

## 8. Exact Remaining Work Before Confirmatory Scoring

1. **Human gold annotation** (BLOCKED)
   - Primary annotator: create structured gold from source documents for 5 preregistered chains
   - Independent second annotator: double-annotate the same 5 chains
   - Adjudicate disagreements
   - Lock and hash the final gold dataset

2. **Gold scope alignment**
   - Human annotators must ensure gold covers the same commitment classes the system extractor produces
   - Classify each gold record as GOLD_ELIGIBLE / GOLD_NOT_IN_SCOPE / SYSTEM_UNSUPPORTED
   - Only GOLD_ELIGIBLE records will be scored

3. **Confirmatory scoring** (after gold is locked)
   - Score existing frozen held-out predictions against locked human gold
   - Compute all confirmatory metrics with 95% CIs
   - Do NOT re-run or alter v1

4. **Foundation defect decision (final)**
   - The 3 Class A defects are already confirmed without gold
   - Any additional defects identified by human gold will be added to the defect record
   - The held-out study remains an honest evaluation of frozen v1

5. **Step 20: Final Confirmatory Publication**
   - NOT YET — blocked on human gold + confirmatory scoring

---

*End of Track B Status*
