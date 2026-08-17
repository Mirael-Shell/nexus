"""Prediction endpoints: POST /predict, GET /predict/{id}."""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.api.routes.alerting import record_prediction
from nexus.api.schemas import (
    PredictionLabel,
    PredictionResult,
    PredictRequest,
    PredictResponse,
)
from nexus.core.logging import get_logger
from nexus.db.models import Prediction
from nexus.db.session import get_db
from nexus.serving.engine import get_engine

router = APIRouter(prefix="/api/v1", tags=["predictions"])
logger = get_logger(__name__)


@router.post("/predict", response_model=PredictResponse, status_code=status.HTTP_201_CREATED)
async def predict(
    request: PredictRequest,
    db: AsyncSession | None = Depends(get_db),
) -> PredictResponse:
    """Classify text content and store the result.

    If the database is unavailable, the prediction is still returned
    (graceful degradation mode).
    """
    engine = get_engine()
    result = await asyncio.to_thread(engine.predict, request.text)

    # Feed the alerting system (toxicity spike / latency detection)
    record_prediction(result.label, result.confidence, result.processing_time_ms)

    prediction_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    stored_at = now

    if db is not None:
        try:
            prediction = Prediction(
                id=prediction_id,
                input_text=request.text,
                predicted_label=result.label,
                confidence=result.confidence,
                model_version=result.model_version,
                processing_time_ms=result.processing_time_ms,
                all_probabilities=json.dumps(result.all_probabilities),
            )
            db.add(prediction)
            await db.flush()
            stored_at = prediction.created_at or now
            logger.info("Prediction stored", prediction_id=prediction_id)
        except Exception as e:
            logger.warning("DB write failed, prediction not stored", error=str(e))
    else:
        logger.info("DB unavailable, prediction not stored", prediction_id=prediction_id)

    return PredictResponse(
        prediction_id=prediction_id,
        label=PredictionLabel(result.label),
        confidence=result.confidence,
        all_probabilities=[
            PredictionResult(label=PredictionLabel(k), probability=v)
            for k, v in result.all_probabilities.items()
        ],
        model_version=result.model_version,
        processing_time_ms=result.processing_time_ms,
        created_at=stored_at,
    )


@router.get("/predict/{prediction_id}", response_model=PredictResponse)
async def get_prediction(
    prediction_id: str,
    db: AsyncSession | None = Depends(get_db),
) -> PredictResponse:
    """Retrieve a stored prediction by ID."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )

    stmt = select(Prediction).where(Prediction.id == prediction_id)
    result = await db.execute(stmt)
    prediction = result.scalar_one_or_none()

    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction {prediction_id} not found",
        )

    probs = json.loads(prediction.all_probabilities)
    return PredictResponse(
        prediction_id=prediction.id,
        label=PredictionLabel(prediction.predicted_label),
        confidence=prediction.confidence,
        all_probabilities=[
            PredictionResult(label=PredictionLabel(k), probability=v) for k, v in probs.items()
        ],
        model_version=prediction.model_version,
        processing_time_ms=prediction.processing_time_ms,
        created_at=prediction.created_at,
    )
