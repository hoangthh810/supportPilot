from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from backend.apps.support_api.app import create_app
from backend.apps.support_api.auth.contracts import AuthUser
from backend.apps.support_api.auth.service import AuthService
from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.tickets.contracts import ResumeOutcome, ResumeTimeoutError
from backend.apps.support_api.tickets.rate_limit import TicketWriteRateLimiter
from backend.apps.support_api.tickets.service import TicketService
from backend.apps.support_api.walking_skeleton.adapters import (
    FakeActionAdapter,
    FakeAgentAdapter,
    FakeApprovalAdapter,
)
from backend.apps.support_api.walking_skeleton.service import SkeletonService
from backend.tests.ticket_fakes import MemoryResumePort, MemoryTicketRepository

CUSTOMER_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000201")
OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000103")
OTHER_CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000203")
AGENT_USER_ID = UUID("00000000-0000-4000-8000-000000000102")


class MemoryAuthRepository:
    def __init__(self) -> None:
        password_hash = PasswordHash.recommended().hash("demo-password")
        self.users = {
            "customer@example.test": AuthUser(
                CUSTOMER_USER_ID,
                "customer@example.test",
                password_hash,
                "CUSTOMER",
                "ACTIVE",
                CUSTOMER_ID,
            ),
            "other@example.test": AuthUser(
                OTHER_USER_ID,
                "other@example.test",
                password_hash,
                "CUSTOMER",
                "ACTIVE",
                OTHER_CUSTOMER_ID,
            ),
            "agent@example.test": AuthUser(
                AGENT_USER_ID,
                "agent@example.test",
                password_hash,
                "SUPPORT_AGENT",
                "ACTIVE",
                None,
            ),
        }

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        return self.users.get(email)

    async def find_user_by_id(self, user_id: UUID) -> AuthUser | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def record_successful_login(self, user_id: UUID) -> bool:
        return any(user.id == user_id for user in self.users.values())


class TimeoutResumePort:
    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        self.calls = 0

    async def resume_after_message(self, **_: object) -> ResumeOutcome:
        self.calls += 1
        raise ResumeTimeoutError(run_id=self.run_id)


def build_client(
    settings: Settings,
    *,
    resume_port: MemoryResumePort | TimeoutResumePort | None = None,
    rate_limit: int = 1000,
) -> tuple[TestClient, MemoryTicketRepository, MemoryResumePort | TimeoutResumePort]:
    repository = MemoryTicketRepository()
    auth_service = AuthService(settings=settings, repository=MemoryAuthRepository())
    actual_resume_port = resume_port or MemoryResumePort()
    ticket_service = TicketService(
        repository=repository,
        resume_port=actual_resume_port,
        request_timeout_seconds=settings.workflow_request_timeout_seconds,
        rate_limiter=TicketWriteRateLimiter(limit=rate_limit),
    )
    skeleton_service = SkeletonService(
        repository=repository,
        agent=FakeAgentAdapter(),
        approval=FakeApprovalAdapter(),
        action=FakeActionAdapter(),
    )
    app = create_app(settings, skeleton_service, auth_service, ticket_service)
    return TestClient(app), repository, actual_resume_port


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "demo-password"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def auth_headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def create_ticket(client: TestClient, token: str, key: str = "ticket-key") -> dict[str, str]:
    response = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token, key),
        json={
            "subject": "Payment mismatch",
            "body": "Synthetic paid order is still pending.",
            "source": "web",
        },
    )
    assert response.status_code == 201
    return cast(dict[str, str], response.json())


def test_create_is_transaction_shaped_idempotent_and_never_starts_run(
    settings: Settings,
) -> None:
    client, repository, resume_port = build_client(settings)
    token = login(client, "customer@example.test")

    first = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token, "create-once"),
        json={"subject": "Mismatch", "body": "Synthetic body", "source": "web"},
    )
    replay = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token, "create-once"),
        json={"subject": "Mismatch", "body": "Synthetic body", "source": "web"},
    )

    assert first.status_code == replay.status_code == 201
    assert first.json()["ticket_id"] == replay.json()["ticket_id"]
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert len(repository.tickets) == 1
    assert len(repository.messages[UUID(first.json()["ticket_id"])]) == 1
    assert resume_port.calls == 0

    conflict = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token, "create-once"),
        json={"subject": "Changed", "body": "Synthetic body", "source": "web"},
    )
    assert conflict.status_code == 409


def test_list_and_detail_enforce_customer_scope_and_safe_projection(
    settings: Settings,
) -> None:
    client, _, _ = build_client(settings)
    owner = login(client, "customer@example.test")
    other = login(client, "other@example.test")
    agent = login(client, "agent@example.test")
    ticket = create_ticket(client, owner)

    own_list = client.get("/api/v1/tickets", headers=auth_headers(owner))
    other_list = client.get("/api/v1/tickets", headers=auth_headers(other))
    staff_list = client.get("/api/v1/tickets", headers=auth_headers(agent))
    hidden = client.get(
        f"/api/v1/tickets/{ticket['ticket_id']}", headers=auth_headers(other)
    )
    detail = client.get(
        f"/api/v1/tickets/{ticket['ticket_id']}", headers=auth_headers(owner)
    )

    assert own_list.json()["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
    }
    assert other_list.json()["items"] == []
    assert staff_list.json()["pagination"]["total"] == 1
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "TICKET_NOT_FOUND"
    assert detail.status_code == 200
    assert detail.json()["messages"][0]["content"] == "Synthetic paid order is still pending."
    assert detail.json()["evidence"] == []
    assert detail.json()["latest_run"] is None
    assert "checkpoint" not in detail.text.lower()
    assert "reasoning" not in detail.text.lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"content": "More context"},
        {"content": "More context", "attachment_references": []},
    ],
)
def test_message_omitted_or_empty_attachments_take_message_only_path(
    settings: Settings, payload: dict[str, object]
) -> None:
    client, repository, resume_port = build_client(settings)
    token = login(client, "customer@example.test")
    ticket = create_ticket(client, token)

    response = client.post(
        f"/api/v1/tickets/{ticket['ticket_id']}/messages",
        headers=auth_headers(token, f"message-{uuid4()}"),
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["resume_attempted"] is False
    assert set(response.json()) == {
        "message_id",
        "ticket_id",
        "ticket_status",
        "resume_attempted",
        "correlation_id",
    }
    assert len(repository.messages[UUID(ticket["ticket_id"])]) == 2
    assert resume_port.calls == 0


def test_non_empty_attachment_is_exact_rejection_before_any_side_effect(
    settings: Settings,
) -> None:
    client, repository, resume_port = build_client(settings, rate_limit=1)
    token = login(client, "customer@example.test")
    ticket = create_ticket(client, token)
    ticket_id = UUID(ticket["ticket_id"])
    before = list(repository.messages[ticket_id])

    rejected = client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=auth_headers(token, "attachment-key"),
        json={"content": "See this", "attachment_references": ["https://invalid.test/a"]},
    )
    accepted = client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=auth_headers(token, "attachment-key"),
        json={"content": "See this", "attachment_references": []},
    )

    assert rejected.status_code == 422
    assert rejected.json()["code"] == "ATTACHMENTS_NOT_SUPPORTED"
    assert rejected.json()["retryable"] is False
    assert rejected.json()["details"] == {"supported_from": "v1.0"}
    assert accepted.status_code == 201
    assert repository.messages[ticket_id][:-1] == before
    assert len(repository.messages[ticket_id]) == len(before) + 1
    assert resume_port.calls == 0


def test_waiting_customer_message_resumes_same_run_once_and_replays_exact_result(
    settings: Settings,
) -> None:
    run_id = uuid4()
    approval_id = uuid4()
    resume_port = MemoryResumePort(
        ResumeOutcome(
            resumed=True,
            ticket_status="WAITING_APPROVAL",
            run_id=run_id,
            run_status="WAITING_APPROVAL",
            next_required_action="approval",
            approval_request_id=approval_id,
            timeline_cursor="opaque-cursor",
        )
    )
    client, repository, _ = build_client(settings, resume_port=resume_port)
    token = login(client, "customer@example.test")
    ticket = create_ticket(client, token)
    ticket_id = UUID(ticket["ticket_id"])
    repository.tickets[ticket_id] = replace(
        repository.tickets[ticket_id], status="WAITING_CUSTOMER"
    )
    headers = auth_headers(token, "resume-once")
    payload = {"content": "The synthetic order was yesterday", "attachment_references": []}

    first = client.post(f"/api/v1/tickets/{ticket_id}/messages", headers=headers, json=payload)
    replay = client.post(f"/api/v1/tickets/{ticket_id}/messages", headers=headers, json=payload)

    assert first.status_code == replay.status_code == 200
    first_body = first.json()
    replay_body = replay.json()
    first_body.pop("correlation_id")
    replay_body.pop("correlation_id")
    assert first_body == replay_body
    assert first.json()["run_id"] == str(run_id)
    assert first.json()["approval_request_id"] == str(approval_id)
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert resume_port.calls == 1
    assert len(repository.messages[ticket_id]) == 2


def test_missing_resume_invariant_keeps_message_and_escalates(settings: Settings) -> None:
    client, repository, resume_port = build_client(settings)
    token = login(client, "customer@example.test")
    ticket = create_ticket(client, token)
    ticket_id = UUID(ticket["ticket_id"])
    repository.tickets[ticket_id] = replace(
        repository.tickets[ticket_id], status="WAITING_CUSTOMER"
    )

    response = client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=auth_headers(token, "missing-checkpoint"),
        json={"content": "Synthetic clarification"},
    )

    assert response.status_code == 200
    assert response.json()["resume_attempted"] is False
    assert response.json()["ticket_status"] == "ESCALATED"
    assert repository.tickets[ticket_id].status == "ESCALATED"
    assert len(repository.messages[ticket_id]) == 2
    assert resume_port.calls == 1


def test_message_idempotency_conflict_and_write_rate_limit_are_enforced(
    settings: Settings,
) -> None:
    client, _, _ = build_client(settings, rate_limit=1)
    token = login(client, "customer@example.test")
    ticket = create_ticket(client, token)
    path = f"/api/v1/tickets/{ticket['ticket_id']}/messages"
    headers = auth_headers(token, "same-message-key")

    first = client.post(path, headers=headers, json={"content": "Original context"})
    conflict = client.post(path, headers=headers, json={"content": "Changed context"})
    limited = client.post(
        path,
        headers=auth_headers(token, "another-message-key"),
        json={"content": "Another context"},
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "REQUEST_VALIDATION_ERROR"
    assert limited.status_code == 429
    assert limited.json()["code"] == "FORBIDDEN"
    assert limited.headers["Retry-After"] == "60"


def test_resume_timeout_keeps_message_escalates_and_does_not_retry_resume(
    settings: Settings,
) -> None:
    run_id = uuid4()
    timeout_port = TimeoutResumePort(run_id)
    client, repository, _ = build_client(settings, resume_port=timeout_port)
    token = login(client, "customer@example.test")
    ticket = create_ticket(client, token)
    ticket_id = UUID(ticket["ticket_id"])
    repository.tickets[ticket_id] = replace(
        repository.tickets[ticket_id], status="WAITING_CUSTOMER"
    )
    headers = auth_headers(token, "timeout-key")
    payload = {"content": "Synthetic timeout clarification"}

    first = client.post(f"/api/v1/tickets/{ticket_id}/messages", headers=headers, json=payload)
    replay = client.post(f"/api/v1/tickets/{ticket_id}/messages", headers=headers, json=payload)

    assert first.status_code == replay.status_code == 504
    assert first.json()["code"] == "WORKFLOW_REQUEST_TIMEOUT"
    assert first.json()["details"] == {
        "ticket_id": str(ticket_id),
        "message_id": str(repository.messages[ticket_id][-1].id),
        "run_id": str(run_id),
    }
    assert repository.tickets[ticket_id].status == "ESCALATED"
    assert len(repository.messages[ticket_id]) == 2
    assert timeout_port.calls == 1
