"""Commitment lineage graph.

Implements the append-only lineage graph specified in
``COMMITMENT_LINEAGE_SCHEMA.md`` and the addendum §3.

The lineage graph records:
- ORIGINATES_FROM edges (agreement version -> commitment)
- MODIFIES edges (amendment -> commitment version change)
- SUPERSEDES edges (commitment version supersedes predecessor)
- WAIVES / REINSTATES edges
- DERIVES_FROM / PROPAGATES_TO edges (downstream)

Every state-changing lineage edge must point to the
authority_version_id that legally supports it.

Lineage continuity invariant (CONSERVATION_INVARIANTS.md §2.7):

    C_t -> lineage_edge -> C_{t-1} -> lineage_edge -> ... -> C_0
"""
from __future__ import annotations

from upsilon.models import (
    EdgeClass,
    LineageEdge,
    TransformationFamily,
    ValidationStatus,
)


class CommitmentLineageGraph:
    """Append-only commitment lineage graph.

    The graph is append-only: edges may be added but never removed.
    An edge's validation_status may transition PENDING -> VALIDATED
    or PENDING -> REJECTED, but a VALIDATED edge may not be un-validated.
    """

    def __init__(self, agreement_identity: str) -> None:
        self.agreement_identity = agreement_identity
        self._edges: list[LineageEdge] = []
        self._edges_by_id: dict[str, LineageEdge] = {}
        # commitment_id -> list of edge indices
        self._edges_by_commitment: dict[str, list[LineageEdge]] = {}
        # amendment_id -> list of edges
        self._edges_by_amendment: dict[str, list[LineageEdge]] = {}

    def add_edge(self, edge: LineageEdge) -> LineageEdge:
        """Add a lineage edge to the graph.

        The graph is append-only.  Once added, an edge cannot be
        removed.  Its validation_status may be updated via
        ``validate_edge``.
        """
        if edge.edge_id in self._edges_by_id:
            raise ValueError(
                f"Lineage edge {edge.edge_id} already exists "
                f"(graph is append-only)"
            )
        self._edges.append(edge)
        self._edges_by_id[edge.edge_id] = edge
        self._edges_by_commitment.setdefault(
            edge.successor_commitment_id, []
        ).append(edge)
        self._edges_by_amendment.setdefault(
            edge.amendment_id, []
        ).append(edge)
        return edge

    def validate_edge(self, edge_id: str) -> None:
        """Mark a lineage edge as VALIDATED.

        A VALIDATED edge may not be un-validated.
        """
        edge = self._edges_by_id.get(edge_id)
        if edge is None:
            raise KeyError(f"Lineage edge {edge_id} not found")
        if edge.validation_status == ValidationStatus.REJECTED:
            raise ValueError(
                f"Cannot validate rejected edge {edge_id}"
            )
        edge.validation_status = ValidationStatus.VALIDATED

    def reject_edge(self, edge_id: str) -> None:
        """Mark a lineage edge as REJECTED."""
        edge = self._edges_by_id.get(edge_id)
        if edge is None:
            raise KeyError(f"Lineage edge {edge_id} not found")
        if edge.validation_status == ValidationStatus.VALIDATED:
            raise ValueError(
                f"Cannot reject validated edge {edge_id}"
            )
        edge.validation_status = ValidationStatus.REJECTED

    def get_edge(self, edge_id: str) -> LineageEdge | None:
        """Get a lineage edge by ID."""
        return self._edges_by_id.get(edge_id)

    def edges_for_commitment(self, commitment_id: str) -> list[LineageEdge]:
        """Get all lineage edges involving a commitment (as successor)."""
        return list(self._edges_by_commitment.get(commitment_id, []))

    def edges_for_amendment(self, amendment_id: str) -> list[LineageEdge]:
        """Get all lineage edges produced by an amendment."""
        return list(self._edges_by_amendment.get(amendment_id, []))

    def all_edges(self) -> list[LineageEdge]:
        """Get all lineage edges in the graph."""
        return list(self._edges)

    def validated_edges(self) -> list[LineageEdge]:
        """Get all validated lineage edges."""
        return [
            e for e in self._edges
            if e.validation_status == ValidationStatus.VALIDATED
        ]

    def trace_to_origin(self, commitment_id: str) -> list[LineageEdge]:
        """Trace a commitment back to its origin through lineage edges.

        Returns the chain of edges from the current version back to
        the origin (C_0).  The chain is ordered most-recent-first.

        For identity-preserving chains (predecessor == successor), all
        edges for the same commitment are walked in reverse insertion
        order.  For identity-changing edges (CREATE, TERMINATE,
        RENUMBER), the trace follows the predecessor_commitment_id.

        If the chain is broken (a predecessor has no edge), the trace
        stops and returns what was found.  A complete trace reaches
        an ORIGINATES_FROM edge, a CREATE edge, or the earliest edge
        for a commitment (whose predecessor is the origin kernel C_0,
        established outside the lineage graph).
        """
        chain: list[LineageEdge] = []
        current_id: str | None = commitment_id
        visited_edges: set[str] = set()

        while current_id is not None:
            edges = self._edges_by_commitment.get(current_id, [])
            # Most-recent-first, skipping edges already traced
            candidates = [
                e for e in reversed(edges) if e.edge_id not in visited_edges
            ]
            if not candidates:
                break
            edge = candidates[0]
            visited_edges.add(edge.edge_id)
            chain.append(edge)
            if edge.predecessor_commitment_id != edge.successor_commitment_id:
                # Identity-changing: follow the predecessor
                current_id = edge.predecessor_commitment_id
            # Identity-preserving: current_id stays the same; the next
            # iteration picks up the next unvisited edge for this commitment

        return chain

    def is_reachable_from_origin(self, commitment_id: str) -> bool:
        """Check if a commitment is reachable from the origin kernel.

        Per lineage continuity invariant: the current authoritative
        state must be reachable from the origin kernel through valid
        lineage edges.

        A commitment is reachable from origin if trace_to_origin
        produces a non-empty chain whose terminal (earliest) edge is
        either:
        - an ORIGINATES_FROM edge, or
        - a CREATE edge (no predecessor), or
        - an identity-preserving edge (the earliest edge for this
          commitment, whose predecessor is the origin kernel C_0
          established outside the lineage graph).

        If the terminal edge is identity-changing and its predecessor
        has no edges in the graph, the chain is broken — the
        predecessor was never established through the lineage graph.
        """
        chain = self.trace_to_origin(commitment_id)
        if not chain:
            return False
        terminal = chain[-1]
        # Origin-type edges are always reachable
        if terminal.edge_class == EdgeClass.ORIGINATES_FROM:
            return True
        if terminal.transformation_type == TransformationFamily.CREATE:
            # CREATE is an origin edge only if it has no parent (predecessor
            # is None or same as successor — a truly new commitment).
            # If CREATE has a different predecessor, the predecessor must
            # be established in the graph.
            if terminal.predecessor_commitment_id in (
                None, terminal.successor_commitment_id
            ):
                return True
            pred_id = terminal.predecessor_commitment_id
            pred_edges = self._edges_by_commitment.get(pred_id, [])
            return len(pred_edges) > 0
        # Identity-preserving terminal: this is the earliest edge for
        # this commitment.  The predecessor is the origin kernel C_0,
        # established outside the lineage graph.  This is reachable.
        if terminal.predecessor_commitment_id == terminal.successor_commitment_id:
            return True
        # Identity-changing terminal: the predecessor must exist in the
        # graph.  If the predecessor has no edges, the chain is broken.
        pred_id = terminal.predecessor_commitment_id
        if pred_id is None:
            return False
        pred_edges = self._edges_by_commitment.get(pred_id, [])
        return len(pred_edges) > 0
