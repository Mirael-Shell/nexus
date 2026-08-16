"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus import __version__
from nexus.api.routes import (
    active_learning,
    alerting,
    business,
    cost,
    dataset,
    demo,
    drift,
    experiments,
    feedback,
    filter,
    guardrails,
    health,
    models,
    multimodal,
    predictions,
    streaming,
)
from nexus.core.config import get_settings
from nexus.core.logging import get_logger, setup_logging
from nexus.core.metrics import PrometheusMiddleware, metrics_endpoint
from nexus.core.security import APIKeyMiddleware, RateLimitMiddleware
from nexus.serving.engine import get_engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    setup_logging(settings.log_level)
    logger = get_logger("nexus")
    logger.info("Starting NEXUS API", version=__version__)

    # Pre-initialize the inference engine
    engine = get_engine()
    logger.info("Inference engine ready", version=engine.model_version)

    yield

    logger.info("Shutting down NEXUS API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NEXUS — End-to-End AI Platform",
        description=(
            "Real-time content moderation platform with MLOps lifecycle "
            "management and product analytics."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Prometheus metrics
    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics_endpoint)

    # Security (API key is optional — enabled when API_KEY env var is set)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)

    # CORS (dev — allow frontend)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health.router, prefix="")
    app.include_router(predictions.router, prefix="")
    app.include_router(feedback.router, prefix="")
    app.include_router(models.router, prefix="")
    app.include_router(experiments.router, prefix="")
    app.include_router(drift.router, prefix="")
    app.include_router(cost.router, prefix="")
    app.include_router(multimodal.router, prefix="")
    app.include_router(dataset.router, prefix="")
    app.include_router(filter.router, prefix="")
    app.include_router(streaming.router, prefix="")
    app.include_router(active_learning.router, prefix="")
    app.include_router(alerting.router, prefix="")
    app.include_router(business.router, prefix="")
    app.include_router(guardrails.router, prefix="")
    app.include_router(demo.router, prefix="")

    return app


app = create_app()
