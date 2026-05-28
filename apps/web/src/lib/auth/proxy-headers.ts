import "server-only";

import { getAuthConfig } from "@/lib/auth/config";
import { getSession } from "@/lib/auth/dal";

/**
 * Build headers for a forwarded request to the FastAPI backend.
 *
 * - Auth enabled + valid session  → adds `Authorization: Bearer <id_token>`
 * - Auth enabled + no session     → returns null; caller must respond 401
 * - Auth disabled                 → no Authorization header (FastAPI is
 *   running with LAWAGENT_AUTH_DISABLED in this dev path too)
 */
export async function buildBackendHeaders(
  extra: Record<string, string> = {},
): Promise<Record<string, string> | null> {
  if (getAuthConfig().authDisabled) {
    return { ...extra };
  }
  const session = await getSession();
  if (!session.ok) return null;
  return {
    ...extra,
    Authorization: `Bearer ${session.idToken}`,
  };
}
