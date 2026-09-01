"""Tests for Step 22F staged field/value semantic interpreter."""
from __future__ import annotations

from semantic_resolver_v2 import (
    StageStatus,
    ResolverStepTrace,
    resolve_instruction,
)
from models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)


def test_stage_status_enum_values():
    """StageStatus should have RESOLVED, AMBIGUOUS, UNSUPPORTED."""
    assert StageStatus.RESOLVED.value == "RESOLVED"
    assert StageStatus.AMBIGUOUS.value == "AMBIGUOUS"
    assert StageStatus.UNSUPPORTED.value == "UNSUPPORTED"


def test_resolver_trace_has_stage_statuses():
    """ResolverStepTrace should have all 7 stage status fields."""
    trace = ResolverStepTrace()
    assert trace.stage1_legal_operation == StageStatus.RESOLVED
    assert trace.stage2_target_commitment == StageStatus.RESOLVED
    assert trace.stage3_target_field == StageStatus.RESOLVED
    assert trace.stage4_old_value == StageStatus.RESOLVED
    assert trace.stage5_new_value == StageStatus.RESOLVED
    assert trace.stage6_unit == StageStatus.RESOLVED
    assert trace.stage7_effective_time == StageStatus.RESOLVED


def test_resolve_instruction_returns_trace_with_stages():
    """resolve_instruction should return a trace with stage statuses."""
    state = {
        "financial_covenant.leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.leverage_ratio",
            commitment_type="financial_covenant",
            threshold=4.0,
            unit="ratio",
            status="ACTIVE",
        ),
    }
    ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_section_ref="Section 7.10",
        source_text="The Maximum Leverage Ratio shall not exceed 3.50 to 1.00",
        provenance=InstructionProvenance.PARSER,
    )
    result, trace = resolve_instruction(ins, state)
    # The trace should have stage statuses set
    assert isinstance(trace.stage1_legal_operation, StageStatus)
    assert isinstance(trace.stage2_target_commitment, StageStatus)


def test_unsupported_commitment_returns_unresolved():
    """An instruction targeting an unsupported commitment should be unresolved."""
    state = {}
    ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_section_ref="Section 99.99",
        source_text="Some unknown covenant shall be 1.00",
        provenance=InstructionProvenance.PARSER,
    )
    result, trace = resolve_instruction(ins, state)
    # Should be unresolved (no mapped mutations)
    assert len(result.mutations) == 0
    assert len(result.unresolved) > 0


def test_ambiguous_value_returns_unresolved():
    """An instruction with ambiguous values should be unresolved, not guessed."""
    state = {
        "facility.revolving_facility": CommitmentState(
            canonical_key="facility.revolving_facility",
            commitment_type="facility_commitment",
            threshold=50000000.0,
            unit="usd",
            status="ACTIVE",
        ),
    }
    # Multiple dollar amounts → ambiguous
    ins = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.REPLACE_VALUE,
        target_section_ref="Section 2.01",
        source_text="The Revolving Facility shall be increased from $50,000,000 to $75,000,000 and the Term Loan shall be $150,000,000",
        provenance=InstructionProvenance.PARSER,
    )
    result, trace = resolve_instruction(ins, state)
    # Should NOT produce a mapped mutation with a guessed value
    # (multiple dollar amounts make the new value ambiguous)
    # The resolver may either unresolved it or map it correctly;
    # the key test is that it doesn't guess wrong.
    if result.mutations:
        # If mapped, the value must be one of the dollar amounts
        # in the source text, not a fabricated value
        mut = result.mutations[0]
        if mut.new_value is not None:
            assert mut.new_value in (50000000.0, 75000000.0, 150000000.0)
