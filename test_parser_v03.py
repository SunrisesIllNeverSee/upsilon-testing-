"""Regression tests for parser v0.3 — document segmentation, composite
detection, bounded instruction extraction, and tightened waiver regex.

These tests encode the specific failure modes found in the v0.2 smoke-test
baseline (see research/LAB_NOTEBOOK.md Entry 005) and assert that v0.3 fixes
them.
"""
from __future__ import annotations
from pathlib import Path

import pytest

from amendment_parser import segment_document, detect_composite, parse, parse_v03

# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

AMENDMENT_BODY_WITH_REAL_WAIVER = """\
NOW, THEREFORE, the parties agree as follows:
1. Amendments. Section 6.11(a) is amended by deleting "4.00 to 1.00" and
replacing it with "5.00 to 1.00".
2. Waiver. Compliance with Section 6.11(a) is hereby waived for the fiscal
quarter ending June 30, 2026.
3. Restatement. Section 6.13 is hereby amended and restated in its entirety
to read as follows: "New text here."
"""

AMENDMENT_BODY_WITH_CROSS_REF_WAIVED = """\
NOW, THEREFORE, the parties agree as follows:
1. The Administrative Agent shall have received evidence that the conditions
in Section 4.01 are satisfied or waived in accordance with Section 10.01.
2. Events for which the 30 day notice period has been waived under ERISA
Section 4043(c).
"""

COMPOSITE_AGREEMENT_BODY = """\
ANNEX A
AMENDED AND RESTATED CREDIT AGREEMENT

"Effective Date" means the first date all conditions precedent in Section 4.01
are satisfied or waived in accordance with Section 10.01.

"Reportable Event" means any event set forth in Section 4043(c) of ERISA,
other than events for which the 30 day notice period has been waived.

"Reports" has the meaning specified in Section 9.12(b).

Section headings herein are for convenience of reference only.
"""

FULL_FILING_WITH_ANNEX_A = """\
EXHIBIT 10.1 FOURTH AMENDMENT TO CREDIT AGREEMENT

WHEREAS, the parties desire to amend the Credit Agreement.

NOW, THEREFORE, the parties agree as follows:
1. Amendments to Credit Agreement.
(a) Composite Credit Agreement. The Credit Agreement is hereby amended to
delete the bold, stricken text and to add the bold, double-underlined text
as set forth in the pages of the Credit Agreement attached as Annex A hereto.
(b) Schedules. The Schedules to the Credit Agreement are hereby deleted in
their entirety and the Schedules attached to Annex A hereto are substituted
in their stead.
2. Ratification. All terms remain in full force and effect.

[signature pages follow]

IN WITNESS WHEREOF, the parties have caused this Amendment to be executed.

DICK'S SPORTING GOODS, INC.
By: John Doe, Vice President

ANNEX A
AMENDED AND RESTATED CREDIT AGREEMENT
Dated as of August 12, 2015

ARTICLE I DEFINITIONS AND ACCOUNTING TERMS

"Effective Date" means the first date all conditions precedent in Section 4.01
are satisfied or waived in accordance with Section 10.01.

"Reportable Event" means any event set forth in Section 4043(c) of ERISA,
other than events for which the 30 day notice period has been waived.
"""

FULL_FILING_NO_ANNEX = """\
EXHIBIT 10.1 AMENDMENT TO CREDIT AGREEMENT

WHEREAS, the parties desire to amend.

NOW, THEREFORE, the parties agree as follows:
1. Section 6.11(a) is amended by deleting "4.00 to 1.00" and replacing it
with "5.00 to 1.00".
2. Compliance with Section 6.11(a) is hereby waived for the quarter ending
June 30, 2026.

[signature pages follow]

IN WITNESS WHEREOF, the parties have caused this Amendment to be executed.
"""


# ---------------------------------------------------------------------------
# Document segmentation tests
# ---------------------------------------------------------------------------

class TestSegmentDocument:
    def test_segments_include_amendment_body(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        assert "amendment_body" in seg
        assert seg["amendment_body"]["start"] >= 0
        assert seg["amendment_body"]["end"] > seg["amendment_body"]["start"]

    def test_segments_include_composite_agreement(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        assert "composite_agreement" in seg
        assert seg["composite_agreement"] is not None
        assert seg["composite_agreement"]["start"] > seg["amendment_body"]["end"]

    def test_filing_without_annex_has_no_composite_segment(self):
        seg = segment_document(FULL_FILING_NO_ANNEX)
        assert seg["composite_agreement"] is None

    def test_amendment_body_starts_at_now_therefore(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        body_text = FULL_FILING_WITH_ANNEX_A[seg["amendment_body"]["start"]:seg["amendment_body"]["end"]]
        assert "NOW, THEREFORE" in body_text

    def test_amendment_body_ends_before_signatures(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        body_text = FULL_FILING_WITH_ANNEX_A[seg["amendment_body"]["start"]:seg["amendment_body"]["end"]]
        assert "IN WITNESS WHEREOF" not in body_text

    def test_composite_agreement_excludes_amendment_body(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        comp_text = FULL_FILING_WITH_ANNEX_A[seg["composite_agreement"]["start"]:seg["composite_agreement"]["end"]]
        assert "Composite Credit Agreement" not in comp_text or "ANNEX A" in comp_text[:20]
        assert "NOW, THEREFORE, the parties agree" not in comp_text


# ---------------------------------------------------------------------------
# Composite ground-truth detection tests
# ---------------------------------------------------------------------------

class TestCompositeDetection:
    def test_filing_with_annex_a_detected(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        comp = detect_composite(FULL_FILING_WITH_ANNEX_A, seg)
        assert comp is not None
        assert comp["annex"] == "A"
        assert comp["start_offset"] > 0
        assert comp["end_offset"] > comp["start_offset"]
        assert comp["source_format"] == "html_redline"

    def test_filing_without_annex_not_detected(self):
        seg = segment_document(FULL_FILING_NO_ANNEX)
        comp = detect_composite(FULL_FILING_NO_ANNEX, seg)
        assert comp is None

    def test_composite_offset_within_composite_segment(self):
        seg = segment_document(FULL_FILING_WITH_ANNEX_A)
        comp = detect_composite(FULL_FILING_WITH_ANNEX_A, seg)
        if comp:
            assert comp["start_offset"] >= seg["composite_agreement"]["start"]


# ---------------------------------------------------------------------------
# Waiver false-positive regression tests
# ---------------------------------------------------------------------------

class TestWaiverFalsePositives:
    def test_cross_reference_waived_does_not_emit_instruction(self):
        """'waived in accordance with Section 10.01' is a cross-reference,
        not a waiver instruction."""
        result = parse_v03(AMENDMENT_BODY_WITH_CROSS_REF_WAIVED)
        waivers = [i for i in result["instructions"] if i["instruction_type"] == "WAIVE_TEMPORARILY"]
        assert len(waivers) == 0

    def test_erisa_notice_period_waived_does_not_emit(self):
        """'notice period has been waived' in ERISA context is not a waiver
        instruction."""
        result = parse_v03(COMPOSITE_AGREEMENT_BODY)
        waivers = [i for i in result["instructions"] if i["instruction_type"] == "WAIVE_TEMPORARILY"]
        assert len(waivers) == 0

    def test_real_imperative_waiver_does_emit(self):
        """'Compliance with Section X is hereby waived' is a real waiver."""
        result = parse_v03(AMENDMENT_BODY_WITH_REAL_WAIVER)
        waivers = [i for i in result["instructions"] if i["instruction_type"] == "WAIVE_TEMPORARILY"]
        assert len(waivers) == 1
        assert "6.11" in waivers[0]["target_section_ref"]

    def test_composite_body_waivers_excluded_by_segmentation(self):
        """Even if the waiver regex would match, instructions from the
        composite agreement segment must not appear."""
        result = parse_v03(FULL_FILING_WITH_ANNEX_A)
        # All instructions should come from the amendment body, not the composite
        for inst in result["instructions"]:
            assert inst["source_start"] < result["segments"]["amendment_body"]["end"]


# ---------------------------------------------------------------------------
# Span bounding tests
# ---------------------------------------------------------------------------

class TestSpanBounding:
    def test_restate_section_span_is_bounded(self):
        """RESTATE_SECTION source_text must not span the entire document."""
        text = AMENDMENT_BODY_WITH_REAL_WAIVER
        result = parse_v03(text)
        restates = [i for i in result["instructions"] if i["instruction_type"] == "RESTATE_SECTION"]
        for r in restates:
            assert len(r["source_text"]) <= 1000, (
                f"RESTATE_SECTION span too large: {len(r['source_text'])} chars"
            )

    def test_instruction_source_text_is_bounded(self):
        """No instruction should have source_text longer than 1000 chars."""
        result = parse_v03(AMENDMENT_BODY_WITH_REAL_WAIVER)
        for inst in result["instructions"]:
            assert len(inst["source_text"]) <= 1000


# ---------------------------------------------------------------------------
# Annex A exclusion test
# ---------------------------------------------------------------------------

class TestAnnexAExclusion:
    def test_no_instructions_from_composite_agreement_text(self):
        """The composite agreement body contains many 'waived' and 'Section'
        references that must NOT produce instructions."""
        result = parse_v03(FULL_FILING_WITH_ANNEX_A)
        body_end = result["segments"]["amendment_body"]["end"]
        for inst in result["instructions"]:
            assert inst["source_start"] < body_end, (
                f"Instruction at offset {inst['source_start']} is outside "
                f"amendment body (ends at {body_end})"
            )


# ---------------------------------------------------------------------------
# Composite target is NOT an instruction (architecture separation test)
# ---------------------------------------------------------------------------

class TestCompositeTargetIsNotInstruction:
    def test_composite_not_in_instructions(self):
        """The composite agreement must NOT appear as an amendment
        instruction. It is a ground-truth document, not a mutation."""
        result = parse_v03(FULL_FILING_WITH_ANNEX_A)
        for inst in result["instructions"]:
            assert inst["instruction_type"] != "COMPOSITE_RESTATEMENT", (
                "COMPOSITE_RESTATEMENT must not be an InstructionType — "
                "the composite is ground truth, not an instruction"
            )

    def test_composite_target_is_separate_object(self):
        """The composite target should be a separate object in the result,
        not mixed into the instructions list."""
        result = parse_v03(FULL_FILING_WITH_ANNEX_A)
        assert result["composite_target"] is not None
        assert result["composite_target"]["annex"] == "A"
        assert "start_offset" in result["composite_target"]
        assert "end_offset" in result["composite_target"]
        assert "source_format" in result["composite_target"]

    def test_no_instruction_type_enum_has_composite(self):
        """The InstructionType enum must not contain COMPOSITE_RESTATEMENT."""
        from models import InstructionType
        members = [m.value for m in InstructionType]
        assert "COMPOSITE_RESTATEMENT" not in members, (
            "COMPOSITE_RESTATEMENT must not be in InstructionType — "
            "it would contaminate instruction precision/recall metrics"
        )


# ---------------------------------------------------------------------------
# Real smoke-case regression tests (using downloaded data if available)
# ---------------------------------------------------------------------------

SMOKE_DIR = Path("data/smoke")


class TestSmokeCasesV03:
    @pytest.mark.parametrize("case_id", ["SW-001", "DKS-001"])
    def test_no_waiver_false_positives_from_composite(self, case_id):
        """v0.2 produced 11 (SW-001) and 8 (DKS-001) WAIVE_TEMPORARILY false
        positives. v0.3 should produce zero from composite agreement text."""
        path = SMOKE_DIR / case_id / "source.txt"
        if not path.exists():
            pytest.skip(f"Smoke case {case_id} not downloaded")
        text = path.read_text(encoding="utf-8", errors="ignore")
        result = parse_v03(text)
        body_end = result["segments"]["amendment_body"]["end"]
        composite_waivers = [
            i for i in result["instructions"]
            if i["instruction_type"] == "WAIVE_TEMPORARILY"
            and i["source_start"] >= body_end
        ]
        assert len(composite_waivers) == 0, (
            f"{case_id}: {len(composite_waivers)} waiver false positives "
            f"from composite agreement"
        )

    @pytest.mark.parametrize("case_id", ["SW-001", "DKS-001"])
    def test_composite_target_detected(self, case_id):
        """Both smoke cases should have a composite target detected as a
        ground-truth document (not as an instruction)."""
        path = SMOKE_DIR / case_id / "source.txt"
        if not path.exists():
            pytest.skip(f"Smoke case {case_id} not downloaded")
        text = path.read_text(encoding="utf-8", errors="ignore")
        result = parse_v03(text)
        assert result["composite_target"] is not None
        assert result["composite_target"]["annex"] == "A"
        assert result["composite_target"]["source_format"] == "html_redline"

    @pytest.mark.parametrize("case_id", ["SW-001", "DKS-001"])
    def test_no_composite_in_instructions(self, case_id):
        """The composite must NOT appear as an instruction in the instructions
        list. It is ground truth only."""
        path = SMOKE_DIR / case_id / "source.txt"
        if not path.exists():
            pytest.skip(f"Smoke case {case_id} not downloaded")
        text = path.read_text(encoding="utf-8", errors="ignore")
        result = parse_v03(text)
        for inst in result["instructions"]:
            assert inst["instruction_type"] != "COMPOSITE_RESTATEMENT"

    @pytest.mark.parametrize("case_id", ["SW-001", "DKS-001"])
    def test_instruction_count_dramatically_reduced(self, case_id):
        """v0.2 produced 12 (SW-001) and 9 (DKS-001) instructions, mostly
        false positives. v0.3 should produce far fewer, all from the
        amendment body. With COMPOSITE_RESTATEMENT removed from instructions,
        the count may be 0 for pure composite-format filings."""
        path = SMOKE_DIR / case_id / "source.txt"
        if not path.exists():
            pytest.skip(f"Smoke case {case_id} not downloaded")
        text = path.read_text(encoding="utf-8", errors="ignore")
        result = parse_v03(text)
        # v0.2 had 12/9; v0.3 should have significantly fewer
        assert len(result["instructions"]) <= 6, (
            f"{case_id}: {len(result['instructions'])} instructions — "
            f"expected <= 6 after segmentation"
        )
