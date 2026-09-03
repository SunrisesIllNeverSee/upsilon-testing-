# Upsilon Financial Commitment Integrity v1 — Development Methods & Results

**Track A Publication Package — Step 19B.3 (Review-Ready)**

**Frozen system:** `v1.0-frozen-operational-build`
**Frozen commit:** `9771fe5`
**Frozen at UTC:** `2026-09-01T05:48:44.147775+00:00`
**Document generated:** `2026-09-01` (Step 19B.3)

> **Held-out confirmatory performance remains pending independent human gold verification.**
>
> All metrics in this document are development-set metrics. Held-out metrics are reported only as acquisition/protocol status (Section 13). No held-out reconstruction accuracy is reported as final. Automated proxy annotations are not human gold and are not confirmatory evidence.

---

## 1. Upsilon Architecture

Upsilon is a pipeline system for reconstructing financial commitment state across credit-agreement amendment chains filed on SEC EDGAR. The system ingests original credit agreements (S0) and sequential amendments, parses each amendment's legal instructions, maps them to structured commitment mutations, executes the mutations against the evolving state, and persists the lineage in PostgreSQL.

### Pipeline stages

```
S0 document → S0 Extractor → initial commitment state
                                    ↓
Amendment A1 → Parser → AmendmentInstructions → Semantic Mapper → StructuredMutations
                                    ↓                                              ↓
                              Executor ←──────────────────────────────────────────┘
                                    ↓
                              Persistence (PostgreSQL lineage)
                                    ↓
Amendment A2 → ... (repeat) → final reconstructed state
                                    ↓
CMP document → GT Extractor → ground truth state → comparison
```

### Frozen components (v1.0-frozen-operational-build)

| Component | Module | Role |
|-----------|--------|------|
| Parser v0.4.1 | `amendment_parser.py` | Regex-based extraction of amendment instructions from legal text |
| Semantic Mapper v0.1 | `semantic_mapper.py` | Maps parsed instructions to structured commitment mutations |
| Executor | `executor.py` | Applies mutations to commitment state; rejects invalid targets |
| Persistence | `persistence.py` | PostgreSQL lineage storage with temporal validity intervals |
| S0 Extractor v0.1 | `s0_extractor.py` | Extracts initial commitment state from original credit agreements |
| GT Extractor v0.1 | `gt_extractor.py` | Extracts ground-truth state from composite/conformed documents |
| Shared extraction engine | `commitment_extractor.py` | Section detection, clause extraction, value parsing |
| Semantic pipeline | `semantic_pipeline.py` | Orchestrates parser → mapper → executor per amendment |
| Pattern classifier | `pattern_classifier.py` | Classifies amendment document genre |
| Chain reconstruction | `chain_reconstruction.py` | IssuerChain and AmendmentStep data models |

---

## 2. Preregistration / Research Protocol

### Research question

Can a rule-based system reliably reconstruct financial commitment state across real-world credit-agreement amendment chains filed on SEC EDGAR, while never silently producing a wrong result?

### Preregistered safety claim

The system's primary safety claim is:

> **Wrong + confident = failure.**

The system must never silently apply an incorrect mutation. When it cannot handle an amendment, it must fail safely to one of the following bounded outcomes:

- **PARTIAL** — some commitments reconstructed, others unresolved
- **UNRESOLVED** — parser detected instructions but mapper could not map them
- **UNSUPPORTED_FORMAT** — parser found 0 instructions (format not handled)
- **VALIDATION_REQUIRED** — mapper produced a mutation but executor could not apply it

### Evaluation protocol

1. Acquire 25 real EDGAR issuer chains (S0 + amendments + optional CMP)
2. Run the frozen system once on each chain
3. Measure: extraction, transformation, reconstruction, safety
4. Freeze the system
5. Acquire 25 held-out chains (Step 19B)
6. Run the frozen system once on held-out chains
7. Score against human gold (preregistered subset)

### Primary endpoint (development)

Incorrect automatic mutation rate = 0 (no wrong + confident mutations).

### Primary endpoint (held-out)

Incorrect automatic mutation rate on held-out chains (pending human gold verification).

---

## 3. Parser Development History

### Parser v0.1 → v0.4.1

The parser evolved through four major versions:

- **v0.1**: Basic regex patterns for REPLACE_VALUE, ADD, DELETE instructions
- **v0.2**: Added RESTATE_SECTION and REPLACE_TEXT instruction types
- **v0.3**: Improved section-reference extraction and multi-line instruction detection
- **v0.4**: Added consent/waiver detection and improved definition-amendment parsing
- **v0.4.1 (frozen)**: Bug fixes from Step 17A/17B diagnosis; final frozen version

### Parser instruction types (frozen)

| InstructionType | Description |
|----------------|-------------|
| REPLACE_VALUE | Replace a numeric/string field value |
| REPLACE_TEXT | Replace a text field value |
| ADD | Add a new commitment or section |
| DELETE | Delete a commitment or section |
| RESTATE_SECTION | Restate a section in its entirety |
| UNRESOLVED | Parser could not classify the instruction |

### Parser coverage (development, 25 chains, 80 amendments)

| Metric | Value |
|--------|-------|
| Total parser instructions detected | 91 |
| Amendments with >=1 instruction | 16/25 (64%) |
| Amendments with 0 instructions | 9/25 (36%) |

The 36% of amendments with 0 instructions represent unsupported document formats (redline amendments, composite restatements, consent-only amendments).

---

## 4. Semantic Mapper Development

### Mapper v0.1 (frozen)

The semantic mapper translates parsed instructions into structured mutations targeting commitment-state fields. It uses rule-based mapping with explicit fallback to UNRESOLVED when no rule matches.

### Mapping rules (frozen)

| Rule | Trigger | Target |
|------|---------|--------|
| `_rule_maturity_date_replacement` | "Maturity Date" + date within 80 chars + REPLACE_VALUE/REPLACE_TEXT instruction type | `facility.credit_agreement.deadline` |
| `_rule_rate_replacement` | Rate/percentage pattern + REPLACE_VALUE | `facility.credit_agreement.rate` |
| `_rule_leverage_ratio` | Leverage ratio threshold | `financial_covenant.leverage_ratio` |
| `_rule_coverage_ratio` | Coverage ratio threshold | `financial_covenant.coverage_ratio` |

### Step 17B defect fix

Three silent-corruption defects were diagnosed in Step 17B, all sharing one root cause: the `_rule_maturity_date_replacement` rule fired on RESTATE_SECTION and DELETE instructions whose source text mentioned "Maturity Date" as a cross-reference, not as an amendment to the maturity date. The fix added an instruction_type guard requiring REPLACE_VALUE or REPLACE_TEXT.

**Before fix:** 3 incorrect automatic mutations (development)
**After fix:** 0 incorrect automatic mutations (development)

Regression tests:
- `test_regression_maturity_date_does_not_fire_on_restate_section`
- `test_regression_maturity_date_does_not_fire_on_delete`

### Mapping coverage (development, post-fix)

| Metric | Value |
|--------|-------|
| Total parser instructions | 91 |
| Semantic mapped | 3 |
| Unresolved | 88 |
| Mapping coverage | 3.30% |
| Mapping precision | 100.00% (3/3) |
| Incorrect automatic mutations | 0 |
| Unresolved rate | 96.70% |

The low mapping coverage is by design: the mapper has only 4 rules and intentionally falls back to UNRESOLVED rather than guessing. The 100% precision (0 incorrect) is the safety claim.

---

## 5. S0/GT Extraction Architecture

### S0 Commitment Extractor v0.1

Extracts initial commitment state from original credit agreements (S0 documents). Uses section detection, clause extraction, and value parsing from the shared `commitment_extractor.py` engine.

**Extracted commitment classes:**
- `facility.revolving_facility`
- `facility.term_loan`
- `financial_covenant.leverage_ratio`
- `financial_covenant.fixed_charge_coverage`
- `financial_covenant.interest_coverage`
- `financial_covenant.current_ratio`
- `financial_covenant.tangible_net_worth`
- `financial_covenant.return_on_average_assets`
- `financial_covenant.risk_based_capital_ratio`

### GT Extractor v0.1

Extracts ground-truth state from composite/conformed/restated credit agreements (CMP documents). Uses the same shared extraction engine.

### Extraction metrics (development)

| Metric | Value |
|--------|-------|
| S0 extraction success rate | 72.73% (16/22 chains with S0) |
| GT extraction success rate | 40.00% (2/5 chains with CMP) |
| S0 extraction coverage (avg) | 49.25% |
| GT extraction coverage (avg) | 21.33% |
| Total S0 commitments extracted | 38 |
| Total GT commitments extracted | 8 |

---

## 6. 25-Chain Development Study

### Study design

25 real EDGAR issuer chains acquired with full provenance (accession numbers, URLs, SHA-256 hashes). Each chain contains S0 + >=2 amendments + optional CMP comparison source.

### Development chain inventory

25 chains across diverse issuers (healthcare, energy, financial services, restaurants, technology). Full manifest in `data/chain_study/manifest.json`.

### Development results (frozen v1, post-17B fix)

| Metric | Value | 95% CI |
|--------|-------|--------|
| Total chains | 25 | — |
| Total amendments | 80 | — |
| Total parser instructions | 91 | — |
| Semantic mapped | 3 | — |
| Unresolved | 88 | — |
| Incorrect mutations | 0 | — |
| S0 extraction success | 16/22 = 72.73% | [49.78%, 89.27%] |
| GT extraction success | 2/5 = 40.00% | [5.27%, 85.34%] |
| Mapping coverage | 3/91 = 3.30% | [0.69%, 9.33%] |
| Mapping precision | 3/3 = 100.00% | [29.24%, 100.00%] |
| Incorrect mutation rate | 0/3 = 0.00% | [0.00%, 70.76%] |
| Unresolved rate | 88/91 = 96.70% | [90.67%, 99.31%] |
| Exact reconstruction (GT) | 2/5 = 40.00% | [5.27%, 85.34%] |
| Lineage completeness | 25/25 = 100.00% | [86.28%, 100.00%] |
| False auth promotion | 0/25 = 0.00% | [0.00%, 13.72%] |

### Development failure taxonomy

| Category | Count | Description |
|----------|-------|-------------|
| PARSER_NO_INSTRUCTIONS | 9 | Parser found 0 instructions in amendment documents |
| S0_EXTRACTION_FAILURE | 6 | S0 document exists but extractor returned 0 commitments |
| SYSTEM_INGESTION_PASS | 5 | System ingested the chain without reconstruction failure |
| MULTIPLE_FAILURES | 2 | Multiple failure modes |
| GT_EXTRACTION_FAILURE | 2 | CMP document exists but GT extractor returned 0 commitments |
| SUCCESS | 1 | Full reconstruction with exact agreement |

---

## 7. Frozen v1 Capability Census

### Outcome distribution (25 development chains)

| Outcome | Count | % | Description |
|---------|-------|---|-------------|
| RECONSTRUCTED | 1 | 4.0% | Final state exactly matches ground truth |
| PARTIAL | 2 | 8.0% | Some commitments reconstructed, others unresolved |
| UNRESOLVED | 5 | 20.0% | Parser detected instructions, mapper could not map |
| UNSUPPORTED_FORMAT | 9 | 36.0% | Parser found 0 instructions (format not handled) |
| VALIDATION_REQUIRED | 8 | 32.0% | S0/GT extraction failure requiring human validation |

### Supported outcomes (bounded)

The system produces five bounded outcomes. None of these are failures — they are honest declarations of capability limits. The only failure mode is **wrong + confident** (incorrect automatic mutation), which the development system produces 0 times.

---

## 8. Failure Taxonomy

### Root-cause classification

| Cause | Description |
|-------|-------------|
| S0_DISCOVERY_FAILURE | Wrong document acquired as S0 |
| S0_EXTRACTION_FAILURE | S0 exists but extractor returns 0 commitments |
| GT_DISCOVERY_FAILURE | Wrong document acquired as CMP |
| GT_EXTRACTION_FAILURE | CMP exists but extractor returns 0 commitments |
| PARSER_FAILURE | Parser finds 0 instructions across all amendments |
| SEMANTIC_MAPPING_FAILURE | Parser found instructions but mapper mapped <50% |
| EXECUTION_FAILURE | Executor could not apply mapped instructions |
| LINEAGE_FAILURE | Lineage incomplete |
| STATE_COMPARISON_FAILURE | Reconstructed state does not match ground truth |
| UNSUPPORTED_DOCUMENT_FORMAT | Document format not handled |

### Dominant development failure modes

1. **PARSER_NO_INSTRUCTIONS (36%)** — the parser's regex patterns do not cover all amendment formats
2. **S0_EXTRACTION_FAILURE (24%)** — the extractor's section detection does not generalize to all credit agreement formats
3. **SYSTEM_INGESTION_PASS (20%)** — the system ingests the chain but produces no reconstruction (all instructions unresolved)

---

## 9. PostgreSQL / Lineage / Temporal Validation

### Integrity checks

All 25 development chains pass PostgreSQL integrity validation:

| Check | Result |
|-------|--------|
| Orphan records | 0 across all chains |
| Lineage cycles | 0 across all chains |
| Contradictory active commitments | 0 across all chains |
| Invalid temporal intervals | 0 across all chains |
| All chains pass | YES (25/25) |

### Temporal validity

Each commitment mutation is persisted with a temporal validity interval (`valid_from`, `valid_to`). The executor enforces that only one commitment version is active at any point in time. The integrity check verifies no overlapping active intervals exist.

---

## 10. Development Safety Results

### Foundation safety claim (VERIFIED on development set)

| Safety Metric | Value | Status |
|---------------|-------|--------|
| Incorrect automatic mutations | 0 | PASS |
| Incorrect automatic mutation rate | 0.00% | PASS |
| False authoritative promotions | 0 | PASS |
| False authoritative promotion rate | 0.00% | PASS |
| Lineage defects | 0 | PASS |
| Temporal defects | 0 | PASS |
| Persistence defects | 0 | PASS |
| False equality/PASS | 0 | PASS |

### Safety mechanism

The system's safety mechanism is multi-layered:

1. **Mapper fallback**: When no rule matches, the mapper returns UNRESOLVED (not a guess)
2. **Executor rejection**: When a mutation targets a non-existent commitment, the executor rejects it as UNRESOLVED
3. **Authority blocking**: Any unresolved mutation blocks authoritative promotion for the chain
4. **Lineage integrity**: PostgreSQL enforces temporal validity and prevents orphan/cycle defects

### Step 17B defect resolution

Three silent-corruption defects were found and fixed before the freeze:
- All 3 shared one root cause: `_rule_maturity_date_replacement` firing on non-replacement instruction types
- Fix: instruction_type guard (REPLACE_VALUE or REPLACE_TEXT only)
- After fix: 0 incorrect automatic mutations

---

## 11. Reproducibility / Freeze Infrastructure

### Freeze record

| Field | Value |
|-------|-------|
| Frozen tag | `v1.0-frozen-operational-build` |
| Frozen commit | `9771fe5` |
| Frozen at UTC | `2026-09-01T05:48:44.147775+00:00` |
| Git status at freeze | clean |
| Test suite at freeze | 662 passed, 2 skipped, 0 failed |

### Code SHA-256 hashes (frozen)

| File | SHA-256 |
|------|---------|
| amendment_parser.py | `b61822f6...` |
| commitment_extractor.py | `11112bdb...` |
| executor.py | `adc628a3...` |
| gt_extractor.py | `faf2f123...` |
| models.py | `6338065e...` |
| persistence.py | `7b922a5b...` |
| s0_extractor.py | `9e15ef44...` |
| semantic_mapper.py | `25dfc7e6...` |
| semantic_pipeline.py | `ce00cc11...` |

Full hashes in `results/step_18_freeze/code_hashes.json`.

### Input manifest

- 237 input files hashed
- Data directories: `data/chain_study`, `data/edgar_chains`
- Full file hashes in `results/step_18_freeze/input_manifest.json`

### Reproduction steps

See `results/step_18_freeze/REPRODUCIBILITY.md` for step-by-step reproduction instructions.

---

## 12. Explicit Development Limitations

The following limitations were measured in the final development run and are NOT fixed (by design — the freeze preserves the system as-is):

### Coverage limitations

1. **S0 extraction success rate: 72.73%** — the extractor fails on 27% of credit agreement formats
2. **GT extraction success rate: 40.00%** — the GT extractor fails on 60% of composite/conformed documents
3. **Semantic mapping coverage: 3.30%** — the mapper has only 4 rules and maps 3 of 91 instructions
4. **Unresolved rate: 96.70%** — the vast majority of parsed instructions are unresolved
5. **Chain-level exact reconstruction: 40.00%** — only 2 of 5 GT-measurable chains reconstruct exactly

### Scope limitations

1. **Parser scope**: regex-based parser handles only a subset of amendment formats (64% of amendments yield >=1 instruction)
2. **Mapper scope**: 4 mapping rules cover maturity date, rate, leverage ratio, and coverage ratio only
3. **Extractor scope**: S0/GT extractors target a fixed set of commitment classes; many covenant types are not extracted
4. **Schema mismatch**: the mapper targets `facility.credit_agreement` (a key the S0 extractor never produces), causing executor rejections on held-out data

### Generalization risk

The development set of 25 chains may not represent the broader population of credit agreement formats. The held-out confirmatory study (Step 19B) is designed to measure generalization, but its results are pending human gold verification.

---

## 13. Held-Out Acquisition / Protocol Status ONLY

> **Held-out confirmatory performance remains pending independent human gold verification.**

### Acquisition status

| Item | Status |
|------|--------|
| Held-out chains acquired | 25/25 |
| Development/held-out CIK overlap | 0 |
| Total documents ingested | 186 |
| Total amendments | 158 |
| Chains with CMP document | 3 |
| Chains with >=2 amendments | 25/25 (100%) |
| Document provenance | Complete (accession, URL, SHA-256, byte count) |
| Frozen system run | Complete (single run, no tuning) |

### Protocol status

| Item | Status |
|------|--------|
| Held-out run locked (immutable) | YES (Step 19B.2) |
| Mutation defect analysis | Complete (3 mutations, all Class A) |
| Gold scope classification | Complete (1 GOLD_ELIGIBLE, 6 NOT_IN_SCOPE, 4 SYSTEM_UNSUPPORTED, 1 PENDING) |
| Human gold annotation | PENDING |
| Confirmatory scoring | BLOCKED (pending human gold) |
| Foundation defect decision | 3 Class A defects independently confirmed (see below) |

### What is NOT reported here

- Held-out reconstruction accuracy (pending human gold)
- Held-out extraction precision/coverage against human gold (pending)
- Held-out mapping precision against human gold (pending)
- Any metric derived from automated proxy annotations (not confirmatory)

---

## 14. Publication-Ready Tables

### Table 1: Development Safety Results

| Metric | k | n | Rate | 95% CI |
|--------|---|---|------|--------|
| Incorrect automatic mutations | 0 | 3 | 0.0000 | [0.0000, 0.7076] |
| False authoritative promotion | 0 | 25 | 0.0000 | [0.0000, 0.1372] |
| Lineage completeness | 25 | 25 | 1.0000 | [0.8628, 1.0000] |
| Temporal defects | 0 | 25 | 0.0000 | [0.0000, 0.1372] |

### Table 2: Development Extraction Results

| Metric | k | n | Rate | 95% CI |
|--------|---|---|------|--------|
| S0 extraction success | 16 | 22 | 0.7273 | [0.4978, 0.8927] |
| GT extraction success | 2 | 5 | 0.4000 | [0.0527, 0.8534] |

### Table 3: Development Transformation Results

| Metric | k | n | Rate | 95% CI |
|--------|---|---|------|--------|
| Mapping coverage | 3 | 91 | 0.0330 | [0.0069, 0.0933] |
| Mapping precision | 3 | 3 | 1.0000 | [0.2924, 1.0000] |
| Incorrect mutation rate | 0 | 3 | 0.0000 | [0.0000, 0.7076] |
| Unresolved rate | 88 | 91 | 0.9670 | [0.9067, 0.9931] |

### Table 4: Development Reconstruction Results

| Metric | k | n | Rate | 95% CI |
|--------|---|---|------|--------|
| Exact reconstruction (GT chains) | 2 | 5 | 0.4000 | [0.0527, 0.8534] |
| Lineage completeness | 25 | 25 | 1.0000 | [0.8628, 1.0000] |

### Table 5: Development Failure Taxonomy

| Category | Count | % |
|----------|-------|---|
| PARSER_NO_INSTRUCTIONS | 9 | 36.0% |
| S0_EXTRACTION_FAILURE | 6 | 24.0% |
| SYSTEM_INGESTION_PASS | 5 | 20.0% |
| MULTIPLE_FAILURES | 2 | 8.0% |
| GT_EXTRACTION_FAILURE | 2 | 8.0% |
| SUCCESS | 1 | 4.0% |

---

## 15. Methods Summary

Upsilon is a rule-based pipeline for reconstructing financial commitment state across SEC EDGAR credit-agreement amendment chains. The system was developed on 25 real issuer chains, frozen as v1.0-frozen-operational-build, and evaluated on a held-out set of 25 additional chains (Step 19B).

The system's design principle is **wrong + confident = failure**: it must never silently apply an incorrect mutation. When it cannot handle an amendment, it fails safely to one of five bounded outcomes (PARTIAL, UNRESOLVED, UNSUPPORTED_FORMAT, VALIDATION_REQUIRED, or RECONSTRUCTED).

The development evaluation verified:
- 0 incorrect automatic mutations (100% mapping precision)
- 0 false authoritative promotions
- 0 lineage, temporal, or persistence defects
- 662 tests passing, 0 failing

The system's coverage is intentionally narrow (4 mapping rules, 3.30% mapping coverage) — this is the trade-off for the safety guarantee. The held-out confirmatory study is designed to measure whether this safety guarantee generalizes, but its results are pending human gold verification.

---

## 16. Limitations Section

1. **Small development sample**: 25 chains may not represent the broader population of credit agreement formats.
2. **Narrow mapper scope**: 4 mapping rules cover only maturity date, rate, leverage ratio, and coverage ratio.
3. **Low extraction coverage**: S0 extractor succeeds on 72.73% of development chains; GT extractor on 40.00%.
4. **Schema mismatch**: the mapper targets `facility.credit_agreement`, a key the S0 extractor never produces. This was not detected during development because the mapper's maturity-date rule was guarded by instruction_type after the Step 17B fix, preventing it from firing on the development set. On held-out data, the rule fires on ADD and REPLACE_TEXT instructions (not guarded), producing 3 incorrect mutations targeting the phantom key.
5. **No held-out confirmatory scoring**: held-out reconstruction accuracy is pending human gold verification.
6. **Automated proxy gold is not human gold**: the preregistered gold subset contains an automated proxy scaffold, not verified human gold. All gold-agreement statistics are provisional.
7. **Single evaluation run**: the system was run once on each set (development and held-out). No cross-validation or bootstrap was performed.

---

## 17. Reproducibility Manifest

### Frozen artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Freeze record | `results/step_18_freeze/freeze_record.json` | Locked |
| Code hashes | `results/step_18_freeze/code_hashes.json` | Locked |
| Input manifest | `results/step_18_freeze/input_manifest.json` | Locked |
| Test results | `results/step_18_freeze/test_results.json` | Locked |
| Development report | `results/step_18_freeze/FINAL_DEVELOPMENT_REPORT.md` | Locked |
| Capability statement | `results/step_18_freeze/CAPABILITY_STATEMENT.md` | Locked |
| Reproducibility guide | `results/step_18_freeze/REPRODUCIBILITY.md` | Locked |
| PostgreSQL integrity | `results/step_18_freeze/postgresql_integrity.json` | Locked |
| False auth promotion | `results/step_18_freeze/false_authoritative_promotion.json` | Locked |
| Defect diagnosis | `results/step_18_freeze/defect_diagnosis.json` | Locked |
| v0.1 vs v0.2 comparison | `results/step_18_freeze/v01_vs_v02_comparison.json` | Locked |
| Held-out run lock | `results/step_19b_held_out_run_lock.json` | Locked |

### Held-out run lock (Step 19B.2)

| Item | Value |
|------|-------|
| Aggregate hash | `8a06d9325067c3d87ade8cd2b948581088fce9c532d70dac80e9b0120da0c4a4` |
| Artifacts locked | 11 |
| Chain documents locked | 372 |
| Lock invariants | 5 (no code modification, no re-run, no tuning, proxy ≠ gold, provisional ≠ confirmatory) |

---

## 18. Clear Statement

> **Held-out confirmatory performance remains pending independent human gold verification.**
>
> The development methods and results presented in this document are based solely on evidence that is valid independently of pending human held-out gold. No held-out reconstruction accuracy is reported as final. Automated proxy annotations are not human gold and are not used as confirmatory evidence. The held-out confirmatory study (Step 19B) is partially executed and blocked on human gold annotation and defect verification.

---

## 19. Defect / Safety Distinction (Step 19B.3)

The held-out study identified 3 incorrect automatic mutations. These are analyzed across three distinct system layers. This distinction is critical for honest reporting.

### Three-layer analysis

| Layer | Finding | Count | Impact |
|-------|---------|-------|--------|
| Semantic Mapper | Wrong confident mappings produced | 3 | Mapper defect confirmed (Class A, no gold needed) |
| Execution Safety | Wrong mutations rejected by executor | 3/3 | State not corrupted |
| Authoritative Corruption | Incorrect state promoted as authoritative | 0 | No authoritative corruption |

### The distinction that belongs in the paper

> The frozen v1 system produced 3 wrong confident semantic mappings on held-out data, but the executor rejected them all as UNKNOWN_COMMITMENT. The system has a confirmed semantic mapper defect, but NOT silent authoritative-state corruption. The safety layer did its job.

### Root cause

All 3 mutations target `facility.credit_agreement`, a phantom key the S0 extractor never produces in any chain (development or held-out). The Step 17B fix guarded the maturity-date rule against RESTATE_SECTION and DELETE instruction types, but did not guard against ADD or REPLACE_TEXT. On held-out chains, the rule fires on these unguarded instruction types.

### What this means

- **Confirmed mapper defect**: the mapper's schema is misaligned with the extractor's output schema
- **Execution safety held**: the executor's key-existence check caught all 3 wrong mutations
- **Authority safety held**: no chain with incorrect mutations was promoted to authoritative status
- **No human gold needed for this finding**: the defect is independently demonstrable from the system's architecture

Full analysis: `results/step_19b_defect_safety_record.md`

---

## 20. Review-Readiness Checklist

| Item | Status |
|------|--------|
| Architecture documented | YES (Section 1) |
| Preregistration protocol | YES (Section 2) |
| Parser development history | YES (Section 3) |
| Semantic mapper development | YES (Section 4) |
| S0/GT extraction architecture | YES (Section 5) |
| 25-chain development study | YES (Section 6) |
| Frozen v1 capability census | YES (Section 7) |
| Failure taxonomy | YES (Section 8) |
| PostgreSQL/lineage/temporal validation | YES (Section 9) |
| Development safety results (0 incorrect, 0 false auth) | YES (Section 10) |
| Reproducibility/freeze infrastructure | YES (Section 11) |
| Explicit development limitations | YES (Section 12) |
| Held-out acquisition/protocol status ONLY | YES (Section 13) |
| Publication-ready tables with 95% CIs | YES (Section 14) |
| Methods summary | YES (Section 15) |
| Limitations section | YES (Section 16) |
| Reproducibility manifest | YES (Section 17) |
| Clear pending-gold statement | YES (Section 18) |
| Defect/safety distinction | YES (Section 19) |
| No held-out accuracy reported as final | YES |
| No proxy gold called human gold | YES |
| No provisional metrics as confirmatory | YES |
| Frozen v1 not modified | YES |
| All tests passing (703 passed, 0 failed) | YES |

**Track A publication package: READY FOR REVIEW.**

---

*End of Track A Publication Package*
