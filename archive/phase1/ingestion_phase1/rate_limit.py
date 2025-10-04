"""Token bucket rate limiter for REST workloads."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class TokenBucket:
    """Simple token bucket limiter supporting async acquisition."""

    def __init__(self, capacity: int, refill_rate_per_sec: float) -> None:
        self._capacity = capacity
        self._tokens = capacity
        self._refill_rate = refill_rate_per_sec
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._waiters: deque[asyncio.Future[None]] = deque()

    async def acquire(self, tokens: int = 1) -> None:
        """Wait until the requested number of tokens are available."""

        async with self._lock:
            self._refill()
            if self._tokens >= tokens and not self._waiters:
                self._tokens -= tokens
                return

            loop = asyncio.get_running_loop()
            future: asyncio.Future[None] = loop.create_future()
            waiter_entry = (future, tokens)
            self._waiters.append(waiter_entry)

        try:
            await future
        finally:
            async with self._lock:
                try:
                    self._waiters.remove(waiter_entry)
                except ValueError:
                    pass

    def _refill(self) -> None:
        """Replenish bucket based on elapsed time."""

        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        refill = elapsed * self._refill_rate
        if refill <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + refill)
        self._last_refill = now
        self._drain_waiters()

    def _drain_waiters(self) -> None:
        """Release waiters if enough tokens accumulated."""

        while self._waiters and self._tokens >= self._waiters[0][1]:
            future, tokens = self._waiters.popleft()
            if not future.done():
                self._tokens -= tokens
                future.set_result(None)

    @property
    def tokens(self) -> int:
        """Return current token count (approximate)."""

        self._refill()
        return int(self._tokens)
