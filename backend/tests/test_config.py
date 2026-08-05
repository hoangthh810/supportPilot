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
