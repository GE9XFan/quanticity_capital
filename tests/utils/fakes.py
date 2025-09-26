"""Async Redis test doubles for unit tests."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class FakeRedis:
    """A minimal async Redis replacement for unit tests."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._sets: Dict[str, set[str]] = defaultdict(set)
        self._hashes: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._streams: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
        self._counter = 0

    def _now(self) -> float:
        return time.time()

    def _purge_if_expired(self, key: str) -> None:
        expiry = self._expiry.get(key)
        if expiry is not None and expiry <= self._now():
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        self._data[key] = value
        if ex is not None:
            self._expiry[key] = self._now() + ex
        else:
            self._expiry.pop(key, None)
        return True

    async def get(self, key: str) -> Optional[Any]:
        self._purge_if_expired(key)
        return self._data.get(key)

    async def expire(self, key: str, ttl: int) -> bool:
        if key not in self._data:
            return False
        self._expiry[key] = self._now() + ttl
        return True

    async def ttl(self, key: str) -> int:
        self._purge_if_expired(key)
        if key not in self._data:
            return -2
        expiry = self._expiry.get(key)
        if expiry is None:
            return -1
        remaining = int(expiry - self._now())
        return remaining if remaining >= 0 else -2

    async def xadd(self, key: str, fields: Dict[str, Any]) -> str:
        self._counter += 1
        entry_id = f"{int(self._now() * 1000)}-{self._counter}"
        self._streams[key].append((entry_id, dict(fields)))
        return entry_id

    async def sadd(self, key: str, member: str) -> int:
        before = len(self._sets[key])
        self._sets[key].add(member)
        return 1 if len(self._sets[key]) > before else 0

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        existing = self._hashes[key]
        before = len(existing)
        for field, value in mapping.items():
            existing[str(field)] = str(value)
        return len(existing) - before

    async def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def close(self) -> None:  # pragma: no cover - compatibility with real client
        return None

    def stream_entries(self, key: str) -> List[Tuple[str, Dict[str, Any]]]:
        return list(self._streams.get(key, []))


__all__ = ["FakeRedis"]
