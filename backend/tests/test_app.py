from fastapi import Query
from fastapi.testclient import TestClient

from backend.apps.support_api.app import create_app
from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.core.errors import ApiError


def test_liveness_returns_correlation_envelope(settings: Settings) -> None:
    response = TestClient(create_app(settings)).get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["correlation_id"].startswith("corr_")
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]


def test_valid_client_correlation_id_is_propagated(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/health/ready", headers={"X-Correlation-ID": "corr_client-123"})

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["correlation_id"] == "corr_client-123"
    assert response.headers["X-Correlation-ID"] == "corr_client-123"


def test_invalid_correlation_id_is_replaced(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/health/live", headers={"X-Correlation-ID": "contains spaces"})

    assert response.status_code == 200
    assert response.json()["correlation_id"].startswith("corr_")
    assert response.json()["correlation_id"] != "contains spaces"


def test_health_response_does_not_expose_secrets(settings: Settings) -> None:
    body = TestClient(create_app(settings)).get("/health/ready").text

    for secret in settings.secret_values():
        assert secret not in body


def test_typed_api_error_uses_safe_envelope(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/test/error")
    async def typed_error() -> None:
        raise ApiError(
            status_code=409,
            code="TEST_CONFLICT",
            message="The request conflicts with current state.",
            details={"state": "existing"},
        )

    response = TestClient(app).get(
        "/test/error", headers={"X-Correlation-ID": "corr_error-test"}
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "TEST_CONFLICT",
        "message": "The request conflicts with current state.",
        "retryable": False,
        "correlation_id": "corr_error-test",
        "details": {"state": "existing"},
    }


def test_request_validation_error_omits_input_value(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/test/validate")
    async def validate(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    response = TestClient(app).get("/test/validate?limit=not-a-number")

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_ERROR"
    assert "input" not in str(response.json()["details"])
    assert "traceback" not in response.text.lower()


def test_unhandled_error_is_safe(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/test/unhandled")
    async def unhandled() -> None:
        raise RuntimeError(settings.internal_service_token.get_secret_value())

    response = TestClient(app, raise_server_exceptions=False).get("/test/unhandled")

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert settings.internal_service_token.get_secret_value() not in response.text
    assert "traceback" not in response.text.lower()

