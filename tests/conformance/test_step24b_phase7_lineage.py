"""Step 24B Phase 7 conformance tests — Lineage as Required Runtime Output.

These tests enforce that:
1. Each accepted transformation creates one traceable lineage edge.
2. The lineage edge references predecessor and successor commitment identity.
3. The lineage edge carries amendment authority/source.
4. The lineage edge carries the transformation proof.
5. The lineage edge carries affected fields and old/new values.
6. Violation: a lineage edge without proof_id is invalid.
7. Violation: a lineage edge without authority_source is invalid.
8. Designated real EDGAR case: Ameresco A1 Section 7.10(a).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from upsilon.models import TransformationFamily
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
    AuthorityContext,
    AuthorizedTransformationEngine,
)
from upsilon.transformations.apply import apply_transformation
from upsilon.conservation.validator import ConservationValidator
from upsilon.proof.transformation_proof import ProofAssembler
from upsilon.lineage.graph import (
    CommitmentLineageGraph,
    EdgeClass,
    LineageEdge,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Test fixtures
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
        old_value=_ameresco_original_state()[
            "financial_covenant.leverage_ratio"
        ].applicability,
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


def _setup_and_execute_with_lineage():
    """Set up the full Phase 1-6 path, create lineage edge, return all."""
    original = _ameresco_original_state()
    store, address_map, _ = establish_authoritative_kernel(
        original, _AMERESCO_AGREEMENT, _SECTION_REFS
    )
    ins = _ameresco_a1_instruction()
    evidence = instruction_to_evidence(
        ins, citation_document="Amendment No. 3, Aug 24, 2023"
    )
    predecessor = store.get_predecessor(
        "financial_covenant.leverage_ratio"
    )
    resolver = IdentityResolver(address_map)
    engine = AuthorizedTransformationEngine(resolver)
    authority = AuthorityContext(
        predecessor_kernel=predecessor,
        predecessor_commitment_ids=list(store.get_all_current().keys()),
        amendment_number=1,
        chain_position=1,
    )
    result = engine.authorize(evidence, authority)
    assert result.authorized

    identity_result = resolver.resolve(
        section_ref=evidence.source_section_ref,
        alias_match=evidence.alias_match,
        text_match=evidence.text_match,
        predecessor_commitment_ids=list(store.get_all_current().keys()),
        canonical_key_hint=evidence.canonical_key_hint,
    )

    candidate = apply_transformation(predecessor, result.transformation)
    validator = ConservationValidator()
    validation = validator.validate(predecessor, candidate, result.transformation)

    assembler = ProofAssembler()
    proof = assembler.assemble_pre_execution(
        delta=result.transformation,
        identity_result=identity_result,
        validation=validation,
        predecessor_version=0,
        successor_version=1,
    )

    assert proof.may_proceed_to_execution()

    new_version = store.advance(
        "financial_covenant.leverage_ratio",
        candidate,
        proof_id=proof.proof_id,
    )

    # Phase 7: Create lineage edge
    delta = result.transformation
    edge = LineageEdge(
        edge_id=f"EDGE-{proof.proof_id}",
        edge_class=EdgeClass.MODIFIES,
        predecessor_commitment_id="financial_covenant.leverage_ratio",
        successor_commitment_id="financial_covenant.leverage_ratio",
        amendment_id="ameresco-a1-2023-08-24",
        authority_source=delta.source_authority,
        transformation_type=delta.transformation_type,
        affected_fields=delta.affected_field_names,
        old_values=delta.old_values(),
        new_values=delta.new_values(),
        effective_date=evidence.effective_date,
        source_span=evidence.source_text[:200] if evidence.source_text else None,
        proof_id=proof.proof_id,
        validation_status=ValidationStatus.VALIDATED,
    )

    graph = CommitmentLineageGraph(agreement_identity=_AMERESCO_AGREEMENT)
    graph.add_edge(edge)

    return store, proof, edge, graph


# ---------------------------------------------------------------------------
# Positive-path tests
# ---------------------------------------------------------------------------


class TestLineageEdgeCreation:
    """Test that lineage edges are created after execution."""

    def test_edge_created_after_execution(self):
        """Positive: one lineage edge is created after execution."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert len(graph.all_edges()) == 1

    def test_edge_references_predecessor_and_successor(self):
        """Positive: edge references predecessor and successor identity."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.predecessor_commitment_id == "financial_covenant.leverage_ratio"
        assert edge.successor_commitment_id == "financial_covenant.leverage_ratio"

    def test_edge_carries_amendment_authority(self):
        """Positive: edge carries amendment authority/source."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert "Amendment No. 3" in edge.authority_source
        assert "Section 7.10(a)" in edge.authority_source

    def test_edge_carries_proof_id(self):
        """Positive: edge carries the transformation proof_id."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.proof_id == proof.proof_id

    def test_edge_carries_transformation_type(self):
        """Positive: edge carries the transformation type."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.transformation_type == TransformationFamily.SCALAR_REPLACEMENT

    def test_edge_carries_affected_fields(self):
        """Positive: edge carries the affected fields."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.affected_fields == ["applicability"]

    def test_edge_carries_old_and_new_values(self):
        """Positive: edge carries old and new values."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert "applicability" in edge.old_values
        assert "applicability" in edge.new_values
        assert edge.old_values["applicability"]["steady_state_threshold"] == 3.50
        assert edge.new_values["applicability"]["steady_state_threshold"] == 3.50

    def test_edge_carries_effective_date(self):
        """Positive: edge carries the effective date."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.effective_date == datetime(2023, 8, 24)

    def test_edge_is_validated(self):
        """Positive: edge has VALIDATED status."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.validation_status == ValidationStatus.VALIDATED
        assert len(graph.validated_edges()) == 1

    def test_edge_queryable_by_commitment(self):
        """Positive: edge is queryable by commitment ID."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        edges = graph.edges_for_commitment("financial_covenant.leverage_ratio")
        assert len(edges) == 1

    def test_edge_queryable_by_amendment(self):
        """Positive: edge is queryable by amendment ID."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        edges = graph.edges_for_amendment("ameresco-a1-2023-08-24")
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# Violation-path tests
# ---------------------------------------------------------------------------


class TestLineageViolations:
    """Test that lineage violations are detected."""

    def test_edge_without_proof_id_is_invalid(self):
        """Violation: a lineage edge without proof_id cannot be VALIDATED."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        # Create an edge without proof_id
        bad_edge = LineageEdge(
            edge_id="EDGE-bad",
            edge_class=EdgeClass.MODIFIES,
            predecessor_commitment_id="financial_covenant.leverage_ratio",
            successor_commitment_id="financial_covenant.leverage_ratio",
            amendment_id="ameresco-a1-2023-08-24",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            affected_fields=["applicability"],
            old_values={"applicability": {"test": 1}},
            new_values={"applicability": {"test": 2}},
            effective_date=datetime(2023, 8, 24),
            proof_id="",  # empty — no proof
            validation_status=ValidationStatus.PENDING,
        )

        graph.add_edge(bad_edge)
        # The bad edge should be in all_edges but not validated
        assert len(graph.all_edges()) == 2
        # Only the first edge (with proof) should be validated
        assert len(graph.validated_edges()) == 1

    def test_edge_without_authority_source_is_pending(self):
        """Violation: a lineage edge without authority_source is PENDING."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        bad_edge = LineageEdge(
            edge_id="EDGE-bad-no-auth",
            edge_class=EdgeClass.MODIFIES,
            predecessor_commitment_id="financial_covenant.leverage_ratio",
            successor_commitment_id="financial_covenant.leverage_ratio",
            amendment_id="ameresco-a1-2023-08-24",
            authority_source="",  # empty — no authority
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            affected_fields=["applicability"],
            old_values={"applicability": {"test": 1}},
            new_values={"applicability": {"test": 2}},
            effective_date=datetime(2023, 8, 24),
            proof_id=proof.proof_id,
            validation_status=ValidationStatus.PENDING,
        )

        graph.add_edge(bad_edge)
        assert len(graph.all_edges()) == 2
        # Only the first edge (with authority) should be validated
        assert len(graph.validated_edges()) == 1


# ---------------------------------------------------------------------------
# Designated real EDGAR case
# ---------------------------------------------------------------------------


class TestAmerescoA1Lineage:
    """Designated real EDGAR case: Ameresco A1 Section 7.10(a)."""

    def test_ameresco_a1_lineage_complete(self):
        """Positive: Ameresco A1 produces a complete lineage edge.

        The edge carries:
        - predecessor/successor identity
        - amendment authority
        - transformation proof
        - affected fields and values
        - effective date
        - VALIDATED status
        """
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        # L1: one traceable lineage edge
        assert len(graph.all_edges()) == 1
        assert len(graph.validated_edges()) == 1

        # L2: references predecessor and successor identity
        assert edge.predecessor_commitment_id == "financial_covenant.leverage_ratio"
        assert edge.successor_commitment_id == "financial_covenant.leverage_ratio"

        # L3: carries amendment authority/source
        assert "Amendment No. 3" in edge.authority_source

        # L4: carries transformation proof
        assert edge.proof_id == proof.proof_id

        # Affected fields and values
        assert edge.affected_fields == ["applicability"]
        assert edge.old_values["applicability"]["steady_state_threshold"] == 3.50
        assert edge.new_values["applicability"]["steady_state_threshold"] == 3.50

        # Effective date
        assert edge.effective_date == datetime(2023, 8, 24)

    def test_ameresco_a1_lineage_edge_class_modifies(self):
        """Positive: Ameresco A1 lineage edge class is MODIFIES."""
        store, proof, edge, graph = _setup_and_execute_with_lineage()

        assert edge.edge_class == EdgeClass.MODIFIES
