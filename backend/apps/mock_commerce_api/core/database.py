from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.apps.mock_commerce_api.core.config import MockCommerceSettings


def create_commerce_engine(settings: MockCommerceSettings) -> AsyncEngine:
    return create_async_engine(
        settings.commerce_database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": "commerce,pg_catalog"}},
    )
