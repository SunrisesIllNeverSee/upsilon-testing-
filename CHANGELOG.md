# Changelog

All notable changes to the Upsilon Financial Commitment Integrity system are
documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.4.1] — 2026-08-30

### Changed
- **Generic ADD/DELETE instruction types**: Parser now emits generic `ADD` and
  `DELETE` instead of `ADD_COMMITMENT` and `DELETE_COMMITMENT`. Commitment-level
  resolution (ADD → ADD_COMMITMENT, DELETE → DELETE_COMMITMENT) happens
  downstream in the executor, not in the parser. This separates the legal
  transformation operation from the domain-level commitment effect.
- **"amended by modifying" emits UNRESOLVED**: The parser cannot classify
  "modifying" as ADD or DELETE, so it emits `UNRESOLVED` for downstream
  validation.
- **Gold annotations updated to generic types**: All gold annotations now use
  `ADD`/`DELETE` instead of `ADD_COMMITMENT`/`DELETE_COMMITMENT`.
- **Gold annotations have IDs and source spans**: Each annotation has a unique
  `id` (e.g., `DEV-007-001`) and a `source_span` `[start, end]` pointing to
  the instruction text in the source document.
- **Span-based matching**: `match_instructions_to_gold` now uses span overlap
  + instruction_type for matching, with key-based fallback for gold without
  spans. This is more precise than key-only matching.
- **Semantic scoring**: Each match includes `span_iou`, `old_value_match`, and
  `new_value_match` fields in the classification results.
- **No confidence on raw hits**: Parser no longer sets `confidence=1.0` on raw
  deterministic regex hits. Confidence should be set by downstream semantic
  validation, not by the regex match itself.
- **ExecutionStatus enum**: `ExecutionResult` now has a `status` field:
  `COMPLETE` (all applied), `PARTIAL` (some applied, some unresolved),
  `UNRESOLVED` (all failed). PARTIAL/UNRESOLVED executions must not be
  promoted to authoritative state.
- **Parser label**: `deterministic_baseline_v0.4.1`.

### Instruction-detection performance (25-document parser-development sample, gold annotations, span-based matching)
| Metric | v0.3.1 | v0.4.1 |
|---|---:|---:|
| Gold annotations | 77 | 77 |
| Detected | 13 | 44 |
| True positives | 7 | 41 |
| False positives | 6 | 3 |
| False negatives | 70 | 36 |
| Precision | 0.538 | 0.932 |
| Recall | 0.091 | 0.532 |
| F1 | 0.156 | 0.678 |
| Unresolved | 0 | 0 |

Note: v0.3.1 baseline metrics dropped because gold annotations now use generic
ADD/DELETE types while v0.3.1 still emits ADD_COMMITMENT/DELETE_COMMITMENT.
The v0.3.1 parser is frozen as the historical baseline.

### Added
- test_semantic_regression.py: 21 exact semantic regression tests covering
  generic ADD/DELETE emission, source spans, old/new value extraction,
  no-confidence verification, gold annotation structure, span-based matching,
  and execution status.
- ExecutionStatus tests in test_executor.py (COMPLETE/PARTIAL/UNRESOLVED).
- MODIFIED_BY_V04 regex for "amended by modifying" → UNRESOLVED.

### Held-out protocol
Not altered. Development corpus changes only. No held-out files created or modified.

## [0.4] — 2026-08-30

### Changed
- **Generalized reference targets**: Section to Section|Article|Schedule|
  Exhibit. The parser now matches amendment instructions targeting Articles,
  Schedules, and Exhibits, not just Sections. Lowercase structural terms
  (Definition, Clause, Paragraph, Subsection) are intentionally excluded
  because they appear as common nouns in amendment text and cause false
  positives. In the current 25-document development sample, restricting
  primary targets to Section/Article/Schedule/Exhibit reduced false
  positives; finer-grained targets remain future work.
- **Broadened replace pattern**: deleting...replacing to deleting...(replacing|
  inserting|substituting). Handles deleting the single instance of X and
  inserting Y in lieu thereof and deleting...substituting in its place.
- **New amended to read pattern**: Section X is amended to read as follows
  mapped to RESTATE_SECTION.
- **amended as follows is a container, not an instruction**: Section X of
  the Credit Agreement is hereby amended as follows is a STRUCTURAL/CONTAINER
  MARKER. The parser does NOT emit RESTATE_SECTION for it. Child operations
  beneath it (detected by ADD_V04, DELETE_BY_V04, REPLACE_V04,
  DELETED_FROM_V04, AMENDED_TO_READ_V04) are the actual instructions.
  Requires of the Credit Agreement to exclude amendment section headings
  (Section 2 hereof).
- **New deleted from Section pattern**: is hereby deleted from Section X
  mapped to DELETE_COMMITMENT.
- **Broadened amended by**: amended by adding to amended by (adding|inserting|
  modifying). amended by deleting mapped to DELETE_COMMITMENT (not ADD).
- **Bounded gaps**: Gap between target and verb bounded to 60-200 chars
  depending on pattern to avoid matching section headings.
- **Overlap deduplication**: When REPLACE_V04 and ADD_V04/DELETE_BY_V04 match
  the same text span, only the more specific match (REPLACE_TEXT) is kept.
- **REPLACE_V04 requires amended by**: Prevents matching cross-references
  followed by deleting in a different instruction.

### Architecture
- **Separated transformation type from domain effect**: InstructionType
  describes how the legal document transformed (REPLACE_VALUE, ADD, DELETE,
  RESTATE_SECTION, etc.). DomainEffect describes what changed in the
  commitment domain (commitment_amount_change, covenant_threshold_change, etc.).
- **Removed domain-effect members from InstructionType**: ADD_EXCEPTION,
  REMOVE_EXCEPTION, EXTEND_DEADLINE, CHANGE_FREQUENCY, CHANGE_PARTY,
  MODIFY_SCOPE have been removed. Their semantics are now expressed as
  DomainEffect values (EXCEPTION_EXPANSION, EXCEPTION_REMOVAL,
  DEADLINE_CHANGE, FREQUENCY_CHANGE, PARTY_CHANGE, SCOPE_CHANGE).
- **Added ADD and DELETE to InstructionType**: Generic transformation
  operations that, combined with domain_effect, replace the removed
  domain-specific instruction types.
- **Executor uses domain_effect for field selection**: When
  InstructionType.REPLACE_VALUE is used with DomainEffect.DEADLINE_CHANGE,
  the executor applies the change to the deadline field. Similarly,
  InstructionType.ADD with DomainEffect.EXCEPTION_EXPANSION adds to the
  exceptions list.
- **FIND_REPLACE_REFERENCE** remains in InstructionType (describes the
  transformation operation: global find-and-replace of defined terms).
- **AmendmentInstruction.domain_effect** field (Optional[DomainEffect]).

### Parser API
- **parse_v03()** preserved as the v0.3.1 baseline (uses v0.3 regexes,
  Section-only targets, no deduplication). Returns
  parser: deterministic_baseline_v0.3.
- **parse_v04()** added as the v0.4 parser (uses v0.4 regexes, generalized
  targets, deduplication). Returns parser: deterministic_baseline_v0.4.
- **parse()** preserved as the v0.2 parser for backward compatibility.
- **CLI**: amendment_parser.py defaults to v0.4. Use --v3 for v0.3.1
  baseline, --v2 for v0.2.

### Evaluation methodology
- **Gold annotations**: Explicit, reviewed, non-overlapping annotations in
  data/development/gold_annotations.json (77 total across 25 documents).
  Replaces the previous overlapping-regex-count method for expected instructions.
- **False positive estimation**: No longer estimated from parser version
  differences. FP/FN computed from gold annotation matching.
- **Matching**: Detected instructions matched to gold annotations by
  (normalized target_ref, instruction_type). Each gold annotation matched
  at most once.
- **Metric type**: Instruction DETECTION only. Matching does NOT verify
  extracted old_value, new_value, amount, exception, or actual semantic
  mutation correctness. Full reconstruction accuracy is a separate
  measurement.
- **Container phrases**: "amended as follows" is NOT annotated as a separate
  instruction when sub-instructions follow; only the actual child operations
  (add/delete/restate/replace) are annotated.

### Instruction-detection performance (25-document parser-development sample, gold annotations)
| Metric | v0.3.1 | v0.4 |
|---|---:|---:|
| Gold annotations | 77 | 77 |
| Detected | 13 | 44 |
| True positives | 11 | 36 |
| False positives | 2 | 8 |
| False negatives | 66 | 41 |
| Precision | 0.846 | 0.818 |
| Recall | 0.143 | 0.468 |
| F1 | 0.244 | 0.595 |
| Unresolved | 0 | 0 |

### Added
- test_parser_v04_regression.py: 36 regression tests with semantic assertions
  (exact instruction type, target reference, FP regression tests). All pass
  on v0.4; v0.3.1 baseline tests confirm v0.3 does NOT detect v0.4 patterns.
- data/development/gold_annotations.json: Gold annotations for the 25-document
  parser-development sample.
- research/DEVELOPMENT_CENSUS_v0.4.md: v0.4 census report.
- research/DEVELOPMENT_CENSUS_comparison.md: v0.3.1 vs v0.4 comparison.
- DomainEffect enum in models.py.
- ADD and DELETE instruction types in models.py.

### Fixed
- **Dataset labeling**: 25-issuer development corpus to 25-document
  parser-development sample (one document per issuer, NOT the agreement-chain
  corpus).
- **Table 2 inconsistency**: separated per-format rows from pooled total,
  renamed pooled row to All amendment documents.
- **Amended by deleting mapping**: was mapped to ADD_COMMITMENT, now
  correctly mapped to DELETE_COMMITMENT.
- **Amended as follows false positives**: Section X hereof (amendment
  section heading) no longer matched as target.
- **Cross-reference false positives**: REPLACE_V04 no longer matches
  cross-references followed by deleting in a different instruction.
- **Overlap double-counting**: REPLACE_V04 and ADD_V04 no longer both emit
  instructions for the same amended by deleting...inserting text.
- **Baseline artifact overwrite**: produce_census_tables.py no longer
  overwrites DEVELOPMENT_CENSUS_v0.3.1.md with v0.4 results. Generates
  separate versioned reports.
- **Schema drift**: schema.sql instruction_type enum updated to match
  models.py (removed MODIFY_SCOPE, ADD_EXCEPTION, REMOVE_EXCEPTION,
  EXTEND_DEADLINE, CHANGE_FREQUENCY, CHANGE_PARTY; added ADD, DELETE,
  FIND_REPLACE_REFERENCE). Added domain_effect enum and
  amendment_instruction.domain_effect column.
- **Executor dead code**: removed unreachable ADD_COMMITMENT and
  DELETE_COMMITMENT branches from the generic ADD/DELETE handler blocks.
  ADD_COMMITMENT is handled before the target_key guard; DELETE_COMMITMENT
  is handled before the ADD/DELETE branches.
- **Generic ADD with dict payload**: ADD with a dict new_value now creates
  a new commitment (mirroring ADD_COMMITMENT), no longer blocked by the
  target_key guard. Previously the dict-payload branch was unreachable.
- **persistence.py _edge_type**: added DELETE to the SUPERSEDES mapping
  so generic DELETE instructions produce correct lineage edges.
- **Documentation drift**: README.md and AMENDMENT_INSTRUCTION_GRAMMAR.md
  updated to reflect the v0.4 instruction type / domain effect separation.

## [Unreleased] — 25-document parser-development sample

### Added
- **`build_development_corpus.py`**: EDGAR full-text search pipeline that
  searches for 8-K filings containing "amendment to credit agreement" across
  4 date ranges (2020-2026), selects 25 unique issuers (excluding smoke cases),
  fetches filing index pages, finds EX-10.1 exhibits, and downloads documents
  with HTML-to-text conversion and SHA-256 hashing.
- **`classify_development_corpus.py`**: heuristic format classifier that runs
  v0.3.1 parser across all 25 documents and classifies each into formats A-G
  (inline, amendment+composite, amended&restated, redline, definition-heavy,
  waiver-only, mixed/other). Captures all required fields: issuer, accession,
  amendment number, document format, composite present, instruction count,
  instruction classes, UNRESOLVED count, false positives, false negatives,
  parser coverage.
- **25-document parser-development sample** in `data/development/DEV-001`
  through `DEV-025/`, each with `source.html`, `source.txt`, and
  `source_meta.json`. NOTE: This is one document per issuer, NOT the
  25-issuer agreement-chain corpus (original + multiple amendments per
  issuer) that the reconstruction study ultimately requires.
- **`development_corpus.csv`**: classification results for all 25 documents.
- **`data/development/manifest.json`**: acquisition metadata.
- **`data/development/classification_results.json`**: JSON classification results.
- **Run record**: `research/run_records/20260830T033000Z_dev_corpus_acquisition.json`.

### Key findings
- **Format distribution**: A=80%, F=4%, G=16%, B/D=0% (no composite targets)
- **Composite format prevalence**: 0/25 (0%) — the Annex A composite format
  from the smoke test is NOT the dominant pattern in the general population
- **Parser coverage**: 44.8% average — the parser misses more than half of
  real amendment instructions due to narrow regex patterns
- **Primary coverage gaps**: parser only matches `Section X` (not
  `Article`/`Schedule`/`Exhibit`), only matches `amended by adding/deleting`
  (not `amended as follows` or `amended to read`), only matches
  `deleting...replacing` (not `deleting...inserting`)
- **Acquisition quality**: 2/25 (8%) documents are non-credit-agreement
  exhibits (wrong EX-10.1)

## [0.3.1] — 2026-08-30

### Fixed
- **Removed `COMPOSITE_RESTATEMENT` from `InstructionType` enum**. The
  composite agreement is ground truth, not an amendment instruction. Having
  it as an `InstructionType` would contaminate instruction precision/recall
  metrics by counting "we found the composite" as "we found an amendment
  instruction."
- **Added `CompositeTarget` Pydantic model** to `models.py`. This is a
  ground-truth document object with `annex`, `start_offset`, `end_offset`,
  and `source_format` fields. It lives outside the instruction pipeline:
  ```
  AMENDMENT BODY → AmendmentInstruction[]
  ANNEX A / COMPOSITE → CompositeTarget (ground truth)
  ```
- **Removed `COMPOSITE_RESTATEMENT_RX` and `COMPOSITE_NAMED_RX`** from
  instruction extraction specs. The composite detection is handled solely
  by `detect_composite()`, which returns a `CompositeTarget`-shaped dict.
- **Renamed `composite_ground_truth` key to `composite_target`** in
  `parse_v03()` result for consistency with the model name.
- **Removed `present` field** from composite detection result. The
  `CompositeTarget` is either present (non-None) or absent (None) — no
  boolean flag needed.

### Added
- **3 architecture-separation tests** in `TestCompositeTargetIsNotInstruction`:
  - `test_composite_not_in_instructions`: no instruction has type
    `COMPOSITE_RESTATEMENT`
  - `test_composite_target_is_separate_object`: composite target is a
    separate dict with `annex`, `start_offset`, `end_offset`,
    `source_format`
  - `test_no_instruction_type_enum_has_composite`: the `InstructionType`
    enum does not contain `COMPOSITE_RESTATEMENT`
- **2 smoke-case architecture tests**: `test_no_composite_in_instructions`
  for both SW-001 and DKS-001.

### Results
- SW-001: 0 instructions (was 1 with COMPOSITE_RESTATEMENT), composite
  target detected as separate object
- DKS-001: 0 instructions (was 1 with COMPOSITE_RESTATEMENT), composite
  target detected as separate object
- Full test suite: 45 passed (was 41)

## [0.3.0] — 2026-08-30

### Added
- **Document segmentation** (`segment_document()`): divides a filing into
  AMENDMENT_BODY, SIGNATURES, COMPOSITE_AGREEMENT, and OTHER segments using
  structural markers (NOW THEREFORE, SIGNATURE PAGES FOLLOW, IN WITNESS
  WHEREOF, ANNEX A ... CREDIT AGREEMENT).
- **Composite ground-truth detection** (`detect_composite()`): identifies
  Annex A composite/conformed agreements as document-level objects with
  annex letter and offset range. This is a validation target, not an
  amendment instruction.
- **`parse_v03()` function**: structure-aware parser that extracts
  instructions only from the amendment body segment, returns segments,
  composite target, and instructions in a single result dict.
- **23 regression tests** (`test_parser_v03.py`) encoding the v0.2 smoke-test
  failure modes: Annex A exclusion, waiver false positives, span bounding,
  composite detection, and real smoke-case regression.
- **`--v2` CLI flag** on `amendment_parser.py` for backward-compatible v0.2
  parsing (regression comparison).

### Changed
- **Waiver regex tightened**: `WAIVER_V03` requires imperative amendment
  language (`Section X is hereby waived` or `Section X is waived`), excludes
  cross-reference contexts (`waived in accordance with`, `has been waived`).
  v0.2's `WAIVER` regex matched any occurrence of "waived" in body text.
- **Instruction regexes bounded**: `REPLACE_V03`, `DELETE_V03`, `RESTATE_V03`,
  `ADD_V03` use `[^\n]{0,200}?` gap limit instead of `.*?` with `re.S`,
  preventing unbounded spans across the entire document.
- **`nearby_v03()` context window**: reduced from 450 to 500 chars radius
  with hard cap, ensuring no instruction source_text exceeds 1000 chars.
- **CLI default**: `amendment_parser.py` now uses v0.3 by default. Use
  `--v2` for the legacy parser.

### Fixed
- **WAIVE_TEMPORARILY false positives** (11 in SW-001, 8 in DKS-001):
  eliminated by segmentation (instructions only from amendment body) and
  tightened waiver regex (imperative language required).
- **Unbounded RESTATE_SECTION spans** (41K chars in SW-001): fixed by
  bounded regex and 500-char context window.
- **Composite agreement treated as instruction source**: fixed by document
  segmentation. The composite agreement is now a ground-truth target, not
  an instruction source.

### Performance
- SW-001: 12 instructions → 1 instruction (91.7% reduction, 100% false
  positive elimination)
- DKS-001: 9 instructions → 1 instruction (88.9% reduction, 100% false
  positive elimination)
- Test suite: 18 → 41 tests, all passing

## [0.2.0] — 2026-08-29

### Initial release
- Deterministic baseline parser with regex patterns for REPLACE_TEXT,
  DELETE_SECTION, RESTATE_SECTION, WAIVE_TEMPORARILY, ADD_COMMITMENT.
- In-memory deterministic amendment executor with prior-state guards.
- PostgreSQL temporal persistence schema and bridge.
- Prospective research protocol: preregistration, smoke-test protocol,
  annotation guide, results template, reproducibility checklist.
- Protocol freeze mechanism (`freeze_study.py`) with SHA-256 hashing.
- SEC document acquisition (`download_smoke_cases.py`) with EDGAR download,
  text extraction, and metadata hashing.
- Run provenance recording (`record_run.py`) with git state, pip freeze,
  protocol lock, and input/output hashes.
- 18 unit/integration tests.
