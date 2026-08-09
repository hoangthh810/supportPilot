"""DB-001A forward-migration, physical-contract and repository integration checks."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.auth.repository import PostgresAuthRepository
from backend.apps.support_api.walking_skeleton.repository import PostgresTicketRepository

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG = ROOT / "infrastructure/migrations/support/alembic.ini"
SKELETON_REVISION = "0001_walking_skeleton"
HEAD_REVISION = "0002_db001a_core_support"

DEMO_CUSTOMER_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
DEMO_AGENT_USER_ID = UUID("00000000-0000-4000-8000-000000000102")
DEMO_CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000201")
PRESERVED_TICKET_ID = UUID("00000000-0000-4000-8000-000000000301")
PRESERVED_MESSAGE_ID = UUID("00000000-0000-4000-8000-000000000401")


def pg_catalog_char(value: str | bytes) -> str:
    """Normalize PostgreSQL's internal one-byte ``char`` through asyncpg."""
    return value.decode("ascii") if isinstance(value, bytes) else value


def migration_config() -> Config:
    config = Config(str(ALEMBIC_CONFIG))
    config.set_main_option("script_location", str(ALEMBIC_CONFIG.parent))
    return config


def migrate(revision: str) -> None:
    command.upgrade(migration_config(), revision)


def downgrade(revision: str) -> None:
    command.downgrade(migration_config(), revision)


async def seed_skeleton_fixture(owner_engine: AsyncEngine) -> dict[str, Any]:
    async with owner_engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO support.support_tickets
                    (id, ticket_number, customer_id, source, subject, intent,
                     priority, status, lock_version)
                VALUES
                    (:id, 'SP-PRESERVE-001', :customer_id, 'API',
                     'Synthetic pre-DB-001A ticket', 'payment_mismatch',
                     'HIGH', 'PROCESSING', 3)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": PRESERVED_TICKET_ID, "customer_id": DEMO_CUSTOMER_ID},
        )
        await connection.execute(
            text(
                """
                INSERT INTO support.ticket_messages
                    (id, ticket_id, sender_type, sender_user_id, content, idempotency_key)
                VALUES
                    (:id, :ticket_id, 'CUSTOMER', :user_id,
                     'Synthetic message created on the skeleton revision.',
                     'db001a-preserved-message')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": PRESERVED_MESSAGE_ID,
                "ticket_id": PRESERVED_TICKET_ID,
                "user_id": DEMO_CUSTOMER_USER_ID,
            },
        )
        return await preserved_snapshot(connection)


async def preserved_snapshot(connection: Any) -> dict[str, Any]:
    user = (
        await connection.execute(
            text(
                """
                SELECT id::text, email::text, password_hash, role::text, status::text,
                       created_at, updated_at
                FROM support.users WHERE id = :id
                """
            ),
            {"id": DEMO_CUSTOMER_USER_ID},
        )
    ).mappings().one()
    customer = (
        await connection.execute(
            text(
                """
                SELECT id::text, user_id::text, commerce_customer_ref, email::text,
                       verified_at, status::text, created_at, updated_at
                FROM support.customers WHERE id = :id
                """
            ),
            {"id": DEMO_CUSTOMER_ID},
        )
    ).mappings().one()
    ticket = (
        await connection.execute(
            text(
                """
                SELECT id::text, ticket_number, customer_id::text, source::text, subject,
                       intent, priority::text, status::text, lock_version,
                       created_at, updated_at, resolved_at
                FROM support.support_tickets WHERE id = :id
                """
            ),
            {"id": PRESERVED_TICKET_ID},
        )
    ).mappings().one()
    message = (
        await connection.execute(
            text(
                """
                SELECT id::text, ticket_id::text, sender_type::text, sender_user_id::text,
                       content, idempotency_key, created_at
                FROM support.ticket_messages WHERE id = :id
                """
            ),
            {"id": PRESERVED_MESSAGE_ID},
        )
    ).mappings().one()
    return {
        "user": dict(user),
        "customer": dict(customer),
        "ticket": dict(ticket),
        "message": dict(message),
    }


async def assert_preserved(owner_engine: AsyncEngine, expected: Mapping[str, Any]) -> None:
    async with owner_engine.connect() as connection:
        assert await preserved_snapshot(connection) == expected


async def assert_physical_contract(owner_engine: AsyncEngine) -> None:
    expected_columns = {
        "users": {
            "id",
            "email",
            "password_hash",
            "role",
            "status",
            "last_login_at",
            "created_at",
            "updated_at",
        },
        "customers": {
            "id",
            "user_id",
            "commerce_customer_ref",
            "email",
            "phone",
            "verified_at",
            "status",
            "created_at",
            "updated_at",
        },
        "support_tickets": {
            "id",
            "ticket_number",
            "customer_id",
            "source",
            "subject",
            "intent",
            "priority",
            "status",
            "assigned_user_id",
            "lock_version",
            "created_at",
            "updated_at",
            "resolved_at",
            "closed_at",
        },
        "ticket_messages": {
            "id",
            "ticket_id",
            "sender_type",
            "sender_user_id",
            "content",
            "idempotency_key",
            "created_at",
        },
    }
    async with owner_engine.connect() as connection:
        current_revision = (
            await connection.execute(text("SELECT version_num FROM support.alembic_version"))
        ).scalar_one()
        assert current_revision == HEAD_REVISION

        rows = (
            await connection.execute(
                text(
                    """
                    SELECT table_name, column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'support'
                      AND table_name IN ('users', 'customers', 'support_tickets',
                                         'ticket_messages')
                    """
                )
            )
        ).mappings().all()
        actual_columns: dict[str, set[str]] = {name: set() for name in expected_columns}
        id_defaults: dict[str, str | None] = {}
        for row in rows:
            actual_columns[row["table_name"]].add(row["column_name"])
            if row["column_name"] == "id":
                id_defaults[row["table_name"]] = row["column_default"]
        assert actual_columns == expected_columns
        assert all(value and "gen_random_uuid()" in value for value in id_defaults.values())

        forbidden_columns = {
            column
            for columns in actual_columns.values()
            for column in columns
            if "attachment" in column
            or column.endswith("_cipher")
            or column.endswith("_lookup_hash")
        }
        assert forbidden_columns == set()

        constraints = {
            row["conname"]: (
                pg_catalog_char(row["contype"]),
                pg_catalog_char(row["confdeltype"]),
            )
            for row in (
                await connection.execute(
                    text(
                        """
                        SELECT constraint_row.conname, constraint_row.contype,
                               constraint_row.confdeltype
                        FROM pg_constraint AS constraint_row
                        JOIN pg_namespace AS namespace
                          ON namespace.oid = constraint_row.connamespace
                        WHERE namespace.nspname = 'support'
                          AND constraint_row.conrelid IN (
                            'support.users'::regclass,
                            'support.customers'::regclass,
                            'support.support_tickets'::regclass,
                            'support.ticket_messages'::regclass
                          )
                        """
                    )
                )
            ).mappings()
        }
        required_constraints = {
            "uq_users_email",
            "uq_customers_user_id",
            "uq_customers_commerce_customer_ref",
            "uq_support_tickets_ticket_number",
            "uq_ticket_messages_ticket_id_idempotency_key",
            "ck_support_tickets_lock_version",
            "ck_support_tickets_resolved_at_status",
            "ck_support_tickets_closed_at_status",
            "ck_support_tickets_intent_v0_1",
            "fk_customers_user_id_users",
            "fk_support_tickets_customer_id_customers",
            "fk_support_tickets_assigned_user_id_users",
            "fk_ticket_messages_ticket_id_support_tickets",
            "fk_ticket_messages_sender_user_id_users",
        }
        assert required_constraints <= constraints.keys()
        for name in (
            "fk_customers_user_id_users",
            "fk_support_tickets_customer_id_customers",
            "fk_support_tickets_assigned_user_id_users",
            "fk_ticket_messages_ticket_id_support_tickets",
            "fk_ticket_messages_sender_user_id_users",
        ):
            assert constraints[name] == ("f", "r")

        indexes = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        """
                        SELECT indexname FROM pg_indexes
                        WHERE schemaname = 'support'
                          AND tablename IN ('users', 'customers', 'support_tickets',
                                            'ticket_messages')
                        """
                    )
                )
            ).all()
        }
        assert {
            "ix_support_tickets_customer_created_at",
            "ix_support_tickets_status_updated_at",
            "ix_ticket_messages_ticket_created_id",
        } <= indexes

        cross_schema_fks = (
            await connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM pg_constraint AS constraint_row
                    JOIN pg_class AS source_table ON source_table.oid = constraint_row.conrelid
                    JOIN pg_namespace AS source_schema
                      ON source_schema.oid = source_table.relnamespace
                    JOIN pg_class AS target_table ON target_table.oid = constraint_row.confrelid
                    JOIN pg_namespace AS target_schema
                      ON target_schema.oid = target_table.relnamespace
                    WHERE constraint_row.contype = 'f'
                      AND source_schema.nspname = 'support'
                      AND target_schema.nspname <> 'support'
                    """
                )
            )
        ).scalar_one()
        assert cross_schema_fks == 0


async def expect_integrity_error(engine: AsyncEngine, statement: str) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    except IntegrityError:
        return
    raise AssertionError(f"Expected integrity error for: {statement}")


async def assert_constraints(runtime_engine: AsyncEngine) -> None:
    await expect_integrity_error(
        runtime_engine,
        """
        INSERT INTO support.support_tickets
            (ticket_number, customer_id, source, subject, intent, priority, status)
        VALUES
            ('SP-BAD-INTENT', '00000000-0000-4000-8000-000000000201', 'WEB',
             'Synthetic invalid intent', 'refund', 'NORMAL', 'OPEN')
        """,
    )
    await expect_integrity_error(
        runtime_engine,
        """
        INSERT INTO support.support_tickets
            (ticket_number, customer_id, source, subject, priority, status, lock_version)
        VALUES
            ('SP-BAD-LOCK', '00000000-0000-4000-8000-000000000201', 'WEB',
             'Synthetic invalid lock', 'NORMAL', 'OPEN', 0)
        """,
    )
    await expect_integrity_error(
        runtime_engine,
        """
        INSERT INTO support.support_tickets
            (ticket_number, customer_id, source, subject, priority, status, closed_at)
        VALUES
            ('SP-BAD-CLOSED', '00000000-0000-4000-8000-000000000201', 'WEB',
             'Synthetic invalid closed time', 'NORMAL', 'OPEN', now())
        """,
    )
    await expect_integrity_error(
        runtime_engine,
        """
        INSERT INTO support.support_tickets
            (ticket_number, customer_id, source, subject, priority, status, resolved_at)
        VALUES
            ('SP-BAD-RESOLVED', '00000000-0000-4000-8000-000000000201', 'WEB',
             'Synthetic invalid resolved time', 'NORMAL', 'OPEN', now())
        """,
    )
    await expect_integrity_error(
        runtime_engine,
        f"""
        UPDATE support.support_tickets
        SET assigned_user_id = '{uuid4()}'
        WHERE id = '{PRESERVED_TICKET_ID}'
        """,
    )
    await expect_integrity_error(
        runtime_engine,
        f"DELETE FROM support.users WHERE id = '{DEMO_CUSTOMER_USER_ID}'",
    )


async def assert_repository(runtime_engine: AsyncEngine) -> None:
    repository = PostgresTicketRepository(runtime_engine)
    auth_repository = PostgresAuthRepository(runtime_engine)
    user = await auth_repository.find_user_by_email("customer@example.test")
    assert user is not None
    assert user.id == DEMO_CUSTOMER_USER_ID
    assert user.password_hash.startswith("$argon2")

    key = f"db001a-repository-{uuid4()}"
    actor = Actor(
        id=DEMO_CUSTOMER_USER_ID,
        role="customer",
        status="active",
        customer_id=user.customer_id,
    )
    created = await repository.create_ticket(
        actor=actor,
        subject="Synthetic DB-001A repository check",
        body="Synthetic message for repository compatibility.",
        source="WEB",
        idempotency_key=key,
    )
    replay = await repository.create_ticket(
        actor=actor,
        subject="Synthetic DB-001A repository check",
        body="Synthetic message for repository compatibility.",
        source="WEB",
        idempotency_key=key,
    )
    ticket = created.ticket
    assert replay.ticket.id == ticket.id

    scoped = await repository.get_ticket_for_actor(
        ticket_id=ticket.id,
        actor=actor,
    )
    assert scoped == ticket
    denied = await repository.get_ticket_for_actor(
        ticket_id=ticket.id,
        actor=Actor(
            id=DEMO_AGENT_USER_ID,
            role="customer",
            status="active",
            customer_id=user.customer_id,
        ),
    )
    assert denied is None

    await repository.set_ticket_status(ticket_id=ticket.id, status="ESCALATED")
    escalated = await repository.get_ticket_for_actor(
        ticket_id=ticket.id,
        actor=actor,
    )
    assert escalated is not None and escalated.status == "ESCALATED"

    async with runtime_engine.connect() as connection:
        can_use_commerce = (
            await connection.execute(
                text("SELECT has_schema_privilege(current_user, 'commerce', 'USAGE')")
            )
        ).scalar_one()
        assert can_use_commerce is False


async def run_checks(owner_url: str, runtime_url: str) -> None:
    owner_engine = create_async_engine(owner_url)
    runtime_engine = create_async_engine(runtime_url)
    try:
        await asyncio.to_thread(downgrade, SKELETON_REVISION)
        before = await seed_skeleton_fixture(owner_engine)

        await asyncio.to_thread(migrate, "head")
        await assert_preserved(owner_engine, before)
        await assert_physical_contract(owner_engine)
        await assert_constraints(runtime_engine)
        await assert_repository(runtime_engine)

        before_round_trip = await preserved_snapshot_from_engine(owner_engine)
        await asyncio.to_thread(downgrade, SKELETON_REVISION)
        await assert_preserved(owner_engine, before_round_trip)
        await asyncio.to_thread(migrate, "head")
        await assert_preserved(owner_engine, before_round_trip)
        await assert_physical_contract(owner_engine)
    finally:
        await runtime_engine.dispose()
        await owner_engine.dispose()


async def preserved_snapshot_from_engine(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as connection:
        return await preserved_snapshot(connection)


def main() -> None:
    owner_url = os.environ.get("SUPPORT_MIGRATION_DATABASE_URL", "").strip()
    runtime_url = os.environ.get("SUPPORT_DATABASE_URL", "").strip()
    if "://support_owner:" not in owner_url:
        raise RuntimeError("SUPPORT_MIGRATION_DATABASE_URL must use support_owner")
    if "://support_app:" not in runtime_url:
        raise RuntimeError("SUPPORT_DATABASE_URL must use support_app")
    asyncio.run(run_checks(owner_url, runtime_url))
    print(
        "DB-001A integration passed: forward preservation, physical contract, "
        "constraints, grants, repository compatibility and downgrade/upgrade review."
    )


if __name__ == "__main__":
    main()
