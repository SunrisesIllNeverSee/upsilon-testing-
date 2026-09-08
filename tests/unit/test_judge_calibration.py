"""Tests for LLM-as-judge calibration (HRN-009 evaluation).

Verifies:
    - Calibration metrics are computed correctly
    - Bias, MAE, agreement rate, and correlation are correct
    - Uncalibrated judges raise UncalibratedJudgeError
    - CalibrationGate blocks uncalibrated judges
    - CalibrationGate allows calibrated judges
    - Insufficient samples fail calibration
    - Low agreement fails calibration
    - Low correlation fails calibration
"""
from __future__ import annotations

import pytest

from research.methodology.judge_calibration import (
    JudgeCalibrationSample,
    JudgeCalibrationReport,
    compute_judge_calibration,
    CalibrationGate,
    UncalibratedJudgeError,
)


def _sample(judge: float, human: float, item_id: str = "item") -> JudgeCalibrationSample:
    return JudgeCalibrationSample(
        item_id=item_id,
        judge_score=judge,
        human_score=human,
    )


class TestComputeCalibration:

    def test_perfect_agreement(self):
        """Judge matches human exactly → calibrated."""
        samples = [_sample(i / 10, i / 10, f"item_{i}") for i in range(10)]
        report = compute_judge_calibration(samples)
        assert report.mean_bias == 0.0
        assert report.mean_absolute_error == 0.0
        assert report.agreement_rate == 1.0
        assert report.pearson_correlation == 1.0
        assert report.calibrated

    def test_systematic_bias(self):
        """Judge consistently scores 0.2 higher than human."""
        samples = [_sample(h + 0.2, h, f"item_{i}") for i, h in enumerate([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])]
        report = compute_judge_calibration(samples, tolerance=0.15)
        assert report.mean_bias == pytest.approx(0.2)
        assert report.mean_absolute_error == pytest.approx(0.2)
        # All diffs are 0.2 > tolerance 0.15 → 0% agreement
        # But with tolerance 0.25, all would agree
        assert report.agreement_rate < 0.5

    def test_insufficient_samples_not_calibrated(self):
        """Fewer than min_samples → not calibrated."""
        samples = [_sample(0.5, 0.5, f"item_{i}") for i in range(5)]
        report = compute_judge_calibration(samples, min_samples=10)
        assert not report.calibrated
        assert report.sample_count == 5

    def test_low_agreement_not_calibrated(self):
        """Low agreement rate → not calibrated."""
        # Judge and human disagree on most items
        samples = [
            _sample(0.9, 0.1, f"item_{i}") if i % 2 == 0
            else _sample(0.1, 0.9, f"item_{i}")
            for i in range(20)
        ]
        report = compute_judge_calibration(samples, min_agreement=0.8)
        assert not report.calibrated
        assert report.agreement_rate < 0.5

    def test_low_correlation_not_calibrated(self):
        """Low correlation → not calibrated."""
        # Judge scores are random relative to human scores
        samples = [
            _sample(0.1, 0.9, "a"),
            _sample(0.9, 0.1, "b"),
            _sample(0.2, 0.8, "c"),
            _sample(0.8, 0.2, "d"),
            _sample(0.3, 0.7, "e"),
            _sample(0.7, 0.3, "f"),
            _sample(0.4, 0.6, "g"),
            _sample(0.6, 0.4, "h"),
            _sample(0.5, 0.5, "i"),
            _sample(0.45, 0.55, "j"),
        ]
        report = compute_judge_calibration(samples, min_correlation=0.7)
        assert not report.calibrated
        assert report.pearson_correlation < 0.0  # negatively correlated

    def test_empty_samples(self):
        """Empty samples → not calibrated, zero metrics."""
        report = compute_judge_calibration([])
        assert not report.calibrated
        assert report.sample_count == 0

    def test_serialization(self):
        """Report serializes to dict correctly."""
        samples = [_sample(0.5, 0.5, f"item_{i}") for i in range(10)]
        report = compute_judge_calibration(samples)
        d = report.to_dict()
        assert "mean_bias" in d
        assert "mean_absolute_error" in d
        assert "agreement_rate" in d
        assert "pearson_correlation" in d
        assert "calibrated" in d
        assert d["sample_count"] == 10


class TestCalibrationGate:

    def test_uncalibrated_raises(self):
        """Gate with no calibration raises UncalibratedJudgeError."""
        gate = CalibrationGate()
        with pytest.raises(UncalibratedJudgeError, match="not been calibrated"):
            gate.check()

    def test_calibrated_passes(self):
        """Gate with sufficient calibration allows use."""
        gate = CalibrationGate(min_samples=5, min_agreement=0.8, min_correlation=0.7)
        samples = [_sample(i / 10, i / 10, f"item_{i}") for i in range(10)]
        report = gate.calibrate(samples)
        assert gate.is_calibrated
        result = gate.check()
        assert result.calibrated

    def test_insufficient_samples_blocked(self):
        """Gate blocks when samples are insufficient."""
        gate = CalibrationGate(min_samples=10)
        samples = [_sample(0.5, 0.5, f"item_{i}") for i in range(5)]
        gate.calibrate(samples)
        with pytest.raises(UncalibratedJudgeError, match="insufficient samples"):
            gate.check()

    def test_low_agreement_blocked(self):
        """Gate blocks when agreement is too low."""
        gate = CalibrationGate(min_samples=10, min_agreement=0.9)
        # Most items disagree
        samples = [
            _sample(0.9, 0.1, f"item_{i}") if i % 3 == 0
            else _sample(0.5, 0.5, f"item_{i}")
            for i in range(15)
        ]
        gate.calibrate(samples)
        with pytest.raises(UncalibratedJudgeError, match="agreement rate"):
            gate.check()

    def test_low_correlation_blocked(self):
        """Gate blocks when correlation is too low."""
        gate = CalibrationGate(min_samples=10, min_correlation=0.9)
        samples = [
            _sample(0.1, 0.9, "a"), _sample(0.9, 0.1, "b"),
            _sample(0.2, 0.8, "c"), _sample(0.8, 0.2, "d"),
            _sample(0.3, 0.7, "e"), _sample(0.7, 0.3, "f"),
            _sample(0.4, 0.6, "g"), _sample(0.6, 0.4, "h"),
            _sample(0.5, 0.5, "i"), _sample(0.45, 0.55, "j"),
        ]
        gate.calibrate(samples)
        with pytest.raises(UncalibratedJudgeError, match="correlation"):
            gate.check()

    def test_report_accessible_after_calibrate(self):
        """Report is accessible after calibration."""
        gate = CalibrationGate()
        samples = [_sample(0.5, 0.5, f"item_{i}") for i in range(10)]
        gate.calibrate(samples)
        assert gate.report is not None
        assert gate.report.sample_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
