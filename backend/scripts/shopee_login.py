"""Capture a Shopee session once, so the collector can read sales figures.

    python scripts/shopee_login.py

Opens a real Chrome window at Shopee's login page. Log in by hand — password,
OTP, CAPTCHA, whatever it asks — then press Enter in this terminal. The cookies
are written to the path in COMPETITOR_SESSION_PATH (default
`var/shopee_session.json`), which is gitignored.

READ THIS FIRST
---------------
Shopee's terms prohibit automated access. The account whose session you capture
here can be rate-limited, CAPTCHA-walled, or banned. **Use a throwaway account,
not the one you sell from.** The session also expires — when the collector starts
reporting "session đã hết hạn", run this again.

Nothing here defeats a security control: you log in yourself, in a visible
browser, with your own credentials. The script only persists the cookie jar that
login produced.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402

LOGIN_URL = "https://shopee.vn/buyer/login"
#: Where we send you after login so the session picks up the cookies the shop
#: pages need, not just the login domain's.
WARMUP_URL = "https://shopee.vn/"


async def main() -> int:
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

    out = Path(settings.COMPETITOR_SESSION_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("CẢNH BÁO: Shopee cấm truy cập tự động. Account dùng ở đây có thể bị")
    print("giới hạn hoặc ban. Hãy dùng account phụ, KHÔNG dùng account bán hàng.")
    print("=" * 70)
    if input("Tiếp tục? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Đã huỷ.")
        return 1

    async with async_playwright() as pw:
        # Headed on purpose: you are the one logging in.
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(
            locale="vi-VN", viewport={"width": 1366, "height": 900}
        )
        page = await ctx.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("\nCửa sổ Chrome đã mở. Đăng nhập Shopee trong đó.")
        print("Xong thì quay lại đây và bấm Enter.")
        # input() blocks the event loop; run it off-thread so the browser stays
        # responsive while you type your password into it.
        await asyncio.get_running_loop().run_in_executor(None, input)

        # Visit the storefront so shop-scoped cookies land in the jar too.
        try:
            await page.goto(WARMUP_URL, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3_000)
        except Exception as exc:  # noqa: BLE001
            print(f"(Bỏ qua warm-up: {exc})")

        body = (await page.inner_text("body")).lower()
        if "đăng nhập" in body and "đăng xuất" not in body:
            print(
                "\nCẢNH BÁO: trang vẫn còn nút Đăng nhập — có thể chưa login xong.\n"
                "Vẫn lưu session, nhưng nếu collector báo hết hạn thì chạy lại script này.",
                file=sys.stderr,
            )

        await ctx.storage_state(path=str(out))
        await browser.close()

    print(f"\nĐã lưu session vào {out.resolve()}")
    print("Bật trong backend/.env:")
    print("  COMPETITOR_USE_SESSION=true")
    print(f"  COMPETITOR_SESSION_PATH={settings.COMPETITOR_SESSION_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
