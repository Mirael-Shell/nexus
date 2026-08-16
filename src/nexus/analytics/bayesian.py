"""Bayesian A/B testing analytics using Beta-Binomial conjugate model.

The Beta-Binomial model is the gold standard for conversion-rate experiments:

    Prior:       θ ~ Beta(α₀, β₀)         (uninformative: α₀=1, β₀=1)
    Likelihood:  k | θ ~ Binomial(n, θ)
    Posterior:   θ | k ~ Beta(α₀ + k, β₀ + n - k)

We compute:
  - Posterior means and credible intervals for each variant
  - P(treatment > control) via Monte Carlo sampling
  - Expected loss (regret of choosing the wrong variant)
  - A stopping recommendation based on expected loss threshold
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class VariantStats:
    """Statistics for a single variant (control or treatment)."""

    total: int
    successes: int  # thumbs-up count
    failures: int  # thumbs-down count

    @property
    def rate(self) -> float:
        """Observed success rate."""
        return self.successes / self.total if self.total > 0 else 0.0


@dataclass
class BayesianResult:
    """Full Bayesian analysis of an A/B experiment."""

    control_posterior_mean: float
    control_ci_low: float
    control_ci_high: float

    treatment_posterior_mean: float
    treatment_ci_low: float
    treatment_ci_high: float

    # P(treatment rate > control rate)
    prob_treatment_better: float

    # Expected loss if we choose each variant
    expected_loss_control: float
    expected_loss_treatment: float

    # Recommendation
    recommendation: str  # "control" / "treatment" / "inconclusive"
    should_stop: bool
    reason: str


def _beta_sample(alpha: float, beta: float, n: int = 50000) -> list[float]:
    """Sample from Beta(α, β) using numpy-free gamma-based approach.

    Uses the ratio of Gamma variables: if X ~ Gamma(α, 1) and Y ~ Gamma(β, 1),
    then X / (X + Y) ~ Beta(α, β).
    """
    samples = []
    for _ in range(n):
        x = _gamma_sample(alpha)
        y = _gamma_sample(beta)
        samples.append(x / (x + y) if (x + y) > 0 else 0.5)
    return samples


def _gamma_sample(shape: float) -> float:
    """Sample from Gamma(shape, 1) using Marsaglia-Tsang method."""
    if shape < 1.0:
        # Boost: Gamma(α) = Gamma(α+1) * U^(1/α)
        u = random.random()
        return _gamma_sample(shape + 1.0) * (u ** (1.0 / shape))

    d = shape - 0.333333333
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        x = random.gauss(0.0, 1.0)
        v = 1.0 + c * x
        if v <= 0.0:
            continue
        v = v * v * v
        u = random.random()
        if u < 1.0 - 0.0331 * x * x * x * x:
            return d * v
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Compute percentile from sorted list."""
    if not sorted_vals:
        return 0.0
    idx = int(len(sorted_vals) * p)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def analyze_experiment(
    control: VariantStats,
    treatment: VariantStats,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    ci_level: float = 0.95,
    loss_threshold: float = 0.001,
    min_samples: int = 30,
    n_samples: int = 50000,
) -> BayesianResult:
    """Run Bayesian A/B analysis.

    Args:
        control: Control variant stats.
        treatment: Treatment variant stats.
        prior_alpha: Beta prior α (uninformative = 1).
        prior_beta: Beta prior β (uninformative = 1).
        ci_level: Credible interval level (0.95 = 95%).
        loss_threshold: Max acceptable expected loss for stopping.
        min_samples: Minimum samples per variant before recommendation.
        n_samples: Monte Carlo samples for posterior estimation.

    Returns:
        BayesianResult with posteriors, probabilities, and recommendation.
    """
    # Posterior parameters: Beta(α₀ + k, β₀ + n - k)
    control_alpha = prior_alpha + control.successes
    control_beta = prior_beta + control.failures
    treatment_alpha = prior_alpha + treatment.successes
    treatment_beta = prior_beta + treatment.failures

    # Sample from posteriors
    control_samples = sorted(_beta_sample(control_alpha, control_beta, n_samples))
    treatment_samples = _beta_sample(treatment_alpha, treatment_beta, n_samples)

    # Posterior means
    control_mean = control_alpha / (control_alpha + control_beta)
    treatment_mean = treatment_alpha / (treatment_alpha + treatment_beta)

    # Credible intervals
    ci_low_p = (1.0 - ci_level) / 2.0
    ci_high_p = 1.0 - ci_low_p

    control_ci_low = _percentile(control_samples, ci_low_p)
    control_ci_high = _percentile(control_samples, ci_high_p)

    treatment_sorted = sorted(treatment_samples)
    treatment_ci_low = _percentile(treatment_sorted, ci_low_p)
    treatment_ci_high = _percentile(treatment_sorted, ci_high_p)

    # P(treatment > control)
    wins = sum(1 for t, c in zip(treatment_samples, control_samples, strict=False) if t > c)
    total_pairs = min(len(treatment_samples), len(control_samples))
    prob_better = wins / total_pairs if total_pairs > 0 else 0.5

    # Expected loss: if we choose X, the loss is max(0, other - X)
    # E[loss_control] = E[max(0, θ_treatment - θ_control)]
    # E[loss_treatment] = E[max(0, θ_control - θ_treatment)]
    loss_control_sum = 0.0
    loss_treatment_sum = 0.0
    for t, c in zip(treatment_samples, control_samples, strict=False):
        loss_control_sum += max(0.0, t - c)
        loss_treatment_sum += max(0.0, c - t)
    expected_loss_control = loss_control_sum / total_pairs if total_pairs > 0 else 0.0
    expected_loss_treatment = loss_treatment_sum / total_pairs if total_pairs > 0 else 0.0

    # Recommendation logic
    has_min_samples = control.total >= min_samples and treatment.total >= min_samples

    if not has_min_samples:
        recommendation = "inconclusive"
        should_stop = False
        reason = (
            f"Insufficient samples (control={control.total}, "
            f"treatment={treatment.total}, min={min_samples})"
        )
    elif expected_loss_treatment < loss_threshold:
        recommendation = "treatment"
        should_stop = True
        reason = (
            f"Treatment expected loss {expected_loss_treatment:.6f} < threshold {loss_threshold}"
        )
    elif expected_loss_control < loss_threshold:
        recommendation = "control"
        should_stop = True
        reason = f"Control expected loss {expected_loss_control:.6f} < threshold {loss_threshold}"
    else:
        # Not yet significant
        recommendation = "treatment" if prob_better > 0.5 else "control"
        should_stop = False
        reason = (
            f"Experiment ongoing (P(treatment>better)={prob_better:.4f}, "
            f"need loss < {loss_threshold})"
        )

    return BayesianResult(
        control_posterior_mean=control_mean,
        control_ci_low=control_ci_low,
        control_ci_high=control_ci_high,
        treatment_posterior_mean=treatment_mean,
        treatment_ci_low=treatment_ci_low,
        treatment_ci_high=treatment_ci_high,
        prob_treatment_better=prob_better,
        expected_loss_control=expected_loss_control,
        expected_loss_treatment=expected_loss_treatment,
        recommendation=recommendation,
        should_stop=should_stop,
        reason=reason,
    )
