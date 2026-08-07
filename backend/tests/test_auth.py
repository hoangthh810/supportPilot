from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from pwdlib import PasswordHash

from backend.apps.support_api.app import create_app
from backend.apps.support_api.auth.contracts import AuthenticatedActor, AuthUser
from backend.apps.support_api.auth.dependencies import require_roles
from backend.apps.support_api.auth.rate_limit import LoginRateLimiter
from backend.apps.support_api.auth.service import AuthService
from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.core.errors import ApiError
from backend.tests.conftest import valid_settings_data

CUSTOMER_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
CUSTOMER_ID = UUID("00000000-0000-4000-8000-000000000201")
AGENT_USER_ID = UUID("00000000-0000-4000-8000-000000000102")
ADMIN_USER_ID = UUID("00000000-0000-4000-8000-000000000103")
DISABLED_USER_ID = UUID("00000000-0000-4000-8000-000000000104")


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
            "agent@example.test": AuthUser(
                AGENT_USER_ID,
                "agent@example.test",
                password_hash,
                "SUPPORT_AGENT",
                "ACTIVE",
                None,
            ),
            "admin@example.test": AuthUser(
                ADMIN_USER_ID,
                "admin@example.test",
                password_hash,
                "ADMIN",
                "ACTIVE",
                None,
            ),
            "disabled@example.test": AuthUser(
                DISABLED_USER_ID,
                "disabled@example.test",
                password_hash,
                "CUSTOMER",
                "DISABLED",
                CUSTOMER_ID,
            ),
        }
        self.successful_logins: list[UUID] = []

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        return self.users.get(email)

    async def find_user_by_id(self, user_id: UUID) -> AuthUser | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def record_successful_login(self, user_id: UUID) -> bool:
        user = await self.find_user_by_id(user_id)
        if user is None or user.status != "ACTIVE":
            return False
        self.successful_logins.append(user_id)
        return True

    def set_status(self, email: str, status: str) -> None:
        user = self.users[email]
        self.users[email] = AuthUser(
            user.id,
            user.email,
            user.password_hash,
            user.role,
            status,
            user.customer_id,
        )

    def set_role(self, email: str, role: str, customer_id: UUID | None) -> None:
        user = self.users[email]
        self.users[email] = AuthUser(
            user.id,
            user.email,
            user.password_hash,
            role,
            user.status,
            customer_id,
        )

    def set_customer_id(self, email: str, customer_id: UUID | None) -> None:
        user = self.users[email]
        self.users[email] = AuthUser(
            user.id,
            user.email,
            user.password_hash,
            user.role,
            user.status,
            customer_id,
        )


def auth_settings(*, limit: int = 10) -> Settings:
    data = valid_settings_data()
    data["AUTH_RATE_LIMIT_PER_MINUTE"] = limit
    return Settings(**data)  # type: ignore[arg-type]


def build_client(
    *, limit: int = 10
) -> tuple[TestClient, MemoryAuthRepository, Settings, AuthService]:
    settings = auth_settings(limit=limit)
    repository = MemoryAuthRepository()
    service = AuthService(settings=settings, repository=repository)
    return TestClient(create_app(settings, auth_service=service)), repository, settings, service


def login(
    client: TestClient,
    *,
    email: str = "customer@example.test",
    password: str = "demo-password",
) -> Response:
    return cast(
        Response,
        client.post("/api/v1/auth/login", json={"email": email, "password": password}),
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_exact_access_token_contract_and_updates_login_state() -> None:
    client, repository, settings, _ = build_client()

    response = login(client, email=" Customer@Example.Test ")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in_seconds"] == 900
    assert body["actor"] == {
        "id": str(CUSTOMER_USER_ID),
        "role": "customer",
        "status": "active",
    }
    assert body["correlation_id"].startswith("corr_")
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "9"
    assert repository.successful_logins == [CUSTOMER_USER_ID]

    claims = jwt.decode(
        body["access_token"],
        settings.jwt_signing_key.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
    )
    assert claims["sub"] == str(CUSTOMER_USER_ID)
    assert claims["role"] == "customer"
    assert claims["exp"] - claims["iat"] == 900
    assert "status" not in claims
    assert "customer_id" not in claims


def test_auth_me_reads_current_database_principal_and_customer_scope() -> None:
    client, _, _, _ = build_client()
    token = login(client).json()["access_token"]

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {
        "actor": {
            "id": str(CUSTOMER_USER_ID),
            "role": "customer",
            "status": "active",
        },
        "customer_id": str(CUSTOMER_ID),
        "correlation_id": response.json()["correlation_id"],
    }


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer malformed"}],
)
def test_auth_me_rejects_missing_or_invalid_bearer(headers: dict[str, str]) -> None:
    client, _, _, _ = build_client()

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert response.json()["retryable"] is False


@pytest.mark.parametrize("claim_change", ["expired", "wrong_issuer", "unknown_role"])
def test_auth_me_validates_expiry_issuer_and_role_claim(claim_change: str) -> None:
    client, _, settings, _ = build_client()
    now = datetime.now(UTC)
    claims = {
        "sub": str(CUSTOMER_USER_ID),
        "role": "customer",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": "auth-test-token",
    }
    if claim_change == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif claim_change == "wrong_issuer":
        claims["iss"] = "wrong-issuer"
    else:
        claims["role"] = "superuser"
    token = jwt.encode(
        claims,
        settings.jwt_signing_key.get_secret_value(),
        algorithm="HS256",
    )

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_disabled_account_is_checked_at_login_and_after_token_issue() -> None:
    client, repository, _, _ = build_client()

    wrong_password = login(
        client,
        email="disabled@example.test",
        password="wrong-password",
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["code"] == "INVALID_CREDENTIALS"

    disabled_login = login(client, email="disabled@example.test")
    assert disabled_login.status_code == 403
    assert disabled_login.json()["code"] == "ACCOUNT_DISABLED"

    token = login(client).json()["access_token"]
    repository.set_status("customer@example.test", "DISABLED")
    protected = client.get("/api/v1/auth/me", headers=bearer(token))
    assert protected.status_code == 403
    assert protected.json()["code"] == "ACCOUNT_DISABLED"


def test_role_change_invalidates_existing_token() -> None:
    client, repository, _, _ = build_client()
    token = login(client).json()["access_token"]
    repository.set_role("customer@example.test", "SUPPORT_AGENT", None)

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_router_and_service_role_checks_return_contract_forbidden() -> None:
    client, _, _, service = build_client()

    app = cast(FastAPI, client.app)

    @app.get("/test/admin-only")
    async def admin_only(
        actor: Annotated[AuthenticatedActor, Depends(require_roles("admin"))],
    ) -> dict[str, str]:
        return {"role": actor.role}

    customer_token = login(client).json()["access_token"]
    denied = client.get("/test/admin-only", headers=bearer(customer_token))
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"

    admin_token = login(client, email="admin@example.test").json()["access_token"]
    allowed = client.get("/test/admin-only", headers=bearer(admin_token))
    assert allowed.status_code == 200
    assert allowed.json() == {"role": "admin"}

    with pytest.raises(ApiError) as error:
        service.require_roles(
            AuthenticatedActor(CUSTOMER_USER_ID, "customer", "active", CUSTOMER_ID),
            frozenset({"admin"}),
        )
    assert error.value.code == "FORBIDDEN"


def test_login_rate_limit_uses_generic_contract_and_safe_headers() -> None:
    client, _, _, _ = build_client(limit=2)

    first = login(client, email="unknown@example.test", password="not-the-password")
    second = login(client, email="unknown@example.test", password="not-the-password")
    limited = login(client, email="unknown@example.test", password="not-the-password")

    assert first.status_code == second.status_code == 401
    assert first.json()["code"] == second.json()["code"] == "INVALID_CREDENTIALS"
    assert limited.status_code == 429
    assert limited.json()["code"] == "INVALID_CREDENTIALS"
    assert limited.json()["message"] == first.json()["message"]
    assert limited.headers["X-RateLimit-Remaining"] == "0"
    assert int(limited.headers["Retry-After"]) >= 1


def test_login_rate_limiter_bounds_identity_memory_and_releases_expired_keys() -> None:
    now = [0.0]
    limiter = LoginRateLimiter(
        limit=1,
        window_seconds=60,
        max_tracked_identities=1,
        clock=lambda: now[0],
    )
    async def scenario() -> int:
        await limiter.consume(
            client_identity="client-a",
            normalized_email="a@example.test",
        )
        with pytest.raises(ApiError) as limited:
            await limiter.consume(
                client_identity="client-b",
                normalized_email="b@example.test",
            )
        assert limited.value.status_code == 429
        assert limited.value.code == "INVALID_CREDENTIALS"

        now[0] = 61.0
        released = await limiter.consume(
            client_identity="client-b",
            normalized_email="b@example.test",
        )
        return released.remaining

    assert asyncio.run(scenario()) == 0


def test_login_failures_do_not_expose_password_hash_token_or_account_existence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, repository, _, _ = build_client()
    supplied_password = "supplied-secret-password"

    unknown = login(
        client,
        email="unknown@example.test",
        password=supplied_password,
    )
    wrong = login(
        client,
        email="customer@example.test",
        password=supplied_password,
    )

    for response in (unknown, wrong):
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"
        assert response.json()["message"] == "The email or password is invalid."
        assert supplied_password not in response.text
        assert "access_token" not in response.text
    password_hash = repository.users["customer@example.test"].password_hash
    assert password_hash not in caplog.text
    assert supplied_password not in caplog.text


def test_customer_without_active_scope_is_forbidden_after_token_issue() -> None:
    client, repository, _, _ = build_client()
    token = login(client).json()["access_token"]
    repository.set_customer_id("customer@example.test", None)

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
