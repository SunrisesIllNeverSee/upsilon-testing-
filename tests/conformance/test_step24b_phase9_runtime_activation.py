"""Step 24B Phase 9: empirical integration verification.

These tests verify that the **actual production EDGAR pipeline**
(``run_semantic_pipeline_v2``) routes SCALAR_REPLACEMENT amendments
through the conservation-first spine (Layers A–G), not merely that
the spine components work in isolation.

This is the integration test that proves the runtime is activated:
the production pipeline must call the spine, the spine must promote
authorized transformations, and the authoritative state must reflect
the conservation-first path.

Designated real EDGAR case: Ameresco A1/A2 leverage ratio amendments.
"""
from __future__ import annotations

from upsilon.ingestion.edgar.edgar_chains import chain_ameresco
from upsilon.pipeline.semantic_pipeline_v2 import run_semantic_pipeline_v2
from upsilon.authority.promotion_gate import AuthorityDecision


class TestStep24BRuntimeActivation:
    """Verify the production pipeline activates the conservation-first spine."""

    def test_pipeline_returns_spine_instance(self):
        """The pipeline result must carry a non-None spine instance.

        This proves the pipeline constructed and used the
        conservation-first spine, not just the legacy path.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert result.spine is not None, (
            "Pipeline result must carry a ConservationFirstSpine instance"
        )

    def test_ameresco_a1_promoted_through_spine(self):
        """Ameresco A1 must be promoted through the spine.

        A1 changes the leverage ratio applicability (step-down
        schedule).  This is a SCALAR_REPLACEMENT that the spine
        must authorize, validate, execute, and promote.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        a1 = result.steps[0]
        assert a1.spine_promoted == 1, (
            f"A1 must promote 1 instruction through the spine, "
            f"got spine_promoted={a1.spine_promoted}"
        )
        assert a1.spine_rejected == 0, (
            f"A1 must not reject any spine instructions, "
            f"got spine_rejected={a1.spine_rejected}"
        )
        # Verify the spine result details
        sr = a1.spine_results[0]
        assert sr.promoted
        assert sr.transformation is not None
        assert sr.transformation.commitment_id == "financial_covenant.leverage_ratio"
        assert sr.authority_decision is not None
        assert sr.authority_decision.is_authoritative
        assert sr.lineage_edge is not None
        assert sr.proof is not None
        assert sr.proof.may_proceed_to_execution()

    def test_ameresco_a2_promoted_through_spine(self):
        """Ameresco A2 must be promoted through the spine.

        A2 further changes the leverage ratio applicability.  The
        spine's predecessor for A2 must be the post-A1 successor,
        proving the kernel store advances correctly across steps.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        a2 = result.steps[1]
        assert a2.spine_promoted == 1, (
            f"A2 must promote 1 instruction through the spine, "
            f"got spine_promoted={a2.spine_promoted}"
        )
        sr = a2.spine_results[0]
        assert sr.promoted
        assert sr.successor_version == 2, (
            f"A2 successor version must be 2 (after A1's version 1), "
            f"got {sr.successor_version}"
        )

    def test_ameresco_a3_routed_away(self):
        """Ameresco A3's ADD instruction must be routed away.

        A3 adds a junior credit agreement commitment.  This is a
        CREATE transformation, not SCALAR_REPLACEMENT.  The spine
        must route it away to the legacy path (CREATE is not yet
        activated in the spine).
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        a3 = result.steps[2]
        assert a3.spine_routed_away >= 1, (
            f"A3 must route away the ADD instruction, "
            f"got spine_routed_away={a3.spine_routed_away}"
        )

    def test_spine_total_promoted_is_2(self):
        """The total spine promotions across all steps must be 2.

        A1 and A2 each promote one SCALAR_REPLACEMENT instruction.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert result.spine_total_promoted == 2, (
            f"Expected 2 total spine promotions, "
            f"got {result.spine_total_promoted}"
        )

    def test_leverage_ratio_threshold_preserved(self):
        """The leverage ratio threshold must be preserved at 3.5.

        Both A1 and A2 change only the applicability field.  The
        threshold must remain 3.5 (conservation invariant:
        unchanged_field_preservation).
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        lr = result.reconstructed_state["financial_covenant.leverage_ratio"]
        assert lr.threshold == 3.5, (
            f"Threshold must be preserved at 3.5, got {lr.threshold}"
        )

    def test_leverage_ratio_applicability_matches_a2(self):
        """The final applicability must match A2's new value.

        After A1 and A2, the applicability should be A2's
        step-down schedule (3.75 for Q4 2023).
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        lr = result.reconstructed_state["financial_covenant.leverage_ratio"]
        sched = lr.applicability["step_down_schedule"]
        assert len(sched) == 1
        assert sched[0]["period_end"] == "2023-12-31"
        assert sched[0]["threshold"] == 3.75

    def test_no_incorrect_mutations(self):
        """The pipeline must report zero incorrect mutations."""
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert len(result.incorrect_mutations) == 0, (
            f"Expected 0 incorrect mutations, got {result.incorrect_mutations}"
        )

    def test_spine_lineage_graph_has_edges(self):
        """The spine's lineage graph must contain edges for A1 and A2.

        Lineage is a required runtime output (Step 24B Phase 7).
        The spine must record a lineage edge for each promoted
        transformation.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert result.spine is not None
        edges = result.spine.lineage_graph.all_edges()
        assert len(edges) >= 2, (
            f"Lineage graph must have at least 2 edges (A1 + A2), "
            f"got {len(edges)}"
        )

    def test_spine_lineage_reachable_from_origin(self):
        """The leverage ratio commitment must be reachable from origin.

        The lineage graph must confirm that the commitment's lineage
        traces back to the S0 origin kernel.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert result.spine is not None
        assert result.spine.lineage_graph.is_reachable_from_origin(
            "financial_covenant.leverage_ratio",
        ), "Leverage ratio must be reachable from origin in lineage graph"

    def test_spine_authority_gate_consumed_lineage(self):
        """The authority gate must have consumed lineage validity.

        The spine's authority gate results for A1 and A2 must show
        AUTHORITY_GRANTED, which requires lineage_valid=True.  This
        proves the lineage validity precondition is wired into the
        production path.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        for step in result.steps[:2]:
            for sr in step.spine_results:
                if sr.promoted:
                    assert sr.authority_decision is not None
                    assert sr.authority_decision.decision == (
                        AuthorityDecision.AUTHORITY_GRANTED
                    ), (
                        f"Promoted spine result must have "
                        f"AUTHORITY_GRANTED, got "
                        f"{sr.authority_decision.decision}"
                    )

    def test_spine_proofs_are_complete_and_valid(self):
        """All promoted spine proofs must be COMPLETE and VALID."""
        result = run_semantic_pipeline_v2(chain_ameresco())
        for step in result.steps:
            for sr in step.spine_results:
                if sr.promoted:
                    assert sr.proof is not None
                    assert sr.proof.may_proceed_to_execution(), (
                        "Promoted proof must permit execution"
                    )

    def test_spine_conservation_validation_passed(self):
        """All promoted spine results must have passed conservation."""
        result = run_semantic_pipeline_v2(chain_ameresco())
        for step in result.steps:
            for sr in step.spine_results:
                if sr.promoted:
                    assert sr.validation is not None
                    assert sr.validation.passed, (
                        "Promoted spine result must have passed conservation"
                    )

    def test_spine_evidence_extracted_not_interpreted(self):
        """The spine must produce evidence objects (Layer A).

        Evidence extraction is separate from interpretation.  The
        spine must produce AmendmentEvidence for each processed
        instruction.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        for step in result.steps:
            for sr in step.spine_results:
                if sr.promoted or sr.rejected:
                    assert sr.evidence is not None, (
                        "Spine result must carry evidence (Layer A)"
                    )

    def test_final_state_agreement_improved(self):
        """The final state agreement must be at least 0.6667.

        With the spine controlling the leverage ratio, 2 of 3
        ground-truth commitments must match (leverage ratio and
        debt service coverage).  The third (junior credit agreement
        from A3) is routed away and not yet activated.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert result.final_state_agreement >= 0.6667, (
            f"Final state agreement must be >= 0.6667, "
            f"got {result.final_state_agreement}"
        )


class TestStep24BSpineFailClosed:
    """Verify the spine fail-closed behavior on the production path."""

    def test_spine_rejection_blocks_authority(self):
        """A spine rejection must prevent authority promotion.

        If the spine rejects an instruction, the step's authority
        must account for it (the spine rejection counts as own
        unresolved for the legacy authority assessment).
        """
        from upsilon.lineage.chain_reconstruction import (
            AmendmentStep,
            IssuerChain,
        )
        from upsilon.models.legacy_models import (
            AmendmentInstruction,
            CommitmentState,
            InstructionProvenance,
            InstructionType,
        )
        from datetime import UTC, datetime

        # Build a chain with a SCALAR_REPLACEMENT instruction that
        # has a mismatched old_value (conservation will fail).
        original_state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=3.5,
                unit="ratio",
                status="ACTIVE",
                applicability={"steady_state_threshold": 3.5},
            ),
        }
        bad_instruction = AmendmentInstruction(
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.leverage_ratio",
            target_section_ref="Section 7.10(a)",
            field="applicability",
            old_value={"steady_state_threshold": 9.99},  # wrong
            new_value={"steady_state_threshold": 4.0},
            provenance=InstructionProvenance.MANUAL_FALLBACK,
            citation_document="Test amendment",
            order=1,
        )
        chain = IssuerChain(
            chain_id="TEST-FAIL-CLOSED",
            issuer_name="Test",
            original_state=original_state,
            ground_truth_state={},
            amendments=[
                AmendmentStep(
                    amendment_number=1,
                    effective_at=datetime.now(UTC),
                    instructions=[bad_instruction],
                    source_document_path=None,
                    description="Test",
                    pattern="incremental",
                ),
            ],
            comparison_at=datetime.now(UTC),
        )
        result = run_semantic_pipeline_v2(chain)
        step = result.steps[0]
        # The spine must reject the bad instruction.
        assert step.spine_rejected >= 1, (
            f"Spine must reject mismatched old_value, "
            f"got spine_rejected={step.spine_rejected}"
        )
        # The spine must not have promoted anything.
        assert step.spine_promoted == 0
        # The authoritative state must be unchanged.
        lr = result.reconstructed_state["financial_covenant.leverage_ratio"]
        assert lr.applicability == {"steady_state_threshold": 3.5}, (
            f"Authoritative state must be unchanged after rejection, "
            f"got {lr.applicability}"
        )
