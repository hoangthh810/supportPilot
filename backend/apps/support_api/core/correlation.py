from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import Message, Receive, Scope, Send

_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def new_correlation_id() -> str:
    return f"corr_{uuid4().hex}"


def normalize_correlation_id(candidate: str | None) -> str:
    if candidate is not None:
        normalized = candidate.strip()
        if _CORRELATION_ID_PATTERN.fullmatch(normalized):
            return normalized
    return new_correlation_id()


def get_correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None)
    return correlation_id if isinstance(correlation_id, str) else new_correlation_id()


class CorrelationIdMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]], *, header_name: str) -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        correlation_id = normalize_correlation_id(headers.get(self.header_name))
        state: dict[str, Any] = scope.setdefault("state", {})
        state["correlation_id"] = correlation_id

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[self.header_name] = correlation_id
            await send(message)

        await self.app(scope, receive, send_with_correlation)

