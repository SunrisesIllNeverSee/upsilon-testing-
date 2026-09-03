from datetime import datetime
from upsilon.models.legacy_models import CommitmentState, AmendmentInstruction, DomainEffect, ExecutionStatus, InstructionType
from upsilon.execution.executor import execute_amendment


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
        instruction_type=InstructionType.ADD,
        domain_effect=DomainEffect.EXCEPTION_EXPANSION,
        target_key="financial_covenant.total_leverage_ratio",
        new_value="permitted_acquisition",
    )
    add2 = add.model_copy(update={"order": 2})
    rem = AmendmentInstruction(
        order=3,
        instruction_type=InstructionType.DELETE,
        domain_effect=DomainEffect.EXCEPTION_REMOVAL,
        target_key="financial_covenant.total_leverage_ratio",
        old_value="permitted_acquisition",
    )
    result = execute_amendment(state, [add, add2, rem])
    assert result.state["financial_covenant.total_leverage_ratio"].exceptions == []


def test_rate_change_via_domain_effect():
    """RATE_CHANGE domain effect resolves to the 'rate' field on the commitment."""
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            rate=1.5,
        )
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            domain_effect=DomainEffect.RATE_CHANGE,
            target_key="facility.credit_agreement",
            old_value=1.5,
            new_value=2.5,
        )
    ])
    assert not result.unresolved
    assert result.state["facility.credit_agreement"].rate == 2.5


def test_rate_change_via_explicit_field():
    """Explicit field='rate' on REPLACE_VALUE updates the rate field."""
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            rate=1.5,
        )
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.REPLACE_VALUE,
            target_key="facility.credit_agreement",
            field="rate",
            old_value=1.5,
            new_value=2.5,
        )
    ])
    assert not result.unresolved
    assert result.state["facility.credit_agreement"].rate == 2.5


def test_party_add_via_domain_effect():
    """ADD with PARTY_CHANGE domain effect appends to the party list."""
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            party=["borrower"],
        )
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.ADD,
            domain_effect=DomainEffect.PARTY_CHANGE,
            target_key="facility.credit_agreement",
            new_value="guarantor",
        )
    ])
    assert not result.unresolved
    assert result.state["facility.credit_agreement"].party == ["borrower", "guarantor"]


def test_party_add_idempotent():
    """ADD with PARTY_CHANGE for an existing party is a no-op (idempotent)."""
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            party=["borrower", "guarantor"],
        )
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.ADD,
            domain_effect=DomainEffect.PARTY_CHANGE,
            target_key="facility.credit_agreement",
            new_value="guarantor",
        )
    ])
    assert not result.unresolved
    assert result.state["facility.credit_agreement"].party == ["borrower", "guarantor"]


def test_party_remove_via_domain_effect():
    """DELETE with PARTY_CHANGE domain effect removes from the party list
    and does NOT mark the commitment as DELETED."""
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            party=["borrower", "guarantor"],
        )
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.DELETE,
            domain_effect=DomainEffect.PARTY_CHANGE,
            target_key="facility.credit_agreement",
            old_value="guarantor",
        )
    ])
    assert not result.unresolved
    assert result.state["facility.credit_agreement"].party == ["borrower"]
    # Critical: the commitment itself must not be marked DELETED
    assert result.state["facility.credit_agreement"].status == "ACTIVE"


def test_party_remove_missing_party_is_noop():
    """DELETE with PARTY_CHANGE for a party not in the list is a no-op
    (the commitment stays ACTIVE, party list unchanged)."""
    state = {
        "facility.credit_agreement": CommitmentState(
            canonical_key="facility.credit_agreement",
            commitment_type="facility_commitment",
            party=["borrower"],
        )
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.DELETE,
            domain_effect=DomainEffect.PARTY_CHANGE,
            target_key="facility.credit_agreement",
            old_value="guarantor",
        )
    ])
    assert not result.unresolved
    assert result.state["facility.credit_agreement"].party == ["borrower"]
    assert result.state["facility.credit_agreement"].status == "ACTIVE"


def test_generic_add_with_dict_payload_creates_new_commitment():
    """Generic ADD with a dict payload (no target_key) creates a new commitment,
    mirroring ADD_COMMITMENT behavior. This is the v0.4 architecture where ADD
    is the generic transformation and the dict payload signals a new commitment."""
    state = base_state()
    new_payload = {
        "canonical_key": "financial_covenant.interest_coverage",
        "commitment_type": "financial_covenant",
        "threshold": 3.0,
    }
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.ADD,
            new_value=new_payload,
        )
    ])
    assert not result.unresolved
    assert "financial_covenant.interest_coverage" in result.state
    assert result.state["financial_covenant.interest_coverage"].threshold == 3.0


def test_generic_add_with_dict_payload_duplicate_rejected():
    """Generic ADD with a dict payload whose canonical_key already exists is rejected."""
    state = base_state()
    new_payload = state["financial_covenant.total_leverage_ratio"].model_dump()
    result = execute_amendment(state, [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.ADD,
            new_value=new_payload,
        )
    ])
    assert len(result.unresolved) == 1


def test_generic_delete_on_commitment_resolves_to_deleted():
    """v0.4.1: Generic DELETE on a commitment resolves to DELETE_COMMITMENT
    behavior (sets status to DELETED). This is commitment-level resolution
    of the generic DELETE instruction."""
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.DELETE,
            target_key="financial_covenant.total_leverage_ratio",
        )
    ])
    assert len(result.applied) == 1
    assert len(result.unresolved) == 0
    assert result.state["financial_covenant.total_leverage_ratio"].status == "DELETED"
    assert result.status == ExecutionStatus.COMPLETE


def test_add_commitment_without_dict_payload_is_unresolved():
    """ADD_COMMITMENT without a dict payload is unresolved."""
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.ADD_COMMITMENT,
            new_value="not a dict",
        )
    ])
    assert len(result.unresolved) == 1


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


# ---------------------------------------------------------------------------
# v0.4.1: ExecutionStatus tests (COMPLETE / PARTIAL / UNRESOLVED)
# ---------------------------------------------------------------------------

def test_execution_status_complete_when_all_applied():
    """All instructions applied → status COMPLETE."""
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
    assert result.status == ExecutionStatus.COMPLETE
    assert len(result.applied) == 1
    assert len(result.unresolved) == 0


def test_execution_status_partial_when_some_unresolved():
    """Some applied, some unresolved → status PARTIAL.
    The resulting state is provisional and must not be promoted to authoritative."""
    result = execute_amendment(base_state(), [
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
            instruction_type=InstructionType.RESTATE_SECTION,
            target_key="financial_covenant.total_leverage_ratio",
        ),
    ])
    assert result.status == ExecutionStatus.PARTIAL
    assert len(result.applied) == 1
    assert len(result.unresolved) == 1


def test_execution_status_unresolved_when_all_failed():
    """No instructions applied, all unresolved → status UNRESOLVED.
    No state change should be promoted."""
    result = execute_amendment(base_state(), [
        AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_key="financial_covenant.total_leverage_ratio",
        ),
    ])
    assert result.status == ExecutionStatus.UNRESOLVED
    assert len(result.applied) == 0
    assert len(result.unresolved) == 1


def test_execution_status_complete_when_noop():
    """No instructions at all → status COMPLETE (no-op)."""
    result = execute_amendment(base_state(), [])
    assert result.status == ExecutionStatus.COMPLETE
    assert len(result.applied) == 0
    assert len(result.unresolved) == 0
