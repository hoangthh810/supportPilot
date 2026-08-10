"""Real PostgreSQL repeatability checks for the payment-mismatch-v01 seed profile."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.seeds.payment_mismatch_v01.seed import PROFILE_ID, seed_profile


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required")
    return value


def snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    encoded = json.dumps(snapshot, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def support_snapshot(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as connection:
        users = (
            await connection.execute(
                text(
                    """
                    SELECT id::text, email::text, role::text, status::text,
                           created_at::text, updated_at::text
                    FROM support.users
                    WHERE id IN (
                        '00000000-0000-4000-8000-000000000101',
                        '00000000-0000-4000-8000-000000000102',
                        '00000000-0000-4000-8000-000000000103'
                    )
                    ORDER BY id
                    """
                )
            )
        ).tuples().all()
        customers = (
            await connection.execute(
                text(
                    """
                    SELECT id::text, user_id::text, commerce_customer_ref, email::text,
                           phone, verified_at::text, status::text, created_at::text,
                           updated_at::text
                    FROM support.customers
                    WHERE id = '00000000-0000-4000-8000-000000000201'
                    """
                )
            )
        ).tuples().all()
        ticket_count = await connection.scalar(text("SELECT count(*) FROM support.support_tickets"))
    return {
        "users": [tuple(row) for row in users],
        "customers": [tuple(row) for row in customers],
        "ticket_count": ticket_count,
    }


async def commerce_snapshot(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as connection:
        tables: dict[str, list[tuple[Any, ...]]] = {}
        queries = {
            "customers": """
                SELECT id::text, external_ref, email::text, status::text, is_synthetic,
                       created_at::text, updated_at::text
                FROM commerce.customers
                WHERE id IN (
                    '10000000-0000-4000-8000-000000000001',
                    '10000000-0000-4000-8000-000000000002'
                )
                ORDER BY id
            """,
            "products": """
                SELECT id::text, sku, name, normalized_name, category, status::text,
                       is_synthetic, created_at::text, updated_at::text
                FROM commerce.products
                WHERE id = '20000000-0000-4000-8000-000000000001'
                ORDER BY id
            """,
            "orders": """
                SELECT id::text, customer_id::text, order_number, status::text,
                       payment_status::text, total_amount::text, currency, version,
                       is_synthetic, created_at::text, updated_at::text
                FROM commerce.orders
                WHERE id IN (
                    '30000000-0000-4000-8000-000000000001',
                    '30000000-0000-4000-8000-000000000002',
                    '30000000-0000-4000-8000-000000000003'
                )
                ORDER BY id
            """,
            "order_items": """
                SELECT id::text, order_id::text, product_id::text, variant, quantity,
                       unit_amount::text, currency, is_synthetic, created_at::text,
                       updated_at::text
                FROM commerce.order_items
                WHERE id IN (
                    '31000000-0000-4000-8000-000000000001',
                    '31000000-0000-4000-8000-000000000002',
                    '31000000-0000-4000-8000-000000000003'
                )
                ORDER BY id
            """,
            "payments": """
                SELECT id::text, customer_id::text, order_id::text, transaction_ref,
                       status::text, amount::text, currency, payment_method, paid_at::text,
                       version, is_synthetic, created_at::text, updated_at::text
                FROM commerce.payments
                WHERE id = '40000000-0000-4000-8000-000000000001'
                ORDER BY id
            """,
        }
        for name, query in queries.items():
            rows = (await connection.execute(text(query))).tuples().all()
            tables[name] = [tuple(row) for row in rows]
        history_counts = {
            "idempotency_records": await connection.scalar(
                text("SELECT count(*) FROM commerce.idempotency_records")
            ),
            "audit_logs": await connection.scalar(text("SELECT count(*) FROM commerce.audit_logs")),
        }
    return {"tables": tables, "history_counts": history_counts}


async def main() -> None:
    support_url = required_environment("SUPPORT_DATABASE_URL")
    commerce_url = required_environment("COMMERCE_DATABASE_URL")
    support_engine = create_async_engine(support_url)
    commerce_engine = create_async_engine(commerce_url)
    try:
        first_summary = await seed_profile(
            support_database_url=support_url,
            commerce_database_url=commerce_url,
        )
        first = {
            "support": await support_snapshot(support_engine),
            "commerce": await commerce_snapshot(commerce_engine),
        }
        second_summary = await seed_profile(
            support_database_url=support_url,
            commerce_database_url=commerce_url,
        )
        second = {
            "support": await support_snapshot(support_engine),
            "commerce": await commerce_snapshot(commerce_engine),
        }
    finally:
        await support_engine.dispose()
        await commerce_engine.dispose()

    assert first_summary == second_summary
    assert first_summary.profile_id == PROFILE_ID
    assert first_summary.golden_cases == 25
    assert snapshot_hash(first) == snapshot_hash(second)
    assert len(first["support"]["users"]) == 3
    assert len(first["support"]["customers"]) == 1
    assert first["support"]["ticket_count"] == second["support"]["ticket_count"]
    expected_counts = {
        "customers": 2,
        "products": 1,
        "orders": 3,
        "order_items": 3,
        "payments": 1,
    }
    assert {
        table_name: len(rows)
        for table_name, rows in first["commerce"]["tables"].items()
    } == expected_counts
    assert first["commerce"]["history_counts"] == second["commerce"]["history_counts"]
    assert all(row[-3] is True for row in first["commerce"]["tables"]["customers"])
    print(
        json.dumps(
            {
                "profile_id": PROFILE_ID,
                "profile_checksum": first_summary.profile_checksum,
                "snapshot_checksum": snapshot_hash(first),
                "repeatable": True,
                "duplicate_free": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
