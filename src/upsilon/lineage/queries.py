"""Lineage queries.

Provides query interfaces over the commitment lineage graph.
"""
from __future__ import annotations

from upsilon.models import (
    LineageEdge,
    TransformationFamily,
    ValidationStatus,
)

from .graph import CommitmentLineageGraph


class LineageQueries:
    """Query interface over the commitment lineage graph."""

    def __init__(self, graph: CommitmentLineageGraph) -> None:
        self._graph = graph

    def history(self, commitment_id: str) -> list[LineageEdge]:
        """Get the full transformation history for a commitment.

        Returns all lineage edges involving this commitment, ordered
        oldest-first.
        """
        edges = self._graph.edges_for_commitment(commitment_id)
        return list(reversed(edges))

    def transformations_by_type(
        self, transformation_type: TransformationFamily
    ) -> list[LineageEdge]:
        """Get all lineage edges of a specific transformation type."""
        return [
            e for e in self._graph.all_edges()
            if e.transformation_type == transformation_type
        ]

    def amendments_affecting(self, commitment_id: str) -> list[str]:
        """Get the list of amendment IDs that affected a commitment."""
        edges = self._graph.edges_for_commitment(commitment_id)
        return list({e.amendment_id for e in edges})

    def validated_history(self, commitment_id: str) -> list[LineageEdge]:
        """Get only validated lineage edges for a commitment."""
        edges = self._graph.edges_for_commitment(commitment_id)
        return [
            e for e in edges
            if e.validation_status == ValidationStatus.VALIDATED
        ]

    def has_unvalidated_edges(self, commitment_id: str) -> bool:
        """Check if a commitment has any pending/rejected lineage edges."""
        edges = self._graph.edges_for_commitment(commitment_id)
        return any(
            e.validation_status != ValidationStatus.VALIDATED
            for e in edges
        )

    def affected_fields_history(self, commitment_id: str) -> dict[str, list]:
        """Get the history of changes to each field for a commitment.

        Returns a dict mapping field_name -> list of (edge, old_value, new_value).
        """
        history: dict[str, list] = {}
        for edge in self._graph.edges_for_commitment(commitment_id):
            for field_name in edge.affected_fields:
                old_val = edge.old_values.get(field_name)
                new_val = edge.new_values.get(field_name)
                history.setdefault(field_name, []).append(
                    (edge, old_val, new_val)
                )
        return history
