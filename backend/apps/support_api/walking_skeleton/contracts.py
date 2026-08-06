from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Actor:
    id: UUID
    role: str
    status: str


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    email: str
    password_hash: str
    role: str
    status: str


@dataclass(frozen=True, slots=True)
class TicketRecord:
    id: UUID
    ticket_number: str
    customer_user_id: UUID
    subject: str
    status: str


@dataclass(frozen=True, slots=True)
class Proposal:
    version: int
    proposal_hash: str
    summary: str
    action: dict[str, Any]
    evidence: tuple[str, ...]


class TicketRepository(Protocol):
    async def find_user_by_email(self, email: str) -> UserRecord | None: ...

    async def create_ticket(
        self,
        *,
        actor_id: UUID,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> TicketRecord: ...

    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: Actor
    ) -> TicketRecord | None: ...

    async def set_ticket_status(self, *, ticket_id: UUID, status: str) -> None: ...


class AgentAdapter(Protocol):
    def propose(self, ticket: TicketRecord) -> Proposal: ...


class ApprovalAdapter(Protocol):
    def validate_decision(
        self,
        *,
        decision: str,
        expected_version: int,
        expected_proposal_hash: str,
        proposal: Proposal,
    ) -> None: ...


class ActionAdapter(Protocol):
    def execute(self, proposal: Proposal) -> str: ...
