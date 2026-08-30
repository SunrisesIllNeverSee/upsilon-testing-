from __future__ import annotations
from copy import deepcopy
from typing import Dict
from models import AmendmentInstruction, CommitmentState, ExecutionResult, InstructionType


class UnresolvedInstruction(Exception):
    pass


def _get(state: Dict[str, CommitmentState], key: str) -> CommitmentState:
    if key not in state:
        raise UnresolvedInstruction(f"Unknown target commitment: {key}")
    return state[key]


def apply_instruction(
    state: Dict[str, CommitmentState],
    ins: AmendmentInstruction,
) -> tuple[dict, dict | None]:
    t = ins.instruction_type

    if t == InstructionType.UNRESOLVED:
        raise UnresolvedInstruction("Parser marked instruction unresolved")

    if t == InstructionType.RENUMBER_REFERENCE:
        old_ref = ins.target_section_ref or ins.old_value
        new_ref = ins.new_value
        if not old_ref or not new_ref:
            raise UnresolvedInstruction("RENUMBER_REFERENCE requires old and new section references")
        return (
            {
                "action": "reference_change",
                "target": ins.target_key,
                "old_section_ref": str(old_ref),
                "new_section_ref": str(new_ref),
            },
            {
                "target_key": ins.target_key,
                "old_section_ref": str(old_ref),
                "new_section_ref": str(new_ref),
            }
        )

    if t == InstructionType.ADD_COMMITMENT:
        if not isinstance(ins.new_value, dict):
            raise UnresolvedInstruction("ADD_COMMITMENT requires object payload")
        obj = CommitmentState(**ins.new_value)
        if obj.canonical_key in state:
            raise UnresolvedInstruction(f"Commitment already exists: {obj.canonical_key}")
        state[obj.canonical_key] = obj
        return {"action": "add", "target": obj.canonical_key}, None

    if not ins.target_key:
        raise UnresolvedInstruction(f"{t} requires target_key")

    c = _get(state, ins.target_key)

    if t == InstructionType.DELETE_COMMITMENT:
        old = c.status
        c.status = "DELETED"
        return {"action": "status", "target": ins.target_key, "old": old, "new": "DELETED"}, None

    if t == InstructionType.SUSPEND:
        old = c.status
        c.status = "SUSPENDED"
        return {"action": "status", "target": ins.target_key, "old": old, "new": "SUSPENDED"}, None

    if t == InstructionType.REINSTATE:
        old = c.status
        c.status = "ACTIVE"
        return {"action": "status", "target": ins.target_key, "old": old, "new": "ACTIVE"}, None

    if t == InstructionType.WAIVE_TEMPORARILY:
        if not ins.effective_start or not ins.effective_end:
            raise UnresolvedInstruction("WAIVE_TEMPORARILY requires effective_start and effective_end")
        if ins.effective_end <= ins.effective_start:
            raise UnresolvedInstruction("Waiver effective_end must be after effective_start")
        old = c.status
        c.status = "WAIVED"
        c.valid_from = ins.effective_start
        c.valid_to = ins.effective_end
        c.applicability = dict(c.applicability)
        c.applicability["waiver"] = {
            "start": ins.effective_start.isoformat(),
            "end": ins.effective_end.isoformat(),
        }
        return {"action": "waive", "target": ins.target_key, "old": old, "new": "WAIVED"}, None

    if t in {
        InstructionType.REPLACE_VALUE,
        InstructionType.REPLACE_TEXT,
        InstructionType.EXTEND_DEADLINE,
        InstructionType.CHANGE_FREQUENCY,
        InstructionType.CHANGE_PARTY,
        InstructionType.MODIFY_SCOPE,
    }:
        field = ins.field
        if t == InstructionType.EXTEND_DEADLINE:
            field = field or "deadline"
        elif t == InstructionType.CHANGE_FREQUENCY:
            field = field or "frequency"
        elif t == InstructionType.CHANGE_PARTY:
            field = field or "party"
        elif t == InstructionType.MODIFY_SCOPE:
            field = field or "scope"

        if not field or not hasattr(c, field):
            raise UnresolvedInstruction(f"Unsupported or missing field: {field}")

        old = deepcopy(getattr(c, field))
        if ins.old_value is not None and old != ins.old_value:
            raise UnresolvedInstruction(
                f"Old-value mismatch for {ins.target_key}.{field}: "
                f"expected {ins.old_value!r}, actual {old!r}"
            )
        setattr(c, field, deepcopy(ins.new_value))
        return {
            "action": "replace",
            "target": ins.target_key,
            "field": field,
            "old": old,
            "new": deepcopy(ins.new_value),
        }, None

    if t == InstructionType.ADD_EXCEPTION:
        old = deepcopy(c.exceptions)
        if ins.new_value not in c.exceptions:
            c.exceptions.append(deepcopy(ins.new_value))
        return {"action": "add_exception", "target": ins.target_key, "old": old, "new": deepcopy(c.exceptions)}, None

    if t == InstructionType.REMOVE_EXCEPTION:
        old = deepcopy(c.exceptions)
        c.exceptions = [x for x in c.exceptions if x != ins.old_value]
        return {"action": "remove_exception", "target": ins.target_key, "old": old, "new": deepcopy(c.exceptions)}, None

    if t == InstructionType.RESTATE_SECTION:
        raise UnresolvedInstruction(
            "RESTATE_SECTION requires decomposition into explicit validated instructions"
        )

    raise UnresolvedInstruction(f"Unsupported instruction: {t}")


def execute_amendment(
    current_state: Dict[str, CommitmentState],
    instructions: list[AmendmentInstruction],
) -> ExecutionResult:
    work = {k: v.model_copy(deep=True) for k, v in current_state.items()}
    applied = []
    unresolved = []
    events = []
    reference_events = []

    for ins in sorted(instructions, key=lambda x: x.order):
        snapshot = {k: v.model_copy(deep=True) for k, v in work.items()}
        try:
            event, ref_event = apply_instruction(work, ins)
            event["order"] = ins.order
            event["instruction_type"] = ins.instruction_type.value
            applied.append(ins)
            events.append(event)
            if ref_event:
                ref_event["order"] = ins.order
                reference_events.append(ref_event)
        except UnresolvedInstruction as exc:
            work = snapshot
            unresolved.append(ins)
            events.append({
                "order": ins.order,
                "instruction_type": ins.instruction_type.value,
                "status": "UNRESOLVED",
                "reason": str(exc),
            })

    return ExecutionResult(
        state=work,
        applied=applied,
        unresolved=unresolved,
        events=events,
        reference_events=reference_events,
    )
