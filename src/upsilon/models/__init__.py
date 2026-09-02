"""Shared data models for the Upsilon/MOSES commitment engine.

This module defines the canonical value objects that all semantic
subdomains operate over.  It is Layer 0 — no layer-specific logic
lives here.

The models are designed to be compatible with the existing legacy
``models.CommitmentState`` so that migration can proceed without
breaking the 980-test legacy suite.  The key additions over the
legacy models are:

- ``CommitmentIdentity`` — persistent agreement-local identity
  (replaces bare ``canonical_key`` as the identity carrier)
- ``CommitmentKernel`` — the canonical commitment state object that
  transformations operate over (C_{t-1} and C_t)
- ``KernelVersion`` — immutable version stamp for lineage tracing
- ``LineageEdge`` — the append-only lineage record
- ``SemanticTransformationProof`` — the proof record precondition
- ``AuthorizedTransformation`` — the delta object (Delta_t)

See:
- docs/moses/COMMITMENT_IDENTITY.md
- docs/moses/COMMITMENT_KERNEL.md
- docs/moses/TRANSFORMATION_ALGEBRA.md
- docs/moses/CONSERVATION_INVARIANTS.md
- docs/moses/SEMANTIC_PROOF_RECORD.md
- docs/moses/SEMANTIC_AUTHORITY_GATE.md
- COMMITMENT_LINEAGE_SCHEMA.md
"""
from __future__ import annotations

from .authority import (
    AuthorityDecision,
)
from .identity import (
    AddressBinding,
    CommitmentIdentity,
    IdentityEvent,
    IdentityProvenance,
)
from .kernel import (
    CommitmentKernel,
    KernelVersion,
)
from .lineage import (
    EdgeClass,
    LineageEdge,
    NodeClass,
    ValidationStatus,
)
from .proof import (
    CheckResult,
    ConservationChecks,
    EvidenceLevel,
    EvidenceStatus,
    ExecutionResultSummary,
    ProofCompleteness,
    ProofValidity,
    SemanticTransformationProof,
    TargetIdentityEvidence,
    TargetSignal,
    UncertaintyStatus,
    ValidatorResults,
)
from .transformation import (
    AffectedField,
    AuthorizedTransformation,
    TransformationFamily,
)

__all__ = [
    "AddressBinding",
    "AffectedField",
    "AuthorityDecision",
    "AuthorizedTransformation",
    "CheckResult",
    "CommitmentIdentity",
    "CommitmentKernel",
    "ConservationChecks",
    "EdgeClass",
    "EvidenceLevel",
    "EvidenceStatus",
    "ExecutionResultSummary",
    "IdentityEvent",
    "IdentityProvenance",
    "KernelVersion",
    "LineageEdge",
    "NodeClass",
    "ProofCompleteness",
    "ProofValidity",
    "SemanticTransformationProof",
    "TargetIdentityEvidence",
    "TargetSignal",
    "TransformationFamily",
    "UncertaintyStatus",
    "ValidationStatus",
    "ValidatorResults",
]
