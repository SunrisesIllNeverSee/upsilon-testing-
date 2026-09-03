"""Authority promotion gate.

Implements the Layer G component specified in
``docs/moses/SEMANTIC_AUTHORITY_GATE.md`` §5.

Authority must no longer be reducible to
"execution complete + nothing unresolved".  Semantic authority requires:

    AUTHORITY_GRANTED
    iff
    proof_completeness == COMPLETE
    AND proof_validity == VALID
    AND required conservation invariants pass
    AND execution succeeds
    AND lineage is valid
    AND no blocking inherited/own unresolved state

The gate consumes existing systems (chain-aware authority model,
execution results, temporal authority rule) — it does NOT redesign
them.  It adds the semantic-proof and conservation-validation
preconditions that the current authority determination lacks.
"""
from __future__ import annotations

from dataclasses import dataclass

from upsilon.models import (
    AuthorityDecision,
    ExecutionResultSummary,
    ProofCompleteness,
    ProofValidity,
    SemanticTransformationProof,
)


@dataclass
class AuthorityGateResult:
    """Result of an authority gate decision."""

    decision: AuthorityDecision
    reason: str = ""
    proof_id: str = ""

    @property
    def is_authoritative(self) -> bool:
        return self.decision.is_authoritative

    @property
    def blocks_promotion(self) -> bool:
        return self.decision.blocks_promotion


class AuthorityGate:
    """Determines whether a step may be promoted to authoritative.

    The gate implements the decision logic from
    SEMANTIC_AUTHORITY_GATE.md §5:

        IF execution_result.status == UNRESOLVED: -> UNRESOLVED
        IF execution_result.status == PARTIAL: -> PARTIAL
        IF execution_result.status == COMPLETE:
            IF proof_record.completeness == INCOMPLETE: -> AUTHORITY_BLOCKED
            IF proof_record.validity == INVALID: -> AUTHORITY_BLOCKED
            IF any conservation_check FAILED: -> AUTHORITY_BLOCKED
            IF lineage is missing or invalid: -> AUTHORITY_BLOCKED
            IF inherited_unresolved > 0: -> AUTHORITY_BLOCKED
            IF proof_record.evidence_status == INSUFFICIENT: -> AUTHORITY_BLOCKED
            IF proof_record.uncertainty_status == HIGH: -> VALIDATION_REQUIRED
            IF target_identity_evidence.evidence_level == WEAK: -> VALIDATION_REQUIRED
            IF proof_record.validity == INDETERMINATE: -> VALIDATION_REQUIRED
            ELSE: -> AUTHORITY_GRANTED

    Lineage validity is a required precondition (Step 24B Phase 8 gap
    closure).  Missing or invalid lineage blocks authority.  The caller
    must affirmatively provide ``lineage_valid=True`` after confirming
    the lineage edge was created and is reachable from origin.  The
    default is ``False`` (fail-closed) so a caller that forgets to
    pass lineage validity cannot accidentally promote a step.
    """

    def evaluate(
        self,
        execution_result: ExecutionResultSummary,
        proof: SemanticTransformationProof,
        inherited_unresolved: int = 0,
        lineage_valid: bool = False,
    ) -> AuthorityGateResult:
        """Evaluate whether a step may be promoted to authoritative.

        Args:
            execution_result: summary of the execution outcome.
            proof: the semantic transformation proof record.
            inherited_unresolved: count of unresolved state inherited
                from prior steps.
            lineage_valid: whether a valid lineage edge was created for
                this transformation and is reachable from origin.
                Defaults to False (fail-closed).  The caller must
                affirmatively confirm lineage validity.
        """
        # Execution status checks
        if execution_result.status == "UNRESOLVED":
            return AuthorityGateResult(
                decision=AuthorityDecision.UNRESOLVED,
                reason="Execution status: UNRESOLVED",
                proof_id=proof.proof_id,
            )

        if execution_result.status == "PARTIAL":
            return AuthorityGateResult(
                decision=AuthorityDecision.PARTIAL,
                reason="Execution status: PARTIAL",
                proof_id=proof.proof_id,
            )

        if execution_result.status != "COMPLETE":
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason=f"Execution status: {execution_result.status}",
                proof_id=proof.proof_id,
            )

        # Proof completeness check
        if proof.proof_completeness == ProofCompleteness.INCOMPLETE:
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason="Proof record is INCOMPLETE",
                proof_id=proof.proof_id,
            )

        # Proof validity check
        if proof.proof_validity == ProofValidity.INVALID:
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason="Proof record is INVALID",
                proof_id=proof.proof_id,
            )

        # Conservation checks
        if not proof.conservation_checks.all_passed:
            failed = proof.conservation_checks.failed
            names = [r.invariant_name for r in failed]
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason=f"Conservation checks failed: {names}",
                proof_id=proof.proof_id,
            )

        # Lineage validity check (Step 24B Phase 8 gap closure).
        # Missing or invalid lineage blocks authority promotion.
        if not lineage_valid:
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason="Lineage is missing or invalid",
                proof_id=proof.proof_id,
            )

        # Inherited unresolved state
        if inherited_unresolved > 0:
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason=f"Inherited unresolved state: {inherited_unresolved}",
                proof_id=proof.proof_id,
            )

        # Evidence status
        if proof.evidence_status.value == "INSUFFICIENT":
            return AuthorityGateResult(
                decision=AuthorityDecision.AUTHORITY_BLOCKED,
                reason="Evidence status: INSUFFICIENT",
                proof_id=proof.proof_id,
            )

        # Uncertainty routing
        if proof.uncertainty_status.value == "HIGH":
            return AuthorityGateResult(
                decision=AuthorityDecision.VALIDATION_REQUIRED,
                reason="Uncertainty status: HIGH",
                proof_id=proof.proof_id,
            )

        # Weak evidence routing
        if proof.target_identity_evidence.evidence_level.value == "WEAK":
            return AuthorityGateResult(
                decision=AuthorityDecision.VALIDATION_REQUIRED,
                reason="Target identity evidence: WEAK",
                proof_id=proof.proof_id,
            )

        # Indeterminate validity routing
        if proof.proof_validity == ProofValidity.INDETERMINATE:
            return AuthorityGateResult(
                decision=AuthorityDecision.VALIDATION_REQUIRED,
                reason="Proof validity: INDETERMINATE",
                proof_id=proof.proof_id,
            )

        # All checks passed — grant authority
        return AuthorityGateResult(
            decision=AuthorityDecision.AUTHORITY_GRANTED,
            reason="All authority conditions satisfied",
            proof_id=proof.proof_id,
        )
