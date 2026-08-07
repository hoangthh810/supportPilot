import pytest
from pydantic import ValidationError

from backend.apps.support_api.core.config import LlmProvider, Settings
from backend.tests.conftest import valid_settings_data


def build_settings(data: dict[str, object] | None = None) -> Settings:
    return Settings(**(data or valid_settings_data()))  # type: ignore[arg-type]


def test_missing_required_configuration_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_support_database_must_use_runtime_role() -> None:
    data = valid_settings_data()
    data["SUPPORT_DATABASE_URL"] = (
        "postgresql+asyncpg://support_owner:unsafe@localhost:5432/supportpilot"
    )
    with pytest.raises(ValidationError, match="support_app runtime role"):
        build_settings(data)


def test_access_token_ttl_is_fixed_to_fifteen_minutes() -> None:
    data = valid_settings_data()
    data["ACCESS_TOKEN_TTL_MINUTES"] = 30
    with pytest.raises(ValidationError):
        build_settings(data)


def test_jwt_signing_key_requires_at_least_32_bytes() -> None:
    data = valid_settings_data()
    data["JWT_SIGNING_KEY"] = "too-short"
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        build_settings(data)


def test_gemini_provider_requires_api_key() -> None:
    data = valid_settings_data()
    data["LLM_PROVIDER"] = "gemini"
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        build_settings(data)


def test_gemini_provider_accepts_secret_key() -> None:
    data = valid_settings_data()
    data["LLM_PROVIDER"] = "gemini"
    data["GEMINI_API_KEY"] = "test-gemini-api-key"
    assert build_settings(data).llm_provider is LlmProvider.GEMINI


@pytest.mark.parametrize("provider", ["openai", "ollama"])
def test_alternative_provider_requires_its_own_configuration(provider: str) -> None:
    data = valid_settings_data()
    data["LLM_PROVIDER"] = provider
    with pytest.raises(ValidationError, match=provider.upper()):
        build_settings(data)


def test_finalization_reserve_must_fit_request_budget() -> None:
    data = valid_settings_data()
    data["WORKFLOW_FINALIZATION_RESERVE_SECONDS"] = 60
    with pytest.raises(ValidationError, match="finalization reserve"):
        build_settings(data)


def test_rag_top_k_must_fit_candidate_count() -> None:
    data = valid_settings_data()
    data["RAG_TOP_K"] = 11
    with pytest.raises(ValidationError, match="RAG_TOP_K"):
        build_settings(data)


def test_local_embedding_provenance_is_fixed_for_v0_1() -> None:
    data = valid_settings_data()
    data["EMBEDDING_PROVIDER"] = "sentence_transformers"
    data["EMBEDDING_DIMENSION"] = 768
    with pytest.raises(ValidationError, match="embedding configuration"):
        build_settings(data)


def test_release_profile_rejects_fake_providers() -> None:
    data = valid_settings_data()
    data["WORKFLOW_PROFILE"] = "v0_1"
    with pytest.raises(ValidationError, match="release profile cannot use fake providers"):
        build_settings(data)


def test_secret_values_are_redacted_from_settings_representation(settings: Settings) -> None:
    rendered = repr(settings)
    for secret in settings.secret_values():
        assert secret not in rendered
    assert "**********" in rendered


def test_forbidden_runtime_database_variables_are_not_settings_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMERCE_DATABASE_URL", "postgresql://commerce_app:secret@db/app")
    monkeypatch.setenv("SUPPORT_MIGRATION_DATABASE_URL", "postgresql://support_owner:secret@db/app")
    settings = build_settings()
    assert not hasattr(settings, "commerce_database_url")
    assert not hasattr(settings, "support_migration_database_url")
