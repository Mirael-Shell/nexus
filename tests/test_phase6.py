"""Tests for Phase 6 features: alerting, business, guardrails, active learning."""

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ─── Alerting ────────────────────────────────────────────


class TestAlerting:
    async def test_thresholds_endpoint(self, client):
        res = await client.get("/api/v1/alerts/thresholds")
        assert res.status_code == 200
        data = res.json()
        assert "toxicity_rate" in data
        assert "latency_ms" in data
        assert "drift_score" in data

    async def test_webhook_crud(self, client):
        # Add
        res = await client.post(
            "/api/v1/alerts/webhooks",
            json={"url": "https://example.com/hook", "name": "test-wh"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "registered"

        # List
        res = await client.get("/api/v1/alerts/webhooks")
        assert any(w["name"] == "test-wh" for w in res.json()["webhooks"])

        # Delete
        res = await client.delete("/api/v1/alerts/webhooks/test-wh")
        assert res.status_code == 200

    async def test_history_empty(self, client):
        res = await client.get("/api/v1/alerts/history")
        assert res.status_code == 200
        assert "alerts" in res.json()

    async def test_record_prediction_spike_detection(self):
        from nexus.api.routes.alerting import (
            _alert_history,
            record_prediction,
        )

        _alert_history.clear()
        # Simulate a toxicity spike: 10 predictions, 8 toxic
        for _ in range(8):
            record_prediction("toxic", 0.9, 10.0)
        for _ in range(2):
            record_prediction("safe", 0.8, 10.0)

        assert any(a["type"] == "toxicity_spike" for a in _alert_history)

    async def test_record_latency_alert(self):
        from nexus.api.routes.alerting import _alert_history, record_prediction

        _alert_history.clear()
        record_prediction("safe", 0.9, 600.0)  # > 500ms threshold
        assert any(a["type"] == "latency" for a in _alert_history)


# ─── Guardrails ──────────────────────────────────────────


class TestGuardrails:
    async def test_layers_info(self, client):
        res = await client.get("/api/v1/guardrails/layers")
        assert res.status_code == 200
        data = res.json()
        assert len(data["layers"]) == 4
        names = {layer["name"] for layer in data["layers"]}
        assert names == {"regex", "lexicon", "ml", "embedding"}

    async def test_clean_text_allowed(self, client):
        res = await client.post(
            "/api/v1/guardrails/analyze",
            json={"text": "Hello, this is a nice day for programming!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["action"] == "allow"
        assert data["final_score"] < 0.3
        assert data["latency_ms"] > 0

    async def test_lexicon_triggered(self, client):
        res = await client.post(
            "/api/v1/guardrails/analyze",
            json={"text": "WIN FREE iPhone! Click here NOW!!!"},
        )
        assert res.status_code == 200
        data = res.json()
        # At least lexicon and ML should trigger
        layers = {layer["layer"]: layer for layer in data["layers"]}
        assert layers["lexicon"]["triggered"] is True
        assert data["action"] in ("flag", "block")
        assert "lexicon" in data["explanation"]

    async def test_regex_layer_signals(self, client):
        res = await client.post(
            "/api/v1/guardrails/analyze",
            json={"text": "Contact me at john@example.com or www.spam-site.com"},
        )
        assert res.status_code == 200
        layers = {layer["layer"]: layer for layer in res.json()["layers"]}
        regex = layers["regex"]
        assert regex["triggered"] is True
        assert "email" in regex["signals"] or "url" in regex["signals"]

    async def test_all_layers_present_in_response(self, client):
        res = await client.post("/api/v1/guardrails/analyze", json={"text": "hello"})
        layers = res.json()["layers"]
        assert len(layers) == 4
        # Each layer has required fields
        for layer in layers:
            assert "triggered" in layer
            assert "signals" in layer
            assert 0.0 <= layer["score"] <= 1.0


# ─── Business Dashboard ──────────────────────────────────


class TestBusiness:
    async def test_dashboard_structure(self, client):
        res = await client.get("/api/v1/business/dashboard")
        assert res.status_code == 200
        data = res.json()
        required_keys = [
            "moderation_quality",
            "funnel",
            "label_distribution",
            "feedback_summary",
            "false_positive_cost",
        ]
        for key in required_keys:
            assert key in data, f"missing {key}"

    async def test_funnel_values(self, client):
        res = await client.get("/api/v1/business/dashboard")
        funnel = res.json()["funnel"]
        assert funnel["total_predictions"] >= 0
        assert funnel["blocked"] >= 0
        assert funnel["allowed"] >= 0

    async def test_false_positive_cost(self, client):
        res = await client.get("/api/v1/business/dashboard")
        fp = res.json()["false_positive_cost"]
        assert fp["cost_per_fp_usd"] > 0
        assert fp["total_fp_cost_usd"] == round(fp["false_positives"] * fp["cost_per_fp_usd"], 2)


# ─── Active Learning ─────────────────────────────────────


class TestActiveLearning:
    async def test_uncertain_returns_structure(self, client):
        res = await client.get("/api/v1/active-learning/uncertain")
        assert res.status_code == 200
        data = res.json()
        assert "samples" in data
        assert "total_low_confidence" in data

    async def test_review_nonexistent_prediction(self, client):
        res = await client.post(
            "/api/v1/active-learning/review",
            json={"prediction_id": "nonexistent-id", "correct_label": "safe"},
        )
        # Should not crash — either 404 or error field
        assert res.status_code in (200, 404)

    async def test_entropy_ordering(self, client):
        """Samples should be ordered by entropy (most uncertain first)."""
        res = await client.get("/api/v1/active-learning/uncertain?limit=10")
        samples = res.json()["samples"]
        entropies = [s["entropy"] for s in samples]
        assert entropies == sorted(entropies, reverse=True)
