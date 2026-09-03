"""Semantic transformation proof builder and assembler.

Implements the Layer E component specified in
``docs/moses/SEMANTIC_PROOF_RECORD.md`` §10.

| Inputs  | Authorized Delta_t, validation results (Layer D), evidence, versions |
| Outputs | SemanticTransformationProof record |
| May do  | Assemble the proof record with all required fields; record evidence/uncertainty status |
| Must not | Invent semantic interpretation; perform validation; execute; grant authority |
| Failure | If required proof fields cannot be populated, the proof is INCOMPLETE. |

The proof record is assembled BEFORE execution.  It carries the
evidence, target identity, transformation, and conservation validation
results.  Execution is permitted only when the proof is COMPLETE and
all conservation checks PASS.
"""
from __future__ import annotations

import uuid

from upsilon.commitments.identity import IdentityResolutionResult
from upsilon.conservation.validator import ValidationResult
from upsilon.models import (
    AuthorizedTransformation,
    EvidenceLevel,
    EvidenceStatus,
    ExecutionResultSummary,
    ProofCompleteness,
    ProofValidity,
    SemanticTransformationProof,
    TargetIdentityEvidence,
    TargetSignal,
    UncertaintyStatus,
)


class ProofBuilder:
    """Builds a SemanticTransformationProof from transformation components.

    The builder assembles the proof record from:
    - The authorized transformation (Delta_t)
    - The identity resolution result (target identity evidence)
    - The conservation validation results (Layer D)
    - The predecessor and successor kernel versions
    """

    def build(
        self,
        delta: AuthorizedTransformation,
        identity_result: IdentityResolutionResult,
        validation: ValidationResult,
        predecessor_version: int = 0,
        successor_version: int = 0,
    ) -> SemanticTransformationProof:
        """Assemble a proof record from transformation components."""
        proof_id = f"PRF-{uuid.uuid4().hex[:12]}"

        # Build target identity evidence
        target_evidence = self._build_target_evidence(identity_result)

        # Determine evidence status from identity resolution
        evidence_status = self._evidence_status(identity_result)

        # Determine uncertainty status
        uncertainty = self._uncertainty_status(identity_result)

        # Determine proof completeness (structural)
        completeness = self._completeness(
            delta, identity_result, validation
        )

        # Determine proof validity (semantic)
        validity = self._validity(delta, identity_result, validation)

        return SemanticTransformationProof(
            proof_id=proof_id,
            agreement_id=delta.agreement_identity,
            commitment_id=delta.commitment_id,
            predecessor_version=predecessor_version,
            successor_version=successor_version,
            source_document=delta.source_document,
            source_span=delta.source_span,
            source_authority=delta.source_authority,
            transformation_type=delta.transformation_type,
            target_identity_evidence=target_evidence,
            affected_fields=delta.affected_field_names,
            predecessor_values=delta.old_values(),
            successor_values=delta.new_values(),
            preserved_fields=delta.preserved_fields,
            conservation_checks=validation.checks,
            validator_results=validation.validator_results,
            evidence_status=evidence_status,
            uncertainty_status=uncertainty,
            proof_completeness=completeness,
            proof_validity=validity,
        )

    def _build_target_evidence(
        self, identity_result: IdentityResolutionResult
    ) -> TargetIdentityEvidence:
        """Build TargetIdentityEvidence from identity resolution."""
        signals = [
            TargetSignal(
                signal_type="resolution_signal",
                signal_value=s,
                signal_weight=identity_result.confidence,
                corroboration=len(identity_result.signals) > 1,
            )
            for s in identity_result.signals
        ]

        try:
            level = EvidenceLevel(identity_result.evidence_level)
        except ValueError:
            level = EvidenceLevel.INSUFFICIENT

        return TargetIdentityEvidence(
            signals=signals,
            confidence=identity_result.confidence,
            evidence_level=level,
            predecessor_state_used=len(identity_result.signals) > 1,
        )

    def _evidence_status(
        self, identity_result: IdentityResolutionResult
    ) -> EvidenceStatus:
        """Map identity evidence level to proof evidence status."""
        level = identity_result.evidence_level
        if level == "SUFFICIENT":
            return EvidenceStatus.SUFFICIENT
        elif level == "CORROBORATED":
            return EvidenceStatus.CORROBORATED
        elif level == "WEAK":
            return EvidenceStatus.WEAK
        return EvidenceStatus.INSUFFICIENT

    def _uncertainty_status(
        self, identity_result: IdentityResolutionResult
    ) -> UncertaintyStatus:
        """Determine uncertainty from identity confidence."""
        conf = identity_result.confidence
        if conf >= 0.85:
            return UncertaintyStatus.NONE
        elif conf >= 0.7:
            return UncertaintyStatus.LOW
        elif conf >= 0.5:
            return UncertaintyStatus.MEDIUM
        return UncertaintyStatus.HIGH

    def _completeness(
        self,
        delta: AuthorizedTransformation,
        identity_result: IdentityResolutionResult,
        validation: ValidationResult,
    ) -> ProofCompleteness:
        """Determine structural completeness (SEMANTIC_PROOF_RECORD.md §7)."""
        # 1. target identity evidence is SUFFICIENT or CORROBORATED
        if identity_result.evidence_level not in ("SUFFICIENT", "CORROBORATED"):
            return ProofCompleteness.INCOMPLETE

        # 2. All affected fields have both predecessor and successor values
        for affected in delta.affected_fields:
            if affected.old_value is None and affected.new_value is None:
                return ProofCompleteness.INCOMPLETE

        # 3. All conservation checks have been run
        if len(validation.validator_results.checks) == 0:
            return ProofCompleteness.INCOMPLETE

        # 4. evidence_status is not INSUFFICIENT
        if identity_result.evidence_level == "INSUFFICIENT":
            return ProofCompleteness.INCOMPLETE

        # 5. transformation_type is one of the 13 families (always true via enum)

        # 6. dependencies populated (or explicitly empty — always true via defaults)

        return ProofCompleteness.COMPLETE

    def _validity(
        self,
        delta: AuthorizedTransformation,
        identity_result: IdentityResolutionResult,
        validation: ValidationResult,
    ) -> ProofValidity:
        """Determine semantic validity (SEMANTIC_PROOF_RECORD.md §7)."""
        # If any conservation check failed, the proof is INVALID
        if not validation.passed:
            return ProofValidity.INVALID

        # If target identity evidence is INSUFFICIENT, the proof is INVALID
        if identity_result.evidence_level == "INSUFFICIENT":
            return ProofValidity.INVALID

        # If old-value consistency was not verified, indeterminate
        if not delta.old_value_consistency_verified:
            return ProofValidity.INDETERMINATE

        return ProofValidity.VALID


class ProofAssembler:
    """Assembles and updates proof records through the transformation lifecycle.

    The proof is assembled BEFORE execution (precondition) and updated
    AFTER execution with the execution result and lineage reference.
    """

    def __init__(self) -> None:
        self._builder = ProofBuilder()

    def assemble_pre_execution(
        self,
        delta: AuthorizedTransformation,
        identity_result: IdentityResolutionResult,
        validation: ValidationResult,
        predecessor_version: int = 0,
        successor_version: int = 0,
    ) -> SemanticTransformationProof:
        """Assemble the proof record before execution.

        This is the precondition that justifies allowing a
        transformation to execute.
        """
        return self._builder.build(
            delta=delta,
            identity_result=identity_result,
            validation=validation,
            predecessor_version=predecessor_version,
            successor_version=successor_version,
        )

    def update_post_execution(
        self,
        proof: SemanticTransformationProof,
        execution_result: ExecutionResultSummary,
        lineage_reference: str,
    ) -> SemanticTransformationProof:
        """Update the proof record after execution.

        Records the execution result and lineage edge reference,
        completing the proof record.
        """
        proof.execution_result = execution_result
        proof.lineage_reference = lineage_reference
        return proof
