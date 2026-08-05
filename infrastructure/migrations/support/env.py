from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Phase 1 deliberately has no application metadata or domain migrations.
target_metadata = None
DATABASE_ENVIRONMENT = "SUPPORT_MIGRATION_DATABASE_URL"
SCHEMA = "support"


def database_url() -> str:
    value = os.environ.get(DATABASE_ENVIRONMENT, "").strip()
    if not value:
        raise RuntimeError(f"{DATABASE_ENVIRONMENT} is required")
    if "://support_owner:" not in value:
        raise RuntimeError(f"{DATABASE_ENVIRONMENT} must use support_owner")
    return value


def configure_context(connection: Connection | None = None) -> None:
    options = {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "version_table_schema": SCHEMA,
        "compare_type": True,
    }
    if connection is None:
        context.configure(url=database_url(), literal_binds=True, **options)
    else:
        context.configure(connection=connection, **options)


def run_migrations_offline() -> None:
    configure_context()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    connection.execute(text("SET search_path TO support, pg_catalog"))
    configure_context(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url().replace("%", "%%")
    engine = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
