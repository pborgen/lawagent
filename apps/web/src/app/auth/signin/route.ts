import { NextResponse, type NextRequest } from "next/server";

import { getAuthConfig } from "@/lib/auth/config";
import {
  buildAuthorizeUrl,
  generateRandomToken,
  pkceChallenge,
} from "@/lib/auth/cognito";
import {
  OIDC_COOKIES,
  OIDC_COOKIE_MAX_AGE_SECONDS,
} from "@/lib/auth/oidc-cookies";

/**
 * Step 1 of the OIDC code flow.
 *
 *   1. Mint a fresh `state`, `nonce`, and PKCE `code_verifier`.
 *   2. Stash them in short-lived httpOnly cookies so /auth/callback can
 *      verify the response (state) and the ID token (nonce, PKCE).
 *   3. Redirect the browser to the Cognito Hosted UI's authorize
 *      endpoint, which itself jumps straight to Google.
 *
 * `returnTo` lets the caller send the user back to a specific path
 * after sign-in (e.g. /chat or /files). Defaulted to "/".
 */

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  if (getAuthConfig().authDisabled) {
    const returnTo = request.nextUrl.searchParams.get("returnTo") || "/";
    return NextResponse.redirect(new URL(returnTo, request.url));
  }

  const state = generateRandomToken();
  const nonce = generateRandomToken();
  const codeVerifier = generateRandomToken();
  const codeChallenge = await pkceChallenge(codeVerifier);
  const returnTo = request.nextUrl.searchParams.get("returnTo") || "/";

  const res = NextResponse.redirect(
    buildAuthorizeUrl({ state, codeChallenge, nonce }),
  );

  // These only need to survive the round-trip through Cognito + Google.
  const opts = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: OIDC_COOKIE_MAX_AGE_SECONDS,
  };
  res.cookies.set(OIDC_COOKIES.state, state, opts);
  res.cookies.set(OIDC_COOKIES.nonce, nonce, opts);
  res.cookies.set(OIDC_COOKIES.verifier, codeVerifier, opts);
  // Avoid open-redirect: only persist relative paths.
  if (returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    res.cookies.set(OIDC_COOKIES.returnTo, returnTo, opts);
  }
  return res;
}
