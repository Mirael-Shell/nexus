"""Active Learning — uncertainty sampling for human-in-the-loop labeling.

Returns the most uncertain predictions (low-confidence, high-entropy) for review.
"""

import csv
import json
import math
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.core.logging import get_logger
from nexus.db.models import Prediction
from nexus.db.session import get_db

logger = get_logger("nexus.active_learning")

router = APIRouter(prefix="/api/v1/active-learning", tags=["active-learning"])

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data"
_DATASET_PATH = _DATA_DIR / "dataset.csv"


class UncertainSample(BaseModel):
    prediction_id: str
    text: str
    predicted_label: str
    confidence: float
    all_probabilities: dict[str, float]
    entropy: float
    created_at: str


class UncertainSamplesResponse(BaseModel):
    samples: list[UncertainSample]
    total_low_confidence: int
    threshold: float


@router.get("/uncertain", response_model=UncertainSamplesResponse)
async def get_uncertain_samples(
    limit: int = 20,
    threshold: float = 0.5,
) -> UncertainSamplesResponse:
    """Get predictions where the model is least confident.

    These are the most valuable samples for human review —
    labeling them improves the model the most.
    """
    samples: list[UncertainSample] = []
    total_low = 0

    async for db in get_db():
        if db is None:
            break

        result = await db.execute(
            select(Prediction)
            .where(Prediction.confidence < threshold)
            .order_by(Prediction.confidence.asc())
            .limit(limit)
        )
        rows = result.scalars().all()

        for row in rows:
            # Parse probabilities from JSON string
            try:
                probs = json.loads(row.all_probabilities) if row.all_probabilities else {}
            except (json.JSONDecodeError, TypeError):
                probs = {}

            # Calculate entropy: higher = more uncertain
            entropy = -sum(p * math.log2(p) for p in probs.values() if p > 0) if probs else 0.0

            samples.append(
                UncertainSample(
                    prediction_id=row.id,
                    text=row.input_text,
                    predicted_label=row.predicted_label,
                    confidence=round(row.confidence, 4),
                    all_probabilities={k: round(v, 4) for k, v in probs.items()},
                    entropy=round(entropy, 4),
                    created_at=row.created_at.isoformat() if row.created_at else "",
                )
            )

        # Count total low-confidence
        count_result = await db.execute(select(Prediction).where(Prediction.confidence < threshold))
        total_low = len(count_result.scalars().all())
        break

    return UncertainSamplesResponse(
        samples=samples,
        total_low_confidence=total_low,
        threshold=threshold,
    )


class ReviewLabel(BaseModel):
    prediction_id: str = Field(..., min_length=1)
    correct_label: str = Field(..., pattern="^(safe|spam|toxic)$")


@router.post("/review")
async def submit_review(req: ReviewLabel) -> dict:
    """Submit a corrected label for an uncertain prediction.

    Adds the corrected example to the dataset for next retrain cycle.
    """
    text = ""
    async for db in get_db():
        if db is None:
            break
        result = await db.execute(select(Prediction).where(Prediction.id == req.prediction_id))
        pred = result.scalar_one_or_none()
        if pred:
            text = pred.input_text
        break

    if not text:
        return {"success": False, "message": "Prediction not found"}

    # Add to dataset CSV with corrected label
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not _DATASET_PATH.exists()
    if _DATASET_PATH.exists():
        with open(_DATASET_PATH) as f:
            write_header = len(f.readline().strip()) == 0

    with open(_DATASET_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["text", "label", "source"])
        writer.writerow([text.strip(), req.correct_label.strip().lower(), "active_learning"])

    return {
        "success": True,
        "message": f"Added to dataset as '{req.correct_label}'",
        "text_preview": text[:80],
    }
