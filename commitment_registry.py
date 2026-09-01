"""Agreement-specific commitment registry (Step 21 / Section B).

A resolver from legal-document structure to the 13 canonical commitment
classes the frozen S0/GT extractors can emit.  The registry is the
single source of truth for mapping legal text (section references,
section headings, defined terms, clause text) to canonical commitment
IDs.

The 13 canonical classes (MUST stay in sync with
commitment_extractor._COVENANT_NAME_MAP and _FACILITY_PATTERNS):

  Facility commitments:
    facility.revolving_facility
    facility.term_loan
    facility.delayed_draw_term_loan

  Financial covenants:
    financial_covenant.leverage_ratio
    financial_covenant.debt_service_coverage
    financial_covenant.fixed_charge_coverage
    financial_covenant.interest_coverage
    financial_covenant.current_ratio
    financial_covenant.tangible_net_worth
    financial_covenant.tier_1_leverage_ratio
    financial_covenant.risk_based_capital_ratio
    financial_covenant.texas_ratio
    financial_covenant.return_on_average_assets

The registry provides:

  1. ALIASES: every known name/phrase that refers to each class
     (e.g., "Maximum Total Leverage Ratio", "Consolidated Leverage
     Ratio", "Leverage Ratio" → financial_covenant.leverage_ratio).

  2. SECTION_PATTERNS: common credit-agreement section references
     that house each class (e.g., Section 7.10 → leverage ratio,
     Section 6.10 → current ratio).

  3. resolve_commitment_from_text(): given source text + section ref +
     current authoritative state, return the best-matching canonical
     commitment ID or None.

  4. resolve_commitment_from_section(): given just a section ref,
     return the best-matching canonical commitment ID or None.

  5. resolve_commitment_from_state(): given a canonical ID and the
     current state, return the matching CommitmentState if one exists.

The resolver is deterministic.  It uses priority-ordered pattern
matching: specific patterns are checked before generic ones (e.g.,
"Tier 1 Leverage Ratio" before "Leverage Ratio") to avoid
misclassification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from models import CommitmentState


# ---------------------------------------------------------------------------
# Canonical commitment classes (the 13 the extractors emit)
# ---------------------------------------------------------------------------

FACILITY_CLASSES = [
    "facility.revolving_facility",
    "facility.term_loan",
    "facility.delayed_draw_term_loan",
]

COVENANT_CLASSES = [
    "financial_covenant.leverage_ratio",
    "financial_covenant.debt_service_coverage",
    "financial_covenant.fixed_charge_coverage",
    "financial_covenant.interest_coverage",
    "financial_covenant.current_ratio",
    "financial_covenant.tangible_net_worth",
    "financial_covenant.tier_1_leverage_ratio",
    "financial_covenant.risk_based_capital_ratio",
    "financial_covenant.texas_ratio",
    "financial_covenant.return_on_average_assets",
]

ALL_CLASSES = FACILITY_CLASSES + COVENANT_CLASSES


# ---------------------------------------------------------------------------
# Alias registry — every known name/phrase → canonical commitment ID
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitmentAlias:
    """One alias entry mapping a textual pattern to a canonical class.

    Fields:
        pattern: compiled regex pattern to search for in source text.
        canonical_id: the 13-class canonical commitment ID.
        priority: lower = checked first (more specific patterns first).
        field_hint: which CommitmentState field this alias typically
            modifies (e.g., "threshold", "amount", "deadline").  None
            if the alias doesn't imply a specific field.
    """

    pattern: re.Pattern
    canonical_id: str
    priority: int
    field_hint: str | None


# Build the alias list.  Priority ordering: specific patterns (lower
# number) are checked before generic ones.  This prevents "Leverage
# Ratio" from matching before "Tier 1 Leverage Ratio".
_ALIASES: list[CommitmentAlias] = [
    # --- Leverage ratio (many aliases, specific first) ---
    CommitmentAlias(
        re.compile(r"Total\s+Funded\s+Debt\s+to\s+EBITDA", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Core\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Total\s+Debt\s+to\s+EBITDA", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Debt\s+to\s+EBITDAX", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Ratio\s+of\s+Debt\s+to\s+EBITDAX", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Senior\s+Funded\s+Debt\s+to\s+EBITDA", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Consolidated\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Total\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Total\s+Leverage\b", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 11, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Maximum\s+Total\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 5, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Maximum\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 8, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Long\s+Term\s+Debt\s+to\s+Long\s+Term\s+Capitalization", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    # Generic "Leverage Ratio" — lowest priority, checked after all
    # specific leverage patterns.
    CommitmentAlias(
        re.compile(r"Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 50, "threshold",
    ),

    # --- Debt service coverage ---
    CommitmentAlias(
        re.compile(r"Debt\s+Service\s+Coverage", re.IGNORECASE),
        "financial_covenant.debt_service_coverage", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Debt\s+Service\s+Coverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.debt_service_coverage", 5, "threshold",
    ),

    # --- Fixed charge coverage ---
    CommitmentAlias(
        re.compile(r"Fixed\s+Charge\s+Coverage", re.IGNORECASE),
        "financial_covenant.fixed_charge_coverage", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Fixed\s+Charge\s+Coverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.fixed_charge_coverage", 5, "threshold",
    ),

    # --- Interest coverage ---
    CommitmentAlias(
        re.compile(r"Interest\s+Coverage", re.IGNORECASE),
        "financial_covenant.interest_coverage", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"EBIT\s+to\s+Interest\s+Ratio", re.IGNORECASE),
        "financial_covenant.interest_coverage", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Interest\s+Coverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.interest_coverage", 5, "threshold",
    ),

    # --- Current ratio ---
    CommitmentAlias(
        re.compile(r"Current\s+Ratio", re.IGNORECASE),
        "financial_covenant.current_ratio", 10, "threshold",
    ),

    # --- Tangible net worth ---
    CommitmentAlias(
        re.compile(r"Tangible\s+Net\s+Worth", re.IGNORECASE),
        "financial_covenant.tangible_net_worth", 10, "threshold",
    ),

    # --- Tier 1 leverage ratio (must be before generic leverage) ---
    CommitmentAlias(
        re.compile(r"Tier\s+1\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.tier_1_leverage_ratio", 5, "threshold",
    ),

    # --- Risk-based capital ratio ---
    CommitmentAlias(
        re.compile(r"Risk.Based\s+Capital\s+Ratio", re.IGNORECASE),
        "financial_covenant.risk_based_capital_ratio", 10, "threshold",
    ),

    # --- Texas ratio ---
    CommitmentAlias(
        re.compile(r"Texas\s+Ratio", re.IGNORECASE),
        "financial_covenant.texas_ratio", 10, "threshold",
    ),

    # --- Return on average assets ---
    CommitmentAlias(
        re.compile(r"Return\s+on\s+Average\s+Assets", re.IGNORECASE),
        "financial_covenant.return_on_average_assets", 10, "threshold",
    ),

    # --- Facility commitments ---
    CommitmentAlias(
        re.compile(r"Revolving\s+(?:Loan|Facility|Credit|Commitment)", re.IGNORECASE),
        "facility.revolving_facility", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Revolving\s+Facility", re.IGNORECASE),
        "facility.revolving_facility", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Term\s+Loan\b", re.IGNORECASE),
        "facility.term_loan", 20, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Term\s+Commitment", re.IGNORECASE),
        "facility.term_loan", 20, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Delayed\s+Draw\s+Term", re.IGNORECASE),
        "facility.delayed_draw_term_loan", 10, "threshold",
    ),

    # Step 22E: Evidence-derived aliases from the 50-chain corpus.
    # These were identified by scanning S0 documents for covenant
    # section headers that the v1 registry did not recognize.

    # --- Tangible Net Worth variants ---
    CommitmentAlias(
        re.compile(r"Minimum\s+Tangible\s+Net\s+Worth", re.IGNORECASE),
        "financial_covenant.tangible_net_worth", 5, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Minimum\s+Shareholders.?\s+Equity", re.IGNORECASE),
        "financial_covenant.tangible_net_worth", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Minimum\s+Stockholders.?\s+Equity", re.IGNORECASE),
        "financial_covenant.tangible_net_worth", 10, "threshold",
    ),

    # --- Leverage ratio variants ---
    CommitmentAlias(
        re.compile(r"Funded\s+Debt\s+to\s+EBITDA", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Debt\s+to\s+EBITDA\b", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 15, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Net\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 8, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"First\s+Lien\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 8, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Secured\s+Leverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.leverage_ratio", 8, "threshold",
    ),

    # --- Asset coverage (BDC pattern) ---
    CommitmentAlias(
        re.compile(r"Asset\s+Coverage\s+Ratio", re.IGNORECASE),
        "financial_covenant.debt_service_coverage", 10, "threshold",
    ),

    # --- Working capital / liquidity ---
    CommitmentAlias(
        re.compile(r"Minimum\s+Working\s+Capital", re.IGNORECASE),
        "financial_covenant.current_ratio", 10, "threshold",
    ),
    CommitmentAlias(
        re.compile(r"Minimum\s+Liquidity(?:\s+Ratio)?", re.IGNORECASE),
        "financial_covenant.interest_coverage", 10, "threshold",
    ),
]


# ---------------------------------------------------------------------------
# Section-to-commitment mapping (expanded from v1's 7-entry map)
# ---------------------------------------------------------------------------

# Maps section reference patterns to canonical commitment IDs.
# Ordered by specificity: more specific refs (e.g., "section 7.10(a)")
# are matched via prefix logic after exact matches fail.
_SECTION_MAP: list[tuple[re.Pattern, str]] = [
    # Financial covenants — common section numbers across credit agreements.
    # These are empirical from the 50-chain development corpus.
    (re.compile(r"section\s+7\.10", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    (re.compile(r"section\s+7\.11", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    (re.compile(r"section\s+6\.10", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    (re.compile(r"section\s+6\.11", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    (re.compile(r"section\s+5\.0?1", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    (re.compile(r"section\s+9\.1\b", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    (re.compile(r"section\s+10\.1\b", re.IGNORECASE), "financial_covenant.leverage_ratio"),
    # Fixed charge / interest coverage
    (re.compile(r"section\s+7\.12", re.IGNORECASE), "financial_covenant.fixed_charge_coverage"),
    (re.compile(r"section\s+6\.12", re.IGNORECASE), "financial_covenant.fixed_charge_coverage"),
    (re.compile(r"section\s+7\.13", re.IGNORECASE), "financial_covenant.interest_coverage"),
    (re.compile(r"section\s+6\.13", re.IGNORECASE), "financial_covenant.interest_coverage"),
    # Current ratio
    (re.compile(r"section\s+7\.14", re.IGNORECASE), "financial_covenant.current_ratio"),
    (re.compile(r"section\s+6\.14", re.IGNORECASE), "financial_covenant.current_ratio"),
    # Tangible net worth
    (re.compile(r"section\s+7\.15", re.IGNORECASE), "financial_covenant.tangible_net_worth"),
    (re.compile(r"section\s+6\.15", re.IGNORECASE), "financial_covenant.tangible_net_worth"),
    # Debt service coverage
    (re.compile(r"section\s+7\.16", re.IGNORECASE), "financial_covenant.debt_service_coverage"),
    (re.compile(r"section\s+6\.16", re.IGNORECASE), "financial_covenant.debt_service_coverage"),
    # Facilities — common sections
    (re.compile(r"section\s+2\.0?1\b", re.IGNORECASE), "facility.revolving_facility"),
    (re.compile(r"section\s+2\.0?2\b", re.IGNORECASE), "facility.term_loan"),
    (re.compile(r"section\s+2\.0?3\b", re.IGNORECASE), "facility.delayed_draw_term_loan"),
    # Indebtedness / general facility sections
    (re.compile(r"section\s+7\.0?1\b", re.IGNORECASE), "facility.revolving_facility"),
    (re.compile(r"section\s+7\.0?2\b", re.IGNORECASE), "facility.term_loan"),
    # Step 22E: Additional section patterns from the 50-chain corpus.
    # Individual covenant sections (HELD-004 pattern: sections 6.11-6.14).
    (re.compile(r"section\s+6\.0?1\b", re.IGNORECASE), "facility.revolving_facility"),
    (re.compile(r"section\s+6\.0?2\b", re.IGNORECASE), "facility.term_loan"),
    (re.compile(r"section\s+6\.0?3\b", re.IGNORECASE), "facility.delayed_draw_term_loan"),
]


# ---------------------------------------------------------------------------
# Resolver functions
# ---------------------------------------------------------------------------


def resolve_commitment_from_text(
    source_text: str,
    section_ref: str | None = None,
    current_state: dict[str, CommitmentState] | None = None,
) -> tuple[str | None, str | None, float]:
    """Resolve a canonical commitment ID from legal text.

    Uses three signals in priority order:
      1. Alias pattern match in source_text (highest confidence)
      2. Section reference mapping
      3. Current state cross-reference (if alias matches a class not
         in state, try the next-best alias)

    Args:
        source_text: the amendment instruction's source text.
        section_ref: the target section reference (e.g., "Section 7.10").
        current_state: the current authoritative commitment state,
            used to validate that a resolved commitment exists.

    Returns:
        (canonical_id, field_hint, confidence) or (None, None, 0.0).
        confidence is 0.95 for alias matches, 0.70 for section-only
        matches, 0.60 for section matches validated against state.
    """
    if not source_text:
        return _resolve_from_section_only(section_ref, current_state)

    # 1. Try alias patterns in priority order.
    sorted_aliases = sorted(_ALIASES, key=lambda a: a.priority)
    for alias in sorted_aliases:
        if alias.pattern.search(source_text):
            # Validate against current state if provided.
            if current_state is not None:
                if alias.canonical_id in current_state:
                    return alias.canonical_id, alias.field_hint, 0.95
                # Alias matched but commitment not in current state.
                # This could be a new commitment being added, or a
                # wrong match.  Keep looking for a better match that
                # IS in state, but remember this as a fallback.
                continue
            return alias.canonical_id, alias.field_hint, 0.95

    # 2. Fall back to section-only resolution.
    return _resolve_from_section_only(section_ref, current_state)


def _resolve_from_section_only(
    section_ref: str | None,
    current_state: dict[str, CommitmentState] | None,
) -> tuple[str | None, str | None, float]:
    """Resolve commitment ID from section reference only."""
    if not section_ref:
        return None, None, 0.0

    for pattern, cid in _SECTION_MAP:
        if pattern.search(section_ref):
            if current_state is not None:
                if cid in current_state:
                    return cid, "threshold", 0.60
                # Section matches but commitment not in state.
                continue
            return cid, "threshold", 0.70

    return None, None, 0.0


def resolve_commitment_from_section(
    section_ref: str | None,
) -> str | None:
    """Resolve a canonical commitment ID from a section reference only.

    Returns the canonical ID or None.
    """
    cid, _, _ = _resolve_from_section_only(section_ref, None)
    return cid


def resolve_commitment_from_state(
    canonical_id: str,
    current_state: dict[str, CommitmentState],
) -> CommitmentState | None:
    """Return the CommitmentState for a canonical ID, or None."""
    return current_state.get(canonical_id)


def get_all_aliases() -> list[CommitmentAlias]:
    """Return all registered aliases, sorted by priority."""
    return sorted(_ALIASES, key=lambda a: a.priority)


def get_aliases_for_class(canonical_id: str) -> list[CommitmentAlias]:
    """Return all aliases for a specific canonical class."""
    return [a for a in _ALIASES if a.canonical_id == canonical_id]


def is_known_class(canonical_id: str) -> bool:
    """Check if a canonical ID is one of the 13 known classes."""
    return canonical_id in ALL_CLASSES


def get_class_unit(canonical_id: str) -> str | None:
    """Return the unit for a canonical class, or None."""
    for alias in _ALIASES:
        if alias.canonical_id == canonical_id:
            if canonical_id.startswith("facility."):
                return "usd"
            if canonical_id in (
                "financial_covenant.tier_1_leverage_ratio",
                "financial_covenant.risk_based_capital_ratio",
                "financial_covenant.texas_ratio",
                "financial_covenant.return_on_average_assets",
            ):
                return "percent"
            return "ratio"
    return None
