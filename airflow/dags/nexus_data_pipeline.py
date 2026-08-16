"""Airflow DAG: Automated data collection and quality pipeline.

Runs daily to:
1. Collect feedback from DB
2. Validate and deduplicate
3. Update training dataset
4. Check data quality (balance, length, duplicates)
5. Trigger retrain if quality is sufficient
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "nexus",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="nexus_data_pipeline",
    description="Daily data collection + quality check + retrain trigger",
    schedule="0 2 * * *",  # Daily at 2am
    start_date=datetime(2026, 1, 1),
    default_args=default_args,
    catchup=False,
    tags=["nexus", "data", "mlops"],
)
def nexus_data_pipeline():
    """Daily data pipeline for NEXUS moderation platform."""

    @task
    def collect_feedback() -> dict:
        """Collect all feedback from the past 24h."""
        import asyncio

        async def _collect():
            from sqlalchemy import select

            from nexus.db.models import Feedback, Prediction
            from nexus.db.session import get_db

            collected: list[dict] = []
            async for db in get_db():
                if db is None:
                    return {"collected": 0, "error": "DB unavailable"}
                result = await db.execute(
                    select(Feedback, Prediction)
                    .join(Prediction, Feedback.prediction_id == Prediction.id)
                    .where(Feedback.feedback_type == "down")
                    .order_by(Feedback.created_at.desc())
                )
                for fb, pred in result.all():
                    collected.append({
                        "text": pred.input_text,
                        "feedback": fb.feedback_type,
                        "comment": fb.comment,
                    })
                break

            return {"collected": len(collected), "data": collected}

        return asyncio.run(_collect())

    @task
    def validate_and_dedup(feedback_data: dict) -> dict:
        """Validate text quality and remove duplicates."""
        items = feedback_data.get("data", [])
        seen = set()
        valid: list[dict] = []
        rejected = 0

        for item in items:
            text = item.get("text", "").strip()
            # Quality checks
            if len(text) < 3 or len(text) > 2000:
                rejected += 1
                continue
            # Deduplicate
            text_lower = text.lower()
            if text_lower in seen:
                rejected += 1
                continue
            seen.add(text_lower)
            valid.append(item)

        return {
            "total_input": len(items),
            "valid": len(valid),
            "rejected": rejected,
            "data": valid,
        }

    @task
    def check_data_quality(validation_result: dict) -> dict:
        """Check dataset balance, size, and quality metrics."""
        import csv

        from pathlib import Path

        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        dataset_path = data_dir / "dataset.csv"

        label_counts: dict[str, int] = {}
        total = 0
        duplicates = 0
        texts_seen: set[str] = set()

        if dataset_path.exists():
            with open(dataset_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total += 1
                    label = row.get("label", "unknown")
                    label_counts[label] = label_counts.get(label, 0) + 1

                    text = row.get("text", "").lower()
                    if text in texts_seen:
                        duplicates += 1
                    texts_seen.add(text)

        # Check balance
        min_label = min(label_counts.values()) if label_counts else 0
        max_label = max(label_counts.values()) if label_counts else 0
        balance_ratio = min_label / max_label if max_label > 0 else 0

        quality_report = {
            "total_samples": total,
            "label_counts": label_counts,
            "duplicates": duplicates,
            "balance_ratio": round(balance_ratio, 2),
            "is_balanced": balance_ratio > 0.5,
            "meets_min_size": total >= 50,
            "should_retrain": total >= 50 and balance_ratio > 0.3,
        }

        return quality_report

    @task
    def trigger_retrain(quality_report: dict) -> dict:
        """Trigger model retraining if data quality is sufficient."""
        if not quality_report.get("should_retrain", False):
            return {
                "retrained": False,
                "reason": f"Quality checks failed: balanced={quality_report.get('is_balanced')}, size={quality_report.get('total_samples')}",
            }

        import asyncio

        async def _retrain():
            from nexus.training.pipeline import train_model

            metrics = train_model()
            return metrics

        try:
            metrics = asyncio.run(_retrain())
            return {
                "retrained": True,
                "accuracy": metrics.get("accuracy"),
                "f1_macro": metrics.get("f1_macro"),
            }
        except Exception as e:
            return {"retrained": False, "error": str(e)}

    # Pipeline
    raw = collect_feedback()
    validated = validate_and_dedup(raw)
    quality = check_data_quality(validated)
    result = trigger_retrain(quality)


# Create the DAG
pipeline_dag = nexus_data_pipeline()
