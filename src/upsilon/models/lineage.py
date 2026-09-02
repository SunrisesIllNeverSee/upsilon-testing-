"""Lineage graph models.

Implements the lineage edge and node class schemas specified in
``COMMITMENT_LINEAGE_SCHEMA.md`` and the addendum §3.

Every accepted transformation produces a lineage edge recording the
predecessor, successor, amendment authority, transformation type,
affected fields, old/new values, effective date, source span, proof
reference, and validation status.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .transformation import TransformationFamily


class NodeClass(str, Enum):
    """Lineage graph node classes (COMMITMENT_LINEAGE_SCHEMA.md)."""

    AGREEMENT = "Agreement"
    AGREEMENT_VERSION = "AgreementVersion"
    COMMITMENT = "Commitment"
    COMMITMENT_VERSION = "CommitmentVersion"
    DOWNSTREAM_REPRESENTATION = "DownstreamRepresentation"


class EdgeClass(str, Enum):
    """Lineage graph edge classes (COMMITMENT_LINEAGE_SCHEMA.md)."""

    ORIGINATES_FROM = "ORIGINATES_FROM"
    MODIFIES = "MODIFIES"
    SUPERSEDES = "SUPERSEDES"
    WAIVES = "WAIVES"
    REINSTATES = "REINSTATES"
    DERIVES_FROM = "DERIVES_FROM"
    PROPAGATES_TO = "PROPAGATES_TO"


class ValidationStatus(str, Enum):
    """Validation status of a lineage edge."""

    VALIDATED = "VALIDATED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class LineageEdge(BaseModel):
    """An append-only lineage edge recording an authorized transformation.

    Every state-changing lineage edge must point to the
    authority_version_id that legally supports it.

    Schema (CONSERVATION_INVARIANTS.md §2.7, SEMANTIC_PROOF_RECORD.md §9):
    """

    edge_id: str
    edge_class: EdgeClass = EdgeClass.MODIFIES

    # --- Commitment linkage ---
    predecessor_commitment_id: str
    successor_commitment_id: str

    # --- Authority ---
    amendment_id: str
    authority_source: str  # the legal authority (amendment, section)

    # --- Transformation ---
    transformation_type: TransformationFamily
    affected_fields: list[str] = Field(default_factory=list)
    old_values: dict[str, Any] = Field(default_factory=dict)
    new_values: dict[str, Any] = Field(default_factory=dict)

    # --- Temporal ---
    effective_date: datetime | None = None
    source_span: str = ""

    # --- Proof linkage ---
    proof_id: str = ""
    validation_status: ValidationStatus = ValidationStatus.PENDING

    @property
    def is_identity_preserving(self) -> bool:
        """Whether this edge preserves commitment identity."""
        return self.predecessor_commitment_id == self.successor_commitment_id

    @property
    def is_validated(self) -> bool:
        return self.validation_status == ValidationStatus.VALIDATED
