"""Build IssuerChain objects for the Development Chain Study v1.

This module constructs IssuerChain objects from the acquired EDGAR
chain data WITHOUT modifying any frozen component (parser, mapper,
executor, authority, lineage, persistence).  It uses:

  - chain_reconstruction.IssuerChain / AmendmentStep (frozen dataclasses)
  - pattern_classifier.classify_amendment (frozen classifier)
  - edgar_chains.all_edgar_chains (frozen fixtures for chains 1-3)

For the 3 existing smoke-test chains (Ameresco, Amedisys, Bausch-Lomb),
the existing fixtures from edgar_chains.py are used — these carry
hand-extracted original_state and ground_truth_state.

For the 22 new chains acquired by acquire_chain_study.py:
  - original_state = {} (empty — S0 commitment extraction is not
    automated; this is a known first-pass limitation recorded in the
    failure taxonomy)
  - amendments = AmendmentStep objects pointing to downloaded text
    files, with pattern classified by the frozen pattern_classifier
  - ground_truth_state = None (no independent ground truth available
    for new chains; this is a known first-pass limitation)
  - is_synthetic = False (all chains are real EDGAR)

The frozen semantic pipeline (semantic_pipeline.run_semantic_pipeline)
parses the amendment source text, maps instructions through the
semantic mapper, executes them, and compares to ground truth.  For
new chains with empty original_state and no ground truth, the pipeline
still measures parser instruction counts, mapper mutation counts,
UNRESOLVED rates, and incorrect mutation rates — the metrics that do
not require ground truth.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from upsilon.lineage.chain_reconstruction import AmendmentStep, IssuerChain
from upsilon.parsing.pattern_classifier import classify_amendment

MANIFEST_JSON = Path("data/chain_study/manifest.json")


def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD date string into a datetime."""
    return datetime.fromisoformat(date_str + "T00:00:00")


def _classify_pattern(text_path: str) -> str:
    """Classify the amendment pattern from the source text.

    Uses the frozen pattern_classifier.  Returns the pattern string
    ('incremental', 'full_restatement', 'conformed_copy', or 'unknown').
    """
    try:
        text = Path(text_path).read_text(encoding="utf-8", errors="ignore")
        if not text:
            return "unknown"
        result = classify_amendment(text)
        return result.pattern.value
    except Exception:  # noqa: BLE001
        return "unknown"


def _build_chain_from_manifest_entry(entry: dict) -> IssuerChain:
    """Build an IssuerChain from a manifest chain entry.

    For new chains:
      - original_state is empty (S0 commitment extraction not automated)
      - amendments point to downloaded text files
      - ground_truth_state is None (no independent ground truth)
    """
    chain_id = entry["chain_id"]
    cik = entry["cik"]
    issuer = entry["issuer"]
    documents = entry["documents"]

    # Find S0 and amendment documents
    amendment_docs = [d for d in documents if d["role"].startswith("A")]
    amendment_docs.sort(key=lambda d: d["role"])

    # Build AmendmentStep objects
    amendments: list[AmendmentStep] = []
    for i, doc in enumerate(amendment_docs, 1):
        text_path = doc["text_path"]
        pattern = _classify_pattern(text_path)
        amendments.append(AmendmentStep(
            amendment_number=i,
            effective_at=_parse_date(doc["file_date"]),
            description=(
                f"{doc['exhibit_description']} "
                f"(filed {doc['file_date']}, accession {doc['accession']})"
            ),
            pattern=pattern,
            parser_instruction_count=None,  # pipeline will compute this
            source_document_path=text_path,
            instructions=[],  # pipeline parses from source text
        ))

    comparison_at = _parse_date(entry["comparison_at"])

    # Build ground-truth label reflecting whether a composite/conformed
    # comparison source was acquired.  Ground-truth *extraction* from the
    # composite source is v0.2 work, but the source itself is recorded.
    cmp_accession = entry.get("comparison_source_accession")
    if cmp_accession:
        gt_label = (
            f"Composite/conformed comparison source acquired for {chain_id} "
            f"(accession {cmp_accession}, filed {entry.get('comparison_source_file_date')}). "
            f"Automated ground-truth extraction from this source is future work (v0.2+). "
            f"Final authoritative source: {entry['final_authoritative_source']}."
        )
    else:
        gt_label = (
            f"No independent ground truth available for {chain_id}. "
            f"Final authoritative source: {entry['final_authoritative_source']} "
            f"(accession {entry['amendment_accessions'][-1]}). "
            f"Ground-truth extraction from composite/conformed source "
            f"is future work (v0.2+)."
        )

    return IssuerChain(
        chain_id=chain_id,
        issuer_name=f"{issuer} (CIK {cik})",
        original_state={},  # S0 commitment extraction not automated
        amendments=amendments,
        comparison_at=comparison_at,
        ground_truth_state=None,  # extraction from composite source is v0.2+
        ground_truth_label=gt_label,
        is_synthetic=False,
    )


def all_study_chains() -> list[IssuerChain]:
    """Return all 25 IssuerChain objects for the Development Chain Study v1.

    Chains 1-3: existing smoke-test chains from edgar_chains.py (with
    hand-extracted ground truth).
    Chains 4-25: new chains from data/chain_study/manifest.json (without
    ground truth).
    """
    from upsilon.ingestion.edgar.edgar_chains import all_edgar_chains

    chains = list(all_edgar_chains())  # 3 existing chains

    if MANIFEST_JSON.exists():
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        for entry in manifest.get("chains", []):
            chains.append(_build_chain_from_manifest_entry(entry))

    return chains


def new_study_chains() -> list[IssuerChain]:
    """Return only the 22 new chains from the manifest (chains 4-25)."""
    if not MANIFEST_JSON.exists():
        return []
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    return [_build_chain_from_manifest_entry(entry) for entry in manifest.get("chains", [])]


def existing_study_chains() -> list[IssuerChain]:
    """Return the 3 existing smoke-test chains (chains 1-3)."""
    from upsilon.ingestion.edgar.edgar_chains import all_edgar_chains
    return list(all_edgar_chains())
