"""Dataset management + retraining endpoints.

POST /api/v1/dataset/add     — Add a new training example
POST /api/v1/dataset/retrain — Retrain model on updated dataset
GET  /api/v1/dataset/stats   — Show dataset statistics
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.core.logging import get_logger
from nexus.serving.engine import reload_engine

router = APIRouter(prefix="/api/v1", tags=["dataset"])
logger = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data"
_DATASET_PATH = _DATA_DIR / "dataset.csv"


class AddExampleRequest(BaseModel):
    """Add a new example to the dataset."""

    text: str = Field(..., min_length=1, max_length=2000)
    label: str = Field(..., pattern="^(safe|spam|toxic)$")


class AddExampleResponse(BaseModel):
    success: bool
    total_samples: int
    message: str


class DatasetStatsResponse(BaseModel):
    total_samples: int
    by_label: dict[str, int]
    last_updated: str | None


class RetrainResponse(BaseModel):
    success: bool
    message: str
    metrics: dict | None = None


@router.post("/dataset/add", response_model=AddExampleResponse)
async def add_example(request: AddExampleRequest) -> AddExampleResponse:
    """Add a new training example to the dataset CSV.

    Used by the feedback loop: when user clicks 👎 on a prediction,
    they can provide the correct label, which gets appended here.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check if file exists and has header
    write_header = not _DATASET_PATH.exists()
    if _DATASET_PATH.exists():
        with open(_DATASET_PATH) as f:
            write_header = len(f.readline().strip()) == 0

    with open(_DATASET_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["text", "label", "source"])
        writer.writerow(
            [
                request.text.strip(),
                request.label.strip().lower(),
                "user_feedback",
            ]
        )

    # Count total
    total = _count_samples()

    logger.info(
        "Example added to dataset",
        label=request.label,
        total=total,
    )

    return AddExampleResponse(
        success=True,
        total_samples=total,
        message=f"Added as '{request.label}'. Dataset now has {total} samples. "
        f"Retrain to update the model.",
    )


@router.post("/dataset/retrain", response_model=RetrainResponse)
async def retrain_model() -> RetrainResponse:
    """Retrain the model on the updated dataset.

    Loads all data from CSV, trains TF-IDF + LogisticRegression,
    saves the new model, and hot-reloads the inference engine.
    """
    from nexus.training.pipeline import train_model

    logger.info("Retraining started")

    try:
        metrics = train_model()

        if "error" in metrics:
            return RetrainResponse(
                success=False,
                message=metrics["error"],
            )

        # Hot-reload the engine
        reload_engine()

        logger.info(
            "Retraining complete",
            accuracy=metrics.get("accuracy"),
            model_version=metrics.get("model_version"),
        )

        return RetrainResponse(
            success=True,
            message=f"Model retrained. Accuracy: {metrics.get('accuracy', '?')}, "
            f"F1: {metrics.get('f1_macro', '?')}. "
            f"Version: {metrics.get('model_version', '?')}",
            metrics=metrics,
        )
    except Exception as e:
        logger.error("Retraining failed", error=str(e))
        return RetrainResponse(
            success=False,
            message=f"Retraining failed: {e}",
        )


@router.get("/dataset/stats", response_model=DatasetStatsResponse)
async def dataset_stats() -> DatasetStatsResponse:
    """Show dataset statistics."""
    from collections import Counter

    if not _DATASET_PATH.exists():
        return DatasetStatsResponse(
            total_samples=0,
            by_label={},
            last_updated=None,
        )

    labels = []
    with open(_DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label", "").strip().lower()
            if label:
                labels.append(label)

    dist = dict(Counter(labels))
    mtime = datetime.fromtimestamp(_DATASET_PATH.stat().st_mtime, tz=UTC)

    return DatasetStatsResponse(
        total_samples=len(labels),
        by_label=dist,
        last_updated=mtime.isoformat(),
    )


def _count_samples() -> int:
    """Count total samples in dataset."""
    if not _DATASET_PATH.exists():
        return 0
    with open(_DATASET_PATH, encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)  # minus header
