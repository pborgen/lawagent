import "server-only";

import { cookies } from "next/headers";

/**
 * Tracks which project the user is currently working in.
 *
 * Stored in a separate, *unencrypted* cookie because:
 *   - It carries no secret: just a UUID the backend re-verifies
 *     ownership on every request.
 *   - Keeping it out of the encrypted session cookie means changing
 *     projects doesn't churn the session, and the value survives the
 *     refresh-token rotation flow in `dal.ts`.
 *
 * The backend remains the authority — every files/* call passes the
 * project_id through and FastAPI rejects any UUID the caller doesn't own.
 */
export const ACTIVE_PROJECT_COOKIE = "lawagent.activeProject";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function readActiveProjectId(): Promise<string | null> {
  const store = await cookies();
  const value = store.get(ACTIVE_PROJECT_COOKIE)?.value;
  if (!value || !UUID_RE.test(value)) return null;
  return value;
}

export async function writeActiveProjectId(projectId: string): Promise<void> {
  if (!UUID_RE.test(projectId)) {
    throw new Error("Invalid project id.");
  }
  const store = await cookies();
  store.set(ACTIVE_PROJECT_COOKIE, projectId, {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
}

export async function clearActiveProjectId(): Promise<void> {
  const store = await cookies();
  store.delete(ACTIVE_PROJECT_COOKIE);
}
