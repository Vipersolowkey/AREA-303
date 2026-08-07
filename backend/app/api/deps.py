"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, Header
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.redis import get_redis
from app.db.session import get_db  # re-export


async def get_db_dep() -> AsyncIterator[AsyncSession]:  # alias for clarity
    async for s in get_db():
        yield s


async def get_redis_dep() -> Redis:
    return get_redis()


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict:
    """Decode the Bearer JWT and return its claims — no DB round trip.

    The role lives in the signed token, so authorising a request never needs a
    query. The trade-off: revoking a role or deleting an account only takes
    effect once the token expires (``JWT_EXPIRE_MINUTES``, 24h by default).
    That's an acceptable window here and it keeps the seller portal working
    when Postgres is down.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing bearer token.")
    token = authorization.split(" ", 1)[1]
    return decode_access_token(token)


def require_role(*roles: str) -> Callable[..., Awaitable[dict]]:
    """Build a dependency that rejects any token whose role isn't listed.

    Mount it per-router in :mod:`app.api.v1` — ``include_router(...,
    dependencies=[Depends(require_admin)])`` — so a whole feature area is
    gated in one place instead of decorating every endpoint.
    """

    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise ForbiddenError("Bạn không có quyền truy cập khu vực này.")
        return user

    return _dep


require_admin = require_role("admin")


__all__ = [
    "get_current_user",
    "get_db",
    "get_db_dep",
    "get_redis",
    "get_redis_dep",
    "require_admin",
    "require_role",
]
