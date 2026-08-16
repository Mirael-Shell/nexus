"""Cost analytics endpoints: GET /cost/summary."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.analytics.cost import compute_cost_summary
from nexus.core.logging import get_logger
from nexus.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["cost"])
logger = get_logger(__name__)


@router.get("/cost/summary")
async def get_cost_summary(
    days: int = 7,
    db: AsyncSession | None = Depends(get_db),
) -> dict:
    """Get cost summary for the last N days.

    Includes per-day breakdown, totals, and unit economics.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    days = min(max(days, 1), 90)  # Clamp 1-90
    summary = await compute_cost_summary(db, days)
    return summary.to_dict()
