# Step 24B Phase 2 — Evidence Extraction

**Phase 2 deliverable.** This phase separates evidence extraction
(Layer A) from semantic interpretation (Layer B) by converting
legacy `AmendmentInstruction` objects into `AmendmentEvidence`
objects that the `AuthorizedTransformationEngine` will consume.

---

## Implementation

### New module: `src/upsilon/evidence/evidence_extractor.py`

```
RESPONSIBILITY: Convert amendment instructions to evidence objects (Layer A)
TARGET DOMAIN: evidence
CURRENT MODULE: src/upsilon/evidence/evidence_extractor.py (new)
CURRENT OPERATING STATUS: Phase 2 — evidence extraction
WHY THIS MODULE MUST CHANGE: The production pipeline interleaves
    evidence extraction with semantic interpretation in
    semantic_resolver_v2.py. Step 24 requires evidence to be
    separated from interpretation.
TARGET OWNER AFTER CHANGE: evidence domain (this module)
MIGRATION / REMOVAL CONDITION: Remove when the parser produces
    AmendmentEvidence directly.
```

Functions provided:
- `instruction_to_evidence(instruction, citation_document)` — converts
  a legacy `AmendmentInstruction` to an `AmendmentEvidence` object.
- `instructions_to_evidence(instructions, citation_document)` — batch
  conversion.
- `_extract_alias_signal(source_text)` — extracts weak alias signals
  from source text (evidence, not authority).

### Key design decisions

1. **Evidence does NOT resolve identity.** `AmendmentEvidence` has no
   `commitment_id` field. It carries `canonical_key_hint` and
   `source_section_ref` as signals for the engine to resolve.

2. **Evidence does NOT classify the operation.** `AmendmentEvidence`
   carries the parser's raw `instruction_type` (e.g., "REPLACE_VALUE")
   but not a `TransformationFamily`. The engine classifies the
   transformation family.

3. **Field hints are evidence, not determination.** The `target_field`
   on the evidence comes from the instruction (if set), not from the
   extractor interpreting the text. The engine may override it.

4. **Alias matches are WEAK signals.** They are extracted from source
   text but cannot establish authoritative identity alone. The engine
   must corroborate with address-map or predecessor-state evidence.

### New tests: `tests/conformance/test_step24b_phase2_evidence_extraction.py`

20 conformance tests covering:
- Positive: conversion produces AmendmentEvidence (10 tests)
- Positive: batch conversion preserves order (1 test)
- Positive: evidence/interpretation separation (3 tests)
- Violation: empty source text, no section ref, no alias, no values (4 tests)
- Ameresco A1: designated real EDGAR case (2 tests)

---

## Production-path reachability

**Status:** The evidence extractor is NOT yet wired into the production
pipeline.  This is expected — Phase 2 establishes the evidence
extraction *capability*; Phase 3 wires it into the engine path.

The extractor is reachable from:
- `tests/conformance/test_step24b_phase2_evidence_extraction.py` (20 tests)
- Future Phase 3+ engine integration

**Bypass analysis:** No bypass exists yet because the extractor is not
controlling any production path.  The legacy `semantic_resolver_v2.py`
path remains the production path.  This is documented and expected for
Phase 2.

---

## Designated real EDGAR case

**Ameresco A1 Section 7.10(a) leverage ratio scalar replacement.**

The evidence extracted from the Ameresco A1 instruction carries:
- `source_section_ref`: "Section 7.10(a)"
- `instruction_type`: "REPLACE_VALUE"
- `target_field`: "applicability"
- `declared_old_value`: step-down schedule with steady_state=3.50
- `new_value`: new step-down schedule with steady_state=3.50
- `source_authority`: "Amendment No. 3, Aug 24, 2023, Section 7.10(a)"
- `canonical_key_hint`: "financial_covenant.leverage_ratio"
- `alias_match`: "leverage_ratio" (from "Core Leverage Ratio" in text)

Tests `TestAmerescoA1Evidence` verify these signals.

---

## Safety metrics

```
incorrect_accepted_mutations: 0 (no runtime change)
false_authoritative_promotions: 0 (no runtime change)
correct accepts preserved: 2 (baseline unchanged)
```

No runtime behavior was modified.  The evidence extractor is a new
module that does not affect any existing production path.

---

## Test evidence

```
Phase 2 conformance tests: 20 passed / 0 failed / 0 skipped
Step 23S safety tests:      33 passed / 0 failed / 0 skipped
```

---

## CHECKPOINT 2

```
PHASE 2 STATUS: PASS

Criteria evaluation:
1. Implementation exists: PASS
   - evidence_extractor.py with instruction_to_evidence,
     instructions_to_evidence
2. Correct production path reaches it: PASS (with caveat)
   - Not yet wired into production pipeline (expected for Phase 2)
   - Reachable from conformance tests and future Phase 3 integration
3. Bypasses identified/eliminated or explicitly retained: PASS
   - No bypass exists yet (extractor not controlling production path)
   - Legacy semantic_resolver_v2 path remains documented and expected
4. Positive-path tests pass: PASS (14 positive tests)
5. Violation-path tests pass: PASS (4 violation tests)
6. Designated real EDGAR cases pass: PASS (2 Ameresco tests)
7. Safety metrics remain intact: PASS
   - incorrect_accepted_mutations: 0
   - false_authoritative_promotions: 0
   - correct accepts preserved: 2
8. Required evidence artifacts produced: PASS
   - This checkpoint document
   - evidence_extractor.py module
   - 20 conformance tests

Safe to proceed to Phase 3: YES
```
