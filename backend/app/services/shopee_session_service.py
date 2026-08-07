"""Connect / verify / disconnect a user's own Shopee login.

## The flow, and why it's shaped this way

The user logs into Shopee **in their own browser**, on their own machine, via
`scripts/shopee_connect.py`. That script uploads only the resulting cookie jar.
We never see their password, which means:

* No third-party password is ever transmitted to or stored by this app.
* 2FA and OTP keep working — a password-collecting form would break both, and
  would be indistinguishable from phishing.

The jar is narrowed to Shopee cookies (:func:`~.competitor.session.narrow_storage_state`)
and encrypted before it touches the database.

## Why connecting runs a real read first

A jar that parses is not a jar that works. Shopee can refuse an automated
request even with valid cookies, and cookies captured a second too early carry no
session at all. So `connect` performs an actual shop read and only stores the
credential if that read returns products. Otherwise the user finds out at the
next scheduled collection, which is the worst possible time to learn it.

## The risk this feature hands to the user

Shopee's terms prohibit automated access, so a connected account can be
rate-limited or banned. That is the *user's* account, not ours, so the consent
text lives in the UI at the point of connecting and is repeated in the connect
script. This module's job is to make sure nothing gets stored silently.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.shopee_session import ShopeeSession
from app.services.competitor.session import (
    ShopeeSessionReader,
    narrow_storage_state,
    state_looks_logged_in,
)

log = get_logger("app.services.shopee_session")

#: A shop read once to prove a new connection works. Any public shop does; this
#: one is large enough to always have best sellers.
_VERIFY_SHOP_ID = "173392916"
_VERIFY_URL = "https://shopee.vn/yody.official"


async def get_session(db: AsyncSession, user_id: int) -> ShopeeSession | None:
    result = await db.execute(
        select(ShopeeSession).where(ShopeeSession.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def storage_state_for(db: AsyncSession, user_id: int) -> dict[str, Any] | None:
    """Decrypted jar for a user, or None if not connected / expired.

    An expired row returns None rather than a dead credential: the collector
    would otherwise launch a browser per run to be refused again.
    """
    row = await get_session(db, user_id)
    if row is None or not row.active:
        return None
    try:
        return json.loads(crypto.decrypt(row.state_encrypted))
    except crypto.CredentialDecryptionFailed:
        # A rotated encryption key. Mark it dead so the UI asks for a reconnect
        # instead of failing the same way on every collection.
        row.active = False
        row.last_error = (
            "Không giải mã được kết nối đã lưu (khoá mã hoá có thể đã đổi). "
            "Cần kết nối lại."
        )
        await db.commit()
        return None
    except ValueError:
        row.active = False
        row.last_error = "Dữ liệu kết nối đã lưu bị hỏng. Cần kết nối lại."
        await db.commit()
        return None


async def verify_state(state: dict[str, Any]) -> tuple[bool, str]:
    """Read one shop with this jar. Returns (ok, human-readable detail)."""
    async with ShopeeSessionReader(state) as reader:
        reading, err = await reader.fetch_sales(_VERIFY_SHOP_ID, _VERIFY_URL)
    if reading is None:
        return False, err or "không rõ lý do"
    return True, (
        f"đọc được {len(reading.top_products)} sản phẩm, "
        f"tổng đã bán {reading.items_sold_total or 0:,}".replace(",", ".")
    )


async def connect(
    db: AsyncSession,
    user_id: int,
    *,
    storage_state: dict[str, Any],
    shopee_username: str | None = None,
) -> ShopeeSession:
    """Store a verified Shopee connection for one user.

    Raises ValidationError when the jar carries no session, or when a live read
    with it fails — nothing unverified is persisted.
    """
    if not crypto.is_available():
        # Raised, not worked around: storing someone's session in plaintext to
        # keep the feature working would be strictly worse than it not working.
        raise crypto.CredentialEncryptionUnavailable(
            "Chưa cấu hình CREDENTIAL_ENCRYPTION_KEY nên không thể lưu kết nối "
            "Shopee. Liên hệ người quản trị hệ thống."
        )

    narrowed = narrow_storage_state(storage_state)
    if not narrowed["cookies"]:
        raise ValidationError(
            "Dữ liệu gửi lên không có cookie nào của shopee.vn. "
            "Hãy đăng nhập Shopee trong cửa sổ do script mở ra, không phải ở "
            "cửa sổ browser khác."
        )
    if not state_looks_logged_in(narrowed):
        raise ValidationError(
            "Có cookie Shopee nhưng chưa thấy cookie phiên đăng nhập. "
            "Có thể đăng nhập chưa hoàn tất — thử lại sau khi vào được trang chủ Shopee."
        )

    ok, detail = await verify_state(narrowed)
    if not ok:
        raise ValidationError(
            f"Kết nối chưa dùng được: {detail}. Chưa lưu gì cả."
        )

    now = datetime.now(UTC)
    row = await get_session(db, user_id)
    if row is None:
        row = ShopeeSession(user_id=user_id, state_encrypted="")
        db.add(row)
    row.state_encrypted = crypto.encrypt(json.dumps(narrowed))
    row.shopee_username = (shopee_username or None) and shopee_username[:120]
    row.active = True
    row.last_ok_at = now
    row.last_checked_at = now
    row.last_error = None
    await db.commit()
    await db.refresh(row)
    log.info(
        "shopee_session.connected",
        user_id=user_id,
        cookies=len(narrowed["cookies"]),
        detail=detail,
    )
    return row


async def disconnect(db: AsyncSession, user_id: int) -> None:
    """Delete the credential outright.

    A hard delete, not a flag: the user asked us to stop holding their Shopee
    session, and a soft-deleted row that still contains it doesn't do that.
    """
    row = await get_session(db, user_id)
    if row is None:
        raise NotFoundError("Chưa kết nối tài khoản Shopee nào.")
    await db.delete(row)
    await db.commit()
    log.info("shopee_session.disconnected", user_id=user_id)


async def mark_result(
    db: AsyncSession, user_id: int, *, ok: bool, expired: bool, error: str | None
) -> None:
    """Record the outcome of a collection that used this connection."""
    row = await get_session(db, user_id)
    if row is None:
        return
    row.last_checked_at = datetime.now(UTC)
    if ok:
        row.last_ok_at = row.last_checked_at
        row.last_error = None
    else:
        row.last_error = error
        # Only a credential-level failure deactivates. A one-off timeout or a
        # changed endpoint shouldn't make the user re-do a login that's fine.
        if expired:
            row.active = False
    await db.commit()
