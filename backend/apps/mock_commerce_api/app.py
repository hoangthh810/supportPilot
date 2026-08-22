from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from backend.apps.mock_commerce_api.auth.middleware import InternalServiceAuthMiddleware
from backend.apps.mock_commerce_api.core.config import (
    MockCommerceSettings,
    load_mock_commerce_settings,
)
from backend.apps.mock_commerce_api.core.correlation import CorrelationIdMiddleware
from backend.apps.mock_commerce_api.core.database import create_commerce_engine
from backend.apps.mock_commerce_api.core.errors import register_error_handlers
from backend.apps.mock_commerce_api.orders.repository import PostgresOrderRepository
from backend.apps.mock_commerce_api.orders.router import router as order_router
from backend.apps.mock_commerce_api.orders.service import OrderService


def create_mock_commerce_app(
    settings: MockCommerceSettings | None = None,
    order_service: OrderService | None = None,
) -> FastAPI:
    runtime_settings = settings or load_mock_commerce_settings()
    engine = None
    if order_service is None:
        engine = create_commerce_engine(runtime_settings)
        order_service = OrderService(PostgresOrderRepository(engine))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(
        title="SupportPilot Mock-Commerce", version="0.1.0", lifespan=lifespan
    )
    app.state.settings = runtime_settings
    app.state.order_service = order_service
    app.add_middleware(
        InternalServiceAuthMiddleware,
        internal_service_token=runtime_settings.internal_service_token,
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        return {
            "status": "ready",
            "service": "mock-commerce",
            "correlation_id": request.state.correlation_id,
        }

    app.include_router(order_router)
    return app
