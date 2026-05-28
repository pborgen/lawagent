import "server-only";

import { cache } from "react";

import { getAuthConfig } from "@/lib/auth/config";
import { refreshTokens } from "@/lib/auth/cognito";
import {
  readSessionCookie,
  writeSessionCookie,
  type SessionData,
} from "@/lib/auth/session";

/**
 * Data Access Layer (per Next 16 docs §Authentication).
 *
 * Every server-side path that needs to know "who is this" reads from
 * here. The `cache(...)` wrapper memoizes the result for one render
 * pass, so multiple components/route handlers in the same request share
 * one cookie read + one possible token refresh.
 */

const REFRESH_SKEW_SECONDS = 60;

export type CurrentSession =
  | { ok: true; session: SessionData; idToken: string }
  | { ok: false; reason: "disabled" | "missing" | "refresh_failed" };

export const getSession = cache(async (): Promise<CurrentSession> => {
  if (getAuthConfig().authDisabled) {
    // Synthetic session — proxy/UI treat this as "signed in" without
    // a real Cognito token. API proxy routes detect this and skip the
    // Authorization header so the FastAPI side can also short-circuit.
    return {
      ok: false,
      reason: "disabled",
    };
  }

  const session = await readSessionCookie();
  if (!session) return { ok: false, reason: "missing" };

  // Refresh proactively a minute before expiry so the token forwarded
  // to FastAPI is never about to die mid-request.
  const now = Math.floor(Date.now() / 1000);
  if (session.idTokenExpiresAt > now + REFRESH_SKEW_SECONDS) {
    return { ok: true, session, idToken: session.idToken };
  }

  try {
    const refreshed = await refreshTokens(session.refreshToken);
    if (!refreshed) return { ok: false, reason: "refresh_failed" };
    const next: SessionData = {
      sub: session.sub,
      email: session.email,
      idToken: refreshed.idToken,
      refreshToken: refreshed.refreshToken,
      idTokenExpiresAt: refreshed.idTokenExpiresAt,
    };
    await writeSessionCookie(next);
    return { ok: true, session: next, idToken: refreshed.idToken };
  } catch {
    return { ok: false, reason: "refresh_failed" };
  }
});

/** Server-component-friendly: returns email (or null) without throwing. */
export async function getCurrentEmail(): Promise<string | null> {
  if (getAuthConfig().authDisabled) return "dev@localhost";
  const s = await getSession();
  return s.ok ? s.session.email : null;
}
