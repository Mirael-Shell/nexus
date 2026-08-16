"""Inference engine — TF-IDF + LogisticRegression classifier.

Loads a trained model from data/model.joblib (created by training.pipeline).
If no model exists, falls back to keyword-based classification.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from nexus.core.config import get_settings
from nexus.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ─── Paths ──────────────────────────────────────────────

# __file__ = .../src/nexus/serving/engine.py → 4 levels up = project root or /app/
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_MODEL_PATH = _DATA_DIR / "model.joblib"
_META_PATH = _DATA_DIR / "model_meta.json"


@dataclass
class InferenceResult:
    """Output of a single inference call."""

    label: str
    confidence: float
    all_probabilities: dict[str, float]
    model_version: str
    processing_time_ms: float


# ─── Keyword fallback (if no trained model) ─────────────

_SPAM_KEYWORDS = {
    "free",
    "win",
    "winner",
    "prize",
    "click",
    "subscribe",
    "buy now",
    "discount",
    "offer",
    "deal",
    "limited",
    "promo",
    "bonus",
    "gift",
    "click here",
    "act now",
    "urgent",
    "money",
    "cash",
    "credit",
    "earn",
    "income",
    "lottery",
    "jackpot",
    "guaranteed",
    "million",
    "invest",
    "profit",
    "rich",
    "passive income",
    "miracle",
    "weight loss",
}

_TOXIC_KEYWORDS = {
    "hate",
    "stupid",
    "idiot",
    "kill",
    "die",
    "ugly",
    "moron",
    "trash",
    "garbage",
    "shut up",
    "dumb",
    "loser",
    "freak",
    "scum",
    "pathetic",
    "worthless",
    "braindead",
    "uninstall",
    "waste of space",
    "nobody likes",
    "annoying",
    "miserable",
    "go away",
    "bitch",
    "fuck",
    "asshole",
    "bastard",
    "crap",
    "suck",
    "damn",
}


def _keyword_predict(text: str) -> InferenceResult:
    """Fallback keyword-based classifier."""
    import math
    import random

    text_lower = text.lower()
    spam_hits = sum(1 for kw in _SPAM_KEYWORDS if kw in text_lower)
    toxic_hits = sum(1 for kw in _TOXIC_KEYWORDS if kw in text_lower)

    scores = {
        "safe": 1.0 + random.uniform(0, 0.3),
        "spam": spam_hits * 0.8 + random.uniform(0, 0.2),
        "toxic": toxic_hits * 1.0 + random.uniform(0, 0.2),
    }

    max_score = max(scores.values())
    exp_scores = {k: math.exp(v - max_score) for k, v in scores.items()}
    total = sum(exp_scores.values())
    probs = {k: v / total for k, v in exp_scores.items()}

    label = max(probs, key=lambda k: probs[k])

    return InferenceResult(
        label=label,
        confidence=round(probs[label], 4),
        all_probabilities={k: round(v, 4) for k, v in probs.items()},
        model_version="keyword-fallback-v0.1.0",
        processing_time_ms=0.01,
    )


# ─── Trained model engine ───────────────────────────────


class TrainedInferenceEngine:
    """TF-IDF + LogisticRegression inference engine.

    Loads a trained sklearn pipeline from disk. If no model exists,
    falls back to keyword-based classification.
    """

    def __init__(self) -> None:
        self._model = None
        self._meta: dict = {}
        self._model_version = "keyword-fallback-v0.1.0"
        self._load_model()

    def _load_model(self) -> None:
        """Try loading the trained model from disk."""
        import joblib

        if _MODEL_PATH.exists():
            try:
                self._model = joblib.load(_MODEL_PATH)
                if _META_PATH.exists():
                    with open(_META_PATH) as f:
                        self._meta = json.load(f)
                    self._model_version = self._meta.get("model_version", "tfidf-logreg-unknown")
                else:
                    self._model_version = "tfidf-logreg-loaded"

                logger.info(
                    "Trained model loaded",
                    path=str(_MODEL_PATH),
                    version=self._model_version,
                    accuracy=self._meta.get("accuracy", "?"),
                )
            except Exception as e:
                logger.warning("Failed to load model, using fallback", error=str(e))
                self._model = None
        else:
            logger.info("No trained model found, using keyword fallback", path=str(_MODEL_PATH))

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def predict(self, text: str) -> InferenceResult:
        """Classify text and return label + probabilities."""
        start = time.perf_counter()

        if self._model is None:
            result = _keyword_predict(text)
            result.processing_time_ms = (time.perf_counter() - start) * 1000
            return result

        # Use trained model

        # Get probabilities
        proba = self._model.predict_proba([text])[0]
        classes = self._model.classes_

        # Map to label dict
        probs = {}
        for cls, p in zip(classes, proba, strict=False):
            probs[str(cls)] = round(float(p), 4)

        # Ensure all labels present
        for label in ("safe", "spam", "toxic"):
            if label not in probs:
                probs[label] = 0.0

        label = max(probs, key=lambda k: probs[k])
        confidence = probs[label]

        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Prediction made",
            label=label,
            confidence=f"{confidence:.3f}",
            time_ms=f"{elapsed_ms:.1f}",
            model=self._model_version,
        )

        return InferenceResult(
            label=label,
            confidence=round(confidence, 4),
            all_probabilities=probs,
            model_version=self._model_version,
            processing_time_ms=round(elapsed_ms, 2),
        )

    def reload(self) -> None:
        """Reload model from disk (after retraining)."""
        self._model = None
        self._meta = {}
        self._model_version = "keyword-fallback-v0.1.0"
        self._load_model()


# Singleton
_engine: TrainedInferenceEngine | None = None


def get_engine() -> TrainedInferenceEngine:
    """Return the inference engine singleton."""
    global _engine
    if _engine is None:
        _engine = TrainedInferenceEngine()
    return _engine


def reload_engine() -> None:
    """Reload the engine after model retraining."""
    global _engine
    if _engine is not None:
        _engine.reload()
        logger.info("Engine reloaded", version=_engine.model_version)
