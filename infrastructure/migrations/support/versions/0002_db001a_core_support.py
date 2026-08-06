"""Complete the DB-001A support identity and Ticket schema in place.

Revision ID: 0002_db001a_core_support
Revises: 0001_walking_skeleton
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_db001a_core_support"
down_revision: str | Sequence[str] | None = "0001_walking_skeleton"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Forward-upgrade the Walking Skeleton tables without replacing them."""
    for table_name in ("users", "customers", "support_tickets", "ticket_messages"):
        op.alter_column(
            table_name,
            "id",
            schema="support",
            server_default=sa.text("gen_random_uuid()"),
        )

    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        schema="support",
    )
    op.add_column(
        "customers",
        sa.Column("phone", sa.String(length=32), nullable=True),
        schema="support",
    )
    op.add_column(
        "support_tickets",
        sa.Column("assigned_user_id", sa.UUID(), nullable=True),
        schema="support",
    )
    op.add_column(
        "support_tickets",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        schema="support",
    )
    op.create_foreign_key(
        "fk_support_tickets_assigned_user_id_users",
        "support_tickets",
        "users",
        ["assigned_user_id"],
        ["id"],
        source_schema="support",
        referent_schema="support",
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_support_tickets_intent_v0_1",
        "support_tickets",
        "intent IS NULL OR intent = 'payment_mismatch'",
        schema="support",
    )
    op.create_check_constraint(
        "ck_support_tickets_closed_at_status",
        "support_tickets",
        "closed_at IS NULL OR status = 'CLOSED'",
        schema="support",
    )


def downgrade() -> None:
    """Return to the minimal skeleton shape without replacing its tables."""
    op.drop_constraint(
        "ck_support_tickets_closed_at_status",
        "support_tickets",
        schema="support",
        type_="check",
    )
    op.drop_constraint(
        "ck_support_tickets_intent_v0_1",
        "support_tickets",
        schema="support",
        type_="check",
    )
    op.drop_constraint(
        "fk_support_tickets_assigned_user_id_users",
        "support_tickets",
        schema="support",
        type_="foreignkey",
    )
    op.drop_column("support_tickets", "closed_at", schema="support")
    op.drop_column("support_tickets", "assigned_user_id", schema="support")
    op.drop_column("customers", "phone", schema="support")
    op.drop_column("users", "last_login_at", schema="support")

    for table_name in ("ticket_messages", "support_tickets", "customers", "users"):
        op.alter_column(
            table_name,
            "id",
            schema="support",
            server_default=None,
        )
