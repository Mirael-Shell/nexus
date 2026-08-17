"""Shared test fixtures for NEXUS test suite.

Uses a file-backed SQLite database in a temp directory for test isolation.
A file-backed DB (unlike :memory:) survives connection pool recycling and
event-loop switches under pytest-asyncio >= 1.0 (new loop per test), so
tables created at fixture setup remain visible to every test.
Each test session gets its own file, removed afterwards.
"""

import os

# Force file-backed SQLite in a temp dir BEFORE any nexus imports
import tempfile

_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="nexus_test_"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
os.environ["API_DEBUG"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.db.models import Base
from nexus.db.session import engine
from nexus.main import create_app


@pytest.fixture
async def client():
    """ASGI test client with isolated file-backed SQLite database.

    create_all is idempotent (checkfirst=True), guaranteeing tables exist
    regardless of fixture ordering or connection recycling.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # Drop data between tests for isolation (file stays, tables persist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
