from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from pydantic import SecretStr
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send


class RejectInternalServiceTokenMiddleware:
    """Prevent the internal service credential from authenticating any public API route."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        internal_service_token: SecretStr,
    ) -> None:
        self.app = app
        self._internal_service_token = internal_service_token.get_secret_value()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if scope["type"] != "http" or not (
            path == "/api/v1" or path.startswith("/api/v1/")
        ):
            await self.app(scope, receive, send)
            return

        authorization_values = Headers(scope=scope).getlist("Authorization")
        contains_internal_token = any(
            value.startswith("Bearer ")
            and hmac.compare_digest(
                value.removeprefix("Bearer "), self._internal_service_token
            )
            for value in authorization_values
        )
        if not contains_internal_token:
            await self.app(scope, receive, send)
            return

        state = scope.get("state", {})
        correlation_id = state.get("correlation_id")
        if not isinstance(correlation_id, str):
            correlation_id = "corr_unavailable"
        response = JSONResponse(
            status_code=401,
            content={
                "code": "UNAUTHENTICATED",
                "message": "A valid access token is required.",
                "retryable": False,
                "correlation_id": correlation_id,
                "details": {},
            },
        )
        await response(scope, receive, send)
