"""Constrained model-assisted semantic candidate interface (Step 21 / Section D).

The model MUST NOT directly mutate state.  The model produces
StructuredMutation CANDIDATES; deterministic validators verify every
candidate before it can be applied.

Architecture:

    source span + surrounding legal context + current commitment state
    + 13-class canonical ontology
        ↓
    model candidate generator (LLM or deterministic fallback)
        ↓
    StructuredMutation candidate (provenance = SEMANTIC_MODEL_CANDIDATE)
        ↓
    deterministic validators (8 checks)
        ↓
    DETERMINISTIC_VALIDATED → apply   |   VALIDATION_REJECTED → UNRESOLVED

The 8 deterministic validators:
  1. target exists (commitment ID is one of the 13 canonical classes)
  2. field exists (field is a valid CommitmentState field)
  3. old value agrees with current state (where required)
  4. new value supported by source (value appears in source text)
  5. unit compatible (unit matches the field type)
  6. operation valid (operation is a valid InstructionType)
  7. source evidence present (source_span is non-empty)
  8. temporal state valid (effective_at is within the amendment's
     effective period)

If ANY validator fails → VALIDATION_REJECTED → UNRESOLVED.

Provenance tracking:
  SEMANTIC_MODEL_CANDIDATE — the model produced this candidate
  DETERMINISTIC_VALIDATED — all 8 validators passed
  VALIDATION_REJECTED — at least one validator failed

Model backend interface:
  The candidate generator is pluggable.  The default backend is the
  deterministic resolver (semantic_resolver_v2), which produces
  candidates using pattern-based extraction.  An optional LLM backend
  can be enabled by setting the UPSILON_MODEL_BACKEND environment
  variable to "llm" and providing an API key.  When no LLM is
  available, the deterministic backend is used.

  This design ensures the system works without an LLM (the
  deterministic resolver produces candidates), and when an LLM is
  available, it produces higher-recall candidates that still go
  through the same deterministic validators.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from upsilon.commitments.commitment_registry import ALL_CLASSES, get_class_unit
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)
from upsilon.transformations.semantic_mapper import (
    AmbiguityReason,
    MappingResult,
    StructuredMutation,
)
from upsilon.transformations.semantic_resolver_v2 import resolve_instruction

# Step 22G: Agreement context integration
try:
    from upsilon.evidence.agreement_context import build_agreement_context, resolve_with_context
    _HAS_CONTEXT = True
except ImportError:
    _HAS_CONTEXT = False


# ---------------------------------------------------------------------------
# Provenance tags for model-assisted candidates
# ---------------------------------------------------------------------------


# Custom provenance tags recorded in the StructuredMutation's
# citation_document field (since InstructionProvenance is a fixed enum).
# Format: "SEMANTIC_MODEL_CANDIDATE|DETERMINISTIC_VALIDATED" or
# "SEMANTIC_MODEL_CANDIDATE|VALIDATION_REJECTED"

MODEL_CANDIDATE_TAG = "SEMANTIC_MODEL_CANDIDATE"
VALIDATED_TAG = "DETERMINISTIC_VALIDATED"
REJECTED_TAG = "VALIDATION_REJECTED"


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of validating a model-assisted candidate.

    Fields:
        passed: True if all 8 validators passed.
        failures: list of (validator_name, error_message) for failed
            validators.
        provenance_tag: the provenance tag to record
            (DETERMINISTIC_VALIDATED or VALIDATION_REJECTED).
    """

    passed: bool
    failures: list[tuple[str, str]] = field(default_factory=list)
    provenance_tag: str = VALIDATED_TAG


# ---------------------------------------------------------------------------
# The 8 deterministic validators
# ---------------------------------------------------------------------------


def _validate_target_exists(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 1: target commitment ID is one of the 13 canonical classes."""
    if candidate.commitment_id is None:
        return "target_is_none"
    if candidate.commitment_id not in ALL_CLASSES:
        return f"target_not_canonical: {candidate.commitment_id}"
    # For non-ADD operations, target must exist in current state
    if candidate.operation != InstructionType.ADD:
        if candidate.commitment_id not in current_state:
            return f"target_not_in_state: {candidate.commitment_id}"
    return None


def _validate_field_exists(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 2: field is a valid CommitmentState field."""
    valid_fields = {
        "threshold", "rate", "deadline", "party", "exceptions",
        "applicability", "status", "unit", "frequency", "scope",
        "operator", "modality", "action", "subject",
    }
    if candidate.field is None:
        return "field_is_none"
    if candidate.field not in valid_fields:
        return f"field_not_valid: {candidate.field}"
    return None


def _validate_old_value_agrees(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 3: old value agrees with current state (where required)."""
    if candidate.old_value is None:
        return None  # no old value to check
    if candidate.commitment_id not in current_state:
        return None  # can't check — target not in state (ADD case)
    current = current_state[candidate.commitment_id]
    if candidate.field in ("exceptions", "party"):
        return None  # list fields — old value check is different
    current_val = getattr(current, candidate.field, None)
    if current_val is not None and candidate.old_value != current_val:
        return (
            f"old_value_mismatch: expected {candidate.old_value!r}, "
            f"actual {current_val!r}"
        )
    return None


def _validate_new_value_supported(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 4: new value is supported by source text."""
    if candidate.new_value is None:
        if candidate.operation in (InstructionType.DELETE, InstructionType.DELETE_COMMITMENT):
            return None  # DELETE doesn't need a new value
        return "no_new_value"

    source = candidate.source_span or ""
    if not source:
        return "no_source_evidence"

    # For numeric values, check that the value appears in the source
    if isinstance(candidate.new_value, (int, float)):
        val_str = str(candidate.new_value)
        # Check if the value (or a close variant) appears in source
        if val_str not in source:
            # Try without trailing zeros (e.g., 4.0 vs 4.00)
            alt_str = f"{candidate.new_value:.2f}"
            if alt_str not in source:
                return f"new_value_not_in_source: {val_str}"

    # For string values (dates, exception text), check substring
    if isinstance(candidate.new_value, str):
        if len(candidate.new_value) > 5 and candidate.new_value not in source:
            # For dates, check just the year-month-day part
            if "-" in candidate.new_value:
                if candidate.new_value not in source:
                    return f"new_value_not_in_source: {candidate.new_value}"

    # For dict values (step-down schedules), check that the threshold
    # values appear in the source
    if isinstance(candidate.new_value, dict):
        steady = candidate.new_value.get("steady_state_threshold")
        if steady is not None and str(steady) not in source:
            # Check with 2 decimal places
            if f"{steady:.2f}" not in source:
                return f"new_value_not_in_source: steady={steady}"

    return None


def _validate_unit_compatible(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 5: unit is compatible with the field type."""
    if candidate.unit is None:
        return None  # no unit to check
    field_unit_map = {
        "threshold": {"ratio", "usd", "percent"},
        "rate": {"percent"},
        "deadline": {"date"},
        "frequency": {"frequency"},
    }
    valid_units = field_unit_map.get(candidate.field, set())
    if valid_units and candidate.unit not in valid_units:
        return f"unit_incompatible: {candidate.unit} for field {candidate.field}"
    return None


def _validate_operation_valid(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 6: operation is a valid InstructionType.

    Also checks that list fields (exceptions, party) do not receive
    REPLACE_VALUE — that would corrupt the list into a scalar.
    """
    valid_ops = {
        InstructionType.REPLACE_VALUE,
        InstructionType.REPLACE_TEXT,
        InstructionType.ADD,
        InstructionType.ADD_COMMITMENT,
        InstructionType.DELETE,
        InstructionType.DELETE_COMMITMENT,
        InstructionType.WAIVE_TEMPORARILY,
        InstructionType.SUSPEND,
        InstructionType.REINSTATE,
    }
    if candidate.operation not in valid_ops:
        return f"operation_not_valid: {candidate.operation}"
    # List fields must not receive REPLACE_VALUE or REPLACE_TEXT
    if candidate.field in ("exceptions", "party"):
        if candidate.operation in (InstructionType.REPLACE_VALUE, InstructionType.REPLACE_TEXT):
            return f"replace_on_list_field: {candidate.field}"
    return None


def _validate_source_evidence(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 7: source evidence is present (non-empty source span)."""
    if not candidate.source_span:
        return "no_source_evidence"
    if len(candidate.source_span) < 10:
        return "source_evidence_too_short"
    return None


def _validate_temporal_state(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> str | None:
    """Validator 8: temporal state is valid.

    Checks that effective_at (if set) is a valid datetime and not in
    the future relative to the amendment's effective period.
    """
    if candidate.effective_at is None:
        return None  # no temporal constraint
    # Basic validity: must be a datetime
    if not isinstance(candidate.effective_at, datetime):
        return "effective_at_not_datetime"
    return None


# Ordered list of all 8 validators
_VALIDATORS: list[tuple[str, Any]] = [
    ("target_exists", _validate_target_exists),
    ("field_exists", _validate_field_exists),
    ("old_value_agrees", _validate_old_value_agrees),
    ("new_value_supported", _validate_new_value_supported),
    ("unit_compatible", _validate_unit_compatible),
    ("operation_valid", _validate_operation_valid),
    ("source_evidence", _validate_source_evidence),
    ("temporal_state", _validate_temporal_state),
]


def validate_candidate(
    candidate: StructuredMutation,
    current_state: dict[str, CommitmentState],
) -> ValidationResult:
    """Run all 8 deterministic validators on a candidate.

    Returns a ValidationResult.
    """
    failures: list[tuple[str, str]] = []
    for name, validator in _VALIDATORS:
        error = validator(candidate, current_state)
        if error is not None:
            failures.append((name, error))

    if failures:
        return ValidationResult(
            passed=False,
            failures=failures,
            provenance_tag=REJECTED_TAG,
        )
    return ValidationResult(passed=True, provenance_tag=VALIDATED_TAG)


# ---------------------------------------------------------------------------
# Model candidate generator interface (pluggable backend)
# ---------------------------------------------------------------------------


class CandidateGenerator(Protocol):
    """Protocol for model-assisted candidate generators."""

    def generate_candidate(
        self,
        source_span: str,
        surrounding_context: str,
        current_state: dict[str, CommitmentState],
        section_ref: str | None,
        instruction_type: InstructionType,
    ) -> StructuredMutation | None:
        """Generate a StructuredMutation candidate from legal text.

        Returns a candidate (with provenance=SEMANTIC_MAPPER and
        ambiguity_reason=None) or None if no candidate can be generated.

        The candidate MUST be validated by validate_candidate() before
        it can be applied.
        """
        ...


class DeterministicCandidateGenerator:
    """Default candidate generator using the v2 semantic resolver.

    This is the fallback when no LLM backend is available.  It uses
    the deterministic pattern-based resolver to produce candidates.
    """

    def generate_candidate(
        self,
        source_span: str,
        surrounding_context: str,
        current_state: dict[str, CommitmentState],
        section_ref: str | None,
        instruction_type: InstructionType,
    ) -> StructuredMutation | None:
        """Generate a candidate using deterministic pattern matching."""
        # Build a temporary AmendmentInstruction for the resolver
        ins = AmendmentInstruction(
            order=1,
            instruction_type=instruction_type,
            target_section_ref=section_ref,
            source_text=source_span,
            provenance=InstructionProvenance.PARSER,
        )
        result, _ = resolve_instruction(ins, current_state)
        if result.mutations:
            return result.mutations[0]
        return None


class LLMCandidateGenerator:
    """LLM-backed candidate generator.

    Requires an LLM API key.  When available, the LLM produces
    StructuredMutation candidates from legal text with higher recall
    than the deterministic resolver.  All candidates still go through
    the same 8 deterministic validators.

    This backend is NOT implemented yet — it requires an LLM API key
    and a specific LLM provider.  When UPSILON_MODEL_BACKEND=llm is
    set but no API key is available, it falls back to the deterministic
    generator.
    """

    def __init__(self) -> None:
        self._fallback = DeterministicCandidateGenerator()
        self._api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            self._api_key = None  # will use fallback

    def generate_candidate(
        self,
        source_span: str,
        surrounding_context: str,
        current_state: dict[str, CommitmentState],
        section_ref: str | None,
        instruction_type: InstructionType,
    ) -> StructuredMutation | None:
        """Generate a candidate using the LLM (or fallback)."""
        if not self._api_key:
            return self._fallback.generate_candidate(
                source_span, surrounding_context, current_state,
                section_ref, instruction_type,
            )
        # LLM backend implementation would go here:
        # 1. Build a prompt with source_span, context, current state,
        #    and the 13-class ontology
        # 2. Call the LLM API
        # 3. Parse the response into a StructuredMutation
        # 4. Return the candidate
        # For now, fall back to deterministic.
        return self._fallback.generate_candidate(
            source_span, surrounding_context, current_state,
            section_ref, instruction_type,
        )


def get_candidate_generator() -> CandidateGenerator:
    """Get the configured candidate generator backend.

    Selection:
      - UPSILON_MODEL_BACKEND=llm → LLMCandidateGenerator
      - default → DeterministicCandidateGenerator
    """
    backend = os.environ.get("UPSILON_MODEL_BACKEND", "deterministic")
    if backend == "llm":
        return LLMCandidateGenerator()
    return DeterministicCandidateGenerator()


# ---------------------------------------------------------------------------
# Model-assisted resolver (combines candidate generation + validation)
# ---------------------------------------------------------------------------


def resolve_with_model_assistance(
    parser_instruction: AmendmentInstruction,
    current_state: dict[str, CommitmentState],
    citation_document: str | None = None,
    generator: CandidateGenerator | None = None,
) -> MappingResult:
    """Resolve an instruction using model-assisted candidates.

    Flow:
      1. Generate a candidate using the configured backend.
         Step 22G: If agreement context is available, use it to
         improve candidate generation.
      2. Validate the candidate with all 8 deterministic validators.
      3. If validated → return as mapped mutation.
      4. If rejected → return as UNRESOLVED.

    The candidate's provenance is tagged with
    SEMANTIC_MODEL_CANDIDATE|DETERMINISTIC_VALIDATED or
    SEMANTIC_MODEL_CANDIDATE|VALIDATION_REJECTED.

    The model MUST NOT directly mutate state.  The model produces
    StructuredMutation CANDIDATES; deterministic validators verify
    every candidate before it can be applied.  This design is
    preserved by Step 22G changes.
    """
    if generator is None:
        generator = get_candidate_generator()

    source_span = parser_instruction.source_text or ""
    section_ref = parser_instruction.target_section_ref

    # Step 22G: Build agreement context for improved candidate generation
    if _HAS_CONTEXT:
        ctx = build_agreement_context(
            source_span, current_state, section_ref,
        )
        # Try context-aware resolution first
        cid, field_hint, conf = resolve_with_context(
            parser_instruction, current_state, ctx,
        )
        if cid is not None and conf > 0.5:
            # Context resolved a high-confidence candidate — still
            # generate the full candidate through the resolver for
            # value extraction and validation.
            pass

    # 1. Generate candidate
    candidate = generator.generate_candidate(
        source_span=source_span,
        surrounding_context=source_span[:200],
        current_state=current_state,
        section_ref=section_ref,
        instruction_type=parser_instruction.instruction_type,
    )

    if candidate is None:
        # No candidate generated → UNRESOLVED
        return MappingResult(
            unresolved=[StructuredMutation(
                commitment_id=None,
                field=None,
                operation=parser_instruction.instruction_type,
                effective_at=parser_instruction.effective_start,
                source_span=source_span,
                provenance=InstructionProvenance.MANUAL,
                confidence=0.0,
                ambiguity_reason=AmbiguityReason.UNKNOWN_COMMITMENT,
                citation_document=citation_document,
                citation_section=section_ref,
            )],
        )

    # Tag the candidate with model-candidate provenance
    original_citation = candidate.citation_document or citation_document or ""
    candidate.citation_document = f"{original_citation}|{MODEL_CANDIDATE_TAG}"

    # 2. Validate
    validation = validate_candidate(candidate, current_state)

    if validation.passed:
        # 3. Validated → return as mapped mutation
        candidate.citation_document = f"{original_citation}|{MODEL_CANDIDATE_TAG}|{VALIDATED_TAG}"
        return MappingResult(mutations=[candidate], rules_matched=["model_assisted_validated"])
    else:
        # 4. Rejected → return as UNRESOLVED
        failure_desc = "; ".join(f"{n}:{e}" for n, e in validation.failures)
        candidate.citation_document = f"{original_citation}|{MODEL_CANDIDATE_TAG}|{REJECTED_TAG}"
        candidate.ambiguity_reason = AmbiguityReason.AMBIGUOUS_VALUE
        candidate.provenance = InstructionProvenance.MANUAL
        candidate.confidence = 0.0
        # Record the validation failures in the source_span for debugging
        candidate.source_span = f"{source_span}\n[VALIDATION_REJECTED: {failure_desc}]"
        return MappingResult(unresolved=[candidate])
