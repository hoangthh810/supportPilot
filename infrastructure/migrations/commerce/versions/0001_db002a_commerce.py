"""Create the exact UC-01 Mock-Commerce persistence contract.

Revision ID: 0001_db002a_commerce
Revises:
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_db002a_commerce"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CUSTOMER_STATUS = postgresql.ENUM(
    "ACTIVE", "DISABLED", name="customer_status", schema="commerce", create_type=False
)
PRODUCT_STATUS = postgresql.ENUM(
    "ACTIVE", "INACTIVE", name="product_status", schema="commerce", create_type=False
)
ORDER_STATUS = postgresql.ENUM(
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    name="order_status",
    schema="commerce",
    create_type=False,
)
ORDER_PAYMENT_STATUS = postgresql.ENUM(
    "PENDING", "PAID", name="order_payment_status", schema="commerce", create_type=False
)
PAYMENT_STATUS = postgresql.ENUM(
    "PENDING",
    "SUCCEEDED",
    "FAILED",
    "REVERSED",
    name="payment_status",
    schema="commerce",
    create_type=False,
)
WRITE_RESULT = postgresql.ENUM(
    "SUCCEEDED",
    "DENIED",
    "FAILED",
    name="write_result",
    schema="commerce",
    create_type=False,
)

ENUMS = (
    CUSTOMER_STATUS,
    PRODUCT_STATUS,
    ORDER_STATUS,
    ORDER_PAYMENT_STATUS,
    PAYMENT_STATUS,
    WRITE_RESULT,
)


class PublicCitext(sa.types.UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        del kw
        return "public.citext"


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "customers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("external_ref", sa.String(128), nullable=False),
        sa.Column("email", PublicCitext(), nullable=False),
        sa.Column(
            "status",
            CUSTOMER_STATUS,
            nullable=False,
            server_default=sa.text("'ACTIVE'::commerce.customer_status"),
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("external_ref", name="uq_commerce_customers_external_ref"),
        sa.UniqueConstraint("email", name="uq_commerce_customers_email"),
        sa.CheckConstraint("is_synthetic", name="ck_commerce_customers_is_synthetic"),
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_customers_status_created_at",
        "customers",
        ["status", sa.text("created_at DESC")],
        schema="commerce",
    )

    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column(
            "status",
            PRODUCT_STATUS,
            nullable=False,
            server_default=sa.text("'ACTIVE'::commerce.product_status"),
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("sku", name="uq_commerce_products_sku"),
        sa.CheckConstraint("is_synthetic", name="ck_commerce_products_is_synthetic"),
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_products_category_status",
        "products",
        ["category", "status"],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_products_normalized_name_trgm",
        "products",
        ["normalized_name"],
        schema="commerce",
        postgresql_using="gin",
        postgresql_ops={"normalized_name": "public.gin_trgm_ops"},
    )

    op.create_table(
        "orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column(
            "status",
            ORDER_STATUS,
            nullable=False,
            server_default=sa.text("'PENDING_CONFIRMATION'::commerce.order_status"),
        ),
        sa.Column(
            "payment_status",
            ORDER_PAYMENT_STATUS,
            nullable=False,
            server_default=sa.text("'PENDING'::commerce.order_payment_status"),
        ),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["commerce.customers.id"],
            name="fk_commerce_orders_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("order_number", name="uq_commerce_orders_order_number"),
        sa.UniqueConstraint("id", "customer_id", name="uq_commerce_orders_id_customer_id"),
        sa.CheckConstraint("total_amount >= 0", name="ck_commerce_orders_total_amount"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_commerce_orders_currency"),
        sa.CheckConstraint("version >= 1", name="ck_commerce_orders_version"),
        sa.CheckConstraint("is_synthetic", name="ck_commerce_orders_is_synthetic"),
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_orders_customer_created_at",
        "orders",
        ["customer_id", sa.text("created_at DESC")],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_orders_customer_status_created_at",
        "orders",
        ["customer_id", "status", sa.text("created_at DESC")],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_orders_customer_payment_created_at",
        "orders",
        ["customer_id", "payment_status", sa.text("created_at DESC")],
        schema="commerce",
    )

    op.create_table(
        "order_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant", sa.String(128), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commerce.orders.id"],
            name="fk_commerce_order_items_order_id_orders",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["commerce.products.id"],
            name="fk_commerce_order_items_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_commerce_order_items_quantity"),
        sa.CheckConstraint("unit_amount >= 0", name="ck_commerce_order_items_unit_amount"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_commerce_order_items_currency"),
        sa.CheckConstraint("is_synthetic", name="ck_commerce_order_items_is_synthetic"),
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_order_items_order_id_id",
        "order_items",
        ["order_id", "id"],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_order_items_product_id",
        "order_items",
        ["product_id"],
        schema="commerce",
    )

    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_ref", sa.String(128), nullable=True),
        sa.Column("status", PAYMENT_STATUS, nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["commerce.customers.id"],
            name="fk_commerce_payments_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id", "customer_id"],
            ["commerce.orders.id", "commerce.orders.customer_id"],
            name="fk_commerce_payments_order_customer",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount > 0", name="ck_commerce_payments_amount"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_commerce_payments_currency"),
        sa.CheckConstraint("version >= 1", name="ck_commerce_payments_version"),
        sa.CheckConstraint("is_synthetic", name="ck_commerce_payments_is_synthetic"),
        sa.CheckConstraint(
            "status <> 'SUCCEEDED' OR paid_at IS NOT NULL",
            name="ck_commerce_payments_succeeded_paid_at",
        ),
        schema="commerce",
    )
    op.create_index(
        "uq_commerce_payments_transaction_ref",
        "payments",
        ["transaction_ref"],
        unique=True,
        schema="commerce",
        postgresql_where=sa.text("transaction_ref IS NOT NULL"),
    )
    op.create_index(
        "ix_commerce_payments_customer_paid_at",
        "payments",
        ["customer_id", sa.text("paid_at DESC")],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_payments_customer_status_amount_currency_paid",
        "payments",
        ["customer_id", "status", "amount", "currency", sa.text("paid_at DESC")],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_payments_order_id",
        "payments",
        ["order_id"],
        schema="commerce",
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )

    op.create_table(
        "idempotency_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.CHAR(64), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_status", sa.SmallInteger(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commerce.orders.id"],
            name="fk_commerce_idempotency_order_id_orders",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "operation",
            "idempotency_key",
            name="uq_commerce_idempotency_operation_key",
        ),
        sa.CheckConstraint(
            "operation = 'SYNC_PAYMENT_STATUS'",
            name="ck_commerce_idempotency_operation",
        ),
        sa.CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="ck_commerce_idempotency_response_status",
        ),
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_idempotency_order_created_at",
        "idempotency_records",
        ["order_id", sa.text("created_at DESC")],
        schema="commerce",
    )

    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result", WRITE_RESULT, nullable=False),
        sa.Column("before_hash", sa.String(71), nullable=True),
        sa.Column("after_hash", sa.String(71), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("action = 'SYNC_PAYMENT_STATUS'", name="ck_commerce_audit_action"),
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_audit_correlation_id",
        "audit_logs",
        ["correlation_id"],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_audit_order_created_at",
        "audit_logs",
        ["order_id", sa.text("created_at DESC")],
        schema="commerce",
    )
    op.create_index(
        "ix_commerce_audit_action_result_created_at",
        "audit_logs",
        ["action", "result", sa.text("created_at DESC")],
        schema="commerce",
    )

    op.execute(
        "REVOKE UPDATE, DELETE ON TABLE "
        "commerce.idempotency_records, commerce.audit_logs FROM commerce_app"
    )
    op.execute(
        "GRANT SELECT, INSERT ON TABLE "
        "commerce.idempotency_records, commerce.audit_logs TO commerce_app"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commerce_audit_action_result_created_at",
        table_name="audit_logs",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_audit_order_created_at",
        table_name="audit_logs",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_audit_correlation_id",
        table_name="audit_logs",
        schema="commerce",
    )
    op.drop_table("audit_logs", schema="commerce")
    op.drop_index(
        "ix_commerce_idempotency_order_created_at",
        table_name="idempotency_records",
        schema="commerce",
    )
    op.drop_table("idempotency_records", schema="commerce")
    op.drop_index("ix_commerce_payments_order_id", table_name="payments", schema="commerce")
    op.drop_index(
        "ix_commerce_payments_customer_status_amount_currency_paid",
        table_name="payments",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_payments_customer_paid_at",
        table_name="payments",
        schema="commerce",
    )
    op.drop_index(
        "uq_commerce_payments_transaction_ref",
        table_name="payments",
        schema="commerce",
    )
    op.drop_table("payments", schema="commerce")
    op.drop_index(
        "ix_commerce_order_items_product_id",
        table_name="order_items",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_order_items_order_id_id",
        table_name="order_items",
        schema="commerce",
    )
    op.drop_table("order_items", schema="commerce")
    op.drop_index(
        "ix_commerce_orders_customer_payment_created_at",
        table_name="orders",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_orders_customer_status_created_at",
        table_name="orders",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_orders_customer_created_at",
        table_name="orders",
        schema="commerce",
    )
    op.drop_table("orders", schema="commerce")
    op.drop_index(
        "ix_commerce_products_normalized_name_trgm",
        table_name="products",
        schema="commerce",
    )
    op.drop_index(
        "ix_commerce_products_category_status",
        table_name="products",
        schema="commerce",
    )
    op.drop_table("products", schema="commerce")
    op.drop_index(
        "ix_commerce_customers_status_created_at",
        table_name="customers",
        schema="commerce",
    )
    op.drop_table("customers", schema="commerce")

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=True)
