from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from backend.apps.support_api.auth.contracts import AuthenticatedActor
from backend.apps.support_api.auth.dependencies import get_auth_service, get_current_actor
from backend.apps.support_api.auth.service import AuthService
from backend.apps.support_api.core.correlation import get_correlation_id

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class ActorResponse(BaseModel):
    id: UUID
    role: str
    status: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in_seconds: int
    actor: ActorResponse
    correlation_id: str


class MeResponse(BaseModel):
    actor: ActorResponse
    customer_id: UUID | None
    correlation_id: str


def actor_response(actor: AuthenticatedActor) -> ActorResponse:
    return ActorResponse(id=actor.id, role=actor.role, status=actor.status)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    client_identity = request.client.host if request.client is not None else "unknown"
    result = await service.login(
        email=payload.email,
        password=payload.password,
        client_identity=client_identity,
    )
    for header, value in result.rate_limit_headers.items():
        response.headers[header] = value
    return LoginResponse(
        access_token=result.access_token,
        expires_in_seconds=result.expires_in_seconds,
        actor=actor_response(result.actor),
        correlation_id=get_correlation_id(request),
    )


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
) -> MeResponse:
    return MeResponse(
        actor=actor_response(actor),
        customer_id=actor.customer_id,
        correlation_id=get_correlation_id(request),
    )
