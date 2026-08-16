"""Alerting system — webhook notifications for anomalies.

Triggers alerts when:
- Drift exceeds threshold
- Toxicity spike (>30% of messages in a time window)
- Model latency exceeds threshold
- Error rate spikes

Sends notifications to configured webhook URLs (Telegram, Slack, generic).
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.core.logging import get_logger

logger = get_logger("nexus.alerting")

router = APIRouter(prefix="/api/v1/alerts", tags=["alerting"])

# ─── State ────────────────────────────────────────────────

# Rolling window of recent predictions for spike detection
_recent_predictions: deque[dict] = deque(maxlen=200)

# Active webhook configurations
_webhooks: list[dict] = []

# Alert history
_alert_history: list[dict] = []

# Configured thresholds
THRESHOLDS = {
    "toxicity_rate": 0.30,  # 30% toxic in window
    "min_window_size": 10,  # need at least 10 messages
    "latency_ms": 500,  # 500ms threshold
    "drift_score": 0.5,  # drift score threshold
}


# ─── Models ───────────────────────────────────────────────


class WebhookConfig(BaseModel):
    url: str = Field(..., min_length=10)
    name: str = Field(default="default")
    enabled: bool = True
    events: list[str] = Field(default=["toxicity_spike", "drift", "latency", "error_rate"])


class AlertEvent(BaseModel):
    type: str
    severity: str  # info, warning, critical
    message: str
    value: float
    threshold: float
    timestamp: str


# ─── Public API ───────────────────────────────────────────


@router.post("/webhooks")
async def add_webhook(config: WebhookConfig) -> dict:
    """Register a webhook endpoint for alert notifications."""
    _webhooks.append(config.model_dump())
    logger.info("Webhook added", name=config.name, url=config.url[:50])
    return {"status": "registered", "total_webhooks": len(_webhooks)}


@router.get("/webhooks")
async def list_webhooks() -> dict:
    """List registered webhooks."""
    return {"webhooks": _webhooks}


@router.delete("/webhooks/{name}")
async def delete_webhook(name: str) -> dict:
    """Remove a webhook by name."""
    global _webhooks
    before = len(_webhooks)
    _webhooks = [w for w in _webhooks if w["name"] != name]
    return {"status": "removed", "deleted": before - len(_webhooks)}


@router.get("/history")
async def alert_history(limit: int = 20) -> dict:
    """Get recent alerts."""
    return {"alerts": _alert_history[-limit:]}


@router.get("/thresholds")
async def get_thresholds() -> dict:
    """Get current alert thresholds."""
    return THRESHOLDS


@router.put("/thresholds")
async def update_thresholds(
    toxicity_rate: float | None = None,
    latency_ms: float | None = None,
    drift_score: float | None = None,
) -> dict:
    """Update alert thresholds."""
    if toxicity_rate is not None:
        THRESHOLDS["toxicity_rate"] = toxicity_rate
    if latency_ms is not None:
        THRESHOLDS["latency_ms"] = latency_ms
    if drift_score is not None:
        THRESHOLDS["drift_score"] = drift_score
    return {"status": "updated", "thresholds": THRESHOLDS}


# ─── Internal: record + detect + notify ───────────────────


def record_prediction(label: str, confidence: float, latency_ms: float) -> None:
    """Record a prediction for anomaly detection. Called from filter/predict."""
    _recent_predictions.append(
        {
            "label": label,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }
    )

    # Check for toxicity spike
    _check_toxicity_spike()

    # Check for latency spike
    if latency_ms > THRESHOLDS["latency_ms"]:
        _create_alert(
            "latency",
            "warning",
            f"High latency: {latency_ms:.0f}ms > {THRESHOLDS['latency_ms']:.0f}ms",
            latency_ms,
            THRESHOLDS["latency_ms"],
        )


def _check_toxicity_spike() -> None:
    """Detect sudden spike in toxic/spam content."""
    window_size = THRESHOLDS["min_window_size"]
    if len(_recent_predictions) < window_size:
        return

    recent = list(_recent_predictions)[-window_size:]
    toxic_count = sum(1 for p in recent if p["label"] in ("toxic", "spam"))
    rate = toxic_count / len(recent)

    if rate > THRESHOLDS["toxicity_rate"]:
        _create_alert(
            "toxicity_spike",
            "critical",
            f"Toxicity spike detected: {rate:.0%} of recent messages are toxic/spam",
            rate,
            THRESHOLDS["toxicity_rate"],
        )


def record_drift(drift_score: float, severity: str) -> None:
    """Record a drift event. Called from drift analysis."""
    if drift_score > THRESHOLDS["drift_score"]:
        _create_alert(
            "drift",
            "critical" if severity == "high" else "warning",
            f"Drift detected: score {drift_score:.2f} > {THRESHOLDS['drift_score']:.2f}",
            drift_score,
            THRESHOLDS["drift_score"],
        )


def _create_alert(
    alert_type: str,
    severity: str,
    message: str,
    value: float,
    threshold: float,
) -> None:
    """Create an alert and notify webhooks."""
    # Deduplicate: skip if same type in last 60s
    now = time.time()
    for a in _alert_history[-5:]:
        if a["type"] == alert_type and now - a["_ts"] < 60:
            return

    alert = {
        "type": alert_type,
        "severity": severity,
        "message": message,
        "value": round(value, 4),
        "threshold": threshold,
        "timestamp": datetime.now(UTC).isoformat(),
        "_ts": now,
    }
    _alert_history.append(alert)
    # Keep history bounded
    if len(_alert_history) > 100:
        _alert_history.pop(0)

    logger.warning("Alert fired", type=alert_type, severity=severity, message=message)

    # Fire webhooks asynchronously
    asyncio.create_task(_notify_webhooks(alert))


async def _notify_webhooks(alert: dict) -> None:
    """Send alert to all registered webhooks."""
    if not _webhooks:
        return

    payload = {k: v for k, v in alert.items() if not k.startswith("_")}

    for wh in _webhooks:
        if not wh["enabled"]:
            continue
        if alert["type"] not in wh["events"]:
            continue
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(wh["url"], json=payload)
        except Exception as e:
            logger.error("Webhook delivery failed", webhook=wh["name"], error=str(e))
