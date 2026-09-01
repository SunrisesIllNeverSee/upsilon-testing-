"""Build the v1 UNRESOLVED instruction corpus (Step 21 / Section A).

Creates a machine-readable corpus of every v1 UNRESOLVED instruction
across all 50 known real issuer chains (25 development + 25 v1 held-out).

For each record captures:
  - chain
  - issuer
  - accession
  - document genre
  - section
  - source span
  - instruction type
  - parser target
  - surrounding context
  - current commitment state
  - candidate canonical commitment
  - candidate field
  - reason unresolved

Clusters by root cause.

Usage:
    python build_unresolved_corpus.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from amendment_parser import parse_v04
from commitment_registry import resolve_commitment_from_text
from models import (
    AmendmentInstruction,
    InstructionProvenance,
    InstructionType,
)
from pattern_classifier import classify_amendment
from semantic_mapper import AmbiguityReason, map_instruction


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class UnresolvedRecord:
    """One UNRESOLVED instruction record."""

    chain: str
    issuer: str
    accession: str
    document_genre: str
    amendment_number: int
    section: str
    source_span: str
    instruction_type: str
    parser_target: str | None
    surrounding_context: str
    current_commitment_state_keys: list[str]
    candidate_canonical_commitment: str | None
    candidate_field: str | None
    reason_unresolved: str
    root_cause_cluster: str


@dataclass
class UnresolvedCorpus:
    """The full unresolved corpus with clustering."""

    records: list[UnresolvedRecord] = field(default_factory=list)
    root_cause_distribution: dict[str, int] = field(default_factory=dict)
    instruction_type_distribution: dict[str, int] = field(default_factory=dict)
    section_distribution: dict[str, int] = field(default_factory=dict)
    genre_distribution: dict[str, int] = field(default_factory=dict)
    total_chains: int = 0
    total_instructions: int = 0
    total_unresolved: int = 0
    total_mapped: int = 0
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Root-cause clustering
# ---------------------------------------------------------------------------


def _classify_root_cause(
    instruction_type: str,
    ambiguity_reason: str,
    section_ref: str | None,
    source_text: str,
    candidate_commitment: str | None,
) -> str:
    """Classify the root cause of an UNRESOLVED instruction.

    Root cause clusters:
      RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT
        The parser detected a section restatement but the mapper has no
        rule to identify which commitment is being restated.

      RC-02: RESTATE_SECTION_AMBIGUOUS_VALUE
        The commitment was identified but the new value could not be
        extracted from the restated text.

      RC-03: ADD_UNKNOWN_COMMITMENT
        The parser detected an addition but the mapper cannot identify
        what commitment is being added.

      RC-04: REPLACE_TEXT_UNKNOWN_COMMITMENT
        The parser detected a text replacement but the mapper cannot
        identify which commitment/field is being changed.

      RC-05: DELETE_UNKNOWN_COMMITMENT
        The parser detected a deletion but the mapper cannot identify
        which commitment is being deleted.

      RC-06: DEFINITION_SECTION_NO_COVENANT
        The instruction targets a definitions section (Section 1.01,
        Section 1.1) that may contain covenant definitions but the
        mapper has no rule to extract them.

      RC-07: NON_COVENANT_SECTION
        The instruction targets a section that does not contain any
        commitment-related content (e.g., administrative sections,
        representations, conditions precedent).

      RC-08: COVENANT_IDENTIFIED_VALUE_EXTRACTION_FAILED
        The registry resolved a candidate commitment but the value
        extractor could not parse the new value from the text.

      RC-09: OTHER
        Catch-all for instructions that don't fit any above cluster.
    """
    section_lower = (section_ref or "").lower()
    text_lower = (source_text or "").lower()

    # Definitions section — common source of unresolved RESTATE_SECTION
    is_def_section = bool(
        re.search(r"section\s+1\.(0?1|02)\b", section_lower)
        or "definition" in text_lower[:200]
    )

    # Check if the text contains any covenant keywords
    covenant_kw = [
        "leverage", "ebitda", "covenant", "threshold", "ratio",
        "interest coverage", "tangible net worth", "current ratio",
        "debt service", "fixed charge", "term loan", "revolving",
        "maturity", "facility", "texas ratio", "tier 1",
        "risk.based capital", "return on average assets",
    ]
    has_covenant_kw = any(kw in text_lower for kw in covenant_kw)

    if ambiguity_reason == AmbiguityReason.AMBIGUOUS_VALUE.value:
        if instruction_type == InstructionType.RESTATE_SECTION.value:
            return "RC-02: RESTATE_SECTION_AMBIGUOUS_VALUE"
        return "RC-08: COVENANT_IDENTIFIED_VALUE_EXTRACTION_FAILED"

    # unknown_commitment cases
    if is_def_section and not has_covenant_kw:
        return "RC-06: DEFINITION_SECTION_NO_COVENANT"

    if not has_covenant_kw and candidate_commitment is None:
        return "RC-07: NON_COVENANT_SECTION"

    if instruction_type == InstructionType.RESTATE_SECTION.value:
        if candidate_commitment is not None:
            return "RC-08: COVENANT_IDENTIFIED_VALUE_EXTRACTION_FAILED"
        return "RC-01: RESTATE_SECTION_UNKNOWN_COMMITMENT"

    if instruction_type == InstructionType.ADD.value:
        return "RC-03: ADD_UNKNOWN_COMMITMENT"

    if instruction_type == InstructionType.REPLACE_TEXT.value:
        return "RC-04: REPLACE_TEXT_UNKNOWN_COMMITMENT"

    if instruction_type == InstructionType.DELETE.value:
        return "RC-05: DELETE_UNKNOWN_COMMITMENT"

    return "RC-09: OTHER"


# ---------------------------------------------------------------------------
# Corpus builder
# ---------------------------------------------------------------------------


def _process_chain(
    chain_id: str,
    issuer: str,
    documents: list[dict],
    current_state_keys: list[str] | None = None,
) -> tuple[list[UnresolvedRecord], int, int, int]:
    """Process one chain's amendments and return UNRESOLVED records.

    Returns:
        (records, total_instructions, total_mapped, total_unresolved)
        where total_instructions/mapped/unresolved are accumulated across
        all amendment documents in this chain.  This avoids a second
        parse+map pass to compute the corpus totals.
    """
    records: list[UnresolvedRecord] = []
    state_keys = current_state_keys or []
    chain_total = 0
    chain_mapped = 0
    chain_unresolved = 0

    amendment_docs = [d for d in documents if d["role"].startswith("A")]
    amendment_docs.sort(key=lambda d: d["role"])

    for i, doc in enumerate(amendment_docs, 1):
        text_path = doc["text_path"]
        try:
            text = Path(text_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue

        if not text:
            continue

        # Classify genre
        genre = classify_amendment(text).pattern.value

        # Parse
        parser_result = parse_v04(text)
        instructions = parser_result["instructions"]

        for j, ins_row in enumerate(instructions):
            chain_total += 1
            ins = AmendmentInstruction(
                order=j + 1,
                instruction_type=InstructionType(ins_row["instruction_type"]),
                target_section_ref=ins_row.get("target_section_ref"),
                source_text=ins_row.get("source_text"),
                old_value=ins_row.get("old_value"),
                new_value=ins_row.get("new_value"),
                provenance=InstructionProvenance.PARSER,
            )

            # Map through v1 mapper
            mr = map_instruction(ins)

            # If mapped successfully, count and skip
            if mr.mutations:
                chain_mapped += len(mr.mutations)
                continue

            # This is UNRESOLVED — build a record
            for u in mr.unresolved:
                chain_unresolved += 1
                source_span = (ins.source_text or "")[:500]
                surrounding = (ins.source_text or "")[:200].replace("\n", " ")

                # Try to resolve a candidate commitment using the v2 registry
                candidate_cid, candidate_field, _ = resolve_commitment_from_text(
                    source_span,
                    ins.target_section_ref,
                )

                root_cause = _classify_root_cause(
                    ins.instruction_type.value,
                    u.ambiguity_reason.value if u.ambiguity_reason else "unknown",
                    ins.target_section_ref,
                    source_span,
                    candidate_cid,
                )

                records.append(UnresolvedRecord(
                    chain=chain_id,
                    issuer=issuer,
                    accession=doc.get("accession", ""),
                    document_genre=genre,
                    amendment_number=i,
                    section=ins.target_section_ref or "",
                    source_span=source_span,
                    instruction_type=ins.instruction_type.value,
                    parser_target=ins.target_section_ref,
                    surrounding_context=surrounding,
                    current_commitment_state_keys=list(state_keys),
                    candidate_canonical_commitment=candidate_cid,
                    candidate_field=candidate_field,
                    reason_unresolved=u.ambiguity_reason.value if u.ambiguity_reason else "unknown",
                    root_cause_cluster=root_cause,
                ))

    return records, chain_total, chain_mapped, chain_unresolved


def _build_documents_from_chain(chain: Any) -> list[dict]:
    """Build a documents list from a chain's amendments.

    Used for chains that have no manifest entry (e.g., the EDGAR-*
    development chains).  Each amendment step becomes one document dict
    with the fields _process_chain needs: role, text_path, accession.
    """
    documents: list[dict] = []
    for step in chain.amendments:
        if not step.source_document_path:
            continue
        documents.append({
            "role": f"A{step.amendment_number}",
            "text_path": step.source_document_path,
            "accession": "",
        })
    return documents


def _find_chain_documents(chain_id: str, source: str) -> list[dict] | None:
    """Find the documents list for a chain from the appropriate manifest.

    Returns the manifest's documents list if the chain has a manifest
    entry, or None if it does not (caller should fall back to
    _build_documents_from_chain).
    """
    if source == "dev":
        manifest_path = Path("data/chain_study/manifest.json")
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest.get("chains", []):
                if entry["chain_id"] == chain_id:
                    return entry["documents"]
        return None
    elif source == "held_out":
        manifest_path = Path("data/held_out/manifest.json")
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest.get("chains", []):
                if entry["chain_id"] == chain_id:
                    return entry["documents"]
    return None


def build_unresolved_corpus() -> UnresolvedCorpus:
    """Build the unresolved corpus from all 50 chains.

    Returns the corpus with root-cause clustering.  Totals
    (total_instructions, total_mapped, total_unresolved) are accumulated
    during the single parse+map pass — no second pass is needed.
    """
    from run_chain_study_v2 import all_v2_chains
    from run_held_out_study import all_held_out_chains

    corpus = UnresolvedCorpus()
    corpus.generated_at = datetime.now(UTC).isoformat()

    total_instructions = 0
    total_mapped = 0
    total_unresolved = 0

    # --- 25 development chains ---
    dev_chains = all_v2_chains()
    for chain, s0_result, gt_result in dev_chains:
        state_keys = list(chain.original_state.keys())
        # Find the manifest entry for this chain; fall back to building
        # documents from chain.amendments (EDGAR-* chains have no
        # manifest entry).
        documents = _find_chain_documents(chain.chain_id, "dev")
        if documents is None:
            documents = _build_documents_from_chain(chain)
        records, n_total, n_mapped, n_unresolved = _process_chain(
            chain.chain_id, chain.issuer_name, documents, state_keys,
        )
        corpus.records.extend(records)
        total_instructions += n_total
        total_mapped += n_mapped
        total_unresolved += n_unresolved

    # --- 25 held-out chains ---
    held_chains = all_held_out_chains()
    for chain, s0_result, gt_result in held_chains:
        state_keys = list(chain.original_state.keys())
        documents = _find_chain_documents(chain.chain_id, "held_out")
        if documents is None:
            documents = _build_documents_from_chain(chain)
        records, n_total, n_mapped, n_unresolved = _process_chain(
            chain.chain_id, chain.issuer_name, documents, state_keys,
        )
        corpus.records.extend(records)
        total_instructions += n_total
        total_mapped += n_mapped
        total_unresolved += n_unresolved

    # Compute distributions
    corpus.total_chains = len(dev_chains) + len(held_chains)
    corpus.total_instructions = total_instructions
    corpus.total_mapped = total_mapped
    corpus.total_unresolved = total_unresolved
    corpus.root_cause_distribution = dict(Counter(
        r.root_cause_cluster for r in corpus.records
    ))
    corpus.instruction_type_distribution = dict(Counter(
        r.instruction_type for r in corpus.records
    ))
    corpus.section_distribution = dict(Counter(
        r.section for r in corpus.records
    ))
    corpus.genre_distribution = dict(Counter(
        r.document_genre for r in corpus.records
    ))

    return corpus


def render_corpus_report(corpus: UnresolvedCorpus) -> str:
    """Render the unresolved corpus report as markdown."""
    lines: list[str] = []
    lines.append("# Step 21A — v1 UNRESOLVED Instruction Corpus")
    lines.append("")
    lines.append(f"**Generated:** {corpus.generated_at}")
    lines.append(f"**Total chains:** {corpus.total_chains}")
    lines.append(f"**Total parser instructions:** {corpus.total_instructions}")
    lines.append(f"**Total UNRESOLVED:** {corpus.total_unresolved}")
    lines.append(f"**Total mapped (v1):** {corpus.total_mapped}")
    lines.append("")

    lines.append("## Root-cause distribution")
    lines.append("")
    lines.append("| Cluster | Count | % |")
    lines.append("|---|---:|---:|")
    for cluster, count in sorted(
        corpus.root_cause_distribution.items(), key=lambda x: -x[1]
    ):
        pct = count / corpus.total_unresolved * 100 if corpus.total_unresolved else 0
        lines.append(f"| {cluster} | {count} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Instruction type distribution")
    lines.append("")
    lines.append("| Type | Count |")
    lines.append("|---|---:|")
    for t, count in sorted(
        corpus.instruction_type_distribution.items(), key=lambda x: -x[1]
    ):
        lines.append(f"| {t} | {count} |")
    lines.append("")

    lines.append("## Document genre distribution")
    lines.append("")
    lines.append("| Genre | Count |")
    lines.append("|---|---:|")
    for g, count in sorted(
        corpus.genre_distribution.items(), key=lambda x: -x[1]
    ):
        lines.append(f"| {g} | {count} |")
    lines.append("")

    lines.append("## Top 20 sections")
    lines.append("")
    lines.append("| Section | Count |")
    lines.append("|---|---:|")
    for s, count in sorted(
        corpus.section_distribution.items(), key=lambda x: -x[1]
    )[:20]:
        lines.append(f"| {s!r} | {count} |")
    lines.append("")

    # Candidate resolution rate
    resolved = sum(
        1 for r in corpus.records if r.candidate_canonical_commitment is not None
    )
    lines.append("## v2 registry candidate resolution")
    lines.append("")
    lines.append(f"- UNRESOLVED records with a v2 registry candidate: {resolved}/{corpus.total_unresolved}")
    if corpus.total_unresolved:
        lines.append(f"- Candidate resolution rate: {resolved / corpus.total_unresolved:.1%}")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    print("Building v1 UNRESOLVED corpus from 50 chains...")

    corpus = build_unresolved_corpus()

    # Write machine-readable corpus
    output_path = Path("results/step_21_unresolved_corpus.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_json = {
        "generated_at": corpus.generated_at,
        "total_chains": corpus.total_chains,
        "total_instructions": corpus.total_instructions,
        "total_unresolved": corpus.total_unresolved,
        "total_mapped": corpus.total_mapped,
        "root_cause_distribution": corpus.root_cause_distribution,
        "instruction_type_distribution": corpus.instruction_type_distribution,
        "section_distribution": corpus.section_distribution,
        "genre_distribution": corpus.genre_distribution,
        "records": [asdict(r) for r in corpus.records],
    }
    output_path.write_text(json.dumps(corpus_json, indent=2), encoding="utf-8")
    print(f"Corpus JSON: {output_path} ({len(corpus.records)} records)")

    # Write report
    report = render_corpus_report(corpus)
    report_path = Path("results/step_21_unresolved_corpus_report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}")

    # Print summary
    print()
    print("=" * 60)
    print("UNRESOLVED CORPUS SUMMARY")
    print("=" * 60)
    print(f"Total chains:              {corpus.total_chains}")
    print(f"Total parser instructions: {corpus.total_instructions}")
    print(f"Total UNRESOLVED:          {corpus.total_unresolved}")
    print(f"Total mapped (v1):         {corpus.total_mapped}")
    print()
    print("Root-cause distribution:")
    for cluster, count in sorted(
        corpus.root_cause_distribution.items(), key=lambda x: -x[1]
    ):
        print(f"  {cluster}: {count}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
