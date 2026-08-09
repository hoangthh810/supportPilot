from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.auth.dependencies import require_roles
from backend.apps.support_api.core.correlation import get_correlation_id
from backend.apps.support_api.walking_skeleton.service import SkeletonService

router = APIRouter(prefix="/api/v1")


class AgentRunRequest(BaseModel):
    pass


class AgentRunResponse(BaseModel):
    run_id: UUID
    run_status: Literal["WAITING_APPROVAL"]
    ticket_status: Literal["WAITING_APPROVAL"]
    next_required_action: Literal["approval"]
    approval_request_id: UUID
    correlation_id: str
    timeline_cursor: str


class ApprovalDetailResponse(BaseModel):
    approval_id: UUID
    approval_status: str
    proposal_version: int
    proposal_hash: str
    run_id: UUID
    ticket_id: UUID
    summary: str
    action: dict[str, Any]
    evidence: list[str]
    synthetic: Literal[True] = True
    correlation_id: str


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)
    expected_proposal_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    edited_action: dict[str, Any] | None = None


class ApprovalDecisionResponse(BaseModel):
    approval_id: UUID
    approval_status: str
    proposal_version: int
    proposal_hash: str
    run_id: UUID
    run_status: str
    ticket_status: str
    action_execution_status: str | None
    next_required_action: str | None
    correlation_id: str
    timeline_cursor: str


def get_skeleton_service(request: Request) -> SkeletonService:
    service = getattr(request.app.state, "skeleton_service", None)
    if not isinstance(service, SkeletonService):
        raise RuntimeError("Walking Skeleton service is unavailable")
    return service


@router.post(
    "/tickets/{ticket_id}/agent-runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_run(
    ticket_id: UUID,
    payload: AgentRunRequest,
    request: Request,
    actor: Annotated[Actor, Depends(require_roles("customer"))],
    service: Annotated[SkeletonService, Depends(get_skeleton_service)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
) -> AgentRunResponse:
    del payload
    state = await service.create_run(
        actor=actor,
        ticket_id=ticket_id,
        idempotency_key=idempotency_key,
    )
    return AgentRunResponse(
        run_id=state.run_id,
        run_status="WAITING_APPROVAL",
        ticket_status="WAITING_APPROVAL",
        next_required_action="approval",
        approval_request_id=state.approval_id,
        correlation_id=get_correlation_id(request),
        timeline_cursor=f"timeline:{state.run_id}:1",
    )


@router.get(
    "/approval-requests/{approval_id}",
    response_model=ApprovalDetailResponse,
)
async def get_approval_request(
    approval_id: UUID,
    request: Request,
    actor: Annotated[
        Actor,
        Depends(require_roles("support_agent", "support_manager", "admin")),
    ],
    service: Annotated[SkeletonService, Depends(get_skeleton_service)],
) -> ApprovalDetailResponse:
    state = service.get_approval(actor=actor, approval_id=approval_id)
    return ApprovalDetailResponse(
        approval_id=state.approval_id,
        approval_status=state.approval_status,
        proposal_version=state.proposal.version,
        proposal_hash=state.proposal.proposal_hash,
        run_id=state.run_id,
        ticket_id=state.ticket.id,
        summary=state.proposal.summary,
        action=state.proposal.action,
        evidence=list(state.proposal.evidence),
        correlation_id=get_correlation_id(request),
    )


@router.post(
    "/approval-requests/{approval_id}/decision",
    response_model=ApprovalDecisionResponse,
)
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    request: Request,
    actor: Annotated[
        Actor,
        Depends(require_roles("support_agent", "support_manager", "admin")),
    ],
    service: Annotated[SkeletonService, Depends(get_skeleton_service)],
) -> ApprovalDecisionResponse:
    result = await service.decide(
        actor=actor,
        approval_id=approval_id,
        decision=payload.decision,
        expected_version=payload.expected_version,
        expected_proposal_hash=payload.expected_proposal_hash,
    )
    return ApprovalDecisionResponse(
        approval_id=result.approval_id,
        approval_status=result.approval_status,
        proposal_version=result.proposal_version,
        proposal_hash=result.proposal_hash,
        run_id=result.run_id,
        run_status=result.run_status,
        ticket_status=result.ticket_status,
        action_execution_status=result.action_execution_status,
        next_required_action=result.next_required_action,
        correlation_id=get_correlation_id(request),
        timeline_cursor=result.timeline_cursor,
    )
