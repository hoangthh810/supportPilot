from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.apps.mock_commerce_api.app import create_mock_commerce_app
from backend.apps.mock_commerce_api.core.config import MockCommerceSettings
from backend.apps.mock_commerce_api.core.logging import RedactingJsonFormatter
from backend.apps.support_api.app import create_app
from backend.apps.support_api.commerce.auth import InternalServiceAuthHeaderProvider
from backend.apps.support_api.core.config import Settings

INTERNAL_TOKEN = "test-internal-service-token"


def mock_settings_data() -> dict[str, object]:
    return {
        "COMMERCE_DATABASE_URL": (
            "postgresql+asyncpg://commerce_app:test-password@postgres:5432/supportpilot"
        ),
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
    }


def mock_settings() -> MockCommerceSettings:
    return MockCommerceSettings(**mock_settings_data())  # type: ignore[arg-type]


def protected_client() -> TestClient:
    app = create_mock_commerce_app(mock_settings())

    @app.get("/internal/v1/test-probe")
    async def probe(request: Request) -> dict[str, Any]:
        return {
            "authenticated": request.state.internal_service_authenticated,
            "correlation_id": request.state.correlation_id,
        }

    return TestClient(app)


def test_missing_internal_token_returns_exact_401_contract() -> None:
    response = protected_client().get(
        "/internal/v1/test-probe",
        headers={"X-Correlation-ID": "corr_internal-missing"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "INTERNAL_UNAUTHENTICATED",
        "message": "A valid internal Bearer token is required.",
        "retryable": False,
        "correlation_id": "corr_internal-missing",
        "details": {},
    }
    assert response.headers["X-Correlation-ID"] == "corr_internal-missing"


@pytest.mark.parametrize(
    "authorization",
    [
        "",
        "Basic credential",
        "Bearer",
        f"bearer {INTERNAL_TOKEN}",
        f"Bearer {INTERNAL_TOKEN} extra",
    ],
)
def test_malformed_internal_authorization_returns_401(authorization: str) -> None:
    response = protected_client().get(
        "/internal/v1/test-probe",
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INTERNAL_UNAUTHENTICATED"
    assert response.json()["retryable"] is False


@pytest.mark.parametrize("credential", ["wrong-service-token", "user.jwt.access-token"])
def test_wrong_token_or_user_jwt_returns_exact_403(credential: str) -> None:
    response = protected_client().get(
        "/internal/v1/test-probe",
        headers={"Authorization": f"Bearer {credential}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INTERNAL_FORBIDDEN"
    assert response.json()["retryable"] is False
    assert credential not in response.text


def test_valid_internal_token_reaches_internal_route() -> None:
    response = protected_client().get(
        "/internal/v1/test-probe",
        headers={
            "Authorization": f"Bearer {INTERNAL_TOKEN}",
            "X-Correlation-ID": "corr_internal-valid",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "correlation_id": "corr_internal-valid",
    }


class InvalidBeforeAuthPayload(BaseModel):
    customer_ref: str


def test_internal_auth_runs_before_body_parsing_and_ownership_lookup() -> None:
    app = create_mock_commerce_app(mock_settings())
    ownership_lookups = 0

    @app.post("/internal/v1/test-order")
    async def order(payload: InvalidBeforeAuthPayload) -> dict[str, str]:
        nonlocal ownership_lookups
        ownership_lookups += 1
        return {"customer_ref": payload.customer_ref}

    client = TestClient(app)
    missing = client.post("/internal/v1/test-order", content=b"not-json")
    wrong = client.post(
        "/internal/v1/test-order",
        content=b"not-json",
        headers={"Authorization": "Bearer wrong-token"},
    )
    valid_but_invalid_body = client.post(
        "/internal/v1/test-order",
        content=b"not-json",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
    )

    assert (missing.status_code, missing.json()["code"]) == (
        401,
        "INTERNAL_UNAUTHENTICATED",
    )
    assert (wrong.status_code, wrong.json()["code"]) == (403, "INTERNAL_FORBIDDEN")
    assert valid_but_invalid_body.status_code == 422
    assert ownership_lookups == 0


def test_no_query_or_body_credential_fallback() -> None:
    client = protected_client()

    query_response = client.get(
        f"/internal/v1/test-probe?internal_service_token={INTERNAL_TOKEN}"
    )
    body_response = client.request(
        "GET",
        "/internal/v1/test-probe",
        json={"internal_service_token": INTERNAL_TOKEN},
    )

    assert query_response.status_code == 401
    assert body_response.status_code == 401


def test_health_is_not_an_internal_authenticated_endpoint() -> None:
    response = TestClient(create_mock_commerce_app(mock_settings())).get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "mock-commerce"
    assert response.json()["correlation_id"].startswith("corr_")


def test_mock_commerce_settings_reject_wrong_role_and_empty_token() -> None:
    wrong_role = mock_settings_data()
    wrong_role["COMMERCE_DATABASE_URL"] = (
        "postgresql+asyncpg://support_app:test-password@postgres:5432/supportpilot"
    )
    with pytest.raises(ValueError, match="commerce_app runtime role"):
        MockCommerceSettings(**wrong_role)  # type: ignore[arg-type]

    empty_token = mock_settings_data()
    empty_token["INTERNAL_SERVICE_TOKEN"] = " "
    with pytest.raises(ValueError, match="must not be empty"):
        MockCommerceSettings(**empty_token)  # type: ignore[arg-type]


def test_mock_commerce_formatter_redacts_service_token_and_bearer_header() -> None:
    settings = mock_settings()
    record = logging.LogRecord(
        name="mock-commerce.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=f"Authorization: Bearer {INTERNAL_TOKEN} token={INTERNAL_TOKEN}",
        args=(),
        exc_info=None,
    )

    rendered = RedactingJsonFormatter(settings.secret_values()).format(record)

    assert INTERNAL_TOKEN not in rendered
    assert "[REDACTED]" in json.loads(rendered)["message"]


def test_support_adapter_injects_exact_header_without_repr_leak(settings: Settings) -> None:
    provider = InternalServiceAuthHeaderProvider.from_settings(settings)

    headers = provider.inject({"X-Correlation-ID": "corr_adapter-test"})

    assert headers == {
        "X-Correlation-ID": "corr_adapter-test",
        "Authorization": f"Bearer {settings.internal_service_token.get_secret_value()}",
    }
    assert settings.internal_service_token.get_secret_value() not in repr(provider)
    with pytest.raises(ValueError, match="owned by the internal HTTP adapter"):
        provider.inject({"authorization": "Bearer caller-controlled"})


def test_internal_token_is_rejected_on_public_api(settings: Settings) -> None:
    token = settings.internal_service_token.get_secret_value()
    response = TestClient(create_app(settings)).post(
        "/api/v1/auth/login",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": "corr_public-isolation",
        },
        json={"email": "customer@example.test", "password": "demo-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "UNAUTHENTICATED",
        "message": "A valid access token is required.",
        "retryable": False,
        "correlation_id": "corr_public-isolation",
        "details": {},
    }
    assert token not in response.text


def test_internal_token_is_absent_from_frontend_and_non_runtime_projections() -> None:
    frontend_files = [
        path
        for path in Path("frontend").rglob("*")
        if path.is_file() and "node_modules" not in path.parts and "dist" not in path.parts
    ]
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in frontend_files
    )
    frontend_runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in frontend_files
        if Path("frontend/src") in path.parents
        and ".test." not in path.name
        and ".spec." not in path.name
    )
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    frontend_block = compose.split("  frontend:", maxsplit=1)[1].split(
        "\nnetworks:", maxsplit=1
    )[0]
    mock_block = compose.split("  mock-commerce:", maxsplit=1)[1].split(
        "\n  backend:", maxsplit=1
    )[0]
    backend_block = compose.split("  backend:", maxsplit=1)[1].split(
        "\n  frontend:", maxsplit=1
    )[0]

    assert "INTERNAL_SERVICE_TOKEN" not in frontend_runtime_text
    assert INTERNAL_TOKEN not in frontend_text
    assert "INTERNAL_SERVICE_TOKEN" not in frontend_block
    assert "--no-access-log" in mock_block
    assert "--no-access-log" in backend_block
    assert "INTERNAL_SERVICE_TOKEN" not in Path(
        "backend/apps/support_api/commerce/auth.py"
    ).read_text(encoding="utf-8")
