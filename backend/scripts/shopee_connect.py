"""Connect your own Shopee account so AREA-303 can read competitor sales data.

    python scripts/shopee_connect.py --email you@example.com

Opens a browser at Shopee's login page. You log in — Google, password, OTP,
CAPTCHA, whatever it asks. When the script sees Shopee's session cookie it
uploads *only the cookie jar* to your AREA-303 account, which verifies it by
reading one shop before storing it encrypted.

Your Shopee password never leaves your machine and is never typed into
AREA-303 — that is why 2FA and OTP keep working here.

READ THIS FIRST
---------------
Shopee's terms prohibit automated access. The account you connect can be
rate-limited, CAPTCHA-walled, or banned. Prefer a secondary account over the one
you sell from. The session also expires — reconnect when the panel says so.

## Two things this script does that a naive version gets wrong

**It waits for a cookie, not for you to press Enter.** `input()` needs a
terminal; run this from an editor or a task runner and stdin is closed, so the
prompt reads EOF and would upload an empty jar before you'd finished logging in.
Watching for `SPC_ST` works either way and can't fire early.

**It prefers your installed Chrome.** Google's OAuth flow frequently refuses
Playwright's bundled Chromium with "this browser or app may not be secure",
which makes a Google-linked Shopee account impossible to log into. Your real
Chrome gets through. That's using a browser you already have, not disguising one
as another — if Chrome isn't present it falls back and warns you.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.services.competitor.session import (  # noqa: E402
    narrow_storage_state,
    state_looks_logged_in,
)

LOGIN_URL = "https://shopee.vn/buyer/login"
#: Visited after login so shop-scoped cookies land in the jar too.
WARMUP_URL = "https://shopee.vn/"
#: Shopee's own endpoint for "who am I" — used to label the connection.
ACCOUNT_URL = "/api/v4/account/basic/get_account_info"

_ACCOUNT_JS = """
async (path) => {
  try {
    const r = await fetch(path, {headers: {'Accept': 'application/json'}});
    return {ok: true, text: await r.text()};
  } catch (e) { return {ok: false, detail: String(e)}; }
}
"""


async def _wait_for_login(ctx, timeout_s: int) -> bool:  # noqa: ANN001
    """Poll the cookie jar until Shopee's session cookie shows up."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    last_report = 0.0
    while loop.time() < deadline:
        if state_looks_logged_in({"cookies": await ctx.cookies()}):
            return True
        remaining = deadline - loop.time()
        if remaining < last_report - 29 or last_report == 0.0:
            print(f"  đang chờ đăng nhập… (còn {int(remaining)}s)")
            last_report = remaining
        await asyncio.sleep(2)
    return False


async def _shopee_username(page) -> str | None:  # noqa: ANN001
    """Best-effort label for the connected account. Never fatal."""
    try:
        raw = await page.evaluate(_ACCOUNT_JS, ACCOUNT_URL)
        body = json.loads((raw or {}).get("text") or "")
    except Exception:  # noqa: BLE001
        return None
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return None
    for key in ("username", "userName", "email", "phone"):
        value = data.get(key)
        if value:
            return str(value)[:120]
    return None


async def _upload(
    api: str, email: str, password: str, state: dict[str, Any], username: str | None
) -> tuple[bool, str]:
    """Log into AREA-303 and POST the jar. Returns (ok, message)."""
    async with httpx.AsyncClient(base_url=api.rstrip("/"), timeout=120.0) as client:
        try:
            r = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
        except httpx.HTTPError as exc:
            return False, f"không kết nối được AREA-303 ở {api}: {exc}"
        if r.status_code != 200:
            return False, f"đăng nhập AREA-303 thất bại (HTTP {r.status_code}): {r.text[:200]}"
        token = ((r.json().get("data") or {}).get("access_token")) or ""
        if not token:
            return False, "AREA-303 không trả về access_token."

        # The verify read on the server launches a browser and reads a live shop,
        # so this is slow by design — hence the long client timeout above.
        print("Đang gửi lên AREA-303 và kiểm tra kết nối (có thể mất ~30s)…")
        r = await client.post(
            "/api/v1/market/shopee-connection",
            json={"storage_state": state, "shopee_username": username},
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 200:
            return True, "đã kết nối và xác minh xong."
        try:
            detail = (r.json().get("error") or {}).get("message") or r.text[:300]
        except ValueError:
            detail = r.text[:300]
        return False, f"HTTP {r.status_code}: {detail}"


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Connect your Shopee account to AREA-303.")
    ap.add_argument("--email", help="email AREA-303 của bạn")
    ap.add_argument("--password", help="mật khẩu AREA-303 (bỏ trống sẽ được hỏi)")
    ap.add_argument("--api", default="http://localhost:8000", help="địa chỉ API AREA-303")
    ap.add_argument("--wait-seconds", type=int, default=420)
    ap.add_argument("--yes", action="store_true", help="bỏ qua xác nhận rủi ro")
    ap.add_argument(
        "--save-to",
        help="chỉ lưu jar ra file này, không upload (dùng khi chạy offline)",
    )
    args = ap.parse_args(argv)

    if not args.save_to and not args.email:
        print("Cần --email (hoặc --save-to nếu chỉ muốn lưu ra file).", file=sys.stderr)
        return 2

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Chưa cài playwright. Chạy:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        return 2

    print("=" * 72)
    print("Shopee cấm truy cập tự động. Tài khoản bạn kết nối ở đây có thể bị")
    print("giới hạn hoặc ban. Nên dùng tài khoản phụ, không dùng tài khoản bán hàng.")
    print("Mật khẩu Shopee của bạn KHÔNG được gửi đi đâu — chỉ cookie phiên.")
    print("=" * 72)
    if not args.yes and input("Tiếp tục? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Đã huỷ.")
        return 1

    password = args.password
    if not args.save_to and not password:
        password = getpass.getpass("Mật khẩu AREA-303: ")

    async with async_playwright() as pw:
        browser = None
        for channel in ("chrome", None):
            try:
                browser = await pw.chromium.launch(headless=False, channel=channel)
                print(f"Đã mở {'Chrome' if channel else 'Chromium (bundled)'}.")
                if channel is None:
                    print(
                        "  Lưu ý: Google có thể chặn đăng nhập trên Chromium bundled.\n"
                        "  Nếu bị chặn, dùng đăng nhập bằng số điện thoại + OTP của Shopee."
                    )
                break
            except Exception as exc:  # noqa: BLE001
                if channel == "chrome":
                    print(f"Không mở được Chrome trên máy ({exc}); thử Chromium bundled.")
                else:
                    print(f"Không mở được browser nào: {exc}", file=sys.stderr)
                    return 2
        assert browser is not None

        ctx = await browser.new_context(
            locale="vi-VN", viewport={"width": 1366, "height": 900}
        )
        page = await ctx.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print(f"\nĐăng nhập Shopee trong cửa sổ vừa mở (tối đa {args.wait_seconds}s).")
        print("Script tự nhận ra khi xong — không cần bấm gì ở terminal.\n")

        if not await _wait_for_login(ctx, args.wait_seconds):
            print(
                "\nHết thời gian chờ mà chưa thấy cookie phiên. Không gửi gì đi.\n"
                "Kiểm tra: bạn có đăng nhập trong ĐÚNG cửa sổ script mở ra không?\n"
                "(Đăng nhập ở cửa sổ Chrome thường của bạn sẽ không được tính — hai\n"
                "cửa sổ dùng profile riêng, không chia sẻ cookie.)",
                file=sys.stderr,
            )
            await browser.close()
            return 1

        print("Đã thấy cookie phiên. Đang lấy thêm cookie phạm vi shop…")
        try:
            await page.goto(WARMUP_URL, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3_000)
        except Exception as exc:  # noqa: BLE001
            print(f"(Bỏ qua warm-up: {exc})")

        username = await _shopee_username(page)
        if username:
            print(f"Tài khoản Shopee: {username}")

        # Narrowed here, on the user's machine, so cookies for unrelated sites
        # never leave it in the first place.
        state = narrow_storage_state(await ctx.storage_state())
        await browser.close()

    print(f"Đã lấy {len(state['cookies'])} cookie của shopee.vn.")

    if args.save_to:
        out = Path(args.save_to)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        print(f"Đã lưu ra {out.resolve()} (KHÔNG upload).")
        print("File này là credential — đừng commit, đừng gửi cho ai.")
        return 0

    ok, message = await _upload(args.api, args.email, password or "", state, username)
    print(f"\nKết quả: {'OK' if ok else 'THẤT BẠI'} — {message}")
    if not ok:
        return 3
    print("Mở panel Theo dõi đối thủ và bấm 'Thu thập ngay' để lấy số liệu bán hàng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
