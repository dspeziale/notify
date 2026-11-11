"""Pytest fixtures with in-memory database and async test client."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.api.deps import get_db
from app.core.config import settings
from app.database.base import Base
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Ensure Redis is disabled during pytest runs for instant isolated testing
settings.REDIS_ENABLED = False


@pytest.fixture
def master_key():
    return "k5b1A0r_y8qR_hN7YJbM5x6_Z8V3qL2kM4p1R9s8T2A="


@pytest.fixture
def secondary_key():
    return "m9c2B1s_z9rS_iO8ZKcO6y7_b9W4rM3lN5q2S0t9U3B="


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    return {"X-Admin-API-Key": settings.ADMIN_API_KEY}


@pytest_asyncio.fixture
async def test_app_and_key(client, admin_headers):
    """Creates a sample registered application and returns (app_data, raw_api_key)."""
    payload = {
        "name": "Integration Test App",
        "description": "App used for testing",
        "rate_limit_per_minute": 100,
        "permissions": ["telegram:send", "gmail:send"],
    }
    response = await client.post("/api/v1/admin/applications", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    raw_key = data["initial_api_key"]["raw_api_key"]
    return data, raw_key
