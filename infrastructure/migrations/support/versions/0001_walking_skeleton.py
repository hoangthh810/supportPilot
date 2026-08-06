"""Create the minimal final-named Walking Skeleton support schema.

Revision ID: 0001_walking_skeleton
Revises:
Create Date: 2026-08-06
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from pwdlib import PasswordHash
from sqlalchemy.dialects import postgresql

revision: str = "0001_walking_skeleton"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ROLE = postgresql.ENUM(
    "CUSTOMER",
    "SUPPORT_AGENT",
    "SUPPORT_MANAGER",
    "ADMIN",
    name="user_role",
    schema="support",
    create_type=False,
)
ACCOUNT_STATUS = postgresql.ENUM(
    "ACTIVE",
    "DISABLED",
    name="account_status",
    schema="support",
    create_type=False,
)
TICKET_SOURCE = postgresql.ENUM(
    "WEB",
    "API",
    name="ticket_source",
    schema="support",
    create_type=False,
)
TICKET_PRIORITY = postgresql.ENUM(
    "LOW",
    "NORMAL",
    "HIGH",
    name="ticket_priority",
    schema="support",
    create_type=False,
)
TICKET_STATUS = postgresql.ENUM(
    "OPEN",
    "PROCESSING",
    "WAITING_CUSTOMER",
    "WAITING_APPROVAL",
    "ESCALATED",
    "RESOLVED",
    "CLOSED",
    name="ticket_status",
    schema="support",
    create_type=False,
)
MESSAGE_SENDER_TYPE = postgresql.ENUM(
    "CUSTOMER",
    "STAFF",
    "SYSTEM",
    name="message_sender_type",
    schema="support",
    create_type=False,
)

DEMO_CUSTOMER_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
DEMO_AGENT_USER_ID = UUID("00000000-0000-4000-8000-000000000102")
DEMO_CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000201")


class PublicCitext(sa.types.UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        del kw
        return "public.citext"


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        USER_ROLE,
        ACCOUNT_STATUS,
        TICKET_SOURCE,
        TICKET_PRIORITY,
        TICKET_STATUS,
        MESSAGE_SENDER_TYPE,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", PublicCitext(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column(
            "status",
            ACCOUNT_STATUS,
            nullable=False,
            server_default=sa.text("'ACTIVE'::support.account_status"),
        ),
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
        sa.UniqueConstraint("email", name="uq_users_email"),
        schema="support",
    )
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commerce_customer_ref", sa.String(128), nullable=False),
        sa.Column("email", PublicCitext(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            ACCOUNT_STATUS,
            nullable=False,
            server_default=sa.text("'ACTIVE'::support.account_status"),
        ),
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
            ["user_id"],
            ["support.users.id"],
            name="fk_customers_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("user_id", name="uq_customers_user_id"),
        sa.UniqueConstraint(
            "commerce_customer_ref",
            name="uq_customers_commerce_customer_ref",
        ),
        schema="support",
    )
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_number", sa.String(32), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", TICKET_SOURCE, nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column(
            "priority",
            TICKET_PRIORITY,
            nullable=False,
            server_default=sa.text("'NORMAL'::support.ticket_priority"),
        ),
        sa.Column(
            "status",
            TICKET_STATUS,
            nullable=False,
            server_default=sa.text("'OPEN'::support.ticket_status"),
        ),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("lock_version >= 1", name="ck_support_tickets_lock_version"),
        sa.CheckConstraint(
            "resolved_at IS NULL OR status IN ('RESOLVED', 'CLOSED')",
            name="ck_support_tickets_resolved_at_status",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["support.customers.id"],
            name="fk_support_tickets_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("ticket_number", name="uq_support_tickets_ticket_number"),
        schema="support",
    )
    op.create_index(
        "ix_support_tickets_customer_created_at",
        "support_tickets",
        ["customer_id", sa.text("created_at DESC")],
        schema="support",
    )
    op.create_index(
        "ix_support_tickets_status_updated_at",
        "support_tickets",
        ["status", sa.text("updated_at DESC")],
        schema="support",
    )
    op.create_table(
        "ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_type", MESSAGE_SENDER_TYPE, nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support.support_tickets.id"],
            name="fk_ticket_messages_ticket_id_support_tickets",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sender_user_id"],
            ["support.users.id"],
            name="fk_ticket_messages_sender_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ticket_id",
            "idempotency_key",
            name="uq_ticket_messages_ticket_id_idempotency_key",
        ),
        schema="support",
    )
    op.create_index(
        "ix_ticket_messages_ticket_created_id",
        "ticket_messages",
        ["ticket_id", "created_at", "id"],
        schema="support",
    )

    now = datetime.now(UTC)
    password_hash = PasswordHash.recommended().hash("demo-password")
    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.Text()),
        sa.column("password_hash", sa.Text()),
        sa.column("role", USER_ROLE),
        sa.column("status", ACCOUNT_STATUS),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        schema="support",
    )
    op.bulk_insert(
        users,
        [
            {
                "id": DEMO_CUSTOMER_USER_ID,
                "email": "customer@example.test",
                "password_hash": password_hash,
                "role": "CUSTOMER",
                "status": "ACTIVE",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": DEMO_AGENT_USER_ID,
                "email": "agent@example.test",
                "password_hash": password_hash,
                "role": "SUPPORT_AGENT",
                "status": "ACTIVE",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    customers = sa.table(
        "customers",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("commerce_customer_ref", sa.String(128)),
        sa.column("email", sa.Text()),
        sa.column("verified_at", sa.DateTime(timezone=True)),
        sa.column("status", ACCOUNT_STATUS),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        schema="support",
    )
    op.bulk_insert(
        customers,
        [
            {
                "id": DEMO_CUSTOMER_ID,
                "user_id": DEMO_CUSTOMER_USER_ID,
                "commerce_customer_ref": "commerce-demo-customer-001",
                "email": "customer@example.test",
                "verified_at": now,
                "status": "ACTIVE",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_messages_ticket_created_id",
        table_name="ticket_messages",
        schema="support",
    )
    op.drop_table("ticket_messages", schema="support")
    op.drop_index(
        "ix_support_tickets_status_updated_at",
        table_name="support_tickets",
        schema="support",
    )
    op.drop_index(
        "ix_support_tickets_customer_created_at",
        table_name="support_tickets",
        schema="support",
    )
    op.drop_table("support_tickets", schema="support")
    op.drop_table("customers", schema="support")
    op.drop_table("users", schema="support")

    bind = op.get_bind()
    for enum_type in (
        MESSAGE_SENDER_TYPE,
        TICKET_STATUS,
        TICKET_PRIORITY,
        TICKET_SOURCE,
        ACCOUNT_STATUS,
        USER_ROLE,
    ):
        enum_type.drop(bind, checkfirst=True)
