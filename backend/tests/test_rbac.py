"""Role gating: the seller portal is admin-only, the buyer flow stays open.

The public-path half of this file is the regression net for "adding auth
didn't break shopping" — those four endpoints back the storefront, the two
buyer GenAI pages and the behaviour-ingest call, and they must answer with no
token at all.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# One representative route per gating mechanism:
#   - /kpis/summary + /dynamic-pricing/  → router-level dependencies
#   - /storefront/reviews/queue          → per-route dependency on a mixed router
#   - /journey/sessions                  → per-route dependency on a mixed router
ADMIN_ONLY_GETS = [
    "/api/v1/kpis/summary",
    "/api/v1/storefront/reviews/queue",
    "/api/v1/journey/sessions",
    "/api/v1/users/",
]

# Same list minus the routes whose handler needs a live Postgres. Rejection is
# testable everywhere (the dependency runs before the handler), but "an admin
# gets through" can only be asserted where the handler itself can complete
# without a database — there's no DB fixture in this repo.
ADMIN_ONLY_GETS_NO_DB = [p for p in ADMIN_ONLY_GETS if p != "/api/v1/users/"]


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ADMIN_ONLY_GETS)
async def test_admin_routes_reject_anonymous(path):
    async with _client() as ac:
        r = await ac.get(path)

    assert r.status_code == 401, path
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ADMIN_ONLY_GETS)
async def test_admin_routes_reject_buyer(path, buyer_headers):
    async with _client() as ac:
        r = await ac.get(path, headers=buyer_headers)

    assert r.status_code == 403, path
    assert r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ADMIN_ONLY_GETS_NO_DB)
async def test_admin_routes_admit_admin(path, admin_headers):
    """Assert only that authorisation passed — some of these then depend on an
    LLM, so the status just must not be 401/403."""
    async with _client() as ac:
        r = await ac.get(path, headers=admin_headers)

    assert r.status_code not in (401, 403), path


@pytest.mark.asyncio
async def test_admin_only_post_rejects_buyer(buyer_headers):
    async with _client() as ac:
        body = {"product_name": "Áo thun", "category": "Thời trang", "current_price": 200000}
        anon = await ac.post("/api/v1/dynamic-pricing/", json=body)
        buyer = await ac.post("/api/v1/dynamic-pricing/", json=body, headers=buyer_headers)

    assert anon.status_code == 401
    assert buyer.status_code == 403


@pytest.mark.asyncio
async def test_buyer_flow_stays_public():
    """No token anywhere — this is what an anonymous shopper does."""
    async with _client() as ac:
        health = await ac.get("/api/v1/health")
        listing = await ac.get("/api/v1/storefront/products")
        pid = listing.json()["data"]["products"][0]["id"]
        detail = await ac.get(f"/api/v1/storefront/products/{pid}")
        ingest = await ac.post(
            "/api/v1/journey/events",
            json={"session_id": "anon-1", "events": [{"type": "view", "ts": 1000}]},
        )

    assert health.status_code == 200
    assert listing.status_code == 200
    assert detail.status_code == 200
    assert ingest.status_code == 200


# Anonymous review submission is covered by
# tests/test_review_submission.py — those tests monkeypatch review_service (the
# write path needs Postgres) and pass no Authorization header, which is exactly
# the "a logged-out shopper can still review" assertion.
