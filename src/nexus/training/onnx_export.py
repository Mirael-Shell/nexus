"""ONNX export and benchmark suite for model optimization.

Exports the logistic regression model to ONNX format and
benchmarks inference latency: Python vs ONNX Runtime.

Phase 5 will add PyTorch → ONNX conversion for DistilBERT.
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


@dataclass
class BenchmarkResult:
    """Single benchmark measurement."""

    name: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    n_samples: int


@dataclass
class ExportResult:
    """Model export result."""

    format: str  # "onnx" / "json"
    model_path: str
    model_size_bytes: int
    n_features: int
    n_classes: int


@dataclass
class OptimizationReport:
    """Full optimization comparison report."""

    original: BenchmarkResult
    optimized: BenchmarkResult
    export_info: ExportResult
    speedup: float
    size_reduction_pct: float

    def to_dict(self) -> dict:
        """Serialize to dict for API."""
        return {
            "export": {
                "format": self.export_info.format,
                "path": self.export_info.model_path,
                "size_bytes": self.export_info.model_size_bytes,
                "n_features": self.export_info.n_features,
                "n_classes": self.export_info.n_classes,
            },
            "original": _benchmark_to_dict(self.original),
            "optimized": _benchmark_to_dict(self.optimized),
            "speedup": round(self.speedup, 2),
            "size_reduction_pct": round(self.size_reduction_pct, 2),
        }


def _benchmark_to_dict(b: BenchmarkResult) -> dict:
    """Serialize benchmark."""
    return {
        "name": b.name,
        "avg_latency_ms": round(b.avg_latency_ms, 4),
        "p95_latency_ms": round(b.p95_latency_ms, 4),
        "p99_latency_ms": round(b.p99_latency_ms, 4),
        "throughput_rps": round(b.throughput_rps, 1),
        "n_samples": b.n_samples,
    }


def export_model_to_onnx(
    weights: list[list[float]],
    vocab: dict[str, int],
    idx_to_label: dict[int, str],
    output_path: str | None = None,
) -> ExportResult:
    """Export logistic regression model to ONNX format.

    Since our MVP model is logistic regression (matrix multiply + softmax),
    we represent it as a simple ONNX graph using MatMul + Softmax nodes.

    Args:
        weights: Model weight matrix [n_classes][n_features].
        vocab: Vocabulary mapping.
        idx_to_label: Class index to label name mapping.
        output_path: Where to save the ONNX file.

    Returns:
        ExportResult with model metadata.
    """
    import numpy as np

    if output_path is None:
        models_dir = Path(settings.model_cache_dir).parent
        models_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(models_dir / "nexus_model.onnx")

    # Try ONNX export; fallback to JSON serialization
    try:
        import onnx
        from onnx import TensorProto, helper

        n_classes = len(weights)
        n_features = len(weights[0]) if weights else 0

        # Create ONNX graph: input → MatMul(weights^T) → Softmax → output
        input_tensor = helper.make_tensor_value_info("input", TensorProto.FLOAT, [None, n_features])
        output_tensor = helper.make_tensor_value_info(
            "output", TensorProto.FLOAT, [None, n_classes]
        )

        # Weight tensor [n_features, n_classes] (transposed for MatMul)
        weights_np = np.array(weights, dtype=np.float32).T  # [n_features, n_classes]
        weights_init = helper.make_tensor(
            "weights", TensorProto.FLOAT, [n_features, n_classes], weights_np.flatten().tolist()
        )

        matmul_node = helper.make_node("MatMul", ["input", "weights"], ["scores"], name="matmul")
        softmax_node = helper.make_node("Softmax", ["scores"], ["output"], axis=1, name="softmax")

        graph = helper.make_graph(
            [matmul_node, softmax_node],
            "nexus_logistic_regression",
            [input_tensor],
            [output_tensor],
            [weights_init],
        )
        model = helper.make_model(graph)
        model.opset_import[0].version = 17
        onnx.checker.check_model(model)
        onnx.save(model, output_path)

        model_size = Path(output_path).stat().st_size
        logger.info("Model exported to ONNX", path=output_path, size=model_size)

        # Save vocabulary alongside
        vocab_path = output_path.replace(".onnx", ".vocab.json")
        with open(vocab_path, "w") as f:
            json.dump({"vocab": vocab, "idx_to_label": idx_to_label}, f)

        return ExportResult(
            format="onnx",
            model_path=output_path,
            model_size_bytes=model_size,
            n_features=n_features,
            n_classes=n_classes,
        )

    except ImportError:
        logger.warning("ONNX not available, falling back to JSON export")
        # Fallback: JSON serialization
        model_data = {
            "weights": weights,
            "vocab": vocab,
            "idx_to_label": idx_to_label,
        }
        json_path = output_path.replace(".onnx", ".json") if output_path else "model.json"
        with open(json_path, "w") as f:
            json.dump(model_data, f)

        model_size = Path(json_path).stat().st_size
        return ExportResult(
            format="json",
            model_path=json_path,
            model_size_bytes=model_size,
            n_features=len(weights[0]) if weights else 0,
            n_classes=len(weights),
        )


def benchmark_inference(
    predict_fn: object,
    sample_inputs: list[str],
    n_warmup: int = 10,
    n_iterations: int = 1000,
) -> BenchmarkResult:
    """Benchmark a prediction function.

    Args:
        predict_fn: Callable that takes text and returns prediction.
        sample_inputs: List of sample texts to use.
        n_warmup: Warmup iterations (not measured).
        n_iterations: Measured iterations.

    Returns:
        BenchmarkResult with latency statistics.
    """
    if not sample_inputs:
        sample_inputs = ["test sample text for benchmarking"]

    # Warmup
    for i in range(n_warmup):
        predict_fn(sample_inputs[i % len(sample_inputs)])  # type: ignore[operator]

    # Measure
    latencies: list[float] = []
    for i in range(n_iterations):
        text = sample_inputs[i % len(sample_inputs)]
        start = time.perf_counter()
        predict_fn(text)  # type: ignore[operator]
        latencies.append((time.perf_counter() - start) * 1000.0)

    latencies.sort()
    avg = sum(latencies) / len(latencies)
    p95_idx = int(len(latencies) * 0.95)
    p99_idx = int(len(latencies) * 0.99)
    total_time_s = sum(latencies) / 1000.0
    throughput = n_iterations / total_time_s if total_time_s > 0 else 0.0

    return BenchmarkResult(
        name="python",
        avg_latency_ms=avg,
        p95_latency_ms=latencies[p95_idx],
        p99_latency_ms=latencies[p99_idx],
        throughput_rps=throughput,
        n_samples=n_iterations,
    )
