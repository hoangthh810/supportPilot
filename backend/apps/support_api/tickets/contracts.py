from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.apps.support_api.auth.contracts import AuthenticatedActor


@dataclass(frozen=True, slots=True)
class TicketRecord:
    id: UUID
    ticket_number: str
    customer_id: UUID
    customer_user_id: UUID
    source: str
    subject: str
    intent: str | None
    priority: str
    status: str
    assigned_user_id: UUID | None
    lock_version: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None


@dataclass(frozen=True, slots=True)
class TicketMessageRecord:
    id: UUID
    ticket_id: UUID
    sender_type: str
    sender_user_id: UUID | None
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TicketPage:
    items: tuple[TicketRecord, ...]
    total: int


@dataclass(frozen=True, slots=True)
class TicketDetail:
    ticket: TicketRecord
    messages: tuple[TicketMessageRecord, ...]


@dataclass(frozen=True, slots=True)
class CreateTicketResult:
    ticket: TicketRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class PersistMessageResult:
    ticket: TicketRecord
    message: TicketMessageRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class ResumeOutcome:
    resumed: bool
    ticket_status: str
    run_id: UUID | None = None
    run_status: str | None = None
    next_required_action: str | None = None
    approval_request_id: UUID | None = None
    timeline_cursor: str | None = None
    invariant_failure: bool = False


@dataclass(frozen=True, slots=True)
class MessageResult:
    message_id: UUID
    ticket_id: UUID
    ticket_status: str
    resume_attempted: bool
    http_status: int
    replayed: bool = False
    run_id: UUID | None = None
    run_status: str | None = None
    next_required_action: str | None = None
    approval_request_id: UUID | None = None
    timeline_cursor: str | None = None


class ResumeTimeoutError(Exception):
    def __init__(self, *, run_id: UUID | None) -> None:
        super().__init__("the same-run resume exceeded its request budget")
        self.run_id = run_id


class TicketRepository(Protocol):
    async def create_ticket(
        self,
        *,
        actor: AuthenticatedActor,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> CreateTicketResult: ...

    async def list_tickets(
        self, *, actor: AuthenticatedActor, page: int, page_size: int
    ) -> TicketPage: ...

    async def get_ticket_detail(
        self, *, actor: AuthenticatedActor, ticket_id: UUID
    ) -> TicketDetail | None: ...

    async def add_message(
        self,
        *,
        actor: AuthenticatedActor,
        ticket_id: UUID,
        content: str,
        idempotency_key: str,
    ) -> PersistMessageResult: ...

    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: AuthenticatedActor
    ) -> TicketRecord | None: ...

    async def set_ticket_status(self, *, ticket_id: UUID, status: str) -> None: ...


class MessageResumePort(Protocol):
    async def resume_after_message(
        self,
        *,
        actor: AuthenticatedActor,
        ticket: TicketRecord,
        message: TicketMessageRecord,
        timeout_seconds: int,
    ) -> ResumeOutcome: ...


class NoopMessageResumePort:
    """Safe composition until the workflow persistence task supplies an adapter."""

    async def resume_after_message(
        self,
        *,
        actor: AuthenticatedActor,
        ticket: TicketRecord,
        message: TicketMessageRecord,
        timeout_seconds: int,
    ) -> ResumeOutcome:
        del actor, message, timeout_seconds
        return ResumeOutcome(
            resumed=False,
            ticket_status="ESCALATED",
            invariant_failure=True,
        )
