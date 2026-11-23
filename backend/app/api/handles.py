from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.recommend import plan_seed, recommend
from app.cf.sync import handle_key
from app.config import get_settings
from app.db import get_session
from app.deps import (
    JobQueue,
    client_ip,
    get_queue,
    get_redis,
    optional_user,
    rate_limit,
    valid_handle,
)
from app.models import Handle, User
from app.schemas import (
    AnalysisOut,
    CompareOut,
    CompareSide,
    ProblemRef,
    RecommendationOut,
    RecommendationsOut,
    SyncStatus,
)
from app.services import analyze, handle_out, sync_status

router = APIRouter(tags=["handles"])

log = logging.getLogger(__name__)

STALE_QUEUE = timedelta(minutes=5)
# Bump when AnalysisOut changes shape, so old cached reports are never served.
ANALYSIS_CACHE_VERSION = 2
OWNER_COOLDOWN_SECONDS = 60


async def _get_synced(session: AsyncSession, handle: str) -> Handle:
    h = await session.get(Handle, handle_key(handle))
    if h is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This handle hasn't been analyzed yet.")
    if h.last_synced_at is None:
        detail = h.sync_error or "This handle is still being synced."
        raise HTTPException(status.HTTP_409_CONFLICT, detail)
    return h


@router.post("/handles/{handle}/sync", response_model=SyncStatus, status_code=202)
async def request_sync(
    request: Request,
    handle: str = Depends(valid_handle),
    force: bool = Query(False, description="Owner only: allow a re-sync after one minute"),
    session: AsyncSession = Depends(get_session),
    queue: JobQueue = Depends(get_queue),
    redis: Redis = Depends(get_redis),
    user: User | None = Depends(optional_user),
) -> SyncStatus:
    """Queue a sync from Codeforces. Repeated calls are cheap: recent or in-flight syncs are
    returned as-is. A verified owner may force a refresh after a short cooldown, so solved plan
    problems show up quickly."""
    settings = get_settings()
    key = handle_key(handle)
    now = datetime.now(UTC)
    cooldown = settings.sync_cooldown_seconds
    if force and user is not None and user.handle_key == key:
        cooldown = OWNER_COOLDOWN_SECONDS
    h = await session.get(Handle, key)
    if h is not None:
        in_flight = h.sync_state in ("queued", "syncing")
        if in_flight and h.sync_requested_at and now - h.sync_requested_at < STALE_QUEUE:
            return await sync_status(session, h)
        fresh = h.last_synced_at and now - h.last_synced_at < timedelta(seconds=cooldown)
        if h.sync_state == "ready" and fresh:
            return await sync_status(session, h)

    await rate_limit(redis, f"sync:{client_ip(request)}", limit=30, window_seconds=600)
    if h is None:
        h = Handle(key=key, handle=handle)
        session.add(h)
    h.sync_state = "queued"
    h.sync_error = None
    h.sync_requested_at = now
    await session.commit()
    await queue.enqueue_job("sync_handle_job", handle, _job_id=f"sync:{key}")
    return await sync_status(session, h)


@router.get("/handles/{handle}/status", response_model=SyncStatus)
async def get_status(
    handle: str = Depends(valid_handle), session: AsyncSession = Depends(get_session)
) -> SyncStatus:
    h = await session.get(Handle, handle_key(handle))
    if h is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This handle hasn't been analyzed yet.")
    return await sync_status(session, h)


@router.get("/handles/{handle}/analysis", response_model=AnalysisOut)
async def get_analysis(
    handle: str = Depends(valid_handle),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> AnalysisOut:
    h = await _get_synced(session, handle)
    assert h.last_synced_at is not None
    synced = int(h.last_synced_at.timestamp())
    cache_key = (
        f"upsolve:analysis:v{ANALYSIS_CACHE_VERSION}:{h.key}:{h.last_submission_id}:{synced}"
    )
    cached = await redis.get(cache_key)
    if cached:
        try:
            report = AnalysisOut.model_validate_json(cached)
        except ValidationError:
            log.warning("discarding unreadable cached analysis for %s", h.key)
        else:
            report.handle = handle_out(h)  # sync state may have changed since caching
            return report
    result = await analyze(session, h)
    await redis.set(
        cache_key, result.report.model_dump_json(), ex=get_settings().analysis_cache_seconds
    )
    return result.report


@router.get("/handles/{handle}/recommendations", response_model=RecommendationsOut)
async def get_recommendations(
    handle: str = Depends(valid_handle),
    n: int = Query(4, ge=1, le=8),
    session: AsyncSession = Depends(get_session),
) -> RecommendationsOut:
    h = await _get_synced(session, handle)
    result = await analyze(session, h)
    now = datetime.now(UTC)
    recs = recommend(
        result.fit,
        result.report.weaknesses,
        result.pool,
        result.attempts,
        seed=plan_seed(h.key, now.date()),
        now=now,
        n=n,
    )
    return RecommendationsOut(
        day=now.date(),
        items=[
            RecommendationOut(
                problem=ProblemRef.make(r.problem_id, r.name, r.rating, r.tags),
                kind=r.kind,
                focus_tag=r.focus_tag,
                reason=r.reason,
                predicted=r.predicted,
            )
            for r in recs
        ],
    )


@router.get("/compare", response_model=CompareOut)
async def compare(
    a: str = Query(..., min_length=3, max_length=24),
    b: str = Query(..., min_length=3, max_length=24),
    session: AsyncSession = Depends(get_session),
) -> CompareOut:
    sides = []
    for handle in (valid_handle(a), valid_handle(b)):
        h = await _get_synced(session, handle)
        result = await analyze(session, h)
        sides.append(
            CompareSide(handle=handle_out(h), level=result.fit.level, skills=result.report.skills)
        )
    return CompareOut(a=sides[0], b=sides[1])
