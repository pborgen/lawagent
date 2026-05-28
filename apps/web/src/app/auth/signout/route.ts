import { NextResponse, type NextRequest } from "next/server";

import { buildLogoutUrl } from "@/lib/auth/cognito";
import { getAuthConfig } from "@/lib/auth/config";
import { SESSION_COOKIE } from "@/lib/auth/session";

/**
 * Sign-out is a two-stage thing:
 *  1. Clear our session cookie (this server's record of "signed in").
 *  2. Bounce the browser through Cognito's /logout, which clears the
 *     Hosted-UI session and then redirects back to
 *     COGNITO_LOGOUT_REDIRECT_URI.
 *
 * POST-only so a stray prefetch can't sign the user out.
 */

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (getAuthConfig().authDisabled) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  const res = NextResponse.redirect(buildLogoutUrl());
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
