"""Tests for feedback endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_feedback_up(client: AsyncClient) -> None:
    """POST /feedback with thumbs up should return 201."""
    # First create a prediction
    predict_resp = await client.post(
        "/api/v1/predict",
        json={"text": "Hello world"},
    )
    assert predict_resp.status_code == 201
    prediction_id = predict_resp.json()["prediction_id"]

    # Then submit feedback
    response = await client.post(
        "/api/v1/feedback",
        json={"prediction_id": prediction_id, "feedback": "up"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["prediction_id"] == prediction_id
    assert data["feedback"] == "up"
    assert data["comment"] is None


@pytest.mark.asyncio
async def test_create_feedback_down_with_comment(client: AsyncClient) -> None:
    """POST /feedback with thumbs down and a comment."""
    predict_resp = await client.post(
        "/api/v1/predict",
        json={"text": "Hello world"},
    )
    prediction_id = predict_resp.json()["prediction_id"]

    response = await client.post(
        "/api/v1/feedback",
        json={
            "prediction_id": prediction_id,
            "feedback": "down",
            "comment": "Wrong classification",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["feedback"] == "down"
    assert data["comment"] == "Wrong classification"


@pytest.mark.asyncio
async def test_feedback_nonexistent_prediction(client: AsyncClient) -> None:
    """Feedback for a non-existent prediction should 404."""
    response = await client.post(
        "/api/v1/feedback",
        json={"prediction_id": "nonexistent-id-12345", "feedback": "up"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_prediction_by_id(client: AsyncClient) -> None:
    """GET /predict/{id} should return the stored prediction."""
    predict_resp = await client.post(
        "/api/v1/predict",
        json={"text": "Get this prediction later"},
    )
    prediction_id = predict_resp.json()["prediction_id"]

    response = await client.get(f"/api/v1/predict/{prediction_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["prediction_id"] == prediction_id
    assert data["label"] in ("safe", "spam", "toxic")


@pytest.mark.asyncio
async def test_get_prediction_not_found(client: AsyncClient) -> None:
    """GET /predict/{id} for non-existent ID should 404."""
    response = await client.get("/api/v1/predict/nonexistent-id")
    assert response.status_code == 404
