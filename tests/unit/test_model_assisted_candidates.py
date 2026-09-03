"""Tests for the model-assisted candidate interface (Step 21 / Section D)."""
from __future__ import annotations

from datetime import datetime

import pytest

from research.model_assisted_candidates import (
    MODEL_CANDIDATE_TAG,
    REJECTED_TAG,
    VALIDATED_TAG,
    DeterministicCandidateGenerator,
    LLMCandidateGenerator,
    ValidationResult,
    validate_candidate,
    resolve_with_model_assistance,
)
from upsilon.models.legacy_models import (
    AmendmentInstruction,
    CommitmentState,
    InstructionProvenance,
    InstructionType,
)
from upsilon.transformations.semantic_mapper import StructuredMutation


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


class TestValidators:
    def _make_state(self) -> dict[str, CommitmentState]:
        return {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }

    def test_valid_candidate_passes(self):
        state = self._make_state()
        candidate = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            operation=InstructionType.REPLACE_VALUE,
            new_value=3.5,
            unit="ratio",
            source_span="not to exceed 3.50 to 1.00",
        )
        result = validate_candidate(candidate, state)
        assert result.passed
        assert result.provenance_tag == VALIDATED_TAG

    def test_invalid_target_rejected(self):
        state = self._make_state()
        candidate = StructuredMutation(
            commitment_id="facility.unknown",
            field="threshold",
            operation=InstructionType.REPLACE_VALUE,
            new_value=3.5,
            source_span="some text",
        )
        result = validate_candidate(candidate, state)
        assert not result.passed
        assert result.provenance_tag == REJECTED_TAG
        assert any("target" in f[0] for f in result.failures)

    def test_replace_value_on_list_field_rejected(self):
        state = self._make_state()
        candidate = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="exceptions",
            operation=InstructionType.REPLACE_VALUE,
            new_value="some exception",
            source_span="some text",
        )
        result = validate_candidate(candidate, state)
        assert not result.passed
        assert any("list_field" in f[1] for f in result.failures)

    def test_no_new_value_rejected(self):
        state = self._make_state()
        candidate = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            operation=InstructionType.REPLACE_VALUE,
            new_value=None,
            source_span="some text",
        )
        result = validate_candidate(candidate, state)
        assert not result.passed

    def test_no_source_evidence_rejected(self):
        state = self._make_state()
        candidate = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            operation=InstructionType.REPLACE_VALUE,
            new_value=3.5,
            source_span="",
        )
        result = validate_candidate(candidate, state)
        assert not result.passed
        assert any("source" in f[0] for f in result.failures)

    def test_old_value_mismatch_rejected(self):
        state = self._make_state()
        candidate = StructuredMutation(
            commitment_id="financial_covenant.leverage_ratio",
            field="threshold",
            operation=InstructionType.REPLACE_VALUE,
            old_value=99.0,  # wrong — actual is 4.0
            new_value=3.5,
            source_span="not to exceed 3.50 to 1.00",
        )
        result = validate_candidate(candidate, state)
        assert not result.passed
        assert any("old_value" in f[1] for f in result.failures)


# ---------------------------------------------------------------------------
# Candidate generator tests
# ---------------------------------------------------------------------------


class TestCandidateGenerator:
    def test_deterministic_generator(self):
        gen = DeterministicCandidateGenerator()
        state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }
        candidate = gen.generate_candidate(
            source_span="Maximum Total Leverage Ratio shall not exceed 3.50 to 1.00",
            surrounding_context="...",
            current_state=state,
            section_ref="Section 7.10",
            instruction_type=InstructionType.RESTATE_SECTION,
        )
        assert candidate is not None
        assert candidate.commitment_id == "financial_covenant.leverage_ratio"
        assert candidate.new_value == 3.5

    def test_deterministic_generator_no_match(self):
        gen = DeterministicCandidateGenerator()
        state = {}
        candidate = gen.generate_candidate(
            source_span="some random text",
            surrounding_context="...",
            current_state=state,
            section_ref="Section 99.99",
            instruction_type=InstructionType.RESTATE_SECTION,
        )
        assert candidate is None


# ---------------------------------------------------------------------------
# Model-assisted resolver tests
# ---------------------------------------------------------------------------


class TestModelAssistedResolver:
    def test_resolve_with_valid_candidate(self):
        state = {
            "financial_covenant.leverage_ratio": CommitmentState(
                canonical_key="financial_covenant.leverage_ratio",
                commitment_type="financial_covenant",
                threshold=4.0,
                unit="ratio",
            ),
        }
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_section_ref="Section 7.10",
            source_text="Maximum Total Leverage Ratio shall not exceed 3.50 to 1.00",
            provenance=InstructionProvenance.PARSER,
        )
        result = resolve_with_model_assistance(ins, state)
        assert len(result.mutations) == 1
        mut = result.mutations[0]
        assert MODEL_CANDIDATE_TAG in (mut.citation_document or "")
        assert VALIDATED_TAG in (mut.citation_document or "")

    def test_resolve_with_invalid_candidate(self):
        state = {}
        ins = AmendmentInstruction(
            order=1,
            instruction_type=InstructionType.RESTATE_SECTION,
            target_section_ref="Section 99.99",
            source_text="some random text",
            provenance=InstructionProvenance.PARSER,
        )
        result = resolve_with_model_assistance(ins, state)
        assert len(result.unresolved) >= 1
        assert len(result.mutations) == 0
