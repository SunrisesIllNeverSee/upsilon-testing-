"""Regression tests for the missed patterns from the 25-document
parser-development sample census (v0.3.1 baseline).

These tests use real amendment language extracted from the development
corpus. They are written to FAIL on v0.3.1 (the parser cannot detect
these patterns) and PASS after v0.4 grammar expansion.

Pattern categories (from DEVELOPMENT_CENSUS_v0.3.1.md):
  - amended_by with Article/Schedule targets (26 missed)
  - amended_to read as follows (9 missed)
  - amended_as_follows (7 missed)
  - deleting...inserting (33 missed)
  - deleted_from_section (1 missed)

Each test provides a minimal amendment body containing the pattern and
asserts that parse_v04() detects at least one instruction with the
correct instruction type.
"""
from __future__ import annotations
import pytest
from amendment_parser import parse_v03, parse_v04


# ---------------------------------------------------------------------------
# Test fixtures: minimal amendment bodies extracted from real documents
# ---------------------------------------------------------------------------

# From DEV-013 (Equifax): "Article I ... is hereby amended by adding"
BODY_ARTICLE_AMENDED_BY_ADDING = """
AMENDMENT TO CREDIT AGREEMENT

WHEREAS, the parties desire to amend the Credit Agreement;

NOW, THEREFORE, in consideration of the premises, the parties agree as follows:

SECTION 1. Defined Terms. All capitalized terms used but not otherwise defined
herein shall have the meanings given in the Credit Agreement.

SECTION 2. Amendments to Credit Agreement.

(a) Article I of the Credit Agreement is hereby amended by adding the following
new Section 1.11:

1.11 Divisions. For all purposes under the Loan Documents, in connection with
any division or plan of division under Delaware law.
"""

# From DEV-025 (Dixie Group): "Schedule 1.1 ... is hereby amended by inserting"
BODY_SCHEDULE_AMENDED_BY_INSERTING = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

2.1. Additional Definitions. Schedule 1.1 of the Credit Agreement is hereby
amended by inserting the following new defined terms therein in appropriate
alphabetical order:

"Ameristate Loan Date" means the date on a Permitted Fixed Asset Loan.
"""

# From DEV-025 (Dixie Group): "Schedule 1.1 ... is hereby amended by deleting"
BODY_SCHEDULE_AMENDED_BY_DELETING = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

2.2. Deleted Definitions. Schedule 1.1 of the Credit Agreement is hereby
amended by deleting the following defined terms in their entirety
"Availability Block FCCR", "Availability Block FCCR Measurement Period".
"""

# From DEV-024 (Mohawk): "Section 1.01 ... is amended to read as follows"
BODY_AMENDED_TO_READ = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

SECTION 1. Amendments to Credit Agreement.

Section 1.01 of the Credit Agreement is amended to read as follows:

"Applicable Cash Balance" means, as of any date of determination, an amount
equal to the Applicable Cash Balance (as defined in the Credit Agreement).
"""

# From DEV-007 (Koppers): "Section 1.1 ... is hereby amended as follows"
BODY_AMENDED_AS_FOLLOWS = """
FOURTH AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.1 [Certain Definitions] of the Credit Agreement is hereby amended
as follows:

(a) The following definition is hereby deleted from Section 1.1 in its entirety:
"Euro-Rate Termination Date"

(b) The following new definitions are hereby added to Section 1.1:
"Adjusted Term SOFR" means the Term SOFR plus the applicable spread adjustment.
"""

# From DEV-008 (XpresSpa): "deleting ... and substituting in its place"
BODY_DELETING_SUBSTITUTING = """
SIXTH AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.1 Definitions. The definition of "Commitment Amount" in Section 1.1
of the Credit Agreement is hereby amended by deleting the definition
corresponding to the following definition and substituting in its place the
following definition:

""Commitment Amount": $7,900,000.00."
"""

# From DEV-025 (Dixie Group): "deleting the single instance of ... and inserting ... in lieu thereof"
BODY_DELETING_INSERTING_IN_LIEU = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

2.6. Fixed Asset Availability Amount. The definition of "Borrowing Base" as
set forth in Schedule 1.1 of the Credit Agreement is hereby amended by
deleting the single instance of "$95,000,000" and inserting "$80,000,000"
in lieu thereof.
"""

# From DEV-011 (AGCO): "deleting the definitions of ... and replacing each with"
BODY_DELETING_REPLACING_DEFINITIONS = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.1 of the Credit Agreement is hereby further modified and amended
by deleting the definitions of "Applicable Margin", "Bail-In Action",
"Bail-in Legislation", "Incremental Term Loan Commitment", "Tranche",
"Unused Fee", and "Weighted Average Life" and replacing each with the
following:

"Applicable Margin" means the applicable margin set forth on Schedule 1.1.
"""

# From DEV-007 (Koppers): "is hereby deleted from Section 1.1 in its entirety"
BODY_DELETED_FROM_SECTION = """
FOURTH AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.1 of the Credit Agreement is hereby amended as follows:

(a) The following definition is hereby deleted from Section 1.1 in its
entirety: "Euro-Rate Termination Date"
"""

# From DEV-013 (Equifax): "Article XII ... is hereby amended by adding"
BODY_ARTICLE_XII_AMENDED_BY_ADDING = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, in consideration of the premises, the parties agree as follows:

SECTION 2. Amendments.

(f) Article XII of the Credit Agreement is hereby amended by adding the
following new Section 12.22:

12.22 Acknowledgement Regarding Any Supported QFCs. To the extent that the
Loan Documents provide support, through a guarantee or otherwise.
"""

# From DEV-025 (Dixie Group): "Section 2.4(e) ... is hereby amended by adding"
BODY_SECTION_AMENDED_BY_ADDING_CLAUSE = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

2.11. Anti-Cash Hoarding. Section 2.4(e) of the Credit Agreement is hereby
amended by adding the following new clause (vi) in appropriate numerical order:

(vi) Anti-Cash Hoarding. If on any day after the Fourteenth Amendment
Effective Date, the Borrower shall not request any Borrowing.
"""

# From DEV-025 (Dixie Group): "Section 2.12(d) ... is hereby amended by (i) deleting ... (ii) inserting"
BODY_AMENDED_BY_DELETING_INSERTING_NUMBERED = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

2.13. Benchmark Replacement. Section 2.12(d) of the Credit Agreement is
hereby amended by (i) deleting clause (ii) and (ii) inserting the following
new clauses (ii) and (iii) in lieu thereof:

(ii) Subject to the provisions set forth in Section 2.12(d)(iii) hereof.
"""

# From DEV-011 (AGCO): "modified and amended by deleting ... inserting in lieu thereof"
BODY_MODIFIED_AND_AMENDED_DELETING_INSERTING = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 2.4 of the Credit Agreement is hereby modified and amended by
deleting sub-clause (v) of clause (b) of such section in its entirety
and inserting in lieu thereof the following:

(v) Each Borrower shall prepay the outstanding Loans.
"""

# From DEV-011 (AGCO): "modified and amended by deleting Section X in its entirety"
BODY_MODIFIED_AND_AMENDED_DELETING_SECTION = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 11.6 of the Credit Agreement is hereby modified and amended by
deleting Section 11.6 in its entirety and inserting in lieu thereof the
following:

11.6 Acknowledgement. Each party acknowledges the terms herein.
"""

# From DEV-022 (Brinker): "amended and restated in its entirety"
BODY_AMENDED_AND_RESTATED = """
SIXTH AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 7.01 of the Credit Agreement is hereby amended and restated in its
entirety to read as follows:

7.01 Financial Reporting. The Borrower shall furnish financial statements.
"""

# From DEV-010 (e.l.f. Beauty): "Exhibit D ... amended and restated in its entirety"
BODY_EXHIBIT_AMENDED_AND_RESTATED = """
THIRD AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Exhibit D to the Credit Agreement is hereby amended and restated in its
entirety to read as follows:

Exhibit D. Form of Compliance Certificate.
"""

# From DEV-008 (XpresSpa): "amended by inserting the following"
BODY_AMENDED_BY_INSERTING = """
SIXTH AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.01 of the Credit Agreement is hereby amended by inserting the
following new definition in appropriate alphabetical order:

"Adjusted Term SOFR" means the Term SOFR plus the applicable spread.
"""

# From DEV-009 (BlueLinx): "shall be amended by adding"
BODY_SHALL_BE_AMENDED_BY_ADDING = """
SIXTH AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.4 of the Credit Agreement shall be amended by adding the following
new definition:

"Adjusted Term SOFR" means the Term SOFR plus the applicable spread.
"""

# Synthetic: "amended by modifying" pattern
BODY_AMENDED_BY_MODIFYING = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 2.1 of the Credit Agreement is hereby amended by modifying the
following provision to read as follows:

2.1 Interest Rate. The interest rate shall be the Base Rate.
"""

# Synthetic: "deleted from Schedule X in its entirety"
BODY_DELETED_FROM_SCHEDULE = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

The definition of "Old Term" is hereby deleted from Schedule 1.1 in its
entirety.
"""

# Synthetic: "amended to read as follows" with Article target
BODY_ARTICLE_AMENDED_TO_READ = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Article I of the Credit Agreement is amended to read as follows:

Article I. Definitions. All defined terms shall have the meanings set forth.
"""

# Synthetic: "amended as follows" with Schedule target
BODY_SCHEDULE_AMENDED_AS_FOLLOWS = """
SECOND AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Schedule 1.1 of the Credit Agreement is hereby amended as follows:

(a) The following defined term is hereby deleted: "Old Term"
"""

# Synthetic: "deleting ... replacing it with"
BODY_DELETING_REPLACING_IT_WITH = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.01 of the Credit Agreement is hereby amended by deleting the
definition of "Old Term" and replacing it with the following:

"New Term" means the new defined term.
"""

# Synthetic: "deleting ... replacing each with"
BODY_DELETING_REPLACING_EACH_WITH = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.01 of the Credit Agreement is hereby amended by deleting the
definitions of "Term A" and "Term B" and replacing each with the following:

"Term A" means the updated definition.
"""

# Synthetic: "deleting ... replace with"
BODY_DELETING_REPLACE_WITH = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.01 of the Credit Agreement is hereby amended by deleting the
definition of "Old Term" and replace with the following:

"New Term" means the new defined term.
"""

# Synthetic: "deleting ... inserting the following new"
BODY_DELETING_INSERTING_FOLLOWING_NEW = """
FIRST AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.01 of the Credit Agreement is hereby amended by deleting the
definition of "Old Term" and inserting the following new definition:

"New Term" means the new defined term.
"""


# ---------------------------------------------------------------------------
# Regression tests: each should detect at least one instruction after v0.4
# with the correct instruction type.
# ---------------------------------------------------------------------------

class TestArticleAmendedByAdding:
    """Article I/Article XII ... is hereby amended by adding."""

    def test_article_amended_by_adding(self):
        result = parse_v04(BODY_ARTICLE_AMENDED_BY_ADDING)
        assert len(result["instructions"]) >= 1
        refs = [i.get("target_section_ref") or "" for i in result["instructions"]]
        assert any("Article" in r for r in refs), f"No Article target; refs={refs}"
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD" in types

    def test_article_xii_amended_by_adding(self):
        result = parse_v04(BODY_ARTICLE_XII_AMENDED_BY_ADDING)
        assert len(result["instructions"]) >= 1
        refs = [i.get("target_section_ref") or "" for i in result["instructions"]]
        assert any("Article" in r for r in refs)
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD" in types


class TestScheduleAmendedByInserting:
    """Schedule 1.1 ... is hereby amended by inserting."""

    def test_schedule_amended_by_inserting(self):
        result = parse_v04(BODY_SCHEDULE_AMENDED_BY_INSERTING)
        assert len(result["instructions"]) >= 1
        inst = result["instructions"][0]
        assert "Schedule" in (inst.get("target_section_ref") or "")
        assert inst["instruction_type"] == "ADD"

    def test_schedule_amended_by_deleting(self):
        result = parse_v04(BODY_SCHEDULE_AMENDED_BY_DELETING)
        assert len(result["instructions"]) >= 1
        inst = result["instructions"][0]
        assert "Schedule" in (inst.get("target_section_ref") or "")
        assert inst["instruction_type"] == "DELETE"


class TestAmendedToRead:
    """Section X ... is amended to read as follows."""

    def test_amended_to_read(self):
        result = parse_v04(BODY_AMENDED_TO_READ)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" in types

    def test_article_amended_to_read(self):
        result = parse_v04(BODY_ARTICLE_AMENDED_TO_READ)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" in types


class TestAmendedAsFollows:
    """Section X of the Credit Agreement ... is hereby amended as follows.

    AMENDED_AS_FOLLOWS is a STRUCTURAL/CONTAINER MARKER, not an instruction.
    The parser must NOT emit RESTATE_SECTION for the container phrase itself.
    Child operations beneath it (detected by other regexes) are the actual
    instructions.
    """

    def test_amended_as_follows_container_not_restate(self):
        """The container phrase 'amended as follows' must NOT emit
        RESTATE_SECTION. Only child operations should be detected."""
        result = parse_v04(BODY_AMENDED_AS_FOLLOWS)
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" not in types, (
            "AMENDED_AS_FOLLOWS container must not emit RESTATE_SECTION"
        )

    def test_amended_as_follows_child_delete_detected(self):
        """The child operation 'is hereby deleted from Section 1.1' beneath
        the 'amended as follows' container should be detected as
        DELETE_COMMITMENT."""
        result = parse_v04(BODY_AMENDED_AS_FOLLOWS)
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "DELETE" in types, (
            "Child DELETE operation beneath container should be detected"
        )

    def test_schedule_amended_as_follows_container_not_restate(self):
        """The container phrase 'amended as follows' with a Schedule target
        must NOT emit RESTATE_SECTION."""
        result = parse_v04(BODY_SCHEDULE_AMENDED_AS_FOLLOWS)
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" not in types, (
            "AMENDED_AS_FOLLOWS container must not emit RESTATE_SECTION"
        )


class TestDeletingInserting:
    """deleting ... inserting / deleting ... substituting / deleting ... in lieu thereof."""

    def test_deleting_substituting(self):
        result = parse_v04(BODY_DELETING_SUBSTITUTING)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_deleting_inserting_in_lieu(self):
        result = parse_v04(BODY_DELETING_INSERTING_IN_LIEU)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_deleting_replacing_definitions(self):
        result = parse_v04(BODY_DELETING_REPLACING_DEFINITIONS)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_amended_by_deleting_inserting_numbered(self):
        result = parse_v04(BODY_AMENDED_BY_DELETING_INSERTING_NUMBERED)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_modified_and_amended_deleting_inserting(self):
        result = parse_v04(BODY_MODIFIED_AND_AMENDED_DELETING_INSERTING)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_modified_and_amended_deleting_section(self):
        result = parse_v04(BODY_MODIFIED_AND_AMENDED_DELETING_SECTION)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_deleting_replacing_it_with(self):
        result = parse_v04(BODY_DELETING_REPLACING_IT_WITH)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_deleting_replacing_each_with(self):
        result = parse_v04(BODY_DELETING_REPLACING_EACH_WITH)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_deleting_replace_with(self):
        result = parse_v04(BODY_DELETING_REPLACE_WITH)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_deleting_inserting_following_new(self):
        result = parse_v04(BODY_DELETING_INSERTING_FOLLOWING_NEW)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types


class TestDeletedFromSection:
    """is hereby deleted from Section X in its entirety."""

    def test_deleted_from_section(self):
        result = parse_v04(BODY_DELETED_FROM_SECTION)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "DELETE" in types

    def test_deleted_from_schedule(self):
        result = parse_v04(BODY_DELETED_FROM_SCHEDULE)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "DELETE" in types


class TestSectionAmendedByAddingClause:
    """Section 2.4(e) ... is hereby amended by adding the following new clause."""

    def test_section_amended_by_adding_clause(self):
        result = parse_v04(BODY_SECTION_AMENDED_BY_ADDING_CLAUSE)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD" in types


class TestAmendedByInserting:
    """Section X ... is hereby amended by inserting."""

    def test_amended_by_inserting(self):
        result = parse_v04(BODY_AMENDED_BY_INSERTING)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD" in types


class TestShallBeAmendedByAdding:
    """Section X ... shall be amended by adding."""

    def test_shall_be_amended_by_adding(self):
        result = parse_v04(BODY_SHALL_BE_AMENDED_BY_ADDING)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD" in types


class TestAmendedByModifying:
    """Section X ... is hereby amended by modifying.

    v0.4.1: "amended by modifying" emits UNRESOLVED (too ambiguous to
    classify as ADD or DELETE).
    """

    def test_amended_by_modifying(self):
        result = parse_v04(BODY_AMENDED_BY_MODIFYING)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "UNRESOLVED" in types


class TestAmendedAndRestated:
    """Section X ... is hereby amended and restated in its entirety."""

    def test_amended_and_restated(self):
        result = parse_v04(BODY_AMENDED_AND_RESTATED)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" in types

    def test_exhibit_amended_and_restated(self):
        result = parse_v04(BODY_EXHIBIT_AMENDED_AND_RESTATED)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" in types
        refs = [i.get("target_section_ref") or "" for i in result["instructions"]]
        assert any("Exhibit" in r for r in refs)


# ---------------------------------------------------------------------------
# V0.3.1 baseline regression: ensure v0.4 doesn't break existing detections
# ---------------------------------------------------------------------------

class TestV03BaselineStillPasses:
    """Ensure v0.4 grammar expansion doesn't break v0.3.1 detections."""

    def test_restate_section_still_detected(self):
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 4.02 (Conditions Precedent to each Credit Event) is hereby amended
and restated in its entirety to read as follows:

4.02 Conditions Precedent to each Credit Event. The Administrative Agent
shall not be required to make any credit event.
"""
        result = parse_v04(body)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "RESTATE_SECTION" in types

    def test_add_commitment_still_detected(self):
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 1.01 (Defined Terms) of the Credit Agreement is hereby amended by
adding the following new definition:

"Adjusted Term SOFR" means the Term SOFR plus the applicable spread.
"""
        result = parse_v04(body)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD" in types

    def test_replace_text_still_detected(self):
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 6.11(a) is amended by deleting "4.00 to 1.00" and
replacing it with "5.00 to 1.00".
"""
        result = parse_v04(body)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "REPLACE_TEXT" in types

    def test_waiver_still_detected(self):
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

1. Waiver. Compliance with Section 6.11(a) is hereby waived for the fiscal
quarter ending June 30, 2026.
"""
        result = parse_v04(body)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "WAIVE_TEMPORARILY" in types


# ---------------------------------------------------------------------------
# V0.3.1 baseline: these patterns should NOT be detected by v0.3
# (verifying that v0.3 is preserved and v0.4 is a separate function)
# ---------------------------------------------------------------------------

class TestV03BaselineDoesNotDetectV04Patterns:
    """Verify that parse_v03 (v0.3.1 baseline) does NOT detect v0.4 patterns.
    This confirms the v0.3 baseline is preserved for comparison."""

    def test_v03_does_not_detect_article_target(self):
        result = parse_v03(BODY_ARTICLE_AMENDED_BY_ADDING)
        assert len(result["instructions"]) == 0

    def test_v03_does_not_detect_schedule_target(self):
        result = parse_v03(BODY_SCHEDULE_AMENDED_BY_INSERTING)
        assert len(result["instructions"]) == 0

    def test_v03_does_not_detect_amended_to_read(self):
        result = parse_v03(BODY_AMENDED_TO_READ)
        assert len(result["instructions"]) == 0

    def test_v03_does_not_detect_amended_as_follows(self):
        result = parse_v03(BODY_AMENDED_AS_FOLLOWS)
        assert len(result["instructions"]) == 0


# ---------------------------------------------------------------------------
# False positive regression: ensure v0.4 fixes don't introduce new FPs
# ---------------------------------------------------------------------------

class TestFalsePositiveRegression:
    """Ensure v0.4 doesn't match amendment section numbers as targets."""

    def test_section_hereof_not_matched(self):
        """'Section 2 hereof, the Credit Agreement is hereby amended as follows'
        should NOT match — 'Section 2' is the amendment's section number."""
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

Section 2 hereof, the Credit Agreement is hereby amended as follows:

(a) Section 1.01 of the Credit Agreement is hereby amended by adding
the following new definition:

"New Term" means the new defined term.
"""
        result = parse_v04(body)
        # Should only detect the real instruction (Section 1.01 amended by adding),
        # not the container "Section 2 hereof ... amended as follows"
        for inst in result["instructions"]:
            ref = inst.get("target_section_ref") or ""
            matched = body[inst["source_start"]:inst["source_end"]]
            assert not ("Section 2" in ref and "hereof" in matched), \
                f"Amendment section number matched as target: {ref} in {matched[:80]}"

    def test_cross_reference_not_matched_as_target(self):
        """A cross-reference 'Schedule 2.01A' should not be matched as a
        REPLACE_TEXT target when the actual deleting/inserting is in a
        different instruction."""
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

(a) The definition of "Old Term" in Schedule 2.01A
or in the Assignment and Assumption pursuant to which such Lender becomes
a party hereto, as applicable."

(b) By deleting in its entirety the table set forth in the definition of
"Applicable Rate" appearing in Section 1.01 of the Credit Agreement and
inserting in lieu thereof the following new table.
"""
        result = parse_v04(body)
        # Should not match Schedule 2.01A as a REPLACE_TEXT target
        for inst in result["instructions"]:
            ref = inst.get("target_section_ref") or ""
            if "Schedule 2.01A" in ref:
                pytest.fail(f"Cross-reference Schedule 2.01A matched as target: {ref}")

    def test_replace_v04_does_not_bridge_across_sections(self):
        """REPLACE_V04 must not bridge from one section reference to another
        section's 'amended by deleting' language.

        Regression test: the old REPLACE_V04 regex used a bare .{0,200}?
        gap between the target and 'amended by'.  This allowed it to
        match 'Section 7.04(c)(xiii) is hereby amended to replace...'
        as the target while using 'Section 7.10 ... amended by deleting...'
        as the amendment language — producing a wrong target and causing
        finditer to skip the real Section 7.10 instruction entirely.

        The fix (tempered group that stops at another
        Section/Article/Schedule/Exhibit reference) ensures each
        section's amendment language is matched to the correct target.
        """
        body = """
AMENDMENT TO CREDIT AGREEMENT

NOW, THEREFORE, the parties agree as follows:

(g) Section 7.04(c)(xiii) is hereby amended to replace the term
"Net Cash Proceeds" in the first line thereof with the term
"Net Cash Payments."

(h) Section 7.10 of the Credit Agreement is hereby amended by deleting
paragraph (a) in its entirety and replacing it with the following:
(a) Total Funded Debt to EBITDA Ratio. The Loan Parties shall not
permit the Core Leverage Ratio as of the end of each fiscal quarter
(i) ending on December 31, 2023 to exceed 3.75 to 1.00, and (ii) for
any quarter ending thereafter, to exceed 3.50 to 1.00.
"""
        result = parse_v04(body)
        refs = [i.get("target_section_ref") or "" for i in result["instructions"]]
        # Section 7.10 must be detected as a REPLACE_TEXT target
        assert any("7.10" in r for r in refs), (
            f"Section 7.10 not detected — refs: {refs}.  "
            f"REPLACE_V04 may be bridging across section boundaries."
        )
        # Section 7.04(c)(xiii) should NOT be matched as a REPLACE_TEXT
        # target for Section 7.10's amendment language.  It uses a
        # different pattern ("amended to replace the term") that
        # REPLACE_V04 does not handle.
        for inst in result["instructions"]:
            ref = inst.get("target_section_ref") or ""
            if "7.04" in ref and inst["instruction_type"] == "REPLACE_TEXT":
                matched = body[inst["source_start"]:inst["source_end"]]
                if "deleting" in matched.lower():
                    pytest.fail(
                        f"Section 7.04(c)(xiii) incorrectly matched with "
                        f"Section 7.10's 'amended by deleting' language: "
                        f"{matched[:100]}"
                    )
