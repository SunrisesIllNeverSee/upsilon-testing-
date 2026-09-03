"""Commitment identity models.

Implements the persistent agreement-local commitment identity layer
specified in ``docs/moses/COMMITMENT_IDENTITY.md``.

Core invariant:

    ID(C_t) = ID(C_{t-1})

unless affirmative evidence establishes one of:
    CREATE, TERMINATE, SPLIT, MERGE, REDEFINE, RENUMBER / READDRESS
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IdentityProvenance(str, Enum):
    """How a commitment identity was established."""

    S0_ORIGIN = "s0_origin"
    AMENDMENT_CREATE = "amendment_create"
    AMENDMENT_RENUMBER = "amendment_renumber"
    HUMAN_VALIDATED = "human_validated"


class AddressBinding(BaseModel):
    """Agreement-local address (section/schedule/annex reference).

    Section numbers are agreement-local addresses, not global semantic
    identifiers.  The same section number can mean different things in
    different agreements.
    """

    section_ref: str
    established_at_version: str
    renumbered_from: str | None = None


class CommitmentIdentity(BaseModel):
    """Stable semantic identifier for a commitment within an agreement.

    This is the persistent identity that survives across amendments.
    The ``canonical_key`` (one of the 13 frozen classes) is the
    experimental family classification; ``commitment_id`` is the stable
    semantic handle.
    """

    commitment_id: str
    agreement_identity: str
    canonical_key: str
    local_address: AddressBinding
    provenance: IdentityProvenance = IdentityProvenance.S0_ORIGIN
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    identity_lineage: list[IdentityEvent] = Field(default_factory=list)

    def __eq__(self, other: object) -> bool:
        """Identity equality is by commitment_id + agreement_identity.

        Two identities are the same commitment iff they share the same
        agreement and commitment_id, regardless of address changes or
        provenance differences.
        """
        if not isinstance(other, CommitmentIdentity):
            return NotImplemented
        return (
            self.commitment_id == other.commitment_id
            and self.agreement_identity == other.agreement_identity
        )

    def __hash__(self) -> int:
        return hash((self.commitment_id, self.agreement_identity))


class IdentityEvent(BaseModel):
    """A recorded identity-changing event in the identity lineage.

    The identity lineage is a projection of the Commitment Lineage
    Graph.  Identity events are the subset of lineage edges that change
    identity (CREATE, TERMINATE, SPLIT, MERGE, REDEFINE, RENUMBER).
    """

    event_type: str  # CREATE, TERMINATE, SPLIT, MERGE, REDEFINE, RENUMBER
    amendment_id: str
    predecessor_id: str | None = None
    successor_id: str | None = None
    evidence_span: str = ""
    proof_id: str = ""
    effective_date: datetime | None = None
