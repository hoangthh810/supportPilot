"""Container-level smoke checks for the internal Bearer authentication boundary."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: dict[str, object]


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required")
    return value


def request_json(url: str, authorization: str | None = None) -> HttpResult:
    headers = {"X-Correlation-ID": "corr_mock-auth-smoke"}
    if authorization is not None:
        headers["Authorization"] = authorization
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return HttpResult(response.status, json.loads(response.read()))
    except urllib.error.HTTPError as error:
        return HttpResult(error.code, json.loads(error.read()))


def main() -> None:
    base_url = required_environment("MOCK_COMMERCE_SMOKE_BASE_URL").rstrip("/")
    token = required_environment("INTERNAL_SERVICE_TOKEN")
    internal_url = f"{base_url}/internal/v1/not-yet-implemented"

    health = request_json(f"{base_url}/health")
    missing = request_json(internal_url)
    malformed = request_json(internal_url, "Basic malformed")
    wrong = request_json(internal_url, "Bearer wrong-service-token")
    user_jwt = request_json(internal_url, "Bearer user.jwt.access-token")
    valid = request_json(internal_url, f"Bearer {token}")

    assert health.status == 200
    assert (missing.status, missing.body["code"]) == (401, "INTERNAL_UNAUTHENTICATED")
    assert (malformed.status, malformed.body["code"]) == (
        401,
        "INTERNAL_UNAUTHENTICATED",
    )
    assert (wrong.status, wrong.body["code"]) == (403, "INTERNAL_FORBIDDEN")
    assert (user_jwt.status, user_jwt.body["code"]) == (403, "INTERNAL_FORBIDDEN")
    assert valid.status == 404
    rendered = json.dumps(
        {
            "health": health.status,
            "missing": missing.status,
            "malformed": malformed.status,
            "wrong": wrong.status,
            "user_jwt": user_jwt.status,
            "valid_reached_router": valid.status == 404,
        },
        sort_keys=True,
    )
    assert token not in rendered
    print(rendered)


if __name__ == "__main__":
    main()
