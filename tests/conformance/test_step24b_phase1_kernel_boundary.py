"""Step 24B Phase 1 conformance tests — Authoritative Kernel Boundary.

These tests enforce that:
1. Legacy CommitmentState can be converted to canonical CommitmentKernel
   with persistent CommitmentIdentity.
2. The KernelStore establishes all commitments at version 0 (origin).
3. The AgreementAddressMap maps section refs to commitment IDs.
4. Identity persists across the boundary (commitment_id == canonical_key).
5. Semantic fields are preserved across the boundary.
6. A violation path: kernels without identity fail closed.
7. A violation path: section refs that don't match any commitment
   fail to resolve.

Designated real EDGAR case: Ameresco Section 7.10(a) leverage ratio
scalar replacement (EDGAR-AMERESCO chain).
"""
from __future__ import annotations

import pytest

from upsilon.models import (
    CommitmentIdentity,
    CommitmentKernel,
    IdentityProvenance,
)
from upsilon.models.legacy_models import CommitmentState
from upsilon.commitments.kernel_bridge import (
    establish_authoritative_kernel,
    state_to_kernel,
    kernel_to_state,
    store_to_state_dict,
)
from upsilon.commitments.identity import AgreementAddressMap, IdentityResolver
from upsilon.commitments.kernel import KernelStore


# ---------------------------------------------------------------------------
# Test fixtures — Ameresco S0 state (real EDGAR case)
# ---------------------------------------------------------------------------


def _ameresco_original_state() -> dict[str, CommitmentState]:
    """Ameresco S0 original state (from edgar_chains.chain_ameresco)."""
    return {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="core_leverage_ratio",
            operator="<=",
            threshold=3.50,
            unit="ratio",
            frequency="quarterly",
            applicability={
                "step_down_schedule": [
                    {"period_end": "2022-03-31", "threshold": 4.50},
                    {"period_end": "2022-06-30", "threshold": 4.25},
                    {"period_end": "2022-09-30", "threshold": 4.00},
                    {"period_end": "2022-12-31", "threshold": 4.00},
                ],
                "steady_state_threshold": 3.50,
            },
        ),
        "financial_covenant.debt_service_coverage": CommitmentState(
            canonical_key="financial_covenant.debt_service_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="debt_service_coverage_ratio",
            operator=">=",
            threshold=1.50,
            unit="ratio",
            frequency="quarterly",
        ),
    }


_AMERESCO_SECTION_REFS = {
    "financial_covenant.leverage_ratio": "Section 7.10(a)",
    "financial_covenant.debt_service_coverage": "Section 7.10(b)",
}

_AMERESCO_AGREEMENT = "ameresco-fifth-ar-credit-agreement-2022-03-04"


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestStateToKernelConversion:
    """Test CommitmentState → CommitmentKernel conversion."""

    def test_state_to_kernel_produces_kernel_with_identity(self):
        """Positive: state_to_kernel produces a CommitmentKernel with
        persistent CommitmentIdentity."""
        state = _ameresco_original_state()["financial_covenant.leverage_ratio"]
        kernel = state_to_kernel(
            state,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_ref="Section 7.10(a)",
        )

        assert isinstance(kernel, CommitmentKernel)
        assert isinstance(kernel.identity, CommitmentIdentity)
        assert kernel.commitment_id == "financial_covenant.leverage_ratio"
        assert kernel.agreement_identity == _AMERESCO_AGREEMENT
        assert kernel.canonical_key == "financial_covenant.leverage_ratio"

    def test_state_to_kernel_preserves_semantic_fields(self):
        """Positive: semantic fields are preserved across the boundary."""
        state = _ameresco_original_state()["financial_covenant.leverage_ratio"]
        kernel = state_to_kernel(
            state,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_ref="Section 7.10(a)",
        )

        assert kernel.threshold == 3.50
        assert kernel.operator == "<="
        assert kernel.unit == "ratio"
        assert kernel.frequency == "quarterly"
        assert kernel.party == ["borrower"]
        assert kernel.action == "maintain"
        assert kernel.subject == "core_leverage_ratio"
        assert kernel.applicability == state.applicability

    def test_state_to_kernel_preserves_temporal_fields(self):
        """Positive: temporal fields are preserved across the boundary."""
        state = CommitmentState(
            canonical_key="financial_covenant.test",
            commitment_type="financial_covenant",
            status="ACTIVE",
        )
        kernel = state_to_kernel(
            state,
            agreement_identity=_AMERESCO_AGREEMENT,
        )

        assert kernel.status == "ACTIVE"

    def test_state_to_kernel_identity_provenance_is_s0_origin(self):
        """Positive: identity provenance is S0_ORIGIN for origin kernels."""
        state = _ameresco_original_state()["financial_covenant.leverage_ratio"]
        kernel = state_to_kernel(
            state,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_ref="Section 7.10(a)",
        )

        assert kernel.identity.provenance == IdentityProvenance.S0_ORIGIN
        assert kernel.identity.confidence == 1.0

    def test_state_to_kernel_local_address_carries_section_ref(self):
        """Positive: local_address carries the section reference."""
        state = _ameresco_original_state()["financial_covenant.leverage_ratio"]
        kernel = state_to_kernel(
            state,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_ref="Section 7.10(a)",
        )

        assert kernel.identity.local_address.section_ref == "Section 7.10(a)"
        assert kernel.identity.local_address.established_at_version == "S0"


class TestKernelToStateConversion:
    """Test CommitmentKernel → CommitmentState reverse conversion."""

    def test_kernel_to_state_roundtrip_preserves_semantic_fields(self):
        """Positive: roundtrip state→kernel→state preserves semantic fields."""
        original = _ameresco_original_state()["financial_covenant.leverage_ratio"]
        kernel = state_to_kernel(
            original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_ref="Section 7.10(a)",
        )
        restored = kernel_to_state(kernel)

        assert restored.canonical_key == original.canonical_key
        assert restored.threshold == original.threshold
        assert restored.operator == original.operator
        assert restored.unit == original.unit
        assert restored.frequency == original.frequency
        assert restored.party == original.party
        assert restored.action == original.action
        assert restored.subject == original.subject
        assert restored.applicability == original.applicability


class TestEstablishAuthoritativeKernel:
    """Test the full S0 boundary establishment."""

    def test_establish_authoritative_kernel_creates_store(self):
        """Positive: establish_authoritative_kernel creates a KernelStore
        with all commitments at version 0."""
        original = _ameresco_original_state()
        store, address_map, kernels = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        assert isinstance(store, KernelStore)
        assert len(store.get_all_current()) == 2
        assert "financial_covenant.leverage_ratio" in store.get_all_current()
        assert "financial_covenant.debt_service_coverage" in store.get_all_current()

    def test_establish_authoritative_kernel_version_zero(self):
        """Positive: all commitments are established at version 0 (origin)."""
        original = _ameresco_original_state()
        store, _, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        for cid in original:
            history = store.get_version_history(cid)
            assert len(history) == 1
            assert history[0].version_number == 0
            assert history[0].produced_by_proof_id == "ORIGIN"
            assert history[0].predecessor_version is None

    def test_establish_authoritative_kernel_address_map(self):
        """Positive: AgreementAddressMap maps section refs to commitment IDs."""
        original = _ameresco_original_state()
        store, address_map, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        assert address_map.resolve_by_address("Section 7.10(a)") == \
            "financial_covenant.leverage_ratio"
        assert address_map.resolve_by_address("Section 7.10(b)") == \
            "financial_covenant.debt_service_coverage"

    def test_establish_authoritative_kernel_identity_persists(self):
        """Positive: identity persists across the boundary."""
        original = _ameresco_original_state()
        store, _, kernels = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        for cid, kernel in kernels.items():
            assert kernel.commitment_id == cid
            assert kernel.agreement_identity == _AMERESCO_AGREEMENT
            assert kernel.canonical_key == cid

    def test_store_to_state_dict_roundtrip(self):
        """Positive: store_to_state_dict produces compatible CommitmentState dict."""
        original = _ameresco_original_state()
        store, _, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        state_dict = store_to_state_dict(store)
        assert set(state_dict.keys()) == set(original.keys())

        for key in original:
            assert state_dict[key].canonical_key == original[key].canonical_key
            assert state_dict[key].threshold == original[key].threshold
            assert state_dict[key].operator == original[key].operator


class TestAmerescoScalarReplacementPredecessor:
    """Designated real EDGAR case: Ameresco leverage ratio predecessor.

    The Ameresco A1 amendment (Section 7.10(a)) replaces the leverage
    ratio step-down schedule.  The predecessor kernel must be the S0
    state with threshold=3.50 and the original step-down schedule.
    """

    def test_ameresco_predecessor_kernel_has_correct_threshold(self):
        """Positive: the Ameresco predecessor kernel has threshold=3.50."""
        original = _ameresco_original_state()
        store, _, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        assert predecessor is not None
        assert predecessor.threshold == 3.50
        assert predecessor.operator == "<="
        assert predecessor.unit == "ratio"

    def test_ameresco_predecessor_kernel_has_step_down_schedule(self):
        """Positive: the predecessor kernel has the original step-down schedule."""
        original = _ameresco_original_state()
        store, _, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        assert predecessor is not None
        schedule = predecessor.applicability.get("step_down_schedule", [])
        assert len(schedule) == 4
        assert schedule[0]["threshold"] == 4.50
        assert schedule[-1]["threshold"] == 4.00

    def test_ameresco_address_map_resolves_section_7_10a(self):
        """Positive: the address map resolves Section 7.10(a) to the
        leverage ratio commitment."""
        original = _ameresco_original_state()
        _, address_map, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        resolver = IdentityResolver(address_map)
        result = resolver.resolve(section_ref="Section 7.10(a)")

        assert result.resolved
        assert result.identity.commitment_id == "financial_covenant.leverage_ratio"
        assert result.evidence_level == "SUFFICIENT"


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestKernelBoundaryViolations:
    """Violation paths that must fail closed."""

    def test_unknown_section_ref_fails_closed(self):
        """Violation: an unknown section ref fails to resolve identity."""
        original = _ameresco_original_state()
        _, address_map, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        resolver = IdentityResolver(address_map)
        result = resolver.resolve(section_ref="Section 99.99")

        assert not result.resolved
        assert result.fail_closed
        assert result.identity is None

    def test_empty_section_ref_fails_closed(self):
        """Violation: an empty section ref fails to resolve identity."""
        original = _ameresco_original_state()
        _, address_map, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        resolver = IdentityResolver(address_map)
        result = resolver.resolve(section_ref=None)

        assert not result.resolved
        assert result.fail_closed

    def test_alias_only_without_corroboration_is_weak(self):
        """Violation: an alias match without address corroboration is WEAK."""
        original = _ameresco_original_state()
        _, address_map, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        resolver = IdentityResolver(address_map)
        result = resolver.resolve(alias_match="leverage_ratio")

        # Alias alone without address corroboration is WEAK (0.3)
        assert not result.resolved
        assert result.evidence_level == "INSUFFICIENT"

    def test_kernel_store_rejects_duplicate_origin(self):
        """Violation: establishing the same commitment twice fails."""
        original = _ameresco_original_state()
        store, _, _ = establish_authoritative_kernel(
            original_state=original,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_refs=_AMERESCO_SECTION_REFS,
        )

        # Try to establish the same commitment again
        state = original["financial_covenant.leverage_ratio"]
        kernel = state_to_kernel(
            state,
            agreement_identity=_AMERESCO_AGREEMENT,
            section_ref="Section 7.10(a)",
        )

        with pytest.raises(ValueError, match="already exists"):
            store.establish_origin(kernel)

    def test_advance_without_authority_raises(self):
        """Violation: KernelStore.advance requires the commitment to exist."""
        store = KernelStore(agreement_identity=_AMERESCO_AGREEMENT)

        # No commitment established — advance must fail
        from upsilon.models import CommitmentIdentity, AddressBinding
        identity = CommitmentIdentity(
            commitment_id="nonexistent",
            agreement_identity=_AMERESCO_AGREEMENT,
            canonical_key="nonexistent",
            local_address=AddressBinding(
                section_ref="Section 1",
                established_at_version="S0",
            ),
        )
        kernel = CommitmentKernel(identity=identity)

        with pytest.raises(ValueError, match="not in kernel store"):
            store.advance("nonexistent", kernel, proof_id="PRF-test")
