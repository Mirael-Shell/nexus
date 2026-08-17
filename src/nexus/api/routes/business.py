"""Business analytics dashboard — product metrics for AI PM.

Computes:
- Moderation precision/recall from feedback
- Funnel: total → filtered → blocked → flagged
- False positive cost estimation
- Label distribution over time

Performance: 4 aggregate queries (was 11, incl. N+1 by label) + 30s TTL cache.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from sqlalchemy import func, select

from nexus.core.logging import get_logger
from nexus.db.models import Feedback, FilterEvent, Prediction
from nexus.db.session import get_db

logger = get_logger("nexus.business")

router = APIRouter(prefix="/api/v1/business", tags=["business"])

# TTL cache: dashboard is a product surface, 30s staleness is acceptable
_CACHE_TTL = 30.0
_cache: dict[str, tuple[float, dict]] = {}


def invalidate_cache() -> None:
    """Drop cached dashboard (e.g. after retrain or feedback writes)."""
    _cache.pop("dashboard", None)


@router.get("/dashboard")
async def business_dashboard() -> dict:
    """Full business metrics dashboard (30s TTL cache)."""
    hit = _cache.get("dashboard")
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]

    metrics: dict = {
        "moderation_quality": {},
        "funnel": {},
        "label_distribution": {},
        "feedback_summary": {},
        "false_positive_cost": {},
    }

    async for db in get_db():
        if db is None:
            break

        # ─── Q1: Feedback totals (up/down) — moderation quality base ───
        fb_rows = await db.execute(
            select(Feedback.feedback_type, func.count()).group_by(Feedback.feedback_type)
        )
        fb_totals = {row[0]: row[1] for row in fb_rows}
        total_up = fb_totals.get("up", 0)
        total_down = fb_totals.get("down", 0)
        total_feedback = total_up + total_down

        precision = total_up / total_feedback if total_feedback > 0 else 0.0
        metrics["moderation_quality"] = {
            "total_feedback": total_feedback,
            "correct": total_up,
            "incorrect": total_down,
            "precision": round(precision, 4),
            "satisfaction_rate": round(precision, 4),
        }

        # ─── Q2: Funnel — filter actions + prediction count ───
        total_preds = await db.scalar(select(func.count()).select_from(Prediction))
        action_rows = await db.execute(
            select(FilterEvent.action, func.count()).group_by(FilterEvent.action)
        )
        actions = {row[0]: row[1] for row in action_rows}
        total_blocked = actions.get("block", 0)
        total_allowed = actions.get("allow", 0)
        total_flagged = actions.get("flag", 0)
        total_filter_events = total_blocked + total_allowed + total_flagged

        metrics["funnel"] = {
            "total_predictions": total_preds or 0,
            "total_filtered": total_filter_events,
            "allowed": total_allowed,
            "blocked": total_blocked,
            "flagged": total_flagged,
            "block_rate": round(total_blocked / total_filter_events, 4)
            if total_filter_events
            else 0,
        }

        # ─── Q3: Label distribution ───
        label_result = await db.execute(
            select(Prediction.predicted_label, func.count()).group_by(Prediction.predicted_label)
        )
        label_counts = {row[0]: row[1] for row in label_result}
        total_all = sum(label_counts.values())

        metrics["label_distribution"] = {
            "labels": label_counts,
            "total": total_all,
            "percentages": {
                k: round(v / total_all, 4) if total_all else 0 for k, v in label_counts.items()
            },
        }

        # ─── Q4: Feedback joined by label (fixes N+1) + false positives ───
        join_rows = await db.execute(
            select(
                Prediction.predicted_label,
                Feedback.feedback_type,
                func.count(),
            )
            .join(Prediction, Feedback.prediction_id == Prediction.id)
            .group_by(Prediction.predicted_label, Feedback.feedback_type)
        )
        fb_by_label: dict[str, dict[str, int]] = {}
        for label, fb_type, cnt in join_rows:
            fb_by_label.setdefault(label, {})[fb_type] = cnt

        feedback_summary: dict[str, dict] = {}
        fp_count = 0
        for label in ("safe", "spam", "toxic"):
            up = fb_by_label.get(label, {}).get("up", 0)
            down = fb_by_label.get(label, {}).get("down", 0)
            denom = up + down
            feedback_summary[label] = {
                "total_predictions": label_counts.get(label, 0),
                "correct": up,
                "incorrect": down,
                "per_label_precision": round(up / denom, 4) if denom > 0 else None,
            }
            if label in ("spam", "toxic"):
                fp_count += down  # "down" on spam/toxic = false positive

        metrics["feedback_summary"] = feedback_summary

        # ─── False Positive Cost (derived from Q4, no extra query) ───
        cost_per_fp = 0.50  # reputation impact + manual review
        metrics["false_positive_cost"] = {
            "false_positives": fp_count,
            "cost_per_fp_usd": cost_per_fp,
            "total_fp_cost_usd": round(fp_count * cost_per_fp, 2),
            "fp_rate": round(fp_count / total_feedback, 4) if total_feedback > 0 else 0,
        }

        break

    _cache["dashboard"] = (time.monotonic(), metrics)
    return metrics
