"""
Test fixtures and async DB setup.

We use SQLite (aiosqlite) for tests instead of PostgreSQL for speed and
no-infra convenience. SQLite doesn't support PostgreSQL UUID columns or ENUM
types natively, so we use a GUID TypeDecorator in the models that renders
as CHAR(36) on SQLite and native UUID on Postgres.

Tradeoff: SQLite won't catch PostgreSQL-specific constraint behaviours
(e.g., ENUM type checks, some FK cascade subtleties). For production CI
you'd spin up a real Postgres via docker-compose or a GitHub Actions service.
The idempotency test (IntegrityError on duplicate event_id) works correctly
because SQLite also enforces UNIQUE constraints.
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Disable slowapi rate limits globally in tests
os.environ["RATELIMIT_ENABLED"] = "0"

from app.db.models import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_diagnostic.db"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(setup_db) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
