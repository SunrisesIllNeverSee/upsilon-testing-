"""Step 24B Phase 3 conformance tests — AuthorizedTransformationEngine.

These tests enforce that the AuthorizedTransformationEngine is the
controlling semantic interpretation step for SCALAR_REPLACEMENT:

1. Given evidence + predecessor kernel, the engine produces an
   AuthorizedTransformation Δ.
2. The engine resolves identity via the AgreementAddressMap (not
   global section heuristics).
3. The engine classifies the transformation family.
4. The engine determines affected fields.
5. The engine extracts old/new values.
6. The engine verifies old-value consistency.
7. The engine determines preserved fields.
8. Violation: evidence with no section ref fails closed.
9. Violation: evidence with wrong declared old value is rejected.
10. Violation: evidence with undeterminable transformation type is rejected.
11. Designated real EDGAR case: Ameresco A1 Section 7.10(a).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from upsilon.models import (
    AuthorizedTransformation,
    CommitmentKernel,
    TransformationFamily,
)
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    DomainEffect,
    InstructionProvenance,
    InstructionType,
)
from upsilon.commitments.kernel_bridge import establish_authoritative_kernel
from upsilon.commitments.identity import IdentityResolver
from upsilon.evidence.evidence_extractor import instruction_to_evidence
from upsilon.transformations.authorized_change import (
    AmendmentEvidence,
    AuthorityContext,
    AuthorizedTransformationEngine,
    TransformationResult,
)


# ---------------------------------------------------------------------------
# Test fixtures — Ameresco S0 + A1
# ---------------------------------------------------------------------------


_AMERESCO_AGREEMENT = "ameresco-fifth-ar-2022"


def _ameresco_original_state() -> dict[str, CommitmentState]:
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


_SECTION_REFS = {
    "financial_covenant.leverage_ratio": "Section 7.10(a)",
    "financial_covenant.debt_service_coverage": "Section 7.10(b)",
}


def _ameresco_a1_instruction() -> AmendmentInstruction:
    return AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_key="financial_covenant.leverage_ratio",
        target_section_ref="Section 7.10(a)",
        field="applicability",
        old_value={
            "step_down_schedule": [
                {"period_end": "2022-03-31", "threshold": 4.50},
                {"period_end": "2022-06-30", "threshold": 4.25},
                {"period_end": "2022-09-30", "threshold": 4.00},
                {"period_end": "2022-12-31", "threshold": 4.00},
            ],
            "steady_state_threshold": 3.50,
        },
        new_value={
            "step_down_schedule": [
                {"period_end": "2023-06-30", "threshold": 4.00},
                {"period_end": "2023-09-30", "threshold": 4.25},
            ],
            "steady_state_threshold": 3.50,
        },
        effective_start=datetime(2023, 8, 24),
        source_text=(
            "Section 7.10 of the Credit Agreement is hereby amended "
            "by deleting paragraph (a) in its entirety and replacing "
            "it with the following: (a) Total Funded Debt to EBITDA "
            "Ratio. The Loan Parties shall not permit the Core "
            "Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on June 30, 2023 to exceed 4.00 to 1.00, "
            "(ii) ending on September 30, 2023 to exceed 4.25 to "
            "1.00, and (ii) for any quarter ending thereafter, to "
            "exceed 3.50 to 1.00."
        ),
        domain_effect=DomainEffect.COVENANT_THRESHOLD_CHANGE,
        provenance=InstructionProvenance.MANUAL_FALLBACK,
        citation_document="Amendment No. 3, Aug 24, 2023",
        citation_section="Section 7.10(a)",
    )


def _setup_engine():
    """Set up the engine with Ameresco S0 kernel + address map."""
    original = _ameresco_original_state()
    store, address_map, _ = establish_authoritative_kernel(
        original, _AMERESCO_AGREEMENT, _SECTION_REFS
    )
    resolver = IdentityResolver(address_map)
    engine = AuthorizedTransformationEngine(resolver)
    return store, address_map, engine


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestEngineAuthorizesScalarReplacement:
    """Test that the engine authorizes SCALAR_REPLACEMENT transformations."""

    def test_engine_produces_authorized_transformation(self):
        """Positive: engine produces an AuthorizedTransformation for
        a valid SCALAR_REPLACEMENT."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
            amendment_number=1,
            chain_position=1,
        )

        result = engine.authorize(evidence, authority)

        assert result.authorized
        assert result.transformation is not None
        assert isinstance(result.transformation, AuthorizedTransformation)

    def test_engine_classifies_as_scalar_replacement(self):
        """Positive: engine classifies REPLACE_VALUE as SCALAR_REPLACEMENT."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.transformation.transformation_type == \
            TransformationFamily.SCALAR_REPLACEMENT

    def test_engine_resolves_identity_via_address_map(self):
        """Positive: engine resolves identity via AgreementAddressMap,
        not global section heuristics."""
        store, address_map, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        # Identity should be resolved to the leverage ratio commitment
        assert result.transformation.commitment_id == \
            "financial_covenant.leverage_ratio"
        assert result.transformation.agreement_identity == _AMERESCO_AGREEMENT

    def test_engine_determines_affected_field(self):
        """Positive: engine determines the affected field from evidence."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.transformation.affected_field_names == ["applicability"]

    def test_engine_extracts_old_value_from_predecessor(self):
        """Positive: engine extracts old value from predecessor kernel."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        old_values = result.transformation.old_values()
        assert "applicability" in old_values
        assert old_values["applicability"] is not None
        # The old value should be the predecessor's applicability
        assert old_values["applicability"]["steady_state_threshold"] == 3.50

    def test_engine_extracts_new_value_from_evidence(self):
        """Positive: engine extracts new value from evidence."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        new_values = result.transformation.new_values()
        assert "applicability" in new_values
        assert new_values["applicability"] is not None
        assert new_values["applicability"]["steady_state_threshold"] == 3.50

    def test_engine_verifies_old_value_consistency(self):
        """Positive: engine verifies old-value consistency."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.transformation.old_value_consistency_verified

    def test_engine_determines_preserved_fields(self):
        """Positive: engine determines preserved fields (all non-affected)."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        preserved = result.transformation.preserved_fields
        # All semantic fields except "applicability" should be preserved
        assert "applicability" not in preserved
        assert "threshold" in preserved
        assert "operator" in preserved
        assert "unit" in preserved
        assert "frequency" in preserved
        assert "party" in preserved
        assert len(preserved) == 19  # 20 semantic fields - 1 affected

    def test_engine_carries_source_authority(self):
        """Positive: engine carries source authority for lineage."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert "Amendment No. 3" in result.transformation.source_authority
        assert "Section 7.10(a)" in result.transformation.source_authority


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestEngineRejections:
    """Test that the engine rejects invalid transformations."""

    def test_unknown_section_ref_fails_closed(self):
        """Violation: evidence with unknown section ref is rejected."""
        store, _, engine = _setup_engine()
        evidence = AmendmentEvidence(
            source_text="Some text",
            source_section_ref="Section 99.99",
            instruction_type="REPLACE_VALUE",
            target_field="threshold",
            new_value=3.00,
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.rejected
        assert result.rejection_step == "target_identity"

    def test_wrong_declared_old_value_rejected(self):
        """Violation: declared old value that doesn't match predecessor
        is rejected at old_value_consistency."""
        store, _, engine = _setup_engine()
        evidence = AmendmentEvidence(
            source_text="Some text",
            source_section_ref="Section 7.10(a)",
            instruction_type="REPLACE_VALUE",
            target_field="threshold",
            new_value=3.00,
            declared_old_value=99.99,  # wrong — predecessor has 3.50
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.rejected
        assert result.rejection_step == "old_value_consistency"

    def test_undeterminable_transformation_type_rejected(self):
        """Violation: evidence with undeterminable instruction type
        is rejected."""
        store, _, engine = _setup_engine()
        evidence = AmendmentEvidence(
            source_text="Some text",
            source_section_ref="Section 7.10(a)",
            instruction_type="UNKNOWN_TYPE",
            target_field="threshold",
            new_value=3.00,
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.rejected
        assert result.rejection_step == "transformation_type"

    def test_no_new_value_rejected(self):
        """Violation: evidence with no new value for REPLACE_VALUE
        is rejected."""
        store, _, engine = _setup_engine()
        evidence = AmendmentEvidence(
            source_text="Some text",
            source_section_ref="Section 7.10(a)",
            instruction_type="REPLACE_VALUE",
            target_field="threshold",
            new_value=None,
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.rejected
        assert result.rejection_step == "value_extraction"

    def test_no_target_field_rejected(self):
        """Violation: REPLACE_VALUE with no target field is rejected."""
        store, _, engine = _setup_engine()
        evidence = AmendmentEvidence(
            source_text="Some text",
            source_section_ref="Section 7.10(a)",
            instruction_type="REPLACE_VALUE",
            target_field=None,
            new_value=3.00,
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        assert result.rejected
        assert result.rejection_step == "affected_fields"

    def test_canonical_key_hint_alone_cannot_establish_identity(self):
        """Violation: canonical_key_hint without address-map corroboration
        is INSUFFICIENT for identity.

        This is the critical anti-circularity test.  If the engine
        accepted canonical_key_hint alone as identity authority, the
        engine would be decorative — it would merely certify the
        caller's pre-selection.  The engine must require address-map
        or predecessor corroboration.
        """
        store, _, engine = _setup_engine()
        # Evidence with canonical_key_hint but NO section_ref and
        # NO address-map signal.  The alias_match alone is WEAK.
        evidence = AmendmentEvidence(
            source_text="Some text about leverage ratio",
            source_section_ref=None,  # no address-map signal
            instruction_type="REPLACE_VALUE",
            target_field="threshold",
            new_value=3.00,
            canonical_key_hint="financial_covenant.leverage_ratio",
            alias_match="leverage_ratio",
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        # Must reject — canonical_key_hint alone is INSUFFICIENT
        assert result.rejected
        assert result.rejection_step == "target_identity"

    def test_engine_resolves_identity_without_predecessor_kernel(self):
        """Positive: engine resolves identity from address map even when
        predecessor_kernel is not pre-selected by the caller.

        This proves the engine is the controlling identity resolution
        step, not a decorative certifier.  The caller passes all
        predecessor kernels via predecessor_kernels, and the engine
        selects the correct one after resolving identity from the
        address map.
        """
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        # Do NOT pre-select the predecessor — pass all kernels
        authority = AuthorityContext(
            predecessor_kernels=dict(store.get_all_current()),
            predecessor_commitment_ids=list(store.get_all_current().keys()),
            amendment_number=1,
            chain_position=1,
        )

        result = engine.authorize(evidence, authority)

        # The engine must resolve identity from the address map
        # (Section 7.10(a) → leverage_ratio) and select the correct
        # predecessor from predecessor_kernels.
        assert result.authorized
        assert result.transformation.commitment_id == \
            "financial_covenant.leverage_ratio"


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1EngineAuthorization:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_full_authorization(self):
        """Positive: Ameresco A1 produces a complete authorized transformation.

        This is the end-to-end test of Phases 1-3:
        - S0 kernel established (Phase 1)
        - Evidence extracted (Phase 2)
        - Engine authorizes transformation (Phase 3)
        """
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
            amendment_number=1,
            chain_position=1,
        )

        result = engine.authorize(evidence, authority)

        # The transformation must be authorized
        assert result.authorized
        assert result.transformation is not None

        # Identity: resolved via address map to leverage ratio
        t = result.transformation
        assert t.commitment_id == "financial_covenant.leverage_ratio"
        assert t.agreement_identity == _AMERESCO_AGREEMENT

        # Transformation type: SCALAR_REPLACEMENT
        assert t.transformation_type == TransformationFamily.SCALAR_REPLACEMENT

        # Affected field: applicability (the step-down schedule)
        assert t.affected_field_names == ["applicability"]

        # Old value: from predecessor (S0 step-down schedule)
        old_val = t.old_values()["applicability"]
        assert old_val["steady_state_threshold"] == 3.50
        assert len(old_val["step_down_schedule"]) == 4

        # New value: from evidence (A1 step-down schedule)
        new_val = t.new_values()["applicability"]
        assert new_val["steady_state_threshold"] == 3.50
        assert len(new_val["step_down_schedule"]) == 2

        # Preserved fields: all non-affected semantic fields
        assert "threshold" in t.preserved_fields
        assert "operator" in t.preserved_fields
        assert "unit" in t.preserved_fields
        assert "frequency" in t.preserved_fields
        assert "applicability" not in t.preserved_fields

        # Old-value consistency: verified (declared old matches predecessor)
        assert t.old_value_consistency_verified

        # Source authority: for lineage continuity
        assert "Amendment No. 3" in t.source_authority

    def test_ameresco_a1_threshold_field_unchanged(self):
        """Positive: the threshold field (3.50) is preserved, not affected.

        The A1 amendment changes the step-down schedule (applicability),
        not the steady-state threshold.  The engine must preserve
        threshold=3.50 from the predecessor.
        """
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        # threshold is in preserved_fields, not affected_fields
        assert "threshold" in result.transformation.preserved_fields
        assert "threshold" not in result.transformation.affected_field_names

    def test_ameresco_a1_debt_service_coverage_not_affected(self):
        """Positive: the debt_service_coverage commitment is not affected
        by the leverage ratio amendment."""
        store, _, engine = _setup_engine()
        ins = _ameresco_a1_instruction()
        evidence = instruction_to_evidence(
            ins, citation_document="Amendment No. 3, Aug 24, 2023"
        )
        predecessor = store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        authority = AuthorityContext(
            predecessor_kernel=predecessor,
            predecessor_commitment_ids=list(store.get_all_current().keys()),
        )

        result = engine.authorize(evidence, authority)

        # The transformation targets leverage_ratio, not debt_service_coverage
        assert result.transformation.commitment_id == \
            "financial_covenant.leverage_ratio"
        assert result.transformation.commitment_id != \
            "financial_covenant.debt_service_coverage"
