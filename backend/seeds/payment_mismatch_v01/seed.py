from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

PROFILE_ID = "payment-mismatch-v01"
PROFILE_VERSION = "1.0.0"
FIXTURE_ROOT = Path(__file__).with_name("fixtures")

CUSTOMER_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
AGENT_USER_ID = UUID("00000000-0000-4000-8000-000000000102")
MANAGER_USER_ID = UUID("00000000-0000-4000-8000-000000000103")
SUPPORT_CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000201")

COMMERCE_CUSTOMER_ID = UUID("10000000-0000-4000-8000-000000000001")
ISOLATION_CUSTOMER_ID = UUID("10000000-0000-4000-8000-000000000002")
CHAIR_PRODUCT_ID = UUID("20000000-0000-4000-8000-000000000001")
PRIMARY_ORDER_ID = UUID("30000000-0000-4000-8000-000000000001")
AMBIGUITY_ORDER_ID = UUID("30000000-0000-4000-8000-000000000002")
ISOLATION_ORDER_ID = UUID("30000000-0000-4000-8000-000000000003")
PRIMARY_ITEM_ID = UUID("31000000-0000-4000-8000-000000000001")
AMBIGUITY_ITEM_ID = UUID("31000000-0000-4000-8000-000000000002")
ISOLATION_ITEM_ID = UUID("31000000-0000-4000-8000-000000000003")
PRIMARY_PAYMENT_ID = UUID("40000000-0000-4000-8000-000000000001")

FIXED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 8, 1, 9, 5, tzinfo=UTC)
DEMO_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$hD6wX2917V10eaCPYy2KNQ$"
    "+9+MlRb4CCt7jBZTI5r6BGsOMw1q6WQGZGyYAWI+9PY"
)


@dataclass(frozen=True)
class SeedSummary:
    profile_id: str
    profile_version: str
    profile_checksum: str
    support_users: int
    support_customers: int
    commerce_customers: int
    products: int
    orders: int
    order_items: int
    payments: int
    policy_documents: int
    golden_cases: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_checksum": self.profile_checksum,
            "support_users": self.support_users,
            "support_customers": self.support_customers,
            "commerce_customers": self.commerce_customers,
            "products": self.products,
            "orders": self.orders,
            "order_items": self.order_items,
            "payments": self.payments,
            "policy_documents": self.policy_documents,
            "golden_cases": self.golden_cases,
        }


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(path for path in FIXTURE_ROOT.rglob("*") if path.is_file()))


def profile_checksum() -> str:
    digest = hashlib.sha256()
    for path in fixture_paths():
        digest.update(path.relative_to(FIXTURE_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def load_json_fixture(name: str) -> dict[str, Any]:
    loaded = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Fixture {name} must contain a JSON object")
    return loaded


async def _seed_support(engine: AsyncEngine) -> None:
    user_rows = (
        {
            "id": CUSTOMER_USER_ID,
            "email": "customer@example.test",
            "role": "CUSTOMER",
        },
        {
            "id": AGENT_USER_ID,
            "email": "agent@example.test",
            "role": "SUPPORT_AGENT",
        },
        {
            "id": MANAGER_USER_ID,
            "email": "manager@example.test",
            "role": "SUPPORT_MANAGER",
        },
    )
    async with engine.begin() as connection:
        for row in user_rows:
            await connection.execute(
                text(
                    """
                    INSERT INTO support.users (
                        id, email, password_hash, role, status, created_at, updated_at
                    ) VALUES (
                        :id, :email, :password_hash,
                        CAST(:role AS support.user_role), 'ACTIVE', :fixed_at, :fixed_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {**row, "password_hash": DEMO_PASSWORD_HASH, "fixed_at": FIXED_AT},
            )
        await connection.execute(
            text(
                """
                INSERT INTO support.customers (
                    id, user_id, commerce_customer_ref, email, phone, verified_at,
                    status, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :commerce_ref, :email, :phone, :verified_at,
                    'ACTIVE', :fixed_at, :fixed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    commerce_customer_ref = EXCLUDED.commerce_customer_ref,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    verified_at = EXCLUDED.verified_at,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": SUPPORT_CUSTOMER_ID,
                "user_id": CUSTOMER_USER_ID,
                "commerce_ref": "commerce-demo-customer-001",
                "email": "customer@example.test",
                "phone": "+84000000001",
                "verified_at": FIXED_AT,
                "fixed_at": FIXED_AT,
            },
        )


async def _seed_commerce(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        for row in (
            {
                "id": COMMERCE_CUSTOMER_ID,
                "external_ref": "commerce-demo-customer-001",
                "email": "customer@example.test",
            },
            {
                "id": ISOLATION_CUSTOMER_ID,
                "external_ref": "commerce-isolation-customer-002",
                "email": "isolation@example.test",
            },
        ):
            await connection.execute(
                text(
                    """
                    INSERT INTO commerce.customers (
                        id, external_ref, email, status, is_synthetic, created_at, updated_at
                    ) VALUES (
                        :id, :external_ref, :email, 'ACTIVE', true, :fixed_at, :fixed_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        external_ref = EXCLUDED.external_ref,
                        email = EXCLUDED.email,
                        status = EXCLUDED.status,
                        is_synthetic = EXCLUDED.is_synthetic,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {**row, "fixed_at": FIXED_AT},
            )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.products (
                    id, sku, name, normalized_name, category, status,
                    is_synthetic, created_at, updated_at
                ) VALUES (
                    :id, 'SYN-CHAIR-ATLAS-001', 'Ghế công thái học Atlas',
                    'ghe cong thai hoc atlas', 'furniture', 'ACTIVE', true,
                    :fixed_at, :fixed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    sku = EXCLUDED.sku,
                    name = EXCLUDED.name,
                    normalized_name = EXCLUDED.normalized_name,
                    category = EXCLUDED.category,
                    status = EXCLUDED.status,
                    is_synthetic = EXCLUDED.is_synthetic,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {"id": CHAIR_PRODUCT_ID, "fixed_at": FIXED_AT},
        )
        order_rows = (
            {
                "id": PRIMARY_ORDER_ID,
                "customer_id": COMMERCE_CUSTOMER_ID,
                "order_number": "SYN-ORD-CHAIR-001",
            },
            {
                "id": AMBIGUITY_ORDER_ID,
                "customer_id": COMMERCE_CUSTOMER_ID,
                "order_number": "SYN-ORD-CHAIR-002",
            },
            {
                "id": ISOLATION_ORDER_ID,
                "customer_id": ISOLATION_CUSTOMER_ID,
                "order_number": "SYN-ORD-CHAIR-ISO-001",
            },
        )
        for row in order_rows:
            await connection.execute(
                text(
                    """
                    INSERT INTO commerce.orders (
                        id, customer_id, order_number, status, payment_status,
                        total_amount, currency, version, is_synthetic, created_at, updated_at
                    ) VALUES (
                        :id, :customer_id, :order_number, 'PENDING_CONFIRMATION', 'PENDING',
                        2490000.00, 'VND', 1, true, :fixed_at, :fixed_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        customer_id = EXCLUDED.customer_id,
                        order_number = EXCLUDED.order_number,
                        status = EXCLUDED.status,
                        payment_status = EXCLUDED.payment_status,
                        total_amount = EXCLUDED.total_amount,
                        currency = EXCLUDED.currency,
                        version = EXCLUDED.version,
                        is_synthetic = EXCLUDED.is_synthetic,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {**row, "fixed_at": FIXED_AT},
            )
        for item_id, order_id in (
            (PRIMARY_ITEM_ID, PRIMARY_ORDER_ID),
            (AMBIGUITY_ITEM_ID, AMBIGUITY_ORDER_ID),
            (ISOLATION_ITEM_ID, ISOLATION_ORDER_ID),
        ):
            await connection.execute(
                text(
                    """
                    INSERT INTO commerce.order_items (
                        id, order_id, product_id, variant, quantity, unit_amount,
                        currency, is_synthetic, created_at, updated_at
                    ) VALUES (
                        :id, :order_id, :product_id, 'synthetic-black', 1, 2490000.00,
                        'VND', true, :fixed_at, :fixed_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        order_id = EXCLUDED.order_id,
                        product_id = EXCLUDED.product_id,
                        variant = EXCLUDED.variant,
                        quantity = EXCLUDED.quantity,
                        unit_amount = EXCLUDED.unit_amount,
                        currency = EXCLUDED.currency,
                        is_synthetic = EXCLUDED.is_synthetic,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "id": item_id,
                    "order_id": order_id,
                    "product_id": CHAIR_PRODUCT_ID,
                    "fixed_at": FIXED_AT,
                },
            )
        await connection.execute(
            text(
                """
                INSERT INTO commerce.payments (
                    id, customer_id, order_id, transaction_ref, status, amount, currency,
                    payment_method, paid_at, version, is_synthetic, created_at, updated_at
                ) VALUES (
                    :id, :customer_id, :order_id, 'SYN-TXN-CHAIR-001', 'SUCCEEDED',
                    2490000.00, 'VND', 'synthetic_wallet', :paid_at, 1, true,
                    :fixed_at, :fixed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    customer_id = EXCLUDED.customer_id,
                    order_id = EXCLUDED.order_id,
                    transaction_ref = EXCLUDED.transaction_ref,
                    status = EXCLUDED.status,
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    payment_method = EXCLUDED.payment_method,
                    paid_at = EXCLUDED.paid_at,
                    version = EXCLUDED.version,
                    is_synthetic = EXCLUDED.is_synthetic,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": PRIMARY_PAYMENT_ID,
                "customer_id": COMMERCE_CUSTOMER_ID,
                "order_id": PRIMARY_ORDER_ID,
                "paid_at": PAID_AT,
                "fixed_at": FIXED_AT,
            },
        )


def _validate_artifacts() -> tuple[int, int]:
    manifest = load_json_fixture("manifest.json")
    dataset = load_json_fixture("golden_cases.json")
    cases = dataset.get("cases")
    if manifest.get("profile_id") != PROFILE_ID or manifest.get("version") != PROFILE_VERSION:
        raise ValueError("Seed manifest identity/version mismatch")
    if dataset.get("dataset_version") != "payment-mismatch-golden-v1":
        raise ValueError("Golden dataset version mismatch")
    if not isinstance(cases, list) or len(cases) != 25:
        raise ValueError("Golden dataset must contain exactly 25 cases")
    calibration = sum(case.get("subset") == "calibration" for case in cases)
    holdout = sum(case.get("subset") == "holdout" for case in cases)
    if (calibration, holdout) != (15, 10):
        raise ValueError("Golden split must contain 15 calibration and 10 holdout cases")
    policy_count = len(tuple((FIXTURE_ROOT / "policies").glob("*.md")))
    if policy_count != 3:
        raise ValueError("Seed profile must contain active, expired and conflict policies")
    return policy_count, len(cases)


async def seed_profile(*, support_database_url: str, commerce_database_url: str) -> SeedSummary:
    policy_count, golden_count = _validate_artifacts()
    support_engine = create_async_engine(support_database_url, pool_pre_ping=True)
    commerce_engine = create_async_engine(commerce_database_url, pool_pre_ping=True)
    try:
        await _seed_support(support_engine)
        await _seed_commerce(commerce_engine)
    finally:
        await support_engine.dispose()
        await commerce_engine.dispose()
    return SeedSummary(
        profile_id=PROFILE_ID,
        profile_version=PROFILE_VERSION,
        profile_checksum=profile_checksum(),
        support_users=3,
        support_customers=1,
        commerce_customers=2,
        products=1,
        orders=3,
        order_items=3,
        payments=1,
        policy_documents=policy_count,
        golden_cases=golden_count,
    )


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Seed the {PROFILE_ID} synthetic profile")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = asyncio.run(
        seed_profile(
            support_database_url=_required_environment("SUPPORT_DATABASE_URL"),
            commerce_database_url=_required_environment("COMMERCE_DATABASE_URL"),
        )
    )
    rendered = json.dumps(summary.as_dict(), sort_keys=True)
    print(rendered if args.json else f"Seeded {PROFILE_ID}: {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
