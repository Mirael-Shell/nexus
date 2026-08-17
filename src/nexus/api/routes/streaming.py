"""Real-time WebSocket streaming endpoint for live content moderation.

Provides a live feed of moderation decisions via WebSocket.
Includes a chat simulator that generates synthetic messages.
"""

import asyncio
import json
import random
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nexus.core.logging import get_logger
from nexus.serving.engine import get_engine

logger = get_logger("nexus.streaming")

router = APIRouter(prefix="/api/v1/stream", tags=["streaming"])

# Sample messages for the chat simulator
SIMULATOR_MESSAGES = [
    # Safe
    ("Hello everyone! Loving the stream today 😊", "safe"),
    ("Great play! How did you do that?", "safe"),
    ("Thanks for the tips, really helpful", "safe"),
    ("First time here, this is awesome!", "safe"),
    ("Can someone explain how this game works?", "safe"),
    ("GG everyone, well played", "safe"),
    ("What's your setup? Looks amazing", "safe"),
    ("Happy Friday everyone! 🎉", "safe"),
    # Spam
    ("WIN a FREE iPhone! Click here NOW!", "spam"),
    ("Earn $5000/day from home! No experience needed!", "spam"),
    ("Check out my channel for FREE giveaways!", "spam"),
    ("BUY NOW! 90% OFF! Limited time offer!!!", "spam"),
    ("Click my link for FREE Bitcoin 🚀🚀🚀", "spam"),
    ("Follow me for daily giveaways and free stuff!", "spam"),
    # Toxic
    ("You are a complete idiot, uninstall and die", "toxic"),
    ("Worst player ever, kill yourself", "toxic"),
    ("You're trash at this game, go cry", "toxic"),
    ("Everyone here is so stupid and brainless", "toxic"),
    ("Shut up you worthless moron", "toxic"),
]


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("WebSocket connected", total=len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)
        logger.info("WebSocket disconnected", total=len(self.active))

    async def broadcast(self, data: dict) -> None:
        """Send data to all connected clients."""
        text = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
simulator_running = False


async def run_simulator(interval_seconds: float = 2.0) -> None:
    """Generate synthetic messages and broadcast moderation decisions."""
    global simulator_running
    engine = get_engine()
    logger.info("Chat simulator started", interval=f"{interval_seconds}s")

    while simulator_running:
        text, expected = random.choice(SIMULATOR_MESSAGES)
        result = await asyncio.to_thread(engine.predict, text)

        event = {
            "type": "moderation",
            "text": text,
            "expected": expected,
            "label": result.label,
            "confidence": round(result.confidence, 4),
            "action": _decide_action(result.label, result.confidence),
            "latency_ms": round(result.processing_time_ms, 2),
            "timestamp": time.time(),
        }
        await manager.broadcast(event)
        await asyncio.sleep(interval_seconds)

    logger.info("Chat simulator stopped")


def _decide_action(label: str, confidence: float) -> str:
    if confidence < 0.4:
        return "allow"
    if label in ("spam", "toxic"):
        return "block"
    return "allow"


@router.websocket("/ws")
async def stream_endpoint(ws: WebSocket) -> None:
    """WebSocket endpoint for live moderation feed."""
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "moderate":
                text = msg.get("text", "")
                engine = get_engine()
                result = await asyncio.to_thread(engine.predict, text)
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "moderation",
                            "text": text,
                            "label": result.label,
                            "confidence": round(result.confidence, 4),
                            "action": _decide_action(result.label, result.confidence),
                            "latency_ms": round(result.processing_time_ms, 2),
                            "timestamp": time.time(),
                        }
                    )
                )
    except WebSocketDisconnect:
        manager.disconnect(ws)


@router.post("/simulator/start")
async def start_simulator(interval: float = 2.0) -> dict:
    """Start the chat simulator."""
    global simulator_running
    if simulator_running:
        return {"status": "already_running"}
    simulator_running = True
    asyncio.create_task(run_simulator(interval))
    return {"status": "started", "interval": interval}


@router.post("/simulator/stop")
async def stop_simulator() -> dict:
    """Stop the chat simulator."""
    global simulator_running
    simulator_running = False
    return {"status": "stopped"}


@router.get("/simulator/status")
async def simulator_status() -> dict:
    """Check simulator status."""
    return {"running": simulator_running, "connections": len(manager.active)}
