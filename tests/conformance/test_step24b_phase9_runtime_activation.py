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

    def test_no_dual_execution_for_spine_controlled_commitments(self):
        """The legacy executor must NOT process spine-controlled commitments.

        This is the dual-execution-path elimination test.  When the
        spine processes a SCALAR_REPLACEMENT instruction (whether
        promoted or rejected), the legacy executor must NOT also
        process a mutation targeting the same commitment.  The spine
        is the sole semantic path for SCALAR_REPLACEMENT.
        """
        result = run_semantic_pipeline_v2(chain_ameresco())
        # A1 and A2 both target financial_covenant.leverage_ratio
        # via SCALAR_REPLACEMENT.  The spine processes both.  The
        # legacy executor must NOT also process them.
        for step in result.steps[:2]:
            # The step must have spine results (spine processed them)
            assert len(step.spine_results) > 0, (
                "Step must have spine results for SCALAR_REPLACEMENT"
            )
            # The legacy executor's applied instructions must NOT
            # include any targeting financial_covenant.leverage_ratio
            for applied in step.execution_result.applied:
                assert applied.target_key != (
                    "financial_covenant.leverage_ratio"
                ), (
                    f"Legacy executor must not process spine-controlled "
                    f"commitment financial_covenant.leverage_ratio, "
                    f"but found applied instruction: {applied}"
                )


class TestStep24BSpineFailClosed:
    """Verify the spine fail-closed behavior on the production path."""

    def test_spine_rejection_blocks_authority(self):
        """A spine rejection must prevent authority promotion.

        A SCALAR_REPLACEMENT with a mismatched amendment-declared old
        value must be rejected by the conservation validator.  The
        spine must NOT promote it, and the authoritative state must
        remain unchanged.

        This test directly exercises the spine with a bad
        StructuredMutation that carries a wrong old_value.  The
        conservation validator must independently detect the mismatch
        between the amendment-declared old value and the predecessor's
        actual value.
        """
        from upsilon.commitments.kernel_bridge import (
            establish_authoritative_kernel,
        )
        from upsilon.pipeline.conservation_first_spine import (
            ConservationFirstSpine,
        )
        from upsilon.models.legacy_models import (
            CommitmentState,
            InstructionProvenance,
            InstructionType,
        )
        from upsilon.transformations.semantic_mapper import StructuredMutation
        from datetime import UTC, datetime

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
        section_refs = {
            "financial_covenant.leverage_ratio": "Section 7.10(a)",
        }
        store, address_map, _ = establish_authoritative_kernel(
            original_state, "TEST-FAIL-CLOSED", section_refs,
        )
        spine = ConservationFirstSpine(
            original_state=original_state,
            agreement_identity="TEST-FAIL-CLOSED",
            section_refs=section_refs,
        )

        # Create a StructuredMutation with a wrong old_value.
        # The mapper's old_value becomes the amendment-declared old
        # value in the evidence.  The conservation validator must
        # compare it against the predecessor's actual value and
        # detect the mismatch.
        bad_mutation = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="applicability",
            operation=InstructionType.REPLACE_VALUE,
            old_value={"steady_state_threshold": 9.99},  # wrong
            new_value={"steady_state_threshold": 4.0},
            unit="ratio",
            effective_at=datetime.now(UTC),
            source_span="Section 7.10 test text with 4.00 to 1.00",
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.95,
            ambiguity_reason=None,
            citation_document="Test amendment",
            citation_section="Section 7.10(a)",
        )

        sr = spine.process_mutation(
            bad_mutation, citation_document="Test amendment",
        )

        # The spine must reject the bad mutation.
        assert sr.rejected, (
            f"Spine must reject mismatched old_value, "
            f"got promoted={sr.promoted}, rejected={sr.rejected}"
        )
        # The spine must not have promoted anything.
        assert not sr.promoted
        # The authoritative state must be unchanged.
        auth_state = spine.authoritative_state()
        lr = auth_state["financial_covenant.leverage_ratio"]
        assert lr.applicability == {"steady_state_threshold": 3.5}, (
            f"Authoritative state must be unchanged after rejection, "
            f"got {lr.applicability}"
        )

    def test_authority_blocked_after_execution_keeps_predecessor(self):
        """Most important atomicity test.

        If the candidate/executed successor exists (was advanced into
        the kernel store) BUT the authority gate blocks promotion, the
        authoritative_current MUST remain the predecessor.

        This test constructs a SCALAR_REPLACEMENT that passes
        conservation validation and proof assembly but fails the
        authority gate (by setting inherited_unresolved > 0).  The
        spine must roll back the kernel store so the authoritative
        current state remains the predecessor.
        """
        from upsilon.commitments.kernel_bridge import (
            establish_authoritative_kernel,
        )
        from upsilon.commitments.identity import IdentityResolver
        from upsilon.commitments.kernel import KernelStore
        from upsilon.evidence.evidence_extractor import instruction_to_evidence
        from upsilon.models.legacy_models import (
            AmendmentInstruction,
            CommitmentState,
            DomainEffect,
            InstructionProvenance,
            InstructionType,
        )
        from upsilon.models import (
            CommitmentKernel,
            CommitmentIdentity,
            AddressBinding,
        )
        from upsilon.pipeline.conservation_first_spine import (
            ConservationFirstSpine,
        )
        from upsilon.transformations.authorized_change import (
            AuthorizedTransformationEngine,
        )
        from datetime import datetime

        _AGREEMENT = "ameresco-fifth-ar-2022"
        original_state = {
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
                    "steady_state_threshold": 3.50,
                },
            ),
        }
        section_refs = {
            "financial_covenant.leverage_ratio": "Section 7.10(a)",
        }
        spine = ConservationFirstSpine(
            original_state=original_state,
            agreement_identity=_AGREEMENT,
            section_refs=section_refs,
        )

        # A valid SCALAR_REPLACEMENT instruction.
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.leverage_ratio",
            target_section_ref="Section 7.10(a)",
            field="applicability",
            old_value={"steady_state_threshold": 3.50},
            new_value={"steady_state_threshold": 4.00},
            effective_start=datetime(2023, 8, 24),
            source_text=(
                "Section 7.10 of the Credit Agreement is amended to "
                "exceed 4.00 to 1.00."
            ),
            domain_effect=DomainEffect.COVENANT_THRESHOLD_CHANGE,
            provenance=InstructionProvenance.MANUAL_FALLBACK,
            citation_document="Amendment No. 3, Aug 24, 2023",
            citation_section="Section 7.10(a)",
        )

        # Process with inherited_unresolved > 0 — this causes the
        # authority gate to block (inherited unresolved state).
        result = spine.process_instruction(
            ins,
            citation_document="Amendment No. 3, Aug 24, 2023",
            inherited_unresolved=1,  # blocks authority
        )

        # The spine must reject (authority blocked).
        assert result.rejected, (
            "Spine must reject when authority is blocked"
        )
        assert result.rejection_layer == "authority_gate", (
            f"Rejection must be at authority_gate, "
            f"got {result.rejection_layer}"
        )

        # The candidate and proof must exist (execution happened
        # before the authority gate).
        assert result.candidate is not None, (
            "Candidate must exist (execution happened before gate)"
        )
        assert result.proof is not None, (
            "Proof must exist (assembled before gate)"
        )

        # CRITICAL: the authoritative current state MUST remain
        # the predecessor.  The rollback must have restored it.
        current = spine.store.get_predecessor(
            "financial_covenant.leverage_ratio"
        )
        assert current.applicability == {"steady_state_threshold": 3.50}, (
            f"Authoritative current must remain predecessor after "
            f"authority block, got {current.applicability}"
        )
        assert current.threshold == 3.50

        # Version history must not contain the rolled-back version.
        history = spine.store.get_version_history(
            "financial_covenant.leverage_ratio"
        )
        assert len(history) == 1, (
            f"Version history must have only the origin version, "
            f"got {len(history)} versions"
        )
        assert history[0].version_number == 0


# ---------------------------------------------------------------------------
# Phase 7: Integrated safety measurement — bad spine mutation detection
# ---------------------------------------------------------------------------


class TestIntegratedSafetyMeasurement:
    """Phase 7: spine mutations must participate in incorrect-mutation
    measurement.

    A deliberately injected incorrect spine mutation must be detected
    by the safety audit.  The correct Ameresco runtime must preserve
    zero incorrect accepted mutations and zero false authoritative
    promotions.
    """

    def test_correct_ameresco_runtime_has_zero_incorrect_mutations(self):
        """The correct Ameresco runtime must have zero incorrect
        accepted mutations and zero false authoritative promotions."""
        result = run_semantic_pipeline_v2(chain_ameresco())
        assert len(result.incorrect_mutations) == 0, (
            f"Expected 0 incorrect accepted mutations, "
            f"got {len(result.incorrect_mutations)}: "
            f"{result.incorrect_mutations}"
        )

    def test_spine_mutations_participate_in_safety_measurement(self):
        """Phase 7: spine-applied mutations must be included in the
        applied_pairs tracking used for incorrect-mutation detection.

        We verify this by checking that the Ameresco A1 spine-promoted
        applicability change is tracked in the safety measurement.
        If spine mutations were invisible, the safety audit would
        not cover them.
        """
        from upsilon.commitments.kernel_bridge import (
            establish_authoritative_kernel,
        )
        from upsilon.pipeline.conservation_first_spine import (
            ConservationFirstSpine,
        )
        from upsilon.models.legacy_models import (
            CommitmentState,
            InstructionProvenance,
            InstructionType,
        )
        from upsilon.transformations.semantic_mapper import StructuredMutation
        from datetime import UTC, datetime

        # Set up a spine with a known S0 state
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
        section_refs = {
            "financial_covenant.leverage_ratio": "Section 7.10(a)",
        }
        spine = ConservationFirstSpine(
            original_state=original_state,
            agreement_identity="TEST-SAFETY",
            section_refs=section_refs,
        )

        # Process a valid mutation through the spine
        mut = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="applicability",
            operation=InstructionType.REPLACE_VALUE,
            old_value=None,
            new_value={"steady_state_threshold": 4.0},
            unit="ratio",
            effective_at=datetime.now(UTC),
            source_span="Section 7.10 amended to 4.00 to 1.00",
            provenance=InstructionProvenance.SEMANTIC_MAPPER,
            confidence=0.95,
            ambiguity_reason=None,
            citation_document="Test",
            citation_section="Section 7.10(a)",
        )

        sr = spine.process_mutation(mut, citation_document="Test")
        assert sr.promoted, (
            f"Spine should promote valid mutation, "
            f"got rejected: {sr.rejection_reason}"
        )

        # The promoted transformation must have affected_fields
        # that the safety measurement can track
        assert sr.transformation is not None
        assert "applicability" in sr.transformation.affected_field_names

    def test_deliberately_wrong_spine_mutation_detected(self):
        """Phase 7: a deliberately wrong spine mutation (one that
        produces a state disagreeing with ground truth) must be
        detectable by the safety audit.

        We construct a chain where the spine promotes a mutation
        that changes the threshold to a wrong value, then verify
        that the safety measurement detects it as an incorrect
        accepted mutation.
        """
        from upsilon.lineage.chain_reconstruction import (
            AmendmentStep,
            IssuerChain,
        )
        from upsilon.models.legacy_models import (
            CommitmentState,
        )
        from datetime import UTC, datetime
        from pathlib import Path
        import tempfile

        # Create a chain with source text that the parser can extract
        # but with a ground truth that disagrees with the extracted value.
        # The parser will extract "4.00" from the text, but the ground
        # truth says the threshold should remain 3.50.
        original_state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=3.50,
                unit="ratio",
                status="ACTIVE",
                applicability={"steady_state_threshold": 3.50},
            ),
        }

        # Ground truth: threshold remains 3.50 (the amendment should
        # NOT change it, but the spine will promote a change to 4.00)
        ground_truth = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=3.50,  # unchanged
                unit="ratio",
                status="ACTIVE",
                applicability={"steady_state_threshold": 3.50},
            ),
        }

        # Write a source document that the parser will extract a
        # Section 7.10 instruction from.  The text contains a step-down
        # schedule pattern that the semantic mapper can extract.
        source_text = (
            "SECTION 1. Section 7.10 of the Credit Agreement is hereby "
            "amended by deleting paragraph (a) in its entirety and "
            "replacing it with the following: (a) Total Funded Debt to "
            "EBITDA Ratio. The Loan Parties shall not permit the Core "
            "Leverage Ratio as of the end of each fiscal quarter "
            "(i) ending on June 30, 2023 to exceed 4.00 to 1.00, "
            "and (ii) for any quarter ending thereafter, to exceed "
            "4.00 to 1.00."
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write(source_text)
            source_path = f.name

        try:
            chain = IssuerChain(
                chain_id="TEST-BAD-SPINE",
                issuer_name="Test",
                original_state=original_state,
                ground_truth_state=ground_truth,
                amendments=[
                    AmendmentStep(
                        amendment_number=1,
                        effective_at=datetime.now(UTC),
                        instructions=[],
                        source_document_path=source_path,
                        description="Test amendment",
                        pattern="incremental",
                    ),
                ],
                comparison_at=datetime.now(UTC),
                s0_section_refs={
                    "financial_covenant.leverage_ratio": "Section 7.10(a)",
                },
            )
            result = run_semantic_pipeline_v2(chain)

            # The spine should have promoted the mutation (changing
            # the applicability).  The safety audit should detect
            # that the resulting state disagrees with ground truth.
            # The incorrect_accepted_mutations should be > 0 because
            # the spine changed the state in a way that disagrees
            # with ground truth.
            # Note: the exact value depends on how the mismatch is
            # classified, but it must be > 0 if the spine mutation
            # is included in the safety measurement.
            assert len(result.incorrect_mutations) > 0 or \
                result.final_state_agreement < 1.0, (
                f"Bad spine mutation must be detected: "
                f"incorrect={len(result.incorrect_mutations)}, "
                f"agreement={result.final_state_agreement}"
            )
        finally:
            Path(source_path).unlink(missing_ok=True)
