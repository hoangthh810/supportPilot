from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from backend.apps.support_api.auth.contracts import AuthenticatedActor
from backend.apps.support_api.tickets.contracts import TicketRecord as TicketRecord


@dataclass(frozen=True, slots=True)
class Proposal:
    version: int
    proposal_hash: str
    summary: str
    action: dict[str, Any]
    evidence: tuple[str, ...]


class TicketRepository(Protocol):
    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: AuthenticatedActor
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
