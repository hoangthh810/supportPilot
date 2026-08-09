"""DB-002A migration, constraint, grant and transaction integration checks."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG = ROOT / "infrastructure/migrations/commerce/alembic.ini"
HEAD = "0001_db002a_commerce"
EXPECTED_TABLES = {
    "audit_logs",
    "customers",
    "idempotency_records",
    "order_items",
    "orders",
    "payments",
    "products",
}
EXPECTED_ENUMS = {
    "customer_status": ["ACTIVE", "DISABLED"],
    "product_status": ["ACTIVE", "INACTIVE"],
    "order_status": ["PENDING_CONFIRMATION", "CONFIRMED"],
    "order_payment_status": ["PENDING", "PAID"],
    "payment_status": ["PENDING", "SUCCEEDED", "FAILED", "REVERSED"],
    "write_result": ["SUCCEEDED", "DENIED", "FAILED"],
}

CUSTOMER_ONE = UUID("10000000-0000-4000-8000-000000000001")
CUSTOMER_TWO = UUID("10000000-0000-4000-8000-000000000002")
PRODUCT = UUID("20000000-0000-4000-8000-000000000001")
ORDER_ONE = UUID("30000000-0000-4000-8000-000000000001")
ORDER_TWO = UUID("30000000-0000-4000-8000-000000000002")
PAYMENT_ONE = UUID("40000000-0000-4000-8000-000000000001")
PAYMENT_TWO = UUID("40000000-0000-4000-8000-000000000002")


def migrate(revision: str, owner_url: str) -> None:
    environment = os.environ.copy()
    environment["COMMERCE_MIGRATION_DATABASE_URL"] = owner_url
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_CONFIG),
            "downgrade" if revision == "base" else "upgrade",
            revision,
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )


async def domain_tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'commerce'
                      AND table_type = 'BASE TABLE'
                      AND table_name <> 'alembic_version'
                    """
                )
            )
        ).scalars()
        return set(rows)


async def enum_values(engine: AsyncEngine) -> dict[str, list[str]]:
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT type.typname, enum.enumlabel
                    FROM pg_type AS type
                    JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
                    JOIN pg_enum AS enum ON enum.enumtypid = type.oid
                    WHERE namespace.nspname = 'commerce'
                    ORDER BY type.typname, enum.enumsortorder
                    """
                )
            )
        ).all()
    values: dict[str, list[str]] = {}
    for name, value in rows:
        values.setdefault(str(name), []).append(str(value))
    return values


async def assert_physical_contract(owner_engine: AsyncEngine) -> None:
    assert await domain_tables(owner_engine) == EXPECTED_TABLES
    assert await enum_values(owner_engine) == EXPECTED_ENUMS
    async with owner_engine.connect() as connection:
        columns = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT table_name, column_name, data_type, udt_name,
                           numeric_precision, numeric_scale,
                           character_maximum_length, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'commerce'
                      AND table_name <> 'alembic_version'
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        by_column = {(str(row["table_name"]), str(row["column_name"])): row for row in columns}
        for table_name in EXPECTED_TABLES:
            assert by_column[(table_name, "id")]["udt_name"] == "uuid"
            assert by_column[(table_name, "created_at")]["data_type"] == (
                "timestamp with time zone"
            )
        for table_name, amount_column in (
            ("orders", "total_amount"),
            ("order_items", "unit_amount"),
            ("payments", "amount"),
        ):
            amount = by_column[(table_name, amount_column)]
            assert (amount["numeric_precision"], amount["numeric_scale"]) == (18, 2)
            currency = by_column[(table_name, "currency")]
            assert currency["data_type"] == "character"
            assert currency["character_maximum_length"] == 3
        assert set(by_column) == {
            ("customers", column)
            for column in (
                "id",
                "external_ref",
                "email",
                "status",
                "is_synthetic",
                "created_at",
                "updated_at",
            )
        } | {
            ("products", column)
            for column in (
                "id",
                "sku",
                "name",
                "normalized_name",
                "category",
                "status",
                "is_synthetic",
                "created_at",
                "updated_at",
            )
        } | {
            ("orders", column)
            for column in (
                "id",
                "customer_id",
                "order_number",
                "status",
                "payment_status",
                "total_amount",
                "currency",
                "version",
                "is_synthetic",
                "created_at",
                "updated_at",
            )
        } | {
            ("order_items", column)
            for column in (
                "id",
                "order_id",
                "product_id",
                "variant",
                "quantity",
                "unit_amount",
                "currency",
                "is_synthetic",
                "created_at",
                "updated_at",
            )
        } | {
            ("payments", column)
            for column in (
                "id",
                "customer_id",
                "order_id",
                "transaction_ref",
                "status",
                "amount",
                "currency",
                "payment_method",
                "paid_at",
                "version",
                "is_synthetic",
                "created_at",
                "updated_at",
            )
        } | {
            ("idempotency_records", column)
            for column in (
                "id",
                "operation",
                "idempotency_key",
                "request_hash",
                "order_id",
                "response_status",
                "response_body",
                "created_at",
            )
        } | {
            ("audit_logs", column)
            for column in (
                "id",
                "correlation_id",
                "action",
                "order_id",
                "result",
                "before_hash",
                "after_hash",
                "details",
                "created_at",
            )
        }

        foreign_keys = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT constraint_name, delete_rule,
                           unique_constraint_schema
                    FROM information_schema.referential_constraints
                    WHERE constraint_schema = 'commerce'
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        assert len(foreign_keys) == 6
        assert all(row["delete_rule"] == "RESTRICT" for row in foreign_keys)
        assert all(row["unique_constraint_schema"] == "commerce" for row in foreign_keys)

        indexes = {
            str(row["indexname"]): str(row["indexdef"])
            for row in (
                await connection.execute(
                    text(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = 'commerce'
                        """
                    )
                )
            ).mappings()
        }
        assert "UNIQUE" in indexes["uq_commerce_payments_transaction_ref"]
        assert (
            "WHERE (transaction_ref IS NOT NULL)" in indexes["uq_commerce_payments_transaction_ref"]
        )
        assert "USING gin" in indexes["ix_commerce_products_normalized_name_trgm"]
        assert "gin_trgm_ops" in indexes["ix_commerce_products_normalized_name_trgm"]


async def assert_grants(commerce_engine: AsyncEngine, support_engine: AsyncEngine) -> None:
    async with commerce_engine.connect() as connection:
        assert (
            await connection.execute(
                text("SELECT has_schema_privilege(current_user, 'commerce', 'USAGE')")
            )
        ).scalar_one()
        assert not (
            await connection.execute(
                text("SELECT has_schema_privilege(current_user, 'support', 'USAGE')")
            )
        ).scalar_one()
        for table_name in EXPECTED_TABLES:
            assert (
                await connection.execute(
                    text(
                        "SELECT has_table_privilege(current_user, :table_name, 'SELECT'), "
                        "has_table_privilege(current_user, :table_name, 'INSERT')"
                    ),
                    {"table_name": f"commerce.{table_name}"},
                )
            ).one() == (True, True)
        for table_name in ("idempotency_records", "audit_logs"):
            assert (
                await connection.execute(
                    text(
                        "SELECT has_table_privilege(current_user, :table_name, 'UPDATE'), "
                        "has_table_privilege(current_user, :table_name, 'DELETE')"
                    ),
                    {"table_name": f"commerce.{table_name}"},
                )
            ).one() == (False, False)

    async with support_engine.connect() as connection:
        assert not (
            await connection.execute(
                text("SELECT has_schema_privilege(current_user, 'commerce', 'USAGE')")
            )
        ).scalar_one()


async def expect_integrity_error(
    engine: AsyncEngine, statement: str, parameters: dict[str, Any]
) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement), parameters)
    except IntegrityError:
        return
    raise AssertionError("expected PostgreSQL to reject an invalid commerce write")


async def seed_contract_fixture(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO commerce.customers (id, external_ref, email)
                VALUES (:one, 'commerce-synthetic-001', 'commerce-001@example.test'),
                       (:two, 'commerce-synthetic-002', 'commerce-002@example.test')
                """
            ),
            {"one": CUSTOMER_ONE, "two": CUSTOMER_TWO},
        )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.products
                    (id, sku, name, normalized_name, category)
                VALUES
                    (:id, 'SYNTHETIC-SKU-001', 'Synthetic Product',
                     'synthetic product', 'demo')
                """
            ),
            {"id": PRODUCT},
        )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.orders
                    (id, customer_id, order_number, total_amount, currency)
                VALUES
                    (:one, :customer_one, 'SYNTH-ORDER-001', 1250000.00, 'VND'),
                    (:two, :customer_two, 'SYNTH-ORDER-002', 2500000.00, 'VND')
                """
            ),
            {
                "one": ORDER_ONE,
                "two": ORDER_TWO,
                "customer_one": CUSTOMER_ONE,
                "customer_two": CUSTOMER_TWO,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.order_items
                    (order_id, product_id, quantity, unit_amount, currency)
                VALUES
                    (:one, :product, 1, 1250000.00, 'VND'),
                    (:two, :product, 2, 1250000.00, 'VND')
                """
            ),
            {"one": ORDER_ONE, "two": ORDER_TWO, "product": PRODUCT},
        )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.payments
                    (id, customer_id, status, amount, currency, payment_method)
                VALUES
                    (:one, :customer_one, 'PENDING', 1250000.00, 'VND', 'bank_transfer'),
                    (:two, :customer_two, 'PENDING', 2500000.00, 'VND', 'bank_transfer')
                """
            ),
            {
                "one": PAYMENT_ONE,
                "two": PAYMENT_TWO,
                "customer_one": CUSTOMER_ONE,
                "customer_two": CUSTOMER_TWO,
            },
        )


async def assert_constraints(engine: AsyncEngine) -> None:
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.customers (external_ref, email)
        VALUES ('commerce-synthetic-001', 'new-customer@example.test')
        """,
        {},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.products (sku, name, normalized_name, category)
        VALUES ('SYNTHETIC-SKU-001', 'Duplicate', 'duplicate', 'demo')
        """,
        {},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.orders
            (customer_id, order_number, total_amount, currency)
        VALUES (:customer, 'SYNTH-ORDER-001', 1.00, 'VND')
        """,
        {"customer": CUSTOMER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.orders
            (customer_id, order_number, total_amount, currency)
        VALUES (:customer, 'SYNTH-NEGATIVE-TOTAL', -1.00, 'VND')
        """,
        {"customer": CUSTOMER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.orders
            (customer_id, order_number, total_amount, currency, version)
        VALUES (:customer, 'SYNTH-ZERO-VERSION', 1.00, 'VND', 0)
        """,
        {"customer": CUSTOMER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.order_items
            (order_id, product_id, quantity, unit_amount, currency)
        VALUES (:order_id, :product_id, 0, 1.00, 'VND')
        """,
        {"order_id": ORDER_ONE, "product_id": PRODUCT},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.orders
            (customer_id, order_number, total_amount, currency)
        VALUES (:customer, 'SYNTH-BAD-CURRENCY', 1.00, 'vnd')
        """,
        {"customer": CUSTOMER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.payments
            (customer_id, status, amount, currency, payment_method)
        VALUES (:customer, 'PENDING', 0, 'VND', 'synthetic')
        """,
        {"customer": CUSTOMER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.payments
            (customer_id, order_id, status, amount, currency, payment_method)
        VALUES (:customer, :other_order, 'PENDING', 1.00, 'VND', 'synthetic')
        """,
        {"customer": CUSTOMER_ONE, "other_order": ORDER_TWO},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.payments
            (customer_id, status, amount, currency, payment_method)
        VALUES (:customer, 'SUCCEEDED', 1.00, 'VND', 'synthetic')
        """,
        {"customer": CUSTOMER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.products
            (sku, name, normalized_name, category, is_synthetic)
        VALUES ('NOT-SYNTHETIC', 'Invalid', 'invalid', 'demo', false)
        """,
        {},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.idempotency_records
            (operation, idempotency_key, request_hash, order_id,
             response_status, response_body)
        VALUES ('OTHER_OPERATION', 'invalid-operation', :request_hash,
                :order_id, 200, '{}'::jsonb)
        """,
        {"request_hash": "f" * 64, "order_id": ORDER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.idempotency_records
            (operation, idempotency_key, request_hash, order_id,
             response_status, response_body)
        VALUES ('SYNC_PAYMENT_STATUS', 'invalid-status', :request_hash,
                :order_id, 99, '{}'::jsonb)
        """,
        {"request_hash": "f" * 64, "order_id": ORDER_ONE},
    )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.audit_logs
            (correlation_id, action, order_id, result)
        VALUES (:correlation_id, 'OTHER_ACTION', :order_id, 'DENIED')
        """,
        {
            "correlation_id": UUID("50000000-0000-4000-8000-000000000099"),
            "order_id": ORDER_ONE,
        },
    )
    await expect_integrity_error(
        engine,
        "DELETE FROM commerce.customers WHERE id = :customer",
        {"customer": CUSTOMER_ONE},
    )

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO commerce.payments
                    (customer_id, transaction_ref, status, amount, currency,
                     payment_method)
                VALUES
                    (:customer, 'SYNTH-TXN-UNIQUE', 'PENDING', 1.00, 'VND', 'synthetic')
                """
            ),
            {"customer": CUSTOMER_ONE},
        )
    await expect_integrity_error(
        engine,
        """
        INSERT INTO commerce.payments
            (customer_id, transaction_ref, status, amount, currency, payment_method)
        VALUES
            (:customer, 'SYNTH-TXN-UNIQUE', 'PENDING', 1.00, 'VND', 'synthetic')
        """,
        {"customer": CUSTOMER_TWO},
    )


async def assert_atomic_sync_and_versions(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        order_version = (
            await connection.execute(
                text(
                    """
                    UPDATE commerce.orders
                    SET payment_status = 'PAID', version = version + 1, updated_at = now()
                    WHERE id = :order_id AND customer_id = :customer_id AND version = 1
                    RETURNING version
                    """
                ),
                {"order_id": ORDER_ONE, "customer_id": CUSTOMER_ONE},
            )
        ).scalar_one()
        payment_version = (
            await connection.execute(
                text(
                    """
                    UPDATE commerce.payments
                    SET order_id = :order_id, status = 'SUCCEEDED', paid_at = now(),
                        version = version + 1, updated_at = now()
                    WHERE id = :payment_id AND customer_id = :customer_id AND version = 1
                    RETURNING version
                    """
                ),
                {
                    "order_id": ORDER_ONE,
                    "payment_id": PAYMENT_ONE,
                    "customer_id": CUSTOMER_ONE,
                },
            )
        ).scalar_one()
        assert (order_version, payment_version) == (2, 2)
        await connection.execute(
            text(
                """
                INSERT INTO commerce.idempotency_records
                    (operation, idempotency_key, request_hash, order_id,
                     response_status, response_body)
                VALUES
                    ('SYNC_PAYMENT_STATUS', 'sync-success-001', :request_hash,
                     :order_id, 200, CAST(:body AS jsonb))
                """
            ),
            {
                "request_hash": "a" * 64,
                "order_id": ORDER_ONE,
                "body": json.dumps({"order_id": str(ORDER_ONE), "status": "PAID"}),
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.audit_logs
                    (correlation_id, action, order_id, result, before_hash,
                     after_hash, details)
                VALUES
                    (:correlation_id, 'SYNC_PAYMENT_STATUS', :order_id,
                     'SUCCEEDED', :before_hash, :after_hash, CAST(:details AS jsonb))
                """
            ),
            {
                "correlation_id": UUID("50000000-0000-4000-8000-000000000001"),
                "order_id": ORDER_ONE,
                "before_hash": f"sha256:{'b' * 64}",
                "after_hash": f"sha256:{'c' * 64}",
                "details": json.dumps({"synthetic": True}),
            },
        )

    async with engine.begin() as connection:
        stale_order = await connection.execute(
            text(
                """
                UPDATE commerce.orders SET version = version + 1
                WHERE id = :id AND version = 1 RETURNING version
                """
            ),
            {"id": ORDER_ONE},
        )
        stale_payment = await connection.execute(
            text(
                """
                UPDATE commerce.payments SET version = version + 1
                WHERE id = :id AND version = 1 RETURNING version
                """
            ),
            {"id": PAYMENT_ONE},
        )
        assert stale_order.scalar_one_or_none() is None
        assert stale_payment.scalar_one_or_none() is None

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO commerce.idempotency_records
                    (operation, idempotency_key, request_hash, order_id,
                     response_status, response_body)
                VALUES
                    ('SYNC_PAYMENT_STATUS', 'sync-rollback-002', :request_hash,
                     :order_id, 200, '{}'::jsonb)
                """
            ),
            {"request_hash": "d" * 64, "order_id": ORDER_TWO},
        )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE commerce.orders SET version = version + 1 "
                    "WHERE id = :id AND version = 1"
                ),
                {"id": ORDER_TWO},
            )
            await connection.execute(
                text(
                    "UPDATE commerce.payments SET version = version + 1 "
                    "WHERE id = :id AND version = 1"
                ),
                {"id": PAYMENT_TWO},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO commerce.idempotency_records
                        (operation, idempotency_key, request_hash, order_id,
                         response_status, response_body)
                    VALUES
                        ('SYNC_PAYMENT_STATUS', 'sync-rollback-002', :request_hash,
                         :order_id, 200, '{}'::jsonb)
                    """
                ),
                {"request_hash": "e" * 64, "order_id": ORDER_TWO},
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError("duplicate idempotency key should roll back the sync")

    async with engine.connect() as connection:
        versions = (
            await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT version FROM commerce.orders WHERE id = :order_id),
                        (SELECT version FROM commerce.payments WHERE id = :payment_id)
                    """
                ),
                {"order_id": ORDER_TWO, "payment_id": PAYMENT_TWO},
            )
        ).one()
        assert versions == (1, 1)
        assert (
            await connection.execute(
                text("SELECT count(*) FROM commerce.audit_logs WHERE order_id = :order_id"),
                {"order_id": ORDER_TWO},
            )
        ).scalar_one() == 0


async def assert_append_only(engine: AsyncEngine) -> None:
    for statement in (
        "UPDATE commerce.idempotency_records SET response_status = 201",
        "DELETE FROM commerce.idempotency_records",
        "UPDATE commerce.audit_logs SET details = '{}'::jsonb",
        "DELETE FROM commerce.audit_logs",
    ):
        try:
            async with engine.begin() as connection:
                await connection.execute(text(statement))
        except DBAPIError:
            continue
        raise AssertionError(f"commerce_app unexpectedly executed: {statement}")


async def run_checks(owner_url: str, commerce_url: str, support_url: str) -> None:
    owner_engine = create_async_engine(owner_url)
    commerce_engine = create_async_engine(commerce_url)
    support_engine = create_async_engine(support_url)
    try:
        await asyncio.to_thread(migrate, "base", owner_url)
        assert await domain_tables(owner_engine) == set()
        assert await enum_values(owner_engine) == {}

        await asyncio.to_thread(migrate, "head", owner_url)
        await assert_physical_contract(owner_engine)
        await assert_grants(commerce_engine, support_engine)
        await seed_contract_fixture(commerce_engine)
        await assert_constraints(commerce_engine)
        await assert_atomic_sync_and_versions(commerce_engine)
        await assert_append_only(commerce_engine)

        await asyncio.to_thread(migrate, "base", owner_url)
        assert await domain_tables(owner_engine) == set()
        assert await enum_values(owner_engine) == {}
        await asyncio.to_thread(migrate, "head", owner_url)
        await assert_physical_contract(owner_engine)
    finally:
        await support_engine.dispose()
        await commerce_engine.dispose()
        await owner_engine.dispose()


def main() -> None:
    owner_url = os.environ.get("COMMERCE_MIGRATION_DATABASE_URL", "").strip()
    commerce_url = os.environ.get("COMMERCE_DATABASE_URL", "").strip()
    support_url = os.environ.get("SUPPORT_DATABASE_URL", "").strip()
    if "://commerce_owner:" not in owner_url:
        raise RuntimeError("COMMERCE_MIGRATION_DATABASE_URL must use commerce_owner")
    if "://commerce_app:" not in commerce_url:
        raise RuntimeError("COMMERCE_DATABASE_URL must use commerce_app")
    if "://support_app:" not in support_url:
        raise RuntimeError("SUPPORT_DATABASE_URL must use support_app")
    asyncio.run(run_checks(owner_url, commerce_url, support_url))
    print(
        f"DB-002A integration passed at {HEAD}: exact seven-table contract, "
        "constraints/indexes/RESTRICT FKs, runtime isolation, append-only grants, "
        "optimistic versions and atomic rollback."
    )


if __name__ == "__main__":
    main()
