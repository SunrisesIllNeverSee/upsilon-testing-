"""Semantic transformation proof records.

This subdomain owns validated semantic transformation evidence
records.  It may not invent semantic interpretation.

See:
- docs/moses/SEMANTIC_PROOF_RECORD.md
"""
from __future__ import annotations

from .transformation_proof import ProofAssembler, ProofBuilder

__all__ = [
    "ProofAssembler",
    "ProofBuilder",
]
