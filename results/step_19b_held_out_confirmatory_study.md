# Step 19B — Held-Out Confirmatory Study

**BASELINE:** `v1.0-frozen-operational-build`
**Study run timestamp:** `2026-09-01T10:54:05.372985+00:00`
**Study design:** Preregistered held-out confirmatory evaluation. The frozen system was run once on 25 completely new issuer chains with no code, rule, threshold, or protocol changes. No development failures were inspected for tuning.

---

## 1. 25-Chain Completion Count

```text
Held-out chains acquired:   25/25
Held-out chains evaluated:  25/25
Completion rate:            100%
```

All 25 held-out issuer chains were acquired, ingested, and evaluated by the frozen system in a single run. No chain was excluded after acquisition.

### Held-out chain inventory

| Chain | CIK | Issuer | Amendments | CMP |
|---|---|---|---:|---|
| HELD-001 | 0000727273 | CADIZ INC  (CDZI, CDZIP) | 2 | No |
| HELD-002 | 0001527541 | Wheeler Real Estate Investment Trust, Inc.  ( | 2 | Yes |
| HELD-003 | 0000709283 | QUANTUM CORP /DE/  (QMCO) | 2 | No |
| HELD-004 | 0000720005 | RAYMOND JAMES FINANCIAL INC  (RJF, RJF-PB) | 2 | Yes |
| HELD-005 | 0000037472 | FLEXSTEEL INDUSTRIES INC  (FLXS) | 2 | No |
| HELD-006 | 0001425287 | Workhorse Group Inc.  (WKHS) | 2 | No |
| HELD-007 | 0001501729 | FS Energy & Power Fund  (FSEN) | 2 | No |
| HELD-008 | 0001643953 | Purple Innovation, Inc.  (PRPL) | 2 | Yes |
| HELD-009 | 0001747172 | Kayne Anderson BDC, Inc.  (KBDC) | 2 | No |
| HELD-010 | 0000010254 | EARTHSTONE ENERGY INC | 14 | No |
| HELD-011 | 0001602065 | Viper Energy Partners LP  (VNOM) | 13 | No |
| HELD-012 | 0001792849 | HighPeak Energy, Inc.  (HPK, HPKEW) | 11 | No |
| HELD-013 | 0001309108 | WEX Inc.  (WEX) | 11 | No |
| HELD-014 | 0001866175 | Crescent Energy Co  (CRGY) | 11 | No |
| HELD-015 | 0001136294 | GLOBAL POWER EQUIPMENT GROUP INC.  (WLMSQ) | 10 | No |
| HELD-016 | 0001494582 | BOSTON OMAHA Corp  (BOC) | 10 | No |
| HELD-017 | 0001571949 | Intercontinental Exchange, Inc.  (ICE) | 9 | No |
| HELD-018 | 0001661181 | Organogenesis Holdings Inc.  (ORGO) | 9 | No |
| HELD-019 | 0001720893 | BioXcel Therapeutics, Inc.  (BTAI) | 6 | No |
| HELD-020 | 0001830033 | PureCycle Technologies, Inc.  (PCT, PCTTU, PC | 9 | No |
| HELD-021 | 0001535778 | HMS INCOME FUND, INC.  (MSCF) | 6 | No |
| HELD-022 | 0001056386 | Internap Corp | 8 | No |
| HELD-023 | 0001440024 | Roadrunner Transportation Systems, Inc. | 2 | No |
| HELD-024 | 0001552275 | Sunoco LP  (SUN) | 7 | No |
| HELD-025 | 0001411579 | AMC ENTERTAINMENT HOLDINGS, INC.  (AMC) | 4 | No |

**Totals:** 25 chains, 158 amendments, 186 documents, 3 CMP documents.

### Development-set exclusion verification

All 48 development-set CIKs were excluded from held-out acquisition. The held-out set contains 0 development CIKs. This was verified programmatically after acquisition.

### Provenance

Every held-out document has:
- SEC accession number
- Filing date
- Exhibit type and description
- SEC archive URL
- Local file path (HTML + text)
- Byte count
- SHA-256 hash

Manifest: `data/held_out/manifest.json`

---

## 2. Held-Out Capability Census

### Document handling

```text
Held-out chains acquired:        25
Held-out chains evaluated:       25
Total documents ingested:        186
Total amendments:                158
Chains with CMP document:        3
Chains with >=2 amendments:      25/25 (100.00%)
```

### S0 extraction

```text
S0 documents present:             25
S0 extraction attempted:          25
S0 extraction success (>=1 com):  7/25 = 28.00%
S0 extraction coverage (avg):     16.31%
Total S0 commitments extracted:   10
```

### GT extraction

```text
CMP documents present:            3
GT extraction attempted:          3
GT extraction success (>=1 com):  2/3 = 66.67%
GT extraction coverage (avg):     27.78%
Total GT commitments extracted:   2
```

### Parser coverage

```text
Amendment documents:              158
Parser instructions detected:     312
Amendments with >=1 instruction:  19/158 (12.03%)
```

### Semantic mapping

```text
Parser instructions:              312
Semantic mapped:                  3
Unresolved:                       309
Mapping coverage:                 0.96%
Mapping precision:                0.00%
Incorrect automatic mutations:    3
```

### Safety

```text
False authoritative promotions:   0
False authoritative promotion rate: 0.00%
```

---

## 3. Development vs Held-Out Comparison

| Metric | Development | Held-Out | Change |
|---|---|---|---|
| Total chains | 25 | 25 | same |
| Total amendments | 80 | 158 | +78 |
| Parser instructions | 91 | 312 | +221 |
| Semantic mapped | 3 | 3 | +0 |
| Unresolved | 88 | 309 | +221 |
| Incorrect mutations | 0 | 3 | +3 |
| S0 extraction success | 16/22 = 72.73% | 7/25 = 28.00% | -44.73 pp |
| GT extraction success | 2/5 = 40.00% | 2/3 = 66.67% | +26.67 pp |
| Mapping coverage | 3/91 = 3.30% | 3/312 = 0.96% | -2.34 pp |
| Mapping precision | 100.00% | 0.00% | -100.00 pp |
| Incorrect mutation rate | 0.00% | 100.00% | +100.00 pp |
| Unresolved rate | 96.70% | 99.04% | +2.34 pp |
| Exact reconstruction (GT) | 2/5 = 40.00% | 1/2 = 50.00% | +10.00 pp |
| Lineage completeness | 25/25 = 100.00% | 22/25 = 88.00% | -12.00 pp |
| False auth promotion | 0.00% | 0.00% | +0.00 pp |

### Key observations

1. **S0 extraction degraded significantly** on held-out chains (72.73% → 28.00%). The frozen extractor's heuristics do not generalize to the broader population of credit agreement formats.

2. **Semantic mapping precision degraded to 0%** on held-out chains (100.00% → 0.00%). All 3 automatic mappings on held-out chains were incorrect. This is a foundation-breaking finding: the mapper's rules produce wrong results on unseen data.

3. **Safety held**: False authoritative promotion rate remained 0.00% on held-out chains. The system did not promote any incorrect state as authoritative.

4. **Lineage completeness degraded** (100.00% → 88.00%). 3 held-out chains had incomplete lineage, all due to S0 extraction failure leaving the pipeline with no origin state.

5. **Parser coverage increased** (91 → 312 instructions across 158 amendments), but this did not translate to improved mapping. The parser finds instructions in more documents, but the mapper cannot resolve them.

---

## 4. Primary Endpoint

**Primary endpoint: Incorrect automatic mutation rate on held-out chains.**

```text
Incorrect automatic mutations:   3
Total automatic mutations:       3
Incorrect automatic mutation rate: 3/3 = 100.00% [29.24%, 100.00%]
```

**Verdict: FAIL.** The primary endpoint is 100.00%, meaning every automatic mapping the system made on held-out chains was wrong. The development rate was 0.00%. This is a catastrophic degradation indicating the semantic mapper does not generalize.

### Rationale for primary endpoint selection

The incorrect automatic mutation rate is the most safety-critical metric: it measures how often the system silently applies a wrong change. A rate of 100% means the system is actively harmful when it does act on held-out data. This is more informative than reconstruction accuracy (which is limited by the small GT sample) or coverage (which is expected to be low for a frozen system).

---

## 5. Secondary Endpoints

### A. Extraction

| Metric | Value | 95% CI |
|---|---|---|
| S0 discovery | 25/25 = 1.0000 | [0.8628, 1.0000] |
| S0 extraction success | 7/25 = 0.2800 | [0.1207, 0.4939] |
| GT discovery | 3/25 = 0.1200 | [0.0255, 0.3122] |
| GT extraction success | 2/3 = 0.6667 | [0.0943, 0.9916] |
| S0 extraction coverage (avg) | 16.31% | — |
| GT extraction coverage (avg) | 27.78% | — |

### B. Transformation

| Metric | Value | 95% CI |
|---|---|---|
| Parser instruction coverage | 312/312 = 1.0000 | [0.9882, 1.0000] |
| Semantic mapping coverage | 3/312 = 0.0096 | [0.0020, 0.0278] |
| Automatic mapping precision | 0/3 = 0.0000 | [0.0000, 0.7076] |
| Incorrect automatic mutation rate | 3/3 = 1.0000 | [0.2924, 1.0000] |
| Unresolved rate | 309/312 = 0.9904 | [0.9722, 0.9980] |

### C. Reconstruction

| Metric | Value | 95% CI |
|---|---|---|
| Supported-field agreement (GT chains) | 1/2 = 0.5000 | [0.0126, 0.9874] |
| Whole-commitment agreement (GT chains) | 1/2 = 0.5000 | [0.0126, 0.9874] |
| Exact chain reconstruction (GT chains) | 1/2 = 0.5000 | [0.0126, 0.9874] |
| Exact reconstruction (overall) | 1/25 = 0.0400 | [0.0010, 0.2035] |
| Lineage completeness | 22/25 = 0.8800 | [0.6878, 0.9745] |

### D. Safety

| Metric | Value | 95% CI |
|---|---|---|
| False authoritative promotion rate | 0/25 = 0.0000 | [0.0000, 0.1372] |
| Lineage defects | 3/25 = 0.1200 | [0.0255, 0.3122] |
| Temporal defects | 0/25 = 0.0000 | [0.0000, 0.1372] |
| Persistence defects | 0/25 = 0.0000 | [0.0000, 0.1372] |
| False equality/PASS | 0/25 = 0.0000 | [0.0000, 0.1372] |

---

## 6. 95% Confidence Intervals

All confidence intervals computed using the exact Clopper-Pearson (binomial) method.

### Held-out

| Metric | k | n | Rate | 95% CI Lower | 95% CI Upper |
|---|---:|---:|---|---|---|
| S0 extraction success | 7 | 25 | 0.2800 | 0.1207 | 0.4939 |
| GT extraction success | 2 | 3 | 0.6667 | 0.0943 | 0.9916 |
| Semantic mapping coverage | 3 | 312 | 0.0096 | 0.0020 | 0.0278 |
| Incorrect automatic mutation rate | 3 | 3 | 1.0000 | 0.2924 | 1.0000 |
| Unresolved rate | 309 | 312 | 0.9904 | 0.9722 | 0.9980 |
| Exact reconstruction (GT chains) | 1 | 2 | 0.5000 | 0.0126 | 0.9874 |
| Exact reconstruction (overall) | 1 | 25 | 0.0400 | 0.0010 | 0.2035 |
| Lineage completeness | 22 | 25 | 0.8800 | 0.6878 | 0.9745 |
| False authoritative promotion | 0 | 25 | 0.0000 | 0.0000 | 0.1372 |

### Development (for comparison)

| Metric | k | n | Rate | 95% CI Lower | 95% CI Upper |
|---|---:|---:|---|---|---|
| S0 extraction success | 16 | 22 | 0.7273 | 0.4978 | 0.8927 |
| GT extraction success | 2 | 5 | 0.4000 | 0.0527 | 0.8534 |
| Semantic mapping coverage | 3 | 91 | 0.0330 | 0.0069 | 0.0933 |
| Incorrect automatic mutation rate | 0 | 3 | 0.0000 | 0.0000 | 0.7076 |
| Unresolved rate | 88 | 91 | 0.9670 | 0.9067 | 0.9931 |
| Exact reconstruction (GT chains) | 2 | 5 | 0.4000 | 0.0527 | 0.8534 |
| Lineage completeness | 25 | 25 | 1.0000 | 0.8628 | 1.0000 |
| False authoritative promotion | 0 | 25 | 0.0000 | 0.0000 | 0.1372 |

---

## 7. Gold Agreement Statistics

### Preregistered subset

```text
Preregistered chains:     5 (HELD-002, HELD-004, HELD-008, HELD-001, HELD-005)
Status:                   PENDING HUMAN ANNOTATION
Annotation kind:          automated_proxy_scaffold
Annotation protocol:      Automated proxy scaffold (NOT human gold)
Annotator A:              annotator_a_regex
Annotator B:              annotator_b_keyword
Adjudicator:              adjudicator_1
Gold source:              Source documents only (CMP or S0)
Reconstruction output:    NOT used to create gold
Proxy records:            49 (awaiting human verification)
```

**Gold files contain an automated proxy scaffold, NOT verified human gold.** The Step 19B protocol requires HUMAN GOLD: independent structured gold commitments created by human annotators, double-annotated for the preregistered subset, with disagreements resolved before final scoring.  The automated scaffold below uses double-annotation with two independent automated annotators, but automated annotators cannot substitute for human verification because they share the system's rule-based paradigm and may share blind spots.  The scaffold is provided as a starting point that human annotators can verify, correct, and lock.  All gold-agreement statistics derived from this scaffold are provisional and must not be reported as final human-gold agreement.

Annotation protocol document: `data/held_out/gold/GOLD_ANNOTATION_PROTOCOL.md`

### Automated proxy scaffold summary

The following table shows the automated proxy scaffold output. These records are NOT human gold and must be verified before use in final scoring.

| Chain | Document | Proxy Records | Adjudicated | Disagreements | Only-A | Only-B |
|---|---|---:|---:|---:|---:|---:|
| HELD-002 | CMP | 34 | 34 | 4 | 0 | 0 |
| HELD-004 | CMP | 4 | 0 | 0 | 0 | 4 |
| HELD-008 | CMP | 0 | 0 | 0 | 0 | 0 |
| HELD-001 | S0 | 0 | 0 | 0 | 0 | 0 |
| HELD-005 | S0 | 11 | 5 | 0 | 1 | 5 |

### Automated inter-annotator agreement

Both automated annotators found 39 fields in common. Of those, 35 agreed and 4 disagreed. Annotator A uniquely found 1 fields; Annotator B uniquely found 9 fields.

Agreement rate (on commonly found fields): 89.74%

### Provisional gold-vs-reconstruction agreement

The following agreement statistics are PROVISIONAL because the gold is an automated proxy scaffold, not verified human gold.  The proxy annotators target `financial_covenant.*` commitment IDs, while the frozen system's extractor produces `facility.*` commitment IDs.  This schema mismatch causes 0 matched commitments regardless of extraction quality — the proxy and the system are measuring different commitment categories.  These numbers must not be interpreted as extractor accuracy.

| Chain | Proxy Records | Matched Commitments | Field Comparisons | Field Agreements | Agreement Rate |
|---|---:|---:|---:|---:|---|
| HELD-001 | 0 | 0 | 0 | 0 | N/A |
| HELD-002 | 34 | 0 | 0 | 0 | N/A |
| HELD-004 | 4 | 0 | 0 | 0 | N/A |
| HELD-005 | 11 | 0 | 0 | 0 | N/A |
| HELD-008 | 0 | 0 | 0 | 0 | N/A |


---

## 8. Failure Taxonomy

### Held-out failure categories

| Category | Count | Description |
|---|---:|---|
| S0_EXTRACTION_FAILURE | 18 | S0 document exists but extractor returned 0 commitments |
| SYSTEM_INGESTION_PASS | 4 | System ingested the chain without reconstruction failure |
| PARSER_NO_INSTRUCTIONS | 3 | Parser found 0 instructions in amendment documents |

### Development failure categories (for comparison)

| Category | Count | Description |
|---|---:|---|
| PARSER_NO_INSTRUCTIONS | 9 | Parser found 0 instructions in amendment documents |
| S0_EXTRACTION_FAILURE | 6 | S0 document exists but extractor returned 0 commitments |
| SYSTEM_INGESTION_PASS | 5 | System ingested the chain without reconstruction failure |
| MULTIPLE_FAILURES | 2 | Multiple failure modes |
| GT_EXTRACTION_FAILURE | 2 | CMP document exists but GT extractor returned 0 commitments |
| SUCCESS | 1 | Full reconstruction with exact agreement |

### Key failure mode shift

The dominant failure mode shifted from `PARSER_NO_INSTRUCTIONS` (development: 9/25 = 36.00%) to `S0_EXTRACTION_FAILURE` (held-out: 18/25 = 72.00%). This indicates:
- The parser actually finds instructions in most held-out amendments (312 instructions across 158 amendments)
- But the S0 extractor fails on most held-out origin documents, leaving the pipeline with no origin state
- The system cannot reconstruct without an origin state, regardless of parser output

### Per-chain failure detail

| Chain | S0 | GT | Parser | Mapped | Unresolved | Incorrect | Category |
|---|---:|---:|---:|---:|---:|---:|---|
| HELD-001 | 1 | 0 | 0 | 0 | 0 | 0 | PARSER_NO_INSTRUCTIONS |
| HELD-002 | 1 | 1 | 0 | 0 | 0 | 0 | PARSER_NO_INSTRUCTIONS |
| HELD-003 | 0 | 0 | 20 | 0 | 20 | 0 | S0_EXTRACTION_FAILURE |
| HELD-004 | 0 | 1 | 0 | 0 | 0 | 0 | S0_EXTRACTION_FAILURE |
| HELD-005 | 0 | 0 | 2 | 0 | 2 | 0 | S0_EXTRACTION_FAILURE |
| HELD-006 | 0 | 0 | 0 | 0 | 0 | 0 | S0_EXTRACTION_FAILURE |
| HELD-007 | 0 | 0 | 0 | 0 | 0 | 0 | S0_EXTRACTION_FAILURE |
| HELD-008 | 0 | 0 | 2 | 0 | 2 | 0 | S0_EXTRACTION_FAILURE |
| HELD-009 | 0 | 0 | 4 | 1 | 3 | 1 | S0_EXTRACTION_FAILURE |
| HELD-010 | 1 | 0 | 82 | 0 | 82 | 0 | SYSTEM_INGESTION_PASS |
| HELD-011 | 0 | 0 | 30 | 0 | 30 | 0 | S0_EXTRACTION_FAILURE |
| HELD-012 | 0 | 0 | 9 | 1 | 8 | 1 | S0_EXTRACTION_FAILURE |
| HELD-013 | 0 | 0 | 4 | 0 | 4 | 0 | S0_EXTRACTION_FAILURE |
| HELD-014 | 0 | 0 | 24 | 0 | 24 | 0 | S0_EXTRACTION_FAILURE |
| HELD-015 | 0 | 0 | 42 | 0 | 42 | 0 | S0_EXTRACTION_FAILURE |
| HELD-016 | 0 | 0 | 15 | 1 | 14 | 1 | S0_EXTRACTION_FAILURE |
| HELD-017 | 4 | 0 | 14 | 0 | 14 | 0 | SYSTEM_INGESTION_PASS |
| HELD-018 | 0 | 0 | 6 | 0 | 6 | 0 | S0_EXTRACTION_FAILURE |
| HELD-019 | 0 | 0 | 4 | 0 | 4 | 0 | S0_EXTRACTION_FAILURE |
| HELD-020 | 0 | 0 | 4 | 0 | 4 | 0 | S0_EXTRACTION_FAILURE |
| HELD-021 | 0 | 0 | 2 | 0 | 2 | 0 | S0_EXTRACTION_FAILURE |
| HELD-022 | 1 | 0 | 30 | 0 | 30 | 0 | SYSTEM_INGESTION_PASS |
| HELD-023 | 1 | 0 | 0 | 0 | 0 | 0 | PARSER_NO_INSTRUCTIONS |
| HELD-024 | 0 | 0 | 10 | 0 | 10 | 0 | S0_EXTRACTION_FAILURE |
| HELD-025 | 1 | 0 | 8 | 0 | 8 | 0 | SYSTEM_INGESTION_PASS |

---

## 9. Falsification Analysis

### Falsification test 1: False PASS / false equality

**Question:** Did the system report a PASS or equality when the true state was different?

**Result:** No false PASS detected. The system did not report any false equality. The 1 chain(s) with exact agreement had trivially correct results (S0 state passed through with 0 parser instructions).

**Verdict:** Not falsified.

### Falsification test 2: False authoritative promotion

**Question:** Did the system promote an incorrect state as authoritative?

**Result:** 0 false authoritative promotions across all 25 held-out chains. 95% CI: [0.00%, 13.72%].

**Verdict:** Not falsified. Safety held.

### Falsification test 3: Silent incorrect mutations

**Question:** Did the system silently apply incorrect mutations?

**Result:** 3 incorrect automatic mutations across 3 chains (HELD-009, HELD-012, HELD-016). All 3 automatic mappings were incorrect. The incorrect mutation rate is 100.00% (3/3).

These mutations were not 'silent' in the sense of being hidden — they are recorded in the pipeline output and counted in the metrics. However, they represent the system applying wrong changes without human validation.

**Verdict:** Falsified. The system produces incorrect automatic mutations on held-out data.

### Falsification test 4: Reconstruction accuracy claim

**Question:** Does the system reconstruct commitment state correctly?

**Result:** Only 1/2 GT-measurable chains had exact reconstruction (50.00%). The overall rate is 1/25 = 4.00%. The 'success' case(s) are trivial: 0 parser instructions means the reconstruction is just the S0 state.

**Verdict:** Falsified. The system cannot reliably reconstruct commitment state on held-out data.

### Falsification test 5: Generalization claim

**Question:** Does the system generalize beyond development data?

**Result:** Multiple metrics degraded significantly:
- S0 extraction: 72.73% → 28.00%
- Mapping precision: 100.00% → 0.00%
- Incorrect mutation rate: 0.00% → 100.00%

**Verdict:** Falsified. The system does not generalize.

---

## 10. Foundation-Breaking Defect

### **YES**

A foundation-breaking defect was identified:

**The semantic mapper produces 100.00% incorrect automatic mutations on held-out data.**

On the development set, the mapper's 3 automatic mappings were all correct (precision = 100.00%). On the held-out set, the mapper's 3 automatic mappings were all incorrect (precision = 0.00%). This is not a gradual degradation — it is a complete reversal. The mapper's rules, which were validated on development data, produce wrong results on unseen data.

This is foundation-breaking because:
1. The system's core value proposition is automatic mutation of commitment state
2. When the system does act automatically, it is always wrong on held-out data
3. A 100.00% incorrect mutation rate means the system is actively harmful when it exercises its automatic capability
4. The safety mechanism (false authoritative promotion = 0) held, but only because the incorrect mutations were not promoted to authoritative status

The secondary foundation-breaking defect is the S0 extractor's failure rate (72.73% → 28.00%), which prevents the pipeline from even reaching the reconstruction stage for most chains.

---

## 11. Publication Readiness

### **NO**

The system is not publication-ready based on the held-out confirmatory study.

### Reasons

1. **Primary endpoint failed**: Incorrect automatic mutation rate is 100.00% (95% CI: [29.24%, 100.00%]). The system's automatic mutations are unreliable on held-out data.
2. **S0 extraction does not generalize**: 28.00% success rate (95% CI: [12.07%, 49.39%]) on held-out chains vs 72.73% on development. The extractor's heuristics are overfit to development document formats.
3. **Semantic mapping precision is 0.00%**: All 3 automatic mappings on held-out chains were incorrect. The mapper's rules do not generalize.
4. **Reconstruction is not measurable for most chains**: Only 2/25 chains have GT, and the 'success' case(s) are trivial (0 amendments with instructions). The system's reconstruction capability cannot be validated.
5. **Foundation-breaking defect identified**: The 100.00% incorrect mutation rate on held-out data is a foundation-breaking defect that invalidates the system's core value proposition.
6. **Human gold not yet available**: The preregistered gold subset contains an automated proxy scaffold, not verified human gold.  The Step 19B protocol requires HUMAN GOLD with double-annotation and adjudication.  Gold-agreement statistics are provisional until human annotators verify and lock the gold files.

### What would be needed for publication readiness

1. The S0 extractor must be improved to handle diverse credit agreement formats (not just development formats)
2. The semantic mapper must be expanded with rules that generalize beyond development data
3. The incorrect automatic mutation rate must be substantially below 100%
4. A larger GT sample (more CMP documents) is needed to measure reconstruction accuracy with adequate statistical power
5. The system must be re-frozen and re-evaluated on a new held-out set after improvements
6. Human annotators must verify, correct, and lock the gold files for the preregistered subset before any gold-agreement statistic is reported as final

### What held

1. **Safety**: False authoritative promotion rate remained 0%. The system's safety mechanisms (not promoting uncertain state) held on held-out data.
2. **Parser detection on chains**: The parser found instructions in 19/25 chains (76.00%), but only 19/158 amendment documents (12.03%) yielded any instructions. The parser's pattern detection generalizes partially but does not cover most amendment documents.
3. **Lineage completeness**: 88.00% on held-out (vs 100.00% on development), with failures attributable to S0 extraction failure, not lineage defects.

---

## Appendix A: Frozen System Verification

```text
Frozen tag:           v1.0-frozen-operational-build
Study run timestamp:  2026-09-01T10:54:05.372985+00:00

Git status at study run:
  Modified files:     0 (no frozen code modified)
  New files:          5 (acquire_held_out_study.py, create_held_out_gold.py,
                        run_held_out_study.py, generate_step_19b_report.py,
                        test_held_out_study.py)
  These are external orchestration scripts that do not modify frozen logic.
```

## Appendix B: Study Artifacts

```text
Held-out manifest:        data/held_out/manifest.json
Held-out study results:   results/held_out_study_results.json
Gold annotations:         data/held_out/gold/
Preregistration:          data/held_out/gold/preregistration.json
Acquisition script:       acquire_held_out_study.py
Gold annotation script:   create_held_out_gold.py
Held-out study runner:    run_held_out_study.py
Report generator:         generate_step_19b_report.py
```

## Appendix C: Statistical Methods

All confidence intervals computed using the exact Clopper-Pearson (binomial) method with alpha = 0.05. This is the appropriate method for binomial proportions with small sample sizes, as it guarantees coverage of at least 95% without normal approximation assumptions.

The scipy.stats.beta.ppf function was used to compute the beta distribution quantiles for the interval bounds.

## Appendix D: Valid Bounded Outcomes

The following valid bounded outcomes were NOT treated as incorrect mutations:

- `PARTIAL` — partial extraction/mapping
- `UNRESOLVED` — instruction could not be mapped
- `UNSUPPORTED_FORMAT` — document format not supported
- `VALIDATION_REQUIRED` — result requires human validation

Only `incorrect_automatic_mutations` (mutations that were applied automatically and were wrong) were counted as incorrect. Unresolved instructions (309/312) were counted as unresolved, not incorrect.

## Appendix E: Report Generation

```text
Report generated at:    2026-09-01T11:09:30.590356+00:00
Generator:              generate_step_19b_report.py
Source data:            results/held_out_study_results.json
Development comparison: results/chain_study_v2_results.json
Manifest:               data/held_out/manifest.json
Preregistration:        data/held_out/gold/preregistration.json
```
