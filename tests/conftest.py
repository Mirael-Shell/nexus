"""Shared test fixtures for NEXUS test suite.

Uses in-memory SQLite with StaticPool for test isolation.
Creates all tables before running tests.
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


@pytest.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once for the entire test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """ASGI test client with isolated in-memory database."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
