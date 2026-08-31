"""S0 Commitment Extractor v0.1.

Turns the actual S0 credit agreement into the initial CommitmentState
set for the reconstruction pipeline.

This is the ORIGIN-STATE end of the measurement loop:

    S0 LEGAL DOCUMENT
          ↓
    [ S0 COMMITMENT EXTRACTOR ]   ← this module
          ↓
    structured origin state
          ↓
    amendment chain
          ↓
    parser → semantic mapper → executor → lineage
          ↓
    reconstructed state at T

The S0 extractor uses the shared commitment extraction engine
(commitment_extractor.extract_commitments). It does NOT use any
amendment reconstruction output — the origin state is extracted
independently from the S0 document.

Unsupported clauses → validation queue. No guessing.

Usage:
    from s0_extractor import extract_s0_state
    result = extract_s0_state("data/chain_study/STUDY-016/S0.txt")
    origin_state = result.commitments  # dict[str, CommitmentState]
    validation_queue = result.validation_queue  # clauses for manual review
"""
from __future__ import annotations

from pathlib import Path

from commitment_extractor import (
    ExtractionResult,
    extract_commitments_from_file,
)


def extract_s0_state(s0_path: str | Path) -> ExtractionResult:
    """Extract the origin commitment state from an S0 credit agreement.

    Args:
        s0_path: path to the S0 document text file.

    Returns:
        ExtractionResult with:
          - commitments: the origin-state CommitmentState dict
          - validation_queue: clauses that could not be extracted
          - provenance: per-commitment provenance records

    The returned commitments dict is suitable for use as
    IssuerChain.original_state in the reconstruction pipeline.
    """
    return extract_commitments_from_file(s0_path, source_label="S0")


def extract_s0_state_for_chain(
    chain_id: str,
    s0_path: str | Path,
) -> ExtractionResult:
    """Extract S0 state with chain-id labeled provenance.

    Args:
        chain_id: the chain identifier (e.g., "STUDY-016").
        s0_path: path to the S0 document text file.

    Returns:
        ExtractionResult with chain-id labeled provenance.
    """
    result = extract_s0_state(s0_path)
    # Augment provenance with chain_id
    for p in result.provenance:
        p["chain_id"] = chain_id
    return result
