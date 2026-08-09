from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.tickets.contracts import (
    CreateTicketResult,
    PersistMessageResult,
    TicketDetail,
    TicketMessageRecord,
    TicketPage,
    TicketRecord,
)

TICKET_COLUMNS = """
    ticket.id, ticket.ticket_number, ticket.customer_id,
    customer.user_id AS customer_user_id, ticket.source::text,
    ticket.subject, ticket.intent, ticket.priority::text,
    ticket.status::text, ticket.assigned_user_id, ticket.lock_version,
    ticket.created_at, ticket.updated_at, ticket.resolved_at, ticket.closed_at
"""


class PostgresTicketRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create_ticket(
        self,
        *,
        actor: Actor,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> CreateTicketResult:
        database_key = self._database_key(
            operation="create-ticket",
            actor_id=actor.id,
            ticket_id=None,
            idempotency_key=idempotency_key,
        )
        async with self._engine.begin() as connection:
            await self._lock(connection, database_key)
            existing = (
                await connection.execute(
                    text(
                        f"""
                        SELECT {TICKET_COLUMNS}, message.content AS first_message
                        FROM support.ticket_messages AS message
                        JOIN support.support_tickets AS ticket ON ticket.id = message.ticket_id
                        JOIN support.customers AS customer ON customer.id = ticket.customer_id
                        WHERE message.sender_user_id = :actor_id
                          AND message.idempotency_key = :idempotency_key
                        LIMIT 1
                        """
                    ),
                    {"actor_id": actor.id, "idempotency_key": database_key},
                )
            ).mappings().one_or_none()
            if existing is not None:
                if (
                    existing["subject"] != subject
                    or existing["source"] != source
                    or existing["first_message"] != body
                ):
                    raise self._idempotency_conflict()
                return CreateTicketResult(ticket=self._ticket(existing), replayed=True)

            customer_id = (
                await connection.execute(
                    text(
                        """
                        SELECT id
                        FROM support.customers
                        WHERE id = :customer_id AND user_id = :actor_id AND status = 'ACTIVE'
                        """
                    ),
                    {"customer_id": actor.customer_id, "actor_id": actor.id},
                )
            ).scalar_one_or_none()
            if customer_id is None:
                raise ApiError(
                    status_code=403,
                    code="FORBIDDEN",
                    message="The authenticated actor cannot perform this operation.",
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
                    "actor_id": actor.id,
                    "content": body,
                    "idempotency_key": database_key,
                },
            )
            row = await self._load_ticket(connection, ticket_id=ticket_id, actor=actor)
            if row is None:
                raise RuntimeError("created Ticket could not be reloaded")
            return CreateTicketResult(ticket=self._ticket(row), replayed=False)

    async def list_tickets(
        self, *, actor: Actor, page: int, page_size: int
    ) -> TicketPage:
        scope_sql, parameters = self._scope(actor)
        parameters.update({"limit": page_size, "offset": (page - 1) * page_size})
        async with self._engine.connect() as connection:
            total = int(
                (
                    await connection.execute(
                        text(
                            f"""
                            SELECT count(*)
                            FROM support.support_tickets AS ticket
                            JOIN support.customers AS customer ON customer.id = ticket.customer_id
                            WHERE TRUE {scope_sql}
                            """
                        ),
                        parameters,
                    )
                ).scalar_one()
            )
            rows = (
                await connection.execute(
                    text(
                        f"""
                        SELECT {TICKET_COLUMNS}
                        FROM support.support_tickets AS ticket
                        JOIN support.customers AS customer ON customer.id = ticket.customer_id
                        WHERE TRUE {scope_sql}
                        ORDER BY ticket.created_at DESC, ticket.id DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    parameters,
                )
            ).mappings().all()
        return TicketPage(items=tuple(self._ticket(row) for row in rows), total=total)

    async def get_ticket_detail(
        self, *, actor: Actor, ticket_id: UUID
    ) -> TicketDetail | None:
        async with self._engine.connect() as connection:
            row = await self._load_ticket(connection, ticket_id=ticket_id, actor=actor)
            if row is None:
                return None
            messages = (
                await connection.execute(
                    text(
                        """
                        SELECT id, ticket_id, sender_type::text, sender_user_id,
                               content, created_at
                        FROM support.ticket_messages
                        WHERE ticket_id = :ticket_id
                        ORDER BY created_at, id
                        """
                    ),
                    {"ticket_id": ticket_id},
                )
            ).mappings().all()
        return TicketDetail(
            ticket=self._ticket(row),
            messages=tuple(self._message(message) for message in messages),
        )

    async def add_message(
        self,
        *,
        actor: Actor,
        ticket_id: UUID,
        content: str,
        idempotency_key: str,
    ) -> PersistMessageResult:
        database_key = self._database_key(
            operation="add-ticket-message",
            actor_id=actor.id,
            ticket_id=ticket_id,
            idempotency_key=idempotency_key,
        )
        async with self._engine.begin() as connection:
            await self._lock(connection, database_key)
            row = await self._load_ticket(
                connection,
                ticket_id=ticket_id,
                actor=actor,
                for_update=True,
            )
            if row is None:
                raise self._not_found()
            existing = (
                await connection.execute(
                    text(
                        """
                        SELECT id, ticket_id, sender_type::text, sender_user_id,
                               content, created_at
                        FROM support.ticket_messages
                        WHERE ticket_id = :ticket_id AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"ticket_id": ticket_id, "idempotency_key": database_key},
                )
            ).mappings().one_or_none()
            if existing is not None:
                if existing["content"] != content:
                    raise self._idempotency_conflict()
                return PersistMessageResult(
                    ticket=self._ticket(row),
                    message=self._message(existing),
                    replayed=True,
                )

            message_id = uuid4()
            sender_type = "CUSTOMER" if actor.role == "customer" else "STAFF"
            inserted = (
                await connection.execute(
                    text(
                        """
                        INSERT INTO support.ticket_messages
                            (id, ticket_id, sender_type, sender_user_id,
                             content, idempotency_key)
                        VALUES
                            (:id, :ticket_id,
                             CAST(:sender_type AS support.message_sender_type),
                             :sender_user_id, :content, :idempotency_key)
                        RETURNING id, ticket_id, sender_type::text, sender_user_id,
                                  content, created_at
                        """
                    ),
                    {
                        "id": message_id,
                        "ticket_id": ticket_id,
                        "sender_type": sender_type,
                        "sender_user_id": actor.id,
                        "content": content,
                        "idempotency_key": database_key,
                    },
                )
            ).mappings().one()
            await connection.execute(
                text(
                    """
                    UPDATE support.support_tickets
                    SET updated_at = now(), lock_version = lock_version + 1
                    WHERE id = :ticket_id
                    """
                ),
                {"ticket_id": ticket_id},
            )
            refreshed = await self._load_ticket(connection, ticket_id=ticket_id, actor=actor)
            if refreshed is None:
                raise RuntimeError("updated Ticket could not be reloaded")
            return PersistMessageResult(
                ticket=self._ticket(refreshed),
                message=self._message(inserted),
                replayed=False,
            )

    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: Actor
    ) -> TicketRecord | None:
        async with self._engine.connect() as connection:
            row = await self._load_ticket(connection, ticket_id=ticket_id, actor=actor)
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
            raise self._not_found()

    async def _load_ticket(
        self,
        connection: AsyncConnection,
        *,
        ticket_id: UUID,
        actor: Actor,
        for_update: bool = False,
    ) -> RowMapping | None:
        scope_sql, parameters = self._scope(actor)
        parameters["ticket_id"] = ticket_id
        lock_sql = "FOR UPDATE OF ticket" if for_update else ""
        return (
            await connection.execute(
                text(
                    f"""
                    SELECT {TICKET_COLUMNS}
                    FROM support.support_tickets AS ticket
                    JOIN support.customers AS customer ON customer.id = ticket.customer_id
                    WHERE ticket.id = :ticket_id {scope_sql}
                    {lock_sql}
                    """
                ),
                parameters,
            )
        ).mappings().one_or_none()

    @staticmethod
    async def _lock(connection: AsyncConnection, key: str) -> None:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": key},
        )

    @staticmethod
    def _scope(actor: Actor) -> tuple[str, dict[str, Any]]:
        if actor.role == "customer":
            return (
                "AND customer.id = :customer_id AND customer.user_id = :actor_id",
                {"customer_id": actor.customer_id, "actor_id": actor.id},
            )
        return "", {}

    @staticmethod
    def _database_key(
        *, operation: str, actor_id: UUID, ticket_id: UUID | None, idempotency_key: str
    ) -> str:
        scope = f"{operation}\0{actor_id}\0{ticket_id or ''}\0{idempotency_key}"
        return f"{operation}:{hashlib.sha256(scope.encode()).hexdigest()}"

    @staticmethod
    def _ticket(row: RowMapping) -> TicketRecord:
        return TicketRecord(
            id=row["id"],
            ticket_number=row["ticket_number"],
            customer_id=row["customer_id"],
            customer_user_id=row["customer_user_id"],
            source=row["source"],
            subject=row["subject"],
            intent=row["intent"],
            priority=row["priority"],
            status=row["status"],
            assigned_user_id=row["assigned_user_id"],
            lock_version=row["lock_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            closed_at=row["closed_at"],
        )

    @staticmethod
    def _message(row: RowMapping) -> TicketMessageRecord:
        return TicketMessageRecord(
            id=row["id"],
            ticket_id=row["ticket_id"],
            sender_type=row["sender_type"],
            sender_user_id=row["sender_user_id"],
            content=row["content"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="TICKET_NOT_FOUND",
            message="The Ticket was not found.",
        )

    @staticmethod
    def _idempotency_conflict() -> ApiError:
        return ApiError(
            status_code=409,
            code="REQUEST_VALIDATION_ERROR",
            message="The Idempotency-Key was already used with a different request.",
        )
