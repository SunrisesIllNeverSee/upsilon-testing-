"""Authority promotion gate.

This subdomain consumes execution + proof + conservation status to
determine if a step may be promoted to authoritative.  It may not
inspect raw EDGAR text to infer meaning.

See:
- docs/moses/SEMANTIC_AUTHORITY_GATE.md
"""
from __future__ import annotations

from .promotion_gate import AuthorityGate, AuthorityGateResult

__all__ = [
    "AuthorityGate",
    "AuthorityGateResult",
]
