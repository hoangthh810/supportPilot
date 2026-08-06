from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.walking_skeleton.contracts import (
    Actor,
    TicketRecord,
    UserRecord,
)


class PostgresTicketRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def find_user_by_email(self, email: str) -> UserRecord | None:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT id, email::text, password_hash, role::text, status::text
                        FROM support.users
                        WHERE email = :email
                        """
                    ),
                    {"email": email},
                )
            ).mappings().one_or_none()
        if row is None:
            return None
        return UserRecord(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=row["role"],
            status=row["status"],
        )

    async def create_ticket(
        self,
        *,
        actor_id: UUID,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> TicketRecord:
        async with self._engine.begin() as connection:
            lock_key = f"ticket-create:{actor_id}:{idempotency_key}"
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": lock_key},
            )
            existing = (
                await connection.execute(
                    text(
                        """
                        SELECT ticket.id, ticket.ticket_number,
                               customer.user_id AS customer_user_id,
                               ticket.subject, ticket.status::text
                        FROM support.ticket_messages AS message
                        JOIN support.support_tickets AS ticket ON ticket.id = message.ticket_id
                        JOIN support.customers AS customer ON customer.id = ticket.customer_id
                        WHERE message.sender_user_id = :actor_id
                          AND message.idempotency_key = :idempotency_key
                        LIMIT 1
                        """
                    ),
                    {"actor_id": actor_id, "idempotency_key": idempotency_key},
                )
            ).mappings().one_or_none()
            if existing is not None:
                return self._ticket(existing)

            customer_id = (
                await connection.execute(
                    text(
                        """
                        SELECT id
                        FROM support.customers
                        WHERE user_id = :actor_id AND status = 'ACTIVE'
                        """
                    ),
                    {"actor_id": actor_id},
                )
            ).scalar_one_or_none()
            if customer_id is None:
                raise ApiError(
                    status_code=403,
                    code="CUSTOMER_SCOPE_FORBIDDEN",
                    message="The authenticated actor has no active customer profile.",
                )

            ticket_id = uuid4()
            ticket_number = f"SP-{ticket_id.hex[:8].upper()}"
            await connection.execute(
                text(
                    """
                    INSERT INTO support.support_tickets
                        (id, ticket_number, customer_id, source, subject, intent,
                         priority, status, lock_version)
                    VALUES
                        (:id, :ticket_number, :customer_id,
                         CAST(:source AS support.ticket_source), :subject,
                         'payment_mismatch', 'NORMAL', 'OPEN', 1)
                    """
                ),
                {
                    "id": ticket_id,
                    "ticket_number": ticket_number,
                    "customer_id": customer_id,
                    "source": source,
                    "subject": subject,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO support.ticket_messages
                        (id, ticket_id, sender_type, sender_user_id, content, idempotency_key)
                    VALUES
                        (:id, :ticket_id, 'CUSTOMER', :actor_id, :content, :idempotency_key)
                    """
                ),
                {
                    "id": uuid4(),
                    "ticket_id": ticket_id,
                    "actor_id": actor_id,
                    "content": body,
                    "idempotency_key": idempotency_key,
                },
            )
            return TicketRecord(
                id=ticket_id,
                ticket_number=ticket_number,
                customer_user_id=actor_id,
                subject=subject,
                status="OPEN",
            )

    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: Actor
    ) -> TicketRecord | None:
        scope_clause = "" if actor.role != "customer" else "AND customer.user_id = :actor_id"
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        f"""
                        SELECT ticket.id, ticket.ticket_number,
                               customer.user_id AS customer_user_id,
                               ticket.subject, ticket.status::text
                        FROM support.support_tickets AS ticket
                        JOIN support.customers AS customer ON customer.id = ticket.customer_id
                        WHERE ticket.id = :ticket_id {scope_clause}
                        """
                    ),
                    {"ticket_id": ticket_id, "actor_id": actor.id},
                )
            ).mappings().one_or_none()
        return None if row is None else self._ticket(row)

    async def set_ticket_status(self, *, ticket_id: UUID, status: str) -> None:
        resolved_at = "now()" if status == "RESOLVED" else "NULL"
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    f"""
                    UPDATE support.support_tickets
                    SET status = CAST(:status AS support.ticket_status),
                        resolved_at = {resolved_at},
                        lock_version = lock_version + 1,
                        updated_at = now()
                    WHERE id = :ticket_id
                    """
                ),
                {"ticket_id": ticket_id, "status": status},
            )
        if result.rowcount != 1:
            raise ApiError(
                status_code=404,
                code="TICKET_NOT_FOUND",
                message="The Ticket was not found.",
            )

    @staticmethod
    def _ticket(row: object) -> TicketRecord:
        mapping = row  # SQLAlchemy RowMapping at runtime.
        return TicketRecord(
            id=mapping["id"],  # type: ignore[index]
            ticket_number=mapping["ticket_number"],  # type: ignore[index]
            customer_user_id=mapping["customer_user_id"],  # type: ignore[index]
            subject=mapping["subject"],  # type: ignore[index]
            status=mapping["status"],  # type: ignore[index]
        )
