import "server-only";

import { cache } from "react";

import { getAuthConfig } from "@/lib/auth/config";
import { refreshTokens } from "@/lib/auth/cognito";
import { buildBackendHeaders } from "@/lib/auth/proxy-headers";
import {
  readSessionCookie,
  writeSessionCookie,
  type SessionData,
} from "@/lib/auth/session";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

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

export type CurrentUser = { sub: string; email: string; isAdmin: boolean };

/**
 * Fetch the caller's identity + admin flag from FastAPI `/me`.
 *
 * Used to gate the admin dashboard server-side. Returns null when the
 * caller isn't authenticated or the backend is unreachable — callers
 * treat null as "not an admin" and never surface admin UI. Memoized per
 * render so the page guard and the nav link share one round-trip.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  const headers = await buildBackendHeaders();
  if (!headers) return null; // auth enabled but no session
  try {
    const res = await fetch(`${AGENT_API_URL}/me`, {
      cache: "no-store",
      headers,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      sub?: string;
      email?: string;
      is_admin?: boolean;
    };
    if (!data.sub || !data.email) return null;
    return { sub: data.sub, email: data.email, isAdmin: Boolean(data.is_admin) };
  } catch {
    return null;
  }
});
