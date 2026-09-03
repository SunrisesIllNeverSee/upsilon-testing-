"""Evidence extraction from amendment instructions (Layer A).

This module converts legacy ``AmendmentInstruction`` objects (parser
output) into ``AmendmentEvidence`` objects that the
``AuthorizedTransformationEngine`` (Layer B) consumes.

The key principle is **evidence/interpretation separation**: the
evidence extractor pulls raw signals from the amendment text and
parser output (section refs, instruction types, declared values,
source text) WITHOUT performing final semantic interpretation
(target identity resolution, field identification, operation
classification).  Those are the engine's job.

However, the existing resolver's lexical extraction (value extraction
via regex, field hints from alias patterns) is repurposed here as
**evidence signals** — they become hints that the engine may use,
not final determinations.

RESPONSIBILITY:
    Convert amendment instructions to evidence objects (Layer A)
TARGET DOMAIN:
    evidence
CURRENT MODULE:
    src/upsilon/evidence/evidence_extractor.py (new)
CURRENT OPERATING STATUS:
    Phase 2 — evidence extraction
WHY THIS MODULE MUST CHANGE:
    The production pipeline interleaves evidence extraction with
    semantic interpretation in semantic_resolver_v2.py.  Step 24
    requires evidence to be separated from interpretation so the
    AuthorizedTransformationEngine can be the controlling
    interpretation step.
TARGET OWNER AFTER CHANGE:
    evidence domain (this module)
MIGRATION / REMOVAL CONDITION:
    Remove when the parser produces AmendmentEvidence directly and
    no longer needs AmendmentInstruction conversion.
"""
from __future__ import annotations

import re
from typing import Any

from upsilon.models.legacy_models import (
    AmendmentInstruction,
    InstructionProvenance,
    InstructionType,
)
from upsilon.transformations.authorized_change import AmendmentEvidence


# ---------------------------------------------------------------------------
# Value provenance determination
# ---------------------------------------------------------------------------

# Automated extraction provenances — values come from the parser or
# semantic mapper, not from a human curator.  These are strong evidence.
_AUTOMATED_PROVENANCES: frozenset[InstructionProvenance] = frozenset({
    InstructionProvenance.PARSER,
    InstructionProvenance.SEMANTIC_MAPPER,
    InstructionProvenance.COMPOSITE_EXTRACTION,
})

# Human-curated provenances — values were provided by a human reading
# the amendment text.  These are evidence but require corroboration
# by the engine against predecessor state and source text.
_CURATED_PROVENANCES: frozenset[InstructionProvenance] = frozenset({
    InstructionProvenance.MANUAL,
    InstructionProvenance.MANUAL_FALLBACK,
})


def _determine_value_provenance(
    provenance: InstructionProvenance,
) -> str:
    """Determine the value provenance from the instruction's provenance.

    Returns one of:
    - ``PARSER_EXTRACTED``: values from automated parser/mapper extraction
    - ``CURATOR_PROVIDED``: values from human curation
    - ``UNKNOWN``: provenance could not be determined
    """
    if provenance in _AUTOMATED_PROVENANCES:
        return "PARSER_EXTRACTED"
    if provenance in _CURATED_PROVENANCES:
        return "CURATOR_PROVIDED"
    return "UNKNOWN"


def instruction_to_evidence(
    instruction: AmendmentInstruction,
    citation_document: str | None = None,
) -> AmendmentEvidence:
    """Convert a legacy AmendmentInstruction to AmendmentEvidence.

    This extracts the evidence signals from the instruction without
    performing final semantic interpretation.  The evidence carries:

    - source_text: the amendment text span
    - source_section_ref: the section reference (e.g., "Section 7.10(a)")
    - source_document: the citation document
    - source_authority: the amendment authority string
    - instruction_type: the parser's instruction type (REPLACE_VALUE, etc.)
    - target_field: the field hint (if explicitly set on the instruction)
    - new_value: the declared new value (if explicitly set)
    - declared_old_value: the declared old value (if explicitly set)
    - exception_text: exception text (for ADD/DELETE on exceptions)
    - alias_match: alias text from the source (weak signal)
    - text_match: text match from the source (weak signal)
    - canonical_key_hint: the target_key as a canonical key hint
    - value_provenance: PARSER_EXTRACTED or CURATOR_PROVIDED

    The engine will use these signals to establish target identity
    and determine the transformation.  The extractor does NOT resolve
    identity, determine the field, or classify the operation beyond
    what the parser already provided.

    Value provenance is determined from the instruction's
    ``provenance`` field:
    - PARSER / SEMANTIC_MAPPER / COMPOSITE_EXTRACTION → PARSER_EXTRACTED
    - MANUAL / MANUAL_FALLBACK → CURATOR_PROVIDED

    Args:
        instruction: the legacy AmendmentInstruction from the parser.
        citation_document: the citation document name (optional).

    Returns:
        An AmendmentEvidence object carrying the extracted signals.
    """
    source_text = instruction.source_text or ""
    section_ref = instruction.target_section_ref

    # The target_key from the parser/fixture is a canonical key hint,
    # not a final identity determination.  The engine will use the
    # agreement-local address map to establish identity.
    canonical_key_hint = instruction.target_key

    # Field hint: if the instruction explicitly sets a field, it's
    # evidence.  If not, the engine must determine the field.
    target_field = instruction.field

    # Values: if the instruction explicitly sets old/new values, they
    # are declared evidence.  If not, the engine must extract them.
    new_value = instruction.new_value
    declared_old_value = instruction.old_value

    # Exception text: for ADD/DELETE on exceptions
    exception_text: str | None = None
    if (
        target_field == "exceptions"
        and isinstance(new_value, str)
    ):
        exception_text = new_value

    # Alias match: extract from source text as a weak signal
    alias_match = _extract_alias_signal(source_text)

    # Text match: the source text itself is a text match signal
    text_match = source_text[:200] if source_text else None

    # Source authority: construct from citation document + section
    source_authority = ""
    if citation_document:
        source_authority = citation_document
        if section_ref:
            source_authority += f", {section_ref}"
    elif section_ref:
        source_authority = section_ref

    # Determine value provenance from the instruction's provenance field.
    # PARSER / SEMANTIC_MAPPER / COMPOSITE_EXTRACTION are automated
    # extraction paths — values are parser-extracted evidence.
    # MANUAL / MANUAL_FALLBACK are human-curated — values are
    # curator-provided evidence that the engine must corroborate.
    value_provenance = _determine_value_provenance(instruction.provenance)

    return AmendmentEvidence(
        source_text=source_text,
        source_section_ref=section_ref,
        source_document=citation_document or "",
        source_authority=source_authority,
        amendment_id="",
        effective_date=instruction.effective_start,
        instruction_type=instruction.instruction_type.value,
        target_field=target_field,
        new_value=new_value,
        declared_old_value=declared_old_value,
        exception_text=exception_text,
        alias_match=alias_match,
        text_match=text_match,
        canonical_key_hint=canonical_key_hint,
        value_provenance=value_provenance,
    )


def instructions_to_evidence(
    instructions: list[AmendmentInstruction],
    citation_document: str | None = None,
) -> list[AmendmentEvidence]:
    """Convert a list of AmendmentInstructions to AmendmentEvidence objects.

    Args:
        instructions: the legacy AmendmentInstructions from the parser.
        citation_document: the citation document name (optional).

    Returns:
        A list of AmendmentEvidence objects.
    """
    return [
        instruction_to_evidence(ins, citation_document=citation_document)
        for ins in instructions
    ]


# ---------------------------------------------------------------------------
# Weak signal extraction (evidence, not authority)
# ---------------------------------------------------------------------------

# Common commitment-related terms that appear in amendment text.
# These are WEAK signals — they supply evidence but cannot establish
# authoritative identity alone.
_ALIAS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bleverage\s+ratio\b", re.I), "leverage_ratio"),
    (re.compile(r"\btotal\s+funded\s+debt\s+to\s+EBITDA\b", re.I), "leverage_ratio"),
    (re.compile(r"\bcore\s+leverage\s+ratio\b", re.I), "leverage_ratio"),
    (re.compile(r"\bdebt\s+service\s+coverage\b", re.I), "debt_service_coverage"),
    (re.compile(r"\binterest\s+coverage\b", re.I), "interest_coverage"),
    (re.compile(r"\bcurrent\s+ratio\b", re.I), "current_ratio"),
    (re.compile(r"\bquick\s+ratio\b", re.I), "quick_ratio"),
    (re.compile(r"\btangible\s+net\s+worth\b", re.I), "tangible_net_worth"),
    (re.compile(r"\bfixed\s+charge\s+coverage\b", re.I), "fixed_charge_coverage"),
]


def _extract_alias_signal(source_text: str) -> str | None:
    """Extract an alias match from source text (weak signal).

    This is a WEAK signal only.  It cannot establish authoritative
    identity.  The engine must corroborate it with address-map or
    predecessor-state evidence.

    Args:
        source_text: the amendment source text.

    Returns:
        The matched alias string, or None.
    """
    if not source_text:
        return None
    for pattern, alias in _ALIAS_PATTERNS:
        if pattern.search(source_text):
            return alias
    return None
