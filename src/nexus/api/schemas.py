"""Pydantic schemas for API request/response contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ─── Enums ───────────────────────────────────────────────


class PredictionLabel(StrEnum):
    SAFE = "safe"
    SPAM = "spam"
    TOXIC = "toxic"


class FeedbackType(StrEnum):
    UP = "up"
    DOWN = "down"


# ─── Inference ───────────────────────────────────────────


class PredictRequest(BaseModel):
    """Inference request — text content to classify."""

    text: str = Field(..., min_length=1, max_length=10000, description="Content to classify")
    model_version: str | None = Field(
        None, description="Specific model version (default: production)"
    )


class PredictionResult(BaseModel):
    """Single class probability."""

    label: PredictionLabel
    probability: float = Field(..., ge=0.0, le=1.0)


class PredictResponse(BaseModel):
    """Inference response."""

    prediction_id: str
    label: PredictionLabel
    confidence: float = Field(..., ge=0.0, le=1.0)
    all_probabilities: list[PredictionResult]
    model_version: str
    processing_time_ms: float
    created_at: datetime


# ─── Feedback ────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    """User feedback for a prediction."""

    prediction_id: str
    feedback: FeedbackType
    comment: str | None = Field(None, max_length=1000)


class FeedbackResponse(BaseModel):
    """Feedback confirmation."""

    id: str
    prediction_id: str
    feedback: FeedbackType
    comment: str | None
    created_at: datetime


# ─── Health ──────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    model_loaded: bool
    database_connected: bool


# ─── A/B Experiments ─────────────────────────────────────


class ExperimentStrategy(StrEnum):
    WEIGHTED = "weighted"
    SHADOW = "shadow"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"


class CreateExperimentRequest(BaseModel):
    """Create a new A/B experiment."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    control_model: str = Field(..., description="Model version for control group")
    treatment_model: str = Field(..., description="Model version for treatment group")
    traffic_split: float = Field(50.0, ge=0.0, le=100.0, description="% traffic to treatment")
    strategy: ExperimentStrategy = ExperimentStrategy.WEIGHTED
    min_samples: int = Field(30, ge=1, le=10000)


class ExperimentResponse(BaseModel):
    """Experiment details."""

    id: str
    name: str
    description: str | None
    control_model: str
    treatment_model: str
    traffic_split: float
    strategy: str
    status: str
    min_samples: int
    created_at: datetime
    updated_at: datetime
    # Aggregated stats
    control_total: int = 0
    control_up: int = 0
    control_down: int = 0
    treatment_total: int = 0
    treatment_up: int = 0
    treatment_down: int = 0


class ExperimentListResponse(BaseModel):
    """List of experiments."""

    experiments: list[ExperimentResponse]
