"""Agreement context graph (Step 22D).

Provides a structured representation of agreement context for the
semantic resolver.  The resolver resolves against this context rather
than only isolated instruction text.

Context fields:
  - section_number → section heading
  - section → canonical commitment candidates
  - defined term → definition
  - commitment aliases
  - current commitment state keys
  - prior amendment references
  - target section
  - surrounding source text

Usage:
    from agreement_context import build_agreement_context, resolve_with_context
    ctx = build_agreement_context(source_text, current_state, section_ref)
    cid, field, conf = resolve_with_context(instruction, current_state, ctx)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from commitment_registry import (
    resolve_commitment_from_text,
    resolve_commitment_from_section,
)
from models import AmendmentInstruction, CommitmentState


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AgreementContext:
    """Structured agreement context for semantic resolution.

    Fields:
        section_headings: section_number → heading text.
        section_commitments: section_ref → list of canonical IDs.
        defined_terms: term → definition text.
        commitment_aliases: canonical_id → list of known aliases.
        current_state_keys: keys in the current commitment state.
        prior_amendments: list of prior amendment references.
        target_section: the section being amended (if known).
        surrounding_text: source text surrounding the instruction.
    """

    section_headings: dict[str, str] = field(default_factory=dict)
    section_commitments: dict[str, list[str]] = field(default_factory=dict)
    defined_terms: dict[str, str] = field(default_factory=dict)
    commitment_aliases: dict[str, list[str]] = field(default_factory=dict)
    current_state_keys: list[str] = field(default_factory=list)
    prior_amendments: list[str] = field(default_factory=list)
    target_section: str | None = None
    surrounding_text: str = ""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

# Section heading pattern: "Section X.XX Title" or "SECTION X.XX Title"
_SECTION_HEADING_RE = re.compile(
    r"(?:Section|SECTION)\s+(\d+\.\d+)\s*\.?\s+([A-Z][^\n]{3,80}?)\s*[\.\n]",
    re.IGNORECASE,
)

# Defined term pattern: '"Term" means' or '"Term" shall mean'
_DEFINED_TERM_RE = re.compile(
    r'["\u201c]([A-Z][A-Za-z\s]{2,60})["\u201d]\s*(?:shall\s+)?means?\s+(.{10,200}?)[\.;]',
    re.IGNORECASE,
)


def build_agreement_context(
    source_text: str,
    current_state: dict[str, CommitmentState],
    section_ref: str | None = None,
    prior_amendments: list[str] | None = None,
) -> AgreementContext:
    """Build an AgreementContext from source text and current state.

    Args:
        source_text: the amendment or agreement source text.
        current_state: the current authoritative commitment state.
        section_ref: the target section reference (if known).
        prior_amendments: list of prior amendment document references.

    Returns:
        AgreementContext populated with section headings, defined
        terms, and commitment candidates.
    """
    ctx = AgreementContext(
        current_state_keys=list(current_state.keys()),
        prior_amendments=prior_amendments or [],
        target_section=section_ref,
        surrounding_text=source_text[:500] if source_text else "",
    )

    # Extract section headings
    for m in _SECTION_HEADING_RE.finditer(source_text):
        section_num = m.group(1)
        heading = m.group(2).strip()
        ctx.section_headings[section_num] = heading

        # Resolve commitment candidates from the heading
        cid = resolve_commitment_from_section(f"Section {section_num}")
        if cid is not None:
            ctx.section_commitments.setdefault(section_num, []).append(cid)

        # Also try resolving from the heading text
        cid_from_text, _, _ = resolve_commitment_from_text(heading)
        if cid_from_text is not None:
            if cid_from_text not in ctx.section_commitments.get(section_num, []):
                ctx.section_commitments.setdefault(section_num, []).append(
                    cid_from_text,
                )

    # Extract defined terms
    for m in _DEFINED_TERM_RE.finditer(source_text):
        term = m.group(1).strip()
        definition = m.group(2).strip()
        ctx.defined_terms[term] = definition

    # Build commitment aliases from current state keys
    from commitment_registry import get_aliases_for_class
    for key in current_state:
        aliases = get_aliases_for_class(key)
        if aliases:
            ctx.commitment_aliases[key] = [
                a.pattern.pattern for a in aliases
            ]

    return ctx


# ---------------------------------------------------------------------------
# Context-aware resolution
# ---------------------------------------------------------------------------


def resolve_with_context(
    instruction: AmendmentInstruction,
    current_state: dict[str, CommitmentState],
    context: AgreementContext,
) -> tuple[str | None, str | None, float]:
    """Resolve a commitment ID using agreement context.

    Uses context signals in priority order:
      1. Alias pattern match in source text (highest confidence)
      2. Section → commitment mapping from context
      3. Defined term cross-reference
      4. Current state cross-reference

    Returns:
        (canonical_id, field_hint, confidence) or (None, None, 0.0).
    """
    source = instruction.source_text or ""
    section_ref = instruction.target_section_ref

    # 1. Alias pattern match (via registry)
    cid, field_hint, conf = resolve_commitment_from_text(
        source, section_ref, current_state,
    )
    if cid is not None:
        return cid, field_hint, conf

    # 2. Context section → commitment mapping
    if section_ref:
        # Extract section number from ref (e.g., "Section 7.10" → "7.10")
        sec_match = re.search(r"(\d+\.\d+)", section_ref)
        if sec_match:
            sec_num = sec_match.group(1)
            candidates = context.section_commitments.get(sec_num, [])
            for candidate_id in candidates:
                if candidate_id in current_state:
                    return candidate_id, "threshold", 0.65

    # 3. Defined term cross-reference
    # Check if the source text mentions any defined terms that map
    # to commitments in the current state.
    for term, definition in context.defined_terms.items():
        if term.lower() in source.lower():
            # Try to resolve a commitment from the definition text
            cid, field_hint, _ = resolve_commitment_from_text(
                definition, None, current_state,
            )
            if cid is not None and cid in current_state:
                return cid, field_hint, 0.60

    # 4. Context section heading → commitment (lower confidence)
    if section_ref:
        sec_match = re.search(r"(\d+\.\d+)", section_ref)
        if sec_match:
            sec_num = sec_match.group(1)
            heading = context.section_headings.get(sec_num, "")
            if heading:
                cid, field_hint, _ = resolve_commitment_from_text(
                    heading, None, current_state,
                )
                if cid is not None:
                    return cid, field_hint, 0.55

    return None, None, 0.0
