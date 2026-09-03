"""Commitment lineage graph — first-class semantic domain.

Lineage is a first-class semantic domain, not a logging utility.
It owns the append-only authoritative history of transformations
applied to persistent commitment identities.

See:
- COMMITMENT_LINEAGE_SCHEMA.md
- src/upsilon/lineage/README.md
- docs/moses/CONSERVATION_INVARIANTS.md §2.7 (lineage continuity)
"""
from __future__ import annotations

from .graph import CommitmentLineageGraph
from .queries import LineageQueries

__all__ = [
    "CommitmentLineageGraph",
    "LineageQueries",
]
