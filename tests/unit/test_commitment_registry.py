"""Tests for the commitment registry (Step 21 / Section B)."""
from __future__ import annotations

import pytest

from upsilon.commitments.commitment_registry import (
    ALL_CLASSES,
    COVENANT_CLASSES,
    FACILITY_CLASSES,
    CommitmentAlias,
    get_aliases_for_class,
    get_all_aliases,
    get_class_unit,
    is_known_class,
    resolve_commitment_from_section,
    resolve_commitment_from_state,
    resolve_commitment_from_text,
)
from upsilon.models.legacy_models import CommitmentState


# ---------------------------------------------------------------------------
# Canonical class tests
# ---------------------------------------------------------------------------


class TestCanonicalClasses:
    def test_13_canonical_classes(self):
        assert len(ALL_CLASSES) == 13

    def test_3_facility_classes(self):
        assert len(FACILITY_CLASSES) == 3
        assert "facility.revolving_facility" in FACILITY_CLASSES
        assert "facility.term_loan" in FACILITY_CLASSES
        assert "facility.delayed_draw_term_loan" in FACILITY_CLASSES

    def test_10_covenant_classes(self):
        assert len(COVENANT_CLASSES) == 10
        assert "financial_covenant.leverage_ratio" in COVENANT_CLASSES
        assert "financial_covenant.tangible_net_worth" in COVENANT_CLASSES

    def test_is_known_class(self):
        assert is_known_class("facility.revolving_facility")
        assert is_known_class("financial_covenant.leverage_ratio")
        assert not is_known_class("facility.unknown")
        assert not is_known_class("")

    def test_get_class_unit(self):
        assert get_class_unit("financial_covenant.leverage_ratio") == "ratio"
        assert get_class_unit("financial_covenant.tier_1_leverage_ratio") == "percent"
        assert get_class_unit("facility.revolving_facility") == "usd"


# ---------------------------------------------------------------------------
# Alias resolution tests
# ---------------------------------------------------------------------------


class TestAliasResolution:
    def test_leverage_ratio_aliases(self):
        aliases = [
            "Maximum Total Leverage Ratio",
            "Consolidated Leverage Ratio",
            "Total Leverage Ratio",
            "Leverage Ratio",
            "Total Funded Debt to EBITDA",
            "Senior Funded Debt to EBITDA",
        ]
        for alias in aliases:
            cid, field, conf = resolve_commitment_from_text(alias)
            assert cid == "financial_covenant.leverage_ratio", f"Failed for: {alias}"
            assert field == "threshold"
            assert conf >= 0.50

    def test_tier_1_leverage_ratio_does_not_match_generic_leverage(self):
        """Tier 1 Leverage Ratio should resolve to tier_1_leverage_ratio,
        not the generic leverage_ratio."""
        cid, _, _ = resolve_commitment_from_text("Tier 1 Leverage Ratio")
        assert cid == "financial_covenant.tier_1_leverage_ratio"

    def test_interest_coverage_aliases(self):
        for alias in ["Interest Coverage", "Interest Coverage Ratio", "EBIT to Interest Ratio"]:
            cid, _, _ = resolve_commitment_from_text(alias)
            assert cid == "financial_covenant.interest_coverage"

    def test_facility_aliases(self):
        cid, _, _ = resolve_commitment_from_text("Revolving Facility")
        assert cid == "facility.revolving_facility"
        cid, _, _ = resolve_commitment_from_text("Term Loan")
        assert cid == "facility.term_loan"
        cid, _, _ = resolve_commitment_from_text("Delayed Draw Term Loan")
        assert cid == "facility.delayed_draw_term_loan"

    def test_no_match_returns_none(self):
        cid, _, conf = resolve_commitment_from_text("some random text without covenant keywords")
        assert cid is None
        assert conf == 0.0

    def test_priority_ordering(self):
        """Specific patterns should match before generic ones."""
        # "Maximum Total Leverage Ratio" should match the specific pattern
        # (priority 5), not the generic "Leverage Ratio" (priority 50)
        aliases = get_all_aliases()
        max_total_idx = next(
            i for i, a in enumerate(aliases)
            if a.canonical_id == "financial_covenant.leverage_ratio"
            and "Maximum" in a.pattern.pattern
        )
        generic_idx = next(
            i for i, a in enumerate(aliases)
            if a.canonical_id == "financial_covenant.leverage_ratio"
            and a.pattern.pattern == r"Leverage\s+Ratio"
        )
        assert max_total_idx < generic_idx


# ---------------------------------------------------------------------------
# Section resolution tests
# ---------------------------------------------------------------------------


class TestSectionResolution:
    def test_section_7_10_maps_to_leverage_ratio(self):
        cid = resolve_commitment_from_section("Section 7.10")
        assert cid == "financial_covenant.leverage_ratio"

    def test_section_2_01_maps_to_revolving_facility(self):
        cid = resolve_commitment_from_section("Section 2.01")
        assert cid == "facility.revolving_facility"

    def test_unknown_section_returns_none(self):
        cid = resolve_commitment_from_section("Section 99.99")
        assert cid is None

    def test_empty_section_returns_none(self):
        cid = resolve_commitment_from_section(None)
        assert cid is None
        cid = resolve_commitment_from_section("")
        assert cid is None


# ---------------------------------------------------------------------------
# State resolution tests
# ---------------------------------------------------------------------------


class TestStateResolution:
    def test_resolve_existing_commitment(self):
        state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }
        result = resolve_commitment_from_state(
            "financial_covenant.leverage_ratio", state,
        )
        assert result is not None
        assert result.threshold == 4.0

    def test_resolve_nonexistent_commitment(self):
        state = {}
        result = resolve_commitment_from_state(
            "financial_covenant.leverage_ratio", state,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Combined resolution tests
# ---------------------------------------------------------------------------


class TestCombinedResolution:
    def test_text_with_alias_and_state(self):
        state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }
        cid, field, conf = resolve_commitment_from_text(
            "Maximum Total Leverage Ratio shall not exceed 3.50 to 1.00",
            section_ref="Section 7.10",
            current_state=state,
        )
        assert cid == "financial_covenant.leverage_ratio"
        assert field == "threshold"
        assert conf == 0.95  # alias match + in state

    def test_text_alias_not_in_state(self):
        """When state is empty, the resolver returns None because it
        cannot validate the alias against state.  This is conservative
        behavior — we don't want to map to a commitment that doesn't
        exist in the current state."""
        state = {}
        cid, field, conf = resolve_commitment_from_text(
            "Maximum Total Leverage Ratio",
            section_ref="Section 7.10",
            current_state=state,
        )
        assert cid is None
        assert conf == 0.0
