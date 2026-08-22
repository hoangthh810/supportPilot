from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CustomerRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
TransactionRef = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
OrderStatus = Literal["PENDING_CONFIRMATION", "CONFIRMED"]
OrderPaymentStatus = Literal["PENDING", "PAID"]


class HttpContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderSummary(HttpContract):
    id: UUID
    order_number: str
    status: OrderStatus
    payment_status: OrderPaymentStatus
    total_amount: Decimal
    currency: Currency
    version: int = Field(ge=1)
    created_at: datetime


class OrderDetail(OrderSummary):
    updated_at: datetime


class OrderSearchResponse(HttpContract):
    customer_ref: CustomerRef
    items: list[OrderSummary]


class OrderItem(HttpContract):
    id: UUID
    product_id: UUID
    sku: str
    product_name: str
    variant: str | None
    quantity: int = Field(gt=0)
    unit_amount: Decimal
    currency: Currency


class OrderItemsResponse(HttpContract):
    customer_ref: CustomerRef
    order_id: UUID
    items: list[OrderItem]


class SyncPaymentRequest(HttpContract):
    customer_ref: CustomerRef
    transaction_ref: TransactionRef
    expected_order_version: int = Field(ge=0)
    approval_ref: str | None = Field(default=None, max_length=128)
    proposal_hash: str | None = Field(default=None, max_length=71)


class SyncPaymentResponse(HttpContract):
    customer_ref: CustomerRef
    order_id: UUID
    order_status: OrderStatus
    payment_status: Literal["PAID"]
    version: int = Field(ge=2)
    transaction_ref: TransactionRef
    updated_at: datetime
