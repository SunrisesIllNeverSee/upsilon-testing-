"""Authorized Transformation Engine.

Implements the Layer B component specified in
``docs/moses/TRANSFORMATION_ALGEBRA.md`` §4.

The engine contract is:

    (C_{t-1}, E_t, A_t) -> Delta_t

Then:

    C_t = Apply(C_{t-1}, Delta_t)

The engine owns transformation interpretation and authorization
reasoning, not raw document parsing (Layer A) or execution (Layer F).

Process (TRANSFORMATION_ALGEBRA.md §4):
    1. Establish target identity
    2. Determine transformation type
    3. Determine affected fields
    4. Determine old/new values
    5. Verify old-value consistency (Constraint #3 — conservation check)
    6. Produce Delta_t

Must NOT:
    - Raw document parsing (Layer A)
    - Mutate commitment state (Layer F)
    - Grant authority (Layer G)
    - Execute the transformation (Layer F)
    - Copy old_value = predecessor[field] and treat
      old_value == predecessor[field] as interpretation evidence
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from upsilon.commitments.identity import IdentityResolutionResult, IdentityResolver
from upsilon.models import (
    AffectedField,
    AuthorizedTransformation,
    CommitmentKernel,
    TransformationFamily,
)


@dataclass
class AmendmentEvidence:
    """Evidence extracted from an amendment (Layer A output).

    This is the input to the AuthorizedTransformationEngine.  It
    carries the evidence signals, not the interpretation.
    """

    source_text: str = ""
    source_section_ref: str | None = None
    source_document: str = ""
    source_authority: str = ""  # e.g., "Amendment No. 3, Section 2"
    amendment_id: str = ""
    effective_date: Any | None = None

    # Extracted values (from Layer A parsing)
    instruction_type: str = ""  # REPLACE_VALUE, ADD, DELETE, etc.
    target_field: str | None = None
    new_value: Any = None
    declared_old_value: Any = None  # old value stated in amendment text
    exception_text: str | None = None

    # Alias/text match evidence (weak signals)
    alias_match: str | None = None
    text_match: str | None = None
    canonical_key_hint: str | None = None


@dataclass
class AuthorityContext:
    """Authority / lineage context for the transformation.

    Carries the predecessor state and chain context that the engine
    uses as constraint evidence (not as proof of target identity).
    """

    predecessor_kernel: CommitmentKernel | None = None
    predecessor_commitment_ids: list[str] = field(default_factory=list)
    amendment_number: int = 0
    chain_position: int = 0


@dataclass
class TransformationResult:
    """Result of a transformation engine invocation.

    Either carries an authorized transformation (Delta_t) or a
    rejection with a reason.
    """

    transformation: AuthorizedTransformation | None = None
    rejected: bool = False
    rejection_reason: str = ""
    rejection_step: str = ""  # which step in the process rejected

    @property
    def authorized(self) -> bool:
        """Whether a transformation was authorized (not rejected)."""
        return self.transformation is not None and not self.rejected


class AuthorizedTransformationEngine:
    """The Layer B component that produces authorized transformations.

    Given predecessor state, amendment evidence, and authority context,
    produces an authorized semantic transformation (Delta_t) or rejects.
    """

    def __init__(self, identity_resolver: IdentityResolver) -> None:
        self._identity_resolver = identity_resolver

    def authorize(
        self,
        evidence: AmendmentEvidence,
        authority: AuthorityContext,
    ) -> TransformationResult:
        """Produce an authorized transformation from evidence + predecessor state.

        Implements the 6-step process from TRANSFORMATION_ALGEBRA.md §4.
        """
        # Step 1: Establish target identity
        identity_result = self._establish_target_identity(evidence, authority)
        if identity_result.fail_closed:
            return TransformationResult(
                rejected=True,
                rejection_reason=identity_result.failure_reason,
                rejection_step="target_identity",
            )

        # Step 2: Determine transformation type
        transform_type = self._determine_transformation_type(evidence)
        if transform_type is None:
            return TransformationResult(
                rejected=True,
                rejection_reason="Cannot determine transformation type from evidence",
                rejection_step="transformation_type",
            )

        # Step 3: Determine affected fields
        affected_fields = self._determine_affected_fields(
            transform_type, evidence, authority
        )
        if affected_fields is None:
            return TransformationResult(
                rejected=True,
                rejection_reason="Cannot fully determine affected fields (transformation completeness)",
                rejection_step="affected_fields",
            )

        # Step 4: Determine old/new values
        old_values, new_values = self._determine_values(
            transform_type, affected_fields, evidence, authority
        )
        if new_values is None:
            return TransformationResult(
                rejected=True,
                rejection_reason="Cannot determine new values from evidence",
                rejection_step="value_extraction",
            )
        # Check that all required new values are populated
        # (for value-bearing transformations, None new_value means extraction failed)
        if transform_type not in (TransformationFamily.WAIVER, TransformationFamily.REINSTATEMENT,
                                  TransformationFamily.TERMINATE, TransformationFamily.RENUMBER):
            for field_name in affected_fields:
                if new_values.get(field_name) is None:
                    return TransformationResult(
                        rejected=True,
                        rejection_reason=f"Cannot extract new value for field '{field_name}'",
                        rejection_step="value_extraction",
                    )

        # Step 5: Verify old-value consistency (Constraint #3)
        # This is a CONSERVATION CHECK, not interpretation evidence.
        # It runs AFTER target/transformation evidence is established.
        old_value_ok = self._verify_old_value_consistency(
            transform_type, affected_fields, old_values,
            evidence, authority
        )
        if not old_value_ok:
            return TransformationResult(
                rejected=True,
                rejection_reason="Old-value consistency check failed (declared old value does not match predecessor state)",
                rejection_step="old_value_consistency",
            )

        # Step 6: Produce Delta_t
        identity = identity_result.identity
        if identity is None:
            return TransformationResult(
                rejected=True,
                rejection_reason="Identity resolved but identity object is None",
                rejection_step="internal_error",
            )

        affected = [
            AffectedField(
                field_name=f,
                old_value=old_values.get(f),
                new_value=new_values.get(f),
                evidence_span=evidence.source_text[:200] if evidence.source_text else "",
            )
            for f in affected_fields
        ]

        # Determine preserved fields
        preserved = self._preserved_fields(transform_type, affected_fields, authority)

        delta = AuthorizedTransformation(
            transformation_type=transform_type,
            commitment_id=identity.commitment_id,
            agreement_identity=identity.agreement_identity,
            affected_fields=affected,
            preserved_fields=preserved,
            source_document=evidence.source_document,
            source_span=evidence.source_text[:500] if evidence.source_text else "",
            source_authority=evidence.source_authority,
            effective_date=evidence.effective_date,
            old_value_consistency_verified=True,
        )

        return TransformationResult(transformation=delta)

    def _establish_target_identity(
        self,
        evidence: AmendmentEvidence,
        authority: AuthorityContext,
    ) -> IdentityResolutionResult:
        """Step 1: Establish target identity from evidence + predecessor state.

        Uses the agreement-local address map (not global section
        heuristics).  Predecessor state biases resolution but does not
        determine it.
        """
        return self._identity_resolver.resolve(
            section_ref=evidence.source_section_ref,
            alias_match=evidence.alias_match,
            text_match=evidence.text_match,
            predecessor_commitment_ids=authority.predecessor_commitment_ids,
            canonical_key_hint=evidence.canonical_key_hint,
        )

    def _determine_transformation_type(
        self, evidence: AmendmentEvidence
    ) -> TransformationFamily | None:
        """Step 2: Determine transformation type from amendment operation + evidence."""
        instr = evidence.instruction_type.upper()

        # Map instruction types to transformation families
        if instr in ("REPLACE_VALUE", "REPLACE_TEXT"):
            return TransformationFamily.SCALAR_REPLACEMENT
        elif instr == "ADD":
            # ADD to an existing commitment: exception_text or an
            # exceptions target_field means EXCEPTION_EXPANSION.
            # Any other ADD without a clear target is undetermined
            # (fail closed — do not silently default).
            if evidence.exception_text or evidence.target_field == "exceptions":
                return TransformationFamily.EXCEPTION_EXPANSION
            return None
        elif instr in ("DELETE", "DELETE_COMMITMENT"):
            if evidence.target_field == "exceptions":
                return TransformationFamily.EXCEPTION_CONTRACTION
            return TransformationFamily.TERMINATE
        elif instr == "ADD_COMMITMENT":
            return TransformationFamily.CREATE
        elif instr == "RESTATE_SECTION":
            return TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT
        elif instr == "WAIVE_TEMPORARILY" or instr == "SUSPEND":
            return TransformationFamily.WAIVER
        elif instr == "REINSTATE":
            return TransformationFamily.REINSTATEMENT
        elif instr == "RENUMBER_REFERENCE":
            return TransformationFamily.RENUMBER
        elif instr == "FIND_REPLACE_REFERENCE":
            return TransformationFamily.DEFINED_TERM_PROPAGATION
        elif instr == "UNRESOLVED":
            return None
        return None

    def _determine_affected_fields(
        self,
        transform_type: TransformationFamily,
        evidence: AmendmentEvidence,
        authority: AuthorityContext,
    ) -> list[str] | None:
        """Step 3: Determine affected fields from transformation type + evidence.

        If affected fields cannot be fully determined, return None
        (transformation completeness — no partial subsets).
        """
        if transform_type == TransformationFamily.SCALAR_REPLACEMENT:
            if evidence.target_field:
                return [evidence.target_field]
            return None

        elif transform_type == TransformationFamily.MULTI_FIELD_REPLACEMENT:
            # Multi-field requires all fields to be identified
            if evidence.target_field:
                return [evidence.target_field]
            return None

        elif transform_type == TransformationFamily.EXCEPTION_EXPANSION or transform_type == TransformationFamily.EXCEPTION_CONTRACTION:
            return ["exceptions"]

        elif transform_type == TransformationFamily.WAIVER:
            # A waiver suspends the commitment.  It changes status and
            # applicability only.  valid_from / valid_to represent the
            # commitment's overall validity period, not the waiver
            # window — they must be preserved.
            return ["status", "applicability"]

        elif transform_type == TransformationFamily.REINSTATEMENT:
            # Reinstatement reverses a waiver.  It restores status and
            # clears the waiver flag in applicability.  valid_from /
            # valid_to are preserved.
            return ["status", "applicability"]

        elif transform_type == TransformationFamily.TERMINATE:
            # Termination ends the commitment.  status -> TERMINATED.
            # valid_to is set to the termination effective date only
            # if the amendment provides one; otherwise it is preserved.
            if evidence.effective_date is not None:
                return ["status", "valid_to"]
            return ["status"]

        elif transform_type == TransformationFamily.CREATE:
            # CREATE affects all fields of the new commitment
            if evidence.target_field:
                return [evidence.target_field]
            return ["threshold", "operator", "unit"]  # minimal required

        elif transform_type == TransformationFamily.RENUMBER:
            return []  # RENUMBER affects the address binding, not kernel fields

        elif transform_type == TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT:
            # Restatement affects only the fields that differ
            if evidence.target_field:
                return [evidence.target_field]
            return None  # cannot determine without semantic differencing

        elif transform_type == TransformationFamily.DEFINED_TERM_PROPAGATION:
            if evidence.target_field:
                return [evidence.target_field]
            return None

        elif transform_type == TransformationFamily.SCHEDULE_REPLACEMENT:
            return ["applicability"]

        elif transform_type == TransformationFamily.TEMPORAL_STEP_CHANGE:
            return ["applicability", "valid_from", "valid_to"]

        return None

    def _determine_values(
        self,
        transform_type: TransformationFamily,
        affected_fields: list[str],
        evidence: AmendmentEvidence,
        authority: AuthorityContext,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Step 4: Determine old/new values.

        New values from evidence.  Old values from predecessor state
        (C_{t-1}[field]).  If old values stated in amendment, verify
        consistency in step 5.
        """
        old_values: dict[str, Any] = {}
        new_values: dict[str, Any] = {}

        predecessor = authority.predecessor_kernel

        for field_name in affected_fields:
            # New value from evidence
            if field_name == evidence.target_field:
                new_values[field_name] = evidence.new_value
            elif transform_type == TransformationFamily.EXCEPTION_EXPANSION:
                new_values[field_name] = evidence.exception_text
            elif transform_type == TransformationFamily.WAIVER:
                if field_name == "status":
                    new_values[field_name] = "WAIVED"
                elif field_name == "applicability":
                    new_values[field_name] = {"waived": True}
                else:
                    new_values[field_name] = None
            elif transform_type == TransformationFamily.REINSTATEMENT:
                if field_name == "status":
                    new_values[field_name] = "ACTIVE"
                elif field_name == "applicability":
                    new_values[field_name] = {}  # clear waiver flag
                else:
                    new_values[field_name] = None
            elif transform_type == TransformationFamily.TERMINATE:
                if field_name == "status":
                    new_values[field_name] = "TERMINATED"
                elif field_name == "valid_to":
                    # Set to the termination effective date from evidence
                    new_values[field_name] = evidence.effective_date
                else:
                    new_values[field_name] = None
            else:
                new_values[field_name] = evidence.new_value

            # Old value from predecessor state
            if predecessor:
                old_values[field_name] = predecessor.field_value(field_name)
            else:
                old_values[field_name] = None

        return old_values, new_values

    def _verify_old_value_consistency(
        self,
        transform_type: TransformationFamily,
        affected_fields: list[str],
        old_values: dict[str, Any],
        evidence: AmendmentEvidence,
        authority: AuthorityContext,
    ) -> bool:
        """Step 5: Verify old-value consistency (Constraint #3).

        This is a CONSERVATION CHECK, not interpretation evidence.
        It runs AFTER target/transformation evidence is established.

        If the amendment declares an old value, it must match the
        predecessor state.  If the amendment does not declare an old
        value, this check passes (there is nothing to verify).

        The engine must NOT simply copy old_value = predecessor[field]
        and treat old_value == predecessor[field] as evidence of
        correct interpretation — that proves only x = x.
        """
        # Only check when the amendment explicitly declares an old value
        if evidence.declared_old_value is None:
            return True

        # Only applies to certain transformation families
        if transform_type not in (
            TransformationFamily.SCALAR_REPLACEMENT,
            TransformationFamily.MULTI_FIELD_REPLACEMENT,
            TransformationFamily.EXCEPTION_CONTRACTION,
            TransformationFamily.SCHEDULE_REPLACEMENT,
            TransformationFamily.TEMPORAL_STEP_CHANGE,
            TransformationFamily.IDENTITY_PRESERVING_RESTATEMENT,
        ):
            return True

        predecessor = authority.predecessor_kernel
        if predecessor is None:
            return True  # no predecessor to check against

        # Check the declared old value against the predecessor state
        target_field = evidence.target_field
        if target_field is None:
            return True

        predecessor_value = predecessor.field_value(target_field)
        declared_old = evidence.declared_old_value

        # Normalize numeric comparison
        if isinstance(predecessor_value, (int, float)) and isinstance(declared_old, (int, float)):
            return float(predecessor_value) == float(declared_old)

        return predecessor_value == declared_old

    def _preserved_fields(
        self,
        transform_type: TransformationFamily,
        affected_fields: list[str],
        authority: AuthorityContext,
    ) -> list[str]:
        """Determine which fields are preserved by this transformation.

        All semantic fields except the affected ones must be preserved.
        """
        all_semantic_fields = [
            "threshold", "operator", "unit", "frequency", "scope",
            "exceptions", "trigger", "cure", "applicability", "rate",
            "deadline", "party", "action", "subject", "modality",
            "valid_from", "valid_to", "status", "grace_period",
            "application_order",
        ]
        return [
            f for f in all_semantic_fields
            if f not in affected_fields
        ]
