"""Document-genre adapters (Step 21 / Section E).

Implements separate processing paths for each amendment genre:

  INCREMENTAL
    parser → semantic resolver → executor

  FULL_RESTATEMENT
    direct authoritative snapshot extraction
    → commitment-state comparison / lineage

  CONFORMED_COPY
    HTML redline / strike / underline diff
    → semantic resolver

  UNKNOWN
    improve genre classification from observed 50-chain evidence.

Each adapter takes an amendment step (source text + current state) and
produces a list of StructuredMutation candidates (mapped or unresolved).

The adapters do NOT bypass the executor.  They produce candidates that
go through the same frozen executor safety guards.  The difference is
how the candidates are generated:
  - INCREMENTAL: parser → resolver (the existing path)
  - FULL_RESTATEMENT: extract commitments directly from the restated
    document, then diff against current state to produce mutations
  - CONFORMED_COPY: strip redline markup, extract clean text, then
    run the resolver on the clean text
  - UNKNOWN: try the incremental path; if no instructions, fall back
    to full_restatement extraction

Architecture:

    amendment source text
        ↓
    genre classifier (pattern_classifier.classify_amendment)
        ↓
    ┌─────────────────┬──────────────────┬──────────────────┬─────────┐
    │   INCREMENTAL   │ FULL_RESTATEMENT │  CONFORMED_COPY  │ UNKNOWN │
    └────────┬────────┴────────┬─────────┴────────┬─────────┴────┬────┘
             ↓                 ↓                  ↓              ↓
        parse_v04      extract from          strip redline     try
             ↓         restated text         → parse_v04      incremental
        resolver v2          ↓                    ↓              ↓
             ↓          diff vs          resolver v2       fallback to
        candidates      current state       candidates       full_restate
                            ↓
                       candidates
             ↓                 ↓                  ↓              ↓
             └─────────────────┴──────────────────┴──────────────────┘
                               ↓
                    deterministic validators
                               ↓
                    executor (frozen safety guards)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from upsilon.parsing.amendment_parser import parse_v04
from upsilon.parsing.commitment_extractor import extract_commitments
from upsilon.commitments.commitment_registry import resolve_commitment_from_text
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)
from upsilon.parsing.pattern_classifier import AmendmentPattern, classify_amendment
from upsilon.transformations.semantic_mapper import (
    AmbiguityReason,
    MappingResult,
    StructuredMutation,
)
from upsilon.transformations.semantic_resolver_v2 import resolve_instruction


# ---------------------------------------------------------------------------
# Genre adapter result
# ---------------------------------------------------------------------------


@dataclass
class GenreAdapterResult:
    """Result of processing one amendment through a genre adapter.

    Fields:
        genre: the detected amendment genre.
        candidates: StructuredMutation candidates (mapped or unresolved).
        parser_instruction_count: number of parser instructions
            detected (0 for full_restatement/conformed_copy).
        extraction_count: number of commitments extracted directly
            (for full_restatement/conformed_copy).
        notes: human-readable notes about the processing.
    """

    genre: AmendmentPattern
    candidates: list[StructuredMutation] = field(default_factory=list)
    parser_instruction_count: int = 0
    extraction_count: int = 0
    notes: str = ""


# ---------------------------------------------------------------------------
# INCREMENTAL adapter
# ---------------------------------------------------------------------------


def process_incremental(
    source_text: str,
    current_state: dict[str, CommitmentState],
    citation_document: str | None = None,
) -> GenreAdapterResult:
    """Process an incremental amendment through the v2 resolver.

    Flow: parse_v04 → resolver v2 → candidates
    """
    if not source_text:
        return GenreAdapterResult(
            genre=AmendmentPattern.INCREMENTAL,
            notes="No source text",
        )

    # Parse
    parser_result = parse_v04(source_text)
    parser_rows = parser_result["instructions"]

    # Convert to AmendmentInstructions
    instructions: list[AmendmentInstruction] = []
    for i, row in enumerate(parser_rows):
        instructions.append(AmendmentInstruction(
            order=i + 1,
            instruction_type=InstructionType(row["instruction_type"]),
            target_section_ref=row.get("target_section_ref"),
            source_text=row.get("source_text"),
            old_value=row.get("old_value"),
            new_value=row.get("new_value"),
            provenance=InstructionProvenance.PARSER,
        ))

    # Resolve each instruction through the v2 resolver
    candidates: list[StructuredMutation] = []
    for ins in instructions:
        result, _ = resolve_instruction(
            ins, current_state, citation_document=citation_document,
        )
        candidates.extend(result.mutations)
        candidates.extend(result.unresolved)

    return GenreAdapterResult(
        genre=AmendmentPattern.INCREMENTAL,
        candidates=candidates,
        parser_instruction_count=len(instructions),
        notes=f"Parsed {len(instructions)} instructions, "
              f"{sum(1 for c in candidates if c.is_resolved)} mapped",
    )


# ---------------------------------------------------------------------------
# FULL_RESTATEMENT adapter
# ---------------------------------------------------------------------------


def process_full_restatement(
    source_text: str,
    current_state: dict[str, CommitmentState],
    citation_document: str | None = None,
    source_label: str = "full_restatement",
) -> GenreAdapterResult:
    """Process a full restatement by extracting commitments directly.

    Flow: extract commitments from restated text → diff vs current
    state → produce REPLACE_VALUE mutations for changed fields.

    The full restatement replaces the entire credit agreement, so we
    extract the new authoritative state directly and diff it against
    the current state to identify what changed.
    """
    if not source_text:
        return GenreAdapterResult(
            genre=AmendmentPattern.FULL_RESTATEMENT,
            notes="No source text",
        )

    # Extract commitments from the restated document
    extraction = extract_commitments(source_text, source_label)
    new_commitments = extraction.commitments

    # CONSERVATIVE POLICY: The extraction path does NOT produce any
    # mutations for existing commitments.  The v1 commitment extractor
    # is not accurate enough to reliably produce correct values, and
    # an incorrect automatic mutation is worse than an unresolved
    # instruction.
    #
    # For new commitments (not in current state), we produce ADD
    # mutations ONLY if the extracted threshold is a simple numeric
    # value (not a complex dict/list).  This is a conservative filter
    # to avoid adding commitments with wrong complex values.
    candidates: list[StructuredMutation] = []
    for key, new_commitment in new_commitments.items():
        if key not in current_state:
            # Only add if threshold is a simple numeric value
            threshold = getattr(new_commitment, "threshold", None)
            if isinstance(threshold, (int, float)) and threshold > 0:
                candidates.append(StructuredMutation(
                    commitment_id=key,
                    field="threshold",
                    operation=InstructionType.ADD,
                    new_value=threshold,
                    unit=getattr(new_commitment, "unit", None),
                    source_span=f"[full_restatement extraction: new {key}]",
                    provenance=InstructionProvenance.SEMANTIC_MAPPER,
                    confidence=0.85,
                    ambiguity_reason=None,
                    citation_document=citation_document,
                    citation_section="full_restatement",
                ))

    return GenreAdapterResult(
        genre=AmendmentPattern.FULL_RESTATEMENT,
        candidates=candidates,
        extraction_count=len(new_commitments),
        notes=f"Extracted {len(new_commitments)} commitments, "
              f"{len(candidates)} diff mutations",
    )


# ---------------------------------------------------------------------------
# CONFORMED_COPY adapter
# ---------------------------------------------------------------------------


def process_conformed_copy(
    source_text: str,
    current_state: dict[str, CommitmentState],
    citation_document: str | None = None,
) -> GenreAdapterResult:
    """Process a conformed copy by stripping redline markup and extracting.

    Flow: strip HTML redline markup (strikethrough, double-underline)
    → extract clean text → run the resolver on the clean text.

    The conformed copy contains the final state with redline markup.
    Strikethrough text is deleted, double-underlined text is added.
    We strip the markup to get the clean final text, then extract
    commitments from it (similar to full_restatement).
    """
    if not source_text:
        return GenreAdapterResult(
            genre=AmendmentPattern.CONFORMED_COPY,
            notes="No source text",
        )

    # Strip redline markup from text
    clean_text = _strip_redline_markup(source_text)

    if not clean_text or len(clean_text) < 100:
        # Not enough text after stripping — fall back to full_restatement
        # on the CLEANED text, not the original markup text.  Passing the
        # original (with HTML tags) would cause the extractor to parse
        # markup as commitment text.
        return process_full_restatement(
            clean_text or source_text, current_state, citation_document,
            source_label="conformed_copy",
        )

    # Extract commitments from the clean text
    extraction = extract_commitments(clean_text, "conformed_copy")
    new_commitments = extraction.commitments

    # CONSERVATIVE POLICY: same as full_restatement — only produce ADD
    # mutations for new commitments with simple numeric thresholds.
    candidates: list[StructuredMutation] = []
    for key, new_commitment in new_commitments.items():
        if key not in current_state:
            threshold = getattr(new_commitment, "threshold", None)
            if isinstance(threshold, (int, float)) and threshold > 0:
                candidates.append(StructuredMutation(
                    commitment_id=key,
                    field="threshold",
                    operation=InstructionType.ADD,
                    new_value=threshold,
                    unit=getattr(new_commitment, "unit", None),
                    source_span=f"[conformed_copy extraction: new {key}]",
                    provenance=InstructionProvenance.SEMANTIC_MAPPER,
                    confidence=0.80,
                    ambiguity_reason=None,
                    citation_document=citation_document,
                    citation_section="conformed_copy",
                ))

    return GenreAdapterResult(
        genre=AmendmentPattern.CONFORMED_COPY,
        candidates=candidates,
        extraction_count=len(new_commitments),
        notes=f"Stripped redline, extracted {len(new_commitments)} commitments, "
              f"{len(candidates)} diff mutations",
    )


def _strip_redline_markup(text: str) -> str:
    """Strip HTML redline markup from text.

    Removes strikethrough (deleted text) and keeps double-underlined
    (added text).  Also removes HTML tags that carry redline markup.
    """
    # Remove strikethrough text (content within <s> tags or with
    # text-decoration: line-through)
    text = re.sub(r"<s>.*?</s>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]*text-decoration:\s*line-through[^>]*>.*?</[^>]*>', "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove double-underline markup but keep the text
    text = re.sub(r"<u[^>]*>(.*?)</u>", r"\1", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]*text-decoration:\s*double.underline[^>]*>(.*?)</[^>]*>', r"\1", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------------------------------------------------------
# UNKNOWN adapter
# ---------------------------------------------------------------------------


def process_unknown(
    source_text: str,
    current_state: dict[str, CommitmentState],
    citation_document: str | None = None,
) -> GenreAdapterResult:
    """Process an unknown-genre amendment.

    Strategy: try the incremental path first.  If the parser finds
    no instructions, fall back to full_restatement extraction.
    """
    if not source_text:
        return GenreAdapterResult(
            genre=AmendmentPattern.UNKNOWN,
            notes="No source text",
        )

    # Try incremental first
    incremental_result = process_incremental(
        source_text, current_state, citation_document,
    )

    if incremental_result.parser_instruction_count > 0:
        # Parser found instructions — use the incremental result
        return GenreAdapterResult(
            genre=AmendmentPattern.UNKNOWN,
            candidates=incremental_result.candidates,
            parser_instruction_count=incremental_result.parser_instruction_count,
            notes=f"Unknown genre → tried incremental: {incremental_result.notes}",
        )

    # No parser instructions — try full_restatement extraction
    restatement_result = process_full_restatement(
        source_text, current_state, citation_document,
        source_label="unknown_genre_fallback",
    )

    return GenreAdapterResult(
        genre=AmendmentPattern.UNKNOWN,
        candidates=restatement_result.candidates,
        extraction_count=restatement_result.extraction_count,
        notes=f"Unknown genre → incremental found 0 instructions, "
              f"fell back to extraction: {restatement_result.notes}",
    )


# ---------------------------------------------------------------------------
# Genre-aware processor (dispatches to the correct adapter)
# ---------------------------------------------------------------------------


def process_amendment_by_genre(
    source_text: str,
    current_state: dict[str, CommitmentState],
    citation_document: str | None = None,
    genre_override: AmendmentPattern | None = None,
) -> GenreAdapterResult:
    """Process an amendment using the genre-appropriate adapter.

    Args:
        source_text: the amendment source text.
        current_state: the current authoritative commitment state.
        citation_document: source document name for citation.
        genre_override: if provided, use this genre instead of
            classifying.  Useful when the genre was already classified
            by the chain builder.

    Returns:
        GenreAdapterResult with candidates and metadata.
    """
    # Classify genre (or use override)
    if genre_override is not None:
        genre = genre_override
    else:
        genre = classify_amendment(source_text).pattern

    # Dispatch to the appropriate adapter
    if genre == AmendmentPattern.INCREMENTAL:
        return process_incremental(source_text, current_state, citation_document)
    elif genre == AmendmentPattern.FULL_RESTATEMENT:
        return process_full_restatement(source_text, current_state, citation_document)
    elif genre == AmendmentPattern.CONFORMED_COPY:
        return process_conformed_copy(source_text, current_state, citation_document)
    else:
        return process_unknown(source_text, current_state, citation_document)


# ---------------------------------------------------------------------------
# Genre distribution analysis (for the "improve genre classification" goal)
# ---------------------------------------------------------------------------


def analyze_genre_distribution(
    chains_data: list[tuple[str, list[dict]]],
) -> dict[str, Any]:
    """Analyze the genre distribution across a set of chains.

    Args:
        chains_data: list of (chain_id, documents) tuples.

    Returns:
        dict with genre distribution statistics.
    """
    genre_counts: dict[str, int] = {}
    total_amendments = 0

    for chain_id, documents in chains_data:
        for doc in documents:
            if not doc["role"].startswith("A"):
                continue
            total_amendments += 1
            try:
                text = Path(doc["text_path"]).read_text(
                    encoding="utf-8", errors="ignore",
                )
                genre = classify_amendment(text).pattern.value
            except Exception:  # noqa: BLE001
                genre = "unknown"
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

    unknown_rate = genre_counts.get("unknown", 0) / total_amendments if total_amendments else 0

    return {
        "total_amendments": total_amendments,
        "genre_counts": genre_counts,
        "unknown_rate": round(unknown_rate, 4),
    }
