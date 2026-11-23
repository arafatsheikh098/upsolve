"""Shared fixtures for integration tests against a real Postgres and Redis.

Integration tests use TEST_DATABASE_URL / TEST_REDIS_URL (defaults match docker-compose) and are
skipped when those services aren't reachable, so the pure unit tests run anywhere.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import models  # noqa: F401  (registers tables)
from app.db import Base

TEST_DB = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://upsolve:upsolve@localhost:5432/upsolve_test"
)
TEST_REDIS = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")


async def _ensure_database(url: str) -> None:
    base, name = url.rsplit("/", 1)
    admin = create_async_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("select 1 from pg_database where datname = :n"), {"n": name}
            )
            if not exists:
                await conn.execute(text(f'create database "{name}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    try:
        await _ensure_database(TEST_DB)
    except Exception as exc:  # pragma: no cover - only when Postgres isn't running
        pytest.skip(f"Postgres not available: {exc}")
    eng = create_async_engine(TEST_DB)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def sessionmaker(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"truncate {tables} restart identity cascade"))
    yield async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    r = Redis.from_url(TEST_REDIS, decode_responses=True)
    try:
        await r.ping()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Redis not available: {exc}")
    await r.flushdb()
    yield r
    await r.flushdb()
    await r.aclose()
