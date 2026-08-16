"""Business analytics dashboard — product metrics for AI PM.

Computes:
- Moderation precision/recall from feedback
- Funnel: total → filtered → blocked → flagged
- False positive cost estimation
- Label distribution over time
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from nexus.core.logging import get_logger
from nexus.db.models import Feedback, FilterEvent, Prediction
from nexus.db.session import get_db

logger = get_logger("nexus.business")

router = APIRouter(prefix="/api/v1/business", tags=["business"])


@router.get("/dashboard")
async def business_dashboard() -> dict:
    """Full business metrics dashboard."""
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

        # ─── Moderation Quality (precision/recall from feedback) ───
        total_up = await db.scalar(
            select(func.count()).select_from(Feedback).where(Feedback.feedback_type == "up")
        )
        total_down = await db.scalar(
            select(func.count()).select_from(Feedback).where(Feedback.feedback_type == "down")
        )
        total_feedback = (total_up or 0) + (total_down or 0)

        # Precision ≈ up / (up + down)
        precision = (total_up or 0) / total_feedback if total_feedback > 0 else 0.0

        metrics["moderation_quality"] = {
            "total_feedback": total_feedback,
            "correct": total_up or 0,
            "incorrect": total_down or 0,
            "precision": round(precision, 4),
            "satisfaction_rate": round(precision, 4),
        }

        # ─── Funnel ───
        total_preds = await db.scalar(select(func.count()).select_from(Prediction))
        total_blocked = await db.scalar(
            select(func.count()).select_from(FilterEvent).where(FilterEvent.action == "block")
        )
        total_allowed = await db.scalar(
            select(func.count()).select_from(FilterEvent).where(FilterEvent.action == "allow")
        )
        total_flagged = await db.scalar(
            select(func.count()).select_from(FilterEvent).where(FilterEvent.action == "flag")
        )
        total_filter_events = (total_blocked or 0) + (total_allowed or 0) + (total_flagged or 0)

        metrics["funnel"] = {
            "total_predictions": total_preds or 0,
            "total_filtered": total_filter_events,
            "allowed": total_allowed or 0,
            "blocked": total_blocked or 0,
            "flagged": total_flagged or 0,
            "block_rate": round((total_blocked or 0) / total_filter_events, 4)
            if total_filter_events
            else 0,
        }

        # ─── Label Distribution ───
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

        # ─── Feedback by Label ───
        feedback_by_label: dict[str, dict] = {}
        for label in ("safe", "spam", "toxic"):
            label_preds = await db.scalar(
                select(func.count())
                .select_from(Prediction)
                .where(Prediction.predicted_label == label)
            )
            label_feedback = await db.execute(
                select(Feedback.feedback_type, func.count())
                .join(Prediction, Feedback.prediction_id == Prediction.id)
                .where(Prediction.predicted_label == label)
                .group_by(Feedback.feedback_type)
            )
            fb = {row[0]: row[1] for row in label_feedback}
            feedback_by_label[label] = {
                "total_predictions": label_preds or 0,
                "correct": fb.get("up", 0),
                "incorrect": fb.get("down", 0),
                "per_label_precision": round(
                    fb.get("up", 0) / (fb.get("up", 0) + fb.get("down", 0)), 4
                )
                if (fb.get("up", 0) + fb.get("down", 0)) > 0
                else None,
            }

        metrics["feedback_summary"] = feedback_by_label

        # ─── False Positive Cost Estimation ───
        # False positive = predicted spam/toxic but user said "down" (incorrect)
        fp_count = await db.scalar(
            select(func.count())
            .select_from(Feedback)
            .join(Prediction, Feedback.prediction_id == Prediction.id)
            .where(
                Feedback.feedback_type == "down",
                Prediction.predicted_label.in_(["spam", "toxic"]),
            )
        )
        # Estimated cost per false positive: $0.50 (reputation impact + manual review)
        cost_per_fp = 0.50
        total_fp_cost = (fp_count or 0) * cost_per_fp

        metrics["false_positive_cost"] = {
            "false_positives": fp_count or 0,
            "cost_per_fp_usd": cost_per_fp,
            "total_fp_cost_usd": round(total_fp_cost, 2),
            "fp_rate": round((fp_count or 0) / total_feedback, 4) if total_feedback > 0 else 0,
        }

        break

    return metrics
