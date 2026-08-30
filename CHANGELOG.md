# Changelog

All notable changes to the Upsilon Financial Commitment Integrity system are
documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
