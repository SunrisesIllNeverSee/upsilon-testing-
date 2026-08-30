# Changelog

All notable changes to the Upsilon Financial Commitment Integrity system are
documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.4] — 2026-08-30

### Changed
- **Generalized reference targets**: `Section` → `Section|Article|Schedule|
  Exhibit|Definition|Clause|Paragraph|Subsection`. The parser now matches
  amendment instructions targeting Articles and Schedules, not just Sections.
- **Broadened replace pattern**: `deleting...replacing` → `deleting...(replacing|
  inserting|substituting)`. Handles "deleting the single instance of X and
  inserting Y in lieu thereof" and "deleting...substituting in its place".
- **New "amended to read" pattern**: "Section X is amended to read as follows"
  mapped to RESTATE_SECTION.
- **New "amended as follows" pattern**: "Section X is hereby amended as follows"
  mapped to RESTATE_SECTION.
- **New "deleted from Section" pattern**: "is hereby deleted from Section X"
  mapped to DELETE_COMMITMENT.
- **Broadened "amended by"**: `amended by adding` → `amended by (adding|inserting|
  deleting|modifying)`.
- **Bounded gaps**: Gap between target and verb bounded to 60-200 chars depending
  on pattern to avoid matching section headings.

### Architecture
- **Separated transformation type from domain effect**: `InstructionType`
  describes how the legal document transformed (REPLACE_VALUE, RESTATE_SECTION,
  etc.). New `DomainEffect` enum describes what changed in the commitment
  domain (commitment_amount_change, covenant_threshold_change, etc.).
- **Moved `COMMITMENT_AMOUNT_CHANGE`** from `InstructionType` to `DomainEffect`.
  It describes what changed, not how the document transformed.
- **`FIND_REPLACE_REFERENCE`** remains in `InstructionType` (describes the
  transformation operation: global find-and-replace of defined terms).
- **`AmendmentInstruction.domain_effect`** field added (Optional[DomainEffect]).

### Performance (25-document parser-development sample)
| Metric | v0.3.1 | v0.4 |
|---|---:|---:|
| Precision | 1.000 | 0.950 |
| Recall | 0.138 | 0.844 |
| F1 | 0.243 | 0.894 |
| False positives | 0 | 4 |
| False negatives | 81 | 14 |

### Added
- `test_parser_v04_regression.py`: 14 regression tests from real development
  corpus patterns. All 14 failed on v0.3.1, all pass on v0.4.
- `DomainEffect` enum in `models.py`.

### Fixed
- **Dataset labeling**: "25-issuer development corpus" → "25-document
  parser-development sample" (one document per issuer, NOT the agreement-chain
  corpus).
- **Table 2 inconsistency**: separated per-format rows from pooled total,
  renamed pooled row to "All amendment documents".

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
