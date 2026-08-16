"""Demo Engine — orchestrated live demo scenario for interviews & portfolio.

Runs a scripted story through the whole platform:
  Phase 1: Baseline traffic (mixed safe/spam/toxic) via /predict
  Phase 2: Toxicity spike → alerting system fires
  Phase 3: Filter API under attack — blocks + pgvector similarity
  Phase 4: Human feedback loop — correct wrong predictions
  Phase 5: Retrain on corrected data → improved metrics
  Phase 6: Final report (before/after)

Progress is streamed to connected dashboard clients via the stream manager.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.api.routes.streaming import manager as stream_manager
from nexus.core.logging import get_logger

logger = get_logger("nexus.demo")

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

API_BASE = "http://127.0.0.1:8000/api/v1"

# Demo scenario messages
BASELINE_TRAFFIC = [
    ("Hello everyone! Loving the stream today 😊", "safe"),
    ("Great play! How did you do that?", "safe"),
    ("WIN a FREE iPhone! Click here NOW!", "spam"),
    ("Thanks for the tips, really helpful", "safe"),
    ("Earn $5000/day from home! No experience needed!", "spam"),
    ("GG everyone, well played", "safe"),
    ("Check out my channel for FREE giveaways!", "spam"),
    ("What's your setup? Looks amazing", "safe"),
]

TOXIC_SPIKE = [
    ("You are a complete idiot, uninstall and die", "toxic"),
    ("Worst player ever, kill yourself", "toxic"),
    ("You're trash at this game, go cry", "toxic"),
    ("Everyone here is so stupid and brainless", "toxic"),
    ("Shut up you worthless moron", "toxic"),
    ("You are a complete moron and a stupid idiot", "toxic"),
    ("Absolute garbage player, uninstall now", "toxic"),
    ("Nobody likes you, just leave", "toxic"),
]

FEEDBACK_CORRECTIONS = [
    ("That was absolutely brilliant!", "safe", "toxic"),  # predicted toxic, actually safe
    ("What a killer play, insane skills!", "safe", "toxic"),
    ("This offer is dangerous, be careful out there", "safe", "spam"),
]

demo_running = False


class DemoReport(BaseModel):
    started_at: str
    finished_at: str | None = None
    duration_sec: float = 0.0
    total_requests: int = 0
    predictions: list[dict] = Field(default_factory=list)
    alerts_fired: list[str] = Field(default_factory=list)
    blocked: int = 0
    allowed: int = 0
    feedback_applied: int = 0
    retrain_metrics: dict | None = None
    phase_log: list[str] = Field(default_factory=list)


_last_report: DemoReport | None = None


async def _emit(event: dict) -> None:
    """Broadcast demo progress to connected stream clients."""
    event["timestamp"] = time.time()
    await stream_manager.broadcast({"type": "demo", **event})


async def _phase(report: DemoReport, name: str) -> None:
    entry = f"[{datetime.now(UTC).strftime('%H:%M:%S')}] ▶ {name}"
    report.phase_log.append(entry)
    await _emit({"phase": name, "log": report.phase_log})
    logger.info("Demo phase", phase=name)


def _block_or_allow(label: str, confidence: float) -> str:
    if label in ("spam", "toxic") and confidence > 0.4:
        return "block"
    return "allow"


@router.post("/run")
async def run_demo() -> dict:
    """Run the full orchestrated demo scenario."""
    global demo_running, _last_report
    if demo_running:
        return {"status": "already_running"}

    demo_running = True
    report = DemoReport(started_at=datetime.now(UTC).isoformat())
    t0 = time.perf_counter()

    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=15.0) as client:
            # ─── Phase 1: Baseline traffic ───
            await _phase(report, "Phase 1/5: Baseline traffic (8 mixed messages)")
            for text, expected in BASELINE_TRAFFIC:
                res = (await client.post("/predict", json={"text": text})).json()
                report.total_requests += 1
                action = _block_or_allow(res["label"], res["confidence"])
                if action == "block":
                    report.blocked += 1
                else:
                    report.allowed += 1
                report.predictions.append(
                    {
                        "text": text,
                        "expected": expected,
                        "got": res["label"],
                        "confidence": res["confidence"],
                    }
                )
                await _emit(
                    {
                        "event": "prediction",
                        "text": text,
                        "label": res["label"],
                        "confidence": res["confidence"],
                        "action": action,
                        "latency_ms": res.get("processing_time_ms", 0),
                        "expected": expected,
                    }
                )
                await asyncio.sleep(0.6)

            # ─── Phase 2: Toxicity spike → alerts ───
            await _phase(report, "Phase 2/5: Toxicity spike — raid simulation")
            for text, expected in TOXIC_SPIKE:
                res = (await client.post("/predict", json={"text": text})).json()
                report.total_requests += 1
                action = _block_or_allow(res["label"], res["confidence"])
                if action == "block":
                    report.blocked += 1
                else:
                    report.allowed += 1
                report.predictions.append(
                    {
                        "text": text,
                        "expected": expected,
                        "got": res["label"],
                        "confidence": res["confidence"],
                    }
                )
                await _emit(
                    {
                        "event": "prediction",
                        "text": text,
                        "label": res["label"],
                        "confidence": res["confidence"],
                        "action": action,
                        "latency_ms": res.get("processing_time_ms", 0),
                        "expected": expected,
                    }
                )
                await asyncio.sleep(0.35)

            # Check alerts fired
            await asyncio.sleep(1.0)
            alerts = (await client.get("/alerts/history")).json().get("alerts", [])
            report.alerts_fired = [a["type"] for a in alerts]
            await _phase(
                report,
                f"Phase 2 done: {len(report.alerts_fired)} alert(s) fired "
                f"({', '.join(set(report.alerts_fired)) or 'none'})",
            )

            # ─── Phase 3: Filter API under attack ───
            await _phase(report, "Phase 3/5: Filter API — production rules + similarity")
            filter_rules = {
                "block_labels": ["spam", "toxic"],
                "flag_labels": [],
                "threshold": 0.3,
                "use_similarity_boost": True,
            }
            attack_texts = [
                "Get rich quick! Free money!",
                "You are stupid, die",
                "Buy followers cheap!!! Link in bio",
            ]
            for text in attack_texts:
                res = (
                    await client.post(
                        "/filter",
                        json={"text": text, "rules": filter_rules, "source": "demo"},
                    )
                ).json()
                report.total_requests += 1
                similar = len(res.get("similar_matches", []))
                await _emit(
                    {
                        "event": "filter",
                        "text": text,
                        "label": res.get("label"),
                        "confidence": res.get("confidence"),
                        "action": res.get("action"),
                        "latency_ms": res.get("latency_ms"),
                        "similar_matches": similar,
                    }
                )
                await asyncio.sleep(0.5)

            # ─── Phase 4: Human feedback ───
            await _phase(report, "Phase 4/5: Human-in-the-loop feedback")
            for text, correct, _predicted_as in FEEDBACK_CORRECTIONS:
                # Predict then correct it
                pred = (await client.post("/predict", json={"text": text})).json()
                report.total_requests += 1
                await client.post(
                    "/feedback",
                    json={"prediction_id": pred["prediction_id"], "feedback": "down"},
                )
                # Add corrected label to dataset
                await client.post("/dataset/add", json={"text": text, "label": correct})
                report.feedback_applied += 1
                await _emit(
                    {
                        "event": "feedback",
                        "text": text,
                        "predicted": pred["label"],
                        "corrected_to": correct,
                    }
                )
                await asyncio.sleep(0.5)

            # ─── Phase 5: Retrain ───
            await _phase(report, "Phase 5/5: Retrain on corrected data")
            retrain = (await client.post("/dataset/retrain")).json()
            report.retrain_metrics = retrain.get("metrics") or {}
            acc = report.retrain_metrics.get("accuracy")
            await _phase(report, f"Retrained: accuracy={acc}")

        report.finished_at = datetime.now(UTC).isoformat()
        report.duration_sec = round(time.perf_counter() - t0, 2)
        _last_report = report
        await _emit({"event": "done", "report": report.model_dump()})
        return {"status": "completed", "duration_sec": report.duration_sec}

    except Exception as e:
        logger.error("Demo failed", error=str(e))
        report.finished_at = datetime.now(UTC).isoformat()
        report.phase_log.append(f"ERROR: {e}")
        _last_report = report
        await _emit({"event": "error", "message": str(e)})
        return {"status": "failed", "error": str(e)}
    finally:
        demo_running = False


@router.get("/status")
async def demo_status() -> dict:
    """Check demo status and last report."""
    return {
        "running": demo_running,
        "last_report": _last_report.model_dump() if _last_report else None,
    }


@router.get("/report")
async def demo_report() -> dict:
    """Get the last demo report."""
    if _last_report is None:
        return {"status": "never_run"}
    return _last_report.model_dump()
