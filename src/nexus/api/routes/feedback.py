"""Feedback endpoint: POST /feedback."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.api.schemas import FeedbackRequest, FeedbackResponse, FeedbackType
from nexus.core.logging import get_logger
from nexus.db.models import Feedback, Prediction
from nexus.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["feedback"])
logger = get_logger(__name__)


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    request: FeedbackRequest,
    db: AsyncSession | None = Depends(get_db),
) -> FeedbackResponse:
    """Submit user feedback for a prediction.

    If DB is unavailable, returns the feedback confirmation without persisting.
    """
    feedback_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    if db is not None:
        try:
            # Verify prediction exists
            stmt = select(Prediction).where(Prediction.id == str(request.prediction_id))
            result = await db.execute(stmt)
            prediction = result.scalar_one_or_none()

            if prediction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prediction {request.prediction_id} not found",
                )

            feedback = Feedback(
                id=feedback_id,
                prediction_id=str(request.prediction_id),
                feedback_type=request.feedback.value,
                comment=request.comment,
            )
            db.add(feedback)
            await db.flush()

            logger.info("Feedback stored", feedback_id=feedback_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("DB write failed, feedback not stored", error=str(e))
    else:
        logger.info("DB unavailable, feedback not stored", feedback_id=feedback_id)

    return FeedbackResponse(
        id=feedback_id,
        prediction_id=str(request.prediction_id),
        feedback=FeedbackType(request.feedback.value),
        comment=request.comment,
        created_at=now,
    )
