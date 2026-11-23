"""Codeforces client: parsing of recorded responses, retries, typed errors, rate limiting."""

import asyncio
import itertools
import json
import time
from pathlib import Path

import httpx
import pytest
import respx

from app.cf.client import CFError, CFUnavailable, CodeforcesClient, HandleNotFound
from app.cf.ratelimit import LocalRateLimiter

BASE = "https://cf.test/api"
FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:  # type: ignore[type-arg]
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    async with httpx.AsyncClient(base_url=BASE) as http:
        yield CodeforcesClient(http, LocalRateLimiter(0), backoff_base=0)


@respx.mock
async def test_parses_recorded_responses(client: CodeforcesClient) -> None:
    respx.get(f"{BASE}/user.info").respond(json=fixture("user_info.json"))
    respx.get(f"{BASE}/user.status").respond(json=fixture("user_status.json"))
    respx.get(f"{BASE}/user.rating").respond(json=fixture("user_rating.json"))
    respx.get(f"{BASE}/problemset.problems").respond(json=fixture("problemset.json"))
    respx.get(f"{BASE}/contest.list").respond(json=fixture("contest_list.json"))

    user = await client.user_info("arafatsheikh098")
    assert (user.handle, user.rating, user.max_rank) == ("arafatsheikh098", 1121, "pupil")

    subs = await client.user_status("arafatsheikh098", start=1, count=3)
    assert len(subs) == 3
    first = subs[0]
    assert first.problem.id == "2266B"
    assert first.verdict == "OK"
    assert first.author.participant_type == "PRACTICE"
    assert first.created_at.year == 2026

    status_call = respx.calls[1].request
    assert status_call.url.params["from"] == "1" and status_call.url.params["count"] == "3"

    changes = await client.user_rating("arafatsheikh098")
    assert changes[0].old_rating == 0 and changes[0].new_rating == 370

    problems, stats = await client.problemset()
    assert problems and stats
    assert all(p.id.startswith(str(p.contest_id)) for p in problems)

    contests = await client.contests()
    assert {c.id for c in contests} >= {2000, 2001}


@respx.mock
async def test_retries_transient_failures(client: CodeforcesClient) -> None:
    route = respx.get(f"{BASE}/user.info").mock(
        side_effect=[
            httpx.Response(503),
            httpx.ConnectError("boom"),
            httpx.Response(200, json={"status": "FAILED", "comment": "Call limit exceeded"}),
            httpx.Response(200, json=fixture("user_info.json")),
        ]
    )
    user = await client.user_info("arafatsheikh098")
    assert user.handle == "arafatsheikh098"
    assert route.call_count == 4


@respx.mock
async def test_gives_up_after_max_retries(client: CodeforcesClient) -> None:
    route = respx.get(f"{BASE}/user.info").respond(502)
    with pytest.raises(CFUnavailable):
        await client.user_info("x")
    assert route.call_count == 5  # 1 try + 4 retries


@respx.mock
async def test_unknown_handle_is_a_typed_error(client: CodeforcesClient) -> None:
    respx.get(f"{BASE}/user.info").respond(
        400, json={"status": "FAILED", "comment": "handles: User with handle nobody not found"}
    )
    with pytest.raises(HandleNotFound):
        await client.user_info("nobody")


@respx.mock
async def test_other_failures_are_not_retried(client: CodeforcesClient) -> None:
    route = respx.get(f"{BASE}/user.status").respond(
        400, json={"status": "FAILED", "comment": "count: Field should contain only digits"}
    )
    with pytest.raises(CFError):
        await client.user_status("x")
    assert route.call_count == 1


async def test_local_rate_limiter_spaces_calls() -> None:
    limiter = LocalRateLimiter(0.05)
    t0 = time.monotonic()
    await asyncio.gather(*(limiter.acquire() for _ in range(5)))
    # 5 calls with a 50 ms gap need at least 200 ms
    assert time.monotonic() - t0 >= 0.19


async def test_redis_rate_limiter_is_shared_between_instances(redis) -> None:  # type: ignore[no-untyped-def]
    """Two limiters (think: API process and worker process) share one schedule via Redis."""
    from app.cf.ratelimit import RedisRateLimiter

    a = RedisRateLimiter(redis, 0.05, key="test:slot")
    b = RedisRateLimiter(redis, 0.05, key="test:slot")
    stamps: list[float] = []

    async def call(limiter: RedisRateLimiter) -> None:
        await limiter.acquire()
        stamps.append(time.monotonic())

    await asyncio.gather(*(call(x) for x in (a, b, a, b, a, b)))
    stamps.sort()
    gaps = [later - earlier for earlier, later in itertools.pairwise(stamps)]
    assert min(gaps) >= 0.04
