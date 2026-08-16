"""Training pipeline — TF-IDF + LogisticRegression classifier.

Trains on data/dataset.csv, logs to MLflow, saves model to disk.
Supports incremental learning: new feedback data is appended to CSV
and the model is retrained on the full dataset.

Usage:
    make train           # Train + log + save
    python -m nexus.training.pipeline
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from nexus.core.logging import get_logger

logger = get_logger(__name__)

# ─── Paths ──────────────────────────────────────────────

# __file__ = .../src/nexus/training/pipeline.py
# .parent = training/, .parent.parent = nexus/, .parent.parent.parent = src/
# In dev: data is at project_root/data/  → need 4 levels up from __file__
# In Docker: app structure is /app/src/nexus/training/ → /app/data/ → also 4 levels up
# But Docker COPY puts data at /app/data/ and src at /app/src/
# So: src/nexus/training/ → ../../../.. = /app/ (Docker) or project root (dev)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
DATASET_PATH = DATA_DIR / "dataset.csv"
MODEL_PATH = DATA_DIR / "model.joblib"


def load_dataset(path: Path = DATASET_PATH) -> tuple[list[str], list[str]]:
    """Load texts and labels from CSV.

    CSV format: text,label,source
    """
    texts: list[str] = []
    labels: list[str] = []

    if not path.exists():
        logger.warning("Dataset not found, using empty", path=str(path))
        return [], []

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", "").strip()
            label = row.get("label", "").strip().lower()
            if text and label in ("safe", "spam", "toxic"):
                texts.append(text)
                labels.append(label)

    logger.info("Dataset loaded", samples=len(texts), path=str(path))

    # Log class distribution
    from collections import Counter

    dist = Counter(labels)
    for label, count in sorted(dist.items()):
        logger.info(f"  {label}: {count} samples")

    return texts, labels


def train_model():
    """Train TF-IDF + LogisticRegression and save to disk.

    Returns:
        Dict with metrics and model info.
    """
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline

    texts, labels = load_dataset()
    if len(texts) < 10:
        logger.error("Not enough data to train", samples=len(texts))
        return {"error": "Not enough data", "samples": len(texts)}

    logger.info("Starting training", samples=len(texts))

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # Build pipeline
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=5000,
                    ngram_range=(1, 2),
                    stop_words="english",
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    C=1.0,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    # Train
    start = time.perf_counter()
    pipeline.fit(X_train, y_train)
    train_time = time.perf_counter() - start

    # Evaluate
    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    accuracy = report.get("accuracy", 0)
    f1_macro = report.get("macro avg", {}).get("f1-score", 0)
    f1_weighted = report.get("weighted avg", {}).get("f1-score", 0)

    logger.info(
        "Training complete",
        accuracy=f"{accuracy:.4f}",
        f1_macro=f"{f1_macro:.4f}",
        f1_weighted=f"{f1_weighted:.4f}",
        train_time=f"{train_time:.2f}s",
    )

    # Per-class metrics
    for label in ("safe", "spam", "toxic"):
        if label in report:
            r = report[label]
            logger.info(
                f"  {label}: precision={r['precision']:.3f} "
                f"recall={r['recall']:.3f} f1={r['f1-score']:.3f}"
            )

    # Save model to disk
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    # Also save metadata
    meta = {
        "accuracy": round(accuracy, 4),
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "train_time_sec": round(train_time, 2),
        "model_version": f"tfidf-logreg-{int(time.time())}",
        "classes": pipeline.classes_.tolist(),
        "per_class": {
            label: {
                "precision": round(report[label]["precision"], 4),
                "recall": round(report[label]["recall"], 4),
                "f1": round(report[label]["f1-score"], 4),
            }
            for label in ("safe", "spam", "toxic")
            if label in report
        },
    }

    meta_path = DATA_DIR / "model_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Model saved", path=str(MODEL_PATH), meta=str(meta_path))

    # Try logging to MLflow (optional — won't fail if MLflow is down)
    try:
        _log_to_mlflow(pipeline, meta)
    except Exception as e:
        logger.warning("MLflow logging failed (non-critical)", error=str(e))

    return meta


def _log_to_mlflow(pipeline, meta: dict) -> None:
    """Log model to MLflow (best-effort)."""
    from nexus.training.mlflow_client import _mlflow_available, init_mlflow

    init_mlflow()
    if not _mlflow_available:
        logger.info("Skipping MLflow logging — server not available")
        return

    import mlflow

    with mlflow.start_run(run_name=meta["model_version"]) as run:
        mlflow.log_params(
            {
                "model_type": "TF-IDF + LogisticRegression",
                "max_features": 5000,
                "ngram_range": "1-2",
                "train_samples": meta["train_samples"],
                "test_samples": meta["test_samples"],
            }
        )
        mlflow.log_metrics(
            {
                "accuracy": meta["accuracy"],
                "f1_macro": meta["f1_macro"],
                "f1_weighted": meta["f1_weighted"],
            }
        )
        for label, m in meta["per_class"].items():
            mlflow.log_metric(f"{label}_precision", m["precision"])
            mlflow.log_metric(f"{label}_recall", m["recall"])
            mlflow.log_metric(f"{label}_f1", m["f1"])

        mlflow.sklearn.log_model(pipeline, "model")
        logger.info("Logged to MLflow", run_id=run.info.run_id)


if __name__ == "__main__":
    result = train_model()
    print(json.dumps(result, indent=2))
