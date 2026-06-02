import { config } from "@/config";

import { discovery } from "./cognito";
import type { StoredTokens } from "./tokenStore";

// Exchange a refresh token for a fresh ID token at Cognito's /oauth2/token.
// Public client → no secret in the body. Cognito reuses the same refresh
// token (it's not rotated), so we keep the existing one.
export async function refreshTokens(
  current: StoredTokens,
): Promise<StoredTokens> {
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: config.cognitoClientId,
    refresh_token: current.refreshToken,
  });

  const res = await fetch(discovery().tokenEndpoint!, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!res.ok) {
    // 400 invalid_grant => refresh token expired/revoked. Caller signs out.
    throw new RefreshError(res.status);
  }

  const json = (await res.json()) as {
    id_token: string;
    expires_in: number;
    refresh_token?: string;
  };

  return {
    idToken: json.id_token,
    refreshToken: json.refresh_token ?? current.refreshToken,
    expiresAt: Date.now() + json.expires_in * 1000,
  };
}

export class RefreshError extends Error {
  status: number;
  constructor(status: number) {
    super(`Token refresh failed (${status})`);
    this.name = "RefreshError";
    this.status = status;
  }
}
