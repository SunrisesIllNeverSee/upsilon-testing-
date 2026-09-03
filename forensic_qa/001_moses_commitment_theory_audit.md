# Forensic Engineering Response: MOSES Commitment Theory in Upsilon

**Date**: 2025-09-02
**Repository**: `feature/semantic-mapper-v0.1` @ `d30e0cc`
**Audit source**: `results/step23r_audit.json` (produced at `90c4f33`, dirty tree)
**Prompt**: Q001 — MOSES Commitment Theory instantiation audit (30 questions)

---

## Q1. Exact Audited Code State

**Audit JSON recorded state** (`results/step23r_audit.json` -> `section_a_repository_state`):
```
branch: feature/semantic-mapper-v0.1
HEAD: 90c4f33
working_tree: dirty
```

**Current repository state** (verified live):
```
branch: feature/semantic-mapper-v0.1
HEAD: d30e0cc (after the Step 23R follow-up commit)
working_tree: clean
```

The audit was **produced at commit `90c4f33`** with a dirty working tree (the uncommitted changes that became `d30e0cc`). The 393 instructions, 86 IN_SCOPE, 10 incorrect accepted, and 1 false authoritative promotion all came from this same code state — they are all computed by `build_step23r_audit.py:run_audit()` in a single pass that runs the actual resolver and executor.

**Post-v2 fixes present**: Yes. Steps 21, 22, 23, and 23R are all present in the git log above `90c4f33`. The semantic resolver (`semantic_resolver_v2.py`) and mapper (`semantic_mapper.py`) include Step 22E evidence-derived aliases and the maturity-date instruction-type guard.

**Fields loaded from frozen artifacts rather than recomputed**:

| Field | Source | File |
|---|---|---|
| `unknown_genre_rate` | `results/step_21_v2_study_results.json` | `build_step23r_audit.py:1907-1909` |
| `v1_correct_mapped` (aggregate) | `results/chain_study_v1_results.json` | `build_step23r_audit.py:1510-1513` |
| `v2_dev_parser_mapped` (aggregate) | `results/step_21_v2_study_results.json` | `build_step23r_audit.py:1517-1520` |

Everything else (eligibility, expected truth, resolver output, executor output, safety metrics, failure trace, taxonomy) is **recomputed from runtime** by the audit script.

---

## Q2. Complete 86-Row IN_SCOPE Diagnostic Ledger

The full 86-row ledger is in `results/step23r_instruction_ledger.csv` and `results/step23r_audit.json` (`instruction_ledger` array). Key distributions:

**Per-chain IN_SCOPE counts** (20 chains have IN_SCOPE instructions):

| Chain | IN_SCOPE | Correct | Incorrect | Failed |
|---|---:|---:|---:|---:|
| EDGAR-AMERESCO | 3 | 0 | 2 | 1 |
| HELD-003 | 3 | 1 | 0 | 2 |
| HELD-009 | 3 | 0 | 0 | 3 |
| HELD-010 | 8 | 1 | 1 | 6 |
| HELD-011 | 6 | 0 | 0 | 6 |
| HELD-012 | 2 | 0 | 0 | 2 |
| HELD-013 | 1 | 0 | 0 | 1 |
| HELD-014 | 3 | 0 | 0 | 3 |
| HELD-015 | 6 | 0 | 0 | 6 |
| HELD-016 | 14 | 0 | 0 | 14 |
| HELD-018 | 2 | 0 | 0 | 2 |
| HELD-022 | 14 | 0 | 0 | 14 |
| HELD-024 | 3 | 0 | 0 | 3 |
| HELD-025 | 1 | 0 | 0 | 1 |
| STUDY-007 | 8 | 0 | 1 | 7 |
| STUDY-014 | 1 | 0 | 0 | 1 |
| STUDY-016 | 2 | 0 | 2 | 0 |
| STUDY-017 | 1 | 0 | 0 | 1 |
| STUDY-020 | 2 | 0 | 0 | 2 |
| STUDY-022 | 3 | 0 | 0 | 3 |
| **Total** | **86** | **2** | **6** | **78** |

**Predecessor authoritative commitment state**: The audit advances state correctly through `join_v2_output_and_trace` (`build_step23r_audit.py:811-902`). Each amendment sees the state produced by the prior amendment's executor run. The predecessor state is the `current_state` dict passed to `resolve_instruction` and `execute_amendment`.

**Full ledger columns** (available in CSV): `instruction_id, chain_id, document_id, amendment_order, instruction_index, genre, instruction_type, target_ref, source_span_start, source_span_end, source_text, independent_eligibility, eligibility_reason, expected_commitment_class, expected_field, expected_operation, expected_old_value, expected_new_value, expected_unit, expected_section, automatic_mapping_attempted, predicted_commitment_class, predicted_field, predicted_operation, predicted_old_value, predicted_new_value, predicted_unit, candidate_created, accepted, executor_accepted, correct_automatic_mapping, first_runtime_stage_entered, first_runtime_failure, terminal_outcome, failure_family, protocol_vs_interpretation, failure_reason`

---

## Q3. The 10 Incorrect Accepted Mutations — Root Causes

### 6 IN_SCOPE Accepted-Incorrect

| ID | Mismatch | Root Cause |
|---|---|---|
| **EDGAR-AMERESCO:A1:I5** | VALUE: exp=4.00 pred=3.5; OP: exp=REPLACE pred=REPLACE_TEXT | **Wrong value extraction.** Source text is about SOFR successor rate amendments, not the leverage ratio threshold. The resolver matched "leverage ratio" via section heuristic (Section 7.10 -> leverage_ratio) and extracted 3.5 from nearby text — but 3.5 is the *current* ratio, not the *new* 4.00. The parser span captured the wrong paragraph. |
| **EDGAR-AMERESCO:A2:I4** | VALUE: exp=3.75 pred=3.5; OP: exp=REPLACE pred=REPLACE_TEXT | **Wrong value extraction.** Same pattern as A1:I5. Section 7.10 heuristic identified leverage_ratio, but the parser span captured "Revolving Loan" capacity text, not the leverage ratio amendment. 3.5 was extracted from the wrong paragraph. |
| **STUDY-007:A2:I2** | VALUE: exp=7.00 pred=10000000.0 | **Wrong value extraction from wrong paragraph.** Source text mentions "$10,000,000" (Capital Lease Obligations) and "$55,000,000" — neither is the leverage ratio threshold of 7.00. The resolver extracted 10,000,000 from the wrong clause. The actual 7.00 ratio appears elsewhere in the amendment. |
| **STUDY-016:A2:I1** | VALUE: exp=2.75 pred=15.0 | **Wrong value extraction.** Source text is about definitions (Section 1.02), not the leverage ratio threshold. The resolver extracted 15.0 from an unrelated number in the definitions section. The expected 2.75 is in a different part of the amendment. |
| **STUDY-016:A2:I2** | CLASS: exp=current_ratio pred=leverage_ratio; VALUE: exp=2.75 pred=15.0 | **Wrong class + wrong value.** Source text mentions "current ratio" but the resolver's alias matching found "leverage ratio" first (priority ordering) or the section heuristic (Section 9.01 -> leverage_ratio in `_SECTION_MAP`) overrode the textual evidence. The 15.0 value is from the wrong paragraph. |
| **HELD-010:A11:I6** | CLASS: exp=leverage_ratio pred=revolving_facility; VALUE: exp=2.50 pred=20000000.0; UNIT: exp=ratio pred=usd | **Wrong class + wrong value + wrong unit.** Source text says "Consolidated Leverage Ratio is equal to or less than 2.50 to 1.00" but the resolver matched "Revolving Credit Exposures" first (the `Revolving\s+(?:Loan|Facility|Credit|Commitment)` alias has priority 10, while `Leverage\s+Ratio` has priority 50). The resolver extracted $20,000,000 from the revolving credit exposure context. |

### 4 OUT_OF_SCOPE Accepted (Unauthorized Mutations)

| ID | Root Cause |
|---|---|
| **HELD-017:A1:I1** | **Debt incurrence provision mistaken for facility amendment.** Source text discusses "Indebtedness incurred...IDHC Acquisition" but contains "Revolving Loans" in the exception text. The `Revolving\s+(?:Loan|Facility|Credit|Commitment)` alias matched, resolving to `facility.revolving_facility`. The `_rule_exception_add_remove` mapper rule found "Notwithstanding" and produced an ADD to `exceptions`. The resolver's `resolve_commitment_from_text` validated that `facility.revolving_facility` exists in `current_state` and accepted it. |
| **HELD-017:A4:I1** | **Same mechanism.** "Ellie Mae Acquisition" financing provision contains "Revolving Loans" -> matched `facility.revolving_facility` -> exception ADD. |
| **HELD-017:A4:I2** | **Same mechanism.** |
| **HELD-017:A4:I3** | **Same mechanism.** |

**Common root cause for all 10**: The resolver identifies commitment class purely from **text pattern matching** (`resolve_commitment_from_text` at `commitment_registry.py:374-417`). It does NOT verify that the instruction is actually *amending* that commitment. It does NOT check whether the source text's use of "Revolving Loans" is in an amendment context vs. a debt incurrence/carve-out context. The only validation is that the canonical_id exists in `current_state` (`commitment_registry.py:407`).

**Which validator should have caught it**: The executor's `old_value` guard (`executor.py:119-122`) could have caught the 6 IN_SCOPE wrong-value cases IF the resolver had supplied `old_value` from the predecessor state. But `_extract_values` (`semantic_resolver_v2.py:650-745`) never reads `current_commitment` (dead parameter) and never supplies `old_value`. The executor's `hasattr` guard (`executor.py:114-115`) only checks field existence, not semantic appropriateness.

**Was predecessor state available?**: Yes — `current_commitment` is retrieved at `semantic_resolver_v2.py:512` and passed to `_extract_values` and `_validate_candidate`. But `_extract_values` never reads it (dead parameter, confirmed by subagent). `_validate_candidate` only reads `getattr(current_commitment, candidate.field, None)` at line 828 — it checks that the field exists, not that the value matches.

**Error classification**:
- 4/10: **Target identity failure** (OUT_OF_SCOPE mistaken for IN_SCOPE — wrong commitment entirely)
- 3/10: **Value extraction failure** (right class, wrong value from wrong paragraph)
- 2/10: **Class + value failure** (wrong class due to alias priority, wrong value)
- 1/10: **Class + value + unit failure** (alias priority picked revolving over leverage)

---

## Q4. The One False Authoritative Promotion — Complete Trace

**Chain**: HELD-017 (Intercontinental Exchange)

**Amendment A1**: Source document is an amendment adding acquisition financing provisions for the IDHC Acquisition.

**Complete path**:
1. **Source document**: HELD-017 A1 amendment document
2. **Parser instruction**: `HELD-017:A1:I1`, type=ADD, target_ref="Article III", source_text contains "Indebtedness incurred...IDHC Acquisition...Revolving Loans"
3. **Semantic resolution**: `resolve_instruction` (`semantic_resolver_v2.py:458`) calls `resolve_commitment_from_text` (`commitment_registry.py:374`). The `Revolving\s+(?:Loan|Facility|Credit|Commitment)` alias (priority 10) matches "Revolving Loans" in source_text. `facility.revolving_facility` is in `current_state` -> returns `(facility.revolving_facility, "threshold", 0.95)`.
4. **Field identification**: `_identify_field` (`semantic_resolver_v2.py:295`) identifies field="exceptions" (the `_rule_exception_add_remove` mapper rule found "Notwithstanding" language).
5. **Value extraction**: `_extract_values` extracts the "Notwithstanding..." sentence as the exception text.
6. **Candidate construction**: `StructuredMutation(commitment_id=facility.revolving_facility, field=exceptions, operation=ADD, new_value="Notwithstanding...")` — confidence 0.85.
7. **Validation**: `_validate_candidate` (`semantic_resolver_v2.py:788`) checks `hasattr(current_commitment, "exceptions")` -> True. No old_value check (ADD operation). **Passes.**
8. **Execution**: `execute_amendment` (`executor.py:182`) -> `apply_instruction` -> ADD with EXCEPTION_EXPANSION domain_effect -> `c.exceptions.append(ins.new_value)` (`executor.py:137-141`). **Applied successfully.**
9. **Unresolved accounting**: 0 unresolved mutations, 0 executor rejections.
10. **Authority determination**: `is_authoritative = (status==COMPLETE) and (not inherited_unresolved) and (own_unresolved==0)` -> **True** (`semantic_pipeline_v2.py:247-251`).
11. **Final authoritative promotion**: Step A1 is marked authoritative.

**The invariant that should have prevented promotion**: A step should not be authoritative if it applied an incorrect/unauthorized mutation. The current authority logic (`semantic_pipeline_v2.py:247-251`) only checks *structural* completeness (no unresolved, no inherited). It does NOT check *semantic* correctness. The `incorrect_mutations` detection (`semantic_pipeline_v2.py:369-431`) only runs **after the entire chain completes** by comparing final state to ground truth — it is not available at authority-determination time.

**The exact reason it did not**: Authority is determined *during* the pipeline loop (line 247), but incorrect-mutation detection requires *ground truth comparison* which only happens *after* the loop (line 307). There is no runtime invariant that checks "is this mutation semantically correct?" before promoting to authoritative.

---

## Q5. Where Is the Conserved Commitment Object?

**Yes, it is `CommitmentState`** (`models.py:97-123`).

**Fields that participate in semantic resolution** (actually read by resolver/executor):
- `threshold` — read by resolver (`semantic_resolver_v2.py:665-704`), written by executor (`executor.py:93-130`)
- `rate` — read by resolver (`semantic_resolver_v2.py:706-707`), written by executor
- `deadline` — read by resolver (`semantic_resolver_v2.py:709-710`), written by executor
- `exceptions` — read by resolver (`semantic_resolver_v2.py:712-722`), written by executor (`executor.py:137-141, 157-163`)
- `party` — read by resolver (`semantic_resolver_v2.py:724-728`), written by executor (`executor.py:138-146, 157-168`)
- `status` — read/written by executor only (`executor.py:62-91, 170-172`)
- `valid_from`, `valid_to` — written by executor WAIVE only (`executor.py:84-85`)
- `applicability` — written by executor WAIVE only (`executor.py:86-90`)
- `canonical_key` — used as state dict key (`executor.py:48-51`)

**Dormant fields** (defined but never read/written by resolver/executor at runtime):
- `commitment_type`, `modality`, `action`, `subject`, `operator`, `unit`, `frequency`, `scope`, `trigger`, `grace_period`, `cure`, `application_order`

**Copied forward unchanged**: All fields are conserved automatically because `execute_amendment` deep-copies the entire state (`executor.py:186`) and `apply_instruction` mutates in-place. Only `ADD`/`ADD_COMMITMENT` with a dict payload constructs a new `CommitmentState` (`executor.py:48`) where missing fields get defaults.

**Can silently disappear**: Only on `ADD` with dict payload — if the payload omits a field, it gets the model default (e.g. `None`, `[]`, `{}`). For `REPLACE_VALUE`/`REPLACE_TEXT`, only the targeted field changes; all others are preserved.

---

## Q6. Does Upsilon Perform Conservation-First Transformation?

**No.** The engine behaves like `amendment text -> rediscover commitment -> construct mutation`, not `C_t = T_t(C_{t-1})`.

**Evidence from code**:

1. `resolve_instruction` (`semantic_resolver_v2.py:458-557`) Step 1 calls `resolve_commitment_from_text(source_text, section_ref, current_state)` — it **rediscovers the commitment identity from text** every time. It does NOT start from "which commitment in `current_state` is this amendment most likely modifying?"

2. `resolve_commitment_from_text` (`commitment_registry.py:374-417`) iterates alias patterns against `source_text`. `current_state` is only used to **validate** that a matched canonical_id exists — it is not used to *bias* resolution toward existing commitments.

3. `_extract_values` (`semantic_resolver_v2.py:650-745`) receives `current_commitment` as a parameter but **never reads it** (dead parameter, confirmed by subagent). Values are extracted purely from `source_text` regex.

4. `_validate_candidate` (`semantic_resolver_v2.py:788`) receives `current_state` but **never reads it** (dead parameter). It only reads `getattr(current_commitment, candidate.field, None)` to check field existence.

**Points where predecessor `CommitmentState` is available but not used**:
- `semantic_resolver_v2.py:512` — `current_commitment` retrieved but only checked for `None`
- `semantic_resolver_v2.py:556` — `current_commitment` passed to `_extract_values` but never read
- `semantic_resolver_v2.py:788` — `current_state` passed to `_validate_candidate` but never read
- `commitment_registry.py:407` — `current_state` used only for key-set membership, not field values

---

## Q7. Information Available at Resolver Entry

| Information | Available? | Classification |
|---|---|---|
| Chain identity | Yes (`chain.chain_id`) | **IGNORED** — resolver receives only `parser_instruction` |
| Amendment order | Yes (`step.amendment_order`) | **IGNORED** — not passed to resolver |
| Source agreement | Yes (`step.description`) | **PARTIALLY USED** — passed as `citation_document`, used for citation only |
| Target section | Yes (`parser_instruction.target_section_ref`) | **USED** — `semantic_resolver_v2.py:478` |
| Parser operation | Yes (`parser_instruction.instruction_type`) | **USED** — `semantic_resolver_v2.py:479` |
| Parser target_key | Always `None` from parser | **IGNORED** — parser never sets it |
| Parser field | Not produced by parser | **N/A** |
| Parser old_value | Yes (`parser_instruction.old_value`) | **IGNORED** — resolver re-extracts from text |
| Parser new_value | Yes (`parser_instruction.new_value`) | **IGNORED** — resolver re-extracts from text |
| Predecessor state | Yes (`current_state` dict) | **PARTIALLY USED** — key-set membership only; field values not read |
| Commitment registry | Yes (imported aliases) | **USED** — for text pattern matching |
| Prior section identity | Not tracked | **NOT IMPLEMENTED** |
| Authority state | Not passed to resolver | **IGNORED** |
| Amendment genre | Yes (`step.pattern`) | **IGNORED** by resolver — only used by pipeline for adapter routing |
| Effective dates | Yes (`parser_instruction.effective_start`) | **PARTIALLY USED** — `semantic_resolver_v2.py:602` for WAIVE only |
| Previously resolved commitments | Not tracked | **NOT IMPLEMENTED** |

---

## Q8. Where Does the Engine Throw Away Known Answers?

| Upstream evidence | Produced by | Discarded at | Impact |
|---|---|---|---|
| `parser.old_value` | `amendment_parser.py:559` (regex capture) | `semantic_resolver_v2.py:556` — resolver re-extracts from text | 6/86 IN_SCOPE wrong-value failures could potentially be caught if old_value was checked against predecessor state |
| `parser.new_value` | `amendment_parser.py:559` | `semantic_resolver_v2.py:556` — resolver re-extracts | Wrong-value extractions (3/6 accepted_incorrect) |
| Predecessor field values | `current_state[canonical_id].threshold` etc. | `semantic_resolver_v2.py:650` — `_extract_values` never reads `current_commitment` | All 6 accepted_incorrect could be caught by old_value==current_state check |
| Known commitment identity | `current_state` keys | `commitment_registry.py:407` — only validates existence, doesn't bias resolution | 4/10 incorrect accepted (OUT_OF_SCOPE) could be prevented if resolver preferred existing commitments over text-pattern matches |
| Section-to-commitment identity from prior amendments | Not tracked | N/A | Unknown — identity persistence not implemented |

**Quantification**: Of the 84 IN_SCOPE non-correct instructions:
- **15 had sufficient evidence** (expected value or class keyword in source text) that was not consumed by the resolver
- **6 had sufficient evidence used incorrectly** (accepted with wrong value/class)
- **33 had insufficient source evidence** (expected value is SOURCE_AMBIGUOUS)
- **58 classified as protocol insufficiency** (RESTATE_SECTION/DELETE/TABLE — protocol cannot express)

---

## Q9. Recoverable Semantic Failure Classification (84 IN_SCOPE non-correct)

| Category | Count | % |
|---|---:|---:|
| Insufficient source evidence (expected value unknown) | 33 | 39.3% |
| Sufficient evidence existed but engine did not use it | 15 | 17.9% |
| Sufficient evidence used incorrectly (accepted wrong) | 6 | 7.1% |
| Interpretation correct but validation/execution failed | 0 | 0.0% |
| Protocol representation insufficient | 58 | 69.0% |
| **Note**: Categories overlap (protocol insufficiency cases also have insufficient evidence) | | |

**Non-overlapping breakdown**:
- Protocol insufficiency (RESTATE_SECTION/DELETE/TABLE): 58 (69.0%)
- Interpretation failure with sufficient evidence: 21 (25.0%)
- Insufficient evidence only: 5 (6.0%)

---

## Q10. Protocol Insufficiency vs Implementation Failure

| Classification | Count | % of 84 |
|---|---:|---:|
| **Representable but unresolved** (protocol can express, interpretation failed at TARGET_IDENTIFICATION or VALUE_EXTRACTION) | 17 | 20.2% |
| **Representable but misinterpreted** (protocol can express, accepted with wrong value/class) | 6 | 7.1% |
| **Not representable** (RESTATE_SECTION multi-field, DELETE, TABLE/SCHEDULE, DEFINED_TERM) | 58 | 69.0% |
| Ambiguous | 3 | 3.6% |

The 17 "representable but unresolved" are the **directly recoverable** failures — the protocol has the fields and operations, but the resolver fails to identify the target or extract the value.

The 6 "representable but misinterpreted" are the **safety failures** — the resolver produced a confident but wrong mutation that the executor accepted.

---

## Q11. Audit of the 13 Frozen Commitment Classes

The 13 classes are **commitment identities** (canonical keys), not the entirety of the semantic protocol. But they are being used as if they were the entirety.

**Can multiple legally distinct commitments collapse into one class?** Yes:
- `financial_covenant.leverage_ratio` collapses: Total Funded Debt to EBITDA, Consolidated Leverage Ratio, Total Leverage Ratio, Net Leverage Ratio, First Lien Leverage Ratio, Secured Leverage Ratio, Core Leverage Ratio, Senior Funded Debt to EBITDA, Funded Debt to EBITDA, Debt to EBITDAX, Maximum Total Leverage Ratio, Maximum Leverage Ratio, Long Term Debt to Long Term Capitalization (13 distinct legal concepts -> 1 class)
- `financial_covenant.debt_service_coverage` collapses: Debt Service Coverage, Debt Service Coverage Ratio, **Asset Coverage Ratio** (a BDC concept semantically different from DSCR)
- `financial_covenant.current_ratio` collapses: Current Ratio, **Minimum Working Capital** (working capital is a dollar amount, not a ratio)
- `financial_covenant.interest_coverage` collapses: Interest Coverage, EBIT to Interest Ratio, Interest Coverage Ratio, **Minimum Liquidity** (liquidity is not interest coverage)
- `financial_covenant.tangible_net_worth` collapses: Tangible Net Worth, Minimum Tangible Net Worth, Minimum Shareholders Equity, Minimum Stockholders Equity

**Aliases asserting semantic equivalence rather than spelling equivalence**:
- `Asset Coverage Ratio` -> `debt_service_coverage` (`commitment_registry.py:307-309`) — **semantically wrong**: asset coverage is a BDC-specific concept, not DSCR
- `Minimum Working Capital` -> `current_ratio` (`commitment_registry.py:312-314`) — **semantically wrong**: working capital is a dollar amount, current ratio is a ratio
- `Minimum Liquidity` -> `interest_coverage` (`commitment_registry.py:316-318`) — **semantically wrong**: liquidity is not interest coverage

---

## Q12. Section-Number Heuristics Audit

`_SECTION_MAP` (`commitment_registry.py:330-366`) and `_SECTION_COMMITMENT_MAP` (`semantic_mapper.py:876-884`) both map section numbers to commitment classes.

**Issuer/agreement-specific or global?**: **Globally applied.** The same `section 7.10 -> leverage_ratio` mapping is used for all chains. There is no per-issuer or per-agreement section mapping.

**Can override contradictory textual/state evidence?**: Yes. `resolve_commitment_from_text` (`commitment_registry.py:374-417`) tries alias patterns first (text-based), then falls back to section-only resolution. But the mapper's `_section_to_commitment_id` (`semantic_mapper.py:887-902`) uses section-only. If an alias matches the wrong commitment (e.g. "Revolving Loans" in a debt incurrence section), the section heuristic is not consulted. If no alias matches, the section heuristic alone determines the class — even if the section number is wrong for that particular agreement.

**Incorrect accepted mutations caused by section heuristics**:
- **EDGAR-AMERESCO:A1:I5 and A2:I4**: target_ref="Section 7.10" -> `_SECTION_MAP` maps to `leverage_ratio`. Source text does NOT contain "leverage ratio" but the section heuristic resolved the class anyway. The resolver then extracted 3.5 from the wrong paragraph. **2/10 incorrect accepted directly caused by section heuristic.**
- **STUDY-016:A2:I2**: target_ref="Section 9.01" -> `_SECTION_MAP` maps `section\s+9\.1\b` to `leverage_ratio`. But the expected class is `current_ratio`. The section heuristic overrode the textual "current ratio" evidence. **1/10 incorrect accepted influenced by section heuristic.**

**Is the engine confusing document navigation with semantic identity?** Yes. Section numbers are document navigation evidence, not semantic identity. The same section number can mean different things in different agreements. The engine treats `Section 7.10` as a global synonym for `leverage_ratio` across all 50 chains.

---

## Q13. Parser-to-Semantic Boundary Integrity

The parser (`amendment_parser.py:479-562`) produces: `instruction_type`, `target_section_ref`, `target_key` (always `None`), `source_start`, `source_end`, `source_text`, `old_value`, `new_value`.

**Internal inconsistency defects** (observed in the 86 IN_SCOPE):
- **Wrong paragraph paired with correct section**: EDGAR-AMERESCO A1:I5 and A2:I4 have target_ref="Section 7.10" but source_text is about SOFR successor rates and revolving loan capacity — not the leverage ratio amendment. The parser span captured the wrong paragraph. **2/86 cases.**
- **Span crosses into subsequent provisions**: STUDY-007 A2:I2 source_text contains "$10,000,000" (Capital Lease Obligations) and "$55,000,000" (Section 2.1(a) amendment) — the span crossed from the leverage ratio section into the facility amount section. **1/86 cases.**
- **Operation labeled incorrectly**: STUDY-007 A2:I3 is labeled DELETE but the source text says "amended and restated in its entirety to read as follows" — this is a REPLACE, not a DELETE. **1/86 cases.**
- **target_key always None**: All 393 instructions have `target_key=None`. The parser never identifies the target commitment. **393/393 cases.**

**Quantification**: At least 4/86 (4.7%) IN_SCOPE instructions have parser-level defects that contribute to downstream resolution failures. The `target_key=None` gap affects 100% of instructions.

---

## Q14. State Advancement Audit

The audit (`build_step23r_audit.py:811-902`) advances state correctly:
- Starts from `chain.original_state` (deep copy)
- After each amendment, executes mapped instructions through `execute_amendment`
- Replaces `current_state` with `exec_result.state` (deep copy)
- Next amendment sees the updated state

The production pipeline (`semantic_pipeline_v2.py:152-279`) does the same.

**No path resolves against original or stale state** in either the audit or the production pipeline. Both advance state correctly.

**How many failures change with proper predecessor state?** This is not directly measurable from the current audit because the resolver does not use predecessor field values. However, 6/10 incorrect accepted mutations could be caught if the resolver checked `old_value == current_state[canonical_id].field` before accepting — this requires predecessor state to be *used*, not just *available*.

---

## Q15. Identity Persistence Audit

**No.** Upsilon does NOT persist commitment identity across amendments. Every amendment independently rediscovers the commitment from language/section heuristics.

**Evidence**: `resolve_instruction` (`semantic_resolver_v2.py:482-484`) calls `resolve_commitment_from_text(source_text, section_ref, current_state)` every time. There is no cache, no "previously resolved" lookup, no identity persistence. `current_state` is used only for key-set membership validation.

**Quantification**: Of the 86 IN_SCOPE instructions, those in chains with multiple amendments referencing the same commitment (e.g. HELD-016 has 14 IN_SCOPE across 7 amendments, many referencing `financial_covenant.fixed_charge_coverage` or `facility.term_loan`) — every one independently re-resolves the commitment identity from text. At least **40+ instructions** refer to commitments whose identity was already established earlier in the same chain.

---

## Q16. Old-Value Conservation Audit

**Does the engine use current state to identify the affected field?** No. `_identify_field` (`semantic_resolver_v2.py:295-339`) uses `source_text` and `canonical_id` only — not `current_commitment`.

**Does it require X to be extracted from amendment text?** No. `_extract_values` (`semantic_resolver_v2.py:650-745`) extracts `new_value` from text but does NOT extract `old_value` from text. `old_value` is left as `None` for most operations.

**Does it verify X equals current authoritative state?** Only if `ins.old_value` is provided. The executor checks at `executor.py:119-122`:
```python
if ins.old_value is not None and old != ins.old_value:
    raise UnresolvedInstruction(...)
```
But `ins.old_value` is almost always `None` because the resolver never sets it. So the guard never fires.

**What happens if multiple fields contain X?** The resolver identifies a single field via `_identify_field`. If it picks the wrong field, the executor applies the mutation to that wrong field. No ambiguity detection.

**Failures caused by not exploiting this invariant**: All 6 IN_SCOPE accepted_incorrect could be caught if the resolver supplied `old_value` from `current_state[canonical_id].threshold` and the executor verified it matched. The executor guard exists but is never activated.

---

## Q17. Unchanged-Field Preservation Audit

**Does the executor produce `new_state = prior_state + explicit_delta`?** Yes, for `REPLACE_VALUE`/`REPLACE_TEXT`/`DELETE`/`WAIVE`/`SUSPEND`/`REINSTATE`. The executor deep-copies the entire state (`executor.py:186`) and mutates only the targeted field in-place. All other fields are conserved.

**Exception**: `ADD`/`ADD_COMMITMENT` with a dict payload constructs a **new** `CommitmentState` (`executor.py:48`) where missing fields get model defaults. This is correct for new commitments but would be wrong if used for an existing commitment modification.

**Proof**: `test_chain_reconstruction.py:test_q1_state_preservation_all_chains` (line 237) verifies that unchanged fields are preserved across all 5 synthetic chains. `test_edgar_chains.py:test_ameresco_leverage_ratio_threshold_preserved` (line 269) verifies threshold preservation for a specific EDGAR chain.

**Verdict**: Unchanged-field preservation is **EXPLICITLY ENFORCED** for in-place operations. It is correct by construction (deep copy + targeted mutation).

---

## Q18. Temporal Semantics Audit

The executor supports:
- **Temporary covenant relief**: `WAIVE_TEMPORARILY` sets `status="WAIVED"`, `valid_from`, `valid_to`, `applicability["waiver"]` (`executor.py:77-91`)
- **Step-down schedules**: `_rule_leverage_ratio_step_down` (`semantic_mapper.py:419-474`) produces a REPLACE_VALUE on `applicability` with a step-down schedule dict
- **Effective periods**: `WAIVE_TEMPORARILY` uses `effective_start`/`effective_end`
- **Waivers**: `SUSPEND`/`REINSTATE` change `status`
- **Exceptions**: ADD/DELETE on `exceptions` list
- **Reinstatement**: `REINSTATE` sets `status="ACTIVE"`
- **Maturity changes**: `_rule_maturity_date_replacement` produces REPLACE_VALUE on `deadline`
- **Amendments effective after conditions precedent**: NOT IMPLEMENTED — no concept of conditional effectiveness

**Is scalar `threshold` replacement used where temporal state transition is needed?** Yes. HELD-022 has step-down schedules (A6:I9, A7:I8) where the expected operation is a table-based step-down (5.75 -> 5.50 -> 5.00 -> 4.50), but the resolver produces a single REPLACE_VALUE. The `applicability` field exists for step-downs but the resolver identifies `threshold` instead. **At least 3/86 IN_SCOPE** (HELD-022 A6:I9, A7:I7, A7:I8) are step-down schedules incorrectly treated as scalar threshold replacements.

---

## Q19. Multi-Field and Restatement Semantics Audit

**Does Upsilon compare predecessor state with replacement section to derive a delta?** No. The executor raises `UnresolvedInstruction` for all `RESTATE_SECTION` operations (`executor.py:174-177`). The resolver never performs predecessor-vs-successor differencing.

**Does it attempt to classify the replacement paragraph directly?** Yes. The resolver treats each RESTATE_SECTION instruction as a standalone text classification problem — it tries to identify the commitment class from the replacement text and extract the new value. It does NOT compare against the predecessor state.

**How many unresolved IN_SCOPE are full/multi-field restatements?** 41/78 failed (52.6%) are `MULTI_FIELD_DECOMPOSITION` — RESTATE_SECTION instructions that group multiple definition amendments into one instruction. The protocol handles one field at a time and cannot decompose multi-field restatements.

**How many could be recovered through predecessor-versus-successor semantic differencing?** Potentially all 41 MULTI_FIELD_DECOMPOSITION cases — if the engine compared the restated section text against the current state and derived the delta. This is the single largest recoverable failure family, but it requires a new protocol capability (section differencing), not just interpretation improvement.

---

## Q20. The 4 OUT_OF_SCOPE Accepted Mutations

All 4 are in HELD-017 (Intercontinental Exchange) and involve acquisition financing provisions (IDHC Acquisition, Ellie Mae Acquisition).

**Why each was mistaken for a frozen commitment**:
- All 4 source texts contain "Revolving Loans" in the exception/carve-out language
- The `Revolving\s+(?:Loan|Facility|Credit|Commitment)` alias (`commitment_registry.py`, priority 10) matched "Revolving Loans"
- This resolved to `facility.revolving_facility`, which exists in `current_state`
- The `_rule_exception_add_remove` mapper rule (`semantic_mapper.py:697-782`) found "Notwithstanding" language and produced an ADD to `exceptions`

**Which mechanism caused it**: **Registry alias matching** — the alias `Revolving\s+(?:Loan|Facility|Credit|Commitment)` matches any mention of "Revolving Loans" regardless of context. There is no check for whether the mention is in an amendment context vs. a debt incurrence/carve-out context.

**Why scope controls did not block it**:
1. The resolver has no scope control — it does not check whether the instruction is actually amending the commitment
2. The executor has no scope control — it only checks structural validity (field exists, old_value matches)
3. The authority determination has no scope control — it only checks completeness

**Are debt-incurrence restrictions being confused with financial covenant obligations?** Yes. The 4 OUT_OF_SCOPE provisions are debt incurrence carve-outs (conditions under which the borrower can incur indebtedness for acquisitions). They mention "Revolving Loans" because the acquisition is financed through revolving loans — but they are NOT amendments to the revolving facility commitment. The engine cannot distinguish "amending the revolving facility" from "mentioning revolving loans in an acquisition financing provision."

---

## Q21. MOSES Governance Enforcement Map

| Governance mechanism | Runtime location | Enforcement level |
|---|---|---|
| **Commitment conservation** | `executor.py:186` (deep copy + in-place mutation) | **EXPLICITLY ENFORCED** for in-place ops; **NOT ENFORCED** for ADD with dict payload |
| **Lineage custody** | `semantic_pipeline_v2.py:262-277` (per-step results) | **PARTIAL** — per-step results recorded but no lineage invariant checked |
| **Provenance** | `InstructionProvenance.PARSER` / `.SEMANTIC_MAPPER` | **IMPLICIT** — provenance tag set but never checked at runtime |
| **Collapse/loss detection** | None | **NOT IMPLEMENTED** — no detection of commitment identity collapse or field loss |
| **Execution gating** | `executor.py:114-115` (hasattr check), `executor.py:119-122` (old_value guard) | **PARTIAL** — structural only, no semantic gating |
| **Authority gating** | `semantic_pipeline_v2.py:247-251` | **PARTIAL** — checks completeness only, not correctness |
| **Unresolved-state propagation** | `semantic_pipeline_v2.py:254-260` | **EXPLICITLY ENFORCED** — inherited_unresolved blocks authority |

---

## Q22. Commitment-Theory Enforcement

| Invariant | Enforcement | Test coverage |
|---|---|---|
| **Conservation** (unchanged fields preserved) | **EXPLICITLY ENFORCED** by deep copy + in-place mutation | 5 tests (`test_executor.py`, `test_edgar_chains.py`, `test_chain_reconstruction.py`) |
| **Transformation** (C_t = T_t(C_{t-1})) | **NOT ENFORCED** — resolver does not use predecessor field values | 0 tests |
| **Identity** (commitment identity persists across amendments) | **NOT ENFORCED** — every amendment re-resolves identity from text | 0 tests |
| **Field preservation** (non-targeted fields unchanged) | **EXPLICITLY ENFORCED** by in-place mutation | 5 tests |
| **Authority** (no promotion when incorrect mutation applied) | **PARTIALLY ENFORCED** — blocks on unresolved, NOT on incorrect | 5 tests for unresolved blocking, 0 tests for incorrect-mutation blocking |

---

## Q23. Where MOSES Is Merely Assumed

| Claimed principle | Expected enforcement | Actual implementation | Test coverage | Gap |
|---|---|---|---|---|
| "Commitment conservation" | Predecessor fields preserved + old_value verified | Deep copy preserves fields; old_value never supplied | 5 tests for preservation, 0 for old_value verification | old_value guard exists but is never activated |
| "Lineage custody" | Per-amendment lineage tracked and verified | Per-step results recorded; no invariant checked | 2 tests for lineage completeness | No lineage invariant enforcement |
| "Authority gating" | No promotion when incorrect mutation applied | Only blocks on unresolved, not on incorrect | 5 tests for unresolved blocking | Incorrect mutations can be promoted |
| "Commitment identity persistence" | Identity established once, reused unless explicitly changed | Every amendment re-resolves from text | 0 tests | No identity persistence mechanism |
| "Predecessor-state matching" | Resolver uses current_state to validate and guide resolution | current_state available but field values never read | 0 tests | Dead parameters in _extract_values and _validate_candidate |
| "Semantic delta construction" | new_state = prior_state + explicit_delta | Resolver constructs mutations from text alone, not from prior state | 0 tests | No delta construction from predecessor state |
| "OUT_OF_SCOPE isolation" | No mutation produced for out-of-scope instructions | No scope check in resolver or executor | 0 tests | 4 OUT_OF_SCOPE mutations accepted |

---

## Q24. Test Quality for MOSES Invariants

**919 passing tests.** How many actually verify MOSES invariants?

| Invariant | Tests | Files |
|---|---|---|
| Commitment identity preservation across amendments | **0** | None |
| Predecessor-state conservation (unchanged fields) | 5 | `test_executor.py`, `test_edgar_chains.py`, `test_chain_reconstruction.py` |
| Correct amendment delta | **0** | None — no test verifies that the delta matches expected |
| Unchanged-field preservation | 5 | Same as conservation |
| Rejection of contradictory transformations | 3 | `test_executor.py:test_old_value_guard_blocks_bad_application`, `test_operational_preflight.py` |
| OUT_OF_SCOPE isolation | **0** | None — only classification tests, no "no mutation produced" test |
| Authority safety (no promotion when incorrect) | 5 | `test_false_authoritative_promotion.py` — but only tests unresolved blocking, not incorrect-mutation blocking |
| Temporal state transitions | 7 | `test_executor.py`, `test_operational_preflight.py`, `test_chain_reconstruction.py` |
| Chain-level conservation across multiple amendments | 9 | `test_chain_reconstruction.py` |

**Major invariants with NO tests**:
- Commitment identity preservation (0 tests)
- Correct amendment delta (0 tests)
- OUT_OF_SCOPE isolation (0 tests)
- Authority safety against incorrect mutations (0 tests — only unresolved blocking tested)
- Predecessor-state matching (0 tests)

---

## Q25. The 2 Correct Mappings

| ID | Why it succeeded |
|---|---|
| **HELD-003:A1:I3** | Source text contains "fixed charge coverage" with a clear "$20,000,000" value. The `Fixed\s+Charge\s+Coverage` alias matched cleanly. The value extraction regex found "$20,000,000". The predecessor state had `financial_covenant.fixed_charge_coverage` with a threshold field. The executor applied REPLACE_VALUE to threshold. All components aligned. |
| **HELD-010:A11:I2** | Source text contains "revolving credit" with a clear "$240,000,000" value. The `Revolving\s+(?:Loan|Facility|Credit|Commitment)` alias matched. The value extraction found "$240,000,000". The predecessor state had `facility.revolving_facility` with a threshold field. The executor applied REPLACE_VALUE to threshold. All components aligned. |

**What made them different from the other 84**: Both had (1) a clear, unambiguous covenant keyword in the source text, (2) a clear dollar amount extractable by regex, (3) the correct commitment already in predecessor state, and (4) no competing alias matches. The 84 failures either had ambiguous text, wrong paragraph spans, multi-field restatements, or competing alias matches.

**Is the success mechanism generalizable?** Partially. The mechanism works when: (a) the source text unambiguously names the covenant, (b) the value is a simple dollar amount or ratio in the same paragraph, (c) the commitment exists in predecessor state. It fails when any of these conditions are not met — which is the majority of real EDGAR amendments.

---

## Q26. The 6 Wrong IN_SCOPE Accepted Mappings

Compared to the 2 correct:

| Discriminating factor | 2 Correct | 6 Incorrect |
|---|---|---|
| Source text contains expected covenant keyword | Yes, unambiguously | 2/6 do not contain the keyword at all (section heuristic used); 1/6 contains "current ratio" but "leverage ratio" alias matched first |
| Value in same paragraph as covenant keyword | Yes | 4/6 value is from a different paragraph (parser span crossed clauses) |
| Competing alias matches | No | 2/6 had competing aliases (revolving matched before leverage) |
| Section heuristic used | No (text was sufficient) | 2/6 relied on section heuristic because text didn't contain keyword |
| Old_value verified against predecessor | No (but not needed — value was correct) | No — old_value guard never activated because resolver doesn't supply it |

**The key discriminator**: The 2 correct mappings had **unambiguous text + correct paragraph + no competing matches**. The 6 incorrect had at least one of: wrong paragraph, competing alias, section heuristic override, or missing keyword. The resolver has no mechanism to detect these failure modes.

---

## Q27. Semantic Precision of the Current Engine

| Metric | Value |
|---|---|
| Correct IN_SCOPE accepted / all IN_SCOPE accepted | 2/8 = 25.0% |
| Correct accepted / all accepted | 2/12 = 16.7% |
| Incorrect IN_SCOPE accepted | 6 |
| Unauthorized OUT_OF_SCOPE accepted | 4 |
| False authoritative promotions | 1 |
| Total accepted | 12 |
| Total correct | 2 |
| Total incorrect/unauthorized | 10 |

**Semantic precision = 2/12 = 16.7%**. The engine is wrong 83.3% of the time when it accepts a mutation. Calling rejection "safety" is misleading — the engine accepts 10 incorrect mutations while rejecting 78 genuine IN_SCOPE failures. The rejections are not catching the incorrect ones.

---

## Q28. Is the Engine Solving the Wrong Problem?

**Yes.** The engine is principally attempting `document classification + information extraction` when the financial problem is `authoritative prior state + legally specified transformation -> authoritative successor state`.

**Code path evidence**:

1. `resolve_instruction` (`semantic_resolver_v2.py:458-557`) starts with `resolve_commitment_from_text(source_text, ...)` — **text classification**. It does not start with "given the current state, which commitment is this amendment most likely modifying?"

2. `_extract_values` (`semantic_resolver_v2.py:650-745`) extracts values from `source_text` regex — **information extraction**. It does not consult `current_commitment` (dead parameter) to verify or guide extraction.

3. `_validate_candidate` (`semantic_resolver_v2.py:788`) checks `hasattr(current_commitment, field)` — **structural validation**. It does not check that the mutation is semantically consistent with the predecessor state.

4. The executor (`executor.py:93-130`) applies `setattr(c, field, deepcopy(ins.new_value))` — **blind application**. It checks `old_value` if supplied, but the resolver never supplies it.

5. Authority determination (`semantic_pipeline_v2.py:247-251`) checks completeness — **structural gating**. It does not check semantic correctness.

The engine treats each amendment as a standalone text-classification-and-extraction problem. The predecessor state is available at every stage but is used only for key-set membership validation. The transformation `C_t = T_t(C_{t-1})` is never explicitly computed — the engine computes `C_t = Execute(Extract(Text_t))` and only incidentally carries forward unchanged fields via deep copy.

---

## Q29. Highest-Leverage MOSES Enforcement Points

| # | Insertion point | Current behavior | Missing invariant | IN_SCOPE failures affected | Incorrect accepted prevented | False positive risk |
|---|---|---|---|---:|---:|---|
| 1 | **Resolver: predecessor-state matching** (`semantic_resolver_v2.py:512`, after `current_commitment` retrieval) | Checks `None` only | Verify resolved canonical_id is the most likely target given predecessor state fields; reject if text match contradicts state evidence | 17 (all TARGET_IDENTIFICATION failures) | 4 (OUT_OF_SCOPE) + 2 (wrong class) | Low — only rejects when state evidence contradicts |
| 2 | **Resolver: old_value extraction** (`semantic_resolver_v2.py:556`, in `_extract_values`) | Never reads `current_commitment` | Extract `old_value` from `current_commitment.field` and supply to candidate; enables executor's existing old_value guard | 6 (all accepted_incorrect) | 6 (all IN_SCOPE wrong-value) | Low — executor already has the guard |
| 3 | **Executor: semantic scope guard** (`executor.py:114`, before `setattr`) | Checks `hasattr` only | Reject if instruction_type is ADD but target is not a new commitment and field is `exceptions` with a long text value (debt incurrence carve-out pattern) | 0 | 4 (OUT_OF_SCOPE) | Medium — may reject legitimate exception additions |
| 4 | **Authority: correctness gate** (`semantic_pipeline_v2.py:247`, in authority determination) | Checks completeness only | Add a correctness check: if any applied mutation at this step or earlier is flagged as incorrect, block authority | 0 | 1 (false auth promotion) | Low — only blocks when incorrect detected |
| 5 | **Resolver: identity persistence** (new, before `resolve_commitment_from_text`) | Re-resolves from text every time | If a commitment was resolved earlier in the same chain, prefer that identity unless text explicitly indicates a different commitment | 15+ (chains with repeated commitment references) | 2 (wrong class due to alias priority) | Medium — may miss genuine commitment switches |

---

## Q30. Recommended Step 24 Build Sequence

**Priority function**: `expected additional correct mappings` subject to `incorrect accepted mutations = 0` and `false authoritative promotions = 0`.

| Rank | Target | Expected correct gains | Safety gains | Rationale |
|---|---|---:|---|---|
| 1 | **Predecessor-state old_value extraction + executor guard activation** | +6 (all accepted_incorrect become rejected, then recoverable) | Eliminates 6/10 incorrect accepted | Highest safety impact. The executor guard already exists (`executor.py:119-122`) — the resolver just needs to supply `old_value` from `current_commitment.field`. This is the smallest change with the largest safety gain. |
| 2 | **OUT_OF_SCOPE scope guard for facility aliases** | +0 direct | Eliminates 4/10 incorrect accepted | Prevents debt-incurrence provisions from being mistaken for facility amendments. Check: if instruction_type is ADD and field is `exceptions` and new_value is a long text (not a short carve-out phrase), require manual review. |
| 3 | **Authority correctness gate** | +0 direct | Eliminates 1 false auth promotion | Block authority promotion when any applied mutation is flagged incorrect. Requires runtime incorrectness detection (not just post-hoc ground truth comparison). |
| 4 | **TARGET_IDENTIFICATION with predecessor-state bias** | +17 (all TARGET_IDENTIFICATION failures) | 0 | After fixing safety, this is the largest recoverable family. Use predecessor state to bias resolution: prefer commitments already in state, verify text match is consistent with state evidence. |
| 5 | **RESTATE_SECTION decomposition via predecessor-vs-successor differencing** | +41 (MULTI_FIELD_DECOMPOSITION) | 0 | Largest failure family but requires protocol extension (section differencing). Should be attempted only after safety and target identification are fixed. |

**Recommended sequence**: 1 -> 2 -> 3 -> 4 -> 5

This sequence ensures `incorrect accepted = 0` and `false auth promotions = 0` before attempting to recover correct mappings. Steps 1-3 are safety fixes with minimal code changes. Steps 4-5 are coverage improvements that build on the safety foundation.

---

# FINAL REQUIRED OUTPUT

## A. Current MOSES Implementation Map

| Component | Location | What it does |
|---|---|---|
| Commitment object | `models.py:97-123` `CommitmentState` | 22-field dataclass; 8 fields active, 14 dormant |
| Commitment identity | `commitment_registry.py:67-86` | 13 frozen canonical classes |
| Alias resolution | `commitment_registry.py:116-320` `_ALIASES` | 35 regex patterns -> 13 classes; spelling-based, not semantic |
| Section resolution | `commitment_registry.py:330-366` `_SECTION_MAP` | 24 section patterns -> classes; globally applied |
| Text resolution | `commitment_registry.py:374-417` `resolve_commitment_from_text` | Alias match -> state validation -> section fallback |
| Semantic resolver | `semantic_resolver_v2.py:458-557` `resolve_instruction` | 10-step resolver; text-based, predecessor state mostly ignored |
| Value extraction | `semantic_resolver_v2.py:650-745` `_extract_values` | Regex extraction from source_text; `current_commitment` is dead parameter |
| Validation | `semantic_resolver_v2.py:788` `_validate_candidate` | `hasattr` check only; `current_state` is dead parameter |
| Executor | `executor.py:17-179` `apply_instruction` | In-place mutation; old_value guard exists but never activated |
| Authority | `semantic_pipeline_v2.py:247-251` | Completeness-only check; no correctness gate |
| Mapper (v0.1) | `semantic_mapper.py:909-916` `_RULES` | 6 rules; no predecessor state access |

## B. Where Commitment Conservation Is Explicitly Enforced

| Enforcement | Location | Mechanism |
|---|---|---|
| Unchanged-field preservation | `executor.py:186` | Deep copy + in-place mutation |
| Old-value guard | `executor.py:119-122` | Rejects if `ins.old_value != current_field_value` — but never activated |
| Unresolved-state propagation | `semantic_pipeline_v2.py:254-260` | `inherited_unresolved` blocks authority |
| DELETE manual review | `semantic_resolver_v2.py:492-499` | All DELETE operations marked UNRESOLVED |
| RESTATE_SECTION rejection | `executor.py:174-177` | All RESTATE_SECTION raises UnresolvedInstruction |

## C. Where Commitment Conservation Is Missing or Bypassed

| Gap | Location | Impact |
|---|---|---|
| Predecessor field values not read | `semantic_resolver_v2.py:650` (`_extract_values` dead param) | 6 accepted_incorrect not caught |
| Commitment identity not persisted | `semantic_resolver_v2.py:482` (re-resolves every time) | 15+ failures from re-resolution |
| No scope check for OUT_OF_SCOPE | `semantic_resolver_v2.py:482-508` | 4 unauthorized mutations accepted |
| Authority has no correctness gate | `semantic_pipeline_v2.py:247-251` | 1 false authoritative promotion |
| old_value never supplied | `semantic_resolver_v2.py:556-557` | Executor guard never fires |
| No semantic legality check | `executor.py:114-115` | Wrong-class/wrong-value mutations accepted |
| Alias priority can override text | `commitment_registry.py:402-404` | 2 wrong-class accepted (revolving > leverage) |
| Section heuristic is global | `commitment_registry.py:330-366` | 2 wrong-class accepted (Section 7.10 -> leverage) |

## D. 86-Row Failure Census Summary

| Outcome | Count | % |
|---|---:|---:|
| Accepted correct | 2 | 2.3% |
| Accepted incorrect | 6 | 7.0% |
| Failed — TARGET_IDENTIFICATION | 67 | 77.9% |
| Failed — VALUE_EXTRACTION | 11 | 12.8% |
| **Total** | **86** | **100%** |

| Failure family | Count | % of 78 failed |
|---|---:|---:|
| MULTI_FIELD_DECOMPOSITION | 41 | 52.6% |
| TARGET_IDENTIFICATION | 16 | 20.5% |
| DELETE_REQUIRES_MANUAL_REVIEW | 6 | 7.7% |
| TABLE_OR_SCHEDULE_VALUE_EXTRACTION | 6 | 7.7% |
| DEFINED_TERM_RESOLUTION | 5 | 6.4% |
| VALUE_EXTRACTION | 4 | 5.1% |

| Protocol vs interpretation | Count | % of 78 failed |
|---|---:|---:|
| MOSES_PROTOCOL_INSUFFICIENCY | 58 | 74.4% |
| UPSILON_INTERPRETATION_FAILURE | 17 | 21.8% |
| AMBIGUOUS_FAILURE_TYPE | 3 | 3.8% |

## E. 10 Incorrect Accepted Mutation Root Causes

| ID | Type | Root cause |
|---|---|---|
| EDGAR-AMERESCO:A1:I5 | IN_SCOPE wrong value | Section heuristic (7.10->leverage) + wrong paragraph value extraction (3.5 vs 4.00) |
| EDGAR-AMERESCO:A2:I4 | IN_SCOPE wrong value | Same as A1:I5 (3.5 vs 3.75) |
| STUDY-007:A2:I2 | IN_SCOPE wrong value | Wrong paragraph span; extracted $10M instead of 7.00 ratio |
| STUDY-016:A2:I1 | IN_SCOPE wrong value | Definitions section; extracted 15.0 instead of 2.75 |
| STUDY-016:A2:I2 | IN_SCOPE wrong class+value | Section heuristic (9.01->leverage) overrode "current ratio" text; extracted 15.0 |
| HELD-010:A11:I6 | IN_SCOPE wrong class+value+unit | Alias priority: "Revolving Credit" (pri 10) matched before "Leverage Ratio" (pri 50); extracted $20M instead of 2.50 |
| HELD-017:A1:I1 | OUT_OF_SCOPE unauthorized | "Revolving Loans" in debt incurrence provision matched facility alias; exception ADD accepted |
| HELD-017:A4:I1 | OUT_OF_SCOPE unauthorized | Same mechanism (Ellie Mae Acquisition) |
| HELD-017:A4:I2 | OUT_OF_SCOPE unauthorized | Same mechanism |
| HELD-017:A4:I3 | OUT_OF_SCOPE unauthorized | Same mechanism |

## F. False Authoritative Promotion Root Cause

**Chain**: HELD-017, Amendment A1.

**Path**: Source text (IDHC Acquisition financing) -> parser (ADD, Article III) -> resolver (`Revolving Loans` alias matched `facility.revolving_facility`) -> mapper (`_rule_exception_add_remove` found "Notwithstanding") -> candidate (ADD exceptions, confidence 0.85) -> validator (`hasattr` check passed) -> executor (`c.exceptions.append()` applied) -> authority (COMPLETE + 0 unresolved + 0 inherited = **authoritative**).

**Missing invariant**: Authority determination checks structural completeness only. It does not verify that the applied mutation is semantically correct. The incorrect-mutation detection runs post-hoc (after the full chain) by comparing to ground truth — it is not available at authority-determination time.

**The exact invariant that should have prevented promotion**: "A step shall not be promoted to authoritative if any mutation applied at or before that step is semantically incorrect." This invariant is **NOT IMPLEMENTED** at runtime.

## G. Protocol Insufficiency vs Implementation Failure Counts

| Classification | Count | % of 84 non-correct |
|---|---:|---:|
| Representable but unresolved (interpretation failure) | 17 | 20.2% |
| Representable but misinterpreted (accepted wrong) | 6 | 7.1% |
| Not representable (protocol insufficiency) | 58 | 69.0% |
| Ambiguous | 3 | 3.6% |

## H. Recoverable Semantic Failure Rate

| Category | Count | % of 84 |
|---|---:|---:|
| Insufficient source evidence | 33 | 39.3% |
| Sufficient evidence not used | 15 | 17.9% |
| Sufficient evidence used incorrectly | 6 | 7.1% |
| Interpretation correct but exec failed | 0 | 0.0% |
| Protocol insufficient | 58 | 69.0% |

**Recoverable without protocol changes**: 23/84 (27.4%) — the 17 unresolved interpretation failures + 6 misinterpreted (fixable by predecessor-state matching + old_value guard).

**Recoverable with protocol extension**: +41/84 (48.8%) — MULTI_FIELD_DECOMPOSITION via section differencing.

**Total potentially recoverable**: 64/84 (76.2%).

## I. Top Five Highest-Leverage Engine Changes

| Rank | Change | IN_SCOPE failures fixed | Incorrect accepted prevented | False auth prevented |
|---|---|---:|---:|---:|
| 1 | Predecessor-state old_value extraction + executor guard | 6 (indirect) | 6 | 1 |
| 2 | OUT_OF_SCOPE scope guard for facility aliases in debt incurrence context | 0 | 4 | 0 |
| 3 | Authority correctness gate | 0 | 0 | 1 |
| 4 | TARGET_IDENTIFICATION with predecessor-state bias | 17 | 2 | 0 |
| 5 | RESTATE_SECTION decomposition via predecessor-vs-successor differencing | 41 | 0 | 0 |

## J. Recommended Step 24 Build Sequence

```
PHASE VI — STEP 24 BUILD SEQUENCE:

1. SAFETY: Predecessor-state old_value extraction
   - In _extract_values, read current_commitment.field and supply as old_value
   - Activates existing executor guard (executor.py:119-122)
   - Eliminates 6/10 incorrect accepted, 1 false auth promotion
   - Net: incorrect_accepted 10->4, false_auth 1->0

2. SAFETY: OUT_OF_SCOPE scope guard
   - In resolver, reject ADD-to-exceptions when source text contains
     debt incurrence signals (Indebtedness, Acquisition, prepay, defease)
     AND target is a facility class
   - Eliminates remaining 4/10 incorrect accepted
   - Net: incorrect_accepted 4->0

3. SAFETY: Authority correctness gate
   - In authority determination, block promotion if any applied mutation
     at or before this step is flagged incorrect
   - Requires runtime incorrectness detection (old_value mismatch)
   - Net: false_auth 0->0 (maintained), defense in depth

4. COVERAGE: TARGET_IDENTIFICATION with predecessor-state bias
   - Before text-based resolution, check if any commitment in
     current_state has a threshold/field consistent with the amendment
   - Prefer existing commitments over text-only matches
   - Recovers up to 17 TARGET_IDENTIFICATION failures
   - Net: correct mappings 2->19, eligible coverage 2.3%->22.1%

5. COVERAGE: RESTATE_SECTION decomposition (protocol extension)
   - Compare restated section text against predecessor state
   - Derive delta (which fields changed, from what to what)
   - Recovers up to 41 MULTI_FIELD_DECOMPOSITION failures
   - Net: correct mappings 19->60, eligible coverage 22.1%->69.8%
```

**Constraint**: Steps 1-3 must be completed and verified (`incorrect_accepted = 0`, `false_auth_promotions = 0`) before Step 4 begins. Step 5 requires a protocol extension and should be the final phase.

---

**Summary**: Upsilon is not currently giving MOSES Commitment Theory the information and enforcement structure it was designed to use. The engine treats amendments as standalone text-classification-and-extraction problems, ignoring predecessor state for target resolution, value verification, and scope control. The 13 commitment classes are used as text-matching targets, not as conserved identities. The result is a 16.7% semantic precision (2/12 accepted mutations correct) with 10 incorrect accepted mutations and 1 false authoritative promotion. The highest-leverage fix is activating the existing old_value guard by supplying predecessor field values — a small change that eliminates 60% of incorrect accepted mutations.
