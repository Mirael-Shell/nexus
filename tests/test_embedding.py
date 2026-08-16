"""Tests for the embedding service."""

from nexus.serving.embedding import (
    EMBEDDING_DIM,
    cosine_similarity,
    embed,
    embed_batch,
    is_model_loaded,
)


def test_embed_returns_correct_dim() -> None:
    """Embedding should return a vector of correct dimensionality."""
    vec = embed("hello world")
    assert len(vec) == EMBEDDING_DIM  # 384


def test_embed_returns_floats() -> None:
    """Embedding values should be floats in [-1, 1] range."""
    vec = embed("test message")
    for v in vec:
        assert isinstance(v, float)
        assert -1.0 <= v <= 1.0


def test_embed_deterministic() -> None:
    """Same text should produce same embedding (both neural and hash)."""
    v1 = embed("deterministic test")
    v2 = embed("deterministic test")
    assert v1 == v2


def test_embed_batch() -> None:
    """Batch embedding should return one vector per text."""
    texts = ["hello", "world", "spam message"]
    vectors = embed_batch(texts)
    assert len(vectors) == len(texts)
    for vec in vectors:
        assert len(vec) == EMBEDDING_DIM


def test_cosine_similarity_identical() -> None:
    """Cosine similarity of identical vectors should be ~1.0."""
    vec = embed("test message")
    sim = cosine_similarity(vec, vec)
    assert sim > 0.99


def test_cosine_similarity_different() -> None:
    """Cosine similarity of very different texts should be lower."""
    v1 = embed("WIN FREE iPhone click here!!!")
    v2 = embed("Hello, nice weather today, let's go for a walk")
    sim = cosine_similarity(v1, v2)
    # Different content should have lower similarity than identical
    assert sim < 0.99


def test_cosine_similarity_zero_vector() -> None:
    """Cosine similarity with zero vector should return 0."""
    v1 = [0.0] * EMBEDDING_DIM
    v2 = [1.0] * EMBEDDING_DIM
    sim = cosine_similarity(v1, v2)
    assert sim == 0.0


def test_is_model_loaded_returns_bool() -> None:
    """is_model_loaded should return a boolean."""
    result = is_model_loaded()
    assert isinstance(result, bool)
