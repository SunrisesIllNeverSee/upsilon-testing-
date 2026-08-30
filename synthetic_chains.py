"""Synthetic issuer-chain fixtures for the system smoke test.

These three chains are SYNTHETIC but model real credit-agreement
amendment-chain structure. They exercise the real executor and
persistence planner (the actual system under test), not a mock.

Chain selection rationale (mirrors the RUNBOOK inclusion rule):
  - Chain ACME: 3 sequential amendments, clean chain, A&R ground truth.
    Exercises Q1 (state preservation), Q2 (lineage), Q4 (ground-truth match).
  - Chain BETA: 2 amendments, one with an intentional UNRESOLVED
    instruction (RESTATE_SECTION). Exercises Q3 (unresolved blocks
    promotion) plus Q1/Q2/Q4.
  - Chain GAMMA: 2 amendments with a temporary waiver + reinstatement,
    then a threshold change. Exercises the waiver/restore persistence
    path plus Q1/Q2/Q4.

Real multi-amendment chain acquisition from EDGAR is the next phase
(25-issuer chain study). These fixtures validate the system plumbing
before that acquisition work.
"""
from __future__ import annotations

from datetime import datetime

from models import AmendmentInstruction, CommitmentState, DomainEffect, InstructionType
from chain_reconstruction import AmendmentStep, IssuerChain


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Chain ACME — 3 clean amendments, A&R ground truth
# ---------------------------------------------------------------------------


def chain_acme() -> IssuerChain:
    """Acme Industries — 3 sequential amendments, clean chain.

    S0: original credit agreement
        - total_leverage_ratio covenant, threshold 4.0
        - interest_coverage covenant, threshold 3.0
        - revolving_commitment, amount 50_000_000
    A1 (2026-01-15): relax leverage 4.0 → 4.5
    A2 (2026-03-01): add debt_service_coverage covenant (1.25),
                     increase revolving commitment 50M → 75M
    A3 (2026-06-01): tighten leverage 4.5 → 4.0,
                     add permitted_acquisition exception to leverage
    Ground truth: Amended and Restated Credit Agreement (filed 2026-07-01)
        - total_leverage_ratio: threshold 4.0, exception permitted_acquisition
        - interest_coverage: threshold 3.0
        - debt_service_coverage: threshold 1.25
        - revolving_commitment: amount 75_000_000
    """
    original = {
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
        ),
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="interest_coverage",
            operator=">=",
            threshold=3.0,
            unit="ratio",
            frequency="quarterly",
        ),
        "facility.revolver.amount": CommitmentState(
            canonical_key="facility.revolver.amount",
            commitment_type="facility_commitment",
            party=["lender"],
            action="commit",
            subject="revolving_commitment",
            threshold=50_000_000.0,
            unit="usd",
        ),
    }

    amendments = [
        AmendmentStep(
            amendment_number=1,
            effective_at=_dt("2026-01-15T00:00:00Z"),
            description="Relax total leverage ratio 4.0 → 4.5",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.total_leverage_ratio",
                    field="threshold",
                    old_value=4.0,
                    new_value=4.5,
                ),
            ],
        ),
        AmendmentStep(
            amendment_number=2,
            effective_at=_dt("2026-03-01T00:00:00Z"),
            description="Add debt service coverage covenant; increase revolver 50M → 75M",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.ADD,
                    new_value={
                        "canonical_key": "financial_covenant.debt_service_coverage",
                        "commitment_type": "financial_covenant",
                        "party": ["borrower"],
                        "action": "maintain",
                        "subject": "debt_service_coverage",
                        "operator": ">=",
                        "threshold": 1.25,
                        "unit": "ratio",
                        "frequency": "quarterly",
                    },
                ),
                AmendmentInstruction(
                    order=2,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="facility.revolver.amount",
                    field="threshold",
                    old_value=50_000_000.0,
                    new_value=75_000_000.0,
                ),
            ],
        ),
        AmendmentStep(
            amendment_number=3,
            effective_at=_dt("2026-06-01T00:00:00Z"),
            description="Tighten leverage 4.5 → 4.0; add permitted_acquisition exception",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.total_leverage_ratio",
                    field="threshold",
                    old_value=4.5,
                    new_value=4.0,
                ),
                AmendmentInstruction(
                    order=2,
                    instruction_type=InstructionType.ADD,
                    domain_effect=DomainEffect.EXCEPTION_EXPANSION,
                    target_key="financial_covenant.total_leverage_ratio",
                    new_value="permitted_acquisition",
                ),
            ],
        ),
    ]

    ground_truth = {
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
            exceptions=["permitted_acquisition"],
        ),
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="interest_coverage",
            operator=">=",
            threshold=3.0,
            unit="ratio",
            frequency="quarterly",
        ),
        "financial_covenant.debt_service_coverage": CommitmentState(
            canonical_key="financial_covenant.debt_service_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="debt_service_coverage",
            operator=">=",
            threshold=1.25,
            unit="ratio",
            frequency="quarterly",
        ),
        "facility.revolver.amount": CommitmentState(
            canonical_key="facility.revolver.amount",
            commitment_type="facility_commitment",
            party=["lender"],
            action="commit",
            subject="revolving_commitment",
            threshold=75_000_000.0,
            unit="usd",
        ),
    }

    return IssuerChain(
        chain_id="CHAIN-ACME",
        issuer_name="Acme Industries, Inc. (ACME) [synthetic fixture]",
        original_state=original,
        amendments=amendments,
        ground_truth_state=ground_truth,
        ground_truth_label="Amended and Restated Credit Agreement, filed 2026-07-01 [synthetic]",
    )


# ---------------------------------------------------------------------------
# Chain BETA — 2 amendments, one with intentional UNRESOLVED
# ---------------------------------------------------------------------------


def chain_beta() -> IssuerChain:
    """Beta Corp — 2 amendments, A1 has an UNRESOLVED instruction.

    S0: original credit agreement
        - total_leverage_ratio covenant, threshold 3.5
        - interest_coverage covenant, threshold 2.5
    A1 (2026-02-01): REPLACE leverage 3.5 → 4.0 (applied)
                     + RESTATE_SECTION (UNRESOLVED — executor cannot
                       decompose a restatement without explicit
                       instructions).
                     → status PARTIAL, is_authoritative=False.
                     The leverage change IS applied to the state, but
                     the step is provisional and must not be promoted
                     to authoritative.
    A2 (2026-05-01): REPLACE leverage 4.0 → 4.25 (clean, COMPLETE).
                     This step is authoritative.
    Ground truth: Composite Credit Agreement (filed 2026-06-01)
        - total_leverage_ratio: threshold 4.25
        - interest_coverage: threshold 2.5

    Note: the ground truth reflects the FINAL state after A2. The
    provisional A1 state (leverage 4.0) is not the ground truth because
    A1 was not authoritative. The reconstructed final state after A2
    (leverage 4.25) should match ground truth. This tests that:
      (a) A1's unresolved blocks its promotion,
      (b) A2's clean application produces an authoritative state that
          matches the independent ground truth.
    """
    original = {
        "financial_covenant.total_leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.total_leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="total_leverage_ratio",
            operator="<=",
            threshold=3.5,
            unit="ratio",
            frequency="quarterly",
        ),
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="interest_coverage",
            operator=">=",
            threshold=2.5,
            unit="ratio",
            frequency="quarterly",
        ),
    }

    amendments = [
        AmendmentStep(
            amendment_number=1,
            effective_at=_dt("2026-02-01T00:00:00Z"),
            description="Relax leverage 3.5 → 4.0 (applied) + RESTATE_SECTION (unresolved)",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.total_leverage_ratio",
                    field="threshold",
                    old_value=3.5,
                    new_value=4.0,
                ),
                AmendmentInstruction(
                    order=2,
                    instruction_type=InstructionType.RESTATE_SECTION,
                    target_key="financial_covenant.interest_coverage",
                    target_section_ref="Section 6.07",
                ),
            ],
        ),
        AmendmentStep(
            amendment_number=2,
            effective_at=_dt("2026-05-01T00:00:00Z"),
            description="Relax leverage 4.0 → 4.25 (clean)",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.total_leverage_ratio",
                    field="threshold",
                    old_value=4.0,
                    new_value=4.25,
                ),
            ],
        ),
    ]

    ground_truth = {
        "financial_covenant.total_leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.total_leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="total_leverage_ratio",
            operator="<=",
            threshold=4.25,
            unit="ratio",
            frequency="quarterly",
        ),
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="interest_coverage",
            operator=">=",
            threshold=2.5,
            unit="ratio",
            frequency="quarterly",
        ),
    }

    return IssuerChain(
        chain_id="CHAIN-BETA",
        issuer_name="Beta Corp (BETA) [synthetic fixture]",
        original_state=original,
        amendments=amendments,
        ground_truth_state=ground_truth,
        ground_truth_label="Composite Credit Agreement, filed 2026-06-01 [synthetic]",
    )


# ---------------------------------------------------------------------------
# Chain GAMMA — 2 amendments, waiver + reinstatement path
# ---------------------------------------------------------------------------


def chain_gamma() -> IssuerChain:
    """Gamma Holdings — 2 amendments with waiver + threshold change.

    S0: original credit agreement
        - total_leverage_ratio covenant, threshold 5.0
        - interest_coverage covenant, threshold 2.0
    A1 (2026-01-01): WAIVE_TEMPORARILY the leverage covenant for Q1-Q2 2026.
                     The persistence plan must produce a WAIVED state with
                     a bounded [valid_from, valid_to) interval and a
                     restore_state that returns to ACTIVE post-waiver.
    A2 (2026-07-01): REPLACE leverage threshold 5.0 → 4.5 (clean).
                     Note: after the waiver expires, the covenant returns
                     to its post-A1 terms (threshold 5.0, ACTIVE). A2 then
                     changes the threshold to 4.5.
    Ground truth: Amended and Restated Credit Agreement (filed 2026-08-01)
        - total_leverage_ratio: threshold 4.5, ACTIVE
        - interest_coverage: threshold 2.0

    This chain exercises the waiver/restore persistence path: the
    persistence plan for A1 must produce both a WAIVED version and a
    restore_state version, with a REINSTATES lineage edge between them.
    """
    original = {
        "financial_covenant.total_leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.total_leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="total_leverage_ratio",
            operator="<=",
            threshold=5.0,
            unit="ratio",
            frequency="quarterly",
        ),
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="interest_coverage",
            operator=">=",
            threshold=2.0,
            unit="ratio",
            frequency="quarterly",
        ),
    }

    amendments = [
        AmendmentStep(
            amendment_number=1,
            effective_at=_dt("2026-01-01T00:00:00Z"),
            description="Waive leverage covenant for Q1-Q2 2026",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.WAIVE_TEMPORARILY,
                    target_key="financial_covenant.total_leverage_ratio",
                    effective_start=_dt("2026-01-01T00:00:00Z"),
                    effective_end=_dt("2026-07-01T00:00:00Z"),
                ),
            ],
        ),
        AmendmentStep(
            amendment_number=2,
            effective_at=_dt("2026-07-01T00:00:00Z"),
            description="Tighten leverage 5.0 → 4.5 (post-waiver)",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.total_leverage_ratio",
                    field="threshold",
                    old_value=5.0,
                    new_value=4.5,
                ),
            ],
        ),
    ]

    ground_truth = {
        "financial_covenant.total_leverage_ratio": CommitmentState(
            canonical_key="financial_covenant.total_leverage_ratio",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="total_leverage_ratio",
            operator="<=",
            threshold=4.5,
            unit="ratio",
            frequency="quarterly",
        ),
        "financial_covenant.interest_coverage": CommitmentState(
            canonical_key="financial_covenant.interest_coverage",
            commitment_type="financial_covenant",
            party=["borrower"],
            action="maintain",
            subject="interest_coverage",
            operator=">=",
            threshold=2.0,
            unit="ratio",
            frequency="quarterly",
        ),
    }

    return IssuerChain(
        chain_id="CHAIN-GAMMA",
        issuer_name="Gamma Holdings, LLC (GAMMA) [synthetic fixture]",
        original_state=original,
        amendments=amendments,
        ground_truth_state=ground_truth,
        ground_truth_label="Amended and Restated Credit Agreement, filed 2026-08-01 [synthetic]",
    )


def all_chains() -> list[IssuerChain]:
    """Return all three smoke-test chains."""
    return [chain_acme(), chain_beta(), chain_gamma()]
