from __future__ import annotations

from fastapi import FastAPI, Request

from backend.apps.mock_commerce_api.auth.middleware import InternalServiceAuthMiddleware
from backend.apps.mock_commerce_api.core.config import (
    MockCommerceSettings,
    load_mock_commerce_settings,
)
from backend.apps.mock_commerce_api.core.correlation import CorrelationIdMiddleware


def create_mock_commerce_app(settings: MockCommerceSettings | None = None) -> FastAPI:
    runtime_settings = settings or load_mock_commerce_settings()
    app = FastAPI(title="SupportPilot Mock-Commerce", version="0.1.0")
    app.state.settings = runtime_settings
    app.add_middleware(
        InternalServiceAuthMiddleware,
        internal_service_token=runtime_settings.internal_service_token,
    )
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        return {
            "status": "ready",
            "service": "mock-commerce",
            "correlation_id": request.state.correlation_id,
        }

    return app
