"""Commitment kernel store and origin kernel builder.

Implements the kernel management specified in
``docs/moses/COMMITMENT_KERNEL.md``.

The origin kernel C0 is the set of commitments extracted from the
source agreement (S0).  It is established by the commitment extractor
from the original credit agreement.  It is the starting point for all
amendment transformations.

The current authoritative kernel C*t is the set of commitments that
results from applying all authorized transformations from C0 through
the current amendment:

    C*t = Apply(C*t-1, Delta_t)

where each Delta_t has a valid proof record and has passed conservation
validation.
"""
from __future__ import annotations

from datetime import UTC, datetime

from upsilon.models import (
    CommitmentIdentity,
    CommitmentKernel,
    KernelVersion,
)


class KernelStore:
    """In-memory store for commitment kernels with version tracking.

    The store maintains:
    - The current authoritative kernel (C*t) — the set of commitments
      that results from applying all authorized transformations.
    - Version history for each commitment — supporting lineage tracing
      and temporal queries.

    Versions are immutable once produced.  A new transformation
    produces a new version; it does not mutate the existing one.
    """

    def __init__(self, agreement_identity: str) -> None:
        self.agreement_identity = agreement_identity
        # commitment_id -> current CommitmentKernel
        self._current: dict[str, CommitmentKernel] = {}
        # commitment_id -> list of KernelVersion (history)
        self._versions: dict[str, list[KernelVersion]] = {}

    def establish_origin(self, kernel: CommitmentKernel) -> KernelVersion:
        """Establish a commitment in the origin kernel (C0).

        This is the starting point.  The commitment gets version 0.
        """
        cid = kernel.commitment_id
        if cid in self._current:
            raise ValueError(
                f"Commitment {cid} already exists in kernel store"
            )

        version = KernelVersion(
            commitment_id=cid,
            version_number=0,
            valid_from=kernel.valid_from or datetime.min.replace(tzinfo=UTC),
            produced_by_proof_id="ORIGIN",
            predecessor_version=None,
        )
        kernel.version = version
        self._current[cid] = kernel
        self._versions[cid] = [version]
        return version

    def get_current(self, commitment_id: str) -> CommitmentKernel | None:
        """Get the current authoritative kernel for a commitment."""
        return self._current.get(commitment_id)

    def get_all_current(self) -> dict[str, CommitmentKernel]:
        """Get all current authoritative kernels."""
        return dict(self._current)

    def advance(
        self,
        commitment_id: str,
        successor: CommitmentKernel,
        proof_id: str,
        expected_predecessor_version: int | None = None,
    ) -> KernelVersion:
        """Advance a commitment to a new version.

        The predecessor kernel is preserved in version history.  The
        successor becomes the current authoritative kernel.

        This does NOT grant authority — that is the authority gate's
        job.  This method is called only after the authority gate has
        granted AUTHORITY_GRANTED.

        If ``expected_predecessor_version`` is provided, the advance
        fails closed if the current predecessor version does not
        match.  This prevents stale-version execution (a candidate
        computed against an older predecessor being committed on top
        of a newer one).
        """
        predecessor = self._current.get(commitment_id)
        if predecessor is None:
            raise ValueError(
                f"Commitment {commitment_id} not in kernel store"
            )

        pred_version = predecessor.version
        pred_version_num = pred_version.version_number if pred_version else 0

        # Stale-version check: if the caller expected a specific
        # predecessor version, verify it matches.  This prevents
        # a candidate computed against an older predecessor from
        # being committed on top of a newer one.
        if expected_predecessor_version is not None:
            if pred_version_num != expected_predecessor_version:
                raise ValueError(
                    f"Predecessor version mismatch for {commitment_id}: "
                    f"expected {expected_predecessor_version}, "
                    f"actual {pred_version_num}"
                )

        new_version = KernelVersion(
            commitment_id=commitment_id,
            version_number=pred_version_num + 1,
            valid_from=successor.valid_from or datetime.min.replace(tzinfo=UTC),
            produced_by_proof_id=proof_id,
            predecessor_version=pred_version_num,
        )
        successor.version = new_version
        self._current[commitment_id] = successor
        self._versions[commitment_id].append(new_version)
        return new_version

    def rollback(
        self, commitment_id: str, predecessor: CommitmentKernel,
    ) -> None:
        """Roll back a commitment to a predecessor kernel.

        Called when the authority gate blocks promotion after
        ``advance`` was called.  The provisional successor that was
        advanced into the store is replaced by the predecessor so
        authoritative current state remains the predecessor.

        This is a public API — callers must NOT reach into private
        members (``_current``, ``_versions``) directly.  The rollback
        restores the predecessor as current and drops the rolled-back
        version from history so version numbering stays monotonic.
        """
        pred_version = predecessor.version
        self._current[commitment_id] = predecessor
        if commitment_id in self._versions:
            versions = self._versions[commitment_id]
            if versions and versions[-1].version_number != (
                pred_version.version_number if pred_version else 0
            ):
                versions.pop()

    def get_version_history(self, commitment_id: str) -> list[KernelVersion]:
        """Get the full version history for a commitment."""
        return list(self._versions.get(commitment_id, []))

    def get_predecessor(self, commitment_id: str) -> CommitmentKernel | None:
        """Get the predecessor kernel for a commitment.

        Returns the current kernel (which is the predecessor of the
        next transformation).  This is C_{t-1} for the next amendment.
        """
        return self._current.get(commitment_id)

    def authoritative_kernel(self, at_time: datetime | None = None) -> dict[str, CommitmentKernel]:
        """Get the authoritative kernel K(A,T) at a point in time.

        Per COMMITMENT_LINEAGE_SCHEMA.md temporal authority rule:

            K(A,T) = all commitment versions
                     whose valid_from <= T
                     and (valid_to is null or valid_to > T)
                     and whose source authority is effective by T
        """
        if at_time is None:
            return dict(self._current)

        result: dict[str, CommitmentKernel] = {}
        for cid, kernel in self._current.items():
            if kernel.valid_from and kernel.valid_from > at_time:
                continue
            if kernel.valid_to and kernel.valid_to <= at_time:
                continue
            result[cid] = kernel
        return result


class OriginKernelBuilder:
    """Builds the origin kernel (C0) from source agreement extraction.

    The origin kernel is the set of commitments extracted from the
    source agreement (S0).  It is human-validated / independently
    established.  The amendment interpreter begins with an authoritative
    predecessor object whenever one is available.
    """

    def __init__(self, agreement_identity: str) -> None:
        self._agreement_identity = agreement_identity
        self._kernels: list[CommitmentKernel] = []

    def add_commitment(
        self,
        identity: CommitmentIdentity,
        **semantic_fields: object,
    ) -> CommitmentKernel:
        """Add a commitment to the origin kernel."""
        kernel = CommitmentKernel(identity=identity, **semantic_fields)
        self._kernels.append(kernel)
        return kernel

    def build(self, store: KernelStore) -> dict[str, KernelVersion]:
        """Build the origin kernel into a kernel store.

        Returns a mapping of commitment_id -> KernelVersion for all
        established commitments.
        """
        versions: dict[str, KernelVersion] = {}
        for kernel in self._kernels:
            version = store.establish_origin(kernel)
            versions[kernel.commitment_id] = version
        return versions
