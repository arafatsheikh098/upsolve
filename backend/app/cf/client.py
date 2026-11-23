"""A small, typed Codeforces API client.

Every call goes through a shared rate limiter. Network errors, 5xx/429 responses and
"Call limit exceeded" are retried with exponential backoff; everything else becomes a typed error.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.cf.ratelimit import RateLimiter

log = logging.getLogger(__name__)


class CFError(Exception):
    """Codeforces answered, but with an error we can't recover from."""


class HandleNotFound(CFError):
    def __init__(self, handle: str) -> None:
        super().__init__(f"Codeforces handle '{handle}' was not found")
        self.handle = handle


class CFUnavailable(CFError):
    """Codeforces is down, timing out, or rate-limiting us after all retries."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class CFUser(_Model):
    handle: str
    rating: int | None = None
    max_rating: int | None = Field(default=None, alias="maxRating")
    rank: str | None = None
    max_rank: str | None = Field(default=None, alias="maxRank")
    avatar: str | None = Field(default=None, alias="titlePhoto")


class CFProblem(_Model):
    contest_id: int | None = Field(default=None, alias="contestId")
    problemset_name: str | None = Field(default=None, alias="problemsetName")
    index: str
    name: str
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)

    @property
    def id(self) -> str:
        if self.contest_id is not None:
            return f"{self.contest_id}{self.index}"
        return f"{self.problemset_name or 'x'}-{self.index}"


class CFAuthor(_Model):
    participant_type: str = Field(alias="participantType")


class CFSubmission(_Model):
    id: int
    creation_time_seconds: int = Field(alias="creationTimeSeconds")
    problem: CFProblem
    author: CFAuthor
    programming_language: str = Field(alias="programmingLanguage")
    verdict: str | None = None

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self.creation_time_seconds, tz=UTC)


class CFRatingChange(_Model):
    contest_id: int = Field(alias="contestId")
    contest_name: str = Field(alias="contestName")
    rank: int
    old_rating: int = Field(alias="oldRating")
    new_rating: int = Field(alias="newRating")
    rating_update_time_seconds: int = Field(alias="ratingUpdateTimeSeconds")


class CFProblemStat(_Model):
    contest_id: int | None = Field(default=None, alias="contestId")
    index: str
    solved_count: int = Field(alias="solvedCount")


class CFContest(_Model):
    id: int
    name: str
    phase: str
    start_time_seconds: int | None = Field(default=None, alias="startTimeSeconds")


USER_AGENT = "Upsolve/0.1 (Codeforces practice coach)"
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class CodeforcesClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        limiter: RateLimiter,
        *,
        max_retries: int = 4,
        backoff_base: float = 2.0,
    ) -> None:
        self._http = http
        self._limiter = limiter
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    async def _call(self, method: str, **params: Any) -> Any:
        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            if attempt:
                await asyncio.sleep(self._backoff_base * 2 ** (attempt - 1))
            await self._limiter.acquire()
            try:
                resp = await self._http.get(f"/{method}", params=params)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning("CF %s network error (attempt %d): %s", method, attempt + 1, last_error)
                continue

            if resp.status_code in _RETRY_STATUSES:
                last_error = f"HTTP {resp.status_code}"
                log.warning("CF %s returned %s (attempt %d)", method, resp.status_code, attempt + 1)
                continue

            try:
                body = resp.json()
            except ValueError:
                last_error = f"non-JSON response (HTTP {resp.status_code})"
                continue

            if body.get("status") == "OK":
                return body["result"]

            comment = str(body.get("comment", ""))
            if "limit exceeded" in comment.lower():
                last_error = comment
                continue
            if "not found" in comment.lower() and "handle" in comment.lower():
                raise HandleNotFound(str(params.get("handle") or params.get("handles") or ""))
            raise CFError(comment or f"Codeforces error (HTTP {resp.status_code})")

        raise CFUnavailable(f"Codeforces API unavailable: {last_error}")

    async def user_info(self, handle: str) -> CFUser:
        result = await self._call("user.info", handles=handle)
        return CFUser.model_validate(result[0])

    async def user_status(
        self, handle: str, start: int = 1, count: int = 500
    ) -> list[CFSubmission]:
        result = await self._call("user.status", handle=handle, **{"from": start, "count": count})
        return [CFSubmission.model_validate(s) for s in result]

    async def user_rating(self, handle: str) -> list[CFRatingChange]:
        result = await self._call("user.rating", handle=handle)
        return [CFRatingChange.model_validate(r) for r in result]

    async def problemset(self) -> tuple[list[CFProblem], list[CFProblemStat]]:
        result = await self._call("problemset.problems")
        problems = [CFProblem.model_validate(p) for p in result["problems"]]
        stats = [CFProblemStat.model_validate(s) for s in result["problemStatistics"]]
        return problems, stats

    async def contests(self) -> list[CFContest]:
        result = await self._call("contest.list", gym="false")
        return [CFContest.model_validate(c) for c in result]
