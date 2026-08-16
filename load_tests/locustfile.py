"""Locust load test scenarios for NEXUS API.

Usage:
    make load-test                  # quick smoke (1 min, 10 users)
    make load-test-heavy            # heavy (3 min, 50 users)
    locust -f load_tests/locustfile.py --host http://localhost:8000 --headless

Scenarios:
    - MixedInferenceUser: /predict with random texts (weighted classes)
    - FilterApiUser:      /filter with production rules (embedding + pgvector)
    - GuardrailsUser:     /guardrails/analyze (4-layer pipeline)
"""

import random

from locust import HttpUser, between, task

TEXTS_SAFE = [
    "Hello everyone! Loving the stream today 😊",
    "Great play! How did you do that?",
    "Thanks for the tips, really helpful",
    "First time here, this is awesome!",
    "GG everyone, well played",
    "What's your setup? Looks amazing",
    "Can someone explain how this game works?",
    "Happy Friday everyone! 🎉",
]

TEXTS_SPAM = [
    "WIN a FREE iPhone! Click here NOW!",
    "Earn $5000/day from home! No experience needed!",
    "Check out my channel for FREE giveaways!",
    "BUY NOW! 90% OFF! Limited time offer!!!",
    "Click my link for FREE Bitcoin 🚀🚀🚀",
    "Follow me for daily giveaways and free stuff!",
]

TEXTS_TOXIC = [
    "You are a complete idiot, uninstall and die",
    "Worst player ever, kill yourself",
    "You're trash at this game, go cry",
    "Everyone here is so stupid and brainless",
    "Shut up you worthless moron",
]

FILTER_RULES = {
    "block_labels": ["spam", "toxic"],
    "flag_labels": [],
    "threshold": 0.5,
    "use_similarity_boost": True,
}

SOURCES = ["twitch", "youtube", "discord", "api"]


def weighted_text() -> str:
    """70% safe, 20% spam, 10% toxic — realistic chat distribution."""
    r = random.random()
    if r < 0.70:
        return random.choice(TEXTS_SAFE)
    if r < 0.90:
        return random.choice(TEXTS_SPAM)
    return random.choice(TEXTS_TOXIC)


class MixedInferenceUser(HttpUser):
    """Hits /predict — the core classification endpoint."""

    wait_time = between(0.1, 0.5)
    weight = 3

    @task
    def predict(self) -> None:
        self.client.post("/api/v1/predict", json={"text": weighted_text()})


class FilterApiUser(HttpUser):
    """Hits /filter — production endpoint with embedding + pgvector."""

    wait_time = between(0.2, 0.8)
    weight = 2

    @task
    def filter_content(self) -> None:
        self.client.post(
            "/api/v1/filter",
            json={
                "text": weighted_text(),
                "rules": FILTER_RULES,
                "source": random.choice(SOURCES),
            },
        )


class GuardrailsUser(HttpUser):
    """Hits /guardrails/analyze — full 4-layer pipeline."""

    wait_time = between(0.3, 1.0)
    weight = 1

    @task
    def guardrails(self) -> None:
        self.client.post("/api/v1/guardrails/analyze", json={"text": weighted_text()})


class ReadOnlyUser(HttpUser):
    """Hits dashboard endpoints — simulates ops/PM viewing dashboards."""

    wait_time = between(1.0, 3.0)
    weight = 1

    @task(3)
    def business(self) -> None:
        self.client.get("/api/v1/business/dashboard")

    @task(2)
    def filter_stats(self) -> None:
        self.client.get("/api/v1/filter/stats")

    @task(2)
    def dataset_stats(self) -> None:
        self.client.get("/api/v1/dataset/stats")

    @task(1)
    def health(self) -> None:
        self.client.get("/api/v1/health")
