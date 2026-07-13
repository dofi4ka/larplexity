from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class RateLimiter:
    """Simple in-memory sliding-window rate limiter per user."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, user_key: int) -> bool:
        async with self._lock:
            now = time.monotonic()
            bucket = self._events[user_key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True

    async def remaining(self, user_key: int) -> int:
        async with self._lock:
            now = time.monotonic()
            bucket = self._events[user_key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            return max(0, self.max_requests - len(bucket))
