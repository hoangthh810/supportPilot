from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.apps.mock_commerce_api.orders.contracts import (
    OrderRepository,
    OrderSearchFilters,
    SyncPaymentResult,
)
from backend.packages.commerce_contracts import (
    OrderDetail,
    OrderItemsResponse,
    OrderSearchResponse,
    SyncPaymentRequest,
)


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def search_orders(
        self,
        *,
        customer_ref: str,
        created_from: datetime | None,
        created_to: datetime | None,
        status: str | None,
        product_query: str | None,
    ) -> OrderSearchResponse:
        return await self._repository.search_orders(
            customer_ref=customer_ref,
            filters=OrderSearchFilters(created_from, created_to, status, product_query),
        )

    async def get_order(self, *, customer_ref: str, order_id: UUID) -> OrderDetail:
        return await self._repository.get_order(customer_ref=customer_ref, order_id=order_id)

    async def get_order_items(
        self, *, customer_ref: str, order_id: UUID
    ) -> OrderItemsResponse:
        return await self._repository.get_order_items(
            customer_ref=customer_ref, order_id=order_id
        )

    async def sync_payment(
        self,
        *,
        order_id: UUID,
        payload: SyncPaymentRequest,
        idempotency_key: str,
        correlation_id: str,
    ) -> SyncPaymentResult:
        return await self._repository.sync_payment(
            order_id=order_id,
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
