"""Assert the Phase 1 PostgreSQL catalog contains no domain objects."""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ALLOWED_RELATIONS = {"alembic_version"}


async def assert_catalog() -> None:
    url = os.environ.get("SUPPORT_MIGRATION_DATABASE_URL", "").strip()
    if "://support_owner:" not in url:
        raise RuntimeError("SUPPORT_MIGRATION_DATABASE_URL must use support_owner")

    engine = create_async_engine(url)
    async with engine.connect() as connection:
        schema_rows = (
            await connection.execute(
                text(
                    """
                    SELECT namespace.nspname, owner.rolname
                    FROM pg_namespace AS namespace
                    JOIN pg_roles AS owner ON owner.oid = namespace.nspowner
                    WHERE namespace.nspname IN ('support', 'commerce')
                    ORDER BY namespace.nspname
                    """
                )
            )
        ).all()
        expected_schemas = [("commerce", "commerce_owner"), ("support", "support_owner")]
        if schema_rows != expected_schemas:
            raise AssertionError(f"unexpected schema ownership: {schema_rows!r}")

        relations = (
            await connection.execute(
                text(
                    """
                    SELECT namespace.nspname, relation.relname
                    FROM pg_class AS relation
                    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname IN ('support', 'commerce')
                      AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                    ORDER BY namespace.nspname, relation.relname
                    """
                )
            )
        ).all()
        unexpected_relations = [row for row in relations if row.relname not in ALLOWED_RELATIONS]
        if unexpected_relations:
            raise AssertionError(f"domain relations exist in Phase 1: {unexpected_relations!r}")

        enums = (
            await connection.execute(
                text(
                    """
                    SELECT namespace.nspname, type_name.typname
                    FROM pg_type AS type_name
                    JOIN pg_namespace AS namespace ON namespace.oid = type_name.typnamespace
                    WHERE namespace.nspname IN ('support', 'commerce')
                      AND type_name.typtype = 'e'
                    """
                )
            )
        ).all()
        if enums:
            raise AssertionError(f"domain enums exist in Phase 1: {enums!r}")

        extensions = {
            row.extname
            for row in (
                await connection.execute(
                    text(
                        """
                        SELECT extname
                        FROM pg_extension
                        WHERE extname IN ('vector', 'pg_trgm', 'unaccent', 'citext')
                        """
                    )
                )
            ).all()
        }
        expected_extensions = {"vector", "pg_trgm", "unaccent", "citext"}
        if extensions != expected_extensions:
            missing_extensions = expected_extensions - extensions
            raise AssertionError(f"missing PostgreSQL extensions: {missing_extensions}")

    await engine.dispose()
    print("Phase 1 catalog assertions passed: no domain table, enum, or seed data.")


if __name__ == "__main__":
    asyncio.run(assert_catalog())
