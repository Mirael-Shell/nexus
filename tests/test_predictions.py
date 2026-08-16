"""Tests for prediction endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_predict_returns_classification(client: AsyncClient) -> None:
    """POST /predict should return a classification result."""
    response = await client.post(
        "/api/v1/predict",
        json={"text": "Hello world, this is a test"},
    )

    assert response.status_code == 201
    data = response.json()

    assert "prediction_id" in data
    assert data["label"] in ("safe", "spam", "toxic")
    assert 0.0 <= data["confidence"] <= 1.0
    assert len(data["all_probabilities"]) == 3
    assert data["model_version"]  # any version string (trained or fallback)
    assert data["processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_predict_spam_detection(client: AsyncClient) -> None:
    """Text with spam keywords should lean towards spam classification."""
    response = await client.post(
        "/api/v1/predict",
        json={"text": "WIN a FREE prize! Click here now for bonus gift offer!"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "spam"


@pytest.mark.asyncio
async def test_predict_toxic_detection(client: AsyncClient) -> None:
    """Text with toxic keywords should lean towards toxic classification."""
    response = await client.post(
        "/api/v1/predict",
        json={"text": "You are a stupid idiot and a complete moron loser"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "toxic"


@pytest.mark.asyncio
async def test_predict_safe_text(client: AsyncClient) -> None:
    """Normal text should be classified as safe."""
    response = await client.post(
        "/api/v1/predict",
        json={"text": "The weather is nice today. Let's go for a walk."},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "safe"


@pytest.mark.asyncio
async def test_predict_empty_text_rejected(client: AsyncClient) -> None:
    """Empty text should fail validation."""
    response = await client.post(
        "/api/v1/predict",
        json={"text": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_too_long_rejected(client: AsyncClient) -> None:
    """Text over 10k chars should fail validation."""
    response = await client.post(
        "/api/v1/predict",
        json={"text": "x" * 10001},
    )
    assert response.status_code == 422
