"""Create database tables on startup (MVP — replaces Alembic for Phase 1)."""

import asyncio

from sqlalchemy import text as sqlalchemy_text

from nexus.core.config import get_settings
from nexus.core.logging import get_logger, setup_logging
from nexus.db.models import Base
from nexus.db.session import engine

settings = get_settings()
logger = get_logger(__name__)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    setup_logging(settings.log_level)

    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                # Enable pgvector extension (idempotent)
                try:
                    await conn.execute(sqlalchemy_text("CREATE EXTENSION IF NOT EXISTS vector"))
                    logger.info("pgvector extension enabled")
                except Exception:
                    logger.info("pgvector extension not available (using JSON fallback)")

                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            return
        except Exception as e:
            logger.warning(
                "DB connection failed",
                attempt=attempt,
                max=max_retries,
                error=str(e),
            )
            if attempt == max_retries:
                logger.error("Max retries reached, giving up on DB init")
                return
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(init_db())
