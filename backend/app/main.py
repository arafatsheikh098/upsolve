from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import auth, handles, plans
from app.cf.client import USER_AGENT, CodeforcesClient
from app.cf.ratelimit import RedisRateLimiter
from app.config import get_settings
from app.db import dispose_engine, get_session
from app.deps import get_redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    http = httpx.AsyncClient(
        base_url=settings.cf_base_url,
        timeout=settings.cf_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    )
    app.state.redis = redis
    app.state.cf = CodeforcesClient(http, RedisRateLimiter(redis, settings.cf_min_interval_seconds))
    app.state.queue = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        yield
    finally:
        await app.state.queue.aclose()
        await http.aclose()
        await redis.aclose()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Upsolve API",
        version="0.1.0",
        description="Codeforces weakness coach: per-tag skill model, recommender, practice plans.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Content-Type"],
    )
    for router in (handles.router, auth.router, plans.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health", tags=["meta"])
    async def health(
        session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
    ) -> dict[str, str]:
        await session.execute(text("select 1"))
        await redis.ping()
        return {"status": "ok"}

    return app


app = create_app()
