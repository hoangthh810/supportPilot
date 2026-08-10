from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.apps.support_api.auth.repository import PostgresAuthRepository
from backend.apps.support_api.auth.router import router as auth_router
from backend.apps.support_api.auth.service import AuthService
from backend.apps.support_api.core.config import Settings, WorkflowProfile, load_settings
from backend.apps.support_api.core.correlation import CorrelationIdMiddleware
from backend.apps.support_api.core.database import create_support_engine
from backend.apps.support_api.core.errors import register_error_handlers
from backend.apps.support_api.core.internal_token_isolation import (
    RejectInternalServiceTokenMiddleware,
)
from backend.apps.support_api.core.logging import configure_logging
from backend.apps.support_api.health import router as health_router
from backend.apps.support_api.tickets.contracts import NoopMessageResumePort
from backend.apps.support_api.tickets.rate_limit import TicketWriteRateLimiter
from backend.apps.support_api.tickets.repository import PostgresTicketRepository
from backend.apps.support_api.tickets.router import router as ticket_router
from backend.apps.support_api.tickets.service import TicketService
from backend.apps.support_api.walking_skeleton.adapters import (
    FakeActionAdapter,
    FakeAgentAdapter,
    FakeApprovalAdapter,
)
from backend.apps.support_api.walking_skeleton.router import router as skeleton_router
from backend.apps.support_api.walking_skeleton.service import SkeletonService


def create_app(
    settings: Settings | None = None,
    skeleton_service: SkeletonService | None = None,
    auth_service: AuthService | None = None,
    ticket_service: TicketService | None = None,
) -> FastAPI:
    runtime_settings = settings or load_settings()
    configure_logging(runtime_settings)

    engine: AsyncEngine | None = None
    skeleton_needs_engine = (
        runtime_settings.workflow_profile is WorkflowProfile.WALKING_SKELETON
        and skeleton_service is None
    )
    if auth_service is None or skeleton_needs_engine or ticket_service is None:
        engine = create_support_engine(runtime_settings)

    if auth_service is None:
        if engine is None:
            raise RuntimeError("authentication composition requires a support engine")
        auth_service = AuthService(
            settings=runtime_settings,
            repository=PostgresAuthRepository(engine),
        )

    repository: PostgresTicketRepository | None = None
    if skeleton_needs_engine or ticket_service is None:
        if engine is None:
            raise RuntimeError("Ticket composition requires a support engine")
        repository = PostgresTicketRepository(engine)

    if ticket_service is None:
        if repository is None:
            raise RuntimeError("Ticket repository composition failed")
        ticket_service = TicketService(
            repository=repository,
            resume_port=NoopMessageResumePort(),
            request_timeout_seconds=runtime_settings.workflow_request_timeout_seconds,
            rate_limiter=TicketWriteRateLimiter(
                limit=runtime_settings.request_rate_limit_per_minute
            ),
        )

    if skeleton_needs_engine:
        if repository is None:
            raise RuntimeError("Walking Skeleton repository composition failed")
        skeleton_service = SkeletonService(
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
    app.state.auth_service = auth_service
    app.state.ticket_service = ticket_service
    app.state.skeleton_service = skeleton_service
    app.add_middleware(
        RejectInternalServiceTokenMiddleware,
        internal_service_token=runtime_settings.internal_service_token,
    )
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
    app.include_router(auth_router)
    app.include_router(ticket_router)
    if skeleton_service is not None:
        app.include_router(skeleton_router)
    return app
