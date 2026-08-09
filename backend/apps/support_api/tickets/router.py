from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, Field

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.auth.dependencies import require_roles
from backend.apps.support_api.core.correlation import get_correlation_id
from backend.apps.support_api.tickets.contracts import MessageResult, TicketRecord
from backend.apps.support_api.tickets.service import TicketService

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=10_000)
    source: Literal["web", "api"]


class TicketCreateResponse(BaseModel):
    ticket_id: UUID
    ticket_number: str
    ticket_status: Literal["OPEN"]
    correlation_id: str


class TicketSummaryResponse(BaseModel):
    ticket_id: UUID
    ticket_number: str
    subject: str
    source: str
    intent: str | None
    priority: str
    status: str
    assigned_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class TicketListResponse(BaseModel):
    items: list[TicketSummaryResponse]
    pagination: PaginationResponse
    correlation_id: str


class TicketMessageResponse(BaseModel):
    message_id: UUID
    sender_type: str
    content: str
    created_at: datetime


class TicketDetailResponse(TicketSummaryResponse):
    customer_id: UUID
    lock_version: int
    resolved_at: datetime | None
    closed_at: datetime | None
    messages: list[TicketMessageResponse]
    evidence: list[Any] = Field(default_factory=list)
    latest_run: None = None
    approvals: list[Any] = Field(default_factory=list)
    timeline: list[Any] = Field(default_factory=list)
    correlation_id: str


class TicketMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    attachment_references: list[Any] = Field(default_factory=list)


class TicketMessageOnlyResponse(BaseModel):
    message_id: UUID
    ticket_id: UUID
    ticket_status: str
    resume_attempted: Literal[False]
    correlation_id: str


class TicketMessageResumeResponse(BaseModel):
    message_id: UUID
    ticket_id: UUID
    ticket_status: str
    run_id: UUID
    run_status: str
    resume_attempted: Literal[True]
    next_required_action: str | None
    approval_request_id: UUID | None
    correlation_id: str
    timeline_cursor: str


def get_ticket_service(request: Request) -> TicketService:
    service = getattr(request.app.state, "ticket_service", None)
    if not isinstance(service, TicketService):
        raise RuntimeError("Ticket service is unavailable")
    return service


def summary(ticket: TicketRecord) -> TicketSummaryResponse:
    return TicketSummaryResponse(
        ticket_id=ticket.id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        source=ticket.source,
        intent=ticket.intent,
        priority=ticket.priority,
        status=ticket.status,
        assigned_user_id=ticket.assigned_user_id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.post("", response_model=TicketCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    response: Response,
    actor: Annotated[Actor, Depends(require_roles("customer"))],
    service: Annotated[TicketService, Depends(get_ticket_service)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
) -> TicketCreateResponse:
    result = await service.create_ticket(
        actor=actor,
        subject=payload.subject,
        body=payload.body,
        source=payload.source,
        idempotency_key=idempotency_key,
    )
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return TicketCreateResponse(
        ticket_id=result.ticket.id,
        ticket_number=result.ticket.ticket_number,
        ticket_status="OPEN",
        correlation_id=get_correlation_id(request),
    )


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    request: Request,
    actor: Annotated[
        Actor,
        Depends(require_roles("customer", "support_agent", "support_manager", "admin")),
    ],
    service: Annotated[TicketService, Depends(get_ticket_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketListResponse:
    result = await service.list_tickets(actor=actor, page=page, page_size=page_size)
    return TicketListResponse(
        items=[summary(ticket) for ticket in result.items],
        pagination=PaginationResponse(
            page=page,
            page_size=page_size,
            total=result.total,
            total_pages=math.ceil(result.total / page_size),
        ),
        correlation_id=get_correlation_id(request),
    )


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket_detail(
    ticket_id: UUID,
    request: Request,
    actor: Annotated[
        Actor,
        Depends(require_roles("customer", "support_agent", "support_manager", "admin")),
    ],
    service: Annotated[TicketService, Depends(get_ticket_service)],
) -> TicketDetailResponse:
    detail = await service.get_ticket_detail(actor=actor, ticket_id=ticket_id)
    ticket_summary = summary(detail.ticket)
    return TicketDetailResponse(
        **ticket_summary.model_dump(),
        customer_id=detail.ticket.customer_id,
        lock_version=detail.ticket.lock_version,
        resolved_at=detail.ticket.resolved_at,
        closed_at=detail.ticket.closed_at,
        messages=[
            TicketMessageResponse(
                message_id=message.id,
                sender_type=message.sender_type,
                content=message.content,
                created_at=message.created_at,
            )
            for message in detail.messages
        ],
        correlation_id=get_correlation_id(request),
    )


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageOnlyResponse | TicketMessageResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_ticket_message(
    ticket_id: UUID,
    payload: TicketMessageRequest,
    request: Request,
    response: Response,
    actor: Annotated[
        Actor,
        Depends(require_roles("customer", "support_agent", "support_manager", "admin")),
    ],
    service: Annotated[TicketService, Depends(get_ticket_service)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
) -> TicketMessageOnlyResponse | TicketMessageResumeResponse:
    result: MessageResult = await service.add_message(
        actor=actor,
        ticket_id=ticket_id,
        content=payload.content,
        attachment_references=payload.attachment_references,
        idempotency_key=idempotency_key,
    )
    response.status_code = result.http_status
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    if not result.resume_attempted:
        return TicketMessageOnlyResponse(
            message_id=result.message_id,
            ticket_id=result.ticket_id,
            ticket_status=result.ticket_status,
            resume_attempted=False,
            correlation_id=get_correlation_id(request),
        )
    if result.run_id is None or result.run_status is None or result.timeline_cursor is None:
        raise RuntimeError("resume outcome is missing its public run projection")
    return TicketMessageResumeResponse(
        message_id=result.message_id,
        ticket_id=result.ticket_id,
        ticket_status=result.ticket_status,
        resume_attempted=True,
        run_id=result.run_id,
        run_status=result.run_status,
        next_required_action=result.next_required_action,
        approval_request_id=result.approval_request_id,
        correlation_id=get_correlation_id(request),
        timeline_cursor=result.timeline_cursor,
    )
