from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

CUSTOMER_REF = "commerce-demo-customer-001"
OTHER_CUSTOMER_REF = "commerce-isolation-customer-002"
ORDER_ID = UUID("30000000-0000-4000-8000-000000000001")
OTHER_ORDER_ID = UUID("30000000-0000-4000-8000-000000000003")
TOKEN = os.environ["INTERNAL_SERVICE_TOKEN"]
DATABASE_URL = os.environ["COMMERCE_DATABASE_URL"]
AUTH = {"Authorization": f"Bearer {TOKEN}"}
BASE_URL = os.environ.get("MOCK_COMMERCE_TEST_BASE_URL", "http://mock-commerce:8080")


@dataclass(frozen=True, slots=True)
class HttpResult:
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]
    text: str

    def json(self) -> dict[str, Any]:
        return self.body


def _request(
    method: str,
    path: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
) -> HttpResult:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={**headers, **({"Content-Type": "application/json"} if data else {})},
        method=method,
    )
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        rendered = response.read().decode()
        parsed = json.loads(rendered) if rendered else {}
        return HttpResult(
            status_code=response.status,
            headers={key.lower(): value for key, value in response.headers.items()},
            body=parsed,
            text=rendered,
        )


async def get(path: str, *, headers: dict[str, str]) -> HttpResult:
    return await asyncio.to_thread(_request, "GET", path, headers=headers)


async def post(
    path: str, *, headers: dict[str, str], body: dict[str, Any]
) -> HttpResult:
    return await asyncio.to_thread(_request, "POST", path, headers=headers, body=body)


def payload(**updates: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "customer_ref": CUSTOMER_REF,
        "transaction_ref": "SYN-TXN-CHAIR-001",
        "expected_order_version": 1,
        "approval_ref": "50000000-0000-4000-8000-000000000001",
        "proposal_hash": f"sha256:{'a' * 64}",
    }
    value.update(updates)
    return value


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    search = await get(
        f"/internal/v1/customers/{CUSTOMER_REF}/orders"
        "?product_query=ghe%20cong%20thai%20hoc&status=PENDING_CONFIRMATION",
        headers=AUTH,
    )
    assert search.status_code == 200, search.text
    ids = {item["id"] for item in search.json()["items"]}
    assert str(ORDER_ID) in ids and str(OTHER_ORDER_ID) not in ids

    detail = await get(
        f"/internal/v1/orders/{ORDER_ID}?customer_ref={CUSTOMER_REF}", headers=AUTH
    )
    items = await get(
        f"/internal/v1/orders/{ORDER_ID}/items?customer_ref={CUSTOMER_REF}",
        headers=AUTH,
    )
    assert detail.status_code == items.status_code == 200
    assert detail.json()["version"] == 1
    assert items.json()["items"][0]["sku"] == "SYN-CHAIR-ATLAS-001"

    denied = await get(
        f"/internal/v1/orders/{OTHER_ORDER_ID}?customer_ref={CUSTOMER_REF}", headers=AUTH
    )
    inverse_denied = await get(
        f"/internal/v1/orders/{ORDER_ID}?customer_ref={OTHER_CUSTOMER_REF}", headers=AUTH
    )
    assert denied.status_code == inverse_denied.status_code == 404
    assert denied.json()["code"] == inverse_denied.json()["code"] == "ORDER_NOT_FOUND"

    missing_approval = await post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers={**AUTH, "Idempotency-Key": "integration-no-approval"},
        body=payload(approval_ref=None),
    )
    stale = await post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers={**AUTH, "Idempotency-Key": "integration-stale"},
        body=payload(expected_order_version=0),
    )
    mismatch = await post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers={**AUTH, "Idempotency-Key": "integration-mismatch"},
        body=payload(transaction_ref="SYN-TXN-NOT-FOUND"),
    )
    assert (missing_approval.status_code, missing_approval.json()["code"]) == (
        403,
        "APPROVAL_REQUIRED",
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "STALE_ORDER")
    assert (mismatch.status_code, mismatch.json()["code"]) == (409, "PAYMENT_MISMATCH")

    key = "integration-concurrent-sync"
    first, second = await asyncio.gather(
        post(
            f"/internal/v1/orders/{ORDER_ID}/sync-payment",
            headers={
                **AUTH,
                "Idempotency-Key": key,
                "X-Correlation-ID": "corr_sync_first",
            },
            body=payload(),
        ),
        post(
            f"/internal/v1/orders/{ORDER_ID}/sync-payment",
            headers={
                **AUTH,
                "Idempotency-Key": key,
                "X-Correlation-ID": "corr_sync_second",
            },
            body=payload(),
        ),
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    replay_headers = {
        first.headers.get("idempotency-replayed"),
        second.headers.get("idempotency-replayed"),
    }
    assert replay_headers == {None, "true"}

    conflict = await post(
        f"/internal/v1/orders/{ORDER_ID}/sync-payment",
        headers={**AUTH, "Idempotency-Key": key},
        body=payload(proposal_hash=f"sha256:{'b' * 64}"),
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "REQUEST_VALIDATION_ERROR"
    combined = "".join(
        response.text
        for response in (
            search,
            detail,
            items,
            denied,
            missing_approval,
            stale,
            mismatch,
            first,
            second,
            conflict,
        )
    )
    assert TOKEN not in combined

    async with engine.connect() as connection:
        order = (
            await connection.execute(
                text(
                    "SELECT payment_status::text, version FROM commerce.orders WHERE id=:id"
                ),
                {"id": ORDER_ID},
            )
        ).one()
        idem_count = int(
            (
                await connection.execute(
                    text(
                        """
                        SELECT count(*) FROM commerce.idempotency_records
                        WHERE operation='SYNC_PAYMENT_STATUS' AND idempotency_key=:key
                        """
                    ),
                    {"key": key},
                )
            ).scalar_one()
        )
        audit_rows = (
            await connection.execute(
                text(
                    """
                    SELECT details::text FROM commerce.audit_logs
                    WHERE action='SYNC_PAYMENT_STATUS' AND order_id=:id
                    """
                ),
                {"id": ORDER_ID},
            )
        ).scalars().all()
    await engine.dispose()
    assert tuple(order) == ("PAID", 2)
    assert idem_count == 1
    assert len(audit_rows) == 1
    audit_text = audit_rows[0]
    assert TOKEN not in audit_text
    assert CUSTOMER_REF not in audit_text
    assert "SYN-TXN-CHAIR-001" not in audit_text
    print(
        json.dumps(
            {
                "mock_order_integration": "passed",
                "customer_isolation": True,
                "same_key_single_write": True,
                "final_order_version": order.version,
                "idempotency_records": idem_count,
                "audit_records": len(audit_rows),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
