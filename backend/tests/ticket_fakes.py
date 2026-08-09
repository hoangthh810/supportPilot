from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.tickets.contracts import (
    CreateTicketResult,
    PersistMessageResult,
    ResumeOutcome,
    TicketDetail,
    TicketMessageRecord,
    TicketPage,
    TicketRecord,
)


class MemoryTicketRepository:
    def __init__(self) -> None:
        self.tickets: dict[UUID, TicketRecord] = {}
        self.messages: dict[UUID, list[TicketMessageRecord]] = {}
        self.create_replays: dict[tuple[UUID, str], tuple[tuple[str, str, str], UUID]] = {}
        self.message_replays: dict[
            tuple[UUID, UUID, str], tuple[str, TicketMessageRecord]
        ] = {}

    async def create_ticket(
        self,
        *,
        actor: Actor,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> CreateTicketResult:
        key = (actor.id, idempotency_key)
        request = (subject, body, source)
        replay = self.create_replays.get(key)
        if replay is not None:
            if replay[0] != request:
                raise ApiError(
                    status_code=409,
                    code="REQUEST_VALIDATION_ERROR",
                    message="The Idempotency-Key was already used with a different request.",
                )
            return CreateTicketResult(self.tickets[replay[1]], replayed=True)
        if actor.customer_id is None:
            raise ApiError(status_code=403, code="FORBIDDEN", message="Forbidden.")
        now = datetime.now(UTC)
        ticket_id = uuid4()
        ticket = TicketRecord(
            id=ticket_id,
            ticket_number=f"SP-{ticket_id.hex[:8].upper()}",
            customer_id=actor.customer_id,
            customer_user_id=actor.id,
            source=source,
            subject=subject,
            intent="payment_mismatch",
            priority="NORMAL",
            status="OPEN",
            assigned_user_id=None,
            lock_version=1,
            created_at=now,
            updated_at=now,
            resolved_at=None,
            closed_at=None,
        )
        first_message = TicketMessageRecord(
            id=uuid4(),
            ticket_id=ticket_id,
            sender_type="CUSTOMER",
            sender_user_id=actor.id,
            content=body,
            created_at=now,
        )
        self.tickets[ticket_id] = ticket
        self.messages[ticket_id] = [first_message]
        self.create_replays[key] = (request, ticket_id)
        return CreateTicketResult(ticket, replayed=False)

    async def list_tickets(self, *, actor: Actor, page: int, page_size: int) -> TicketPage:
        tickets = [
            ticket
            for ticket in self.tickets.values()
            if actor.role != "customer" or ticket.customer_user_id == actor.id
        ]
        tickets.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        offset = (page - 1) * page_size
        return TicketPage(tuple(tickets[offset : offset + page_size]), len(tickets))

    async def get_ticket_detail(
        self, *, actor: Actor, ticket_id: UUID
    ) -> TicketDetail | None:
        ticket = await self.get_ticket_for_actor(ticket_id=ticket_id, actor=actor)
        if ticket is None:
            return None
        return TicketDetail(ticket, tuple(self.messages[ticket_id]))

    async def add_message(
        self,
        *,
        actor: Actor,
        ticket_id: UUID,
        content: str,
        idempotency_key: str,
    ) -> PersistMessageResult:
        ticket = await self.get_ticket_for_actor(ticket_id=ticket_id, actor=actor)
        if ticket is None:
            raise ApiError(
                status_code=404,
                code="TICKET_NOT_FOUND",
                message="The Ticket was not found.",
            )
        key = (actor.id, ticket_id, idempotency_key)
        replay = self.message_replays.get(key)
        if replay is not None:
            if replay[0] != content:
                raise ApiError(
                    status_code=409,
                    code="REQUEST_VALIDATION_ERROR",
                    message="The Idempotency-Key was already used with a different request.",
                )
            return PersistMessageResult(ticket, replay[1], replayed=True)
        now = datetime.now(UTC)
        message = TicketMessageRecord(
            id=uuid4(),
            ticket_id=ticket_id,
            sender_type="CUSTOMER" if actor.role == "customer" else "STAFF",
            sender_user_id=actor.id,
            content=content,
            created_at=now,
        )
        self.messages[ticket_id].append(message)
        updated = replace(ticket, lock_version=ticket.lock_version + 1, updated_at=now)
        self.tickets[ticket_id] = updated
        self.message_replays[key] = (content, message)
        return PersistMessageResult(updated, message, replayed=False)

    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: Actor
    ) -> TicketRecord | None:
        ticket = self.tickets.get(ticket_id)
        if ticket is None or (
            actor.role == "customer" and ticket.customer_user_id != actor.id
        ):
            return None
        return ticket

    async def set_ticket_status(self, *, ticket_id: UUID, status: str) -> None:
        ticket = self.tickets[ticket_id]
        self.tickets[ticket_id] = replace(
            ticket,
            status=status,
            lock_version=ticket.lock_version + 1,
            updated_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC) if status == "RESOLVED" else None,
        )


class MemoryResumePort:
    def __init__(self, outcome: ResumeOutcome | None = None) -> None:
        self.outcome = outcome or ResumeOutcome(
            resumed=False,
            ticket_status="ESCALATED",
            invariant_failure=True,
        )
        self.calls = 0

    async def resume_after_message(
        self,
        *,
        actor: Actor,
        ticket: TicketRecord,
        message: TicketMessageRecord,
        timeout_seconds: int,
    ) -> ResumeOutcome:
        del actor, ticket, message, timeout_seconds
        self.calls += 1
        return self.outcome
