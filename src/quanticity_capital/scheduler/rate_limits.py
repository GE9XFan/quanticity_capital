"""Token bucket utilities for the scheduler."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from ..config.models import ScheduleBucketConfig


@dataclass(slots=True)
class TokenBucketState:
    """Serializable token bucket representation."""

    tokens: float
    last_refill: float


class TokenBucket:
    """Simple token bucket supporting fractional refill."""

    def __init__(self, name: str, config: ScheduleBucketConfig) -> None:
        self.name = name
        self.capacity = float(config.capacity)
        self.refill_per_second = float(config.refill_per_second)
        self.tokens = self.capacity
        self.last_refill = time.time()

    def _refill(self, now: float | None = None) -> None:
        reference = now or time.time()
        elapsed = max(reference - self.last_refill, 0)
        if elapsed <= 0:
            return
        refill_amount = elapsed * self.refill_per_second
        if refill_amount > 0:
            self.tokens = min(self.capacity, self.tokens + refill_amount)
            self.last_refill = reference

    def consume(self, amount: float = 1.0, *, now: float | None = None) -> bool:
        """Attempt to consume ``amount`` tokens."""

        self._refill(now)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def time_until_available(self, amount: float = 1.0, *, now: float | None = None) -> float:
        """Return seconds until ``amount`` tokens become available."""

        reference = now or time.time()
        self._refill(reference)
        if self.tokens >= amount:
            return 0.0
        deficit = amount - self.tokens
        return deficit / self.refill_per_second if self.refill_per_second else float("inf")

    def snapshot(self) -> TokenBucketState:
        return TokenBucketState(tokens=self.tokens, last_refill=self.last_refill)

    def restore(self, state: TokenBucketState) -> None:
        self.tokens = min(self.capacity, max(state.tokens, 0))
        self.last_refill = state.last_refill


def snapshot_buckets(buckets: Dict[str, "TokenBucket"]) -> Dict[str, TokenBucketState]:
    return {name: bucket.snapshot() for name, bucket in buckets.items()}


def restore_buckets(buckets: Dict[str, "TokenBucket"], state: Dict[str, TokenBucketState]) -> None:
    for name, bucket in buckets.items():
        if name in state:
            bucket.restore(state[name])


__all__ = ["TokenBucket", "TokenBucketState", "snapshot_buckets", "restore_buckets"]
