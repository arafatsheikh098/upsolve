from __future__ import annotations

import re
from typing import Any, Protocol

import jwt
from fastapi import Cookie, Depends, HTTPException, Path, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cf.client import CodeforcesClient
from app.config import get_settings
from app.db import get_session
from app.models import User

SESSION_COOKIE = "upsolve_session"
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,24}$")


class JobQueue(Protocol):
    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> Any: ...


def valid_handle(handle: str = Path(..., description="Codeforces handle")) -> str:
    if not _HANDLE_RE.match(handle):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That isn't a valid handle.")
    return handle


def get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


def get_cf(request: Request) -> CodeforcesClient:
    return request.app.state.cf  # type: ignore[no-any-return]


def get_queue(request: Request) -> JobQueue:
    return request.app.state.queue  # type: ignore[no-any-return]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def rate_limit(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window limiter. Raises 429 once `limit` hits happen within the window."""
    full = f"upsolve:rl:{key}"
    count = await redis.incr(full)
    if count == 1:
        await redis.expire(full, window_seconds)
    if count > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please wait a few minutes."
        )


async def optional_user(
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return await session.get(User, user_id)


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Verify your handle to use this.")
    return user
