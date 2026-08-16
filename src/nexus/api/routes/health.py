"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nexus import __version__
from nexus.api.schemas import HealthResponse
from nexus.db.session import get_db
from nexus.serving.engine import get_engine

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession | None = Depends(get_db)) -> HealthResponse:
    """Return service health status."""
    db_ok = False
    if db is not None:
        try:
            await db.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False

    engine = get_engine()

    return HealthResponse(
        status="ok",
        version=__version__,
        model_loaded=engine.is_loaded,
        database_connected=db_ok,
    )
