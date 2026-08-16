"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://nexus:nexus_dev@localhost:5432/nexus"

    # ── Redis ─────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── MLflow ────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "nexus_content_moderation"
    mlflow_s3_endpoint_url: str = "http://localhost:9000"
    aws_access_key_id: str = "minio"
    aws_secret_access_key: str = "minio12345"

    # ── API ───────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True
    log_level: str = "DEBUG"

    # ── ML Model ──────────────────────────────────────────
    model_name: str = "distilbert-base-uncased"
    model_cache_dir: str = str(PROJECT_ROOT / "models" / "cache")
    inference_device: str = "cpu"
    inference_batch_size: int = 32

    # ── Class labels ──────────────────────────────────────
    labels: tuple[str, ...] = ("safe", "spam", "toxic")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
