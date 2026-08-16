"""Cost tracking module — compute costs, revenue model, ROI.

Tracks:
  - Inference cost per request (CPU-seconds × $/hour)
  - Total daily/monthly cost
  - Revenue model (per-moderation pricing)
  - ROI metrics (revenue/cost ratio)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.logging import get_logger
from nexus.db.models import Prediction

logger = get_logger(__name__)

# ─── Cost constants (configurable via env in production) ───

# CPU inference cost: $0.03/hr for a small instance
INFERENCE_COST_PER_CPU_HOUR = 0.03

# Average ms per inference → CPU-seconds
INFERENCE_AVG_MS = 0.02  # mock classifier

# Revenue model: $0.001 per moderation check
REVENUE_PER_PREDICTION = 0.001

# Feedback cost: human reviewer cost for down-voted items
REVIEW_COST_PER_ITEM = 0.05


@dataclass
class CostBreakdown:
    """Daily cost breakdown."""

    date: str
    total_predictions: int = 0
    total_feedback: int = 0
    negative_feedback: int = 0

    inference_cost: float = 0.0
    review_cost: float = 0.0
    total_cost: float = 0.0
    revenue: float = 0.0
    profit: float = 0.0
    margin: float = 0.0  # profit / revenue

    def to_dict(self) -> dict:
        """Serialize to dict for API."""
        return {
            "date": self.date,
            "total_predictions": self.total_predictions,
            "total_feedback": self.total_feedback,
            "negative_feedback": self.negative_feedback,
            "inference_cost_usd": round(self.inference_cost, 6),
            "review_cost_usd": round(self.review_cost, 4),
            "total_cost_usd": round(self.total_cost, 4),
            "revenue_usd": round(self.revenue, 4),
            "profit_usd": round(self.profit, 4),
            "margin_pct": round(self.margin * 100, 2),
        }


@dataclass
class CostSummary:
    """Aggregated cost summary over a period."""

    period_days: int
    daily: list[CostBreakdown] = field(default_factory=list)
    total_predictions: int = 0
    total_cost: float = 0.0
    total_revenue: float = 0.0
    total_profit: float = 0.0
    avg_daily_cost: float = 0.0
    avg_margin: float = 0.0
    cost_per_1k_predictions: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dict for API."""
        return {
            "period_days": self.period_days,
            "total_predictions": self.total_predictions,
            "total_cost_usd": round(self.total_cost, 4),
            "total_revenue_usd": round(self.total_revenue, 4),
            "total_profit_usd": round(self.total_profit, 4),
            "avg_daily_cost_usd": round(self.avg_daily_cost, 4),
            "avg_margin_pct": round(self.avg_margin * 100, 2),
            "cost_per_1k_predictions_usd": round(self.cost_per_1k_predictions, 4),
            "daily": [d.to_dict() for d in self.daily],
        }


async def compute_cost_summary(db: AsyncSession, days: int = 7) -> CostSummary:
    """Compute cost summary for the last N days.

    Args:
        db: Async DB session.
        days: Number of days to analyze.

    Returns:
        CostSummary with per-day breakdown and aggregates.
    """
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    # Fetch predictions grouped by day
    stmt = (
        select(
            func.date(Prediction.created_at).label("day"),
            func.count(Prediction.id).label("count"),
            func.avg(Prediction.processing_time_ms).label("avg_ms"),
        )
        .where(Prediction.created_at >= start_date)
        .group_by(func.date(Prediction.created_at))
        .order_by(func.date(Prediction.created_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    summary = CostSummary(period_days=days)

    for row in rows:
        day_str = str(row.day)[:10] if row.day else "unknown"
        count = row.count or 0
        avg_ms = float(row.avg_ms or INFERENCE_AVG_MS)

        # Compute costs
        cpu_seconds = count * avg_ms / 1000.0
        inference_cost = cpu_seconds * INFERENCE_COST_PER_CPU_HOUR / 3600.0
        revenue = count * REVENUE_PER_PREDICTION

        breakdown = CostBreakdown(
            date=day_str,
            total_predictions=count,
            inference_cost=inference_cost,
            total_cost=inference_cost,
            revenue=revenue,
            profit=revenue - inference_cost,
            margin=(revenue - inference_cost) / revenue if revenue > 0 else 0.0,
        )

        summary.daily.append(breakdown)
        summary.total_predictions += count
        summary.total_cost += inference_cost
        summary.total_revenue += revenue

    summary.total_profit = summary.total_revenue - summary.total_cost
    summary.avg_daily_cost = summary.total_cost / max(days, 1)
    summary.avg_margin = (
        summary.total_profit / summary.total_revenue if summary.total_revenue > 0 else 0.0
    )
    summary.cost_per_1k_predictions = (
        summary.total_cost / summary.total_predictions * 1000
        if summary.total_predictions > 0
        else 0.0
    )

    return summary
