import { NextResponse, type NextRequest } from "next/server";

import { exchangeAuthorizationCode } from "@/lib/auth/cognito";
import { getAuthConfig } from "@/lib/auth/config";
import {
  OIDC_COOKIES,
} from "@/lib/auth/oidc-cookies";
import { writeSessionCookie } from "@/lib/auth/session";

/**
 * Step 2 of the OIDC code flow.
 *
 * Cognito redirects the browser here with a `code` + `state`. We:
 *   1. Pull the expected state/nonce/PKCE-verifier from the cookies set
 *      by /auth/signin.
 *   2. Exchange the code for tokens (oauth4webapi verifies the ID
 *      token's signature, audience, issuer, and nonce).
 *   3. Stash the verified ID + refresh tokens in the encrypted session
 *      cookie.
 *   4. Bounce the user back to the original `returnTo` path (or `/`).
 *
 * Any failure clears the handshake cookies and redirects to a small
 * error page; we never echo the raw error back to the user.
 */

export const dynamic = "force-dynamic";

function bounceError(request: NextRequest, message: string) {
  const url = new URL("/auth/error", request.url);
  url.searchParams.set("reason", message);
  const res = NextResponse.redirect(url);
  res.cookies.delete(OIDC_COOKIES.state);
  res.cookies.delete(OIDC_COOKIES.nonce);
  res.cookies.delete(OIDC_COOKIES.verifier);
  res.cookies.delete(OIDC_COOKIES.returnTo);
  return res;
}

export async function GET(request: NextRequest) {
  if (getAuthConfig().authDisabled) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  const expectedState = request.cookies.get(OIDC_COOKIES.state)?.value;
  const expectedNonce = request.cookies.get(OIDC_COOKIES.nonce)?.value;
  const codeVerifier = request.cookies.get(OIDC_COOKIES.verifier)?.value;
  const returnTo = request.cookies.get(OIDC_COOKIES.returnTo)?.value || "/";

  if (!expectedState || !expectedNonce || !codeVerifier) {
    // No handshake cookies → either a stale callback URL or a CSRF
    // attempt. Either way, restart the flow.
    return bounceError(request, "session_expired");
  }

  let tokens;
  try {
    tokens = await exchangeAuthorizationCode({
      code: request.nextUrl.searchParams.get("code") ?? "",
      expectedState,
      expectedNonce,
      codeVerifier,
      callbackUrl: request.nextUrl,
    });
  } catch (err) {
    console.error("OIDC callback failed:", err);
    return bounceError(request, "token_exchange_failed");
  }

  const email = String(tokens.claims.email ?? "").toLowerCase();
  if (!email) {
    return bounceError(request, "no_email_claim");
  }

  await writeSessionCookie({
    sub: String(tokens.claims.sub),
    email,
    idToken: tokens.idToken,
    refreshToken: tokens.refreshToken,
    idTokenExpiresAt: tokens.idTokenExpiresAt,
  });

  const res = NextResponse.redirect(new URL(returnTo, request.url));
  res.cookies.delete(OIDC_COOKIES.state);
  res.cookies.delete(OIDC_COOKIES.nonce);
  res.cookies.delete(OIDC_COOKIES.verifier);
  res.cookies.delete(OIDC_COOKIES.returnTo);
  return res;
}
