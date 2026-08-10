from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import SecretStr
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send


class InternalServiceAuthMiddleware:
    """Authenticate every internal route before routing or body consumption."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        internal_service_token: SecretStr,
    ) -> None:
        self.app = app
        self._expected_token = internal_service_token.get_secret_value()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if scope["type"] != "http" or not (
            path == "/internal/v1" or path.startswith("/internal/v1/")
        ):
            await self.app(scope, receive, send)
            return

        authorization_values = Headers(scope=scope).getlist("Authorization")
        presented = self._parse_bearer(authorization_values)
        if presented is None:
            await self._reject(
                scope,
                receive,
                send,
                status_code=401,
                code="INTERNAL_UNAUTHENTICATED",
                message="A valid internal Bearer token is required.",
            )
            return
        if not hmac.compare_digest(presented, self._expected_token):
            await self._reject(
                scope,
                receive,
                send,
                status_code=403,
                code="INTERNAL_FORBIDDEN",
                message="The supplied credential is not allowed for this internal API.",
            )
            return

        state: dict[str, Any] = scope.setdefault("state", {})
        state["internal_service_authenticated"] = True
        await self.app(scope, receive, send)

    @staticmethod
    def _parse_bearer(values: list[str]) -> str | None:
        if len(values) != 1:
            return None
        value = values[0]
        if not value.startswith("Bearer "):
            return None
        token = value.removeprefix("Bearer ")
        if not token or token != token.strip() or any(character.isspace() for character in token):
            return None
        return token

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        state = scope.get("state", {})
        correlation_id = state.get("correlation_id")
        if not isinstance(correlation_id, str):
            correlation_id = "corr_unavailable"
        response = JSONResponse(
            status_code=status_code,
            content={
                "code": code,
                "message": message,
                "retryable": False,
                "correlation_id": correlation_id,
                "details": {},
            },
        )
        await response(scope, receive, send)
