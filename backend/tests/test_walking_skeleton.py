from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from backend.apps.support_api.app import create_app
from backend.apps.support_api.auth.contracts import AuthenticatedActor as Actor
from backend.apps.support_api.auth.contracts import AuthUser
from backend.apps.support_api.auth.service import AuthService
from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.walking_skeleton.adapters import (
    FakeActionAdapter,
    FakeAgentAdapter,
    FakeApprovalAdapter,
)
from backend.apps.support_api.walking_skeleton.contracts import TicketRecord
from backend.apps.support_api.walking_skeleton.service import SkeletonService

CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000101")
AGENT_ID = UUID("00000000-0000-4000-8000-000000000102")


class MemoryAuthRepository:
    def __init__(self) -> None:
        password_hash = PasswordHash.recommended().hash("demo-password")
        self.users = {
            "customer@example.test": AuthUser(
                CUSTOMER_ID,
                "customer@example.test",
                password_hash,
                "CUSTOMER",
                "ACTIVE",
                UUID("00000000-0000-4000-8000-000000000201"),
            ),
            "agent@example.test": AuthUser(
                AGENT_ID,
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
        return any(user.id == user_id and user.status == "ACTIVE" for user in self.users.values())


class MemoryTicketRepository:
    def __init__(self) -> None:
        self.tickets: dict[UUID, TicketRecord] = {}
        self.replays: dict[tuple[UUID, str], TicketRecord] = {}

    async def create_ticket(
        self,
        *,
        actor_id: UUID,
        subject: str,
        body: str,
        source: str,
        idempotency_key: str,
    ) -> TicketRecord:
        del body, source
        replay_key = (actor_id, idempotency_key)
        if replay_key in self.replays:
            return self.replays[replay_key]
        ticket_id = uuid4()
        ticket = TicketRecord(
            id=ticket_id,
            ticket_number=f"SP-{ticket_id.hex[:8].upper()}",
            customer_user_id=actor_id,
            subject=subject,
            status="OPEN",
        )
        self.tickets[ticket.id] = ticket
        self.replays[replay_key] = ticket
        return ticket

    async def get_ticket_for_actor(
        self, *, ticket_id: UUID, actor: Actor
    ) -> TicketRecord | None:
        ticket = self.tickets.get(ticket_id)
        if ticket is None or (actor.role == "customer" and ticket.customer_user_id != actor.id):
            return None
        return ticket

    async def set_ticket_status(self, *, ticket_id: UUID, status: str) -> None:
        ticket = self.tickets[ticket_id]
        self.tickets[ticket_id] = TicketRecord(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            customer_user_id=ticket.customer_user_id,
            subject=ticket.subject,
            status=status,
        )


def build_client(settings: Settings) -> tuple[TestClient, MemoryTicketRepository]:
    repository = MemoryTicketRepository()
    auth_service = AuthService(settings=settings, repository=MemoryAuthRepository())
    service = SkeletonService(
        repository=repository,
        agent=FakeAgentAdapter(),
        approval=FakeApprovalAdapter(),
        action=FakeActionAdapter(),
    )
    return TestClient(create_app(settings, service, auth_service)), repository


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "demo-password"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def create_ticket_and_run(client: TestClient, customer_token: str) -> tuple[str, dict[str, str]]:
    headers = {
        "Authorization": f"Bearer {customer_token}",
        "Idempotency-Key": f"ticket-{uuid4()}",
    }
    ticket_response = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "subject": "Payment mismatch",
            "body": "Synthetic paid order is pending.",
            "source": "web",
        },
    )
    assert ticket_response.status_code == 201
    assert ticket_response.json()["ticket_status"] == "OPEN"

    ticket_id = str(ticket_response.json()["ticket_id"])
    run_key = f"run-{uuid4()}"
    run_headers = {
        "Authorization": f"Bearer {customer_token}",
        "Idempotency-Key": run_key,
    }
    run_response = client.post(
        f"/api/v1/tickets/{ticket_id}/agent-runs",
        headers=run_headers,
        json={},
    )
    assert run_response.status_code == 201
    assert run_response.json()["run_status"] == "WAITING_APPROVAL"
    replay = client.post(
        f"/api/v1/tickets/{ticket_id}/agent-runs",
        headers=run_headers,
        json={},
    )
    assert replay.json()["run_id"] == run_response.json()["run_id"]
    return ticket_id, run_response.json()


def test_explicit_run_and_approved_verified_resolution(settings: Settings) -> None:
    client, repository = build_client(settings)
    customer_token = login(client, "customer@example.test")
    ticket_id, run = create_ticket_and_run(client, customer_token)

    conflicting = client.post(
        f"/api/v1/tickets/{ticket_id}/agent-runs",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "Idempotency-Key": "different-run-key",
        },
        json={},
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["code"] == "AGENT_RUN_ALREADY_ACTIVE"

    agent_token = login(client, "agent@example.test")
    approval = client.get(
        f"/api/v1/approval-requests/{run['approval_request_id']}",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert approval.status_code == 200
    decision = client.post(
        f"/api/v1/approval-requests/{run['approval_request_id']}/decision",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "decision": "approve",
            "reason": "Synthetic evidence is sufficient.",
            "expected_version": approval.json()["proposal_version"],
            "expected_proposal_hash": approval.json()["proposal_hash"],
            "edited_action": None,
        },
    )
    assert decision.status_code == 200
    assert decision.json()["action_execution_status"] == "VERIFIED"
    assert decision.json()["ticket_status"] == "RESOLVED"
    assert repository.tickets[UUID(ticket_id)].status == "RESOLVED"


def test_rejection_escalates_without_action(settings: Settings) -> None:
    client, repository = build_client(settings)
    customer_token = login(client, "customer@example.test")
    ticket_id, run = create_ticket_and_run(client, customer_token)
    agent_token = login(client, "agent@example.test")
    approval = client.get(
        f"/api/v1/approval-requests/{run['approval_request_id']}",
        headers={"Authorization": f"Bearer {agent_token}"},
    ).json()
    decision = client.post(
        f"/api/v1/approval-requests/{run['approval_request_id']}/decision",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "decision": "reject",
            "reason": "Synthetic reviewer chose escalation.",
            "expected_version": approval["proposal_version"],
            "expected_proposal_hash": approval["proposal_hash"],
            "edited_action": None,
        },
    )
    assert decision.status_code == 200
    assert decision.json()["action_execution_status"] is None
    assert decision.json()["ticket_status"] == "ESCALATED"
    assert repository.tickets[UUID(ticket_id)].status == "ESCALATED"
