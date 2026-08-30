from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class InstructionType(str, Enum):
    """How the legal document transformed (the operation, not the domain effect).

    Separated from DomainEffect: a single transformation (e.g., REPLACE_VALUE)
    can produce different domain effects (e.g., commitment_amount_change,
    covenant_threshold_change) depending on which field changed.

    The transformation vocabulary aligns with the v0.4 grammar:
        REPLACE_VALUE  — replace a specific field value
        REPLACE_TEXT   — replace text content (broader than REPLACE_VALUE)
        ADD            — add a new element (definition, clause, section)
        ADD_COMMITMENT — add a new commitment (specific case of ADD)
        DELETE         — delete an element
        DELETE_COMMITMENT — delete/remove a commitment (specific case of DELETE)
        RESTATE_SECTION — restate a section in its entirety
        WAIVE_TEMPORARILY — temporarily waive compliance
        SUSPEND        — suspend a commitment
        REINSTATE      — reinstate a suspended commitment
        RENUMBER_REFERENCE — renumber a section reference
        FIND_REPLACE_REFERENCE — global find-and-replace of a defined term
        UNRESOLVED     — parser could not resolve the instruction

    Domain-effect concepts (ADD_EXCEPTION, EXTEND_DEADLINE, CHANGE_PARTY, etc.)
    have been migrated to DomainEffect. The executor uses domain_effect to
    determine which field to modify, while instruction_type determines how.
    """
    REPLACE_VALUE = "REPLACE_VALUE"
    REPLACE_TEXT = "REPLACE_TEXT"
    ADD = "ADD"
    ADD_COMMITMENT = "ADD_COMMITMENT"
    DELETE = "DELETE"
    DELETE_COMMITMENT = "DELETE_COMMITMENT"
    WAIVE_TEMPORARILY = "WAIVE_TEMPORARILY"
    SUSPEND = "SUSPEND"
    REINSTATE = "REINSTATE"
    RESTATE_SECTION = "RESTATE_SECTION"
    RENUMBER_REFERENCE = "RENUMBER_REFERENCE"
    # FIND_REPLACE_REFERENCE: global defined-term substitution propagated
    # across multiple sections (e.g., "find 'Term Loan A' and replace with
    # 'Term Loan B' throughout"). Distinct from REPLACE_TEXT because it is
    # a global find-and-replace directive, not a single-section text swap.
    # Observed in SW-001 smoke case; not yet implemented in parser.
    FIND_REPLACE_REFERENCE = "FIND_REPLACE_REFERENCE"
    UNRESOLVED = "UNRESOLVED"


class DomainEffect(str, Enum):
    """What changed in the commitment domain (the semantic effect, not the
    legal-document operation).

    Separated from InstructionType because a single transformation
    (REPLACE_VALUE) can produce different domain effects depending on
    which field changed. For example:

        InstructionType.REPLACE_VALUE
        target: lender_commitment.amount
        domain_effect: COMMITMENT_AMOUNT_CHANGE

    This separation lets us track the legal transformation mechanism and
    the business-semantic effect independently.
    """
    COVENANT_THRESHOLD_CHANGE = "covenant_threshold_change"
    COMMITMENT_AMOUNT_CHANGE = "commitment_amount_change"
    DEADLINE_CHANGE = "deadline_change"
    EXCEPTION_EXPANSION = "exception_expansion"
    EXCEPTION_REMOVAL = "exception_removal"
    PARTY_CHANGE = "party_change"
    FREQUENCY_CHANGE = "frequency_change"
    SCOPE_CHANGE = "scope_change"
    DEFINITION_CHANGE = "definition_change"
    UNKNOWN = "unknown"


class CompositeTarget(BaseModel):
    """Ground-truth composite/conformed agreement attached to a filing.

    This is NOT an amendment instruction. It is the authoritative
    post-amendment state of the credit agreement, expressed as a redline
    (bold/stricken/double-underlined) composite document. The parser
    detects its presence and location; downstream comparison uses it as
    ground truth, never as a mutation to apply.
    """
    annex: str
    start_offset: int
    end_offset: int
    source_format: str = "html_redline"


class CommitmentState(BaseModel):
    canonical_key: str
    commitment_type: str
    status: str = "ACTIVE"

    # Effective-state metadata. Half-open interval [valid_from, valid_to).
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    applicability: dict[str, Any] = Field(default_factory=dict)

    party: list[str] = Field(default_factory=list)
    modality: Optional[str] = None
    action: Optional[str] = None
    subject: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    unit: Optional[str] = None
    frequency: Optional[str] = None
    deadline: Optional[str] = None
    scope: dict[str, Any] = Field(default_factory=dict)
    exceptions: list[Any] = Field(default_factory=list)
    trigger: dict[str, Any] = Field(default_factory=dict)
    grace_period: Optional[str] = None
    cure: dict[str, Any] = Field(default_factory=dict)
    application_order: list[str] = Field(default_factory=list)


class InstructionProvenance(str, Enum):
    """How an instruction was derived — its origin and trust level.

    PARSER
        Automatically extracted by the deterministic parser (parse_v04).
        The instruction came directly from regex-based section-level
        extraction.  No human intervention.

    SEMANTIC_MAPPER
        Automatically derived by the semantic-mapping layer, which
        converts parser-extracted section-level instructions into
        commitment-level changes (target_key, field, old_value,
        new_value) with citations and confidence.  No human
        intervention beyond mapper configuration.

    COMPOSITE_EXTRACTION
        Derived from an Annex A composite or conformed copy — the
        authoritative post-amendment state was extracted directly
        from the composite document, not by replaying amendment
        instructions.  This is the fallback for full restatement
        and conformed copy patterns where the parser finds 0
        instructions.

    MANUAL
        Hand-mapped by a human reading the amendment text.  Used
        during development and for ambiguous mappings that the
        semantic mapper cannot resolve automatically.  Manual
        instructions must be reviewed before release acceptance.

    MANUAL_FALLBACK
        Hand-mapped because the parser or semantic mapper could not
        produce an instruction automatically.  This is a known
        limitation, not a routine path.  Must be tracked for
        release acceptance (manual review should be reserved for
        ambiguous mappings, not routine field population).
    """
    PARSER = "parser"
    SEMANTIC_MAPPER = "semantic_mapper"
    COMPOSITE_EXTRACTION = "composite_extraction"
    MANUAL = "manual"
    MANUAL_FALLBACK = "manual_fallback"


class AmendmentInstruction(BaseModel):
    order: int
    instruction_type: InstructionType
    target_key: Optional[str] = None
    target_section_ref: Optional[str] = None
    field: Optional[str] = None
    old_value: Any = None
    new_value: Any = None
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None
    source_text: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    # Domain effect: what changed in the commitment domain (separate from
    # the legal-document transformation operation). Populated by downstream
    # semantic analysis, not by the parser directly.
    domain_effect: Optional[DomainEffect] = None
    # Provenance: how this instruction was derived.  Required for
    # release acceptance auditing.  Defaults to MANUAL for backward
    # compatibility with existing fixtures that do not set it.
    provenance: InstructionProvenance = Field(
        default=InstructionProvenance.MANUAL,
        description="How this instruction was derived (parser, mapper, composite, manual)",
    )
    # Citation: document and section reference for audit trail.
    # Populated by the semantic mapper or manual review.
    citation_document: Optional[str] = Field(
        default=None,
        description="Source document (e.g., 'Amendment No. 3, Aug 24, 2023')",
    )
    citation_section: Optional[str] = Field(
        default=None,
        description="Source section reference (e.g., 'Section 7.10(a)')",
    )


class ExecutionStatus(str, Enum):
    """Status of an amendment execution.

    COMPLETE — all instructions applied successfully, no unresolved.
    PARTIAL — some instructions applied, some unresolved. The resulting
        state is provisional and must not be promoted to authoritative.
    UNRESOLVED — no instructions applied (all failed). No state change.
    """
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"


class ExecutionResult(BaseModel):
    state: dict[str, CommitmentState]
    applied: list[AmendmentInstruction] = Field(default_factory=list)
    unresolved: list[AmendmentInstruction] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    reference_events: list[dict[str, Any]] = Field(default_factory=list)
    status: ExecutionStatus = Field(default=ExecutionStatus.COMPLETE)
