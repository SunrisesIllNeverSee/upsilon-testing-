"""MOSES Semantic Safety Layer (Step 23S).

Implements the conservation-first safety baseline that blocks unsupported
semantic transformations before they can execute or become authoritative.

This module sits between the semantic resolver and the executor.  It
validates that each candidate mutation has affirmative target evidence,
a value compatible with the identified commitment, and a section reference
that corroborates (or at least does not contradict) the target identity.

Invariants enforced (Step 23S safety baseline):

  I1  Target-vs-reference separation
      A mention of a commitment is not sufficient evidence that the
      amendment transforms that commitment.  The engine requires
      affirmative target evidence beyond mere alias presence.

  I2  Value-extraction compatibility
      The extracted value must come from a semantic context compatible
      with the identified commitment's field type.  A percentage
      extracted from a SOFR-rate paragraph is not a valid leverage-ratio
      threshold.

  I3  Cross-type evidence
      If the source text contains operative language for a different
      commitment family (e.g., a ratio threshold pattern when the
      resolved target is a facility), the target identity is ambiguous.

  I4  Section-alias consistency
      When the section reference maps to a known commitment class, it
      must agree with the alias-resolved class.  A contradiction means
      the alias matched in a reference context, not an operative context.

  I5  Section corroboration for structural amendments
      For ADD operations that modify list fields (exceptions, party),
      the section reference must corroborate the target.  An exception
      being added "to" a facility must come from a facility section,
      not from an unrelated article.

  I6  Old-value consistency (amendment-evidence-only)
      When the amendment text independently declares an old value, that
      value must match the authoritative predecessor state.  Old values
      are never fabricated from predecessor state to satisfy the guard.

  I7  Minimal semantic proof
      Every executed mutation must carry a COMPLETE and VALID semantic
      proof.  An INDETERMINATE or INVALID proof routes to UNRESOLVED,
      blocking execution and authoritative promotion.

Design constraints (from Step 23S prompt):
  - No lexical rejection heuristics (e.g., debt-incurrence word lists).
  - No hardcoded diagnostic IDs or Step 23R labels in runtime logic.
  - No tautological old-value checks (predecessor value used as both
    expected and actual).
  - No predecessor state as proof of target identity.
  - No coverage expansion or multi-field decomposition.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from commitment_registry import (
    FACILITY_CLASSES,
    resolve_commitment_from_section,
)
from models import CommitmentState, InstructionType


# ---------------------------------------------------------------------------
# Local value-extraction helpers (kept local to avoid circular imports
# with semantic_resolver_v2, which imports this module).
# ---------------------------------------------------------------------------


def _extract_ratio_threshold(source_text: str) -> float | None:
    """Extract a ratio threshold from covenant text."""
    patterns = [
        r"(?:not\s+to\s+exceed|not\s+greater\s+than|shall\s+not\s+exceed|"
        r"shall\s+not\s+be\s+greater\s+than|shall\s+not\s+exceed|"
        r"maximum\s+(?:ratio\s+of\s+)?|not\s+to\s+be\s+greater\s+than|"
        r"not\s+exceed|not\s+greater\s+than)"
        r"\s+([\d.]+)\s*(?:to\s+|[:]\s*)1\.00",
        r"(?:ratio|level)\s+(?:of\s+)?([\d.]+)\s*(?:to\s+|[:]\s*)1\.00",
        r"not\s+to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
    ]
    for pat in patterns:
        m = re.search(pat, source_text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _extract_dollar_amount_with_scale(source_text: str) -> int | None:
    """Extract a dollar amount with million/billion scaling."""
    m = re.search(
        r"\$\s*([\d.]+)\s*(million|billion)",
        source_text,
        re.IGNORECASE,
    )
    if m:
        amount = float(m.group(1))
        scale = m.group(2).lower()
        if scale == "million":
            return int(amount * 1_000_000)
        elif scale == "billion":
            return int(amount * 1_000_000_000)
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", source_text)
    if m:
        return int(m.group(1).replace(",", "").split(".")[0])
    return None


def _extract_percentage(source_text: str) -> float | None:
    """Extract a percentage value from text."""
    amend_pattern = re.compile(
        r"(?:amended\s+to|to\s+mean|set\s+at|shall\s+be|to\s+be)"
        r"\s*"
        r"(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )
    m = amend_pattern.search(source_text)
    if m:
        return float(m.group(1))
    all_pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", source_text)
    if len(all_pcts) == 1:
        return float(all_pcts[0])
    return None


def _extract_step_down_schedule(source_text: str) -> dict | None:
    """Extract a leverage ratio step-down schedule."""
    step_pattern = re.compile(
        r"\([ivx]+\)\s+ending\s+on\s+"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        r"\s+to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
        re.IGNORECASE,
    )
    steady_pattern = re.compile(
        r"for\s+any\s+quarter\s+ending\s+thereafter,?\s+to\s+exceed\s+([\d.]+)\s+to\s+1\.00",
        re.IGNORECASE,
    )
    schedule = []
    for m in step_pattern.finditer(source_text):
        threshold = float(m.group(2))
        schedule.append({"period_end": m.group(1), "threshold": threshold})
    steady_match = steady_pattern.search(source_text)
    steady_state = float(steady_match.group(1)) if steady_match else None
    if not schedule and steady_state is None:
        return None
    return {
        "step_down_schedule": schedule,
        "steady_state_threshold": steady_state,
    }


# ---------------------------------------------------------------------------
# Covenant classes that can have dollar-amount thresholds (not just ratios).
# These covenants legitimately accept both ratio and dollar values, so the
# value-extraction compatibility check must allow both.
# ---------------------------------------------------------------------------

DOLLAR_THRESHOLD_COVENANTS = {
    "financial_covenant.tangible_net_worth",
    "financial_covenant.fixed_charge_coverage",
}

# Banking covenants whose thresholds are expressed as percentages.
PERCENT_THRESHOLD_COVENANTS = {
    "financial_covenant.tier_1_leverage_ratio",
    "financial_covenant.risk_based_capital_ratio",
    "financial_covenant.texas_ratio",
    "financial_covenant.return_on_average_assets",
}

# Ratio covenants whose thresholds are expressed as ratios (X.XX to 1.00).
# Excludes DOLLAR_THRESHOLD_COVENANTS and PERCENT_THRESHOLD_COVENANTS.
RATIO_THRESHOLD_COVENANTS = {
    "financial_covenant.leverage_ratio",
    "financial_covenant.debt_service_coverage",
    "financial_covenant.interest_coverage",
    "financial_covenant.current_ratio",
}


# ---------------------------------------------------------------------------
# Proof record
# ---------------------------------------------------------------------------


class TargetEvidenceLevel(str, Enum):
    """Strength of target-identity evidence."""
    SUFFICIENT = "SUFFICIENT"
    CORROBORATED = "CORROBORATED"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class ProofCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class ProofValidity(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class SemanticProof:
    """Minimal semantic proof record for a candidate mutation.

    A proof is COMPLETE when all required checks have been evaluated.
    A proof is VALID when every evaluated check passes (or is
    NOT_APPLICABLE).  An INVALID proof blocks execution.  An
    INDETERMINATE proof routes to UNRESOLVED.
    """
    # Target identity
    target_evidence_level: TargetEvidenceLevel = TargetEvidenceLevel.INSUFFICIENT
    target_evidence_reason: str = ""

    # Individual checks
    value_extraction_compatible: CheckResult = CheckResult.NOT_APPLICABLE
    cross_type_evidence: CheckResult = CheckResult.NOT_APPLICABLE
    section_alias_consistent: CheckResult = CheckResult.NOT_APPLICABLE
    section_corroboration: CheckResult = CheckResult.NOT_APPLICABLE
    old_value_check: CheckResult = CheckResult.NOT_APPLICABLE

    # Aggregate
    proof_completeness: ProofCompleteness = ProofCompleteness.INCOMPLETE
    proof_validity: ProofValidity = ProofValidity.INDETERMINATE

    @property
    def is_valid(self) -> bool:
        return self.proof_validity == ProofValidity.VALID

    @property
    def is_executable(self) -> bool:
        """A candidate is executable only when the proof is COMPLETE
        and VALID."""
        return (
            self.proof_completeness == ProofCompleteness.COMPLETE
            and self.proof_validity == ProofValidity.VALID
        )


# ---------------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------------


def _is_facility(canonical_id: str) -> bool:
    return canonical_id in FACILITY_CLASSES


def _is_ratio_covenant(canonical_id: str) -> bool:
    return canonical_id in RATIO_THRESHOLD_COVENANTS


def _is_percent_covenant(canonical_id: str) -> bool:
    return canonical_id in PERCENT_THRESHOLD_COVENANTS


def _is_dollar_covenant(canonical_id: str) -> bool:
    return canonical_id in DOLLAR_THRESHOLD_COVENANTS


def _text_contains_ratio_pattern(text: str) -> bool:
    """Check whether the source text contains a ratio threshold pattern
    (e.g., '4.00 to 1.00' or '3.50:1.00')."""
    return bool(re.search(r"[\d.]+\s*(?:to\s+|:\s*)1\.00", text, re.IGNORECASE))


def _text_contains_dollar_pattern(text: str) -> bool:
    """Check whether the source text contains a dollar amount pattern."""
    return bool(re.search(r"\$\s*[\d,]+", text))


def _text_contains_percentage_pattern(text: str) -> bool:
    """Check whether the source text contains a percentage pattern."""
    return bool(re.search(r"\d+(?:\.\d+)?\s*%", text))


def check_value_extraction_compatibility(
    canonical_id: str,
    field_name: str,
    new_value: Any,
    source_text: str,
) -> CheckResult:
    """I2: Check whether the extracted value is compatible with the
    identified commitment's field type.

    For ratio covenants (leverage_ratio, interest_coverage, etc.), the
    value must be extractable as a ratio from the source text.  If the
    text does not contain a ratio pattern, the value was likely extracted
    from an incompatible context (e.g., a SOFR rate percentage misread
    as a leverage threshold).

    For facilities, the value must be extractable as a dollar amount.

    For banking covenants, the value must be extractable as a percentage.

    For dollar-threshold covenants (tangible_net_worth,
    fixed_charge_coverage), both ratio and dollar extractions are
    accepted.

    This check is NOT_APPLICABLE for non-threshold fields (exceptions,
 party, deadline, rate) or when the new_value is a string (exception text).
    """
    if field_name not in ("threshold",):
        return CheckResult.NOT_APPLICABLE

    if new_value is None:
        return CheckResult.NOT_APPLICABLE

    # String values (e.g., exception text) are not numeric thresholds.
    if isinstance(new_value, str):
        return CheckResult.NOT_APPLICABLE

    # Facilities: value must be a dollar amount.
    if _is_facility(canonical_id):
        if _extract_dollar_amount_with_scale(source_text) is not None:
            return CheckResult.PASS
        return CheckResult.FAIL

    # Dollar-threshold covenants: accept ratio or dollar.
    if _is_dollar_covenant(canonical_id):
        if _extract_ratio_threshold(source_text) is not None:
            return CheckResult.PASS
        if _extract_dollar_amount_with_scale(source_text) is not None:
            return CheckResult.PASS
        return CheckResult.FAIL

    # Banking covenants: value must be a percentage.
    if _is_percent_covenant(canonical_id):
        if _extract_percentage(source_text) is not None:
            return CheckResult.PASS
        return CheckResult.FAIL

    # Ratio covenants: value must be a ratio.
    if _is_ratio_covenant(canonical_id):
        # Step-down schedules also produce ratio thresholds.
        schedule = _extract_step_down_schedule(source_text)
        if schedule is not None:
            # A step-down schedule is a multi-component transformation
            # (multiple thresholds with different effective dates).
            # Extracting a single scalar (e.g., steady_state_threshold)
            # from a schedule is an incomplete semantic representation
            # of the actual transformation.  The safe behavior under
            # the MOSES conservation-first contract is to NOT guess
            # which scalar component represents the transformation.
            # Route to UNRESOLVED for manual review.
            if not isinstance(new_value, dict):
                return CheckResult.FAIL
            return CheckResult.PASS
        if _extract_ratio_threshold(source_text) is not None:
            return CheckResult.PASS
        return CheckResult.FAIL

    # Unknown class — cannot validate.
    return CheckResult.NOT_APPLICABLE


def check_cross_type_evidence(
    canonical_id: str,
    field_name: str,
    source_text: str,
) -> CheckResult:
    """I3: Check whether the source text contains operative evidence for
    a different commitment family than the resolved target.

    If the resolved target is a facility but the text contains a ratio
    threshold pattern (X.XX to 1.00), the text is about a covenant, not
    a facility.  The target identity is ambiguous.

    Conversely, if the resolved target is a ratio covenant but the text
    contains only dollar amounts (no ratio pattern), the value may come
    from a facility context.  This is handled by I2 (value-extraction
    compatibility), so we only check the facility-target-with-ratio-evidence
    direction here.
    """
    if field_name not in ("threshold",):
        return CheckResult.NOT_APPLICABLE

    if _is_facility(canonical_id):
        if _text_contains_ratio_pattern(source_text):
            return CheckResult.FAIL
        return CheckResult.PASS

    return CheckResult.NOT_APPLICABLE


def check_section_alias_consistency(
    canonical_id: str,
    section_ref: str | None,
) -> CheckResult:
    """I4: Check whether the section reference maps to the same class
    as the alias-resolved target.

    If the section reference maps to a DIFFERENT class, the alias likely
    matched in a reference context, not an operative context.  The target
    identity is contradicted.

    If the section reference does not map to any class, the result is
    NOT_APPLICABLE (neutral — no corroboration, but no contradiction).
    """
    if not section_ref:
        return CheckResult.NOT_APPLICABLE

    section_class = resolve_commitment_from_section(section_ref)
    if section_class is None:
        return CheckResult.NOT_APPLICABLE

    if section_class == canonical_id:
        return CheckResult.PASS

    # Section maps to a different class — contradiction.
    return CheckResult.FAIL


def check_section_corroboration(
    canonical_id: str,
    section_ref: str | None,
    operation: InstructionType,
    field_name: str,
) -> CheckResult:
    """I5: For structural amendments (ADD on list fields), require the
    section reference to corroborate the target.

    An exception being added "to" a facility must come from a facility
    section, not from an unrelated article.  If the section reference
    does not map to the resolved class, the target evidence is
    insufficient for structural amendments.

    This check is NOT_APPLICABLE for non-ADD operations or non-list
    fields.
    """
    if operation != InstructionType.ADD:
        return CheckResult.NOT_APPLICABLE

    if field_name not in ("exceptions", "party"):
        return CheckResult.NOT_APPLICABLE

    if not section_ref:
        return CheckResult.FAIL

    section_class = resolve_commitment_from_section(section_ref)
    if section_class is None:
        # Section doesn't map to any known class — no corroboration.
        return CheckResult.FAIL

    if section_class == canonical_id:
        return CheckResult.PASS

    return CheckResult.FAIL


def check_old_value_consistency(
    old_value: Any,
    current_commitment: CommitmentState | None,
    field_name: str,
) -> CheckResult:
    """I6: Check old-value consistency when the amendment evidence
    independently declares an old value.

    If the amendment text states an old value, that value must match
    the authoritative predecessor state.  If no old value is declared,
    the check is NOT_APPLICABLE — we do NOT fabricate an old value from
    predecessor state.

    This is NOT a tautological check: the old value comes from amendment
    evidence, not from the predecessor state.  The predecessor state is
    only used as the comparison target, not as the source of the expected
    value.
    """
    if old_value is None:
        return CheckResult.NOT_APPLICABLE

    if current_commitment is None:
        return CheckResult.NOT_APPLICABLE

    if field_name in ("exceptions", "party"):
        return CheckResult.NOT_APPLICABLE

    current_val = getattr(current_commitment, field_name, None)
    if current_val is None:
        return CheckResult.NOT_APPLICABLE

    if current_val == old_value:
        return CheckResult.PASS

    return CheckResult.FAIL


def assess_target_evidence(
    canonical_id: str,
    field_name: str,
    new_value: Any,
    source_text: str,
    section_ref: str | None,
    operation: InstructionType,
    confidence: float,
) -> tuple[TargetEvidenceLevel, str]:
    """Assess the overall target-identity evidence level.

    Returns (evidence_level, reason).
    """
    # If the resolver matched via section-only (confidence <= 0.60),
    # the target evidence is weak unless the section corroborates.
    if confidence <= 0.60:
        section_class = resolve_commitment_from_section(section_ref) if section_ref else None
        if section_class == canonical_id:
            return TargetEvidenceLevel.CORROBORATED, "section-only match with section corroboration"
        return TargetEvidenceLevel.WEAK, "section-only match without corroboration"

    # Alias match (confidence >= 0.95).
    # Check for contradicting evidence.
    reasons: list[str] = []

    # Section contradiction
    section_check = check_section_alias_consistency(canonical_id, section_ref)
    if section_check == CheckResult.FAIL:
        reasons.append("section contradicts alias")

    # Cross-type evidence
    cross_check = check_cross_type_evidence(canonical_id, field_name, source_text)
    if cross_check == CheckResult.FAIL:
        reasons.append("text contains cross-type evidence")

    # Value extraction compatibility
    value_check = check_value_extraction_compatibility(
        canonical_id, field_name, new_value, source_text,
    )
    if value_check == CheckResult.FAIL:
        reasons.append("value extraction incompatible with target field")

    # Section corroboration for structural amendments
    corroboration_check = check_section_corroboration(
        canonical_id, section_ref, operation, field_name,
    )
    if corroboration_check == CheckResult.FAIL:
        reasons.append("section does not corroborate structural amendment target")

    if reasons:
        return TargetEvidenceLevel.INSUFFICIENT, "; ".join(reasons)

    return TargetEvidenceLevel.SUFFICIENT, "alias match with compatible evidence"


def _is_structurally_complete(
    canonical_id: str,
    field_name: str,
    new_value: Any,
    source_text: str,
) -> bool:
    """Determine whether the proof record can be structurally complete.

    Completeness is a structural property (per
    `SEMANTIC_AUTHORITY_GATE.md` §2): all required proof fields can be
    populated.  This is distinct from validity, which is the semantic
    question of whether the populated evidence supports the
    transformation.

    A proof is INCOMPLETE when a required structural component is
    missing and therefore the proof cannot be evaluated for validity
    at all.  The required structural components for Step 23S are:

      - ``canonical_id`` — the target commitment must be identified
      - ``field_name`` — the affected field must be identified
      - ``new_value`` — a successor value must be present (a
        transformation with no successor value is not a transformation)
      - ``source_text`` — amendment evidence must be present

    When any of these is missing, the proof is INCOMPLETE regardless
    of how the individual checks would evaluate.  An INCOMPLETE proof
    is not the same as an INVALID proof: INVALID means the evidence
    contradicts the transformation; INCOMPLETE means there is not
    enough structure to even ask.
    """
    if not canonical_id:
        return False
    if not field_name:
        return False
    if new_value is None:
        return False
    if not source_text:
        return False
    return True


def build_semantic_proof(
    canonical_id: str,
    field_name: str,
    operation: InstructionType,
    old_value: Any,
    new_value: Any,
    source_text: str,
    section_ref: str | None,
    current_commitment: CommitmentState | None,
    confidence: float,
) -> SemanticProof:
    """Build a semantic proof record for a candidate mutation.

    Runs all safety checks and produces a proof with completeness and
    validity status.

    Completeness and validity are kept distinct (per
    `SEMANTIC_AUTHORITY_GATE.md` §2): a completely populated wrong
    proof is still wrong.  ``is_executable`` requires both
    ``COMPLETE`` and ``VALID``.
    """
    proof = SemanticProof()

    # --- Structural completeness ---

    # Evaluated first.  When required structural components are
    # missing, the proof is INCOMPLETE and validity is INDETERMINATE
    # (we cannot evaluate validity without the structure to ask the
    # question).  Individual checks are still recorded as
    # NOT_APPLICABLE so the proof record is self-describing.
    structurally_complete = _is_structurally_complete(
        canonical_id, field_name, new_value, source_text,
    )

    # --- Individual checks ---

    proof.value_extraction_compatible = check_value_extraction_compatibility(
        canonical_id, field_name, new_value, source_text,
    )

    proof.cross_type_evidence = check_cross_type_evidence(
        canonical_id, field_name, source_text,
    )

    proof.section_alias_consistent = check_section_alias_consistency(
        canonical_id, section_ref,
    )

    proof.section_corroboration = check_section_corroboration(
        canonical_id, section_ref, operation, field_name,
    )

    proof.old_value_check = check_old_value_consistency(
        old_value, current_commitment, field_name,
    )

    # --- Target evidence assessment ---

    evidence_level, evidence_reason = assess_target_evidence(
        canonical_id, field_name, new_value, source_text,
        section_ref, operation, confidence,
    )
    proof.target_evidence_level = evidence_level
    proof.target_evidence_reason = evidence_reason

    # --- Aggregate: completeness ---

    if structurally_complete:
        proof.proof_completeness = ProofCompleteness.COMPLETE
    else:
        proof.proof_completeness = ProofCompleteness.INCOMPLETE

    # --- Aggregate: validity ---

    # An INCOMPLETE proof cannot be evaluated for validity.
    if not structurally_complete:
        proof.proof_validity = ProofValidity.INDETERMINATE
        return proof

    # A proof is INVALID if any check FAILs.
    # A proof is INDETERMINATE if target evidence is WEAK.
    # A proof is VALID if all checks pass (or are NOT_APPLICABLE) and
    # target evidence is SUFFICIENT or CORROBORATED.
    any_fail = (
        proof.value_extraction_compatible == CheckResult.FAIL
        or proof.cross_type_evidence == CheckResult.FAIL
        or proof.section_alias_consistent == CheckResult.FAIL
        or proof.section_corroboration == CheckResult.FAIL
        or proof.old_value_check == CheckResult.FAIL
    )

    if any_fail:
        proof.proof_validity = ProofValidity.INVALID
    elif evidence_level in (TargetEvidenceLevel.SUFFICIENT, TargetEvidenceLevel.CORROBORATED):
        proof.proof_validity = ProofValidity.VALID
    else:
        proof.proof_validity = ProofValidity.INDETERMINATE

    return proof


def validate_safety(
    canonical_id: str,
    field_name: str,
    operation: InstructionType,
    old_value: Any,
    new_value: Any,
    source_text: str,
    section_ref: str | None,
    current_commitment: CommitmentState | None,
    confidence: float,
) -> tuple[SemanticProof, bool]:
    """Run all MOSES safety checks on a candidate mutation.

    Returns (proof, is_safe).  is_safe is True only when the proof is
    COMPLETE and VALID.  When is_safe is False, the candidate must be
    routed to UNRESOLVED.
    """
    proof = build_semantic_proof(
        canonical_id, field_name, operation, old_value, new_value,
        source_text, section_ref, current_commitment, confidence,
    )
    return proof, proof.is_executable
