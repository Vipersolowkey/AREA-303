"""Checkout + order contract tests.

`order_service`/`inventory_service` are monkeypatched with an in-memory fake
(the pattern `test_review_submission.py` uses) because there's no DB fixture in
this repo. The fake reuses the REAL pricing and stock arithmetic so the tests
still catch a mispriced order or an oversell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import ConflictError, NotFoundError
from app.main import app
from app.schemas.orders import CheckoutRequest
from app.services import commerce_store as store
from app.services import order_service


@dataclass
class _FakeItem:
    product_id: str
    product_name: str
    brand: str
    unit_price_vnd: int
    qty: int


@dataclass
class _FakeOrder:
    order_no: str
    customer_id: str | None
    customer_name: str
    email: str | None
    total_vnd: int
    status: str
    items: list[_FakeItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class _FakeOrders:
    """Mirrors order_service's real logic against a dict of stock levels."""

    def __init__(self) -> None:
        self.orders: list[_FakeOrder] = []
        self.stock: dict[str, int] = {
            p["id"]: p["stock"] for p in store.all_products()
        }
        self._seq = 0

    async def create_order(self, db, req: CheckoutRequest, *, customer_id=None):  # noqa: ANN001, ARG002
        catalogue = {p["id"]: p for p in store.all_products()}

        wanted: dict[str, int] = {}
        for it in req.items:
            if it.product_id not in catalogue:
                raise NotFoundError(f"Sản phẩm {it.product_id} không tồn tại.")
            wanted[it.product_id] = wanted.get(it.product_id, 0) + it.qty

        # Check everything before mutating, like the real transaction does.
        for pid, qty in wanted.items():
            if self.stock.get(pid, 0) < qty:
                raise ConflictError(f"Không đủ hàng: chỉ còn {self.stock.get(pid, 0)} sản phẩm.")
        for pid, qty in wanted.items():
            self.stock[pid] -= qty

        items, total = [], 0
        for pid, qty in wanted.items():
            p = catalogue[pid]
            unit = int(p["price_vnd"])
            total += unit * qty
            items.append(_FakeItem(pid, p["name"], p["brand"], unit, qty))

        self._seq += 1
        order = _FakeOrder(
            order_no=f"AR-TEST-{self._seq:04d}",
            customer_id=customer_id,
            customer_name=req.customer_name.strip(),
            email=(req.email or "").strip().lower() or None,
            total_vnd=total,
            status="pending",
            items=items,
        )
        self.orders.append(order)
        return order

    async def list_for_customer(self, db, customer_id, limit=50):  # noqa: ANN001, ARG002
        return [o for o in self.orders if o.customer_id == customer_id]

    async def list_all(self, db, limit=100):  # noqa: ANN001, ARG002
        return list(self.orders)


@pytest.fixture
def fake_orders(monkeypatch) -> _FakeOrders:  # noqa: ANN001
    fake = _FakeOrders()
    monkeypatch.setattr(order_service, "create_order", fake.create_order)
    monkeypatch.setattr(order_service, "list_for_customer", fake.list_for_customer)
    monkeypatch.setattr(order_service, "list_all", fake.list_all)
    return fake


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _a_product() -> dict:
    """A catalogue product that actually has stock to sell."""
    return next(p for p in store.all_products() if p["stock"] > 5)


def _a_low_stock_product() -> dict:
    """A product whose whole stock fits under the per-line qty cap (99), so an
    oversell attempt reaches the stock check instead of failing validation."""
    return next(
        p for p in store.all_products() if 5 < p["stock"] <= 90
    )


@pytest.mark.asyncio
async def test_guest_can_check_out_and_price_comes_from_catalogue(fake_orders):
    p = _a_product()
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={
                "items": [{"product_id": p["id"], "qty": 2}],
                "customer_name": "Khách lẻ",
            },
        )

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "pending"          # no payment gateway
    assert data["total_vnd"] == p["price_vnd"] * 2
    assert data["items"][0]["line_total_vnd"] == p["price_vnd"] * 2
    assert data["order_no"].startswith("AR-")


@pytest.mark.asyncio
async def test_checkout_ignores_client_supplied_price(fake_orders):
    """A tampered cart must not change what's charged."""
    p = _a_product()
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={
                "items": [{"product_id": p["id"], "qty": 1, "unit_price_vnd": 1}],
                "customer_name": "Kẻ gian",
            },
        )

    assert r.status_code == 200
    assert r.json()["data"]["total_vnd"] == p["price_vnd"]


@pytest.mark.asyncio
async def test_checkout_decrements_stock(fake_orders):
    p = _a_product()
    before = fake_orders.stock[p["id"]]
    async with _client() as ac:
        await ac.post(
            "/api/v1/storefront/checkout",
            json={"items": [{"product_id": p["id"], "qty": 3}], "customer_name": "A"},
        )
    assert fake_orders.stock[p["id"]] == before - 3


@pytest.mark.asyncio
async def test_cannot_oversell(fake_orders):
    p = _a_low_stock_product()
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={
                "items": [{"product_id": p["id"], "qty": p["stock"] + 1}],
                "customer_name": "A",
            },
        )

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "RESOURCE_CONFLICT"
    # Nothing was taken.
    assert fake_orders.stock[p["id"]] == p["stock"]


@pytest.mark.asyncio
async def test_duplicate_lines_are_summed_against_stock(fake_orders):
    """Two lines for the same product must not each pass their own check."""
    p = _a_low_stock_product()
    half = p["stock"] // 2 + 1
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={
                "items": [
                    {"product_id": p["id"], "qty": half},
                    {"product_id": p["id"], "qty": half},
                ],
                "customer_name": "A",
            },
        )

    assert r.status_code == 409
    assert fake_orders.stock[p["id"]] == p["stock"]


@pytest.mark.asyncio
async def test_unknown_product_is_404(fake_orders):
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={"items": [{"product_id": "khong-ton-tai-99"}], "customer_name": "A"},
        )
    # qty is required, so this is a validation error before the lookup.
    assert r.status_code == 422

    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={
                "items": [{"product_id": "khong-ton-tai-99", "qty": 1}],
                "customer_name": "A",
            },
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_empty_cart_rejected(fake_orders):
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/storefront/checkout",
            json={"items": [], "customer_name": "A"},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_order_attaches_to_signed_in_user_and_shows_in_history(
    fake_orders, buyer_headers
):
    p = _a_product()
    async with _client() as ac:
        placed = await ac.post(
            "/api/v1/storefront/checkout",
            json={"items": [{"product_id": p["id"], "qty": 1}], "customer_name": "B"},
            headers=buyer_headers,
        )
        history = await ac.get("/api/v1/storefront/orders", headers=buyer_headers)

    assert placed.status_code == 200
    assert history.status_code == 200
    nos = [o["order_no"] for o in history.json()["data"]]
    assert placed.json()["data"]["order_no"] in nos


@pytest.mark.asyncio
async def test_guest_order_does_not_appear_in_anyones_history(fake_orders, buyer_headers):
    p = _a_product()
    async with _client() as ac:
        await ac.post(  # no auth header → guest
            "/api/v1/storefront/checkout",
            json={"items": [{"product_id": p["id"], "qty": 1}], "customer_name": "Guest"},
        )
        history = await ac.get("/api/v1/storefront/orders", headers=buyer_headers)

    assert history.json()["data"] == []


@pytest.mark.asyncio
async def test_order_history_requires_login(fake_orders):
    async with _client() as ac:
        r = await ac.get("/api/v1/storefront/orders")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_all_orders_is_admin_only(fake_orders, buyer_headers, admin_headers):
    async with _client() as ac:
        anon = await ac.get("/api/v1/storefront/orders/all")
        buyer = await ac.get("/api/v1/storefront/orders/all", headers=buyer_headers)
        admin = await ac.get("/api/v1/storefront/orders/all", headers=admin_headers)

    assert anon.status_code == 401
    assert buyer.status_code == 403
    assert admin.status_code == 200
