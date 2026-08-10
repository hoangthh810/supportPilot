from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import SecretStr

from backend.apps.support_api.core.config import Settings


@dataclass(frozen=True)
class InternalServiceAuthHeaderProvider:
    """Materialize the service credential only at the HTTP transport boundary."""

    _token: SecretStr = field(repr=False)

    @classmethod
    def from_settings(cls, settings: Settings) -> InternalServiceAuthHeaderProvider:
        return cls(settings.internal_service_token)

    def inject(self, headers: Mapping[str, str] | None = None) -> dict[str, str]:
        outgoing = dict(headers or {})
        if any(name.lower() == "authorization" for name in outgoing):
            raise ValueError("Authorization is owned by the internal HTTP adapter")
        outgoing["Authorization"] = f"Bearer {self._token.get_secret_value()}"
        return outgoing
