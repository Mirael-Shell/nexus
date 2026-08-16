"""MLflow client wrapper for experiment tracking and model registry."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient

from nexus.core.config import get_settings
from nexus.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Track initialization state to avoid repeated connection attempts
_mlflow_initialized = False
_mlflow_available: bool | None = None


def _check_mlflow_available() -> bool:
    """Quick TCP check if MLflow server is reachable."""
    global _mlflow_available
    if _mlflow_available is not None:
        return _mlflow_available

    try:
        from urllib.parse import urlparse

        parsed = urlparse(settings.mlflow_tracking_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5000
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        _mlflow_available = True
        logger.info("MLflow server is reachable", host=host, port=port)
    except Exception:
        _mlflow_available = False
        logger.warning("MLflow server is not reachable", uri=settings.mlflow_tracking_uri)

    return _mlflow_available


def init_mlflow() -> None:
    """Initialize MLflow connection and set tracking URI."""
    global _mlflow_initialized
    if _mlflow_initialized:
        return

    if not _check_mlflow_available():
        return

    os.environ.setdefault("AWS_ACCESS_KEY_ID", settings.aws_access_key_id)
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", settings.aws_secret_access_key)
    os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", settings.mlflow_s3_endpoint_url)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)
    _mlflow_initialized = True
    logger.info(
        "MLflow initialized",
        tracking_uri=settings.mlflow_tracking_uri,
        experiment=settings.mlflow_experiment_name,
    )


def get_client() -> MlflowClient | None:
    """Return an MLflow client for registry operations, or None if unavailable."""
    init_mlflow()
    if not _mlflow_available:
        return None
    return MlflowClient()


@contextmanager
def start_run(run_name: str, params: dict[str, Any] | None = None) -> Iterator[str]:
    """Context manager for an MLflow run.

    Args:
        run_name: Human-readable name for this run.
        params: Optional dict of parameters to log.

    Yields:
        The run ID.
    """
    init_mlflow()
    with mlflow.start_run(run_name=run_name) as run:
        if params:
            for key, value in params.items():
                mlflow.log_param(key, value)
        logger.info("MLflow run started", run_name=run_name, run_id=run.info.run_id)
        yield run.info.run_id


def log_metrics(metrics: dict[str, float], step: int | None = None) -> None:
    """Log metrics to the current MLflow run."""
    for key, value in metrics.items():
        mlflow.log_metric(key, value, step=step)


def register_model(
    run_id: str,
    model_name: str = "nexus-moderation",
    artifact_path: str = "model",
    tags: dict[str, str] | None = None,
) -> str:
    """Register a model version in the MLflow Model Registry.

    Returns:
        The model version string (e.g., "1").
    """
    init_mlflow()
    model_uri = f"runs:/{run_id}/{artifact_path}"

    result = mlflow.register_model(model_uri, model_name, tags=tags)
    logger.info(
        "Model registered",
        name=model_name,
        version=result.version,
        run_id=run_id,
    )
    return result.version


def transition_stage(
    model_name: str,
    version: str,
    stage: str,
    archive_existing: bool = True,
) -> None:
    """Transition a model version to a new stage.

    Stages: None → Staging → Production → Archived
    """
    client = get_client()
    if client is None:
        raise RuntimeError("MLflow server is not available")

    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage=stage,
        archive_existing_versions=archive_existing,
    )
    logger.info(
        "Model stage transitioned",
        name=model_name,
        version=version,
        stage=stage,
    )


def list_model_versions(model_name: str = "nexus-moderation") -> list[dict[str, Any]]:
    """List all versions of a model from the registry."""
    client = get_client()
    if client is None:
        return []

    try:
        versions = client.search_model_versions(f"name='{model_name}'")
    except Exception as e:
        logger.warning("Failed to list model versions", error=str(e))
        return []

    result = []
    for v in versions:
        run = client.get_run(v.run_id) if v.run_id else None
        result.append(
            {
                "version": v.version,
                "stage": v.current_stage,
                "run_id": v.run_id,
                "status": v.status,
                "metrics": run.data.metrics if run else {},
                "params": run.data.params if run else {},
                "created_at": v.creation_timestamp,
                "updated_at": v.last_updated_timestamp,
            }
        )

    result.sort(key=lambda x: int(x["version"]), reverse=True)
    return result


def get_production_model(model_name: str = "nexus-moderation") -> dict[str, Any] | None:
    """Return the current production model version, or None."""
    versions = list_model_versions(model_name)
    for v in versions:
        if v["stage"] == "Production":
            return v
    return None
