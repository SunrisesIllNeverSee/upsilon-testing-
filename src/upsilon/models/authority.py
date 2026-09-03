"""Authority decision models.

Implements the authority promotion contract specified in
``docs/moses/SEMANTIC_AUTHORITY_GATE.md``.

Authority states:
    AUTHORITY_GRANTED   — step promoted to authoritative
    AUTHORITY_BLOCKED   — step NOT promoted (proof/conservation failure)
    VALIDATION_REQUIRED — provisionally accepted, needs validation
    PARTIAL             — some instructions applied, some unresolved
    UNRESOLVED          — no instructions applied
"""
from __future__ import annotations

from enum import Enum


class AuthorityDecision(str, Enum):
    """Authority gate decision (SEMANTIC_AUTHORITY_GATE.md §3)."""

    AUTHORITY_GRANTED = "AUTHORITY_GRANTED"
    AUTHORITY_BLOCKED = "AUTHORITY_BLOCKED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"

    @property
    def is_authoritative(self) -> bool:
        """Whether this decision promotes the step to authoritative."""
        return self == AuthorityDecision.AUTHORITY_GRANTED

    @property
    def blocks_promotion(self) -> bool:
        """Whether this decision blocks authoritative promotion."""
        return self in (
            AuthorityDecision.AUTHORITY_BLOCKED,
            AuthorityDecision.PARTIAL,
            AuthorityDecision.UNRESOLVED,
        )
