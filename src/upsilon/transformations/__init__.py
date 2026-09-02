"""Transformations over commitment state.

This subdomain owns operations over commitment state that consume
evidence.  It may not grant authority.

See:
- docs/moses/TRANSFORMATION_ALGEBRA.md
"""
from __future__ import annotations

from .apply import apply_transformation
from .authorized_change import (
    AmendmentEvidence,
    AuthorityContext,
    AuthorizedTransformationEngine,
    TransformationResult,
)

__all__ = [
    "AmendmentEvidence",
    "AuthorityContext",
    "AuthorizedTransformationEngine",
    "TransformationResult",
    "apply_transformation",
]
