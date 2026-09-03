"""Synthetic issuer-chain fixtures for the synthetic system smoke test.

These chains are SYNTHETIC ORACLE fixtures, not independent ground truth.
The ground-truth states are hand-constructed in this same fixture module.
They model real credit-agreement amendment-chain structure and exercise
the real executor and persistence planner (the actual system under test),
not a mock.

Chain selection rationale (mirrors the RUNBOOK inclusion rule):
  - Chain ACME: 3 sequential amendments, clean chain, A&R oracle.
    Exercises Q1 (state preservation), Q2 (lineage), Q4 (oracle match).
  - Chain BETA: 2 amendments, A1 has an intentional UNRESOLVED
    instruction (RESTATE_SECTION). A2 is clean but does NOT target the
    same commitment as A1's unresolved, so A2 does NOT resolve the
    inherited uncertainty → A2 is NOT authoritative (chain-aware
    authority). Exercises Q3 (inherited unresolved blocks promotion).
  - Chain GAMMA: 2 amendments with a temporary waiver + reinstatement,
    then a threshold change. Exercises the waiver/restore persistence
    path plus Q1/Q2/Q4.
  - Chain DELTA: 3 amendments where A1 waives a covenant Jan→Jul, A2
    is an UNRELATED amendment in March, A3 is in August. Regression
    test for the chain-wide pending-restoration queue: the A1 July
    restore must NOT be lost just because A2 (the immediately
    preceding amendment) didn't touch the waived covenant.
  - Chain EPSILON: 3 amendments where A1 has a field-specific
    UNRESOLVED (REPLACE_VALUE with wrong old_value on
    interest_coverage.threshold), A2 targets a different commitment
    (does not resolve → A2 NOT authoritative), A3 targets the same
    commitment + same field + same operation (resolves A1's inherited
    unresolved → A3 IS authoritative). Regression test for
    field-specific chain-aware authority resolution.

Real multi-amendment chain acquisition from EDGAR is the next phase
(25-issuer chain study). These fixtures validate the system plumbing
before that acquisition work.
"""
from __future__ import annotations

from datetime import datetime

from upsilon.models.legacy_models import AmendmentInstruction, CommitmentState, DomainEffect, InstructionType
from upsilon.lineage.chain_reconstruction import AmendmentStep, IssuerChain


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Chain ACME — 3 clean amendments, A&R oracle
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
    Oracle ground truth: Amended and Restated Credit Agreement (filed 2026-07-01)
        - total_leverage_ratio: threshold 4.0, exception permitted_acquisition
        - interest_coverage: threshold 3.0
        - debt_service_coverage: threshold 1.25
        - revolving_commitment: amount 75_000_000
    Comparison at: 2026-07-01 (A&R filing date)
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
        comparison_at=_dt("2026-07-01T00:00:00Z"),
        ground_truth_state=ground_truth,
        ground_truth_label="Amended and Restated Credit Agreement, filed 2026-07-01 [synthetic oracle]",
    )


# ---------------------------------------------------------------------------
# Chain BETA — 2 amendments, one with intentional UNRESOLVED (not resolved)
# ---------------------------------------------------------------------------


def chain_beta() -> IssuerChain:
    """Beta Corp — 2 amendments, A1 has an UNRESOLVED instruction that A2
    does NOT resolve.

    S0: original credit agreement
        - total_leverage_ratio covenant, threshold 3.5
        - interest_coverage covenant, threshold 2.5
    A1 (2026-02-01): REPLACE leverage 3.5 → 4.0 (applied)
                     + RESTATE_SECTION on interest_coverage (UNRESOLVED —
                       executor cannot decompose a restatement without
                       explicit instructions).
                     → status PARTIAL, is_authoritative=False.
                     The leverage change IS applied to the state, but
                     the step is provisional and must not be promoted
                     to authoritative.
    A2 (2026-05-01): REPLACE leverage 4.0 → 4.25 (clean, COMPLETE).
                     A2 targets total_leverage_ratio, NOT interest_coverage
                     (the commitment with A1's unresolved RESTATE_SECTION).
                     Therefore A2 does NOT resolve A1's inherited unresolved.
                     → A2 is COMPLETE but NOT authoritative (chain-aware
                       authority: inherited unresolved blocks promotion).
    Oracle ground truth: Composite Credit Agreement (filed 2026-06-01)
        - total_leverage_ratio: threshold 4.25
        - interest_coverage: threshold 2.5
    Comparison at: 2026-06-01 (composite filing date)

    Note: the oracle ground truth reflects the FINAL state after A2. The
    reconstructed final state (leverage 4.25, interest 2.5) matches the
    oracle (Q4 passes), but the chain is NOT authoritative (Q3 correctly
    reports that A2 is blocked by inherited unresolved from A1). This
    tests that:
      (a) A1's unresolved blocks its own promotion,
      (b) A2's clean application on a DIFFERENT commitment does NOT
          clear A1's inherited unresolved → A2 is also not authoritative,
      (c) the reconstructed state still matches the oracle (state
          reconstruction is independent of authority).
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
            description="Relax leverage 4.0 → 4.25 (clean, but does not resolve A1's unresolved)",
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
        comparison_at=_dt("2026-06-01T00:00:00Z"),
        ground_truth_state=ground_truth,
        ground_truth_label="Composite Credit Agreement, filed 2026-06-01 [synthetic oracle]",
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
    Oracle ground truth: Amended and Restated Credit Agreement (filed 2026-08-01)
        - total_leverage_ratio: threshold 4.5, ACTIVE
        - interest_coverage: threshold 2.0
    Comparison at: 2026-08-01 (A&R filing date)

    This chain exercises the waiver/restore persistence path: the
    persistence plan for A1 must produce both a WAIVED version and a
    restore_state version, with a REINSTATES lineage edge between them.
    The waiver expires exactly when A2 takes effect, so the restore
    fires at the A1→A2 transition.
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
        comparison_at=_dt("2026-08-01T00:00:00Z"),
        ground_truth_state=ground_truth,
        ground_truth_label="Amended and Restated Credit Agreement, filed 2026-08-01 [synthetic oracle]",
    )


# ---------------------------------------------------------------------------
# Chain DELTA — 3 amendments, waiver with intervening unrelated amendment
# Regression test for chain-wide pending-restoration queue.
# ---------------------------------------------------------------------------


def chain_delta() -> IssuerChain:
    """Delta Systems — 3 amendments where A1 waives a covenant Jan→Jul,
    A2 is an UNRELATED amendment in March, A3 is in August.

    S0: original credit agreement
        - total_leverage_ratio covenant, threshold 5.0
        - interest_coverage covenant, threshold 2.0
    A1 (2026-01-01): WAIVE_TEMPORARILY the leverage covenant for Q1-Q2 2026
                     (Jan 1 → Jul 1).
    A2 (2026-03-01): REPLACE interest_coverage threshold 2.0 → 2.5.
                     This is UNRELATED to the waived leverage covenant.
                     At A2's effective_at (Mar 1), the waiver has NOT
                     expired (expires Jul 1), so no restore is applied yet.
    A3 (2026-08-01): REPLACE leverage threshold 5.0 → 4.5.
                     At A3's effective_at (Aug 1), the waiver HAS expired
                     (expired Jul 1). The chain-wide pending-restoration
                     queue must apply the A1 restore (leverage → ACTIVE,
                     threshold 5.0) BEFORE A3 executes. A3 then changes
                     the threshold to 4.5.
    Oracle ground truth: Amended and Restated Credit Agreement (filed 2026-09-01)
        - total_leverage_ratio: threshold 4.5, ACTIVE
        - interest_coverage: threshold 2.5
    Comparison at: 2026-09-01 (A&R filing date)

    REGRESSION TEST: This chain exposes the bug where
    _apply_expired_waiver_restores only consulted the IMMEDIATELY
    PRECEDING persistence plan. At the A2→A3 transition, the old code
    consulted A2's plan (which has no restore_state for leverage), and
    the A1 July restore was silently lost. The chain-wide pending queue
    fixes this: the A1 restore stays in the queue across A2 and fires
    at A3.
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
            description="Waive leverage covenant for Q1-Q2 2026 (Jan→Jul)",
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
            effective_at=_dt("2026-03-01T00:00:00Z"),
            description="Tighten interest_coverage 2.0 → 2.5 (unrelated to waived leverage)",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.interest_coverage",
                    field="threshold",
                    old_value=2.0,
                    new_value=2.5,
                ),
            ],
        ),
        AmendmentStep(
            amendment_number=3,
            effective_at=_dt("2026-08-01T00:00:00Z"),
            description="Tighten leverage 5.0 → 4.5 (post-waiver, after intervening A2)",
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
            threshold=2.5,
            unit="ratio",
            frequency="quarterly",
        ),
    }

    return IssuerChain(
        chain_id="CHAIN-DELTA",
        issuer_name="Delta Systems, Inc. (DELTA) [synthetic fixture]",
        original_state=original,
        amendments=amendments,
        comparison_at=_dt("2026-09-01T00:00:00Z"),
        ground_truth_state=ground_truth,
        ground_truth_label="Amended and Restated Credit Agreement, filed 2026-09-01 [synthetic oracle]",
    )


# ---------------------------------------------------------------------------
# Chain EPSILON — 3 amendments, inherited unresolved resolved by A3
# Regression test for chain-aware authority resolution.
# ---------------------------------------------------------------------------


def chain_epsilon() -> IssuerChain:
    """Epsilon Energy — 3 amendments where A1 has a field-specific
    UNRESOLVED (REPLACE_VALUE with wrong old_value on
    interest_coverage.threshold), A2 does NOT resolve it (different
    commitment), A3 DOES resolve it (same commitment + same field +
    same operation) → A3 becomes authoritative.

    S0: original credit agreement
        - total_leverage_ratio covenant, threshold 3.5
        - interest_coverage covenant, threshold 2.5
    A1 (2026-01-15): REPLACE leverage 3.5 → 4.0 (applied, correct old_value)
                     + REPLACE interest_coverage.threshold with
                       old_value=2.0 (WRONG — actual is 2.5) → UNRESOLVED.
                       The parser misread the prior threshold, so the
                       old-value guard in the executor rejects it.
                     → PARTIAL, not authoritative. inherited_unresolved
                       = [REPLACE_VALUE on interest_coverage.threshold].
    A2 (2026-03-01): REPLACE leverage 4.0 → 4.25 (clean, COMPLETE).
                     A2 targets total_leverage_ratio, NOT interest_coverage.
                     → A2 does NOT resolve A1's inherited unresolved
                       (different target_key → different resolution key).
                     → A2 is COMPLETE but NOT authoritative.
    A3 (2026-05-01): REPLACE interest_coverage.threshold 2.5 → 3.0
                     (clean, COMPLETE, correct old_value=2.5).
                     A3's resolution key = (interest_coverage, threshold,
                     REPLACE_VALUE) — SAME as A1's unresolved resolution
                     key. The inherited unresolved is resolved.
                     → A3 is COMPLETE AND inherited_unresolved is now
                       empty → A3 IS authoritative.
    Oracle ground truth: Composite Credit Agreement (filed 2026-06-01)
        - total_leverage_ratio: threshold 4.25
        - interest_coverage: threshold 3.0
    Comparison at: 2026-06-01 (composite filing date)

    REGRESSION TEST: This chain proves that chain-aware authority is not
    just "block forever" — it has a field-specific resolution mechanism.
    A later amendment that addresses the same commitment + same field +
    same operation as an inherited unresolved instruction clears the
    inherited uncertainty and allows the chain to promote to
    authoritative. A later amendment on the same commitment but a
    DIFFERENT field does NOT resolve it (see CHAIN-ZETA unit tests).
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
            effective_at=_dt("2026-01-15T00:00:00Z"),
            description="Relax leverage 3.5 → 4.0 (applied) + REPLACE interest_coverage.threshold (wrong old_value, unresolved)",
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
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.interest_coverage",
                    field="threshold",
                    old_value=2.0,  # WRONG — actual is 2.5
                    new_value=3.0,
                ),
            ],
        ),
        AmendmentStep(
            amendment_number=2,
            effective_at=_dt("2026-03-01T00:00:00Z"),
            description="Relax leverage 4.0 → 4.25 (does NOT resolve A1's unresolved on interest_coverage.threshold)",
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
        AmendmentStep(
            amendment_number=3,
            effective_at=_dt("2026-05-01T00:00:00Z"),
            description="Tighten interest_coverage.threshold 2.5 → 3.0 (resolves A1's inherited unresolved: same target + field + operation)",
            instructions=[
                AmendmentInstruction(
                    order=1,
                    instruction_type=InstructionType.REPLACE_VALUE,
                    target_key="financial_covenant.interest_coverage",
                    field="threshold",
                    old_value=2.5,  # CORRECT — matches actual
                    new_value=3.0,
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
            threshold=3.0,
            unit="ratio",
            frequency="quarterly",
        ),
    }

    return IssuerChain(
        chain_id="CHAIN-EPSILON",
        issuer_name="Epsilon Energy, LLC (EPSILON) [synthetic fixture]",
        original_state=original,
        amendments=amendments,
        comparison_at=_dt("2026-06-01T00:00:00Z"),
        ground_truth_state=ground_truth,
        ground_truth_label="Composite Credit Agreement, filed 2026-06-01 [synthetic oracle]",
    )


def all_chains() -> list[IssuerChain]:
    """Return all five smoke-test chains."""
    return [chain_acme(), chain_beta(), chain_gamma(), chain_delta(), chain_epsilon()]
