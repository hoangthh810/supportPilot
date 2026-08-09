from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from typing import Any
from uuid import UUID

from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.core.errors import ApiError
from backend.apps.support_api.tickets.contracts import (
    CreateTicketResult,
    MessageResult,
    MessageResumePort,
    ResumeTimeoutError,
    TicketDetail,
    TicketPage,
    TicketRepository,
)
from backend.apps.support_api.tickets.rate_limit import TicketWriteRateLimiter

STAFF_ROLES = frozenset({"support_agent", "support_manager", "admin"})


class TicketService:
    def __init__(
        self,
        *,
        repository: TicketRepository,
        resume_port: MessageResumePort,
        request_timeout_seconds: int,
        rate_limiter: TicketWriteRateLimiter,
    ) -> None:
        self._repository = repository
        self._resume_port = resume_port
        self._request_timeout_seconds = request_timeout_seconds
        self._rate_limiter = rate_limiter
        self._message_lock = asyncio.Lock()
        self._message_replays: dict[bytes, tuple[bytes, MessageResult | ApiError]] = {}

    async def create_ticket(
        self,
        *,
        actor: Actor,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> CreateTicketResult:
        self._require_customer(actor)
        await self._rate_limiter.consume(actor_id=actor.id, operation="create-ticket")
        return await self._repository.create_ticket(
            actor=actor,
            subject=subject,
            body=body,
            source=source.upper(),
            idempotency_key=idempotency_key,
        )

    async def list_tickets(
        self, *, actor: Actor, page: int, page_size: int
    ) -> TicketPage:
        self._require_scoped_reader(actor)
        return await self._repository.list_tickets(actor=actor, page=page, page_size=page_size)

    async def get_ticket_detail(self, *, actor: Actor, ticket_id: UUID) -> TicketDetail:
        self._require_scoped_reader(actor)
        detail = await self._repository.get_ticket_detail(actor=actor, ticket_id=ticket_id)
        if detail is None:
            raise self._not_found()
        return detail

    async def add_message(
        self,
        *,
        actor: Actor,
        ticket_id: UUID,
        content: str,
        attachment_references: list[Any],
        idempotency_key: str,
    ) -> MessageResult:
        if attachment_references:
            raise ApiError(
                status_code=422,
                code="ATTACHMENTS_NOT_SUPPORTED",
                message="Ticket attachments are not supported in v0.1.",
                retryable=False,
                details={"supported_from": "v1.0"},
            )
        self._require_scoped_reader(actor)
        replay_key = hashlib.sha256(
            f"{actor.id}\0{ticket_id}\0{idempotency_key}".encode()
        ).digest()
        request_hash = hashlib.sha256(content.encode()).digest()
        async with self._message_lock:
            cached = self._message_replays.get(replay_key)
            if cached is not None and cached[0] != request_hash:
                raise ApiError(
                    status_code=409,
                    code="REQUEST_VALIDATION_ERROR",
                    message="The Idempotency-Key was already used with a different request.",
                )
            replay = None if cached is None else cached[1]
            if isinstance(replay, MessageResult):
                return replace(replay, replayed=True)
            if isinstance(replay, ApiError):
                raise replay
            try:
                result = await self._add_message_once(
                    actor=actor,
                    ticket_id=ticket_id,
                    content=content,
                    idempotency_key=idempotency_key,
                )
            except ApiError as error:
                if error.code == "WORKFLOW_REQUEST_TIMEOUT":
                    self._remember_message_result(replay_key, request_hash, error)
                raise
            self._remember_message_result(replay_key, request_hash, result)
            return result

    async def _add_message_once(
        self,
        *,
        actor: Actor,
        ticket_id: UUID,
        content: str,
        idempotency_key: str,
    ) -> MessageResult:
        await self._rate_limiter.consume(actor_id=actor.id, operation="add-ticket-message")
        persisted = await self._repository.add_message(
            actor=actor,
            ticket_id=ticket_id,
            content=content,
            idempotency_key=idempotency_key,
        )
        if persisted.replayed or persisted.ticket.status != "WAITING_CUSTOMER":
            return MessageResult(
                message_id=persisted.message.id,
                ticket_id=persisted.ticket.id,
                ticket_status=persisted.ticket.status,
                resume_attempted=False,
                http_status=201,
                replayed=persisted.replayed,
            )

        try:
            outcome = await self._resume_port.resume_after_message(
                actor=actor,
                ticket=persisted.ticket,
                message=persisted.message,
                timeout_seconds=self._request_timeout_seconds,
            )
        except ResumeTimeoutError as error:
            await self._repository.set_ticket_status(ticket_id=ticket_id, status="ESCALATED")
            details: dict[str, Any] = {
                "ticket_id": str(ticket_id),
                "message_id": str(persisted.message.id),
            }
            if error.run_id is not None:
                details["run_id"] = str(error.run_id)
            raise ApiError(
                status_code=504,
                code="WORKFLOW_REQUEST_TIMEOUT",
                message="The workflow request exceeded its time budget.",
                retryable=False,
                details=details,
            ) from error

        if outcome.invariant_failure:
            await self._repository.set_ticket_status(ticket_id=ticket_id, status="ESCALATED")
            return MessageResult(
                message_id=persisted.message.id,
                ticket_id=ticket_id,
                ticket_status="ESCALATED",
                resume_attempted=False,
                http_status=200,
            )
        return MessageResult(
            message_id=persisted.message.id,
            ticket_id=ticket_id,
            ticket_status=outcome.ticket_status,
            resume_attempted=outcome.resumed,
            http_status=200,
            run_id=outcome.run_id,
            run_status=outcome.run_status,
            next_required_action=outcome.next_required_action,
            approval_request_id=outcome.approval_request_id,
            timeline_cursor=outcome.timeline_cursor,
        )

    def _remember_message_result(
        self, key: bytes, request_hash: bytes, result: MessageResult | ApiError
    ) -> None:
        if len(self._message_replays) >= 10_000:
            self._message_replays.pop(next(iter(self._message_replays)))
        self._message_replays[key] = (request_hash, result)

    @staticmethod
    def _require_customer(actor: Actor) -> None:
        if actor.status != "active" or actor.role != "customer" or actor.customer_id is None:
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message="The authenticated actor cannot perform this operation.",
            )

    @staticmethod
    def _require_scoped_reader(actor: Actor) -> None:
        if actor.status != "active" or (
            actor.role != "customer" and actor.role not in STAFF_ROLES
        ):
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message="The authenticated actor cannot perform this operation.",
            )
        if actor.role == "customer" and actor.customer_id is None:
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message="The authenticated actor cannot perform this operation.",
            )

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="TICKET_NOT_FOUND",
            message="The Ticket was not found.",
        )
