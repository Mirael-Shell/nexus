"""Hyperparameter optimization using Optuna.

Runs Optuna study on the logistic regression training pipeline,
sweeping over learning_rate, epochs, and train_split. Each trial
is logged to MLflow for comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus.core.config import get_settings
from nexus.core.logging import get_logger, setup_logging

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class HPOResult:
    """Best hyperparameters found."""

    best_params: dict
    best_value: float  # validation F1
    n_trials: int
    best_trial_number: int


def run_hpo(n_trials: int = 20) -> HPOResult:
    """Run Optuna hyperparameter optimization.

    Sweeps:
      - learning_rate: log-uniform [1e-4, 1e-1]
      - epochs: int [5, 50]
      - train_split: float [0.6, 0.9]

    Each trial trains the pipeline and reports validation F1-macro.
    Best trial is registered in MLflow.

    Args:
        n_trials: Number of Optuna trials.

    Returns:
        HPOResult with best params and metrics.
    """
    import optuna

    from nexus.training.pipeline import TrainConfig, train

    setup_logging(settings.log_level)

    def objective(trial: optuna.Trial) -> float:
        config = TrainConfig(
            learning_rate=trial.suggest_float("learning_rate", 1e-4, 1e-1, log=True),
            epochs=trial.suggest_int("epochs", 5, 50),
            train_split=trial.suggest_float("train_split", 0.6, 0.9),
            batch_size=trial.suggest_int("batch_size", 4, 16),
        )
        result = train(config)
        return result.f1_macro

    study = optuna.create_study(
        direction="maximize",
        study_name="nexus_hpo",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_trial
    logger.info(
        "HPO complete",
        best_value=f"{best.value:.4f}",
        best_params=best.params,
        n_trials=n_trials,
    )

    return HPOResult(
        best_params=best.params,
        best_value=best.value,
        n_trials=n_trials,
        best_trial_number=best.number,
    )


if __name__ == "__main__":
    result = run_hpo(n_trials=20)
    print(f"\nBest F1: {result.best_value:.4f}")
    print(f"Best params: {result.best_params}")
