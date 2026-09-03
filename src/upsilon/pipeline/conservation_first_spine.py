"""Conservation-first runtime spine (Step 24B activation).

This module is the **actual empirical execution path** for the
SCALAR_REPLACEMENT transformation family.  It orchestrates the full
Layer A–G conservation-first architecture for a single amendment
instruction against an authoritative predecessor kernel:

    Layer A: Evidence Extraction          (evidence_extractor)
    Layer B: AuthorizedTransformationEngine (authorized_change)
    Layer C: apply_transformation          (apply)
    Layer D: ConservationValidator         (validator)
    Layer E: ProofAssembler                (transformation_proof)
    Layer F: KernelStore.advance           (kernel)  [thin executor]
    Lineage: CommitmentLineageGraph.add_edge (graph)
    Layer G: AuthorityGate.evaluate        (promotion_gate)

The spine is the controlling semantic path for SCALAR_REPLACEMENT.
No mutation may execute unless the Step 24 engine produced the
authorized transformation, conservation validation passed, and a
valid semantic proof was assembled.  Execution commits the validated
candidate successor via ``KernelStore.advance`` (a thin executor that
does NOT reinterpret legal text, resolve identity, or derive values).
Lineage is recorded as a required runtime output.  Authority
promotion is gated by ``AuthorityGate.evaluate`` with lineage
validity.

For transformation families outside SCALAR_REPLACEMENT, the spine
returns ``SpineResult.routed_away=True`` so the caller (the
production pipeline) can route them through the legacy path until
they are migrated in follow-up steps.

RESPONSIBILITY:
    Orchestrate the conservation-first runtime spine (Layers A–G)
TARGET DOMAIN:
    pipeline
CURRENT MODULE:
    src/upsilon/pipeline/conservation_first_spine.py (new)
CURRENT OPERATING STATUS:
    Step 24B — activated for SCALAR_REPLACEMENT
WHY THIS MODULE MUST CHANGE:
    The production pipeline previously bypassed the Step 24
    architecture entirely.  This module is the wiring point that
    makes the conservation-first spine the controlling path for
    SCALAR_REPLACEMENT.
TARGET OWNER AFTER CHANGE:
    pipeline domain (this module)
MIGRATION / REMOVAL CONDITION:
    Remove when all 13 transformation families are migrated to the
    spine and the legacy resolver/executor path is retired.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from upsilon.authority.promotion_gate import AuthorityGate, AuthorityGateResult
from upsilon.commitments.identity import (
    AgreementAddressMap,
    IdentityResolutionResult,
    IdentityResolver,
)
from upsilon.commitments.kernel import KernelStore
from upsilon.commitments.kernel_bridge import (
    establish_authoritative_kernel,
    kernel_to_state,
    store_to_state_dict,
)
from upsilon.conservation.validator import ConservationValidator, ValidationResult
from upsilon.evidence.evidence_extractor import instruction_to_evidence, mutation_to_evidence
from upsilon.lineage.graph import CommitmentLineageGraph
from upsilon.models import (
    AuthorizedTransformation,
    CommitmentKernel,
    EdgeClass,
    ExecutionResultSummary,
    LineageEdge,
    SemanticTransformationProof,
    TransformationFamily,
    ValidationStatus,
)
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    ExecutionStatus,
    InstructionType,
)
from upsilon.proof.transformation_proof import ProofAssembler
from upsilon.transformations.apply import apply_transformation
from upsilon.transformations.authorized_change import (
    AmendmentEvidence,
    AuthorityContext,
    AuthorizedTransformationEngine,
    TransformationResult,
)
from upsilon.transformations.semantic_mapper import StructuredMutation


# Transformation families that the spine currently controls.
# Other families are routed away to the legacy path until migrated.
_ACTIVATED_FAMILIES: frozenset[TransformationFamily] = frozenset({
    TransformationFamily.SCALAR_REPLACEMENT,
})


@dataclass
class SpineResult:
    """Result of processing one amendment instruction through the spine.

    A ``promoted`` result means the transformation was authorized,
    validated, executed, recorded in lineage, and promoted to
    authoritative current state.

    A ``rejected`` result means the spine fail-closed at some layer;
    the authoritative predecessor state is unchanged.

    A ``routed_away`` result means the transformation family is not
    yet activated in the spine; the caller should route it through
    the legacy path.
    """

    promoted: bool = False
    rejected: bool = False
    rejection_reason: str = ""
    rejection_layer: str = ""
    routed_away: bool = False

    # Artifacts produced along the spine (populated when promoted)
    evidence: AmendmentEvidence | None = None
    transformation: AuthorizedTransformation | None = None
    identity_result: IdentityResolutionResult | None = None
    candidate: CommitmentKernel | None = None
    validation: ValidationResult | None = None
    proof: SemanticTransformationProof | None = None
    lineage_edge: LineageEdge | None = None
    authority_decision: AuthorityGateResult | None = None
    successor_version: int | None = None

    @property
    def authorized(self) -> bool:
        """Whether the spine produced an authorized transformation."""
        return self.transformation is not None and not self.rejected


class ConservationFirstSpine:
    """The conservation-first runtime spine for SCALAR_REPLACEMENT.

    The spine holds the authoritative kernel state (KernelStore +
    AgreementAddressMap + CommitmentLineageGraph) and processes
    amendment instructions one at a time through Layers A–G.

    Construction establishes the S0 authoritative kernel from the
    legacy original_state.  Each call to :meth:`process_instruction`
    attempts to advance one commitment through the spine.
    """

    def __init__(
        self,
        original_state: dict[str, CommitmentState],
        agreement_identity: str,
        section_refs: dict[str, str] | None = None,
    ) -> None:
        self.agreement_identity = agreement_identity
        self.store, self.address_map, self._kernels = establish_authoritative_kernel(
            original_state, agreement_identity, section_refs,
        )
        self.lineage_graph = CommitmentLineageGraph(agreement_identity)
        self.identity_resolver = IdentityResolver(self.address_map)
        self.engine = AuthorizedTransformationEngine(self.identity_resolver)
        self.validator = ConservationValidator()
        self.proof_assembler = ProofAssembler()
        self.gate = AuthorityGate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_predecessor(
        self, commitment_id: str,
    ) -> CommitmentKernel | None:
        """Get the current authoritative kernel for a commitment."""
        return self.store.get_predecessor(commitment_id)

    def authoritative_state(self) -> dict[str, CommitmentState]:
        """Return the current authoritative state as legacy CommitmentState."""
        return store_to_state_dict(self.store)

    def is_activated(self, instruction: AmendmentInstruction) -> bool:
        """Whether the spine controls this instruction's family.

        The spine currently controls SCALAR_REPLACEMENT, which maps
        from REPLACE_VALUE / REPLACE_TEXT instruction types.  Other
        instruction types are routed away to the legacy path.
        """
        itype = instruction.instruction_type
        if itype in (InstructionType.REPLACE_VALUE, InstructionType.REPLACE_TEXT):
            # Determine the family the engine would assign.  We only
            # activate SCALAR_REPLACEMENT for now; the engine maps
            # REPLACE_VALUE/REPLACE_TEXT to SCALAR_REPLACEMENT when a
            # target_field is present.
            return instruction.field is not None
        return False

    def process_mutation(
        self,
        mut: StructuredMutation,
        citation_document: str | None = None,
        inherited_unresolved: int = 0,
    ) -> SpineResult:
        """Process a parser-extracted StructuredMutation through the spine.

        This is the production evidence path.  The StructuredMutation
        is produced by the semantic mapper from parser-extracted
        section-level instructions — it is genuine parser/source
        evidence, not manually curated commitment-level answers.

        The mutation's ``commitment_id`` is treated as a weak hint
        (canonical_key_hint), NOT as authoritative identity.  The
        engine resolves identity from the section_ref → S0 address map.
        """
        # Check if this mutation's family is activated.
        # REPLACE_VALUE/REPLACE_TEXT with a field → SCALAR_REPLACEMENT.
        if mut.operation not in (
            InstructionType.REPLACE_VALUE, InstructionType.REPLACE_TEXT,
        ) or mut.field is None:
            return SpineResult(routed_away=True)

        evidence = mutation_to_evidence(
            mut, citation_document=citation_document,
        )
        return self._process_evidence(
            evidence, inherited_unresolved=inherited_unresolved,
        )

    def process_instruction(
        self,
        instruction: AmendmentInstruction,
        citation_document: str | None = None,
        inherited_unresolved: int = 0,
    ) -> SpineResult:
        """Process one amendment instruction through the full spine.

        Returns a :class:`SpineResult`.  If the instruction's family
        is not activated, returns ``routed_away=True`` and the caller
        must route it through the legacy path.

        Identity is resolved by the engine (Layer B) from amendment
        evidence signals (section_ref, alias, text_match) corroborated
        by the agreement-local address map.  The predecessor kernel
        is selected AFTER identity resolution — NOT pre-selected by
        ``canonical_key_hint``.  This ensures the engine is the
        controlling semantic interpretation step.
        """
        # Route away non-activated families.
        if not self.is_activated(instruction):
            return SpineResult(routed_away=True)

        # --- Layer A: Evidence Extraction ---
        evidence = instruction_to_evidence(
            instruction, citation_document=citation_document,
        )
        return self._process_evidence(
            evidence, inherited_unresolved=inherited_unresolved,
        )

    def _process_evidence(
        self,
        evidence: AmendmentEvidence,
        inherited_unresolved: int = 0,
    ) -> SpineResult:
        """Process AmendmentEvidence through Layers B–G of the spine.

        This is the shared core for both ``process_instruction`` and
        ``process_mutation``.  It implements:

        Layer B: AuthorizedTransformationEngine (identity + delta)
        Layer C: apply_transformation (candidate successor)
        Layer D: ConservationValidator
        Layer E: ProofAssembler (pre-execution precondition)
        Layer F: KernelStore.stage (provisional execution — does NOT
                 change authoritative current)
        Lineage: CommitmentLineageGraph.add_edge
        Layer E2: ProofAssembler.update_post_execution
        Layer G: AuthorityGate.evaluate
                 → promote() if AUTHORITY_GRANTED
                 → discard() if AUTHORITY_BLOCKED

        The authoritative-current store is NOT changed until the
        authority gate grants authority.  This separates provisional
        execution from authority promotion.
        """
        # --- Layer B: AuthorizedTransformationEngine ---
        authority = AuthorityContext(
            predecessor_kernels=dict(self.store.get_all_current()),
            predecessor_commitment_ids=list(self.store.get_all_current().keys()),
            amendment_number=0,
            chain_position=0,
        )
        transform_result = self.engine.authorize(evidence, authority)
        if not transform_result.authorized:
            return SpineResult(
                rejected=True,
                rejection_reason=transform_result.rejection_reason,
                rejection_layer=f"engine:{transform_result.rejection_step}",
                evidence=evidence,
            )

        delta = transform_result.transformation
        assert delta is not None  # guarded by .authorized

        # Confirm the engine classified this as an activated family.
        if delta.transformation_type not in _ACTIVATED_FAMILIES:
            return SpineResult(
                rejected=True,
                rejection_reason=(
                    f"Transformation family {delta.transformation_type.value} "
                    f"is not activated in the spine"
                ),
                rejection_layer="family_activation",
                evidence=evidence,
                transformation=delta,
            )

        # The engine resolved identity and selected the predecessor.
        commitment_id = delta.commitment_id
        predecessor = self.store.get_predecessor(commitment_id)
        if predecessor is None:
            return SpineResult(
                rejected=True,
                rejection_reason=(
                    f"Engine resolved identity to {commitment_id!r} "
                    f"but no predecessor kernel exists in the store"
                ),
                rejection_layer="predecessor_lookup",
                evidence=evidence,
                transformation=delta,
            )

        # Re-resolve identity to obtain the IdentityResolutionResult
        # the proof assembler needs.
        identity_result = self.identity_resolver.resolve(
            section_ref=evidence.source_section_ref,
            alias_match=evidence.alias_match,
            text_match=evidence.text_match,
            predecessor_commitment_ids=list(self.store.get_all_current().keys()),
            canonical_key_hint=evidence.canonical_key_hint,
        )

        # --- Layer C: apply_transformation (candidate successor) ---
        candidate = apply_transformation(predecessor, delta)

        # --- Layer D: ConservationValidator ---
        validation = self.validator.validate(predecessor, candidate, delta)
        if not validation.passed:
            return SpineResult(
                rejected=True,
                rejection_reason=(
                    f"Conservation validation failed: {validation.failed_invariants}"
                ),
                rejection_layer="conservation",
                evidence=evidence,
                transformation=delta,
                identity_result=identity_result,
                candidate=candidate,
                validation=validation,
            )

        # --- Layer E: ProofAssembler (pre-execution precondition) ---
        pred_version = (
            predecessor.version.version_number if predecessor.version else 0
        )
        proof = self.proof_assembler.assemble_pre_execution(
            delta=delta,
            identity_result=identity_result,
            validation=validation,
            predecessor_version=pred_version,
            successor_version=pred_version + 1,
        )
        if not proof.may_proceed_to_execution():
            return SpineResult(
                rejected=True,
                rejection_reason=(
                    f"Proof does not permit execution: "
                    f"completeness={proof.proof_completeness.value} "
                    f"validity={proof.proof_validity.value}"
                ),
                rejection_layer="proof_precondition",
                evidence=evidence,
                transformation=delta,
                identity_result=identity_result,
                candidate=candidate,
                validation=validation,
                proof=proof,
            )

        # --- Layer F: KernelStore.stage (provisional execution) ---
        # Stage the candidate WITHOUT changing authoritative current.
        # The authoritative _current remains the predecessor until
        # promote() is called after authority grants permission.
        try:
            staged_version = self.store.stage(
                commitment_id=delta.commitment_id,
                successor=candidate,
                proof_id=proof.proof_id,
                expected_predecessor_version=proof.predecessor_version,
            )
        except ValueError as exc:
            return SpineResult(
                rejected=True,
                rejection_reason=f"Kernel staging failed: {exc}",
                rejection_layer="execution",
                evidence=evidence,
                transformation=delta,
                identity_result=identity_result,
                candidate=candidate,
                validation=validation,
                proof=proof,
            )

        # --- Lineage: CommitmentLineageGraph.add_edge ---
        edge_id = f"LE-{uuid.uuid4().hex[:12]}"
        edge = LineageEdge(
            edge_id=edge_id,
            edge_class=EdgeClass.MODIFIES,
            predecessor_commitment_id=delta.commitment_id,
            successor_commitment_id=delta.commitment_id,
            amendment_id=evidence.amendment_id or evidence.source_document,
            authority_source=delta.source_authority,
            transformation_type=delta.transformation_type,
            affected_fields=delta.affected_field_names,
            old_values=delta.old_values(),
            new_values=delta.new_values(),
            effective_date=delta.effective_date,
            source_span=delta.source_span,
            proof_id=proof.proof_id,
            validation_status=ValidationStatus.VALIDATED,
        )
        self.lineage_graph.add_edge(edge)

        # Lineage validity: the edge must be reachable from origin.
        lineage_valid = self.lineage_graph.is_reachable_from_origin(
            delta.commitment_id,
        )

        # --- Layer E2: ProofAssembler.update_post_execution ---
        # Complete the proof record with execution result and lineage.
        execution_summary = ExecutionResultSummary(
            applied=True,
            status="COMPLETE",
            state_changed=True,
        )
        proof = self.proof_assembler.update_post_execution(
            proof=proof,
            execution_result=execution_summary,
            lineage_reference=edge_id,
        )

        # --- Layer G: AuthorityGate.evaluate ---
        authority_decision = self.gate.evaluate(
            execution_result=execution_summary,
            proof=proof,
            inherited_unresolved=inherited_unresolved,
            lineage_valid=lineage_valid,
        )

        if not authority_decision.is_authoritative:
            # Authority blocked: discard the staged successor.
            # Authoritative current was NEVER changed — it remains
            # the predecessor throughout.
            self.store.discard(delta.commitment_id)
            return SpineResult(
                rejected=True,
                rejection_reason=(
                    f"Authority gate did not grant authority: "
                    f"{authority_decision.decision.value} "
                    f"({authority_decision.reason})"
                ),
                rejection_layer="authority_gate",
                evidence=evidence,
                transformation=delta,
                identity_result=identity_result,
                candidate=candidate,
                validation=validation,
                proof=proof,
                lineage_edge=edge,
                authority_decision=authority_decision,
            )

        # Authority granted: promote the staged successor to
        # authoritative current.  This is the ONLY place authoritative
        # current changes.
        promoted_version = self.store.promote(delta.commitment_id)
        final_version = promoted_version or staged_version

        return SpineResult(
            promoted=True,
            evidence=evidence,
            transformation=delta,
            identity_result=identity_result,
            candidate=candidate,
            validation=validation,
            proof=proof,
            lineage_edge=edge,
            authority_decision=authority_decision,
            successor_version=final_version.version_number,
        )
