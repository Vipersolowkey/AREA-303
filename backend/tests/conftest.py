"""Shared test fixtures."""

import os

# Force test config BEFORE importing app modules.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")

import pytest  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402


def _bearer(user_id: str, role: str, email: str) -> dict[str, str]:
    """Mint a real signed token — the same helper the login endpoint uses, so
    these fixtures exercise the actual claim shape rather than a stand-in."""
    token = create_access_token(
        user_id, extra={"role": role, "email": email, "name": role.title()}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return _bearer("1", "admin", "admin@test.dev")


@pytest.fixture
def buyer_headers() -> dict[str, str]:
    return _bearer("2", "buyer", "buyer@test.dev")


__all__ = ["admin_headers", "app", "buyer_headers"]
