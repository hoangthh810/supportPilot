from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.apps.support_api.auth.contracts import AuthUser


class PostgresAuthRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT user_row.id, user_row.email::text, user_row.password_hash,
                               user_row.role::text, user_row.status::text,
                               customer.id AS customer_id
                        FROM support.users AS user_row
                        LEFT JOIN support.customers AS customer
                          ON customer.user_id = user_row.id
                         AND customer.status = 'ACTIVE'
                        WHERE user_row.email = :email
                        """
                    ),
                    {"email": email},
                )
            ).mappings().one_or_none()
        return self._user(row)

    async def find_user_by_id(self, user_id: UUID) -> AuthUser | None:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT user_row.id, user_row.email::text, user_row.password_hash,
                               user_row.role::text, user_row.status::text,
                               customer.id AS customer_id
                        FROM support.users AS user_row
                        LEFT JOIN support.customers AS customer
                          ON customer.user_id = user_row.id
                         AND customer.status = 'ACTIVE'
                        WHERE user_row.id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
            ).mappings().one_or_none()
        return self._user(row)

    async def record_successful_login(self, user_id: UUID) -> bool:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE support.users
                    SET last_login_at = now(), updated_at = now()
                    WHERE id = :user_id AND status = 'ACTIVE'
                    """
                ),
                {"user_id": user_id},
            )
        return result.rowcount == 1

    @staticmethod
    def _user(row: object | None) -> AuthUser | None:
        if row is None:
            return None
        mapping = row  # SQLAlchemy RowMapping at runtime.
        return AuthUser(
            id=mapping["id"],  # type: ignore[index]
            email=mapping["email"],  # type: ignore[index]
            password_hash=mapping["password_hash"],  # type: ignore[index]
            role=mapping["role"],  # type: ignore[index]
            status=mapping["status"],  # type: ignore[index]
            customer_id=mapping["customer_id"],  # type: ignore[index]
        )
