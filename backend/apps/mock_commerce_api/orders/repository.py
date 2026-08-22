from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.apps.mock_commerce_api.core.errors import CommerceApiError
from backend.apps.mock_commerce_api.orders.contracts import (
    OrderSearchFilters,
    SyncPaymentResult,
)
from backend.packages.commerce_contracts import (
    OrderDetail,
    OrderItem,
    OrderItemsResponse,
    OrderSearchResponse,
    OrderSummary,
    SyncPaymentRequest,
    SyncPaymentResponse,
)

_OPERATION = "SYNC_PAYMENT_STATUS"
_PROPOSAL_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_ORDER_COLUMNS = """
    o.id, o.order_number, o.status::text AS status,
    o.payment_status::text AS payment_status, o.total_amount,
    o.currency, o.version, o.created_at, o.updated_at
"""


class PostgresOrderRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def search_orders(
        self, *, customer_ref: str, filters: OrderSearchFilters
    ) -> OrderSearchResponse:
        clauses = ["c.external_ref = :customer_ref", "c.status = 'ACTIVE'"]
        parameters: dict[str, Any] = {"customer_ref": customer_ref}
        if filters.created_from is not None:
            clauses.append("o.created_at >= :created_from")
            parameters["created_from"] = filters.created_from
        if filters.created_to is not None:
            clauses.append("o.created_at <= :created_to")
            parameters["created_to"] = filters.created_to
        if filters.status is not None:
            clauses.append("o.status::text = :status")
            parameters["status"] = filters.status
        if filters.product_query is not None:
            clauses.append(
                """
                EXISTS (
                    SELECT 1
                    FROM commerce.order_items AS oi
                    JOIN commerce.products AS p ON p.id = oi.product_id
                    WHERE oi.order_id = o.id
                      AND (p.normalized_name ILIKE :product_query OR p.sku ILIKE :product_query)
                )
                """
            )
            parameters["product_query"] = f"%{filters.product_query.strip()}%"

        async with self._engine.connect() as connection:
            await self._require_customer(connection, customer_ref)
            rows = (
                await connection.execute(
                    text(
                        f"""
                        SELECT {_ORDER_COLUMNS}
                        FROM commerce.orders AS o
                        JOIN commerce.customers AS c ON c.id = o.customer_id
                        WHERE {' AND '.join(clauses)}
                        ORDER BY o.created_at DESC, o.id DESC
                        LIMIT 50
                        """
                    ),
                    parameters,
                )
            ).mappings().all()
        return OrderSearchResponse(
            customer_ref=customer_ref,
            items=[self._summary(row) for row in rows],
        )

    async def get_order(self, *, customer_ref: str, order_id: UUID) -> OrderDetail:
        async with self._engine.connect() as connection:
            row = await self._scoped_order(
                connection, customer_ref=customer_ref, order_id=order_id
            )
        if row is None:
            raise self._order_not_found()
        return self._detail(row)

    async def get_order_items(
        self, *, customer_ref: str, order_id: UUID
    ) -> OrderItemsResponse:
        async with self._engine.connect() as connection:
            order = await self._scoped_order(
                connection, customer_ref=customer_ref, order_id=order_id
            )
            if order is None:
                raise self._order_not_found()
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT oi.id, oi.product_id, p.sku, p.name AS product_name,
                               oi.variant, oi.quantity, oi.unit_amount, oi.currency
                        FROM commerce.order_items AS oi
                        JOIN commerce.products AS p ON p.id = oi.product_id
                        WHERE oi.order_id = :order_id
                        ORDER BY oi.id
                        """
                    ),
                    {"order_id": order_id},
                )
            ).mappings().all()
        return OrderItemsResponse(
            customer_ref=customer_ref,
            order_id=order_id,
            items=[OrderItem.model_validate(dict(row)) for row in rows],
        )

    async def sync_payment(
        self,
        *,
        order_id: UUID,
        payload: SyncPaymentRequest,
        idempotency_key: str,
        correlation_id: str,
    ) -> SyncPaymentResult:
        request_hash = self._request_hash(order_id, payload)
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                {"scope": f"{_OPERATION}:{idempotency_key}"},
            )
            replay = (
                await connection.execute(
                    text(
                        """
                        SELECT request_hash, response_body
                        FROM commerce.idempotency_records
                        WHERE operation = :operation AND idempotency_key = :key
                        """
                    ),
                    {"operation": _OPERATION, "key": idempotency_key},
                )
            ).mappings().one_or_none()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise CommerceApiError(
                        status_code=409,
                        code="REQUEST_VALIDATION_ERROR",
                        message="The Idempotency-Key was already used with a different request.",
                    )
                return SyncPaymentResult(
                    response=SyncPaymentResponse.model_validate(replay["response_body"]),
                    replayed=True,
                )

            order = await self._scoped_order(
                connection,
                customer_ref=payload.customer_ref,
                order_id=order_id,
                for_update=True,
            )
            if order is None:
                raise self._order_not_found()
            if order["version"] != payload.expected_order_version:
                raise CommerceApiError(
                    status_code=409,
                    code="STALE_ORDER",
                    message="The order version no longer matches the approved proposal.",
                )
            self._require_approval(payload)

            payment = (
                await connection.execute(
                    text(
                        """
                        SELECT p.id, p.status::text AS status, p.amount, p.currency,
                               p.transaction_ref, p.order_id
                        FROM commerce.payments AS p
                        JOIN commerce.customers AS c ON c.id = p.customer_id
                        WHERE c.external_ref = :customer_ref
                          AND p.order_id = :order_id
                          AND p.transaction_ref = :transaction_ref
                        FOR UPDATE OF p
                        """
                    ),
                    {
                        "customer_ref": payload.customer_ref,
                        "order_id": order_id,
                        "transaction_ref": payload.transaction_ref,
                    },
                )
            ).mappings().one_or_none()
            if (
                payment is None
                or payment["status"] != "SUCCEEDED"
                or payment["amount"] != order["total_amount"]
                or payment["currency"] != order["currency"]
                or order["payment_status"] != "PENDING"
            ):
                raise CommerceApiError(
                    status_code=409,
                    code="PAYMENT_MISMATCH",
                    message="The payment evidence does not match the target order state.",
                )

            before_hash = self._state_hash(order)
            updated = (
                await connection.execute(
                    text(
                        """
                        UPDATE commerce.orders
                        SET payment_status = 'PAID', version = version + 1, updated_at = now()
                        WHERE id = :order_id AND version = :expected_version
                        RETURNING id, status::text AS status,
                                  payment_status::text AS payment_status,
                                  version, updated_at
                        """
                    ),
                    {
                        "order_id": order_id,
                        "expected_version": payload.expected_order_version,
                    },
                )
            ).mappings().one_or_none()
            if updated is None:
                raise CommerceApiError(
                    status_code=409,
                    code="STALE_ORDER",
                    message="The order version no longer matches the approved proposal.",
                )

            response = SyncPaymentResponse.model_validate(
                {
                    "customer_ref": payload.customer_ref,
                    "order_id": updated["id"],
                    "order_status": updated["status"],
                    "payment_status": updated["payment_status"],
                    "version": updated["version"],
                    "transaction_ref": payload.transaction_ref,
                    "updated_at": updated["updated_at"],
                }
            )
            response_body = response.model_dump(mode="json")
            await connection.execute(
                text(
                    """
                    INSERT INTO commerce.audit_logs
                        (correlation_id, action, order_id, result,
                         before_hash, after_hash, details)
                    VALUES
                        (:correlation_id, :operation, :order_id, 'SUCCEEDED',
                         :before_hash, :after_hash, CAST(:details AS jsonb))
                    """
                ),
                {
                    "correlation_id": uuid5(NAMESPACE_URL, correlation_id),
                    "operation": _OPERATION,
                    "order_id": order_id,
                    "before_hash": before_hash,
                    "after_hash": self._state_hash(response_body),
                    "details": json.dumps(
                        {
                            "approval_ref": payload.approval_ref,
                            "proposal_hash": payload.proposal_hash,
                        },
                        sort_keys=True,
                    ),
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO commerce.idempotency_records
                        (operation, idempotency_key, request_hash, order_id,
                         response_status, response_body)
                    VALUES
                        (:operation, :key, :request_hash, :order_id, 200,
                         CAST(:response_body AS jsonb))
                    """
                ),
                {
                    "operation": _OPERATION,
                    "key": idempotency_key,
                    "request_hash": request_hash,
                    "order_id": order_id,
                    "response_body": json.dumps(response_body, sort_keys=True),
                },
            )
        return SyncPaymentResult(response=response, replayed=False)

    @staticmethod
    async def _require_customer(connection: AsyncConnection, customer_ref: str) -> None:
        found = (
            await connection.execute(
                text(
                    """
                    SELECT id FROM commerce.customers
                    WHERE external_ref = :customer_ref AND status = 'ACTIVE'
                    """
                ),
                {"customer_ref": customer_ref},
            )
        ).scalar_one_or_none()
        if found is None:
            raise CommerceApiError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="The customer was not found.",
            )

    @staticmethod
    async def _scoped_order(
        connection: AsyncConnection,
        *,
        customer_ref: str,
        order_id: UUID,
        for_update: bool = False,
    ) -> RowMapping | None:
        lock = "FOR UPDATE OF o" if for_update else ""
        return (
            await connection.execute(
                text(
                    f"""
                    SELECT {_ORDER_COLUMNS}
                    FROM commerce.orders AS o
                    JOIN commerce.customers AS c ON c.id = o.customer_id
                    WHERE o.id = :order_id
                      AND c.external_ref = :customer_ref
                      AND c.status = 'ACTIVE'
                    {lock}
                    """
                ),
                {"order_id": order_id, "customer_ref": customer_ref},
            )
        ).mappings().one_or_none()

    @staticmethod
    def _require_approval(payload: SyncPaymentRequest) -> None:
        try:
            if payload.approval_ref is None:
                raise ValueError
            UUID(payload.approval_ref)
        except (ValueError, AttributeError):
            raise CommerceApiError(
                status_code=403,
                code="APPROVAL_REQUIRED",
                message="A valid approval reference is required.",
            ) from None
        if payload.proposal_hash is None or _PROPOSAL_HASH.fullmatch(payload.proposal_hash) is None:
            raise CommerceApiError(
                status_code=403,
                code="APPROVAL_REQUIRED",
                message="A valid approved proposal hash is required.",
            )

    @staticmethod
    def _request_hash(order_id: UUID, payload: SyncPaymentRequest) -> str:
        canonical = json.dumps(
            {"order_id": str(order_id), **payload.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _state_hash(value: RowMapping | dict[str, Any]) -> str:
        if not isinstance(value, dict):
            state = {
                "id": str(value["id"]),
                "status": value["status"],
                "payment_status": value["payment_status"],
                "version": value["version"],
            }
        else:
            state = {
                "id": str(value["order_id"]),
                "status": value["order_status"],
                "payment_status": value["payment_status"],
                "version": value["version"],
            }
        canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

    @staticmethod
    def _summary(row: RowMapping) -> OrderSummary:
        values = dict(row)
        values.pop("updated_at", None)
        return OrderSummary.model_validate(values)

    @staticmethod
    def _detail(row: RowMapping) -> OrderDetail:
        return OrderDetail.model_validate(dict(row))

    @staticmethod
    def _order_not_found() -> CommerceApiError:
        return CommerceApiError(
            status_code=404,
            code="ORDER_NOT_FOUND",
            message="The order was not found.",
        )
