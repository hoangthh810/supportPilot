from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable
from uuid import UUID

from backend.apps.support_api.core.errors import ApiError


class TicketWriteRateLimiter:
    """Process-local v0.1 write limiter keyed only by principal and operation."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[tuple[UUID, str], deque[float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, *, actor_id: UUID, operation: str) -> None:
        now = self._clock()
        key = (actor_id, operation)
        async with self._lock:
            window_start = now - self._window_seconds
            attempts = self._attempts.setdefault(key, deque())
            while attempts and attempts[0] <= window_start:
                attempts.popleft()
            if len(attempts) >= self._limit:
                retry_after = max(1, math.ceil(self._window_seconds - (now - attempts[0])))
                raise ApiError(
                    status_code=429,
                    code="FORBIDDEN",
                    message="The request rate limit was exceeded.",
                    headers={"Retry-After": str(retry_after)},
                )
            attempts.append(now)
