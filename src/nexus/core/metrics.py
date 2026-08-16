"""Prometheus metrics middleware for FastAPI.

Exposes /metrics endpoint with:
  - Request count by method/path/status
  - Request latency histogram
  - Inference count by label
  - Inference latency histogram
  - Active experiments gauge
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ─── Metrics ────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "nexus_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "nexus_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

INFERENCE_COUNT = Counter(
    "nexus_inference_total",
    "Total inference requests",
    ["label", "model_version"],
)

INFERENCE_LATENCY = Histogram(
    "nexus_inference_duration_seconds",
    "Inference latency in seconds",
    ["model_version"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

FEEDBACK_COUNT = Counter(
    "nexus_feedback_total",
    "Total user feedback submissions",
    ["feedback_type"],  # up / down
)

ACTIVE_EXPERIMENTS = Gauge(
    "nexus_experiments_active",
    "Number of active (running) experiments",
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect HTTP metrics for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        # Normalize path (collapse IDs)
        path = request.url.path
        # Replace UUID-like segments with :id
        parts = path.split("/")
        normalized = [":id" if len(p) == 36 and "-" in p else p for p in parts]
        path = "/".join(normalized)

        import time

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        REQUEST_COUNT.labels(
            method=method,
            path=path,
            status=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

        return response


def metrics_endpoint(_: Request) -> Response:
    """Expose Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
