from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import CHAR, Boolean, DateTime, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID

from backend.apps.mock_commerce_api.persistence import models

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infrastructure/migrations/commerce/versions/0001_db002a_commerce.py"
)

EXPECTED_COLUMNS = {
    "customers": {
        "id",
        "external_ref",
        "email",
        "status",
        "is_synthetic",
        "created_at",
        "updated_at",
    },
    "products": {
        "id",
        "sku",
        "name",
        "normalized_name",
        "category",
        "status",
        "is_synthetic",
        "created_at",
        "updated_at",
    },
    "orders": {
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
    },
    "order_items": {
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
    },
    "payments": {
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
    },
    "idempotency_records": {
        "id",
        "operation",
        "idempotency_key",
        "request_hash",
        "order_id",
        "response_status",
        "response_body",
        "created_at",
    },
    "audit_logs": {
        "id",
        "correlation_id",
        "action",
        "order_id",
        "result",
        "before_hash",
        "after_hash",
        "details",
        "created_at",
    },
}

EXPECTED_ENUMS = {
    "customer_status": ("ACTIVE", "DISABLED"),
    "product_status": ("ACTIVE", "INACTIVE"),
    "order_status": ("PENDING_CONFIRMATION", "CONFIRMED"),
    "order_payment_status": ("PENDING", "PAID"),
    "payment_status": ("PENDING", "SUCCEEDED", "FAILED", "REVERSED"),
    "write_result": ("SUCCEEDED", "DENIED", "FAILED"),
}


def migration_function(name: str) -> ast.FunctionDef:
    module = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    return next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def created_table_names(function: ast.FunctionDef) -> list[str]:
    names: list[str] = []
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
            and node.func.attr == "create_table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.append(node.args[0].value)
    return names


def test_db002a_is_the_first_commerce_revision_with_exact_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0001_db002a_commerce"' in source
    assert "down_revision: str | Sequence[str] | None = None" in source
    assert created_table_names(migration_function("upgrade")) == list(EXPECTED_COLUMNS)
    assert set(models.metadata.tables) == {
        f"commerce.{table_name}" for table_name in EXPECTED_COLUMNS
    }


def test_db002a_models_have_exact_columns_and_synthetic_timestamps() -> None:
    for table_name, expected in EXPECTED_COLUMNS.items():
        table = models.metadata.tables[f"commerce.{table_name}"]
        assert set(table.c.keys()) == expected
        assert isinstance(table.c.id.type, UUID)
        assert table.c.id.server_default is not None
        assert isinstance(table.c.created_at.type, DateTime)
        assert table.c.created_at.type.timezone is True

    for table_name in ("customers", "products", "orders", "order_items", "payments"):
        column = models.metadata.tables[f"commerce.{table_name}"].c.is_synthetic
        assert isinstance(column.type, Boolean)
        assert column.nullable is False


def test_db002a_named_enums_match_the_contract() -> None:
    enum_types = (
        models.customer_status,
        models.product_status,
        models.order_status,
        models.order_payment_status,
        models.payment_status,
        models.write_result,
    )

    assert {enum.name: tuple(enum.enums) for enum in enum_types} == EXPECTED_ENUMS
    assert all(enum.schema == "commerce" for enum in enum_types)


def test_db002a_money_currency_and_version_types_are_exact() -> None:
    orders = models.orders.c
    order_items = models.order_items.c
    payments = models.payments.c

    for amount in (orders.total_amount, order_items.unit_amount, payments.amount):
        assert isinstance(amount.type, Numeric)
        assert (amount.type.precision, amount.type.scale) == (18, 2)
    for currency in (orders.currency, order_items.currency, payments.currency):
        assert isinstance(currency.type, CHAR)
        assert currency.type.length == 3
    for version in (orders.version, payments.version):
        assert isinstance(version.type, Integer)
        assert version.nullable is False
        assert version.server_default is not None


def test_db002a_foreign_keys_are_commerce_only_and_restrict() -> None:
    foreign_keys = [
        foreign_key
        for table in models.metadata.tables.values()
        for foreign_key in table.foreign_key_constraints
    ]

    assert len(foreign_keys) == 6
    assert all(foreign_key.ondelete == "RESTRICT" for foreign_key in foreign_keys)
    assert all(
        element.target_fullname.startswith("commerce.")
        for foreign_key in foreign_keys
        for element in foreign_key.elements
    )
    assert len(models.audit_logs.foreign_key_constraints) == 0


def test_db002a_has_required_indexes_and_partial_uniqueness() -> None:
    index_names = {
        index.name for table in models.metadata.tables.values() for index in table.indexes
    }
    required = {
        "ix_commerce_customers_status_created_at",
        "ix_commerce_products_category_status",
        "ix_commerce_products_normalized_name_trgm",
        "ix_commerce_orders_customer_created_at",
        "ix_commerce_orders_customer_status_created_at",
        "ix_commerce_orders_customer_payment_created_at",
        "ix_commerce_order_items_order_id_id",
        "ix_commerce_order_items_product_id",
        "uq_commerce_payments_transaction_ref",
        "ix_commerce_payments_customer_paid_at",
        "ix_commerce_payments_customer_status_amount_currency_paid",
        "ix_commerce_payments_order_id",
        "ix_commerce_idempotency_order_created_at",
        "ix_commerce_audit_correlation_id",
        "ix_commerce_audit_order_created_at",
        "ix_commerce_audit_action_result_created_at",
    }

    assert index_names == required
    transaction_index = next(
        index
        for index in models.payments.indexes
        if index.name == "uq_commerce_payments_transaction_ref"
    )
    assert transaction_index.unique is True
    assert transaction_index.dialect_options["postgresql"]["where"] is not None


def test_db002a_migration_enforces_append_only_grants_and_no_extra_uc_scope() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    lowered = source.lower()

    for table in models.metadata.tables.values():
        for constraint in table.constraints:
            if constraint.name is not None:
                assert str(constraint.name) in source
        for index in table.indexes:
            assert index.name is not None
            assert index.name in source

    assert "revoke update, delete" in lowered
    assert "commerce.idempotency_records, commerce.audit_logs" in lowered
    assert "from commerce_app" in lowered
    assert "support." not in lowered
    for forbidden in ("shipping", "refund", "warranty", "claim", "address"):
        assert forbidden not in lowered
