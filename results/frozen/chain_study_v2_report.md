# Development Chain Study v2 — Measurement-Loop Report

**Frozen system: semantic-mapper-v0.1 (tag: semantic-mapper-v0.1)**
**New components: S0 Commitment Extractor v0.1, Authoritative GT Extractor v0.1**

## Study Protocol

```text
S0 legal document
  → automated origin-state extraction (S0 Extractor v0.1)
  → structured initial commitment state
  → amendment parser / semantic mapper / executor / lineage
  → reconstructed final state
  → independent authoritative ground-truth extraction (GT Extractor v0.1)
  → exact comparison
```

### Key principle: prediction path != validation path

The S0 extractor feeds the reconstruction pipeline (origin state).
The GT extractor feeds the comparison (ground truth state).
Both use the same deterministic extraction engine but process
different documents. Neither uses amendment reconstruction output
to construct the other.

## Extraction Summary

```text
Chains with extracted S0 state:    12/22
Chains with CMP document:          5/22
Chains with extracted GT state:    2/5
Total S0 commitments extracted:    27
Total GT commitments extracted:    8
Total S0 validation queue items:   14
Total GT validation queue items:   6
S0 extraction success rate:        54.5%
GT extraction success rate:        40.0%
S0 extraction coverage (avg):      40.3%
GT extraction coverage (avg):      25.0%
```

## Per-Issuer Results

```text
EDGAR-AMERESCO  Ameresco, Inc.                          
  has ground truth:         yes (source: manual)
  extraction status:        n/a
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    14
  semantic-mapped instr:    3
  UNRESOLVED instr:         11
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  100.0%
  supported-field agree:    100.0%
  failure category:         SUCCESS

EDGAR-AMEDISYS  Amedisys, Inc.                          
  has ground truth:         yes (source: manual)
  extraction status:        n/a
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  100.0%
  supported-field agree:    100.0%
  failure category:         PARSER_NO_INSTRUCTIONS

EDGAR-BAUSCH-LOMB  Bausch + Lomb Corporation               
  has ground truth:         yes (source: manual)
  extraction status:        n/a
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  25.0%
  supported-field agree:    46.9%
  failure category:         PARSER_NO_INSTRUCTIONS

STUDY-004  CareView Communications Inc  (CRVW) (CIK
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    4
  semantic-mapped instr:    0
  UNRESOLVED instr:         4
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-005  TUPPERWARE BRANDS CORP  (TUP) (CIK 00010
  has ground truth:         no (source: none)
  extraction status:        s0_incomplete
  S0 extracted commitments: 2 (coverage: 66.7%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    2
  semantic-mapped instr:    0
  UNRESOLVED instr:         2
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         SYSTEM_INGESTION_PASS

STUDY-006  AMERICA FIRST MULTIFAMILY INVESTORS, L.P
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    2
  semantic-mapped instr:    0
  UNRESOLVED instr:         2
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-007  CARROLS RESTAURANT GROUP, INC. (CIK 0000
  has ground truth:         no (source: none)
  extraction status:        s0_incomplete
  S0 extracted commitments: 2 (coverage: 66.7%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    18
  semantic-mapped instr:    2
  UNRESOLVED instr:         16
  incorrect auto mutations: 2
  chain authoritative?      no
  lineage complete?         no
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         MULTIPLE_FAILURES

STUDY-008  RGC RESOURCES INC  (RGCO) (CIK 000106953
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    3
  semantic-mapped instr:    0
  UNRESOLVED instr:         3
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-010  Presto Automation Inc.  (PRST, PRSTW) (C
  has ground truth:         no (source: none)
  extraction status:        s0_incomplete
  S0 extracted commitments: 1 (coverage: 50.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         PARSER_NO_INSTRUCTIONS

STUDY-012  Yuma Energy, Inc. (CIK 0000081318)      
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    11
  semantic-mapped instr:    0
  UNRESOLVED instr:         11
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-013  Digerati Technologies, Inc.  (DTGI) (CIK
  has ground truth:         no (source: none)
  extraction status:        s0_incomplete
  S0 extracted commitments: 1 (coverage: 50.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         PARSER_NO_INSTRUCTIONS

STUDY-014  Chefs' Warehouse, Inc.  (CHEF) (CIK 0001
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    3
  semantic-mapped instr:    0
  UNRESOLVED instr:         3
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-015  WINTRUST FINANCIAL CORP  (WTFC, WTFCM, W
  has ground truth:         yes (source: CMP)
  extraction status:        s0_and_gt_incomplete
  S0 extracted commitments: 4 (coverage: 36.4%)
  GT extracted commitments: 6 (coverage: 75.0%)
  parser-detected instr:    4
  semantic-mapped instr:    0
  UNRESOLVED instr:         4
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  0.0%
  supported-field agree:    58.3%
  failure category:         MULTIPLE_FAILURES

STUDY-016  NORTHERN OIL & GAS, INC.  (NOG) (CIK 000
  has ground truth:         no (source: CMP)
  extraction status:        gt_failure
  S0 extracted commitments: 3 (coverage: 100.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    8
  semantic-mapped instr:    0
  UNRESOLVED instr:         8
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         GT_EXTRACTION_FAILURE

STUDY-017  MOLINA HEALTHCARE INC  (MOH) (CIK 000117
  has ground truth:         no (source: none)
  extraction status:        ok
  S0 extracted commitments: 2 (coverage: 100.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    4
  semantic-mapped instr:    0
  UNRESOLVED instr:         4
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         SYSTEM_INGESTION_PASS

STUDY-018  Yuma Energy, Inc. (CIK 0001672326)      
  has ground truth:         no (source: CMP)
  extraction status:        gt_failure
  S0 extracted commitments: 3 (coverage: 75.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    3
  semantic-mapped instr:    0
  UNRESOLVED instr:         3
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         GT_EXTRACTION_FAILURE

STUDY-020  FlexShopper, Inc.  (FPAY) (CIK 000139704
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    9
  semantic-mapped instr:    0
  UNRESOLVED instr:         9
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-021  Vertex Energy Inc.  (VTNR) (CIK 00008904
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-022  FASTENAL CO  (FAST) (CIK 0000815556)    
  has ground truth:         yes (source: CMP)
  extraction status:        gt_incomplete
  S0 extracted commitments: 2 (coverage: 100.0%)
  GT extracted commitments: 2 (coverage: 50.0%)
  parser-detected instr:    4
  semantic-mapped instr:    1
  UNRESOLVED instr:         3
  incorrect auto mutations: 1
  chain authoritative?      no
  lineage complete?         no
  final-state exact agree:  0.0%
  supported-field agree:    87.5%
  failure category:         MULTIPLE_FAILURES

STUDY-026  BOSTON SCIENTIFIC CORP  (BSX) (CIK 00008
  has ground truth:         no (source: none)
  extraction status:        s0_incomplete
  S0 extracted commitments: 3 (coverage: 75.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    1
  semantic-mapped instr:    0
  UNRESOLVED instr:         1
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         SYSTEM_INGESTION_PASS

STUDY-027  BRADY CORP  (BRC) (CIK 0000746598)      
  has ground truth:         no (source: none)
  extraction status:        s0_incomplete
  S0 extracted commitments: 2 (coverage: 66.7%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         PARSER_NO_INSTRUCTIONS

STUDY-028  B&G Foods, Inc.  (BGS) (CIK 0001278027) 
  has ground truth:         no (source: none)
  extraction status:        ok
  S0 extracted commitments: 2 (coverage: 100.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         PARSER_NO_INSTRUCTIONS

STUDY-029  NATURAL GAS SERVICES GROUP INC  (NGS) (C
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-030  FS Investment Corp II (CIK 0001525759)  
  has ground truth:         no (source: CMP)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    1
  semantic-mapped instr:    0
  UNRESOLVED instr:         1
  incorrect auto mutations: 0
  chain authoritative?      no
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

STUDY-031  OLIN Corp  (OLN) (CIK 0000074303)       
  has ground truth:         no (source: none)
  extraction status:        s0_failure
  S0 extracted commitments: 0 (coverage: 0.0%)
  GT extracted commitments: 0 (coverage: 0.0%)
  parser-detected instr:    0
  semantic-mapped instr:    0
  UNRESOLVED instr:         0
  incorrect auto mutations: 0
  chain authoritative?      yes
  lineage complete?         yes
  final-state exact agree:  N/A
  supported-field agree:    N/A
  failure category:         S0_EXTRACTION_FAILURE

```

## Aggregate Metrics

```text
Total chains:                      25
Total amendments:                  80
Total parser instructions:         91
Total semantic-mapped:             6
Total UNRESOLVED:                  85
Total incorrect mutations:         3

Primary study metrics:

  Semantic mapping precision:        50.0%
  Semantic mapping coverage:         6.6%
  Incorrect automatic mutation rate: 50.0%
  UNRESOLVED rate:                   93.4%
  Chain-level exact reconstruction:  40.0%
  Lineage completeness rate:         92.0%
  False authoritative promotion rate: 0.0%
  False authoritative promotion count: 0

Extraction metrics (new chains only):

  S0 extraction success rate:        54.5%
  GT extraction success rate:        40.0%
  S0 extraction coverage (avg):      40.3%
  GT extraction coverage (avg):      25.0%
```

## Safety Check

> **False authoritative promotion rate should remain 0.**

**PASS** — False authoritative promotion rate is 0.

## Failure Taxonomy

> Extractor failures (S0_EXTRACTION_FAILURE, GT_EXTRACTION_FAILURE)
> are distinct from reconstruction failures. A chain classified as
> an extractor failure did not reach the reconstruction measurement
> loop — the failure is in the extractor, not in Upsilon.

| Category | Count | Description |
|---|---|---|
| S0_EXTRACTION_FAILURE | 10 | S0 document exists but extractor returned 0 commitments. Reconstruction had no origin state — any downstream result is meaningless, not a reconstruction failure. |
| PARSER_NO_INSTRUCTIONS | 6 | Parser found 0 instructions across all amendments (unsupported format). |
| SYSTEM_INGESTION_PASS | 3 | System behaved correctly (no false promotion, no incorrect mutations) but reconstruction incomplete.  The system safely marked unsupported instructions as UNRESOLVED and did not falsely promote to authoritative. |
| MULTIPLE_FAILURES | 3 | Multiple failure categories apply. |
| GT_EXTRACTION_FAILURE | 2 | CMP document exists but GT extractor returned 0 commitments. Cannot measure reconstruction accuracy — this is an extractor limitation, not a reconstruction failure. |
| SUCCESS | 1 | Chain reconstructed end-to-end with 100% state agreement. |

### Final-State Mismatch Attribution

> Chains with final-state mismatches where extraction was
> incomplete could have extraction-error contribution, not just
> reconstruction error. The extraction_status column flags these.

| Chain | Category | Extraction Status | S0 VQ | GT VQ | Note |
|---|---|---|---|---|---|
| EDGAR-BAUSCH-LOMB | PARSER_NO_INSTRUCTIONS | n/a | 0 | 0 | Extraction OK — mismatch is reconstruction error |
| STUDY-015 | MULTIPLE_FAILURES | s0_and_gt_incomplete | 7 | 2 | Both S0 and GT incomplete |
| STUDY-022 | MULTIPLE_FAILURES | gt_incomplete | 0 | 2 | GT incomplete — ground truth may be missing commitments |

## Extraction Detail

### S0 Extraction (new chains)

| Chain | S0 chars | Commitments | Validation Queue | Coverage |
|---|---|---|---|---|
| STUDY-004 | 221271 | 0 | 0 | 0.0% |
| STUDY-005 | 317130 | 2 | 1 | 66.7% |
| STUDY-006 | 6848 | 0 | 0 | 0.0% |
| STUDY-007 | 432224 | 2 | 1 | 66.7% |
| STUDY-008 | 40907 | 0 | 0 | 0.0% |
| STUDY-010 | 293460 | 1 | 1 | 50.0% |
| STUDY-012 | 14219 | 0 | 0 | 0.0% |
| STUDY-013 | 269634 | 1 | 1 | 50.0% |
| STUDY-014 | 92823 | 0 | 0 | 0.0% |
| STUDY-015 | 275233 | 4 | 7 | 36.4% |
| STUDY-016 | 333628 | 3 | 0 | 100.0% |
| STUDY-017 | 396787 | 2 | 0 | 100.0% |
| STUDY-018 | 479379 | 3 | 1 | 75.0% |
| STUDY-020 | 279069 | 0 | 0 | 0.0% |
| STUDY-021 | 167031 | 0 | 0 | 0.0% |
| STUDY-022 | 322908 | 2 | 0 | 100.0% |
| STUDY-026 | 351682 | 3 | 1 | 75.0% |
| STUDY-027 | 457646 | 2 | 1 | 66.7% |
| STUDY-028 | 438166 | 2 | 0 | 100.0% |
| STUDY-029 | 187297 | 0 | 0 | 0.0% |
| STUDY-030 | 25632 | 0 | 0 | 0.0% |
| STUDY-031 | 403481 | 0 | 0 | 0.0% |

### GT Extraction (chains with CMP document)

| Chain | CMP chars | Commitments | Validation Queue | Coverage |
|---|---|---|---|---|
| STUDY-015 | 373594 | 6 | 2 | 75.0% |
| STUDY-016 | 18910 | 0 | 0 | 0.0% |
| STUDY-018 | 230987 | 0 | 0 | 0.0% |
| STUDY-022 | 455230 | 2 | 2 | 50.0% |
| STUDY-030 | 660112 | 0 | 2 | 0.0% |

## Conclusion

```text
Across real amendment chains, how often can Upsilon reconstruct
authoritative commitment state correctly, and where does the
current architecture stop?
```

- **Safety**: False authoritative promotion rate is
  0.0% (0 violations).

- **S0 extraction**: 12/22 new chains
  had at least 1 commitment extracted from S0. Average coverage:
  40.3%.

- **GT extraction**: 2/5
  chains with CMP documents had at least 1 commitment extracted.
  Average coverage: 25.0%.

- **Reconstruction accuracy**: 40.0% for chains with ground truth.
