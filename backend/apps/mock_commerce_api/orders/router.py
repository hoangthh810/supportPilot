from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response

from backend.apps.mock_commerce_api.orders.contracts import SyncPaymentResult
from backend.apps.mock_commerce_api.orders.service import OrderService
from backend.packages.commerce_contracts import (
    OrderDetail,
    OrderItemsResponse,
    OrderSearchResponse,
    SyncPaymentRequest,
    SyncPaymentResponse,
)

router = APIRouter(prefix="/internal/v1", tags=["internal-orders"])


def service(request: Request) -> OrderService:
    value = request.app.state.order_service
    if not isinstance(value, OrderService):
        raise RuntimeError("Mock-Commerce order service is not configured")
    return value


@router.get("/customers/{customer_ref}/orders", response_model=OrderSearchResponse)
async def search_orders(
    customer_ref: str,
    request: Request,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    status: Literal["PENDING_CONFIRMATION", "CONFIRMED"] | None = None,
    product_query: str | None = None,
) -> OrderSearchResponse:
    return await service(request).search_orders(
        customer_ref=customer_ref,
        created_from=created_from,
        created_to=created_to,
        status=status,
        product_query=product_query,
    )


@router.get("/orders/{order_id}", response_model=OrderDetail)
async def get_order(
    order_id: UUID,
    request: Request,
    customer_ref: Annotated[str, Query(min_length=1, max_length=128)],
) -> OrderDetail:
    return await service(request).get_order(customer_ref=customer_ref, order_id=order_id)


@router.get("/orders/{order_id}/items", response_model=OrderItemsResponse)
async def get_order_items(
    order_id: UUID,
    request: Request,
    customer_ref: Annotated[str, Query(min_length=1, max_length=128)],
) -> OrderItemsResponse:
    return await service(request).get_order_items(customer_ref=customer_ref, order_id=order_id)


@router.post("/orders/{order_id}/sync-payment", response_model=SyncPaymentResponse)
async def sync_payment(
    order_id: UUID,
    payload: SyncPaymentRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
) -> SyncPaymentResponse:
    result: SyncPaymentResult = await service(request).sync_payment(
        order_id=order_id,
        payload=payload,
        idempotency_key=idempotency_key,
        correlation_id=request.state.correlation_id,
    )
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result.response
