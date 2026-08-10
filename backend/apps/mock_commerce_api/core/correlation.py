from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import Message, Receive, Scope, Send

_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def normalize_correlation_id(candidate: str | None) -> str:
    if candidate is not None:
        normalized = candidate.strip()
        if _CORRELATION_ID_PATTERN.fullmatch(normalized):
            return normalized
    return f"corr_{uuid4().hex}"


class CorrelationIdMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = normalize_correlation_id(Headers(scope=scope).get("X-Correlation-ID"))
        state: dict[str, Any] = scope.setdefault("state", {})
        state["correlation_id"] = correlation_id

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Correlation-ID"] = correlation_id
            await send(message)

        await self.app(scope, receive, send_with_correlation)
