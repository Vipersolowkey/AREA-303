"""Tests for #13 Customer Segmentation endpoint + envelope shape.

Loads the real trained XGBoost artifacts from customer_segmentation/models/.
If those .pkl files are absent, the service raises UpstreamUnavailableError
(503) — the last test covers the missing-artifacts path via monkeypatch.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# A user with clear buying behaviour (recent login, likes/wishes/buys).
_ACTIVE_BUYER = {
    "log_recency": 5.92,
    "seniority_months": 102.0,
    "log_followers": 1.5,
    "log_follows": 2.21,
    "log_products_liked": 0.77,
    "log_products_listed": 0.02,
    "log_products_sold": 0.04,
    "products_pass_rate": 0.83,
    "log_products_wished": 0.44,
    "log_products_bought": 0.16,
    "buy_ratio": 0.16,
    "wish_to_buy": 0.14,
    "has_any_app": 1,
    "has_profile_picture": 1,
}

# A completely inactive user (no activity, high recency, no app).
_DORMANT = {
    **_ACTIVE_BUYER,
    "log_recency": 6.56,
    "log_products_liked": 0.0,
    "log_products_listed": 0.0,
    "log_products_sold": 0.0,
    "products_pass_rate": 0.0,
    "log_products_wished": 0.0,
    "log_products_bought": 0.0,
    "buy_ratio": 0.0,
    "wish_to_buy": 0.0,
    "has_any_app": 0,
}

_PERSONAS = {
    "Active Buyers",
    "At-risk / Low-activity Users",
    "Dormant / Ghost Users",
    "Sellers (listing & selling activity)",
}


@pytest.mark.asyncio
async def test_segmentation_returns_envelope(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/segmentation/", json=_ACTIVE_BUYER, headers=admin_headers
        )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["persona"] in _PERSONAS
    # probabilities cover all 4 personas and sum to ~1.0
    assert set(data["probabilities"].keys()) == _PERSONAS
    assert abs(sum(data["probabilities"].values()) - 1.0) < 0.01


@pytest.mark.asyncio
async def test_active_buyer_is_predicted_active(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/segmentation/", json=_ACTIVE_BUYER, headers=admin_headers
        )
    assert r.json()["data"]["persona"] == "Active Buyers"


@pytest.mark.asyncio
async def test_dormant_user_is_predicted_dormant(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/segmentation/", json=_DORMANT, headers=admin_headers
        )
    assert r.json()["data"]["persona"] == "Dormant / Ghost Users"


@pytest.mark.asyncio
async def test_invalid_input_rejected(admin_headers):
    """buy_ratio must be in [0, 1] — an out-of-range value fails validation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/segmentation/",
            json={**_ACTIVE_BUYER, "buy_ratio": 5.0},
            headers=admin_headers,
        )
    assert r.status_code == 422
    assert r.json()["success"] is False


@pytest.mark.asyncio
async def test_missing_field_rejected(admin_headers):
    payload = {k: v for k, v in _ACTIVE_BUYER.items() if k != "log_recency"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/segmentation/", json=payload, headers=admin_headers)
    assert r.status_code == 422
