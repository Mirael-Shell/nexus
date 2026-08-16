"""Tests for health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Health endpoint should return 200 with status info."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "version" in data
    assert "model_loaded" in data  # True if model file exists, False if fallback
    # database_connected may be False in test (no DB), that's OK
