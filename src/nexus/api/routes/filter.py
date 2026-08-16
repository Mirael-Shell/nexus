"""Filter API — production-grade content moderation endpoint.

POST /api/v1/filter
    Classify text, apply rules, compute embedding, store in DB,
    and return an action: allow / block / flag.

Designed for integration with Twitch bots, YouTube comment moderation,
Discord bots, and other real-time platforms.

Unlike /predict, this endpoint:
- Applies configurable rules (which labels to block, threshold)
- Computes and stores embeddings for semantic similarity
- Returns a simple action: allow / block / flag
- Supports source tagging (twitch, youtube, discord, etc.)
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.logging import get_logger
from nexus.db.models import FilterEvent
from nexus.db.session import get_db
from nexus.serving.embedding import cosine_similarity, embed, is_model_loaded
from nexus.serving.engine import get_engine

router = APIRouter(prefix="/api/v1", tags=["filter"])
logger = get_logger(__name__)


# ─── Schemas ────────────────────────────────────────────


class FilterRules(BaseModel):
    """Configuration for the filter."""

    block_labels: list[str] = Field(
        default=["spam", "toxic"],
        description="Labels that trigger a block action",
    )
    flag_labels: list[str] = Field(
        default=[],
        description="Labels that trigger a flag (send to review)",
    )
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to trigger action",
    )
    use_similarity_boost: bool = Field(
        default=True,
        description="If true, similar blocked messages boost block confidence",
    )


class FilterRequest(BaseModel):
    """Request for the filter endpoint."""

    text: str = Field(..., min_length=1, max_length=5000)
    rules: FilterRules = Field(default_factory=FilterRules)
    source: str = Field(default="api", description="Source identifier (twitch, youtube, etc.)")


class SimilarityMatch(BaseModel):
    """A similar message found in the database."""

    text: str
    label: str
    action: str
    similarity: float


class FilterResponse(BaseModel):
    """Response from the filter endpoint."""

    action: str  # allow / block / flag
    label: str
    confidence: float
    latency_ms: float
    triggered_rules: list[str]
    similar_matches: list[SimilarityMatch]
    embedding_model: str
    event_id: str | None = None


# ─── Endpoint ───────────────────────────────────────────


@router.post("/filter", response_model=FilterResponse)
async def filter_content(
    request: FilterRequest,
    db: AsyncSession | None = Depends(get_db),
) -> FilterResponse:
    """Filter content and return an action decision.

    This is the production endpoint for real-time moderation.
    It classifies the text, applies rules, and optionally uses
    vector similarity to boost confidence.
    """
    import time

    start = time.perf_counter()

    # 1. Classify
    engine = get_engine()
    result = engine.predict(request.text)

    # 2. Compute embedding
    embedding = embed(request.text)
    embed_model = "all-MiniLM-L6-v2" if is_model_loaded() else "hash-fallback"

    # 3. Apply rules
    triggered: list[str] = []
    action = "allow"

    rules = request.rules

    if result.label in rules.block_labels and result.confidence >= rules.threshold:
        action = "block"
        triggered.append(f"label:{result.label}>= {rules.threshold}")
    elif result.label in rules.flag_labels and result.confidence >= rules.threshold:
        action = "flag"
        triggered.append(f"label:{result.label}>= {rules.threshold}")

    # 4. Similarity search (if DB available)
    similar_matches: list[SimilarityMatch] = []

    if db is not None and rules.use_similarity_boost:
        try:
            similar_matches = await _find_similar(db, embedding, k=5)

            # Boost: if >= 3 similar messages were blocked, escalate
            blocked_similar = [
                m for m in similar_matches if m.action == "block" and m.similarity > 0.7
            ]
            if len(blocked_similar) >= 3 and action == "allow":
                action = "flag"
                triggered.append(f"similarity_boost: {len(blocked_similar)} similar blocked")
        except Exception as e:
            logger.warning("Similarity search failed", error=str(e))

    # 5. Store event in DB
    event_id = None
    if db is not None:
        try:
            event = FilterEvent(
                id=str(uuid.uuid4()),
                input_text=request.text,
                label=result.label,
                confidence=result.confidence,
                action=action,
                triggered_rules=json.dumps(triggered) if triggered else None,
                model_version=result.model_version,
                processing_time_ms=result.processing_time_ms,
                source=request.source,
                embedding=json.dumps(embedding),
            )
            db.add(event)
            await db.flush()
            event_id = event.id
        except Exception as e:
            logger.warning("Failed to store filter event", error=str(e))

    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "Filter decision",
        action=action,
        label=result.label,
        confidence=f"{result.confidence:.3f}",
        latency=f"{elapsed_ms:.1f}ms",
        source=request.source,
        similar=len(similar_matches),
    )

    return FilterResponse(
        action=action,
        label=result.label,
        confidence=result.confidence,
        latency_ms=round(elapsed_ms, 2),
        triggered_rules=triggered,
        similar_matches=similar_matches,
        embedding_model=embed_model,
        event_id=event_id,
    )


@router.get("/filter/stats")
async def filter_stats(
    db: AsyncSession | None = Depends(get_db),
) -> dict:
    """Show filter statistics: actions breakdown, top labels."""
    if db is None:
        return {"error": "Database unavailable"}

    try:
        # Action breakdown
        stmt = select(
            FilterEvent.action,
            func.count(FilterEvent.id).label("count"),
        ).group_by(FilterEvent.action)
        result = await db.execute(stmt)
        actions = {row.action: row.count for row in result}

        # Label breakdown
        stmt2 = select(
            FilterEvent.label,
            func.count(FilterEvent.id).label("count"),
        ).group_by(FilterEvent.label)
        result2 = await db.execute(stmt2)
        labels = {row.label: row.count for row in result2}

        # Total
        total = sum(actions.values())

        return {
            "total_events": total,
            "by_action": actions,
            "by_label": labels,
        }
    except Exception as e:
        logger.warning("Filter stats failed", error=str(e))
        return {"error": str(e)}


@router.get("/filter/recent")
async def filter_recent(
    limit: int = 20,
    db: AsyncSession | None = Depends(get_db),
) -> dict:
    """Show recent filter events."""
    if db is None:
        return {"events": []}

    try:
        stmt = select(FilterEvent).order_by(desc(FilterEvent.created_at)).limit(limit)
        result = await db.execute(stmt)
        events = result.scalars().all()

        return {
            "events": [
                {
                    "id": e.id,
                    "text": e.input_text[:100],
                    "label": e.label,
                    "confidence": e.confidence,
                    "action": e.action,
                    "source": e.source,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ]
        }
    except Exception as e:
        logger.warning("Filter recent failed", error=str(e))
        return {"events": []}


# ─── Similarity search ──────────────────────────────────


async def _find_similar(
    db: AsyncSession,
    query_embedding: list[float],
    k: int = 5,
) -> list[SimilarityMatch]:
    """Find similar filter events using cosine similarity.

    Loads recent events and computes similarity in Python.
    For production scale, this would use pgvector's <=> operator.
    """
    # Get recent events with embeddings (last 1000)
    stmt = (
        select(FilterEvent.input_text, FilterEvent.label, FilterEvent.action, FilterEvent.embedding)
        .where(FilterEvent.embedding.is_not(None))
        .order_by(desc(FilterEvent.created_at))
        .limit(1000)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return []

    # Compute similarities
    scored: list[tuple[float, str, str, str]] = []
    for row in rows:
        if not row.embedding:
            continue
        try:
            stored_emb = json.loads(row.embedding)
            sim = cosine_similarity(query_embedding, stored_emb)
            scored.append((sim, row.input_text, row.label, row.action))
        except (json.JSONDecodeError, TypeError):
            continue

    # Sort by similarity descending, take top k
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:k]

    return [
        SimilarityMatch(
            text=text[:100],
            label=label,
            action=action,
            similarity=round(sim, 4),
        )
        for sim, text, label, action in top
        if sim > 0.3  # Only return meaningful matches
    ]
