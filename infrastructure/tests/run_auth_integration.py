"""Real PostgreSQL and HTTP checks for AUTH-001."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BASE_URL = os.environ.get("AUTH_BASE_URL", "http://backend:8000/api/v1").rstrip("/")
CUSTOMER_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000201")


@dataclass(frozen=True, slots=True)
class HttpResult:
    status: int
    body: dict[str, Any]
    headers: dict[str, str]


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> HttpResult:
    headers = {
        "Accept": "application/json",
        "X-Correlation-ID": f"corr_auth-e2e-{uuid4()}",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    raw = None if payload is None else json.dumps(payload).encode()
    http_request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=raw,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(http_request, timeout=15) as response:
            return HttpResult(
                status=response.status,
                body=json.loads(response.read()),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as error:
        return HttpResult(
            status=error.code,
            body=json.loads(error.read()),
            headers={key.lower(): value for key, value in error.headers.items()},
        )


def login(email: str, password: str) -> HttpResult:
    return request(
        "POST",
        "/auth/login",
        payload={"email": email, "password": password},
    )


async def set_customer_status(status: str) -> None:
    engine = create_async_engine(os.environ["SUPPORT_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE support.users
                    SET status = CAST(:status AS support.account_status), updated_at = now()
                    WHERE id = :user_id
                    """
                ),
                {"status": status, "user_id": CUSTOMER_USER_ID},
            )
    finally:
        await engine.dispose()


async def assert_database_login_state() -> None:
    engine = create_async_engine(os.environ["SUPPORT_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT user_row.password_hash, user_row.last_login_at,
                               customer.id AS customer_id
                        FROM support.users AS user_row
                        JOIN support.customers AS customer ON customer.user_id = user_row.id
                        WHERE user_row.id = :user_id
                        """
                    ),
                    {"user_id": CUSTOMER_USER_ID},
                )
            ).mappings().one()
            assert row["password_hash"].startswith("$argon2")
            assert row["last_login_at"] is not None
            assert row["customer_id"] == CUSTOMER_ID
    finally:
        await engine.dispose()


def assert_error(result: HttpResult, *, status: int, code: str) -> None:
    assert result.status == status, result
    assert result.body["code"] == code, result
    assert result.body["retryable"] is False
    assert result.body["details"] == {}
    assert result.body["correlation_id"].startswith("corr_auth-e2e-")


def main() -> None:
    missing = request("GET", "/auth/me")
    assert_error(missing, status=401, code="UNAUTHENTICATED")

    unknown = login("unknown-auth@example.test", "wrong-password")
    wrong = login("customer@example.test", "wrong-password")
    assert_error(unknown, status=401, code="INVALID_CREDENTIALS")
    assert_error(wrong, status=401, code="INVALID_CREDENTIALS")
    assert unknown.body["message"] == wrong.body["message"]

    customer_login = login("CUSTOMER@example.test", "demo-password")
    assert customer_login.status == 200
    assert customer_login.body["token_type"] == "Bearer"
    assert customer_login.body["expires_in_seconds"] == 900
    assert customer_login.body["actor"] == {
        "id": str(CUSTOMER_USER_ID),
        "role": "customer",
        "status": "active",
    }
    assert customer_login.headers["x-ratelimit-limit"] == "10"
    customer_token = str(customer_login.body["access_token"])

    me = request("GET", "/auth/me", token=customer_token)
    assert me.status == 200
    assert me.body["actor"] == customer_login.body["actor"]
    assert me.body["customer_id"] == str(CUSTOMER_ID)
    asyncio.run(assert_database_login_state())

    tampered = request("GET", "/auth/me", token=f"{customer_token}tampered")
    assert_error(tampered, status=401, code="UNAUTHENTICATED")
    assert customer_token not in json.dumps(tampered.body)

    agent_login = login("agent@example.test", "demo-password")
    assert agent_login.status == 200
    agent_me = request("GET", "/auth/me", token=str(agent_login.body["access_token"]))
    assert agent_me.status == 200
    assert agent_me.body["actor"]["role"] == "support_agent"
    assert agent_me.body["customer_id"] is None

    asyncio.run(set_customer_status("DISABLED"))
    try:
        disabled_token = request("GET", "/auth/me", token=customer_token)
        assert_error(disabled_token, status=403, code="ACCOUNT_DISABLED")
        disabled_login = login("customer@example.test", "demo-password")
        assert_error(disabled_login, status=403, code="ACCOUNT_DISABLED")
        disabled_wrong = login("customer@example.test", "still-wrong")
        assert_error(disabled_wrong, status=401, code="INVALID_CREDENTIALS")
    finally:
        asyncio.run(set_customer_status("ACTIVE"))

    for attempt in range(10):
        result = login("rate-limit-auth@example.test", f"wrong-{attempt}")
        assert_error(result, status=401, code="INVALID_CREDENTIALS")
    limited = login("rate-limit-auth@example.test", "wrong-final")
    assert_error(limited, status=429, code="INVALID_CREDENTIALS")
    assert limited.headers["x-ratelimit-remaining"] == "0"
    assert int(limited.headers["retry-after"]) >= 1

    refresh = request("POST", "/auth/refresh", payload={})
    assert refresh.status == 404

    print(
        "AUTH-001 integration passed: login/me, Argon2/last-login, current-state "
        "scope, disabled account, safe JWT errors and 10/minute rate limit."
    )


if __name__ == "__main__":
    main()
