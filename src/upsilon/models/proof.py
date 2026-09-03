"""Semantic transformation proof record models.

Implements the proof record schema specified in
``docs/moses/SEMANTIC_PROOF_RECORD.md``.

The proof record is NOT philosophical proof.  It is a structured
record of:
- what evidence was available
- what target identity was established
- what transformation was authorized
- what conservation checks passed
- what the execution result was
- what lineage edge was created

The proof record is assembled BEFORE execution.  It carries the
evidence, target identity, transformation, and conservation validation
results.  Execution is permitted only when the proof is COMPLETE and
all conservation checks PASS.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .transformation import TransformationFamily


class EvidenceLevel(str, Enum):
    """Target evidence levels (CONSERVATION_INVARIANTS.md §2.6)."""

    SUFFICIENT = "SUFFICIENT"
    CORROBORATED = "CORROBORATED"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceStatus(str, Enum):
    """Overall evidence status for the proof."""

    SUFFICIENT = "SUFFICIENT"
    CORROBORATED = "CORROBORATED"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class UncertaintyStatus(str, Enum):
    """Uncertainty level for the transformation."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ProofCompleteness(str, Enum):
    """Structural completeness of the proof record."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class ProofValidity(str, Enum):
    """Semantic validity of the proof record.

    A COMPLETE proof can be INVALID.  Completeness is structural;
    validity is semantic.
    """

    VALID = "VALID"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"


class CheckResult(BaseModel):
    """Result of a single conservation invariant check."""

    invariant_name: str
    passed: bool
    failure_reason: str = ""


class ValidatorResults(BaseModel):
    """Detailed validator output, including failure reasons."""

    checks: list[CheckResult] = Field(default_factory=list)
    summary: str = ""

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


class ConservationChecks(BaseModel):
    """Per-invariant pass/fail results (CONSERVATION_INVARIANTS.md)."""

    identity_persistence: CheckResult | None = None
    old_value_consistency: CheckResult | None = None
    unchanged_field_preservation: CheckResult | None = None
    no_unsupported_semantic_gain: CheckResult | None = None
    no_silent_semantic_loss: CheckResult | None = None
    target_reference_separation: CheckResult | None = None
    lineage_continuity: CheckResult | None = None
    temporal_validity: CheckResult | None = None
    out_of_scope_isolation: CheckResult | None = None
    transformation_completeness: CheckResult | None = None

    def all_results(self) -> list[CheckResult]:
        """All non-None check results."""
        return [
            r for r in [
                self.identity_persistence,
                self.old_value_consistency,
                self.unchanged_field_preservation,
                self.no_unsupported_semantic_gain,
                self.no_silent_semantic_loss,
                self.target_reference_separation,
                self.lineage_continuity,
                self.temporal_validity,
                self.out_of_scope_isolation,
                self.transformation_completeness,
            ]
            if r is not None
        ]

    @property
    def all_passed(self) -> bool:
        results = self.all_results()
        return len(results) > 0 and all(r.passed for r in results)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.all_results() if not r.passed]


class TargetSignal(BaseModel):
    """One evidence signal used to establish target identity."""

    signal_type: str  # section_ref, alias_match, text_match, defined_term, predecessor_bias, model_assisted
    signal_value: str
    signal_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    corroboration: bool = False


class TargetIdentityEvidence(BaseModel):
    """Evidence that establishes the amendment targets this commitment.

    This structure makes explicit what evidence was used to establish
    target identity.  It prevents the tautological old-value problem
    (Constraint #3): the target identity evidence must come from
    amendment evidence + predecessor context, NOT from copying
    old_value = predecessor[field].
    """

    signals: list[TargetSignal] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_level: EvidenceLevel = EvidenceLevel.INSUFFICIENT
    predecessor_state_used: bool = False
    local_address: str | None = None


class ExecutionResultSummary(BaseModel):
    """Summary of execution: applied/unresolved, state change."""

    applied: bool = False
    status: str = "UNRESOLVED"  # COMPLETE, PARTIAL, UNRESOLVED
    state_changed: bool = False
    error_message: str = ""


class SemanticTransformationProof(BaseModel):
    """The compact machine-readable proof record.

    Every accepted semantic transformation must produce this record.
    The proof record is a runtime evidence object showing why the
    transformation was allowed.

    Authority is granted only when:
        proof_completeness == COMPLETE
        AND proof_validity == VALID
        AND all conservation_checks PASS
        AND execution succeeds
        AND no inherited unresolved state blocks promotion
    """

    # --- Identity ---
    proof_id: str
    agreement_id: str
    commitment_id: str

    # --- Versions ---
    predecessor_version: int = 0
    successor_version: int = 0

    # --- Source evidence ---
    source_document: str = ""
    source_span: str = ""
    source_authority: str = ""

    # --- Transformation ---
    transformation_type: TransformationFamily = TransformationFamily.SCALAR_REPLACEMENT
    target_identity_evidence: TargetIdentityEvidence = Field(
        default_factory=TargetIdentityEvidence
    )

    # --- Field-level changes ---
    affected_fields: list[str] = Field(default_factory=list)
    predecessor_values: dict[str, Any] = Field(default_factory=dict)
    successor_values: dict[str, Any] = Field(default_factory=dict)
    preserved_fields: list[str] = Field(default_factory=list)

    # --- Dependencies ---
    defined_term_dependencies: list[str] = Field(default_factory=list)
    temporal_dependencies: list[str] = Field(default_factory=list)

    # --- Conservation ---
    conservation_checks: ConservationChecks = Field(default_factory=ConservationChecks)
    validator_results: ValidatorResults = Field(default_factory=ValidatorResults)

    # --- Status ---
    evidence_status: EvidenceStatus = EvidenceStatus.INSUFFICIENT
    uncertainty_status: UncertaintyStatus = UncertaintyStatus.NONE
    proof_completeness: ProofCompleteness = ProofCompleteness.INCOMPLETE
    proof_validity: ProofValidity = ProofValidity.INDETERMINATE

    # --- Execution ---
    execution_result: ExecutionResultSummary = Field(default_factory=ExecutionResultSummary)
    lineage_reference: str = ""  # proof_id of the lineage edge

    def is_complete_and_valid(self) -> bool:
        """Whether this proof is both structurally complete and semantically valid."""
        return (
            self.proof_completeness == ProofCompleteness.COMPLETE
            and self.proof_validity == ProofValidity.VALID
        )

    def may_proceed_to_execution(self) -> bool:
        """Whether execution is permitted based on this proof.

        Execution is permitted only when the proof is COMPLETE and
        all conservation checks PASS.
        """
        return (
            self.proof_completeness == ProofCompleteness.COMPLETE
            and self.proof_validity == ProofValidity.VALID
            and self.conservation_checks.all_passed
        )
