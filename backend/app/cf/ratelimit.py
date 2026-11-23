"""Rate limiters that keep every process at or below Codeforces' one call every two seconds.

`RedisRateLimiter` is shared by the API and the worker: each caller atomically reserves the next
free time slot in Redis, then sleeps until that slot arrives. `LocalRateLimiter` does the same in
memory for tests and scripts.
"""

import asyncio
import time
from typing import Protocol

from redis.asyncio import Redis


class RateLimiter(Protocol):
    async def acquire(self) -> None: ...


class LocalRateLimiter:
    def __init__(self, min_interval: float) -> None:
        self._interval = min_interval
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + self._interval
        if slot > now:
            await asyncio.sleep(slot - now)


# Reserve the next slot atomically. Uses Redis' own clock so callers on different machines agree.
_RESERVE_SLOT = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local nxt = tonumber(redis.call('GET', KEYS[1]) or '0')
local interval = tonumber(ARGV[1])
local slot = math.max(now, nxt)
redis.call('SET', KEYS[1], slot + interval, 'PX', (slot - now) + interval + 1000)
return slot - now
"""


class RedisRateLimiter:
    def __init__(
        self, redis: Redis, min_interval: float, key: str = "upsolve:cf:next-slot"
    ) -> None:
        self._redis = redis
        self._interval_ms = int(min_interval * 1000)
        self._key = key
        self._script = redis.register_script(_RESERVE_SLOT)

    async def acquire(self) -> None:
        wait_ms = int(await self._script(keys=[self._key], args=[self._interval_ms]))
        if wait_ms > 0:
            await asyncio.sleep(wait_ms / 1000)
