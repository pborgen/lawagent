import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/auth/session";

/**
 * Optimistic auth gate — runs on every request, on the Edge.
 *
 * We deliberately do NOT decrypt the session cookie here:
 *   - Cookie crypto in Edge runtime is fast but still adds latency on
 *     every prefetch/static request.
 *   - The real authorization check lives in /api/* routes (which
 *     forward to FastAPI, which verifies the JWT) and in server
 *     components that call `getSession()` from the DAL.
 *
 * So this proxy only does coarse routing: "is there *any* session
 * cookie? if not, redirect to /auth/signin." A forged cookie still
 * fails real verification downstream.
 *
 * AUTH_DISABLED=true makes this a no-op so dev work doesn't require
 * sign-in.
 */

// Routes the gate should NOT touch.
//  - /auth/* : sign-in flow itself
//  - /_next/* : framework assets
//  - /api/health (we don't have one, but if added would belong here)
//  - /brand/*, favicon, public files
//  - "/" : landing page (marketing) is publicly readable
const PUBLIC_PATH_PREFIXES = ["/auth/", "/_next/", "/brand/"];
const PUBLIC_PATH_EXACT = new Set(["/", "/favicon.ico"]);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATH_EXACT.has(pathname)) return true;
  return PUBLIC_PATH_PREFIXES.some((p) => pathname.startsWith(p));
}

export function proxy(request: NextRequest): NextResponse {
  // Hot path: bypass the gate entirely when AUTH_DISABLED is set so
  // dev work doesn't require sign-in. We don't import getAuthConfig
  // here because the proxy runs on the Edge and we want zero
  // dependencies + zero env-validation cost on every request.
  if (process.env.AUTH_DISABLED === "true") {
    return NextResponse.next();
  }

  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) return NextResponse.next();

  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  // /api/* with no session: respond 401 instead of redirecting, so
  // client-side fetches get a clean error instead of HTML.
  if (pathname.startsWith("/api/")) {
    return new NextResponse(JSON.stringify({ error: "unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const url = new URL("/auth/signin", request.url);
  url.searchParams.set("returnTo", `${pathname}${search}`);
  return NextResponse.redirect(url);
}

export const config = {
  // Run on everything except framework assets and public files.
  matcher: ["/((?!_next/static|_next/image|brand/|.*\\.(?:png|jpg|svg|ico)$).*)"],
};
