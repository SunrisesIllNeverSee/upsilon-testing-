"""Tests for Step 22C unresolved taxonomy builder."""
from __future__ import annotations

from build_step22_taxonomy import (
    ALL_BUCKETS,
    classify_record,
    build_taxonomy,
    TARGET_RESOLUTION,
    NEW_VALUE_EXTRACTION,
    DEFINED_TERM_RESOLUTION,
    UNSUPPORTED_COMMITMENT,
    OTHER,
)


def _make_record(
    chain="TEST",
    rc="RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT",
    candidate=None,
    ins_type="RESTATE_SECTION",
    section="Section 7.10",
    source="Some text about leverage ratio",
):
    return {
        "chain": chain,
        "amendment_number": 1,
        "section": section,
        "instruction_type": ins_type,
        "source_span": source,
        "root_cause_cluster": rc,
        "candidate_canonical_commitment": candidate,
    }


def test_classify_rc01_no_candidate():
    """RC-01 with no candidate → TARGET_RESOLUTION."""
    rec = _make_record(rc="RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT", candidate=None)
    assert classify_record(rec) == TARGET_RESOLUTION


def test_classify_rc01_with_candidate():
    """RC-01 with a candidate → NEW_VALUE_EXTRACTION (refined)."""
    rec = _make_record(
        rc="RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT",
        candidate="financial_covenant.leverage_ratio",
    )
    assert classify_record(rec) == NEW_VALUE_EXTRACTION


def test_classify_rc02():
    """RC-02 → NEW_VALUE_EXTRACTION."""
    rec = _make_record(rc="RC-02: RESTATE_SECTION_AMBIGUOUS_VALUE")
    assert classify_record(rec) == NEW_VALUE_EXTRACTION


def test_classify_rc03():
    """RC-03 → TARGET_RESOLUTION."""
    rec = _make_record(rc="RC-03: ADD_UNKNOWN_COMMITMENT", ins_type="ADD")
    assert classify_record(rec) == TARGET_RESOLUTION


def test_classify_rc06():
    """RC-06 → DEFINED_TERM_RESOLUTION."""
    rec = _make_record(rc="RC-06: DEFINITION_SECTION_NO_COVENANT")
    assert classify_record(rec) == DEFINED_TERM_RESOLUTION


def test_classify_rc07_no_covenant_kw():
    """RC-07 with no covenant keywords → OTHER."""
    rec = _make_record(
        rc="RC-07: NON_COVENANT_SECTION",
        source="Administrative section about notices",
    )
    assert classify_record(rec) == OTHER


def test_classify_rc07_with_covenant_kw_no_candidate():
    """RC-07 with covenant keywords but no candidate → UNSUPPORTED_COMMITMENT."""
    rec = _make_record(
        rc="RC-07: NON_COVENANT_SECTION",
        source="The borrower shall maintain an asset coverage ratio",
        candidate=None,
    )
    assert classify_record(rec) == UNSUPPORTED_COMMITMENT


def test_classify_rc07_with_covenant_kw_and_candidate():
    """RC-07 with covenant keywords and a candidate → NEW_VALUE_EXTRACTION."""
    rec = _make_record(
        rc="RC-07: NON_COVENANT_SECTION",
        source="The leverage ratio shall not exceed 4.00",
        candidate="financial_covenant.leverage_ratio",
    )
    assert classify_record(rec) == NEW_VALUE_EXTRACTION


def test_classify_rc08():
    """RC-08 → NEW_VALUE_EXTRACTION."""
    rec = _make_record(
        rc="RC-08: COVENANT_IDENTIFIED_VALUE_EXTRACTION_FAILED",
        candidate="financial_covenant.leverage_ratio",
    )
    assert classify_record(rec) == NEW_VALUE_EXTRACTION


def test_build_taxonomy_all_buckets_represented():
    """The taxonomy should include all 14 buckets in percentages."""
    records = [_make_record() for _ in range(10)]
    corpus = {"records": records}
    taxonomy = build_taxonomy(corpus)
    for bucket in ALL_BUCKETS:
        assert bucket in taxonomy["bucket_percentages"]


def test_build_taxonomy_percentages_sum_to_100():
    """Bucket percentages should sum to approximately 100%."""
    records = [
        _make_record(rc="RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT"),
        _make_record(rc="RC-02: RESTATE_SECTION_AMBIGUOUS_VALUE"),
        _make_record(rc="RC-07: NON_COVENANT_SECTION", source="no keywords here"),
        _make_record(rc="RC-08: COVENANT_IDENTIFIED_VALUE_EXTRACTION_FAILED",
                     candidate="financial_covenant.leverage_ratio"),
    ]
    corpus = {"records": records}
    taxonomy = build_taxonomy(corpus)
    total_pct = sum(taxonomy["bucket_percentages"].values())
    assert abs(total_pct - 100.0) < 0.1, f"Percentages sum to {total_pct}, expected ~100"


def test_build_taxonomy_mechanism_set_covers_80pct():
    """The mechanism set should cover at least 80% of records."""
    # Create records where 2 buckets cover >80%
    records = []
    for _ in range(40):
        records.append(_make_record(rc="RC-07: NON_COVENANT_SECTION",
                                     source="no keywords"))
    for _ in range(10):
        records.append(_make_record(rc="RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT"))
    corpus = {"records": records}
    taxonomy = build_taxonomy(corpus)
    assert taxonomy["mechanism_set_coverage"] >= 80.0


def test_build_taxonomy_empty_corpus():
    """Empty corpus should not crash."""
    corpus = {"records": []}
    taxonomy = build_taxonomy(corpus)
    assert taxonomy["total_records"] == 0
    assert taxonomy["mechanism_set_80pct"] == []
