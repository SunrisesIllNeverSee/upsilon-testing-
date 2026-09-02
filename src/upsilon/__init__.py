"""Upsilon/MOSES commitment engine package.

This is the target home for Upsilon runtime engine code, implementing
the conservation-first commitment architecture specified in the MOSES
design documents (docs/moses/).

Architecture:

    SOURCE AGREEMENT
          ↓
    AUTHORITATIVE ORIGIN KERNEL C₀
          ↓
    PERSISTENT COMMITMENT IDENTITIES
          ↓
    AMENDMENT EVIDENCE
          ↓
    AUTHORIZED TRANSFORMATION ENGINE
          ↓
    TRANSFORMATION PROOF
          ↓
    CONSERVATION VALIDATION
          ↓
    LINEAGE EDGE
          ↓
    AUTHORITATIVE SUCCESSOR KERNEL C*
          ↓
    PROPAGATION / DOWNSTREAM COMPARISON

Governing equations:

    C_t = C_{t-1} ⊕ Δ_t_authorized

subject to:

    Δ_t_actual = Δ_t_authorized

and:

    C_t[f] = C_{t-1}[f]  for all f ∉ affected(Δ_t)
"""
from __future__ import annotations

__version__ = "0.1.0"
