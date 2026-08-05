from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    DEMO = "demo"


class WorkflowProfile(StrEnum):
    V0_1 = "v0_1"
    WALKING_SKELETON = "walking_skeleton"


class LlmProvider(StrEnum):
    GEMINI = "gemini"
    OPENAI = "openai"
    OLLAMA = "ollama"
    FAKE = "fake"


class EmbeddingProvider(StrEnum):
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    FAKE = "fake"


class Settings(BaseSettings):
    """Typed settings accepted by the SupportPilot backend runtime only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    app_env: AppEnvironment = Field(alias="APP_ENV")
    app_name: str = Field(alias="APP_NAME", min_length=1)
    api_host: str = Field(alias="API_HOST", min_length=1)
    api_port: int = Field(alias="API_PORT", ge=1, le=65535)
    frontend_origin: AnyHttpUrl = Field(alias="FRONTEND_ORIGIN")
    correlation_header: Literal["X-Correlation-ID"] = Field(alias="CORRELATION_HEADER")

    workflow_request_timeout_seconds: int = Field(
        alias="WORKFLOW_REQUEST_TIMEOUT_SECONDS", ge=1
    )
    workflow_finalization_reserve_seconds: int = Field(
        alias="WORKFLOW_FINALIZATION_RESERVE_SECONDS", ge=1
    )
    workflow_profile: WorkflowProfile = Field(alias="WORKFLOW_PROFILE")

    support_database_url: SecretStr = Field(alias="SUPPORT_DATABASE_URL")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE", ge=1)
    db_pool_timeout_seconds: int = Field(default=5, alias="DB_POOL_TIMEOUT_SECONDS", ge=1)

    jwt_signing_key: SecretStr = Field(alias="JWT_SIGNING_KEY")
    jwt_issuer: str = Field(alias="JWT_ISSUER", min_length=1)
    access_token_ttl_minutes: int = Field(alias="ACCESS_TOKEN_TTL_MINUTES", ge=1)
    password_hash_scheme: Literal["argon2"] = Field(alias="PASSWORD_HASH_SCHEME")
    auth_rate_limit_per_minute: int = Field(alias="AUTH_RATE_LIMIT_PER_MINUTE", ge=1)

    llm_provider: LlmProvider = Field(alias="LLM_PROVIDER")
    gemini_model: str = Field(alias="GEMINI_MODEL", min_length=1)
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    llm_timeout_seconds: int = Field(alias="LLM_TIMEOUT_SECONDS", ge=1)
    llm_structured_output_max_attempts: int = Field(
        alias="LLM_STRUCTURED_OUTPUT_MAX_ATTEMPTS", ge=1
    )
    llm_max_tokens_per_run: int = Field(alias="LLM_MAX_TOKENS_PER_RUN", ge=1)
    openai_model: str | None = Field(default=None, alias="OPENAI_MODEL")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    ollama_base_url: AnyHttpUrl | None = Field(default=None, alias="OLLAMA_BASE_URL")
    ollama_model: str | None = Field(default=None, alias="OLLAMA_MODEL")

    embedding_provider: EmbeddingProvider = Field(alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(alias="EMBEDDING_MODEL", min_length=1)
    embedding_revision: str = Field(alias="EMBEDDING_REVISION", min_length=1)
    embedding_dimension: int = Field(alias="EMBEDDING_DIMENSION", ge=1)
    embedding_input_format_version: str = Field(
        alias="EMBEDDING_INPUT_FORMAT_VERSION", min_length=1
    )
    embedding_device: Literal["cpu"] = Field(alias="EMBEDDING_DEVICE")
    embedding_normalize: bool = Field(alias="EMBEDDING_NORMALIZE")

    rag_chunk_tokens: int = Field(alias="RAG_CHUNK_TOKENS", ge=1)
    rag_chunk_overlap: int = Field(alias="RAG_CHUNK_OVERLAP", ge=0)
    rag_top_k_candidates: int = Field(alias="RAG_TOP_K_CANDIDATES", ge=1)
    rag_top_k: int = Field(alias="RAG_TOP_K", ge=1)
    rrf_k: int = Field(alias="RRF_K", ge=1)
    rag_min_similarity: float = Field(alias="RAG_MIN_SIMILARITY", ge=-1, le=1)
    rag_min_lexical_confidence: str | None = Field(
        default=None, alias="RAG_MIN_LEXICAL_CONFIDENCE"
    )
    rag_threshold_calibrated: bool = Field(alias="RAG_THRESHOLD_CALIBRATED")

    knowledge_reindex_timeout_seconds: int = Field(
        alias="KNOWLEDGE_REINDEX_TIMEOUT_SECONDS", ge=1
    )
    approval_ttl_hours: int = Field(alias="APPROVAL_TTL_HOURS", ge=1)
    all_business_writes_require_approval: bool = Field(
        alias="ALL_BUSINESS_WRITES_REQUIRE_APPROVAL"
    )

    mock_commerce_base_url: AnyHttpUrl = Field(alias="MOCK_COMMERCE_BASE_URL")
    internal_service_token: SecretStr = Field(alias="INTERNAL_SERVICE_TOKEN")
    default_currency: str = Field(alias="DEFAULT_CURRENCY", pattern=r"^[A-Z]{3}$")

    allowed_upload_types: Literal["text/markdown"] = Field(alias="ALLOWED_UPLOAD_TYPES")
    max_upload_mb: int = Field(alias="MAX_UPLOAD_MB", ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        alias="LOG_LEVEL"
    )
    log_format: Literal["json"] = Field(alias="LOG_FORMAT")
    request_rate_limit_per_minute: int = Field(
        alias="REQUEST_RATE_LIMIT_PER_MINUTE", ge=1
    )
    email_backend: Literal["draft_only"] = Field(alias="EMAIL_BACKEND")

    @field_validator("support_database_url")
    @classmethod
    def support_database_uses_runtime_role(cls, value: SecretStr) -> SecretStr:
        database_url = value.get_secret_value()
        if "://support_app:" not in database_url:
            raise ValueError("SUPPORT_DATABASE_URL must use the support_app runtime role")
        return value

    @field_validator(
        "gemini_api_key", "openai_api_key", "jwt_signing_key", "internal_service_token"
    )
    @classmethod
    def secrets_must_not_be_empty(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("secret values must not be empty")
        return value

    @model_validator(mode="after")
    def validate_runtime_invariants(self) -> Self:
        if not self.all_business_writes_require_approval:
            raise ValueError("ALL_BUSINESS_WRITES_REQUIRE_APPROVAL must be true")
        if self.workflow_finalization_reserve_seconds >= self.workflow_request_timeout_seconds:
            raise ValueError("workflow finalization reserve must be below request timeout")
        if self.llm_provider is LlmProvider.GEMINI and self.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        if self.llm_provider is LlmProvider.OPENAI and (
            not self.openai_model or self.openai_api_key is None
        ):
            raise ValueError(
                "OPENAI_MODEL and OPENAI_API_KEY are required when LLM_PROVIDER=openai"
            )
        if self.llm_provider is LlmProvider.OLLAMA and (
            self.ollama_base_url is None or not self.ollama_model
        ):
            raise ValueError(
                "OLLAMA_BASE_URL and OLLAMA_MODEL are required when LLM_PROVIDER=ollama"
            )
        if self.rag_top_k > self.rag_top_k_candidates:
            raise ValueError("RAG_TOP_K cannot exceed RAG_TOP_K_CANDIDATES")
        if self.embedding_provider is EmbeddingProvider.SENTENCE_TRANSFORMERS:
            expected_embedding = (
                "intfloat/multilingual-e5-small",
                "c007d7ef6fd86656326059b28395a7a03a7c5846",
                384,
                "e5-prefix-v1",
                "cpu",
                True,
            )
            configured_embedding = (
                self.embedding_model,
                self.embedding_revision,
                self.embedding_dimension,
                self.embedding_input_format_version,
                self.embedding_device,
                self.embedding_normalize,
            )
            if configured_embedding != expected_embedding:
                raise ValueError("local embedding configuration must match v0.1 provenance")
        return self

    def secret_values(self) -> tuple[str, ...]:
        values = [
            self.support_database_url.get_secret_value(),
            self.jwt_signing_key.get_secret_value(),
            self.internal_service_token.get_secret_value(),
        ]
        if self.gemini_api_key is not None:
            values.append(self.gemini_api_key.get_secret_value())
        if self.openai_api_key is not None:
            values.append(self.openai_api_key.get_secret_value())
        return tuple(values)


def load_settings() -> Settings:
    """Load settings once at application startup and fail on an invalid contract."""

    return Settings()
