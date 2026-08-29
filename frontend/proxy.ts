import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE, claimsValid, decodeJwtPayload } from "@/lib/auth-token";

/** UX routing only. API authorization remains the security boundary. */
export function proxy(req: NextRequest) {
  const token = req.cookies.get(TOKEN_COOKIE)?.value;
  const claims = token ? decodeJwtPayload(token) : null;

  if (!claimsValid(claims)) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }

  const role = claims!.role;
  const path = req.nextUrl.pathname;
  const onboardingPaths = new Set(["/seller/onboarding", "/seller/workspace"]);
  if (onboardingPaths.has(path)) return NextResponse.next();

  if (role !== "seller" && role !== "admin") {
    const url = req.nextUrl.clone();
    url.pathname = "/seller/onboarding";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (path === "/seller/content-generator" || path === "/seller/seller-coach") {
    return NextResponse.next();
  }

  if (role !== "admin") {
    const url = req.nextUrl.clone();
    url.pathname = "/seller/workspace";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = { matcher: ["/seller", "/seller/:path*"] };
