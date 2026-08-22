from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from backend.apps.mock_commerce_api.app import create_mock_commerce_app
from backend.apps.mock_commerce_api.core.errors import CommerceApiError
from backend.apps.mock_commerce_api.orders.contracts import (
    OrderSearchFilters,
    SyncPaymentResult,
)
from backend.apps.mock_commerce_api.orders.service import OrderService
from backend.packages.commerce_contracts import (
    OrderDetail,
    OrderItem,
    OrderItemsResponse,
    OrderSearchResponse,
    OrderSummary,
    SyncPaymentRequest,
    SyncPaymentResponse,
)
from backend.tests.test_mock_commerce_auth import INTERNAL_TOKEN, mock_settings

CUSTOMER_REF = "commerce-demo-customer-001"
ORDER_ID = UUID("30000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
AUTH = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


class FakeOrderRepository:
    def __init__(self) -> None:
        self.search_filters: OrderSearchFilters | None = None
        self.sync_calls = 0

    async def search_orders(
        self, *, customer_ref: str, filters: OrderSearchFilters
    ) -> OrderSearchResponse:
        self.search_filters = filters
        return OrderSearchResponse(customer_ref=customer_ref, items=[summary()])

    async def get_order(self, *, customer_ref: str, order_id: UUID) -> OrderDetail:
        if customer_ref != CUSTOMER_REF or order_id != ORDER_ID:
            raise CommerceApiError(
                status_code=404,
                code="ORDER_NOT_FOUND",
                message="The order was not found.",
            )
        return OrderDetail(**summary().model_dump(), updated_at=NOW)

    async def get_order_items(
        self, *, customer_ref: str, order_id: UUID
    ) -> OrderItemsResponse:
        if customer_ref != CUSTOMER_REF or order_id != ORDER_ID:
            raise CommerceApiError(
                status_code=404,
                code="ORDER_NOT_FOUND",
                message="The order was not found.",
            )
        return OrderItemsResponse(
            customer_ref=customer_ref,
            order_id=order_id,
            items=[
                OrderItem(
                    id=UUID("31000000-0000-4000-8000-000000000001"),
                    product_id=UUID("20000000-0000-4000-8000-000000000001"),
                    sku="SYN-CHAIR-ATLAS-001",
                    product_name="Synthetic chair",
                    variant="synthetic-black",
                    quantity=1,
                    unit_amount=Decimal("2490000.00"),
                    currency="VND",
                )
            ],
        )

    async def sync_payment(
        self,
        *,
        order_id: UUID,
        payload: SyncPaymentRequest,
        idempotency_key: str,
        correlation_id: str,
    ) -> SyncPaymentResult:
        del idempotency_key, correlation_id
        self.sync_calls += 1
        return SyncPaymentResult(
            response=SyncPaymentResponse(
                customer_ref=payload.customer_ref,
                order_id=order_id,
                order_status="PENDING_CONFIRMATION",
                payment_status="PAID",
                version=payload.expected_order_version + 1,
                transaction_ref=payload.transaction_ref,
                updated_at=NOW,
            ),
            replayed=self.sync_calls > 1,
        )


def summary() -> OrderSummary:
    return OrderSummary(
        id=ORDER_ID,
        order_number="SYN-ORD-CHAIR-001",
        status="PENDING_CONFIRMATION",
        payment_status="PENDING",
        total_amount=Decimal("2490000.00"),
        currency="VND",
        version=1,
        created_at=NOW,
    )


def client(repository: FakeOrderRepository | None = None) -> tuple[TestClient, FakeOrderRepository]:
    runtime_repository = repository or FakeOrderRepository()
    app = create_mock_commerce_app(
        mock_settings(), order_service=OrderService(runtime_repository)
    )
    return TestClient(app), runtime_repository


def sync_payload() -> dict[str, object]:
    return {
        "customer_ref": CUSTOMER_REF,
        "transaction_ref": "SYN-TXN-CHAIR-001",
        "expected_order_version": 1,
        "approval_ref": "50000000-0000-4000-8000-000000000001",
        "proposal_hash": f"sha256:{'a' * 64}",
    }


def test_order_search_detail_and_items_are_customer_scoped_safe_projections() -> None:
    http, repository = client()

    search = http.get(
        f"/internal/v1/customers/{CUSTOMER_REF}/orders",
        headers=AUTH,
        params={"status": "PENDING_CONFIRMATION", "product_query": "chair"},
    )
    detail = http.get(
        f"/internal/v1/orders/{ORDER_ID}",
        headers=AUTH,
        params={"customer_ref": CUSTOMER_REF},
    )
    items = http.get(
        f"/internal/v1/orders/{ORDER_ID}/items",
        headers=AUTH,
        params={"customer_ref": CUSTOMER_REF},
    )

    assert search.status_code == detail.status_code == items.status_code == 200
    assert search.json()["items"][0]["order_number"] == "SYN-ORD-CHAIR-001"
    assert detail.json()["version"] == 1
    assert items.json()["items"][0]["sku"] == "SYN-CHAIR-ATLAS-001"
    assert repository.search_filters == OrderSearchFilters(
        status="PENDING_CONFIRMATION", product_query="chair"
    )
    serialized = f"{search.text}{detail.text}{items.text}".lower()
    assert "email" not in serialized
    assert "phone" not in serialized
    assert "payment_method" not in serialized


def test_other_customer_receives_indistinguishable_order_not_found() -> None:
    http, _ = client()

    response = http.get(
        f"/internal/v1/orders/{ORDER_ID}",
        headers={**AUTH, "X-Correlation-ID": "corr_wrong-owner"},
        params={"customer_ref": "commerce-isolation-customer-002"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "ORDER_NOT_FOUND",
        "message": "The order was not found.",
        "retryable": False,
        "correlation_id": "corr_wrong-owner",
        "details": {},
    }


def test_sync_contract_and_replay_header_are_stable() -> None:
    http, repository = client()
    headers = {**AUTH, "Idempotency-Key": "sync-action-001"}

    first = http.post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers=headers,
        json=sync_payload(),
    )
    replay = http.post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers=headers,
        json=sync_payload(),
    )

    assert first.status_code == replay.status_code == 200
    assert first.json()["payment_status"] == "PAID"
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert repository.sync_calls == 2


def test_authentication_precedes_sync_body_validation_and_service_call() -> None:
    http, repository = client()

    response = http.post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers={"Idempotency-Key": "sync-action-unauthenticated"},
        content=b"not-json",
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INTERNAL_UNAUTHENTICATED"
    assert repository.sync_calls == 0


def test_shared_commerce_contracts_have_no_runtime_or_persistence_imports() -> None:
    forbidden = ("sqlalchemy", "asyncpg", "mock_commerce_api", "support_api")
    violations: list[str] = []
    for path in Path("backend/packages/commerce_contracts").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = " ".join(alias.name for alias in node.names)
            if any(name in module for name in forbidden):
                violations.append(f"{path}: {module}")
    assert violations == []
