"""Independent Authoritative Ground-Truth Extractor v0.1.

For chains with composite/conformed/amended-and-restated documents,
independently extracts the final authoritative commitment state.

This is the VALIDATION end of the measurement loop:

    reconstructed state at T
          ↓
    [ AUTHORITATIVE GT EXTRACTOR ]   ← this module
          ↓
    independent structured final state
          ↓
    EXACT COMPARISON

CRITICAL ARCHITECTURAL PRINCIPLE:
    prediction path != validation path

The GT extractor uses the shared commitment extraction engine
(commitment_extractor.extract_commitments) to extract from the
composite/conformed document. It does NOT use amendment reconstruction
output to construct the ground truth. The ground truth is extracted
independently from the authoritative source document.

Unsupported clauses → validation queue. No guessing.

Usage:
    from upsilon.evidence.gt_extractor import extract_ground_truth
    result = extract_ground_truth("data/chain_study/STUDY-015/CMP.txt")
    ground_truth = result.commitments  # dict[str, CommitmentState]
    validation_queue = result.validation_queue  # clauses for manual review
"""
from __future__ import annotations

from pathlib import Path

from upsilon.parsing.commitment_extractor import (
    ExtractionResult,
    extract_commitments_from_file,
)


def extract_ground_truth(cmp_path: str | Path) -> ExtractionResult:
    """Extract the authoritative ground-truth state from a composite/conformed document.

    Args:
        cmp_path: path to the composite/conformed/restated document text file.

    Returns:
        ExtractionResult with:
          - commitments: the ground-truth CommitmentState dict
          - validation_queue: clauses that could not be extracted
          - provenance: per-commitment provenance records

    The returned commitments dict is suitable for use as
    IssuerChain.ground_truth_state in the reconstruction pipeline.
    """
    return extract_commitments_from_file(cmp_path, source_label="CMP")


def extract_ground_truth_for_chain(
    chain_id: str,
    cmp_path: str | Path,
) -> ExtractionResult:
    """Extract ground truth with chain-id labeled provenance.

    Args:
        chain_id: the chain identifier (e.g., "STUDY-015").
        cmp_path: path to the composite/conformed document text file.

    Returns:
        ExtractionResult with chain-id labeled provenance.
    """
    result = extract_ground_truth(cmp_path)
    # Augment provenance with chain_id
    for p in result.provenance:
        p["chain_id"] = chain_id
    return result
