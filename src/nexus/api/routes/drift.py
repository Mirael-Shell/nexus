"""Drift detection endpoints: POST /drift/analyze."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.analytics.drift import PredictionSample, detect_drift
from nexus.core.logging import get_logger
from nexus.db.models import Prediction
from nexus.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["drift"])
logger = get_logger(__name__)


class DriftRequest(BaseModel):
    """Request drift analysis with configurable windows."""

    reference_days: int = Field(7, ge=1, le=90, description="Days of historical data as reference")
    current_hours: int = Field(
        24, ge=1, le=168, description="Hours of recent data as current window"
    )


@router.post("/drift/analyze")
async def analyze_drift(
    request: DriftRequest,
    db: AsyncSession | None = Depends(get_db),
) -> dict:
    """Analyze prediction drift between reference and current windows."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    ref_start = now - timedelta(days=request.reference_days)
    cur_start = now - timedelta(hours=request.current_hours)

    # Fetch reference and current predictions
    ref_stmt = (
        select(Prediction)
        .where(Prediction.created_at >= ref_start)
        .where(Prediction.created_at < cur_start)
        .order_by(Prediction.created_at)
    )
    ref_result = await db.execute(ref_stmt)
    ref_predictions = list(ref_result.scalars().all())

    cur_stmt = (
        select(Prediction).where(Prediction.created_at >= cur_start).order_by(Prediction.created_at)
    )
    cur_result = await db.execute(cur_stmt)
    cur_predictions = list(cur_result.scalars().all())

    if len(ref_predictions) < 5 or len(cur_predictions) < 5:
        return {
            "drift_detected": False,
            "severity": "none",
            "recommendation": (
                f"Insufficient data (reference={len(ref_predictions)}, "
                f"current={len(cur_predictions)}, need ≥5 each)"
            ),
            "reference_size": len(ref_predictions),
            "current_size": len(cur_predictions),
            "metrics": [],
        }

    ref_samples = [
        PredictionSample(
            label=p.predicted_label,
            confidence=p.confidence,
            text_length=len(p.input_text),
        )
        for p in ref_predictions
    ]
    cur_samples = [
        PredictionSample(
            label=p.predicted_label,
            confidence=p.confidence,
            text_length=len(p.input_text),
        )
        for p in cur_predictions
    ]

    report = detect_drift(ref_samples, cur_samples)

    # Feed the alerting system when drift is detected
    if report.drift_detected:
        from nexus.api.routes.alerting import record_drift

        record_drift(report.overall_drift_score, report.severity)

    logger.info(
        "Drift analysis complete",
        severity=report.severity,
        drifted=report.drift_detected,
    )
    return report.to_dict()


@router.get("/drift/latest")
async def latest_drift(
    db: AsyncSession | None = Depends(get_db),
) -> dict:
    """Quick drift check using default windows (7d reference, 24h current)."""
    return await analyze_drift(DriftRequest(), db)
