from __future__ import annotations

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MockCommerceSettings(BaseSettings):
    """Secrets and runtime connection owned exclusively by Mock-Commerce."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    commerce_database_url: SecretStr = Field(alias="COMMERCE_DATABASE_URL")
    internal_service_token: SecretStr = Field(alias="INTERNAL_SERVICE_TOKEN")

    @field_validator("commerce_database_url")
    @classmethod
    def commerce_database_uses_runtime_role(cls, value: SecretStr) -> SecretStr:
        if "://commerce_app:" not in value.get_secret_value():
            raise ValueError("COMMERCE_DATABASE_URL must use the commerce_app runtime role")
        return value

    @field_validator("internal_service_token")
    @classmethod
    def internal_service_token_is_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("INTERNAL_SERVICE_TOKEN must not be empty")
        return value

    def secret_values(self) -> tuple[str, ...]:
        return (
            self.commerce_database_url.get_secret_value(),
            self.internal_service_token.get_secret_value(),
        )


def load_mock_commerce_settings() -> MockCommerceSettings:
    return MockCommerceSettings()
