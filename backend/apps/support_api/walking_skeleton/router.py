from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.apps.support_api.core.correlation import get_correlation_id
from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.walking_skeleton.contracts import Actor
from backend.apps.support_api.walking_skeleton.service import SkeletonService

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)


class ActorResponse(BaseModel):
    id: UUID
    role: str
    status: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in_seconds: int
    actor: ActorResponse
    correlation_id: str


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=10_000)
    source: Literal["web", "api"]


class TicketCreateResponse(BaseModel):
    ticket_id: UUID
    ticket_number: str
    ticket_status: Literal["OPEN"]
    correlation_id: str


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


def get_actor(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[SkeletonService, Depends(get_skeleton_service)],
) -> Actor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="AUTH_UNAUTHENTICATED",
            message="A valid access token is required.",
        )
    return service.authenticate(credentials.credentials)


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    service: Annotated[SkeletonService, Depends(get_skeleton_service)],
) -> LoginResponse:
    result = await service.login(email=str(payload.email), password=payload.password)
    return LoginResponse(
        access_token=result.access_token,
        expires_in_seconds=result.expires_in_seconds,
        actor=ActorResponse(id=result.actor.id, role=result.actor.role, status=result.actor.status),
        correlation_id=get_correlation_id(request),
    )


@router.post(
    "/tickets",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    actor: Annotated[Actor, Depends(get_actor)],
    service: Annotated[SkeletonService, Depends(get_skeleton_service)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
) -> TicketCreateResponse:
    ticket = await service.create_ticket(
        actor=actor,
        subject=payload.subject,
        body=payload.body,
        source=payload.source,
        idempotency_key=idempotency_key,
    )
    return TicketCreateResponse(
        ticket_id=ticket.id,
        ticket_number=ticket.ticket_number,
        ticket_status="OPEN",
        correlation_id=get_correlation_id(request),
    )


@router.post(
    "/tickets/{ticket_id}/agent-runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_run(
    ticket_id: UUID,
    payload: AgentRunRequest,
    request: Request,
    actor: Annotated[Actor, Depends(get_actor)],
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
    actor: Annotated[Actor, Depends(get_actor)],
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
    actor: Annotated[Actor, Depends(get_actor)],
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
