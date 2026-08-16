"""Tests for the dataset management API."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_example_spam(client: AsyncClient) -> None:
    """Adding a spam example should return success."""
    response = await client.post(
        "/api/v1/dataset/add",
        json={"text": "Amazing spam test example for testing", "label": "spam"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_samples"] > 0


@pytest.mark.asyncio
async def test_add_example_toxic(client: AsyncClient) -> None:
    """Adding a toxic example should return success."""
    response = await client.post(
        "/api/v1/dataset/add",
        json={"text": "You are a complete moron for testing", "label": "toxic"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_add_example_safe(client: AsyncClient) -> None:
    """Adding a safe example should return success."""
    response = await client.post(
        "/api/v1/dataset/add",
        json={"text": "This is a perfectly safe message for testing", "label": "safe"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_add_example_invalid_label(client: AsyncClient) -> None:
    """Invalid label should be rejected (422 validation error)."""
    response = await client.post(
        "/api/v1/dataset/add",
        json={"text": "test message", "label": "invalid_label"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_example_empty_text(client: AsyncClient) -> None:
    """Empty text should be rejected."""
    response = await client.post(
        "/api/v1/dataset/add",
        json={"text": "", "label": "spam"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dataset_stats(client: AsyncClient) -> None:
    """Dataset stats should return valid structure."""
    response = await client.get("/api/v1/dataset/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_samples" in data
    assert "by_label" in data
    assert isinstance(data["by_label"], dict)


@pytest.mark.asyncio
async def test_add_then_stats_increase(client: AsyncClient) -> None:
    """Adding an example should increase total_samples."""
    # Get initial count
    r1 = await client.get("/api/v1/dataset/stats")
    initial = r1.json()["total_samples"]

    # Add example
    await client.post(
        "/api/v1/dataset/add",
        json={"text": "Incremental test example unique text", "label": "safe"},
    )

    # Get new count
    r2 = await client.get("/api/v1/dataset/stats")
    after = r2.json()["total_samples"]
    assert after == initial + 1


@pytest.mark.asyncio
async def test_retrain_returns_metrics(client: AsyncClient) -> None:
    """Retraining should return model metrics or a clear error."""
    response = await client.post("/api/v1/dataset/retrain")
    assert response.status_code == 200
    data = response.json()

    if data["success"]:
        assert "metrics" in data
        metrics = data["metrics"]
        assert "accuracy" in metrics
        assert "f1_macro" in metrics
        assert "model_version" in metrics
        assert metrics["accuracy"] > 0
    else:
        # Not enough data — acceptable
        assert "message" in data
