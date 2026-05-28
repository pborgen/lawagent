/**
 * Short-lived httpOnly cookies that carry OIDC handshake state between
 * /auth/signin and /auth/callback. They never live beyond a single
 * sign-in flow (max 5 minutes).
 */

export const OIDC_COOKIES = {
  state: "lawagent.oidc.state",
  nonce: "lawagent.oidc.nonce",
  verifier: "lawagent.oidc.pkce",
  returnTo: "lawagent.oidc.return",
} as const;

export const OIDC_COOKIE_MAX_AGE_SECONDS = 5 * 60;
