from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.core.correlation import get_correlation_id
from backend.apps.support_api.dependencies import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]
    service: str
    environment: str
    correlation_id: str


@router.get("/health/live", response_model=HealthResponse)
async def liveness(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        correlation_id=get_correlation_id(request),
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    return HealthResponse(
        status="ready",
        service=settings.app_name,
        environment=settings.app_env,
        correlation_id=get_correlation_id(request),
    )

