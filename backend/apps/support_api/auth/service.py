from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from backend.apps.support_api.auth.contracts import (
    AuthenticatedActor,
    AuthRepository,
    AuthUser,
    LoginResult,
)
from backend.apps.support_api.auth.rate_limit import LoginRateLimiter
from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.core.errors import ApiError

ALLOWED_ROLES = frozenset({"customer", "support_agent", "support_manager", "admin"})


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: AuthRepository,
        rate_limiter: LoginRateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._password_hash = PasswordHash.recommended()
        self._dummy_password_hash = self._password_hash.hash("supportpilot-dummy-password")
        self._rate_limiter = rate_limiter or LoginRateLimiter(
            limit=settings.auth_rate_limit_per_minute
        )

    async def login(self, *, email: str, password: str, client_identity: str) -> LoginResult:
        normalized_email = email.strip().lower()
        rate_limit = await self._rate_limiter.consume(
            client_identity=client_identity,
            normalized_email=normalized_email,
        )
        headers = rate_limit.headers()
        user = await self._repository.find_user_by_email(normalized_email)
        stored_hash = self._dummy_password_hash if user is None else user.password_hash
        try:
            password_matches = self._password_hash.verify(password, stored_hash)
        except Exception as error:
            raise self._invalid_credentials(headers=headers) from error
        if user is None or not password_matches:
            raise self._invalid_credentials(headers=headers)
        if user.status != "ACTIVE":
            raise self._account_disabled(headers=headers)

        actor = self._actor_from_user(user)
        if actor.role == "customer" and actor.customer_id is None:
            raise self._invalid_credentials(headers=headers)
        if not await self._repository.record_successful_login(user.id):
            raise self._account_disabled(headers=headers)

        expires_in_seconds = self._settings.access_token_ttl_minutes * 60
        now = datetime.now(UTC)
        access_token = jwt.encode(
            {
                "sub": str(actor.id),
                "role": actor.role,
                "iss": self._settings.jwt_issuer,
                "iat": now,
                "exp": now + timedelta(seconds=expires_in_seconds),
                "jti": str(uuid4()),
            },
            self._settings.jwt_signing_key.get_secret_value(),
            algorithm="HS256",
        )
        return LoginResult(
            access_token=access_token,
            expires_in_seconds=expires_in_seconds,
            actor=actor,
            rate_limit_headers=headers,
        )

    async def authenticate(self, token: str) -> AuthenticatedActor:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.jwt_signing_key.get_secret_value(),
                algorithms=["HS256"],
                issuer=self._settings.jwt_issuer,
                options={"require": ["sub", "role", "iat", "exp", "iss", "jti"]},
            )
            user_id = UUID(str(payload["sub"]))
            token_role = str(payload["role"])
            if token_role not in ALLOWED_ROLES:
                raise ValueError("invalid role claim")
        except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise self._unauthenticated() from error

        user = await self._repository.find_user_by_id(user_id)
        if user is None:
            raise self._unauthenticated()
        if user.status != "ACTIVE":
            raise self._account_disabled()
        actor = self._actor_from_user(user)
        if actor.role != token_role:
            raise self._unauthenticated()
        if actor.role == "customer" and actor.customer_id is None:
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message="The authenticated actor cannot perform this operation.",
            )
        return actor

    @staticmethod
    def require_roles(
        actor: AuthenticatedActor, allowed_roles: frozenset[str]
    ) -> AuthenticatedActor:
        if actor.status != "active" or actor.role not in allowed_roles:
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message="The authenticated actor cannot perform this operation.",
            )
        return actor

    @staticmethod
    def _actor_from_user(user: AuthUser) -> AuthenticatedActor:
        role = user.role.lower()
        if role not in ALLOWED_ROLES:
            raise ApiError(
                status_code=401,
                code="UNAUTHENTICATED",
                message="A valid access token is required.",
            )
        return AuthenticatedActor(
            id=user.id,
            role=role,
            status=user.status.lower(),
            customer_id=user.customer_id,
        )

    @staticmethod
    def _invalid_credentials(*, headers: dict[str, str]) -> ApiError:
        return ApiError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="The email or password is invalid.",
            headers=headers,
        )

    @staticmethod
    def _account_disabled(*, headers: dict[str, str] | None = None) -> ApiError:
        return ApiError(
            status_code=403,
            code="ACCOUNT_DISABLED",
            message="The account is disabled.",
            headers=headers,
        )

    @staticmethod
    def _unauthenticated() -> ApiError:
        return ApiError(
            status_code=401,
            code="UNAUTHENTICATED",
            message="A valid access token is required.",
        )
