from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.walking_skeleton.contracts import (
    ActionAdapter,
    AgentAdapter,
    ApprovalAdapter,
    Proposal,
    TicketRecord,
    TicketRepository,
)


@dataclass(slots=True)
class RunState:
    run_id: UUID
    ticket: TicketRecord
    approval_id: UUID
    proposal: Proposal
    run_status: str = "WAITING_APPROVAL"
    approval_status: str = "PENDING"
    action_execution_status: str | None = None
    decision: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionResult:
    approval_id: UUID
    approval_status: str
    proposal_version: int
    proposal_hash: str
    run_id: UUID
    run_status: str
    ticket_status: str
    action_execution_status: str | None
    next_required_action: str | None
    timeline_cursor: str


class SkeletonService:
    def __init__(
        self,
        *,
        repository: TicketRepository,
        agent: AgentAdapter,
        approval: ApprovalAdapter,
        action: ActionAdapter,
    ) -> None:
        self._repository = repository
        self._agent = agent
        self._approval = approval
        self._action = action
        self._lock = asyncio.Lock()
        self._active_runs: dict[UUID, RunState] = {}
        self._run_replays: dict[tuple[UUID, UUID, str], RunState] = {}
        self._approvals: dict[UUID, RunState] = {}

    async def create_ticket(
        self,
        *,
        actor: Actor,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> TicketRecord:
        self._require_role(actor, {"customer"})
        return await self._repository.create_ticket(
            actor_id=actor.id,
            subject=subject,
            body=body,
            source=source.upper(),
            idempotency_key=idempotency_key,
        )

    async def create_run(
        self,
        *,
        actor: Actor,
        ticket_id: UUID,
        idempotency_key: str,
    ) -> RunState:
        self._require_role(actor, {"customer"})
        replay_key = (ticket_id, actor.id, idempotency_key)
        async with self._lock:
            replay = self._run_replays.get(replay_key)
            if replay is not None:
                return replay

            ticket = await self._repository.get_ticket_for_actor(ticket_id=ticket_id, actor=actor)
            if ticket is None:
                raise ApiError(
                    status_code=404,
                    code="TICKET_NOT_FOUND",
                    message="The Ticket was not found.",
                )
            active = self._active_runs.get(ticket_id)
            if active is not None and active.run_status == "WAITING_APPROVAL":
                raise ApiError(
                    status_code=409,
                    code="AGENT_RUN_ALREADY_ACTIVE",
                    message="A non-terminal Agent Run already exists for this Ticket.",
                    details={
                        "ticket_id": str(ticket_id),
                        "run_id": str(active.run_id),
                        "run_status": active.run_status,
                        "next_required_action": "approval",
                    },
                )

            proposal = self._agent.propose(ticket)
            state = RunState(
                run_id=uuid4(),
                ticket=ticket,
                approval_id=uuid4(),
                proposal=proposal,
            )
            await self._repository.set_ticket_status(
                ticket_id=ticket_id,
                status="WAITING_APPROVAL",
            )
            self._active_runs[ticket_id] = state
            self._run_replays[replay_key] = state
            self._approvals[state.approval_id] = state
            return state

    def get_approval(self, *, actor: Actor, approval_id: UUID) -> RunState:
        self._require_role(actor, {"support_agent", "support_manager", "admin"})
        state = self._approvals.get(approval_id)
        if state is None:
            raise ApiError(
                status_code=404,
                code="APPROVAL_NOT_FOUND",
                message="The approval request was not found.",
            )
        return state

    async def decide(
        self,
        *,
        actor: Actor,
        approval_id: UUID,
        decision: str,
        expected_version: int,
        expected_proposal_hash: str,
    ) -> DecisionResult:
        self._require_role(actor, {"support_agent", "support_manager", "admin"})
        async with self._lock:
            state = self._approvals.get(approval_id)
            if state is None:
                raise ApiError(
                    status_code=404,
                    code="APPROVAL_NOT_FOUND",
                    message="The approval request was not found.",
                )
            if state.decision is not None:
                if state.decision != decision:
                    raise ApiError(
                        status_code=409,
                        code="APPROVAL_ALREADY_DECIDED",
                        message="The approval request already has a terminal decision.",
                    )
                return self._decision_result(state)

            self._approval.validate_decision(
                decision=decision,
                expected_version=expected_version,
                expected_proposal_hash=expected_proposal_hash,
                proposal=state.proposal,
            )
            state.decision = decision
            if decision == "reject":
                state.approval_status = "REJECTED"
                state.run_status = "ESCALATED"
                await self._repository.set_ticket_status(
                    ticket_id=state.ticket.id,
                    status="ESCALATED",
                )
            else:
                action_status = self._action.execute(state.proposal)
                if action_status != "VERIFIED":
                    raise ApiError(
                        status_code=500,
                        code="SKELETON_ACTION_NOT_VERIFIED",
                        message="The deterministic skeleton action did not verify.",
                    )
                state.action_execution_status = action_status
                state.approval_status = "APPROVED"
                state.run_status = "COMPLETED"
                await self._repository.set_ticket_status(
                    ticket_id=state.ticket.id,
                    status="RESOLVED",
                )
            self._active_runs.pop(state.ticket.id, None)
            return self._decision_result(state)

    @staticmethod
    def _require_role(actor: Actor, allowed: set[str]) -> None:
        if actor.status != "active" or actor.role not in allowed:
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message="The authenticated actor cannot perform this operation.",
            )

    @staticmethod
    def _decision_result(state: RunState) -> DecisionResult:
        ticket_status = "RESOLVED" if state.run_status == "COMPLETED" else "ESCALATED"
        return DecisionResult(
            approval_id=state.approval_id,
            approval_status=state.approval_status,
            proposal_version=state.proposal.version,
            proposal_hash=state.proposal.proposal_hash,
            run_id=state.run_id,
            run_status=state.run_status,
            ticket_status=ticket_status,
            action_execution_status=state.action_execution_status,
            next_required_action=None,
            timeline_cursor=f"timeline:{state.run_id}:2",
        )
