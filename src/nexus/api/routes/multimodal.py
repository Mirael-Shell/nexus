"""Multi-modal moderation endpoints: POST /moderate/image."""

from __future__ import annotations

import time

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field

from nexus.core.logging import get_logger
from nexus.serving.image_engine import classify_image

router = APIRouter(prefix="/api/v1", tags=["multimodal"])
logger = get_logger(__name__)


class ImageModerationResponse(BaseModel):
    """Image moderation result."""

    label: str = Field(description="safe / suspicious / violation")
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str
    processing_time_ms: float
    file_size_bytes: int
    detected_issues: list[str]


@router.post("/moderate/image", response_model=ImageModerationResponse)
async def moderate_image(
    file: UploadFile = File(..., description="Image file to moderate"),
) -> ImageModerationResponse:
    """Classify an uploaded image for content moderation.

    Supports PNG, JPEG, GIF, WebP. Returns label + confidence + detected issues.
    """
    start = time.perf_counter()

    # Read file
    contents = await file.read()
    file_size = len(contents)

    # Get base64 for potential future processing
    import base64

    img_b64 = base64.b64encode(contents).decode("utf-8")

    result = classify_image(
        image_base64=img_b64,
        filename=file.filename or "",
        file_size=file_size,
    )

    elapsed_ms = (time.perf_counter() - start) * 1000

    return ImageModerationResponse(
        label=result.label,
        confidence=result.confidence,
        model_version=result.model_version,
        processing_time_ms=elapsed_ms,
        file_size_bytes=result.file_size_bytes,
        detected_issues=result.detected_issues,
    )
