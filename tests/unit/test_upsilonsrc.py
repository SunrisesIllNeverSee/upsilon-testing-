"""Tests for the src/upsilon/ package — MOSES conservation-first commitment engine.

Tests the full pipeline:
    identity resolution → transformation engine → conservation validation
    → proof assembly → authority gate → lineage → kernel advancement

Plus safety/failure-path tests verifying that incorrect mutations are
blocked at the appropriate layer.
"""
import os
import sys
from datetime import UTC, datetime

import pytest

# Ensure src/ is on the path
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from upsilon.authority import AuthorityGate
from upsilon.commitments import (
    AgreementAddressMap,
    IdentityResolver,
    KernelStore,
    OriginKernelBuilder,
)
from upsilon.commitments.identity import IdentityResolutionResult
from upsilon.conservation import ConservationValidator, LossDetector
from upsilon.lineage import CommitmentLineageGraph, LineageQueries
from upsilon.models import (
    AddressBinding,
    AffectedField,
    AuthorityDecision,
    AuthorizedTransformation,
    CommitmentIdentity,
    CommitmentKernel,
    ConservationChecks,
    EvidenceStatus,
    ExecutionResultSummary,
    LineageEdge,
    ProofCompleteness,
    ProofValidity,
    SemanticTransformationProof,
    TransformationFamily,
    UncertaintyStatus,
)
from upsilon.proof import ProofAssembler
from upsilon.transformations import (
    AmendmentEvidence,
    AuthorityContext,
    AuthorizedTransformationEngine,
    apply_transformation,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def addr_map():
    """Agreement-local address map with two commitments registered."""
    am = AgreementAddressMap("AGR-001")
    am.register("FC-001", "7.10", "S0")
    am.register("FC-002", "7.11", "S0")
    return am


@pytest.fixture
def kernel_store(addr_map):
    """Kernel store with an origin kernel containing one leverage ratio commitment."""
    store = KernelStore("AGR-001")
    builder = OriginKernelBuilder("AGR-001")
    ident = CommitmentIdentity(
        commitment_id="FC-001",
        agreement_identity="AGR-001",
        canonical_key="financial_covenant.leverage_ratio",
        local_address=addr_map.get_binding("FC-001"),
    )
    builder.add_commitment(
        ident, threshold=4.0, operator="<=", unit="ratio", status="ACTIVE",
        exceptions=["Permitted Acquisitions"],
    )
    builder.build(store)
    return store


@pytest.fixture
def resolver(addr_map):
    return IdentityResolver(addr_map)


@pytest.fixture
def engine(resolver):
    return AuthorizedTransformationEngine(resolver)


@pytest.fixture
def validator():
    return ConservationValidator()


@pytest.fixture
def assembler():
    return ProofAssembler()


@pytest.fixture
def gate():
    return AuthorityGate()


def make_evidence(
    section_ref="7.10",
    instruction_type="REPLACE_VALUE",
    target_field="threshold",
    new_value=3.75,
    declared_old_value=4.0,
    alias_match="Total Leverage Ratio",
    canonical_key_hint="financial_covenant.leverage_ratio",
    source_text="Section 7.10 is hereby amended to reduce the Total Leverage Ratio from 4.00 to 1 to 3.75 to 1.0",
    exception_text=None,
    effective_date=None,
):
    return AmendmentEvidence(
        source_text=source_text,
        source_section_ref=section_ref,
        source_document="Amendment No. 3",
        source_authority="Amendment No. 3, Section 2",
        amendment_id="AMN-003",
        instruction_type=instruction_type,
        target_field=target_field,
        new_value=new_value,
        declared_old_value=declared_old_value,
        alias_match=alias_match,
        canonical_key_hint=canonical_key_hint,
        exception_text=exception_text,
        effective_date=effective_date,
    )


def make_authority(kernel_store, commitment_ids=None):
    if commitment_ids is None:
        commitment_ids = ["FC-001"]
    return AuthorityContext(
        predecessor_kernel=kernel_store.get_current("FC-001"),
        predecessor_commitment_ids=commitment_ids,
        amendment_number=3,
        chain_position=3,
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestCommitmentIdentity:
    def test_identity_equality_by_id_and_agreement(self):
        addr = AddressBinding(section_ref="7.10", established_at_version="S0")
        id1 = CommitmentIdentity(
            commitment_id="FC-001", agreement_identity="AGR-001",
            canonical_key="financial_covenant.leverage_ratio", local_address=addr,
        )
        id2 = CommitmentIdentity(
            commitment_id="FC-001", agreement_identity="AGR-001",
            canonical_key="financial_covenant.leverage_ratio",
            local_address=AddressBinding(section_ref="7.10A", established_at_version="AMN-1"),
        )
        assert id1 == id2  # same commitment, different address

    def test_identity_inequality_different_agreement(self):
        addr = AddressBinding(section_ref="7.10", established_at_version="S0")
        id1 = CommitmentIdentity(
            commitment_id="FC-001", agreement_identity="AGR-001",
            canonical_key="financial_covenant.leverage_ratio", local_address=addr,
        )
        id2 = CommitmentIdentity(
            commitment_id="FC-001", agreement_identity="AGR-002",
            canonical_key="financial_covenant.leverage_ratio", local_address=addr,
        )
        assert id1 != id2

    def test_identity_hashable(self):
        addr = AddressBinding(section_ref="7.10", established_at_version="S0")
        ident = CommitmentIdentity(
            commitment_id="FC-001", agreement_identity="AGR-001",
            canonical_key="financial_covenant.leverage_ratio", local_address=addr,
        )
        assert hash(ident) == hash(("FC-001", "AGR-001"))


class TestCommitmentKernel:
    def test_semantic_fields(self, kernel_store):
        kernel = kernel_store.get_current("FC-001")
        fields = kernel.semantic_fields()
        assert "threshold" in fields
        assert "operator" in fields
        assert "exceptions" in fields
        assert fields["threshold"] == 4.0

    def test_field_value(self, kernel_store):
        kernel = kernel_store.get_current("FC-001")
        assert kernel.field_value("threshold") == 4.0
        assert kernel.field_value("operator") == "<="
        assert kernel.field_value("nonexistent") is None


class TestTransformationFamily:
    def test_identity_changing_families(self):
        assert TransformationFamily.CREATE.is_identity_changing
        assert TransformationFamily.TERMINATE.is_identity_changing
        assert TransformationFamily.RENUMBER.is_identity_changing
        assert not TransformationFamily.SCALAR_REPLACEMENT.is_identity_changing
        assert not TransformationFamily.EXCEPTION_EXPANSION.is_identity_changing


# ---------------------------------------------------------------------------
# Address map tests
# ---------------------------------------------------------------------------


class TestAgreementAddressMap:
    def test_register_and_resolve(self, addr_map):
        assert addr_map.resolve_by_address("7.10") == "FC-001"
        assert addr_map.resolve_by_address("7.11") == "FC-002"

    def test_resolve_unknown_returns_none(self, addr_map):
        assert addr_map.resolve_by_address("9.99") is None

    def test_renumber_preserves_identity(self, addr_map):
        new_binding = addr_map.renumber("FC-001", "7.10A", "AMN-001")
        assert new_binding is not None
        assert new_binding.renumbered_from == "7.10"
        # Both old and new addresses resolve to same commitment
        assert addr_map.resolve_by_address("7.10A") == "FC-001"
        assert addr_map.resolve_by_address("7.10") == "FC-001"

    def test_get_binding(self, addr_map):
        binding = addr_map.get_binding("FC-001")
        assert binding is not None
        assert binding.section_ref == "7.10"

    def test_known_commitments(self, addr_map):
        commitments = addr_map.known_commitments()
        assert "FC-001" in commitments
        assert "FC-002" in commitments


# ---------------------------------------------------------------------------
# Identity resolver tests
# ---------------------------------------------------------------------------


class TestIdentityResolver:
    def test_resolve_by_address_sufficient(self, resolver):
        result = resolver.resolve(
            section_ref="7.10",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        assert result.resolved
        assert result.identity is not None
        assert result.identity.commitment_id == "FC-001"
        assert result.evidence_level == "SUFFICIENT"

    def test_resolve_insufficient_fails_closed(self, resolver):
        result = resolver.resolve(
            section_ref=None,
            alias_match="Leverage Ratio",
            predecessor_commitment_ids=[],
        )
        assert result.fail_closed
        assert result.identity is None
        assert result.evidence_level == "INSUFFICIENT"

    def test_resolve_weak_alias_only(self, resolver):
        result = resolver.resolve(
            section_ref=None,
            alias_match="Leverage Ratio",
            predecessor_commitment_ids=[],
        )
        assert result.evidence_level == "INSUFFICIENT"
        assert result.fail_closed

    def test_resolve_corroborated(self, resolver):
        result = resolver.resolve(
            section_ref="7.10",
            alias_match="Leverage Ratio",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        assert result.evidence_level in ("SUFFICIENT", "CORROBORATED")
        assert result.resolved


# ---------------------------------------------------------------------------
# Kernel store tests
# ---------------------------------------------------------------------------


class TestKernelStore:
    def test_establish_origin(self, kernel_store):
        kernel = kernel_store.get_current("FC-001")
        assert kernel is not None
        assert kernel.threshold == 4.0
        assert kernel.version is not None
        assert kernel.version.version_number == 0

    def test_establish_duplicate_raises(self, kernel_store, addr_map):
        ident = CommitmentIdentity(
            commitment_id="FC-001", agreement_identity="AGR-001",
            canonical_key="financial_covenant.leverage_ratio",
            local_address=addr_map.get_binding("FC-001"),
        )
        with pytest.raises(ValueError, match="already exists"):
            kernel_store.establish_origin(
                CommitmentKernel(identity=ident, threshold=5.0)
            )

    def test_advance_creates_new_version(self, kernel_store):
        pred = kernel_store.get_current("FC-001")
        successor = pred.model_copy(deep=True)
        successor.threshold = 3.75
        version = kernel_store.advance("FC-001", successor, "PRF-001")
        assert version.version_number == 1
        assert version.predecessor_version == 0
        assert kernel_store.get_current("FC-001").threshold == 3.75

    def test_version_history(self, kernel_store):
        pred = kernel_store.get_current("FC-001")
        successor = pred.model_copy(deep=True)
        successor.threshold = 3.75
        kernel_store.advance("FC-001", successor, "PRF-001")
        history = kernel_store.get_version_history("FC-001")
        assert len(history) == 2
        assert history[0].version_number == 0
        assert history[1].version_number == 1

    def test_authoritative_kernel_at_time(self, kernel_store):
        pred = kernel_store.get_current("FC-001")
        successor = pred.model_copy(deep=True)
        successor.threshold = 3.75
        successor.valid_from = datetime(2025, 1, 1, tzinfo=UTC)
        kernel_store.advance("FC-001", successor, "PRF-001")
        # Before the successor's valid_from, should not include it
        # (but current kernel is the successor, so it will be included
        # unless valid_from filters it out)
        before = kernel_store.authoritative_kernel(at_time=datetime(2024, 1, 1, tzinfo=UTC))
        assert "FC-001" not in before


# ---------------------------------------------------------------------------
# Transformation engine tests
# ---------------------------------------------------------------------------


class TestAuthorizedTransformationEngine:
    def test_authorize_valid_scalar_replacement(self, engine, kernel_store):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.authorized
        assert result.transformation.transformation_type == TransformationFamily.SCALAR_REPLACEMENT
        assert result.transformation.affected_field_names == ["threshold"]
        assert result.transformation.old_values() == {"threshold": 4.0}
        assert result.transformation.new_values() == {"threshold": 3.75}

    def test_reject_wrong_old_value(self, engine, kernel_store):
        ev = make_evidence(declared_old_value=3.5)  # wrong: predecessor has 4.0
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.rejected
        assert result.rejection_step == "old_value_consistency"

    def test_reject_insufficient_identity(self, engine, kernel_store):
        ev = make_evidence(section_ref=None, alias_match=None)
        auth = make_authority(kernel_store, commitment_ids=[])
        result = engine.authorize(ev, auth)
        assert result.rejected
        assert result.rejection_step == "target_identity"

    def test_reject_no_new_value(self, engine, kernel_store):
        ev = make_evidence(new_value=None)
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.rejected
        assert result.rejection_step == "value_extraction"

    def test_old_value_consistency_verified_flag(self, engine, kernel_store):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.authorized
        assert result.transformation.old_value_consistency_verified is True

    def test_no_declared_old_value_passes(self, engine, kernel_store):
        """When amendment doesn't declare an old value, consistency check passes."""
        ev = make_evidence(declared_old_value=None)
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.authorized

    def test_add_without_exception_target_fails_closed(self, engine, kernel_store):
        """ADD without exception_text or exceptions target_field must fail closed."""
        ev = make_evidence(
            instruction_type="ADD",
            target_field="threshold",
            new_value=3.75,
            exception_text=None,
        )
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.rejected
        assert result.rejection_step == "transformation_type"

    def test_add_with_exception_text_authorizes(self, engine, kernel_store):
        """ADD with exception_text authorizes as EXCEPTION_EXPANSION."""
        ev = make_evidence(
            instruction_type="ADD",
            target_field="exceptions",
            new_value="New Exception",
            exception_text="New Exception",
            declared_old_value=None,
        )
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.authorized
        assert result.transformation.transformation_type == TransformationFamily.EXCEPTION_EXPANSION

    def test_waiver_engine_preserves_temporal_fields(self, engine, kernel_store):
        """Engine-produced WAIVER delta must not include valid_from/valid_to
        in affected_fields — those are preserved, not wiped."""
        pred = kernel_store.get_current("FC-001")
        pred.valid_from = datetime(2024, 1, 1, tzinfo=UTC)
        pred.valid_to = datetime(2030, 1, 1, tzinfo=UTC)
        ev = make_evidence(
            instruction_type="WAIVE_TEMPORARILY",
            target_field=None,
            new_value=None,
            declared_old_value=None,
        )
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.authorized
        affected = result.transformation.affected_field_names
        assert "status" in affected
        assert "applicability" in affected
        assert "valid_from" not in affected
        assert "valid_to" not in affected


# ---------------------------------------------------------------------------
# Apply transformation tests
# ---------------------------------------------------------------------------


class TestApplyTransformation:
    def test_scalar_replacement_preserves_other_fields(self, kernel_store):
        pred = kernel_store.get_current("FC-001")
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            commitment_id="FC-001",
            agreement_identity="AGR-001",
            affected_fields=[AffectedField(field_name="threshold", old_value=4.0, new_value=3.75)],
            preserved_fields=["operator", "unit", "exceptions"],
        )
        successor = apply_transformation(pred, delta)
        assert successor.threshold == 3.75
        assert successor.operator == "<="  # preserved
        assert successor.unit == "ratio"  # preserved
        assert successor.exceptions == ["Permitted Acquisitions"]  # preserved

    def test_exception_expansion_appends(self, kernel_store):
        pred = kernel_store.get_current("FC-001")
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.EXCEPTION_EXPANSION,
            commitment_id="FC-001",
            agreement_identity="AGR-001",
            affected_fields=[AffectedField(field_name="exceptions", old_value=["Permitted Acquisitions"], new_value="New Exception")],
            preserved_fields=["threshold", "operator", "unit"],
        )
        successor = apply_transformation(pred, delta)
        assert "Permitted Acquisitions" in successor.exceptions
        assert "New Exception" in successor.exceptions

    def test_terminate_sets_status(self, kernel_store):
        pred = kernel_store.get_current("FC-001")
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.TERMINATE,
            commitment_id="FC-001",
            agreement_identity="AGR-001",
            affected_fields=[AffectedField(field_name="status", old_value="ACTIVE", new_value="TERMINATED")],
            preserved_fields=["threshold", "operator", "unit", "exceptions"],
        )
        successor = apply_transformation(pred, delta)
        assert successor.status == "TERMINATED"
        assert successor.threshold == 4.0  # preserved

    def test_waiver_preserves_valid_from_valid_to(self, kernel_store):
        """WAIVER must not wipe valid_from / valid_to — those are the
        commitment's overall validity period, not the waiver window."""
        pred = kernel_store.get_current("FC-001")
        pred.valid_from = datetime(2024, 1, 1, tzinfo=UTC)
        pred.valid_to = datetime(2030, 1, 1, tzinfo=UTC)
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.WAIVER,
            commitment_id="FC-001",
            agreement_identity="AGR-001",
            affected_fields=[
                AffectedField(field_name="status", old_value="ACTIVE", new_value="WAIVED"),
                AffectedField(field_name="applicability", old_value={}, new_value={"waived": True}),
            ],
            preserved_fields=["threshold", "operator", "unit", "exceptions",
                              "valid_from", "valid_to"],
            source_authority="AMN-001",
        )
        successor = apply_transformation(pred, delta)
        assert successor.status == "WAIVED"
        assert successor.valid_from == datetime(2024, 1, 1, tzinfo=UTC)  # preserved
        assert successor.valid_to == datetime(2030, 1, 1, tzinfo=UTC)  # preserved

    def test_reinstatement_preserves_valid_from_valid_to(self, kernel_store):
        """REINSTATEMENT must not wipe valid_from / valid_to."""
        pred = kernel_store.get_current("FC-001")
        pred.status = "WAIVED"
        pred.valid_from = datetime(2024, 1, 1, tzinfo=UTC)
        pred.valid_to = datetime(2030, 1, 1, tzinfo=UTC)
        pred.applicability = {"waived": True}
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.REINSTATEMENT,
            commitment_id="FC-001",
            agreement_identity="AGR-001",
            affected_fields=[
                AffectedField(field_name="status", old_value="WAIVED", new_value="ACTIVE"),
                AffectedField(field_name="applicability", old_value={"waived": True}, new_value={}),
            ],
            preserved_fields=["threshold", "operator", "unit", "exceptions",
                              "valid_from", "valid_to"],
            source_authority="AMN-002",
        )
        successor = apply_transformation(pred, delta)
        assert successor.status == "ACTIVE"
        assert successor.valid_from == datetime(2024, 1, 1, tzinfo=UTC)  # preserved
        assert successor.valid_to == datetime(2030, 1, 1, tzinfo=UTC)  # preserved


# ---------------------------------------------------------------------------
# Conservation validator tests
# ---------------------------------------------------------------------------


class TestConservationValidator:
    def test_valid_transformation_passes(self, validator, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        validation = validator.validate(
            kernel_store.get_current("FC-001"), successor, result.transformation
        )
        assert validation.passed
        assert validation.failed_invariants == []

    def test_unchanged_field_violation_detected(self, validator, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        successor.operator = ">="  # corrupt a preserved field
        validation = validator.validate(
            kernel_store.get_current("FC-001"), successor, result.transformation
        )
        assert not validation.passed
        assert "unchanged_field_preservation" in validation.failed_invariants

    def test_identity_persistence_violation(self, validator, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        # Corrupt the identity
        successor.identity = CommitmentIdentity(
            commitment_id="FC-999",  # different ID
            agreement_identity="AGR-001",
            canonical_key="financial_covenant.leverage_ratio",
            local_address=AddressBinding(section_ref="7.10", established_at_version="S0"),
        )
        validation = validator.validate(
            kernel_store.get_current("FC-001"), successor, result.transformation
        )
        assert not validation.passed
        assert "identity_persistence" in validation.failed_invariants

    def test_no_unsupported_semantic_gain(self, validator, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        successor.exceptions.append("Sneaky New Exception")  # gain without evidence
        validation = validator.validate(
            kernel_store.get_current("FC-001"), successor, result.transformation
        )
        assert not validation.passed
        assert "no_unsupported_semantic_gain" in validation.failed_invariants

    def test_no_silent_semantic_loss(self, validator, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        successor.exceptions = []  # silent loss
        validation = validator.validate(
            kernel_store.get_current("FC-001"), successor, result.transformation
        )
        assert not validation.passed
        assert "no_silent_semantic_loss" in validation.failed_invariants

    def test_temporal_validity_waiver_requires_active(self, validator, kernel_store):
        pred = kernel_store.get_current("FC-001")
        pred.status = "WAIVED"  # not active
        delta = AuthorizedTransformation(
            transformation_type=TransformationFamily.WAIVER,
            commitment_id="FC-001",
            agreement_identity="AGR-001",
            affected_fields=[AffectedField(field_name="status", old_value="WAIVED", new_value="WAIVED")],
            preserved_fields=["threshold"],
            source_authority="AMN-001",
        )
        validation = validator.validate(pred, pred, delta)
        assert not validation.passed
        assert "temporal_validity" in validation.failed_invariants


# ---------------------------------------------------------------------------
# Loss detector tests
# ---------------------------------------------------------------------------


class TestLossDetector:
    def test_no_loss_detected(self, kernel_store, engine):
        detector = LossDetector()
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        loss = detector.detect(kernel_store.get_current("FC-001"), successor, result.transformation)
        assert not loss.has_losses

    def test_exception_loss_detected(self, kernel_store, engine):
        detector = LossDetector()
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        successor.exceptions = []  # silent loss
        loss = detector.detect(kernel_store.get_current("FC-001"), successor, result.transformation)
        assert loss.has_losses
        assert any(l.field_name == "exceptions" for l in loss.losses)


# ---------------------------------------------------------------------------
# Proof tests
# ---------------------------------------------------------------------------


class TestProofAssembly:
    def test_complete_valid_proof(self, assembler, validator, resolver, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        validation = validator.validate(kernel_store.get_current("FC-001"), successor, result.transformation)
        identity_result = resolver.resolve(
            section_ref="7.10", alias_match="Total Leverage Ratio",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        proof = assembler.assemble_pre_execution(
            delta=result.transformation, identity_result=identity_result,
            validation=validation, predecessor_version=0, successor_version=1,
        )
        assert proof.proof_completeness == ProofCompleteness.COMPLETE
        assert proof.proof_validity == ProofValidity.VALID
        assert proof.may_proceed_to_execution()

    def test_incomplete_proof_when_identity_insufficient(self, assembler, validator, resolver, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        validation = validator.validate(kernel_store.get_current("FC-001"), successor, result.transformation)
        # Force insufficient identity
        identity_result = IdentityResolutionResult(
            identity=None, confidence=0.2, evidence_level="INSUFFICIENT",
            fail_closed=True, failure_reason="test",
        )
        proof = assembler.assemble_pre_execution(
            delta=result.transformation, identity_result=identity_result,
            validation=validation, predecessor_version=0, successor_version=1,
        )
        assert proof.proof_completeness == ProofCompleteness.INCOMPLETE

    def test_invalid_proof_when_conservation_fails(self, assembler, validator, resolver, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        successor.operator = ">="  # corrupt
        validation = validator.validate(kernel_store.get_current("FC-001"), successor, result.transformation)
        identity_result = resolver.resolve(
            section_ref="7.10", alias_match="Total Leverage Ratio",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        proof = assembler.assemble_pre_execution(
            delta=result.transformation, identity_result=identity_result,
            validation=validation, predecessor_version=0, successor_version=1,
        )
        assert proof.proof_validity == ProofValidity.INVALID

    def test_post_execution_update(self, assembler, validator, resolver, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        validation = validator.validate(kernel_store.get_current("FC-001"), successor, result.transformation)
        identity_result = resolver.resolve(
            section_ref="7.10", alias_match="Total Leverage Ratio",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        proof = assembler.assemble_pre_execution(
            delta=result.transformation, identity_result=identity_result,
            validation=validation, predecessor_version=0, successor_version=1,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE", state_changed=True)
        proof = assembler.update_post_execution(proof, exec_result, "EDG-001")
        assert proof.execution_result.applied is True
        assert proof.lineage_reference == "EDG-001"


# ---------------------------------------------------------------------------
# Authority gate tests
# ---------------------------------------------------------------------------


class TestAuthorityGate:
    def test_grant_authority_when_all_conditions_met(self, gate, assembler, validator, resolver, kernel_store, engine):
        ev = make_evidence()
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        validation = validator.validate(kernel_store.get_current("FC-001"), successor, result.transformation)
        identity_result = resolver.resolve(
            section_ref="7.10", alias_match="Total Leverage Ratio",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        proof = assembler.assemble_pre_execution(
            delta=result.transformation, identity_result=identity_result,
            validation=validation, predecessor_version=0, successor_version=1,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE", state_changed=True)
        gate_result = gate.evaluate(exec_result, proof, inherited_unresolved=0, lineage_valid=True)
        assert gate_result.decision == AuthorityDecision.AUTHORITY_GRANTED

    def test_block_when_proof_invalid(self, gate):
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.COMPLETE,
            proof_validity=ProofValidity.INVALID,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE")
        gate_result = gate.evaluate(exec_result, proof)
        assert gate_result.decision == AuthorityDecision.AUTHORITY_BLOCKED

    def test_block_when_proof_incomplete(self, gate):
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.INCOMPLETE,
            proof_validity=ProofValidity.VALID,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE")
        gate_result = gate.evaluate(exec_result, proof)
        assert gate_result.decision == AuthorityDecision.AUTHORITY_BLOCKED

    def test_block_when_unresolved(self, gate):
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.COMPLETE,
            proof_validity=ProofValidity.VALID,
        )
        exec_result = ExecutionResultSummary(applied=False, status="UNRESOLVED")
        gate_result = gate.evaluate(exec_result, proof)
        assert gate_result.decision == AuthorityDecision.UNRESOLVED

    def test_block_when_partial(self, gate):
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.COMPLETE,
            proof_validity=ProofValidity.VALID,
        )
        exec_result = ExecutionResultSummary(applied=True, status="PARTIAL")
        gate_result = gate.evaluate(exec_result, proof)
        assert gate_result.decision == AuthorityDecision.PARTIAL

    def test_block_when_inherited_unresolved(self, gate):
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.COMPLETE,
            proof_validity=ProofValidity.VALID,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE")
        gate_result = gate.evaluate(exec_result, proof, inherited_unresolved=1, lineage_valid=True)
        assert gate_result.decision == AuthorityDecision.AUTHORITY_BLOCKED

    def test_validation_required_when_indeterminate(self, gate):
        from upsilon.models import CheckResult
        passing_checks = ConservationChecks(
            identity_persistence=CheckResult(invariant_name="identity_persistence", passed=True),
        )
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.COMPLETE,
            proof_validity=ProofValidity.INDETERMINATE,
            conservation_checks=passing_checks,
            evidence_status=EvidenceStatus.SUFFICIENT,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE")
        gate_result = gate.evaluate(exec_result, proof, lineage_valid=True)
        assert gate_result.decision == AuthorityDecision.VALIDATION_REQUIRED

    def test_validation_required_when_high_uncertainty(self, gate):
        from upsilon.models import CheckResult
        passing_checks = ConservationChecks(
            identity_persistence=CheckResult(invariant_name="identity_persistence", passed=True),
        )
        proof = SemanticTransformationProof(
            proof_id="PRF-001", agreement_id="AGR-001", commitment_id="FC-001",
            proof_completeness=ProofCompleteness.COMPLETE,
            proof_validity=ProofValidity.VALID,
            uncertainty_status=UncertaintyStatus.HIGH,
            conservation_checks=passing_checks,
            evidence_status=EvidenceStatus.SUFFICIENT,
        )
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE")
        gate_result = gate.evaluate(exec_result, proof, lineage_valid=True)
        assert gate_result.decision == AuthorityDecision.VALIDATION_REQUIRED


# ---------------------------------------------------------------------------
# Lineage graph tests
# ---------------------------------------------------------------------------


class TestCommitmentLineageGraph:
    def test_add_and_get_edge(self):
        graph = CommitmentLineageGraph("AGR-001")
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            affected_fields=["threshold"],
            old_values={"threshold": 4.0},
            new_values={"threshold": 3.75},
        )
        graph.add_edge(edge)
        assert graph.get_edge("EDG-001") is not None

    def test_append_only_rejects_duplicate(self):
        graph = CommitmentLineageGraph("AGR-001")
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
        )
        graph.add_edge(edge)
        with pytest.raises(ValueError, match="append-only"):
            graph.add_edge(edge)

    def test_validate_edge(self):
        graph = CommitmentLineageGraph("AGR-001")
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
        )
        graph.add_edge(edge)
        graph.validate_edge("EDG-001")
        assert edge.is_validated

    def test_cannot_validate_rejected_edge(self):
        graph = CommitmentLineageGraph("AGR-001")
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
        )
        graph.add_edge(edge)
        graph.reject_edge("EDG-001")
        with pytest.raises(ValueError, match="Cannot validate rejected"):
            graph.validate_edge("EDG-001")

    def test_edges_for_commitment(self):
        graph = CommitmentLineageGraph("AGR-001")
        for i in range(3):
            graph.add_edge(LineageEdge(
                edge_id=f"EDG-{i:03d}",
                predecessor_commitment_id="FC-001",
                successor_commitment_id="FC-001",
                amendment_id=f"AMN-{i}",
                authority_source=f"Amendment {i}",
                transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            ))
        edges = graph.edges_for_commitment("FC-001")
        assert len(edges) == 3

    def test_trace_to_origin_identity_preserving(self):
        """Trace must walk all edges in reverse order for identity-preserving chains."""
        graph = CommitmentLineageGraph("AGR-001")
        for i in range(3):
            graph.add_edge(LineageEdge(
                edge_id=f"EDG-{i:03d}",
                predecessor_commitment_id="FC-001",
                successor_commitment_id="FC-001",
                amendment_id=f"AMN-{i}",
                authority_source=f"Amendment {i}",
                transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            ))
        chain = graph.trace_to_origin("FC-001")
        # Must return ALL 3 edges, most-recent-first
        assert len(chain) == 3
        assert chain[0].edge_id == "EDG-002"
        assert chain[1].edge_id == "EDG-001"
        assert chain[2].edge_id == "EDG-000"

    def test_trace_to_origin_identity_changing(self):
        """Trace must follow predecessor across identity-changing edges."""
        graph = CommitmentLineageGraph("AGR-001")
        # FC-001 origin edge
        graph.add_edge(LineageEdge(
            edge_id="EDG-000",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-0",
            authority_source="Amendment 0",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
        ))
        # FC-002 created from FC-001
        graph.add_edge(LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-002",
            amendment_id="AMN-1",
            authority_source="Amendment 1",
            transformation_type=TransformationFamily.CREATE,
        ))
        chain = graph.trace_to_origin("FC-002")
        assert len(chain) == 2
        assert chain[0].edge_id == "EDG-001"
        assert chain[1].edge_id == "EDG-000"

    def test_is_reachable_from_origin_identity_preserving(self):
        graph = CommitmentLineageGraph("AGR-001")
        for i in range(3):
            graph.add_edge(LineageEdge(
                edge_id=f"EDG-{i:03d}",
                predecessor_commitment_id="FC-001",
                successor_commitment_id="FC-001",
                amendment_id=f"AMN-{i}",
                authority_source=f"Amendment {i}",
                transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            ))
        assert graph.is_reachable_from_origin("FC-001")

    def test_is_reachable_from_origin_broken_chain(self):
        """Identity-changing edge whose predecessor has no edges is NOT reachable."""
        graph = CommitmentLineageGraph("AGR-001")
        graph.add_edge(LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-999",  # never established
            successor_commitment_id="FC-002",
            amendment_id="AMN-1",
            authority_source="Amendment 1",
            transformation_type=TransformationFamily.CREATE,
        ))
        assert not graph.is_reachable_from_origin("FC-002")

    def test_is_reachable_from_origin_empty(self):
        graph = CommitmentLineageGraph("AGR-001")
        assert not graph.is_reachable_from_origin("FC-001")

    def test_identity_preserving_edge(self):
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
        )
        assert edge.is_identity_preserving

    def test_identity_changing_edge(self):
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-002",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3",
            transformation_type=TransformationFamily.CREATE,
        )
        assert not edge.is_identity_preserving


# ---------------------------------------------------------------------------
# Lineage queries tests
# ---------------------------------------------------------------------------


class TestLineageQueries:
    def test_history(self):
        graph = CommitmentLineageGraph("AGR-001")
        for i in range(3):
            graph.add_edge(LineageEdge(
                edge_id=f"EDG-{i:03d}",
                predecessor_commitment_id="FC-001",
                successor_commitment_id="FC-001",
                amendment_id=f"AMN-{i}",
                authority_source=f"Amendment {i}",
                transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
                affected_fields=["threshold"],
                old_values={"threshold": 4.0 - i * 0.25},
                new_values={"threshold": 3.75 - i * 0.25},
            ))
        queries = LineageQueries(graph)
        history = queries.history("FC-001")
        assert len(history) == 3

    def test_amendments_affecting(self):
        graph = CommitmentLineageGraph("AGR-001")
        for i in range(3):
            graph.add_edge(LineageEdge(
                edge_id=f"EDG-{i:03d}",
                predecessor_commitment_id="FC-001",
                successor_commitment_id="FC-001",
                amendment_id=f"AMN-{i}",
                authority_source=f"Amendment {i}",
                transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            ))
        queries = LineageQueries(graph)
        amendments = queries.amendments_affecting("FC-001")
        assert len(amendments) == 3

    def test_affected_fields_history(self):
        graph = CommitmentLineageGraph("AGR-001")
        graph.add_edge(LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-001",
            authority_source="Amendment 1",
            transformation_type=TransformationFamily.SCALAR_REPLACEMENT,
            affected_fields=["threshold"],
            old_values={"threshold": 4.0},
            new_values={"threshold": 3.75},
        ))
        queries = LineageQueries(graph)
        history = queries.affected_fields_history("FC-001")
        assert "threshold" in history
        assert len(history["threshold"]) == 1


# ---------------------------------------------------------------------------
# End-to-end pipeline test
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    def test_full_authorized_transformation_pipeline(
        self, engine, validator, assembler, gate, resolver, kernel_store
    ):
        """Full pipeline: evidence → engine → apply → validate → proof → authority → lineage → advance."""
        ev = make_evidence()
        auth = make_authority(kernel_store)

        # 1. Authorize
        result = engine.authorize(ev, auth)
        assert result.authorized

        # 2. Apply
        successor = apply_transformation(kernel_store.get_current("FC-001"), result.transformation)
        assert successor.threshold == 3.75

        # 3. Validate
        validation = validator.validate(
            kernel_store.get_current("FC-001"), successor, result.transformation
        )
        assert validation.passed

        # 4. Proof
        identity_result = resolver.resolve(
            section_ref="7.10", alias_match="Total Leverage Ratio",
            predecessor_commitment_ids=["FC-001"],
            canonical_key_hint="financial_covenant.leverage_ratio",
        )
        proof = assembler.assemble_pre_execution(
            delta=result.transformation, identity_result=identity_result,
            validation=validation, predecessor_version=0, successor_version=1,
        )
        assert proof.is_complete_and_valid()

        # 5. Authority
        exec_result = ExecutionResultSummary(applied=True, status="COMPLETE", state_changed=True)
        gate_result = gate.evaluate(exec_result, proof, inherited_unresolved=0, lineage_valid=True)
        assert gate_result.is_authoritative

        # 6. Lineage
        graph = CommitmentLineageGraph("AGR-001")
        edge = LineageEdge(
            edge_id="EDG-001",
            predecessor_commitment_id="FC-001",
            successor_commitment_id="FC-001",
            amendment_id="AMN-003",
            authority_source="Amendment No. 3, Section 2",
            transformation_type=result.transformation.transformation_type,
            affected_fields=result.transformation.affected_field_names,
            old_values=result.transformation.old_values(),
            new_values=result.transformation.new_values(),
            proof_id=proof.proof_id,
        )
        graph.add_edge(edge)
        graph.validate_edge(edge.edge_id)
        assert edge.is_validated

        # 7. Advance kernel
        proof = assembler.update_post_execution(proof, exec_result, edge.edge_id)
        kernel_store.advance("FC-001", successor, proof.proof_id)
        assert kernel_store.get_current("FC-001").threshold == 3.75
        assert len(kernel_store.get_version_history("FC-001")) == 2

    def test_incorrect_old_value_blocked_end_to_end(
        self, engine, validator, assembler, gate, resolver, kernel_store
    ):
        """The HELD-017 / AMERESCO pattern: wrong old value must be blocked."""
        ev = make_evidence(declared_old_value=3.5)  # wrong: predecessor has 4.0
        auth = make_authority(kernel_store)
        result = engine.authorize(ev, auth)
        assert result.rejected
        assert result.rejection_step == "old_value_consistency"
        # Never reaches conservation validation, proof, or authority

    def test_insufficient_identity_blocked_end_to_end(
        self, engine, validator, assembler, gate, resolver, kernel_store
    ):
        """The STUDY-016 pattern: no section ref, no predecessor → fail closed."""
        ev = make_evidence(section_ref=None, alias_match=None)
        auth = make_authority(kernel_store, commitment_ids=[])
        result = engine.authorize(ev, auth)
        assert result.rejected
        assert result.rejection_step == "target_identity"
