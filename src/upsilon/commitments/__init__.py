"""Commitment identity and canonical commitment state.

This subdomain owns commitment identity and canonical commitment
state.  It may not depend on authority.

See:
- docs/moses/COMMITMENT_IDENTITY.md
- docs/moses/COMMITMENT_KERNEL.md
"""
from __future__ import annotations

from .identity import (
    AgreementAddressMap,
    IdentityResolutionResult,
    IdentityResolver,
)
from .kernel import (
    KernelStore,
    OriginKernelBuilder,
)

__all__ = [
    "AgreementAddressMap",
    "IdentityResolutionResult",
    "IdentityResolver",
    "KernelStore",
    "OriginKernelBuilder",
]
