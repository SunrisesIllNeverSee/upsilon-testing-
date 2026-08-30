"""Regression tests for the 75 missed patterns from the 25-document
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
asserts that parse_v04() (or parse_v03() after v0.4 changes) detects
at least one instruction.
"""
from __future__ import annotations
import pytest
from amendment_parser import parse_v03


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


# ---------------------------------------------------------------------------
# Regression tests: each should detect at least one instruction after v0.4
# ---------------------------------------------------------------------------

class TestArticleAmendedByAdding:
    """Article I/Article XII ... is hereby amended by adding."""

    def test_article_amended_by_adding(self):
        result = parse_v03(BODY_ARTICLE_AMENDED_BY_ADDING)
        assert len(result["instructions"]) >= 1, (
            "Article I ... amended by adding should produce an instruction"
        )
        # At least one instruction should target an Article
        refs = [i.get("target_section_ref") or "" for i in result["instructions"]]
        assert any("Article" in r for r in refs), (
            f"No instruction targets an Article; refs={refs}"
        )

    def test_article_xii_amended_by_adding(self):
        result = parse_v03(BODY_ARTICLE_XII_AMENDED_BY_ADDING)
        assert len(result["instructions"]) >= 1, (
            "Article XII ... amended by adding should produce an instruction"
        )


class TestScheduleAmendedByInserting:
    """Schedule 1.1 ... is hereby amended by inserting."""

    def test_schedule_amended_by_inserting(self):
        result = parse_v03(BODY_SCHEDULE_AMENDED_BY_INSERTING)
        assert len(result["instructions"]) >= 1, (
            "Schedule 1.1 ... amended by inserting should produce an instruction"
        )
        inst = result["instructions"][0]
        assert "Schedule" in (inst.get("target_section_ref") or "")

    def test_schedule_amended_by_deleting(self):
        result = parse_v03(BODY_SCHEDULE_AMENDED_BY_DELETING)
        assert len(result["instructions"]) >= 1, (
            "Schedule 1.1 ... amended by deleting should produce an instruction"
        )


class TestAmendedToRead:
    """Section X ... is amended to read as follows."""

    def test_amended_to_read(self):
        result = parse_v03(BODY_AMENDED_TO_READ)
        assert len(result["instructions"]) >= 1, (
            "Section 1.01 ... amended to read as follows should produce an instruction"
        )


class TestAmendedAsFollows:
    """Section X ... is hereby amended as follows."""

    def test_amended_as_follows(self):
        result = parse_v03(BODY_AMENDED_AS_FOLLOWS)
        assert len(result["instructions"]) >= 1, (
            "Section 1.1 ... amended as follows should produce an instruction"
        )


class TestDeletingInserting:
    """deleting ... inserting / deleting ... substituting / deleting ... in lieu thereof."""

    def test_deleting_substituting(self):
        result = parse_v03(BODY_DELETING_SUBSTITUTING)
        assert len(result["instructions"]) >= 1, (
            "deleting ... substituting in its place should produce an instruction"
        )

    def test_deleting_inserting_in_lieu(self):
        result = parse_v03(BODY_DELETING_INSERTING_IN_LIEU)
        assert len(result["instructions"]) >= 1, (
            "deleting the single instance of ... inserting ... in lieu thereof should produce an instruction"
        )

    def test_deleting_replacing_definitions(self):
        result = parse_v03(BODY_DELETING_REPLACING_DEFINITIONS)
        assert len(result["instructions"]) >= 1, (
            "deleting the definitions of ... and replacing each with should produce an instruction"
        )

    def test_amended_by_deleting_inserting_numbered(self):
        result = parse_v03(BODY_AMENDED_BY_DELETING_INSERTING_NUMBERED)
        assert len(result["instructions"]) >= 1, (
            "amended by (i) deleting ... (ii) inserting should produce an instruction"
        )


class TestDeletedFromSection:
    """is hereby deleted from Section X in its entirety."""

    def test_deleted_from_section(self):
        result = parse_v03(BODY_DELETED_FROM_SECTION)
        assert len(result["instructions"]) >= 1, (
            "is hereby deleted from Section 1.1 in its entirety should produce an instruction"
        )


class TestSectionAmendedByAddingClause:
    """Section 2.4(e) ... is hereby amended by adding the following new clause."""

    def test_section_amended_by_adding_clause(self):
        result = parse_v03(BODY_SECTION_AMENDED_BY_ADDING_CLAUSE)
        assert len(result["instructions"]) >= 1, (
            "Section 2.4(e) ... amended by adding the following new clause should produce an instruction"
        )


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
        result = parse_v03(body)
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
        result = parse_v03(body)
        assert len(result["instructions"]) >= 1
        types = [i["instruction_type"] for i in result["instructions"]]
        assert "ADD_COMMITMENT" in types
