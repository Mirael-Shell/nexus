"""SQLAlchemy ORM models for NEXUS platform."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexus.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Prediction(Base):
    """A single inference request and its result."""

    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # All class probabilities stored as JSON-like text
    all_probabilities: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    feedback: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="prediction", cascade="all, delete-orphan"
    )


class Feedback(Base):
    """User feedback (thumbs up/down) for a prediction."""

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prediction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("predictions.id", ondelete="CASCADE"),
        nullable=False,
    )
    feedback_type: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prediction: Mapped["Prediction"] = relationship("Prediction", back_populates="feedback")


class ModelVersion(Base):
    """Registry of all model versions deployed in the platform."""

    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    stage: Mapped[str] = mapped_column(
        String(20), nullable=False, default="development"
    )  # development / staging / production / archived
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ─── A/B Testing ────────────────────────────────────────


class Experiment(Base):
    """An A/B test experiment comparing model variants."""

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Models being compared
    control_model: Mapped[str] = mapped_column(String(100), nullable=False)
    treatment_model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Traffic split: percentage going to treatment (0-100)
    traffic_split: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)

    # Strategy: "weighted" (probabilistic split) or "shadow" (treatment runs alongside)
    strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="weighted")

    # Status lifecycle: draft → running → completed → stopped
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    # Minimum samples before evaluation is meaningful
    min_samples: Mapped[int] = mapped_column(nullable=False, default=30)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assignments: Mapped[list["ExperimentAssignment"]] = relationship(
        "ExperimentAssignment", back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentAssignment(Base):
    """Tracks which model was assigned to a prediction in an experiment."""

    __tablename__ = "experiment_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    variant: Mapped[str] = mapped_column(String(20), nullable=False)  # control / treatment
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    # Feedback outcome (filled later when user provides feedback)
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)  # up / down / None

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="assignments")


# ─── Filter API (pgvector) ──────────────────────────────


class FilterEvent(Base):
    """An event processed by the Filter API.

    Stores the text, classification result, the action taken,
    and a vector embedding for semantic similarity search.
    """

    __tablename__ = "filter_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # allow / block / flag

    # Which rules triggered the action
    triggered_rules: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array

    # Model that classified this event
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # Source identifier (e.g., "twitch", "youtube", "manual")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="api")

    # Vector embedding (384 dims from all-MiniLM-L6-v2)
    # Stored as pgvector for cosine similarity search
    embedding = mapped_column("embedding", Text, nullable=True)  # JSON array fallback

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
