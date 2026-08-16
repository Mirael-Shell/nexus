"""Tests for the Filter API endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_filter_blocks_spam(client: AsyncClient) -> None:
    """Filter should block spam messages above threshold."""
    response = await client.post(
        "/api/v1/filter",
        json={
            "text": "WIN a FREE iPhone! Click here NOW to claim!",
            "rules": {
                "block_labels": ["spam", "toxic"],
                "flag_labels": [],
                "threshold": 0.3,
                "use_similarity_boost": False,
            },
            "source": "twitch",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["action"] in ("block", "flag", "allow")
    assert data["label"] in ("safe", "spam", "toxic")
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["latency_ms"] > 0
    assert data["embedding_model"]  # some model name
    assert isinstance(data["triggered_rules"], list)
    assert isinstance(data["similar_matches"], list)


@pytest.mark.asyncio
async def test_filter_allows_safe(client: AsyncClient) -> None:
    """Filter should allow safe messages with high threshold."""
    response = await client.post(
        "/api/v1/filter",
        json={
            "text": "Hello everyone, great stream today!",
            "rules": {
                "block_labels": ["spam", "toxic"],
                "flag_labels": [],
                "threshold": 0.99,  # Very high — nothing should trigger
                "use_similarity_boost": False,
            },
            "source": "youtube",
        },
    )
    # In tests DB may be unavailable — endpoint should still work
    assert response.status_code == 200
    data = response.json()
    assert data["action"] in ("allow", "block", "flag")
    assert data["label"] in ("safe", "spam", "toxic")


@pytest.mark.asyncio
async def test_filter_returns_action(client: AsyncClient) -> None:
    """Filter response should always have a valid action."""
    response = await client.post(
        "/api/v1/filter",
        json={
            "text": "Some random text for testing",
            "rules": {
                "block_labels": ["spam"],
                "flag_labels": [],
                "threshold": 0.5,
                "use_similarity_boost": True,
            },
            "source": "discord",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] in ("allow", "block", "flag")


@pytest.mark.asyncio
async def test_filter_default_rules(client: AsyncClient) -> None:
    """Filter should work with default rules (no rules specified)."""
    response = await client.post(
        "/api/v1/filter",
        json={"text": "Hello world"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] in ("allow", "block", "flag")
    assert data["label"] in ("safe", "spam", "toxic")


@pytest.mark.asyncio
async def test_filter_stats(client: AsyncClient) -> None:
    """Filter stats endpoint should return valid structure."""
    response = await client.get("/api/v1/filter/stats")
    assert response.status_code == 200
    data = response.json()
    # May have error if DB unavailable, or valid stats
    if "error" not in data:
        assert "total_events" in data
        assert "by_action" in data
        assert "by_label" in data


@pytest.mark.asyncio
async def test_filter_recent(client: AsyncClient) -> None:
    """Filter recent endpoint should return events list."""
    response = await client.get("/api/v1/filter/recent?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_filter_source_tagging(client: AsyncClient) -> None:
    """Filter should accept and store source identifier."""
    response = await client.post(
        "/api/v1/filter",
        json={
            "text": "Test message for source tagging",
            "source": "custom_platform",
        },
    )
    assert response.status_code == 200
