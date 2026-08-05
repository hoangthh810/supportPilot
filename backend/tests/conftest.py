from collections.abc import Iterator

import pytest

from backend.apps.support_api.core.config import Settings


def valid_settings_data() -> dict[str, object]:
    return {
        "APP_ENV": "test",
        "APP_NAME": "SupportPilot",
        "API_HOST": "127.0.0.1",
        "API_PORT": 8000,
        "FRONTEND_ORIGIN": "http://localhost:5173",
        "CORRELATION_HEADER": "X-Correlation-ID",
        "WORKFLOW_REQUEST_TIMEOUT_SECONDS": 60,
        "WORKFLOW_FINALIZATION_RESERVE_SECONDS": 5,
        "WORKFLOW_PROFILE": "v0_1",
        "SUPPORT_DATABASE_URL": (
            "postgresql+asyncpg://support_app:test-password@localhost:5432/supportpilot"
        ),
        "DB_POOL_SIZE": 10,
        "DB_POOL_TIMEOUT_SECONDS": 5,
        "JWT_SIGNING_KEY": "test-jwt-signing-key",
        "JWT_ISSUER": "supportpilot",
        "ACCESS_TOKEN_TTL_MINUTES": 15,
        "PASSWORD_HASH_SCHEME": "argon2",
        "AUTH_RATE_LIMIT_PER_MINUTE": 10,
        "LLM_PROVIDER": "fake",
        "GEMINI_MODEL": "gemini-3.6-flash",
        "LLM_TIMEOUT_SECONDS": 12,
        "LLM_STRUCTURED_OUTPUT_MAX_ATTEMPTS": 2,
        "LLM_MAX_TOKENS_PER_RUN": 12000,
        "EMBEDDING_PROVIDER": "fake",
        "EMBEDDING_MODEL": "intfloat/multilingual-e5-small",
        "EMBEDDING_REVISION": "c007d7ef6fd86656326059b28395a7a03a7c5846",
        "EMBEDDING_DIMENSION": 384,
        "EMBEDDING_INPUT_FORMAT_VERSION": "e5-prefix-v1",
        "EMBEDDING_DEVICE": "cpu",
        "EMBEDDING_NORMALIZE": True,
        "RAG_CHUNK_TOKENS": 450,
        "RAG_CHUNK_OVERLAP": 75,
        "RAG_TOP_K_CANDIDATES": 10,
        "RAG_TOP_K": 5,
        "RRF_K": 60,
        "RAG_MIN_SIMILARITY": 0.72,
        "RAG_MIN_LEXICAL_CONFIDENCE": "replace-after-calibration",
        "RAG_THRESHOLD_CALIBRATED": False,
        "KNOWLEDGE_REINDEX_TIMEOUT_SECONDS": 120,
        "APPROVAL_TTL_HOURS": 24,
        "ALL_BUSINESS_WRITES_REQUIRE_APPROVAL": True,
        "MOCK_COMMERCE_BASE_URL": "http://mock-commerce:8080/internal/v1",
        "INTERNAL_SERVICE_TOKEN": "test-internal-service-token",
        "DEFAULT_CURRENCY": "VND",
        "ALLOWED_UPLOAD_TYPES": "text/markdown",
        "MAX_UPLOAD_MB": 2,
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "json",
        "REQUEST_RATE_LIMIT_PER_MINUTE": 60,
        "EMAIL_BACKEND": "draft_only",
    }


@pytest.fixture
def settings() -> Settings:
    return Settings(**valid_settings_data())  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in valid_settings_data():
        monkeypatch.delenv(name, raising=False)
    yield
