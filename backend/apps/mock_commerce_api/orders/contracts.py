from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.packages.commerce_contracts import (
    OrderDetail,
    OrderItemsResponse,
    OrderSearchResponse,
    SyncPaymentRequest,
    SyncPaymentResponse,
)


@dataclass(frozen=True, slots=True)
class OrderSearchFilters:
    created_from: datetime | None = None
    created_to: datetime | None = None
    status: str | None = None
    product_query: str | None = None


@dataclass(frozen=True, slots=True)
class SyncPaymentResult:
    response: SyncPaymentResponse
    replayed: bool


class OrderRepository(Protocol):
    async def search_orders(
        self, *, customer_ref: str, filters: OrderSearchFilters
    ) -> OrderSearchResponse: ...

    async def get_order(self, *, customer_ref: str, order_id: UUID) -> OrderDetail: ...

    async def get_order_items(
        self, *, customer_ref: str, order_id: UUID
    ) -> OrderItemsResponse: ...

    async def sync_payment(
        self,
        *,
        order_id: UUID,
        payload: SyncPaymentRequest,
        idempotency_key: str,
        correlation_id: str,
    ) -> SyncPaymentResult: ...
