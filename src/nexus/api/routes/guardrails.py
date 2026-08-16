"""Guardrails — multi-layer content moderation pipeline.

Layer 1: Rule-based (regex patterns for URLs, emails, phone numbers)
Layer 2: Lexicon (banned words list — fast O(1) lookup)
Layer 3: ML classifier (TF-IDF + LogisticRegression)
Layer 4: Embedding similarity (pgvector kNN against known violations)

Each layer contributes signals; final decision is a weighted combination.
"""

from __future__ import annotations

import re
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.core.logging import get_logger
from nexus.serving.engine import get_engine

logger = get_logger("nexus.guardrails")

router = APIRouter(prefix="/api/v1/guardrails", tags=["guardrails"])

# ─── Layer 1: Regex patterns ─────────────────────────────

REGEX_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "url": [
        re.compile(r"https?://\S+", re.IGNORECASE),
        re.compile(r"www\.\S+\.\w{2,}", re.IGNORECASE),
        re.compile(r"\bbit\.ly/\S+", re.IGNORECASE),
        re.compile(r"\btinyurl\.com/\S+", re.IGNORECASE),
    ],
    "email": [
        re.compile(r"\b[\w.-]+@[\w.-]+\.\w{2,}\b", re.IGNORECASE),
    ],
    "phone": [
        re.compile(r"\b\+?\d{1,3}?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    ],
    "excessive_caps": [
        re.compile(r"\b[A-Z]{6,}\b"),  # ALL CAPS words 6+ chars
    ],
    "excessive_punctuation": [
        re.compile(r"[!?]{4,}"),  # 4+ ! or ? in a row
    ],
}

# ─── Layer 2: Banned words lexicon ───────────────────────

BANNED_WORDS = {
    # Severe
    "kill yourself",
    "kys",
    "go die",
    "uninstall and die",
    "stupid idiot",
    "complete moron",
    "brain dead",
    # Spam indicators
    "free iphone",
    "free money",
    "click here now",
    "earn from home",
    "get rich",
    "crypto giveaway",
}

# Weights for each layer's contribution
LAYER_WEIGHTS = {
    "regex": 0.3,
    "lexicon": 0.5,
    "ml": 1.0,
    "embedding": 0.4,
}


# ─── Models ───────────────────────────────────────────────


class GuardrailRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class LayerResult(BaseModel):
    layer: str
    triggered: bool
    signals: list[str]
    score: float  # 0.0 to 1.0


class GuardrailResponse(BaseModel):
    action: str  # allow, flag, block
    final_score: float
    ml_label: str
    ml_confidence: float
    layers: list[LayerResult]
    explanation: str
    latency_ms: float


# ─── Endpoint ─────────────────────────────────────────────


@router.post("/analyze", response_model=GuardrailResponse)
async def analyze_with_guardrails(req: GuardrailRequest) -> GuardrailResponse:
    """Multi-layer moderation pipeline.

    Each layer adds signals. The final score is a weighted combination.
    A high score means more layers agree the content is problematic.
    """
    t0 = time.perf_counter()
    text = req.text.strip()
    text_lower = text.lower()
    layers: list[LayerResult] = []

    # ─── Layer 1: Regex ───
    regex_signals: list[str] = []
    for category, patterns in REGEX_PATTERNS.items():
        for pat in patterns:
            if pat.search(text):
                regex_signals.append(category)

    regex_score = min(len(regex_signals) * 0.2, 1.0)
    layers.append(
        LayerResult(
            layer="regex",
            triggered=len(regex_signals) > 0,
            signals=regex_signals,
            score=regex_score,
        )
    )

    # ─── Layer 2: Lexicon ───
    lexicon_signals = [w for w in BANNED_WORDS if w in text_lower]
    lexicon_score = min(len(lexicon_signals) * 0.5, 1.0)
    layers.append(
        LayerResult(
            layer="lexicon",
            triggered=len(lexicon_signals) > 0,
            signals=lexicon_signals,
            score=lexicon_score,
        )
    )

    # ─── Layer 3: ML Classifier ───
    engine = get_engine()
    result = engine.predict(text)
    ml_score = result.confidence if result.label in ("spam", "toxic") else 0.0
    layers.append(
        LayerResult(
            layer="ml",
            triggered=result.label in ("spam", "toxic") and result.confidence > 0.3,
            signals=[f"label={result.label}({result.confidence:.2f})"],
            score=ml_score,
        )
    )

    # ─── Layer 4: Embedding similarity (skip if DB unavailable) ───
    # For now, we use a simple heuristic based on text similarity
    # to recent blocked messages
    embedding_score = 0.0
    embedding_signals: list[str] = []
    try:
        from nexus.serving.embedding import cosine_similarity, embed, is_model_loaded

        if is_model_loaded():
            query_vec = embed(text)
            # Check against a small in-memory cache of blocked texts
            # (production would query pgvector)
            from nexus.api.routes.alerting import _recent_predictions

            recent_blocked = [
                p for p in _recent_predictions if p.get("label") in ("spam", "toxic")
            ][-20:]

            max_sim = 0.0
            for p in recent_blocked:
                p_vec = embed(p.get("text", ""))
                sim = cosine_similarity(query_vec, p_vec)
                if sim > max_sim:
                    max_sim = sim
                    if sim > 0.85:
                        embedding_signals.append(f"similar_to_blocked({sim:.2f})")

            embedding_score = max_sim if max_sim > 0.85 else 0.0
    except Exception as e:
        logger.debug("Embedding layer skipped", error=str(e))

    layers.append(
        LayerResult(
            layer="embedding",
            triggered=embedding_score > 0,
            signals=embedding_signals,
            score=embedding_score,
        )
    )

    # ─── Weighted combination ───
    final_score = sum(layer.score * LAYER_WEIGHTS.get(layer.layer, 0.5) for layer in layers)
    # Normalize
    total_weight = sum(LAYER_WEIGHTS.values())
    final_score = min(final_score / total_weight, 1.0) if total_weight else 0.0

    # ─── Decision ───
    if final_score >= 0.6:
        action = "block"
    elif final_score >= 0.3:
        action = "flag"
    else:
        action = "allow"

    latency = (time.perf_counter() - t0) * 1000

    # Explanation
    triggered_layers = [lyr for lyr in layers if lyr.triggered]
    if not triggered_layers:
        explanation = "No layers triggered — content appears clean."
    else:
        parts = [f"{lyr.layer}({', '.join(lyr.signals)})" for lyr in triggered_layers]
        explanation = f"Triggered by: {' + '.join(parts)}"

    return GuardrailResponse(
        action=action,
        final_score=round(final_score, 4),
        ml_label=result.label,
        ml_confidence=round(result.confidence, 4),
        layers=layers,
        explanation=explanation,
        latency_ms=round(latency, 2),
    )


@router.get("/layers")
async def get_layer_info() -> dict:
    """Get information about guardrail layers and weights."""
    return {
        "layers": [
            {
                "name": "regex",
                "description": "URL/email/phone/caps detection",
                "weight": LAYER_WEIGHTS["regex"],
            },
            {
                "name": "lexicon",
                "description": "Banned phrases list",
                "weight": LAYER_WEIGHTS["lexicon"],
            },
            {
                "name": "ml",
                "description": "TF-IDF + LogisticRegression classifier",
                "weight": LAYER_WEIGHTS["ml"],
            },
            {
                "name": "embedding",
                "description": "Semantic similarity to blocked content",
                "weight": LAYER_WEIGHTS["embedding"],
            },
        ],
        "decision_thresholds": {"allow": "<0.3", "flag": "0.3-0.6", "block": ">=0.6"},
    }
