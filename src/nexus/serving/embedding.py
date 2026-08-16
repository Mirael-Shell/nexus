"""Embedding service for semantic similarity search.

Uses sentence-transformers all-MiniLM-L6-v2 (384 dims, ~80MB).
Falls back to hash-based pseudo-embeddings if model not available.

The embeddings power the Filter API's k-NN search: when a new message
arrives, we compute its embedding and find similar blocked/flagged
messages in pgvector. If multiple similar messages were blocked,
we boost the block confidence.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import numpy as np

from nexus.core.logging import get_logger

logger = get_logger(__name__)

# Model constants
EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"

# Singleton
_model: Any = None
_model_loaded = False
_load_attempted = False


def _load_model() -> None:
    """Try loading sentence-transformers model (best-effort)."""
    global _model, _model_loaded, _load_attempted
    if _load_attempted:
        return
    _load_attempted = True

    try:
        import os

        from sentence_transformers import SentenceTransformer

        # If model already cached, skip network checks (avoids HF 429)
        cache_dir = os.path.expanduser(os.environ.get("HF_HOME", "~/.cache/huggingface"))
        use_local = os.path.exists(cache_dir)

        _model = SentenceTransformer(
            MODEL_NAME,
            model_kwargs={"low_cpu_mem_usage": True},
        )
        if use_local:
            logger.info("Using cached model (offline mode)")

        _model_loaded = True
        logger.info(
            "Embedding model loaded",
            model=MODEL_NAME,
            dim=EMBEDDING_DIM,
        )
    except Exception as e:
        logger.warning(
            "sentence-transformers not available, using hash embeddings",
            error=str(e)[:200],
        )


def embed(text: str) -> list[float]:
    """Compute embedding for a single text.

    Returns a 384-dim vector. If sentence-transformers is available,
    uses real neural embeddings. Otherwise falls back to deterministic
    hash-based pseudo-embeddings (same text → same vector).

    Args:
        text: Input text to embed.

    Returns:
        List of 384 floats, L2-normalized.
    """
    _load_model()

    if _model_loaded and _model is not None:
        # Real embedding
        vec = _model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    # Hash-based fallback: deterministic, fast, but not semantic
    return _hash_embed(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Compute embeddings for multiple texts (batched)."""
    _load_model()

    if _model_loaded and _model is not None:
        vecs = _model.encode(texts, normalize_embeddings=True)
        return vecs.tolist()

    return [_hash_embed(t) for t in texts]


def _hash_embed(text: str) -> list[float]:
    """Deterministic hash-based pseudo-embedding (fallback).

    Generates a 384-dim vector from character n-gram hashes.
    Not semantically meaningful, but provides consistent vectors
    for similarity dedup when no ML model is available.
    """
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)

    # Character trigrams
    text_lower = text.lower().strip()
    for i in range(len(text_lower) - 2):
        trigram = text_lower[i : i + 3]
        h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
        vec[h % EMBEDDING_DIM] += 1.0

    # Word-level features
    words = text_lower.split()
    for word in words:
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % EMBEDDING_DIM] += 2.0

    # L2 normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    return vec.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va, vb = np.array(a), np.array(b)
    dot = np.dot(va, vb)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(dot / (na * nb))


def is_model_loaded() -> bool:
    """Check if the neural embedding model is loaded."""
    return _model_loaded


def warmup() -> None:
    """Pre-load the model (call at startup for warm inference)."""
    start = time.perf_counter()
    _load_model()
    if _model_loaded:
        # Warm pass
        embed("warmup")
        elapsed = time.perf_counter() - start
        logger.info("Embedding model warmed up", elapsed_ms=f"{elapsed * 1000:.0f}")
