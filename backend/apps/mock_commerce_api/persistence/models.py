from __future__ import annotations

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import UserDefinedType

SCHEMA = "commerce"
metadata = MetaData(schema=SCHEMA)


class PublicCitext(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        del kw
        return "public.citext"


customer_status = Enum(
    "ACTIVE", "DISABLED", name="customer_status", schema=SCHEMA, native_enum=True
)
product_status = Enum("ACTIVE", "INACTIVE", name="product_status", schema=SCHEMA, native_enum=True)
order_status = Enum(
    "PENDING_CONFIRMATION", "CONFIRMED", name="order_status", schema=SCHEMA, native_enum=True
)
order_payment_status = Enum(
    "PENDING", "PAID", name="order_payment_status", schema=SCHEMA, native_enum=True
)
payment_status = Enum(
    "PENDING",
    "SUCCEEDED",
    "FAILED",
    "REVERSED",
    name="payment_status",
    schema=SCHEMA,
    native_enum=True,
)
write_result = Enum(
    "SUCCEEDED", "DENIED", "FAILED", name="write_result", schema=SCHEMA, native_enum=True
)

customers = Table(
    "customers",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("external_ref", String(128), nullable=False),
    Column("email", PublicCitext(), nullable=False),
    Column("status", customer_status, nullable=False, server_default=text("'ACTIVE'")),
    Column("is_synthetic", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("external_ref", name="uq_commerce_customers_external_ref"),
    UniqueConstraint("email", name="uq_commerce_customers_email"),
    CheckConstraint("is_synthetic", name="ck_commerce_customers_is_synthetic"),
)
Index("ix_commerce_customers_status_created_at", customers.c.status, customers.c.created_at.desc())

products = Table(
    "products",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("sku", String(64), nullable=False),
    Column("name", String(255), nullable=False),
    Column("normalized_name", Text(), nullable=False),
    Column("category", String(64), nullable=False),
    Column("status", product_status, nullable=False, server_default=text("'ACTIVE'")),
    Column("is_synthetic", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("sku", name="uq_commerce_products_sku"),
    CheckConstraint("is_synthetic", name="ck_commerce_products_is_synthetic"),
)
Index("ix_commerce_products_category_status", products.c.category, products.c.status)
Index(
    "ix_commerce_products_normalized_name_trgm",
    products.c.normalized_name,
    postgresql_using="gin",
    postgresql_ops={"normalized_name": "public.gin_trgm_ops"},
)

orders = Table(
    "orders",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "customer_id",
        UUID(as_uuid=True),
        ForeignKey("commerce.customers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("order_number", String(64), nullable=False),
    Column("status", order_status, nullable=False, server_default=text("'PENDING_CONFIRMATION'")),
    Column(
        "payment_status",
        order_payment_status,
        nullable=False,
        server_default=text("'PENDING'"),
    ),
    Column("total_amount", Numeric(18, 2), nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("version", Integer(), nullable=False, server_default=text("1")),
    Column("is_synthetic", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("order_number", name="uq_commerce_orders_order_number"),
    UniqueConstraint("id", "customer_id", name="uq_commerce_orders_id_customer_id"),
    CheckConstraint("total_amount >= 0", name="ck_commerce_orders_total_amount"),
    CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_commerce_orders_currency"),
    CheckConstraint("version >= 1", name="ck_commerce_orders_version"),
    CheckConstraint("is_synthetic", name="ck_commerce_orders_is_synthetic"),
)
Index("ix_commerce_orders_customer_created_at", orders.c.customer_id, orders.c.created_at.desc())
Index(
    "ix_commerce_orders_customer_status_created_at",
    orders.c.customer_id,
    orders.c.status,
    orders.c.created_at.desc(),
)
Index(
    "ix_commerce_orders_customer_payment_created_at",
    orders.c.customer_id,
    orders.c.payment_status,
    orders.c.created_at.desc(),
)

order_items = Table(
    "order_items",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "order_id",
        UUID(as_uuid=True),
        ForeignKey("commerce.orders.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "product_id",
        UUID(as_uuid=True),
        ForeignKey("commerce.products.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("variant", String(128), nullable=True),
    Column("quantity", Integer(), nullable=False),
    Column("unit_amount", Numeric(18, 2), nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("is_synthetic", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("quantity > 0", name="ck_commerce_order_items_quantity"),
    CheckConstraint("unit_amount >= 0", name="ck_commerce_order_items_unit_amount"),
    CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_commerce_order_items_currency"),
    CheckConstraint("is_synthetic", name="ck_commerce_order_items_is_synthetic"),
)
Index("ix_commerce_order_items_order_id_id", order_items.c.order_id, order_items.c.id)
Index("ix_commerce_order_items_product_id", order_items.c.product_id)

payments = Table(
    "payments",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "customer_id",
        UUID(as_uuid=True),
        ForeignKey("commerce.customers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("order_id", UUID(as_uuid=True), nullable=True),
    Column("transaction_ref", String(128), nullable=True),
    Column("status", payment_status, nullable=False),
    Column("amount", Numeric(18, 2), nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("payment_method", String(32), nullable=False),
    Column("paid_at", DateTime(timezone=True), nullable=True),
    Column("version", Integer(), nullable=False, server_default=text("1")),
    Column("is_synthetic", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(
        ["order_id", "customer_id"],
        ["commerce.orders.id", "commerce.orders.customer_id"],
        name="fk_commerce_payments_order_customer",
        ondelete="RESTRICT",
    ),
    CheckConstraint("amount > 0", name="ck_commerce_payments_amount"),
    CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_commerce_payments_currency"),
    CheckConstraint("version >= 1", name="ck_commerce_payments_version"),
    CheckConstraint("is_synthetic", name="ck_commerce_payments_is_synthetic"),
    CheckConstraint(
        "status <> 'SUCCEEDED' OR paid_at IS NOT NULL",
        name="ck_commerce_payments_succeeded_paid_at",
    ),
)
Index(
    "uq_commerce_payments_transaction_ref",
    payments.c.transaction_ref,
    unique=True,
    postgresql_where=payments.c.transaction_ref.is_not(None),
)
Index("ix_commerce_payments_customer_paid_at", payments.c.customer_id, payments.c.paid_at.desc())
Index(
    "ix_commerce_payments_customer_status_amount_currency_paid",
    payments.c.customer_id,
    payments.c.status,
    payments.c.amount,
    payments.c.currency,
    payments.c.paid_at.desc(),
)
Index(
    "ix_commerce_payments_order_id",
    payments.c.order_id,
    postgresql_where=payments.c.order_id.is_not(None),
)

idempotency_records = Table(
    "idempotency_records",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("operation", String(64), nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_hash", CHAR(64), nullable=False),
    Column(
        "order_id",
        UUID(as_uuid=True),
        ForeignKey("commerce.orders.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("response_status", SmallInteger(), nullable=False),
    Column("response_body", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("operation", "idempotency_key", name="uq_commerce_idempotency_operation_key"),
    CheckConstraint("operation = 'SYNC_PAYMENT_STATUS'", name="ck_commerce_idempotency_operation"),
    CheckConstraint(
        "response_status BETWEEN 100 AND 599",
        name="ck_commerce_idempotency_response_status",
    ),
)
Index(
    "ix_commerce_idempotency_order_created_at",
    idempotency_records.c.order_id,
    idempotency_records.c.created_at.desc(),
)

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("correlation_id", UUID(as_uuid=True), nullable=False),
    Column("action", String(64), nullable=False),
    Column("order_id", UUID(as_uuid=True), nullable=False),
    Column("result", write_result, nullable=False),
    Column("before_hash", String(71), nullable=True),
    Column("after_hash", String(71), nullable=True),
    Column("details", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("action = 'SYNC_PAYMENT_STATUS'", name="ck_commerce_audit_action"),
)
Index("ix_commerce_audit_correlation_id", audit_logs.c.correlation_id)
Index("ix_commerce_audit_order_created_at", audit_logs.c.order_id, audit_logs.c.created_at.desc())
Index(
    "ix_commerce_audit_action_result_created_at",
    audit_logs.c.action,
    audit_logs.c.result,
    audit_logs.c.created_at.desc(),
)

COMMERCE_TABLES = frozenset(metadata.tables)
