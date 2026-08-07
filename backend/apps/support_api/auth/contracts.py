from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: UUID
    email: str
    password_hash: str
    role: str
    status: str
    customer_id: UUID | None


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    id: UUID
    role: str
    status: str
    customer_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    expires_in_seconds: int
    actor: AuthenticatedActor
    rate_limit_headers: dict[str, str]


class AuthRepository(Protocol):
    async def find_user_by_email(self, email: str) -> AuthUser | None: ...

    async def find_user_by_id(self, user_id: UUID) -> AuthUser | None: ...

    async def record_successful_login(self, user_id: UUID) -> bool: ...
