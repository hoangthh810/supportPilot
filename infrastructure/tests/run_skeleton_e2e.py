"""Real PostgreSQL and HTTP smoke for the temporary Walking Skeleton profile."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BASE_URL = os.environ.get("SKELETON_BASE_URL", "http://backend:8000/api/v1").rstrip("/")


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json", "X-Correlation-ID": f"corr_e2e-{uuid4()}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    raw = None if payload is None else json.dumps(payload).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"{BASE_URL}{path}", data=raw, headers=headers, method=method),
            timeout=15,
        ) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise AssertionError(f"{method} {path} failed: {error.code} {error.read()!r}") from error


def login(email: str) -> str:
    response = request(
        "POST",
        "/auth/login",
        payload={"email": email, "password": "demo-password"},
    )
    return str(response["access_token"])


def create_ticket_and_run(customer_token: str, suffix: str) -> tuple[str, dict[str, Any]]:
    ticket_key = f"e2e-ticket-{suffix}-{uuid4()}"
    ticket = request(
        "POST",
        "/tickets",
        token=customer_token,
        idempotency_key=ticket_key,
        payload={
            "subject": f"Synthetic payment mismatch {suffix}",
            "body": "Synthetic customer paid but the order remains pending.",
            "source": "web",
        },
    )
    replay = request(
        "POST",
        "/tickets",
        token=customer_token,
        idempotency_key=ticket_key,
        payload={
            "subject": f"Synthetic payment mismatch {suffix}",
            "body": "Synthetic customer paid but the order remains pending.",
            "source": "web",
        },
    )
    assert replay["ticket_id"] == ticket["ticket_id"]
    run = request(
        "POST",
        f"/tickets/{ticket['ticket_id']}/agent-runs",
        token=customer_token,
        idempotency_key=f"e2e-run-{suffix}-{uuid4()}",
        payload={},
    )
    assert run["run_status"] == "WAITING_APPROVAL"
    return str(ticket["ticket_id"]), run


async def assert_database(approved_ticket: str, rejected_ticket: str) -> None:
    database_url = os.environ["SUPPORT_MIGRATION_DATABASE_URL"]
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        relations = {
            row.relname
            for row in (
                await connection.execute(
                    text(
                        """
                        SELECT relation.relname
                        FROM pg_class AS relation
                        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'support' AND relation.relkind = 'r'
                        """
                    )
                )
            ).all()
        }
        assert relations == {
            "alembic_version",
            "users",
            "customers",
            "support_tickets",
            "ticket_messages",
        }
        enums = {
            row.typname
            for row in (
                await connection.execute(
                    text(
                        """
                        SELECT type_name.typname
                        FROM pg_type AS type_name
                        JOIN pg_namespace AS namespace ON namespace.oid = type_name.typnamespace
                        WHERE namespace.nspname = 'support' AND type_name.typtype = 'e'
                        """
                    )
                )
            ).all()
        }
        assert enums == {
            "user_role",
            "account_status",
            "ticket_source",
            "ticket_priority",
            "ticket_status",
            "message_sender_type",
        }
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT id::text, status::text, resolved_at IS NOT NULL AS has_resolved_at
                    FROM support.support_tickets
                    WHERE id IN (CAST(:approved AS uuid), CAST(:rejected AS uuid))
                    ORDER BY id
                    """
                ),
                {"approved": approved_ticket, "rejected": rejected_ticket},
            )
        ).mappings().all()
        states = {row["id"]: (row["status"], row["has_resolved_at"]) for row in rows}
        assert states[approved_ticket] == ("RESOLVED", True)
        assert states[rejected_ticket] == ("ESCALATED", False)
        message_count = (
            await connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM support.ticket_messages
                    WHERE ticket_id IN (CAST(:approved AS uuid), CAST(:rejected AS uuid))
                    """
                ),
                {"approved": approved_ticket, "rejected": rejected_ticket},
            )
        ).scalar_one()
        assert message_count == 2
    await engine.dispose()


def main() -> None:
    customer_token = login("customer@example.test")
    approved_ticket, approved_run = create_ticket_and_run(customer_token, "approve")
    rejected_ticket, rejected_run = create_ticket_and_run(customer_token, "reject")
    agent_token = login("agent@example.test")

    for decision, run in (("approve", approved_run), ("reject", rejected_run)):
        approval = request(
            "GET",
            f"/approval-requests/{run['approval_request_id']}",
            token=agent_token,
        )
        result = request(
            "POST",
            f"/approval-requests/{run['approval_request_id']}/decision",
            token=agent_token,
            payload={
                "decision": decision,
                "reason": f"Synthetic {decision} smoke.",
                "expected_version": approval["proposal_version"],
                "expected_proposal_hash": approval["proposal_hash"],
                "edited_action": None,
            },
        )
        if decision == "approve":
            assert result["action_execution_status"] == "VERIFIED"
            assert result["ticket_status"] == "RESOLVED"
        else:
            assert result["action_execution_status"] is None
            assert result["ticket_status"] == "ESCALATED"

    asyncio.run(assert_database(approved_ticket, rejected_ticket))
    print("Walking Skeleton E2E passed: approve VERIFIED→RESOLVED; reject→ESCALATED.")


if __name__ == "__main__":
    main()
