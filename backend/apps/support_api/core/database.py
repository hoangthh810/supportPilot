from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.apps.support_api.core.config import Settings


def create_support_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.support_database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": "support,pg_catalog"}},
    )
