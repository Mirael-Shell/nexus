"""Security middleware: API key authentication and rate limiting.

API Key Auth:
  - Clients send X-API-Key header
  - Validated against API_KEY env var (or a set of known keys)
  - /health, /metrics, /docs, /openapi.json are exempt (public endpoints)

Rate Limiting:
  - Sliding window counter per client (IP or API key)
  - Configurable: requests per minute, burst size
  - Returns 429 Too Many Requests when exceeded
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from nexus.core.logging import get_logger

logger = get_logger(__name__)

# ─── Configuration ──────────────────────────────────────

# Endpoints that don't require API key
PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/api/v1/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/",
        "/api/v1/stream/ws",  # WebSocket endpoint
    }
)

# Rate limiting defaults
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "300"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "50"))


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header for non-public endpoints.

    Set API_KEY env var to enable. If not set, all requests pass (dev mode).
    Supports comma-separated keys for multiple clients.
    """

    def __init__(self, app, public_paths: frozenset[str] | None = None):
        super().__init__(app)
        self.api_keys: set[str] = set()
        raw_key = os.getenv("API_KEY", "")
        if raw_key:
            self.api_keys = {k.strip() for k in raw_key.split(",") if k.strip()}
        self.public_paths = public_paths or PUBLIC_PATHS
        logger.info(
            "API Key middleware initialized",
            enabled=bool(self.api_keys),
            num_keys=len(self.api_keys),
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Allow public endpoints
        if path in self.public_paths or path.startswith("/assets"):
            return await call_next(request)

        # If no API keys configured → open mode (dev)
        if not self.api_keys:
            return await call_next(request)

        # Validate key
        provided_key = request.headers.get("X-API-Key", "")
        if provided_key not in self.api_keys:
            client_ip = request.client.host if request.client else "?"
            logger.warning("Unauthorized API access", path=path, ip=client_ip)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter per client.

    Uses in-memory counter (suitable for single-instance).
    For multi-instance, replace with Redis-based limiter.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = RATE_LIMIT_PER_MINUTE,
        burst: int = RATE_LIMIT_BURST,
    ):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.burst = burst
        self._requests: dict[str, list[float]] = defaultdict(list)
        logger.info(
            "Rate limiter initialized",
            rpm=requests_per_minute,
            burst=burst,
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip rate limiting for public endpoints (health, metrics, docs)
        if path in PUBLIC_PATHS or path.startswith("/assets"):
            return await call_next(request)

        # Get client identifier (API key or IP)
        client_id = request.headers.get("X-API-Key") or (
            request.client.host if request.client else "unknown"
        )
        now = time.time()
        window_start = now - 60.0

        # Clean old entries
        self._requests[client_id] = [t for t in self._requests[client_id] if t > window_start]

        # Check limit
        if len(self._requests[client_id]) >= self.rpm:
            retry_after = int(60 - (now - self._requests[client_id][0]))
            logger.warning(
                "Rate limit exceeded",
                client=client_id,
                count=len(self._requests[client_id]),
                limit=self.rpm,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Max {self.rpm} requests/minute.",
                    "retry_after": max(retry_after, 1),
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._requests[client_id].append(now)
        return await call_next(request)
