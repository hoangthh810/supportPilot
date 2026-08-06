from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.apps.support_api.core.config import Settings, WorkflowProfile, load_settings
from backend.apps.support_api.core.correlation import CorrelationIdMiddleware
from backend.apps.support_api.core.database import create_support_engine
from backend.apps.support_api.core.errors import register_error_handlers
from backend.apps.support_api.core.logging import configure_logging
from backend.apps.support_api.health import router as health_router
from backend.apps.support_api.walking_skeleton.adapters import (
    FakeActionAdapter,
    FakeAgentAdapter,
    FakeApprovalAdapter,
)
from backend.apps.support_api.walking_skeleton.repository import PostgresTicketRepository
from backend.apps.support_api.walking_skeleton.router import router as skeleton_router
from backend.apps.support_api.walking_skeleton.service import SkeletonService


def create_app(
    settings: Settings | None = None,
    skeleton_service: SkeletonService | None = None,
) -> FastAPI:
    runtime_settings = settings or load_settings()
    configure_logging(runtime_settings)

    engine: AsyncEngine | None = None
    if (
        runtime_settings.workflow_profile is WorkflowProfile.WALKING_SKELETON
        and skeleton_service is None
    ):
        engine = create_support_engine(runtime_settings)
        repository = PostgresTicketRepository(engine)
        skeleton_service = SkeletonService(
            settings=runtime_settings,
            repository=repository,
            agent=FakeAgentAdapter(),
            approval=FakeApprovalAdapter(),
            action=FakeActionAdapter(),
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title=runtime_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = runtime_settings
    app.state.skeleton_service = skeleton_service
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name=runtime_settings.correlation_header,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(runtime_settings.frontend_origin).rstrip("/")],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-ID"],
    )
    register_error_handlers(app)
    app.include_router(health_router)
    if skeleton_service is not None:
        app.include_router(skeleton_router)
    return app
