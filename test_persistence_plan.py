from datetime import datetime, timezone
from models import CommitmentState, AmendmentInstruction, InstructionType
from executor import execute_amendment
from persistence import build_persistence_plan


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def state():
    return {
        "financial_covenant.total_leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.total_leverage_ratio",
            commitment_type="financial_covenant",
            threshold=4.0,
        )
    }


def test_two_instructions_same_commitment_plan_one_version():
    result = execute_amendment(state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=5.0,
        ),
        AmendmentInstruction(
            order=2,
            instruction_type=InstructionType.ADD_EXCEPTION,
            target_key="financial_covenant.total_leverage_ratio",
            new_value="permitted_acquisition",
        ),
    ])
    plan = build_persistence_plan(result, dt("2026-01-01T00:00:00Z"))
    assert len(plan["mutations"]) == 1
    m = plan["mutations"][0]
    assert len(m["instructions"]) == 2
    assert m["state"].threshold == 5.0
    assert "permitted_acquisition" in m["state"].exceptions


def test_waiver_restores_post_amendment_terms():
    result = execute_amendment(state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=5.0,
        ),
        AmendmentInstruction(
            order=2,
            instruction_type=InstructionType.WAIVE_TEMPORARILY,
            target_key="financial_covenant.total_leverage_ratio",
            effective_start=dt("2026-01-01T00:00:00Z"),
            effective_end=dt("2026-03-01T00:00:00Z"),
        ),
    ])
    plan = build_persistence_plan(result, dt("2026-01-01T00:00:00Z"))
    m = plan["mutations"][0]
    assert m["state"].status == "WAIVED"
    assert m["state"].threshold == 5.0
    assert m["restore_state"].status == "ACTIVE"
    assert m["restore_state"].threshold == 5.0
    assert "waiver" not in m["restore_state"].applicability


def test_state_change_requires_effective_time():
    result = execute_amendment(state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="financial_covenant.total_leverage_ratio",
            field="threshold",
            old_value=4.0,
            new_value=5.0,
        )
    ])
    try:
        build_persistence_plan(result, None)
        assert False, "Expected ValueError"
    except ValueError:
        pass
