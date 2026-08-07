from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.apps.support_api.auth.contracts import AuthenticatedActor
from backend.apps.support_api.auth.service import AuthService
from backend.apps.support_api.core.errors import ApiError

bearer = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    service = getattr(request.app.state, "auth_service", None)
    if not isinstance(service, AuthService):
        raise RuntimeError("authentication service is unavailable")
    return service


async def get_current_actor(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedActor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="UNAUTHENTICATED",
            message="A valid access token is required.",
        )
    return await service.authenticate(credentials.credentials)


def require_roles(
    *roles: str,
) -> Callable[..., Awaitable[AuthenticatedActor]]:
    allowed_roles = frozenset(roles)

    async def role_dependency(
        actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> AuthenticatedActor:
        return service.require_roles(actor, allowed_roles)

    return role_dependency
