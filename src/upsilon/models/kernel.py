"""Commitment kernel models.

Implements the canonical commitment state object specified in
``docs/moses/COMMITMENT_KERNEL.md``.

The governing state model is:

    C_t = C_{t-1} ⊕ Δ_t_authorized

The kernel is C_{t-1} (predecessor) and C_t (successor).
Transformations produce deltas; the kernel is what the delta applies to.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .identity import CommitmentIdentity


class KernelVersion(BaseModel):
    """Immutable version stamp for a commitment kernel.

    Each transformation produces a new version.  The version is
    immutable once produced.  A new transformation produces a new
    version; it does not mutate the existing one.

    This supports lineage tracing and temporal queries
    (COMMITMENT_LINEAGE_SCHEMA.md temporal authority rule K(A,T)).
    """

    commitment_id: str
    version_number: int  # monotonic within a chain
    valid_from: datetime
    valid_to: datetime | None = None
    produced_by_proof_id: str = ""
    predecessor_version: int | None = None


class CommitmentKernel(BaseModel):
    """Canonical commitment state at a point in time.

    This is the state object that transformations operate over.
    It combines the persistent identity with the mutable semantic
    state, temporal state, and evidentiary/provenance state.

    Field categories (per COMMITMENT_KERNEL.md §3):

    Identity-bearing:
        commitment_id, canonical_key, agreement_identity,
        identity_provenance

    Mutable semantic state:
        threshold, operator, unit, frequency, scope, exceptions,
        trigger, cure, applicability, rate, deadline, party,
        action, subject, modality

    Temporal state:
        valid_from, valid_to, status, grace_period, application_order

    Evidentiary / provenance state:
        source_document, source_span, defined_term_support,
        lineage_reference, authority_status, proof_reference
    """

    # --- Identity-bearing ---
    identity: CommitmentIdentity

    # --- Mutable semantic state ---
    threshold: float | None = None
    operator: str | None = None  # >=, <=, =, >, <
    unit: str | None = None  # ratio, dollars, percent
    frequency: str | None = None  # quarterly, continuous, annual
    scope: dict[str, Any] = Field(default_factory=dict)
    exceptions: list[Any] = Field(default_factory=list)
    trigger: dict[str, Any] = Field(default_factory=dict)
    cure: dict[str, Any] = Field(default_factory=dict)
    applicability: dict[str, Any] = Field(default_factory=dict)
    rate: float | None = None
    deadline: str | None = None
    party: list[str] = Field(default_factory=list)
    action: str | None = None
    subject: str | None = None
    modality: str | None = None  # obligation, prohibition, permission

    # --- Temporal state ---
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    status: str = "ACTIVE"  # ACTIVE, WAIVED, SUSPENDED, TERMINATED
    grace_period: str | None = None
    application_order: list[str] = Field(default_factory=list)

    # --- Evidentiary / provenance state ---
    source_document: str | None = None
    source_span: str | None = None
    defined_term_support: list[str] = Field(default_factory=list)
    lineage_reference: str | None = None  # lineage edge ID
    authority_status: str | None = None  # authority decision
    proof_reference: str | None = None  # proof record ID

    # --- Version ---
    version: KernelVersion | None = None

    @property
    def commitment_id(self) -> str:
        return self.identity.commitment_id

    @property
    def canonical_key(self) -> str:
        return self.identity.canonical_key

    @property
    def agreement_identity(self) -> str:
        return self.identity.agreement_identity

    def field_value(self, field_name: str) -> Any:
        """Get the value of a semantic field by name.

        Used by conservation validators to compare predecessor and
        successor field values.
        """
        return getattr(self, field_name, None)

    def semantic_fields(self) -> dict[str, Any]:
        """Return all mutable semantic fields as a dict.

        Excludes identity, version, and evidentiary/provenance fields.
        Used for semantic differencing in IDENTITY_PRESERVING_RESTATEMENT.
        """
        semantic_field_names = [
            "threshold", "operator", "unit", "frequency", "scope",
            "exceptions", "trigger", "cure", "applicability", "rate",
            "deadline", "party", "action", "subject", "modality",
            "valid_from", "valid_to", "status", "grace_period",
            "application_order",
        ]
        return {f: getattr(self, f) for f in semantic_field_names}
