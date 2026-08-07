from __future__ import annotations

import asyncio
import hashlib
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from backend.apps.support_api.core.errors import ApiError


@dataclass(frozen=True, slots=True)
class RateLimitState:
    limit: int
    remaining: int
    reset_after_seconds: int

    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_after_seconds),
        }


class LoginRateLimiter:
    """Process-local v0.1 login limiter without retaining raw email or IP values."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int = 60,
        max_tracked_identities: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._max_tracked_identities = max_tracked_identities
        self._clock = clock
        self._attempts: dict[bytes, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, *, client_identity: str, normalized_email: str) -> RateLimitState:
        now = self._clock()
        key = hashlib.sha256(f"{client_identity}\0{normalized_email}".encode()).digest()
        async with self._lock:
            window_start = now - self._window_seconds
            self._remove_expired_keys(window_start=window_start)
            attempts = self._attempts.get(key)
            if attempts is None:
                if len(self._attempts) >= self._max_tracked_identities:
                    raise self._limited_error(retry_after=self._window_seconds)
                attempts = deque()
                self._attempts[key] = attempts
            if len(attempts) >= self._limit:
                retry_after = max(1, math.ceil(self._window_seconds - (now - attempts[0])))
                raise self._limited_error(retry_after=retry_after)
            attempts.append(now)
            reset_after = max(1, math.ceil(self._window_seconds - (now - attempts[0])))
            return RateLimitState(
                limit=self._limit,
                remaining=self._limit - len(attempts),
                reset_after_seconds=reset_after,
            )

    def _remove_expired_keys(self, *, window_start: float) -> None:
        empty_keys: list[bytes] = []
        for key, attempts in self._attempts.items():
            while attempts and attempts[0] <= window_start:
                attempts.popleft()
            if not attempts:
                empty_keys.append(key)
        for key in empty_keys:
            self._attempts.pop(key, None)

    def _limited_error(self, *, retry_after: int) -> ApiError:
        headers = RateLimitState(
            limit=self._limit,
            remaining=0,
            reset_after_seconds=retry_after,
        ).headers()
        headers["Retry-After"] = str(retry_after)
        return ApiError(
            status_code=429,
            code="INVALID_CREDENTIALS",
            message="The email or password is invalid.",
            headers=headers,
        )
