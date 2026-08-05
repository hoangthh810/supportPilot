from fastapi import FastAPI

from backend.apps.support_api.core.config import Settings, load_settings
from backend.apps.support_api.core.correlation import CorrelationIdMiddleware
from backend.apps.support_api.core.errors import register_error_handlers
from backend.apps.support_api.core.logging import configure_logging
from backend.apps.support_api.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or load_settings()
    configure_logging(runtime_settings)

    app = FastAPI(title=runtime_settings.app_name, version="0.1.0")
    app.state.settings = runtime_settings
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name=runtime_settings.correlation_header,
    )
    register_error_handlers(app)
    app.include_router(health_router)
    return app

