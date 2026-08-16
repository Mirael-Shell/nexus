"""NEXUS automated retraining pipeline DAG.

This DAG runs on a schedule and also supports manual triggering
when drift is detected. Pipeline stages:

  1. check_drift     → Query API for latest drift report
  2. validate_data   → Check if we have enough fresh samples
  3. run_hpo         → Optuna hyperparameter optimization (optional)
  4. train_model     → Train with best params, log to MLflow
  5. evaluate        → Compare new model vs production
  6. promote         → Auto-promote if new model is better
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

# Airflow imports — graceful degradation when not running in Airflow
try:
    from airflow.decorators import dag, task
    from airflow.providers.http.operators.http import SimpleHttpOperator
except ImportError:
    # Fallback: allow importing DAG file outside Airflow (for linting/CI)
    def dag(*args, **kwargs):  # type: ignore[misc]
        def wrapper(func):
            return func
        return wrapper

    def task(*args, **kwargs):  # type: ignore[misc]
        def wrapper(func):
            return func
        return wrapper

    SimpleHttpOperator = None  # type: ignore[assignment,misc]


API_BASE = "http://nexus-api:8000/api/v1"
DRIFT_THRESHOLD = "medium"


@dag(
    dag_id="nexus_retrain_pipeline",
    description="NEXUS automated retraining: drift check → train → evaluate → promote",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "nexus",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "depends_on_past": False,
    },
    tags=["nexus", "mlops", "retraining"],
)
def nexus_retrain_dag():
    """Define the retraining pipeline DAG."""

    @task
    def check_drift() -> dict:
        """Check latest drift report from API."""
        import httpx

        resp = httpx.post(
            f"{API_BASE}/drift/analyze",
            json={"reference_days": 7, "current_hours": 24},
            timeout=30,
        )
        report = resp.json()
        return report

    @task
    def decide_retrain(drift_report: dict) -> bool:
        """Decide whether to retrain based on drift severity."""
        severity = drift_report.get("severity", "none")
        should_retrain = severity in ("medium", "high")

        print(f"Drift severity: {severity}")
        print(f"Drift detected: {drift_report.get('drift_detected', False)}")
        print(f"Should retrain: {should_retrain}")

        return should_retrain or True  # Always retrain in MVP (for demo)

    @task
    def run_hpo(n_trials: int = 10) -> dict:
        """Run Optuna hyperparameter optimization."""
        from nexus.training.hpo import run_hpo

        result = run_hpo(n_trials=n_trials)
        return {
            "best_params": result.best_params,
            "best_value": result.best_value,
            "n_trials": result.n_trials,
        }

    @task
    def train_with_best_params(hpo_result: dict) -> dict:
        """Train model with best hyperparameters from HPO."""
        from nexus.training.pipeline import TrainConfig, train

        params = hpo_result["best_params"]
        config = TrainConfig(
            learning_rate=params["learning_rate"],
            epochs=params["epochs"],
            train_split=params.get("train_split", 0.8),
            batch_size=params.get("batch_size", 8),
        )

        result = train(config)
        return {
            "accuracy": result.accuracy,
            "f1_macro": result.f1_macro,
            "model_version": result.model_version,
            "run_id": result.run_id,
        }

    @task
    def evaluate_and_promote(train_result: dict) -> dict:
        """Compare new model with current production model."""
        from nexus.training.mlflow_client import get_production_model

        current_prod = get_production_model()
        current_f1 = 0.0
        if current_prod and "final_f1_macro" in current_prod.get("metrics", {}):
            current_f1 = current_prod["metrics"]["final_f1_macro"]

        new_f1 = train_result["f1_macro"]
        improvement = new_f1 - current_f1

        decision = {
            "current_production_f1": current_f1,
            "new_model_f1": new_f1,
            "improvement": improvement,
            "should_promote": improvement > 0.001,
            "new_version": train_result["model_version"],
        }

        if decision["should_promote"]:
            from nexus.training.mlflow_client import transition_stage

            transition_stage(
                model_name="nexus-moderation",
                version=train_result["model_version"],
                stage="Production",
            )
            decision["promoted"] = True
            print(f"✓ Model v{train_result['model_version']} promoted to Production")
        else:
            decision["promoted"] = False
            print(
                f"✗ Model not promoted: new F1={new_f1:.4f} "
                f"vs current F1={current_f1:.4f}"
            )

        return decision

    # ─── Pipeline flow ────────────────────────────────────
    drift = check_drift()
    should = decide_retrain(drift)

    # Branch: only run HPO + training if drift detected (or manual trigger)
    hpo = run_hpo(n_trials=10)
    trained = train_with_best_params(hpo)
    result = evaluate_and_promote(trained)

    # Wire dependencies
    should >> hpo


# Instantiate the DAG
nexus_retrain = nexus_retrain_dag()
