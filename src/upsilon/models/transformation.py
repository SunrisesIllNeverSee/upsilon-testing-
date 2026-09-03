"""Authorized transformation models.

Implements the transformation delta object (Delta_t) specified in
``docs/moses/TRANSFORMATION_ALGEBRA.md``.

The AuthorizedTransformationEngine contract is:

    (C_{t-1}, E_t, A_t) -> Delta_t

Then:

    C_t = Apply(C_{t-1}, Delta_t)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransformationFamily(str, Enum):
    """The 13 transformation families over commitment state.

    These are NOT commitment classes.  The 13 frozen commitment classes
    (commitment_registry.py) are unchanged.  Transformation richness
    and ontology breadth are different questions.
    """

    SCALAR_REPLACEMENT = "SCALAR_REPLACEMENT"
    MULTI_FIELD_REPLACEMENT = "MULTI_FIELD_REPLACEMENT"
    EXCEPTION_EXPANSION = "EXCEPTION_EXPANSION"
    EXCEPTION_CONTRACTION = "EXCEPTION_CONTRACTION"
    SCHEDULE_REPLACEMENT = "SCHEDULE_REPLACEMENT"
    TEMPORAL_STEP_CHANGE = "TEMPORAL_STEP_CHANGE"
    WAIVER = "WAIVER"
    REINSTATEMENT = "REINSTATEMENT"
    IDENTITY_PRESERVING_RESTATEMENT = "IDENTITY_PRESERVING_RESTATEMENT"
    DEFINED_TERM_PROPAGATION = "DEFINED_TERM_PROPAGATION"
    RENUMBER = "RENUMBER"
    TERMINATE = "TERMINATE"
    CREATE = "CREATE"

    @property
    def is_identity_changing(self) -> bool:
        """Whether this transformation changes commitment identity."""
        return self in (
            TransformationFamily.CREATE,
            TransformationFamily.TERMINATE,
            TransformationFamily.RENUMBER,
        )


class AffectedField(BaseModel):
    """One field affected by a transformation, with old and new values."""

    field_name: str
    old_value: Any = None
    new_value: Any = None
    evidence_span: str = ""


class AuthorizedTransformation(BaseModel):
    """An authorized semantic transformation (Delta_t).

    Produced by the AuthorizedTransformationEngine.  Carries the
    transformation type, affected fields with old/new values, preserved
    fields, and evidence references.

    This is the delta in:

        C_t = C_{t-1} ⊕ Delta_t_authorized
    """

    transformation_type: TransformationFamily
    commitment_id: str
    agreement_identity: str

    # The fields this transformation affects, with old/new values
    affected_fields: list[AffectedField] = Field(default_factory=list)

    # Fields explicitly preserved (must satisfy C_t[f] == C_{t-1}[f])
    preserved_fields: list[str] = Field(default_factory=list)

    # Source evidence references
    source_document: str = ""
    source_span: str = ""
    source_authority: str = ""  # e.g., "Amendment No. 3, Section 2"

    # Effective date of the transformation
    effective_date: datetime | None = None

    # Reference to the proof record that validates this transformation
    proof_id: str = ""

    # Whether old-value consistency was verified (Constraint #3)
    old_value_consistency_verified: bool = False

    @property
    def affected_field_names(self) -> list[str]:
        """Names of all affected fields."""
        return [f.field_name for f in self.affected_fields]

    def old_values(self) -> dict[str, Any]:
        """Predecessor values for all affected fields."""
        return {f.field_name: f.old_value for f in self.affected_fields}

    def new_values(self) -> dict[str, Any]:
        """Successor values for all affected fields."""
        return {f.field_name: f.new_value for f in self.affected_fields}
