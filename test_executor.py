from datetime import datetime, timezone
from models import CommitmentState, AmendmentInstruction, InstructionType
from executor import execute_amendment


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def base_state():
    return {
        "financial_covenant.total_leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.total_leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="total_leverage_ratio",
            operator="<=",
            threshold=4.0,
            unit="ratio",
            frequency="quarterly",
        )
    }


def test_leverage_threshold_replacement():
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=5.0,
        )
    ])
    assert not result.unresolved
    assert result.state["financial_covenant.total_leverage_ratio"].threshold == 5.0


def test_old_value_guard_blocks_bad_application():
    state = base_state()
    state["financial_covenant.total_leverage_ratio"].threshold = 4.5
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=5.0,
        )
    ])
    assert len(result.unresolved) == 1
    assert result.state["financial_covenant.total_leverage_ratio"].threshold == 4.5


def test_add_commitment_duplicate_rejected():
    state = base_state()
    new_payload = state["financial_covenant.total_leverage_ratio"].model_dump()
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.ADD_COMMITMENT,
            new_value=new_payload,
        )
    ])
    assert len(result.unresolved) == 1


def test_delete_then_reinstate():
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.DELETE_COMMITMENT,
            target_key="financial_covenant.total_leverage_ratio",
        ),
        AmendmentInstruction(
            order=2,
            instruction_type=InstructionType.REINSTATE,
            target_key="financial_covenant.total_leverage_ratio",
        ),
    ])
    assert not result.unresolved
    assert result.state["financial_covenant.total_leverage_ratio"].status == "ACTIVE"


def test_exception_add_remove_idempotent():
    state = base_state()
    add = AmendmentInstruction(
        order=1,
        instruction_type=InstructionType.ADD_EXCEPTION,
        target_key="financial_covenant.total_leverage_ratio",
        new_value="permitted_acquisition",
    )
    add2 = add.model_copy(update={"order": 2})
    rem = AmendmentInstruction(
        order=3,
        instruction_type=InstructionType.REMOVE_EXCEPTION,
        target_key="financial_covenant.total_leverage_ratio",
        old_value="permitted_acquisition",
    )
    result = execute_amendment(state, [add, add2, rem])
    assert result.state["financial_covenant.total_leverage_ratio"].exceptions == []


def test_first_instruction_persists_when_second_fails():
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=4.5,
        ),
        AmendmentInstruction(
            order=2,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,  # now stale, must fail
            new_value=5.0,
        ),
    ])
    assert len(result.unresolved) == 1
    assert result.state["financial_covenant.total_leverage_ratio"].threshold == 4.5


def test_restate_section_is_unresolved():
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_key="financial_covenant.total_leverage_ratio",
        )
    ])
    assert len(result.unresolved) == 1


def test_renumber_reference_does_not_mutate_commitment_state():
    state = base_state()
    before = state["financial_covenant.total_leverage_ratio"].model_dump()
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RENUMBER_REFERENCE,
            target_key="financial_covenant.total_leverage_ratio",
            target_section_ref="Section 6.11",
            new_value="Section 6.12",
        )
    ])
    after = result.state["financial_covenant.total_leverage_ratio"].model_dump()
    assert before == after
    assert result.reference_events[0]["old_section_ref"] == "Section 6.11"
    assert result.reference_events[0]["new_section_ref"] == "Section 6.12"


def test_empty_instruction_list_is_noop():
    state = base_state()
    result = execute_amendment(state, [])
    assert result.state["financial_covenant.total_leverage_ratio"].threshold == 4.0
    assert result.events == []


def test_unresolved_passthrough():
    result = execute_amendment(base_state(), [
        AmendmentInstruction(order=1, instruction_type=InstructionType.UNRESOLVED)
    ])
    assert len(result.unresolved) == 1
    assert result.events[0]["status"] == "UNRESOLVED"


def test_temporary_waiver_uses_applicability_interval():
    state = {
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            threshold=3.0,
        )
    }
    start = dt("2026-01-01T00:00:00Z")
    end = dt("2026-06-30T00:00:00Z")
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.WAIVE_TEMPORARILY,
            target_key="financial_covenant.interest_coverage",
            effective_start=start,
            effective_end=end,
        )
    ])
    c = result.state["financial_covenant.interest_coverage"]
    assert c.status == "WAIVED"
    assert c.threshold == 3.0
    assert c.valid_from == start
    assert c.valid_to == end
    assert c.applicability["waiver"]["end"].startswith("2026-06-30")
