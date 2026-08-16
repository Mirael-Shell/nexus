"""Model management endpoints: list versions, promote, get metrics."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from nexus.core.logging import get_logger
from nexus.training.mlflow_client import (
    list_model_versions,
    transition_stage,
)

router = APIRouter(prefix="/api/v1", tags=["models"])
logger = get_logger(__name__)


class ModelVersionResponse(BaseModel):
    """Model version info."""

    version: str
    stage: str
    run_id: str
    status: str
    metrics: dict[str, float | int]
    params: dict[str, str]
    created_at: int | None = None
    updated_at: int | None = None


class ModelListResponse(BaseModel):
    """List of model versions."""

    model_name: str
    versions: list[ModelVersionResponse]


class PromoteRequest(BaseModel):
    """Promote a model version to a new stage."""

    stage: str  # Staging / Production / Archived

    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v not in ("Staging", "Production", "Archived"):
            raise ValueError(f"Stage must be Staging, Production, or Archived, got {v}")
        return v


class PromoteResponse(BaseModel):
    """Promotion confirmation."""

    model_name: str
    version: str
    new_stage: str
    success: bool


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List all model versions from the registry."""
    try:
        versions = list_model_versions("nexus-moderation")
        return ModelListResponse(
            model_name="nexus-moderation",
            versions=[
                ModelVersionResponse(
                    version=v["version"],
                    stage=v["stage"],
                    run_id=v["run_id"],
                    status=v["status"],
                    metrics=v.get("metrics", {}),
                    params=v.get("params", {}),
                    created_at=v.get("created_at"),
                    updated_at=v.get("updated_at"),
                )
                for v in versions
            ],
        )
    except Exception as e:
        logger.warning("Failed to list models", error=str(e))
        return ModelListResponse(model_name="nexus-moderation", versions=[])


@router.post("/models/{version}/promote", response_model=PromoteResponse)
async def promote_model(version: str, request: PromoteRequest) -> PromoteResponse:
    """Promote a model version to a new stage."""
    if request.stage not in ("Staging", "Production", "Archived"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stage must be Staging, Production, or Archived, got '{request.stage}'",
        )

    try:
        transition_stage(
            model_name="nexus-moderation",
            version=version,
            stage=request.stage,
        )
        logger.info("Model promoted", version=version, stage=request.stage)
        return PromoteResponse(
            model_name="nexus-moderation",
            version=version,
            new_stage=request.stage,
            success=True,
        )
    except Exception as e:
        logger.error("Promotion failed", version=version, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote model: {e}",
        ) from e
