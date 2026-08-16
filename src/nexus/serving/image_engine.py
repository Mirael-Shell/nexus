"""Image classification engine for multi-modal content moderation.

Phase 5 MVP: Mock image classifier that uses simple heuristics
(file size, filename keywords) to simulate content moderation.

Phase 6+ will integrate a real model (e.g., ViT or ResNet fine-tuned
on NSFW/spam image datasets).
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from nexus.core.logging import get_logger

logger = get_logger(__name__)

# Suspicious filename patterns
_SUSPICIOUS_PATTERNS = [
    r"(?i)spam",
    r"(?i)scam",
    r"(?i)adult",
    r"(?i)nsfw",
    r"(?i)violen",
    r"(?i)weapon",
    r"(?i)explicit",
]

_COMPILED_PATTERNS = [re.compile(p) for p in _SUSPICIOUS_PATTERNS]


@dataclass
class ImagePrediction:
    """Image classification result."""

    label: str  # safe / suspicious / violation
    confidence: float
    model_version: str
    processing_time_ms: float
    file_size_bytes: int
    detected_issues: list[str]


def classify_image(
    image_base64: str | None = None,
    filename: str = "",
    file_size: int = 0,
) -> ImagePrediction:
    """Classify an image for content moderation (mock implementation).

    In production, this would run a CNN/ViT model. For the MVP,
    we use filename heuristics and file size analysis.

    Args:
        image_base64: Base64-encoded image data (optional).
        filename: Original filename.
        file_size: Size of the image in bytes.

    Returns:
        ImagePrediction with label and confidence.
    """
    import time

    start = time.perf_counter()

    detected: list[str] = []

    # Check filename for suspicious patterns
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(filename):
            detected.append(f"filename matched: {pattern.pattern}")

    # Heuristic: very large images might be suspicious (steganography, etc.)
    if file_size > 5_000_000:  # 5MB
        detected.append("unusually large file size")

    # Heuristic: tiny images might be tracking pixels
    if 0 < file_size < 100:
        detected.append("suspiciously small image (possible tracker)")

    # Decode image size from base64 if provided
    actual_size = file_size
    if image_base64 and not actual_size:
        try:
            decoded = base64.b64decode(image_base64[:1024])  # sample first 1KB
            actual_size = len(decoded) * (len(image_base64) / max(len(image_base64[:1024]), 1))
        except Exception:
            actual_size = len(image_base64) * 3 // 4  # rough estimate

    # Determine label and confidence
    if len(detected) >= 2:
        label = "violation"
        confidence = 0.82 + min(len(detected) * 0.03, 0.15)
    elif len(detected) == 1:
        label = "suspicious"
        confidence = 0.65 + min(len(detected) * 0.05, 0.1)
    else:
        label = "safe"
        confidence = 0.92

    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "Image classified",
        label=label,
        confidence=f"{confidence:.4f}",
        filename=filename,
        size=actual_size,
    )

    return ImagePrediction(
        label=label,
        confidence=min(confidence, 0.99),
        model_version="image-mock-v0.1.0",
        processing_time_ms=elapsed_ms,
        file_size_bytes=int(actual_size),
        detected_issues=detected,
    )
