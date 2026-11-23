"""Prove you own a Codeforces handle by submitting a compilation error to a problem we choose.

Codeforces has no "log in with Codeforces" for third-party apps, so tools in the CF community use
this trick: only the account owner can make a submission from that account, and a compilation
error costs nothing (it doesn't count as a wrong attempt or affect rating).
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cf.client import CFError, CodeforcesClient
from app.cf.sync import handle_key
from app.config import get_settings
from app.db import get_session
from app.deps import (
    SESSION_COOKIE,
    client_ip,
    current_user,
    get_cf,
    get_redis,
    rate_limit,
    valid_handle,
)
from app.models import Handle, User, Verification
from app.schemas import MeOut, ProblemRef, VerifyCheckIn, VerifyStartIn, VerifyStartOut
from app.services import pool_cache

router = APIRouter(prefix="/auth", tags=["auth"])

# Allow for clock differences between us and Codeforces.
CLOCK_SKEW = timedelta(minutes=2)


class VerifyCheckOut(BaseModel):
    verified: bool
    message: str
    handle: str | None = None


def issue_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "h": user.handle_key,
        "exp": datetime.now(UTC) + timedelta(days=settings.jwt_ttl_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.jwt_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/verify/start", response_model=VerifyStartOut)
async def verify_start(
    body: VerifyStartIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> VerifyStartOut:
    handle = valid_handle(body.handle)
    key = handle_key(handle)
    await rate_limit(redis, f"verify-start:ip:{client_ip(request)}", limit=10, window_seconds=600)
    await rate_limit(redis, f"verify-start:h:{key}", limit=5, window_seconds=600)

    h = await session.get(Handle, key)
    if h is None or h.last_synced_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Analyze this handle first, then verify it.")

    easy = [p for p in await pool_cache.get(session) if p.rating == 800]
    if not easy:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Problem list is still loading. Try again soon."
        )
    problem = random.SystemRandom().choice(easy)
    now = datetime.now(UTC)
    v = Verification(
        id=str(uuid.uuid4()),
        handle_key=key,
        handle=h.handle,
        problem_id=problem.id,
        created_at=now,
        expires_at=now + timedelta(seconds=get_settings().verification_ttl_seconds),
    )
    session.add(v)
    await session.commit()
    return VerifyStartOut(
        verification_id=v.id,
        handle=h.handle,
        problem=ProblemRef.make(problem.id, problem.name, problem.rating, problem.tags),
        submit_url=f"https://codeforces.com/contest/{problem.contest_id}/submit/{problem.index}",
        expires_at=v.expires_at,
    )


@router.post("/verify/check", response_model=VerifyCheckOut)
async def verify_check(
    body: VerifyCheckIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    cf: CodeforcesClient = Depends(get_cf),
) -> VerifyCheckOut:
    await rate_limit(redis, f"verify-check:ip:{client_ip(request)}", limit=30, window_seconds=600)
    v = await session.get(Verification, body.verification_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown verification. Start again.")
    if v.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "This verification was already used.")
    now = datetime.now(UTC)
    if now > v.expires_at:
        raise HTTPException(status.HTTP_410_GONE, "This verification expired. Start again.")

    try:
        recent = await cf.user_status(v.handle, start=1, count=10)
    except CFError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Couldn't reach Codeforces. Try again."
        ) from exc

    found = any(
        s.problem.id == v.problem_id
        and s.verdict == "COMPILATION_ERROR"
        and s.created_at >= v.created_at - CLOCK_SKEW
        for s in recent
    )
    if not found:
        return VerifyCheckOut(
            verified=False,
            message="No compilation error on that problem yet. If you just submitted, wait for "
            "Codeforces to judge it and check again.",
        )

    v.completed = True
    user = await session.scalar(select(User).where(User.handle_key == v.handle_key))
    if user is None:
        user = User(handle_key=v.handle_key, verified_at=now)
        session.add(user)
    else:
        user.verified_at = now
    await session.commit()
    set_session_cookie(response, issue_token(user))
    return VerifyCheckOut(verified=True, message="Handle verified.", handle=v.handle)


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> MeOut:
    h = await session.get(Handle, user.handle_key)
    return MeOut(handle=h.handle if h else user.handle_key, verified_at=user.verified_at)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response
