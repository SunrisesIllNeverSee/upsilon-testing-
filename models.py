from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class InstructionType(str, Enum):
    REPLACE_VALUE = "REPLACE_VALUE"
    REPLACE_TEXT = "REPLACE_TEXT"
    ADD_COMMITMENT = "ADD_COMMITMENT"
    DELETE_COMMITMENT = "DELETE_COMMITMENT"
    MODIFY_SCOPE = "MODIFY_SCOPE"
    ADD_EXCEPTION = "ADD_EXCEPTION"
    REMOVE_EXCEPTION = "REMOVE_EXCEPTION"
    EXTEND_DEADLINE = "EXTEND_DEADLINE"
    CHANGE_FREQUENCY = "CHANGE_FREQUENCY"
    CHANGE_PARTY = "CHANGE_PARTY"
    WAIVE_TEMPORARILY = "WAIVE_TEMPORARILY"
    SUSPEND = "SUSPEND"
    REINSTATE = "REINSTATE"
    RESTATE_SECTION = "RESTATE_SECTION"
    RENUMBER_REFERENCE = "RENUMBER_REFERENCE"
    COMPOSITE_RESTATEMENT = "COMPOSITE_RESTATEMENT"
    UNRESOLVED = "UNRESOLVED"


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


class ExecutionResult(BaseModel):
    state: dict[str, CommitmentState]
    applied: list[AmendmentInstruction] = Field(default_factory=list)
    unresolved: list[AmendmentInstruction] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    reference_events: list[dict[str, Any]] = Field(default_factory=list)
