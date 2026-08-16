"""Shared test fixtures for NEXUS test suite.

Uses in-memory SQLite with StaticPool for test isolation.
Tables are created per-test inside the client fixture so they share
the test's event loop (required by pytest-asyncio >= 1.0, where
session-scoped async fixtures run on a separate loop and their
aiosqlite connections cannot be reused from test loops).
"""

import os

# Force in-memory SQLite BEFORE any nexus imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["API_DEBUG"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.db.models import Base
from nexus.db.session import engine
from nexus.main import create_app


@pytest.fixture
async def client():
    """ASGI test client with in-memory database (tables on the test's loop)."""
    # Idempotent (checkfirst=True by default) — guarantees tables exist
    # on this test's event loop regardless of fixture ordering.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
