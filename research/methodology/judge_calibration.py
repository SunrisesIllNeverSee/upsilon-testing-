"""LLM-as-judge calibration (HRN-009 evaluation).

HRN-009: "Calibrate judge scores against human labels. Track judge-human
agreement. Avoid treating an unvalidated judge as ground truth."

An LLM-as-judge produces scores for evaluation outputs. Without
calibration, those scores are unvalidated — the judge may be
systematically biased (too lenient, too harsh, or inconsistent). This
module provides:

    - JudgeCalibrationSample: a single (judge_score, human_score) pair
    - JudgeCalibrationReport: aggregate calibration metrics
    - compute_judge_calibration: computes agreement, bias, and reliability
    - CalibrationGate: a gate that blocks deployment of a judge until
      calibration meets a minimum threshold

The key insight is that a judge is NOT ground truth. A judge is a
measurement instrument that must itself be validated against human
labels before its scores can be trusted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class JudgeCalibrationSample:
    """A single calibration sample: judge score vs human score.

    Both scores are on the same scale (typically 0.0–1.0 or 0–5).
    The human score is the ground truth label from a human annotator.
    The judge score is what the LLM-as-judge produced for the same item.
    """
    item_id: str
    judge_score: float
    human_score: float
    judge_rationale: str = ""  # optional: the judge's stated reasoning

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "judge_score": self.judge_score,
            "human_score": self.human_score,
            "judge_rationale": self.judge_rationale,
        }


@dataclass
class JudgeCalibrationReport:
    """Aggregate calibration metrics for an LLM-as-judge.

    Metrics:
        - mean_bias: average (judge - human) — positive = judge too lenient
        - mean_absolute_error: average |judge - human|
        - agreement_rate: fraction of samples within tolerance
        - pearson_correlation: correlation between judge and human scores
        - sample_count: number of calibration samples
        - calibrated: whether the judge meets the calibration threshold
    """
    mean_bias: float = 0.0
    mean_absolute_error: float = 0.0
    agreement_rate: float = 0.0
    pearson_correlation: float = 0.0
    sample_count: int = 0
    tolerance: float = 0.1
    calibrated: bool = False
    samples: List[JudgeCalibrationSample] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mean_bias": round(self.mean_bias, 4),
            "mean_absolute_error": round(self.mean_absolute_error, 4),
            "agreement_rate": round(self.agreement_rate, 4),
            "pearson_correlation": round(self.pearson_correlation, 4),
            "sample_count": self.sample_count,
            "tolerance": self.tolerance,
            "calibrated": self.calibrated,
            "samples": [s.to_dict() for s in self.samples],
        }


def _pearson(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient. Returns 0.0 if undefined."""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = sum((xi - mean_x) ** 2 for xi in x)
    den_y = sum((yi - mean_y) ** 2 for yi in y)
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / ((den_x * den_y) ** 0.5)


def compute_judge_calibration(
    samples: List[JudgeCalibrationSample],
    tolerance: float = 0.1,
    min_samples: int = 10,
    min_agreement: float = 0.8,
    min_correlation: float = 0.7,
) -> JudgeCalibrationReport:
    """Compute calibration metrics for an LLM-as-judge.

    Args:
        samples: calibration samples (judge_score vs human_score pairs)
        tolerance: max |judge - human| to count as "agreement"
        min_samples: minimum samples for calibration to be valid
        min_agreement: minimum agreement_rate for calibration to pass
        min_correlation: minimum pearson_correlation for calibration to pass

    Returns:
        JudgeCalibrationReport with metrics and calibrated flag.

    A judge is "calibrated" if:
        - sample_count >= min_samples (enough data to trust the metrics)
        - agreement_rate >= min_agreement (judge agrees with human often enough)
        - pearson_correlation >= min_correlation (judge tracks human ranking)
    """
    if not samples:
        return JudgeCalibrationReport(
            tolerance=tolerance,
            sample_count=0,
            calibrated=False,
        )

    judge_scores = [s.judge_score for s in samples]
    human_scores = [s.human_score for s in samples]
    diffs = [j - h for j, h in zip(judge_scores, human_scores)]
    abs_diffs = [abs(d) for d in diffs]

    mean_bias = sum(diffs) / len(diffs)
    mae = sum(abs_diffs) / len(abs_diffs)
    agreement = sum(1 for d in abs_diffs if d <= tolerance) / len(abs_diffs)
    corr = _pearson(judge_scores, human_scores)

    calibrated = (
        len(samples) >= min_samples
        and agreement >= min_agreement
        and corr >= min_correlation
    )

    return JudgeCalibrationReport(
        mean_bias=mean_bias,
        mean_absolute_error=mae,
        agreement_rate=agreement,
        pearson_correlation=corr,
        sample_count=len(samples),
        tolerance=tolerance,
        calibrated=calibrated,
        samples=list(samples),
    )


class UncalibratedJudgeError(Exception):
    """Raised when an uncalibrated judge is used as ground truth (HRN-009).

    A judge that has not been calibrated against human labels must not be
    treated as ground truth. The orchestrator catches this to route the
    judge's scores through a "validation required" path instead of
    accepting them directly.
    """
    pass


class CalibrationGate:
    """Gate that blocks an uncalibrated judge from being used as ground truth.

    HRN-009: "Avoid treating an unvalidated judge as ground truth."

    The gate holds a calibration report. If the report says the judge is
    calibrated, the gate allows the judge's scores to be used directly.
    If not, the gate raises UncalibratedJudgeError — the orchestrator
    must route the scores through human validation instead.
    """

    def __init__(
        self,
        min_samples: int = 10,
        min_agreement: float = 0.8,
        min_correlation: float = 0.7,
        tolerance: float = 0.1,
    ) -> None:
        self.min_samples = min_samples
        self.min_agreement = min_agreement
        self.min_correlation = min_correlation
        self.tolerance = tolerance
        self._report: Optional[JudgeCalibrationReport] = None

    def calibrate(self, samples: List[JudgeCalibrationSample]) -> JudgeCalibrationReport:
        """Compute and store the calibration report for this judge."""
        self._report = compute_judge_calibration(
            samples,
            tolerance=self.tolerance,
            min_samples=self.min_samples,
            min_agreement=self.min_agreement,
            min_correlation=self.min_correlation,
        )
        return self._report

    @property
    def report(self) -> Optional[JudgeCalibrationReport]:
        return self._report

    @property
    def is_calibrated(self) -> bool:
        return self._report is not None and self._report.calibrated

    def check(self) -> JudgeCalibrationReport:
        """Check whether the judge is calibrated. Raises if not.

        Returns the calibration report if calibrated.
        Raises UncalibratedJudgeError if the judge has not been calibrated
        or if calibration failed (insufficient samples, low agreement, etc.).
        """
        if self._report is None:
            raise UncalibratedJudgeError(
                "Judge has not been calibrated. Run calibrate() with human "
                "labels before using judge scores as ground truth (HRN-009)."
            )
        if not self._report.calibrated:
            reasons = []
            if self._report.sample_count < self.min_samples:
                reasons.append(
                    f"insufficient samples ({self._report.sample_count} < {self.min_samples})"
                )
            if self._report.agreement_rate < self.min_agreement:
                reasons.append(
                    f"agreement rate {self._report.agreement_rate:.1%} < {self.min_agreement:.1%}"
                )
            if self._report.pearson_correlation < self.min_correlation:
                reasons.append(
                    f"correlation {self._report.pearson_correlation:.3f} < {self.min_correlation:.3f}"
                )
            raise UncalibratedJudgeError(
                f"Judge calibration failed: {'; '.join(reasons)}. "
                f"Do not use judge scores as ground truth without human validation (HRN-009)."
            )
        return self._report
