"""End-to-end API flow against real Postgres + Redis, with a fake Codeforces."""

from __future__ import annotations

import math
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cf.client import (
    CFContest,
    CFProblem,
    CFProblemStat,
    CFRatingChange,
    CFSubmission,
    CFUser,
    HandleNotFound,
)
from app.cf.sync import refresh_problemset, sync_handle
from app.db import get_session
from app.main import create_app
from app.models import Handle
from app.services import pool_cache

NOW = datetime.now(UTC)
TAGS = ["dp", "greedy", "math", "strings", "graphs", "implementation"]
SKILL = {"dp": -250, "greedy": 120, "math": 60, "strings": 0, "graphs": -50, "implementation": 100}


class FakeCF:
    """Just enough of Codeforces for the app: 100 contests and a user with a weakness in dp."""

    def __init__(self) -> None:
        rng = random.Random(42)
        self.problems: list[dict[str, Any]] = []
        self.contest_list: list[CFContest] = []
        for c in range(1500, 1600):
            start = NOW - timedelta(days=(1600 - c) * 7)
            self.contest_list.append(
                CFContest(
                    id=c,
                    name=f"Round {c}",
                    phase="FINISHED",
                    startTimeSeconds=int(start.timestamp()),
                )
            )
            for i, idx in enumerate("ABCDEF"):
                tags = sorted(rng.sample(TAGS, rng.choice([1, 2])))
                self.problems.append(
                    {
                        "contestId": c,
                        "index": idx,
                        "name": f"P{c}{idx}",
                        "rating": 800 + 200 * i,
                        "tags": tags,
                    }
                )
        self.subs: list[dict[str, Any]] = []
        self.ratings: list[CFRatingChange] = []
        next_id = 1000
        for k, p in enumerate(self.problems[:420]):
            if p["rating"] > 1800:
                continue
            delta = sum(SKILL[t] for t in p["tags"]) / len(p["tags"])
            prob = 1 / (1 + math.exp(-math.log(10) / 400 * (1500 + delta - p["rating"])))
            if rng.random() > 0.8:
                continue
            when = NOW - timedelta(days=400 - k // 2)
            ptype = "CONTESTANT" if p["contestId"] % 4 == 0 else "PRACTICE"
            verdict = "OK" if rng.random() < prob else "WRONG_ANSWER"
            self._add(next_id, p, verdict, when, ptype)
            next_id += 1
        self.next_id = next_id
        for i, c in enumerate(c for c in range(1500, 1600) if c % 4 == 0):
            start = NOW - timedelta(days=(1600 - c) * 7)
            self.ratings.append(
                CFRatingChange(
                    contestId=c,
                    contestName=f"Round {c}",
                    rank=100,
                    oldRating=1300 + i,
                    newRating=1301 + i,
                    ratingUpdateTimeSeconds=int(start.timestamp()),
                )
            )
        self.status_calls: list[tuple[int, int]] = []

    def _add(self, sid: int, p: dict[str, Any], verdict: str, when: datetime, ptype: str) -> None:
        self.subs.append(
            {
                "id": sid,
                "creationTimeSeconds": int(when.timestamp()),
                "problem": p,
                "author": {"participantType": ptype},
                "programmingLanguage": "C++17",
                "verdict": verdict,
            }
        )

    def submit(self, problem_id: str, verdict: str) -> None:
        p = next(p for p in self.problems if f"{p['contestId']}{p['index']}" == problem_id)
        self._add(self.next_id, p, verdict, datetime.now(UTC), "PRACTICE")
        self.next_id += 1

    async def user_info(self, handle: str) -> CFUser:
        if handle.lower() != "tester_1":
            raise HandleNotFound(handle)
        return CFUser(
            handle="Tester_1", rating=1324, maxRating=1400, rank="pupil", maxRank="specialist"
        )

    async def user_status(
        self, handle: str, start: int = 1, count: int = 500
    ) -> list[CFSubmission]:
        self.status_calls.append((start, count))
        newest_first = sorted(self.subs, key=lambda s: -s["id"])
        return [CFSubmission.model_validate(s) for s in newest_first[start - 1 : start - 1 + count]]

    async def user_rating(self, handle: str) -> list[CFRatingChange]:
        return self.ratings

    async def problemset(self) -> tuple[list[CFProblem], list[CFProblemStat]]:
        probs = [CFProblem.model_validate(p) for p in self.problems]
        stats = [
            CFProblemStat(contestId=p.contest_id, index=p.index, solvedCount=5000) for p in probs
        ]
        return probs, stats

    async def contests(self) -> list[CFContest]:
        return self.contest_list


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.jobs.append((function, args))


@pytest.fixture
async def env(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeCF, FakeQueue, async_sessionmaker[AsyncSession]]]:
    pool_cache.clear()
    app = create_app()
    cf, queue = FakeCF(), FakeQueue()
    app.state.redis = redis
    app.state.cf = cf
    app.state.queue = queue

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as s:
            yield s

    app.dependency_overrides[get_session] = session_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, cf, queue, sessionmaker
    pool_cache.clear()


async def run_sync(sm: async_sessionmaker[AsyncSession], cf: FakeCF, handle: str) -> None:
    async with sm() as s:
        await sync_handle(s, cf, handle)  # type: ignore[arg-type]


async def test_full_flow(env) -> None:  # type: ignore[no-untyped-def]
    client, cf, queue, sm = env
    async with sm() as s:
        assert await refresh_problemset(s, cf) == 600  # type: ignore[arg-type]

    r = await client.post("/api/handles/Tester_1/sync")
    assert r.status_code == 202 and r.json()["sync_state"] == "queued"
    assert queue.jobs == [("sync_handle_job", ("Tester_1",))]
    assert (await client.get("/api/handles/Tester_1/analysis")).status_code == 409

    await run_sync(sm, cf, "Tester_1")
    status = (await client.get("/api/handles/tester_1/status")).json()
    assert status["sync_state"] == "ready" and status["submissions"] == len(cf.subs)
    assert status["handle"] == "Tester_1" and status["rating"] == 1324

    # A second sync request inside the cooldown doesn't enqueue anything.
    await client.post("/api/handles/Tester_1/sync")
    assert len(queue.jobs) == 1

    r = await client.get("/api/handles/Tester_1/analysis")
    assert r.status_code == 200
    a = r.json()
    skills = {s["tag"]: s for s in a["skills"]}
    assert min(skills.values(), key=lambda s: s["delta"])["tag"] == "dp"
    assert skills["dp"]["label"] == "weak"
    assert a["weaknesses"][0]["tag"] == "dp" and "skill" in a["weaknesses"][0]["kinds"]
    assert a["weaknesses"][0]["evidence"]["attempts"] > 0
    assert len(a["rating_history"]) == len(cf.ratings)
    assert a["history"]["dates"] and a["model"]["converged"]
    assert (await client.get("/api/handles/Tester_1/analysis")).json() == a  # served from cache

    recs = (await client.get("/api/handles/Tester_1/recommendations?n=4")).json()["items"]
    attempted = {f"{s['problem']['contestId']}{s['problem']['index']}" for s in cf.subs}
    fresh = [x for x in recs if x["kind"] != "upsolve"]
    assert fresh and not attempted & {x["problem"]["id"] for x in fresh}
    assert recs[0]["focus_tag"] == "dp"

    # Incremental sync only fetches the newest page.
    cf.status_calls.clear()
    await run_sync(sm, cf, "Tester_1")
    assert cf.status_calls == [(1, 500)]


async def test_unknown_handle(env) -> None:  # type: ignore[no-untyped-def]
    client, cf, _, sm = env
    await client.post("/api/handles/nobody_here/sync")
    with pytest.raises(HandleNotFound):
        await run_sync(sm, cf, "nobody_here")
    status = (await client.get("/api/handles/nobody_here/status")).json()
    assert status["sync_state"] == "error" and "does not exist" in status["sync_error"]
    assert (await client.get("/api/handles/x/status")).status_code == 422


async def test_verification_plans_goals_and_progress(env) -> None:  # type: ignore[no-untyped-def]
    client, cf, queue, sm = env
    async with sm() as s:
        await refresh_problemset(s, cf)  # type: ignore[arg-type]
    await client.post("/api/handles/Tester_1/sync")
    await run_sync(sm, cf, "Tester_1")

    assert (await client.get("/api/me/plan/today")).status_code == 401
    start = (await client.post("/api/auth/verify/start", json={"handle": "Tester_1"})).json()
    assert start["problem"]["rating"] == 800 and "/submit/" in start["submit_url"]

    check = await client.post(
        "/api/auth/verify/check", json={"verification_id": start["verification_id"]}
    )
    assert check.json()["verified"] is False

    cf.submit(start["problem"]["id"], "COMPILATION_ERROR")
    check = await client.post(
        "/api/auth/verify/check", json={"verification_id": start["verification_id"]}
    )
    assert check.json()["verified"] is True
    assert "upsolve_session" in check.headers["set-cookie"]
    assert "HttpOnly" in check.headers["set-cookie"]
    reuse = await client.post(
        "/api/auth/verify/check", json={"verification_id": start["verification_id"]}
    )
    assert reuse.status_code == 409

    assert (await client.get("/api/auth/me")).json()["handle"] == "Tester_1"

    put = await client.put("/api/me/goals", json={"daily_count": 3, "focus_tags": ["Strings"]})
    assert put.json() == {"target_rating": None, "daily_count": 3, "focus_tags": ["strings"]}

    plan = (await client.get("/api/me/plan/today")).json()
    assert len(plan["items"]) == 3 and plan["streak"] == 0
    assert plan["items"][0]["focus_tag"] == "strings"
    assert (await client.get("/api/me/plan/today")).json()["items"] == plan["items"]

    first, second = plan["items"][0], plan["items"][1]
    skipped = await client.patch(f"/api/me/plan/items/{second['id']}", json={"status": "skipped"})
    assert skipped.json()["status"] == "skipped"
    bad = await client.patch(f"/api/me/plan/items/{second['id']}", json={"status": "solved"})
    assert bad.status_code == 422

    cf.submit(first["problem"]["id"], "OK")
    await run_sync(sm, cf, "Tester_1")
    plan = (await client.get("/api/me/plan/today")).json()
    assert plan["items"][0]["status"] == "solved" and plan["solved_today"] == 1
    assert plan["streak"] == 1

    progress = (await client.get("/api/me/progress")).json()
    assert progress["plan_solved"] == 1 and progress["plan_days"] == 1 and progress["streak"] == 1

    # A forced refresh is honoured for the verified owner after a minute, but not for others.
    async with sm() as sess:
        h = await sess.get(Handle, "tester_1")
        h.last_synced_at = datetime.now(UTC) - timedelta(minutes=2)
        await sess.commit()
    queue.jobs.clear()
    anon = httpx.AsyncClient(transport=client._transport, base_url="http://test")
    await anon.post("/api/handles/Tester_1/sync?force=true")
    assert queue.jobs == []
    await client.post("/api/handles/Tester_1/sync?force=true")
    assert queue.jobs == [("sync_handle_job", ("Tester_1",))]
    await anon.aclose()

    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_compare(env) -> None:  # type: ignore[no-untyped-def]
    client, cf, _, sm = env
    async with sm() as s:
        await refresh_problemset(s, cf)  # type: ignore[arg-type]
    await run_sync(sm, cf, "Tester_1")
    r = await client.get("/api/compare", params={"a": "Tester_1", "b": "tester_1"})
    assert r.status_code == 200
    assert r.json()["a"]["skills"] == r.json()["b"]["skills"]
    assert (
        await client.get("/api/compare", params={"a": "Tester_1", "b": "ghost"})
    ).status_code == 404
