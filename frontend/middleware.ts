import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE, claimsValid, decodeJwtPayload } from "@/lib/auth-token";

/**
 * Keeps non-admins out of the seller portal at the routing layer, so they never
 * see a half-rendered dashboard.
 *
 * This is UX, NOT security. The payload is decoded WITHOUT verifying the
 * signature — the client must never hold JWT_SECRET. Anyone can hand-craft a
 * cookie claiming `role: "admin"` and reach /seller/*, but every panel's API
 * call still fails `require_admin` on the backend, so they'd see an empty
 * shell. The backend is the enforcement point.
 */
export function middleware(req: NextRequest) {
  const token = req.cookies.get(TOKEN_COOKIE)?.value;
  const claims = token ? decodeJwtPayload(token) : null;

  if (!claimsValid(claims)) {
    // Not signed in → log in, then come back to where they were headed.
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }

  if (claims!.role !== "admin") {
    // Signed in but not an admin → back to the shop with a reason. Sending a
    // valid buyer to a login form would be a dead end.
    const url = req.nextUrl.clone();
    url.pathname = "/shop";
    url.search = "?denied=seller";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = { matcher: ["/seller", "/seller/:path*"] };
