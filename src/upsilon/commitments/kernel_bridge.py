"""Bridge between legacy CommitmentState and canonical CommitmentKernel.

This module establishes the authoritative kernel boundary required by
Step 24B Phase 1.  It converts legacy ``CommitmentState`` objects (the
flat state model used by the existing pipeline) into canonical
``CommitmentKernel`` objects with persistent ``CommitmentIdentity``,
and registers them in a ``KernelStore`` as the authoritative
predecessor state.

The bridge is one-directional at the boundary: legacy state is
converted to canonical kernels at S0 initialization.  After that
point, the Step 24 spine operates on ``CommitmentKernel`` objects.
A reverse conversion is provided for compatibility with the existing
ground-truth comparison and metrics layer, which still operates on
``CommitmentState``.

RESPONSIBILITY:
    Establish authoritative kernel boundary (CommitmentState ↔ CommitmentKernel)
TARGET DOMAIN:
    commitments
CURRENT MODULE:
    src/upsilon/commitments/kernel_bridge.py (new)
CURRENT OPERATING STATUS:
    Phase 1 — authoritative kernel boundary
WHY THIS MODULE MUST CHANGE:
    The production pipeline operates on CommitmentState (legacy).
    The Step 24 spine requires CommitmentKernel with persistent
    identity.  A conversion bridge is needed at the boundary.
TARGET OWNER AFTER CHANGE:
    commitments domain (this module)
MIGRATION / REMOVAL CONDITION:
    Remove when the production pipeline operates natively on
    CommitmentKernel and no longer needs CommitmentState conversion.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from upsilon.models import (
    AddressBinding,
    CommitmentIdentity,
    CommitmentKernel,
    IdentityProvenance,
)
from upsilon.models.legacy_models import CommitmentState
from upsilon.commitments.identity import AgreementAddressMap
from upsilon.commitments.kernel import KernelStore


# Semantic fields shared between CommitmentState and CommitmentKernel.
# These are the mutable semantic state fields that must be carried
# across the boundary.
_SEMANTIC_FIELDS: tuple[str, ...] = (
    "threshold", "operator", "unit", "frequency", "scope",
    "exceptions", "trigger", "cure", "applicability", "rate",
    "deadline", "party", "action", "subject", "modality",
)

# Temporal fields carried across the boundary.
_TEMPORAL_FIELDS: tuple[str, ...] = (
    "valid_from", "valid_to", "status", "grace_period",
    "application_order",
)


def state_to_kernel(
    state: CommitmentState,
    agreement_identity: str,
    section_ref: str | None = None,
) -> CommitmentKernel:
    """Convert a legacy CommitmentState to a canonical CommitmentKernel.

    The resulting kernel has a persistent CommitmentIdentity with:
    - commitment_id = state.canonical_key (the frozen class identifier)
    - agreement_identity = the agreement this commitment belongs to
    - canonical_key = state.canonical_key
    - local_address = the section reference (if provided)
    - provenance = S0_ORIGIN

    The semantic and temporal fields are copied from the state.

    Args:
        state: the legacy CommitmentState to convert.
        agreement_identity: the agreement identity string.
        section_ref: the agreement-local section reference (e.g.,
            "Section 7.10(a)").  May be None if the section is
            not known.

    Returns:
        A CommitmentKernel with persistent identity.
    """
    binding = AddressBinding(
        section_ref=section_ref or "",
        established_at_version="S0",
    )

    identity = CommitmentIdentity(
        commitment_id=state.canonical_key,
        agreement_identity=agreement_identity,
        canonical_key=state.canonical_key,
        local_address=binding,
        provenance=IdentityProvenance.S0_ORIGIN,
        confidence=1.0,
    )

    kernel_kwargs: dict[str, Any] = {"identity": identity}

    # Copy semantic fields
    for fname in _SEMANTIC_FIELDS:
        val = getattr(state, fname, None)
        if val is not None:
            kernel_kwargs[fname] = val

    # Copy temporal fields
    for fname in _TEMPORAL_FIELDS:
        val = getattr(state, fname, None)
        if val is not None:
            kernel_kwargs[fname] = val

    # Evidentiary fields
    kernel_kwargs["source_document"] = None

    return CommitmentKernel(**kernel_kwargs)


def kernel_to_state(kernel: CommitmentKernel) -> CommitmentState:
    """Convert a canonical CommitmentKernel back to legacy CommitmentState.

    This is used for compatibility with the existing ground-truth
    comparison and metrics layer, which operates on CommitmentState.

    Args:
        kernel: the canonical CommitmentKernel to convert.

    Returns:
        A CommitmentState with the same semantic and temporal fields.
    """
    state_kwargs: dict[str, Any] = {
        "canonical_key": kernel.commitment_id,
        "commitment_type": _infer_commitment_type(kernel),
    }

    # Copy semantic fields
    for fname in _SEMANTIC_FIELDS:
        val = getattr(kernel, fname, None)
        if val is not None:
            state_kwargs[fname] = val

    # Copy temporal fields
    for fname in _TEMPORAL_FIELDS:
        val = getattr(kernel, fname, None)
        if val is not None:
            state_kwargs[fname] = val

    return CommitmentState(**state_kwargs)


def _infer_commitment_type(kernel: CommitmentKernel) -> str:
    """Infer the commitment_type from the canonical key.

    The canonical_key uses the pattern ``<type>.<subject>`` (e.g.,
    ``financial_covenant.leverage_ratio``).  The commitment_type is
    the prefix before the dot.
    """
    ck = kernel.canonical_key
    if "." in ck:
        return ck.split(".")[0]
    return ck


def establish_authoritative_kernel(
    original_state: dict[str, CommitmentState],
    agreement_identity: str,
    section_refs: dict[str, str] | None = None,
) -> tuple[KernelStore, AgreementAddressMap, dict[str, CommitmentKernel]]:
    """Establish the authoritative kernel from legacy original state.

    This is the S0 boundary: it converts the legacy original_state
    (dict[str, CommitmentState]) into a KernelStore of canonical
    CommitmentKernel objects with persistent identity, and an
    AgreementAddressMap that maps section references to commitment IDs.

    Args:
        original_state: the legacy original state dict (S0).
        agreement_identity: the agreement identity string.
        section_refs: optional mapping of canonical_key → section_ref.
            If not provided, section references are inferred from the
            canonical key (best-effort).

    Returns:
        A tuple of (KernelStore, AgreementAddressMap, kernels_by_id):
        - KernelStore with all commitments established at version 0.
        - AgreementAddressMap with section_ref → commitment_id mappings.
        - dict[str, CommitmentKernel] mapping commitment_id to kernel.
    """
    store = KernelStore(agreement_identity=agreement_identity)
    address_map = AgreementAddressMap(agreement_identity=agreement_identity)
    kernels_by_id: dict[str, CommitmentKernel] = {}

    for canonical_key, state in original_state.items():
        section_ref = (
            section_refs.get(canonical_key) if section_refs else None
        )

        kernel = state_to_kernel(
            state,
            agreement_identity=agreement_identity,
            section_ref=section_ref,
        )

        # Register in the kernel store (establishes version 0)
        store.establish_origin(kernel)

        # Register in the address map
        if section_ref:
            address_map.register(
                commitment_id=canonical_key,
                section_ref=section_ref,
                established_at_version="S0",
            )

        kernels_by_id[canonical_key] = kernel

    return store, address_map, kernels_by_id


def store_to_state_dict(
    store: KernelStore,
) -> dict[str, CommitmentState]:
    """Convert a KernelStore's current authoritative state to legacy dict.

    This is used for compatibility with the existing ground-truth
    comparison layer.

    Args:
        store: the KernelStore to convert.

    Returns:
        A dict[str, CommitmentState] of the current authoritative state.
    """
    result: dict[str, CommitmentState] = {}
    for cid, kernel in store.get_all_current().items():
        result[cid] = kernel_to_state(kernel)
    return result
