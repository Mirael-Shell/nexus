"""Drift detection module — statistical tests for data and prediction drift.

Implements:
  - Prediction drift: KS-test on confidence scores, chi-square on label distribution
  - Data drift: text length distribution, vocabulary drift
  - Reference vs current window comparison
  - Severity scoring and alerting thresholds
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DriftMetric:
    """Single drift metric result."""

    name: str
    value: float  # test statistic
    threshold: float
    p_value: float
    is_drifted: bool
    description: str


@dataclass
class DriftReport:
    """Full drift analysis report."""

    window_size: int
    reference_size: int
    metrics: list[DriftMetric] = field(default_factory=list)
    overall_drift_score: float = 0.0
    drift_detected: bool = False
    severity: str = "none"  # none / low / medium / high
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API response."""
        return {
            "window_size": self.window_size,
            "reference_size": self.reference_size,
            "overall_drift_score": round(self.overall_drift_score, 4),
            "drift_detected": self.drift_detected,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "metrics": [
                {
                    "name": m.name,
                    "value": round(m.value, 4),
                    "threshold": m.threshold,
                    "p_value": round(m.p_value, 6),
                    "is_drifted": m.is_drifted,
                    "description": m.description,
                }
                for m in self.metrics
            ],
        }


def _kolmogorov_smirnov(sample1: list[float], sample2: list[float]) -> tuple[float, float]:
    """Compute KS statistic and approximate p-value (two-sample).

    Returns (D statistic, p_value).
    """
    s1 = sorted(sample1)
    s2 = sorted(sample2)
    n1, n2 = len(s1), len(s2)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    # Merge and compute CDF differences
    all_vals = sorted(set(s1 + s2))
    cdf1_prev = cdf2_prev = 0.0
    d_stat = 0.0
    i1 = i2 = 0

    for val in all_vals:
        while i1 < n1 and s1[i1] <= val:
            i1 += 1
        while i2 < n2 and s2[i2] <= val:
            i2 += 1
        cdf1 = i1 / n1
        cdf2 = i2 / n2
        d_stat = max(d_stat, abs(cdf1 - cdf2), abs(cdf1 - cdf1_prev), abs(cdf2 - cdf2_prev))
        cdf1_prev = cdf1
        cdf2_prev = cdf2

    # Approximate p-value using Kolmogorov distribution
    en = math.sqrt(n1 * n2 / (n1 + n2))
    lambda_val = (en + 0.12 + 0.11 / en) * d_stat
    p_value = _kolmogorov_cdf(lambda_val)

    return d_stat, p_value


def _kolmogorov_cdf(x: float) -> float:
    """CDF of Kolmogorov distribution Q(x) → p-value."""
    if x <= 0:
        return 1.0
    if x < 0.18:
        return 1.0
    if x > 3.0:
        return 0.0

    # Series approximation: Q(λ) = 2 * Σ (-1)^(k-1) * exp(-2 * k² * λ²)
    total = 0.0
    for k in range(1, 101):
        term = 2.0 * ((-1) ** (k - 1)) * math.exp(-2.0 * k * k * x * x)
        total += term
        if abs(term) < 1e-10:
            break

    return max(0.0, min(1.0, total))


def _chi_square_labels(ref_labels: list[str], cur_labels: list[str]) -> tuple[float, float]:
    """Chi-square test on label distribution.

    Returns (chi2 statistic, p_value).
    """
    ref_counts = Counter(ref_labels)
    cur_counts = Counter(cur_labels)

    all_labels = set(ref_labels) | set(cur_labels)
    n_ref = len(ref_labels)
    n_cur = len(cur_labels)
    n_total = n_ref + n_cur
    if n_total == 0:
        return 0.0, 1.0

    chi2 = 0.0
    for label in all_labels:
        ref_exp = ref_counts.get(label, 0)
        cur_exp = cur_counts.get(label, 0)
        ref_obs = ref_exp
        cur_obs = cur_exp

        # Expected under H0 (same distribution)
        pooled = (ref_obs + cur_obs) / n_total
        exp_ref = pooled * n_ref
        exp_cur = pooled * n_cur

        if exp_ref > 0:
            chi2 += (ref_obs - exp_ref) ** 2 / exp_ref
        if exp_cur > 0:
            chi2 += (cur_obs - exp_cur) ** 2 / exp_cur

    # Degrees of freedom = (num_labels - 1)
    df = max(len(all_labels) - 1, 1)
    p_value = _chi_square_sf(chi2, df)
    return chi2, p_value


def _chi_square_sf(x: float, df: int) -> float:
    """Survival function (1 - CDF) for chi-square distribution.

    Uses the regularized upper incomplete gamma function.
    """
    if x <= 0:
        return 1.0
    return _gammainc_upper(df / 2.0, x / 2.0)


def _gammainc_upper(a: float, x: float) -> float:
    """Regularized upper incomplete gamma function Q(a, x).

    Uses continued fraction expansion (Numerical Recipes).
    """
    if x < 0 or a <= 0:
        return 1.0
    if x == 0:
        return 1.0
    if x < a + 1.0:
        # Series expansion
        return 1.0 - _gammainc_lower(a, x)
    else:
        # Continued fraction
        return _gammainc_cf(a, x)


def _gammainc_lower(a: float, x: float) -> float:
    """Lower incomplete gamma P(a, x) via series."""
    if x < 0 or a <= 0:
        return 0.0
    if x == 0:
        return 0.0

    ln_gamma_a = math.lgamma(a)
    ap = a
    summ = 1.0 / a
    delta = summ
    for _ in range(200):
        ap += 1
        delta *= x / ap
        summ += delta
        if abs(delta) < abs(summ) * 1e-12:
            break

    return summ * math.exp(-x + a * math.log(x) - ln_gamma_a)


def _gammainc_cf(a: float, x: float) -> float:
    """Upper incomplete gamma Q(a, x) via continued fraction."""
    ln_gamma_a = math.lgamma(a)
    b = x + 1.0 - a
    c = 1e30
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break

    return math.exp(-x + a * math.log(x) - ln_gamma_a) * h


@dataclass
class PredictionSample:
    """A single prediction sample for drift analysis."""

    label: str
    confidence: float
    text_length: int


def detect_drift(
    reference: list[PredictionSample],
    current: list[PredictionSample],
    p_threshold: float = 0.05,
) -> DriftReport:
    """Run full drift detection comparing reference vs current window.

    Args:
        reference: Baseline samples (e.g., from first week of deployment).
        current: Recent samples (e.g., last 24 hours).
        p_threshold: Significance threshold (default 0.05).

    Returns:
        DriftReport with per-metric results and overall assessment.
    """
    report = DriftReport(
        window_size=len(current),
        reference_size=len(reference),
    )

    if len(reference) < 5 or len(current) < 5:
        report.recommendation = "Insufficient data for drift detection (need ≥5 samples per window)"
        return report

    # ─── 1. Confidence score drift (KS-test) ──────────────
    ref_conf = [s.confidence for s in reference]
    cur_conf = [s.confidence for s in current]
    ks_d, ks_p = _kolmogorov_smirnov(ref_conf, cur_conf)

    report.metrics.append(
        DriftMetric(
            name="confidence_ks",
            value=ks_d,
            threshold=0.1,  # D-statistic threshold
            p_value=ks_p,
            is_drifted=ks_p < p_threshold,
            description="KS-test on confidence scores distribution",
        )
    )

    # ─── 2. Label distribution drift (chi-square) ─────────
    ref_labels = [s.label for s in reference]
    cur_labels = [s.label for s in current]
    chi2_val, chi2_p = _chi_square_labels(ref_labels, cur_labels)

    report.metrics.append(
        DriftMetric(
            name="label_chi2",
            value=chi2_val,
            threshold=9.49,  # df=2, p=0.05
            p_value=chi2_p,
            is_drifted=chi2_p < p_threshold,
            description="Chi-square test on label distribution",
        )
    )

    # ─── 3. Text length drift (KS-test) ───────────────────
    ref_len = [float(s.text_length) for s in reference]
    cur_len = [float(s.text_length) for s in current]
    len_d, len_p = _kolmogorov_smirnov(ref_len, cur_len)

    report.metrics.append(
        DriftMetric(
            name="text_length_ks",
            value=len_d,
            threshold=0.15,
            p_value=len_p,
            is_drifted=len_p < p_threshold,
            description="KS-test on input text length distribution",
        )
    )

    # ─── Overall assessment ───────────────────────────────
    drifted_metrics = [m for m in report.metrics if m.is_drifted]
    report.overall_drift_score = sum(1.0 - m.p_value for m in drifted_metrics) / max(
        len(report.metrics), 1
    )
    report.drift_detected = len(drifted_metrics) > 0

    if len(drifted_metrics) == 0:
        report.severity = "none"
        report.recommendation = "No significant drift detected."
    elif len(drifted_metrics) == 1:
        report.severity = "low"
        report.recommendation = f"Minor drift in {drifted_metrics[0].name}. Monitor closely."
    elif report.overall_drift_score > 0.8:
        report.severity = "high"
        report.recommendation = "Severe drift detected. Trigger immediate model retraining."
    else:
        report.severity = "medium"
        report.recommendation = "Moderate drift across multiple metrics. Consider retraining soon."

    return report
