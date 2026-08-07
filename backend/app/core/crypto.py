"""Symmetric encryption for third-party credentials we hold on a user's behalf.

Used for stored Shopee sessions. A Shopee session cookie is a bearer credential
for someone's real account — whoever holds it can act as that user on Shopee. So
it must not sit in the database in plaintext: a dump, a backup left in an S3
bucket, or read access to one table would otherwise be account takeover for every
connected user at once.

Fernet (AES-128-CBC + HMAC-SHA256, timestamped) is the right primitive here:
authenticated, versioned, and part of `cryptography`, which is already a
dependency via python-jose.

## The key is deliberately not derived from JWT_SECRET

Reusing the JWT signing key would mean rotating one forces rotating the other,
and it widens the blast radius of either leaking. `CREDENTIAL_ENCRYPTION_KEY` is
its own setting, and when it's unset, storing a credential *fails loudly* rather
than falling back to plaintext or to a hardcoded default — a silent fallback is
how plaintext credentials end up in production.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode


class CredentialEncryptionUnavailable(AppError):
    """No usable key configured. Raised instead of degrading to plaintext."""

    status_code = 503
    code = ErrorCode.UPSTREAM_UNAVAILABLE


class CredentialDecryptionFailed(AppError):
    """Ciphertext didn't verify — wrong key, or the row was tampered with."""

    status_code = 500
    code = ErrorCode.INTERNAL_ERROR


def generate_key() -> str:
    """A fresh key, for `python -c` during setup."""
    return Fernet.generate_key().decode()


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = (settings.CREDENTIAL_ENCRYPTION_KEY or "").strip()
    if not raw:
        raise CredentialEncryptionUnavailable(
            "Chưa cấu hình CREDENTIAL_ENCRYPTION_KEY, nên không thể lưu thông tin "
            "đăng nhập của người dùng. Sinh key bằng: python -c "
            '"from app.core.crypto import generate_key; print(generate_key())"'
        )
    try:
        return Fernet(raw.encode())
    except (ValueError, TypeError) as exc:
        raise CredentialEncryptionUnavailable(
            "CREDENTIAL_ENCRYPTION_KEY không đúng định dạng — cần một Fernet key "
            "(32 byte, base64 urlsafe)."
        ) from exc


def is_available() -> bool:
    """Whether credentials can be stored — checked before offering the feature."""
    try:
        _fernet()
    except CredentialEncryptionUnavailable:
        return False
    return True


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        # Most often a rotated key against old rows. Say so, because "invalid
        # token" alone sends people looking at the wrong thing.
        raise CredentialDecryptionFailed(
            "Không giải mã được thông tin đã lưu — có thể "
            "CREDENTIAL_ENCRYPTION_KEY đã thay đổi. Người dùng cần kết nối lại."
        ) from exc
