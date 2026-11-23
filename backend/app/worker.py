"""Background worker (arq): syncs handles and keeps the problemset fresh.

Run with:  arq app.worker.WorkerSettings
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx
from arq import cron, func
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy import delete, exists, select

from app.cf.client import USER_AGENT, CFError, CodeforcesClient
from app.cf.ratelimit import RedisRateLimiter
from app.cf.sync import problem_count, refresh_problemset, sync_handle
from app.config import get_settings
from app.db import make_engine, make_sessionmaker
from app.models import Handle, Submission, User, Verification

log = logging.getLogger("upsolve.worker")

Ctx = dict[str, Any]


async def startup(ctx: Ctx) -> None:
    settings = get_settings()
    ctx["redis_client"] = Redis.from_url(settings.redis_url, decode_responses=True)
    ctx["http"] = httpx.AsyncClient(
        base_url=settings.cf_base_url,
        timeout=settings.cf_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    )
    ctx["cf"] = CodeforcesClient(
        ctx["http"], RedisRateLimiter(ctx["redis_client"], settings.cf_min_interval_seconds)
    )
    ctx["engine"] = make_engine()
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    async with ctx["sessionmaker"]() as session:
        if await problem_count(session) == 0:
            log.info("problemset is empty; scheduling a refresh")
            await ctx["redis"].enqueue_job("refresh_problemset_job", _job_id="refresh-problemset")


async def shutdown(ctx: Ctx) -> None:
    await ctx["http"].aclose()
    await ctx["redis_client"].aclose()
    await ctx["engine"].dispose()


async def sync_handle_job(ctx: Ctx, handle: str) -> str:
    async with ctx["sessionmaker"]() as session:
        try:
            h = await sync_handle(session, ctx["cf"], handle)
        except CFError as exc:
            log.warning("sync %s failed: %s", handle, exc)
            return f"error: {exc}"
        return f"synced {h.handle}"


async def refresh_problemset_job(ctx: Ctx) -> int:
    async with ctx["sessionmaker"]() as session:
        return await refresh_problemset(session, ctx["cf"])


async def sync_verified_users(ctx: Ctx) -> int:
    """Keep verified users' data fresh so their plans update without them pressing refresh."""
    async with ctx["sessionmaker"]() as session:
        rows = await session.execute(
            select(Handle.key, Handle.handle).join(User, User.handle_key == Handle.key)
        )
        handles = [(key, handle) for key, handle in rows]
        for key, handle in handles:
            await ctx["redis"].enqueue_job("sync_handle_job", handle, _job_id=f"sync:{key}")
    return len(handles)


async def cleanup(ctx: Ctx) -> None:
    now = datetime.now(UTC)
    async with ctx["sessionmaker"]() as session:
        await session.execute(
            delete(Verification).where(Verification.expires_at < now - timedelta(days=1))
        )
        # Handles that failed (typos, deleted accounts) and never got any data.
        await session.execute(
            delete(Handle).where(
                Handle.sync_state == "error",
                Handle.last_synced_at.is_(None),
                Handle.created_at < now - timedelta(days=1),
                ~exists().where(Submission.handle_key == Handle.key),
                ~exists().where(User.handle_key == Handle.key),
            )
        )
        await session.commit()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        # keep_result=0 so a finished job doesn't block re-enqueueing the same job id.
        func(sync_handle_job, keep_result=0, timeout=900),
        func(refresh_problemset_job, keep_result=0, timeout=600),
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(refresh_problemset_job, hour={3}, minute={0}, keep_result=0),
        cron(sync_verified_users, hour={0, 12}, minute={30}, keep_result=0),
        cron(cleanup, minute={15}, keep_result=0),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
