"""Credential handling for a user's connected Shopee account.

These tests exist because the failure modes here are silent and expensive: a jar
stored in plaintext, cookies for unrelated sites kept "just in case", or an
unverified credential accepted so the user learns it's broken at the next
scheduled run. Each of those is one forgotten line away, so each is pinned.

The browser is never launched — `verify_state` is the seam, monkeypatched.
"""

from __future__ import annotations

import json

import pytest

from app.core import crypto
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services import shopee_session_service as svc
from app.services.competitor.session import (
    narrow_storage_state,
    state_looks_logged_in,
)

_KEY = "0" * 43 + "="  # a syntactically valid Fernet key shape


def _cookie(name: str, value: str, domain: str = ".shopee.vn") -> dict:
    return {"name": name, "value": value, "domain": domain, "path": "/"}


# --- Narrowing: what we refuse to hold -------------------------------------


def test_narrowing_drops_cookies_for_other_sites():
    """A jar from a browser the user had open carries their whole session set."""
    state = {
        "cookies": [
            _cookie("SPC_ST", "abc"),
            _cookie("SID", "google-session", ".google.com"),
            _cookie("li_at", "linkedin-session", ".linkedin.com"),
            _cookie("csrftoken", "x", "shopee.vn"),
        ],
        "origins": [{"origin": "https://mail.google.com", "localStorage": [{"name": "a", "value": "b"}]}],
    }
    got = narrow_storage_state(state)

    names = {c["name"] for c in got["cookies"]}
    assert names == {"SPC_ST", "csrftoken"}
    # localStorage is dropped wholesale — Shopee's session is in cookies, so it
    # buys nothing and can carry a lot.
    assert got["origins"] == []


def test_narrowing_is_not_fooled_by_a_lookalike_domain():
    state = {"cookies": [_cookie("SPC_ST", "x", ".notshopee.vn.evil.com")]}
    assert narrow_storage_state(state)["cookies"] == []


def test_narrowing_survives_a_malformed_jar():
    state = {"cookies": ["not-a-dict", None, _cookie("SPC_ST", "x")]}
    assert len(narrow_storage_state(state)["cookies"]) == 1


# --- Login detection --------------------------------------------------------


def test_a_jar_without_a_session_cookie_is_not_logged_in():
    """Cookies exist for any visitor; only a session cookie means logged in."""
    assert not state_looks_logged_in({"cookies": [_cookie("csrftoken", "x")]})
    assert not state_looks_logged_in({"cookies": []})
    # Present but empty — what you get capturing mid-login.
    assert not state_looks_logged_in({"cookies": [_cookie("SPC_ST", "")]})
    assert state_looks_logged_in({"cookies": [_cookie("SPC_ST", "real-token")]})


# --- Encryption -------------------------------------------------------------


def test_encryption_refuses_to_run_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", None)
    crypto._fernet.cache_clear()
    assert crypto.is_available() is False
    with pytest.raises(crypto.CredentialEncryptionUnavailable):
        crypto.encrypt("secret")


def test_encryption_rejects_a_malformed_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "not-a-fernet-key")
    crypto._fernet.cache_clear()
    assert crypto.is_available() is False


def test_encrypt_round_trips_and_does_not_leak_plaintext(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()

    secret = json.dumps({"cookies": [_cookie("SPC_ST", "super-secret-token")]})
    blob = crypto.encrypt(secret)

    assert "super-secret-token" not in blob
    assert crypto.decrypt(blob) == secret


def test_decrypt_under_a_rotated_key_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()
    blob = crypto.encrypt("x")

    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()
    with pytest.raises(crypto.CredentialDecryptionFailed):
        crypto.decrypt(blob)


# --- connect(): nothing unverified is stored --------------------------------


class _FakeDb:
    """Enough AsyncSession surface for connect()'s failure paths.

    The rejection cases must not reach the database at all, so any use of it is
    itself the assertion.
    """

    def __init__(self) -> None:
        self.committed = 0
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed += 1

    async def refresh(self, obj: object) -> None:  # noqa: ARG002
        pass

    async def execute(self, *_a, **_k):  # noqa: ANN002, ANN003
        class _R:
            def scalar_one_or_none(self):  # noqa: ANN201
                return None

        return _R()


@pytest.mark.asyncio
async def test_connect_rejects_a_jar_with_no_shopee_cookies(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()
    db = _FakeDb()

    with pytest.raises(ValidationError, match="không có cookie nào của shopee.vn"):
        await svc.connect(
            db,  # type: ignore[arg-type]
            1,
            storage_state={"cookies": [_cookie("SID", "x", ".google.com")]},
        )
    assert db.committed == 0


@pytest.mark.asyncio
async def test_connect_rejects_a_jar_captured_before_login_finished(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()
    db = _FakeDb()

    with pytest.raises(ValidationError, match="chưa thấy cookie phiên"):
        await svc.connect(
            db,  # type: ignore[arg-type]
            1,
            storage_state={"cookies": [_cookie("csrftoken", "x")]},
        )
    assert db.committed == 0


@pytest.mark.asyncio
async def test_connect_stores_nothing_when_the_live_read_fails(monkeypatch):
    """The whole point of verifying: a jar that parses need not work."""
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()

    async def refused(state):  # noqa: ANN001, ARG001
        return False, "Shopee từ chối yêu cầu dù đã kết nối (error 90309999)"

    monkeypatch.setattr(svc, "verify_state", refused)
    db = _FakeDb()

    with pytest.raises(ValidationError, match="Chưa lưu gì cả"):
        await svc.connect(
            db,  # type: ignore[arg-type]
            1,
            storage_state={"cookies": [_cookie("SPC_ST", "token")]},
        )
    assert db.committed == 0


@pytest.mark.asyncio
async def test_connect_refuses_when_encryption_is_unavailable(monkeypatch):
    """Better to not offer the feature than to store a session in plaintext."""
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", None)
    crypto._fernet.cache_clear()

    async def ok(state):  # noqa: ANN001, ARG001
        return True, "fine"

    monkeypatch.setattr(svc, "verify_state", ok)
    db = _FakeDb()

    with pytest.raises(crypto.CredentialEncryptionUnavailable):
        await svc.connect(
            db,  # type: ignore[arg-type]
            1,
            storage_state={"cookies": [_cookie("SPC_ST", "token")]},
        )
    assert db.committed == 0


@pytest.mark.asyncio
async def test_connect_stores_ciphertext_not_the_jar(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key())
    crypto._fernet.cache_clear()

    async def ok(state):  # noqa: ANN001, ARG001
        return True, "đọc được 20 sản phẩm"

    monkeypatch.setattr(svc, "verify_state", ok)
    db = _FakeDb()

    row = await svc.connect(
        db,  # type: ignore[arg-type]
        7,
        storage_state={
            "cookies": [_cookie("SPC_ST", "super-secret"), _cookie("SID", "x", ".google.com")]
        },
        shopee_username="tyler",
    )

    assert db.committed == 1
    assert row.active is True
    assert row.shopee_username == "tyler"
    # The credential is not readable from the column...
    assert "super-secret" not in row.state_encrypted
    # ...but round-trips, and carries only the Shopee cookie.
    restored = json.loads(crypto.decrypt(row.state_encrypted))
    assert [c["name"] for c in restored["cookies"]] == ["SPC_ST"]


# --- mark_result(): only a dead credential deactivates ----------------------


class _RowDb(_FakeDb):
    def __init__(self, row) -> None:  # noqa: ANN001
        super().__init__()
        self._row = row

    async def execute(self, *_a, **_k):  # noqa: ANN002, ANN003
        row = self._row

        class _R:
            def scalar_one_or_none(self):  # noqa: ANN201
                return row

        return _R()


@pytest.mark.asyncio
async def test_a_transient_failure_does_not_force_a_reconnect():
    from app.models.shopee_session import ShopeeSession

    row = ShopeeSession(user_id=1, state_encrypted="x", active=True)
    db = _RowDb(row)

    await svc.mark_result(db, 1, ok=False, expired=False, error="hết thời gian chờ")  # type: ignore[arg-type]

    # A timeout or a changed endpoint shouldn't make the user redo a login that
    # is perfectly valid.
    assert row.active is True
    assert row.last_error == "hết thời gian chờ"


@pytest.mark.asyncio
async def test_a_refused_session_is_deactivated():
    from app.models.shopee_session import ShopeeSession

    row = ShopeeSession(user_id=1, state_encrypted="x", active=True)
    db = _RowDb(row)

    await svc.mark_result(db, 1, ok=False, expired=True, error="error 90309999")  # type: ignore[arg-type]

    assert row.active is False


@pytest.mark.asyncio
async def test_an_inactive_row_yields_no_storage_state():
    """The collector must not launch a browser for a credential already refused."""
    from app.models.shopee_session import ShopeeSession

    row = ShopeeSession(user_id=1, state_encrypted="x", active=False)
    db = _RowDb(row)

    assert await svc.storage_state_for(db, 1) is None  # type: ignore[arg-type]
