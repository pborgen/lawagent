import "server-only";

import * as oauth from "oauth4webapi";

import { getAuthConfig } from "@/lib/auth/config";

/**
 * OIDC authorization-code flow against the Cognito Hosted UI.
 *
 * Cognito speaks standard OIDC but its discovery document is not always
 * stable, and we don't need it — every endpoint is a deterministic path
 * under the Hosted UI domain. Hand-rolling the URL construction keeps
 * cold-start latency lower and removes one network round trip per sign-in.
 */

function cognitoAs() {
  const { cognito } = getAuthConfig();
  // The `as` (Authorization Server) struct oauth4webapi expects.
  const as: oauth.AuthorizationServer = {
    issuer: cognito.issuer,
    authorization_endpoint: `${cognito.domain}/oauth2/authorize`,
    token_endpoint: `${cognito.domain}/oauth2/token`,
    userinfo_endpoint: `${cognito.domain}/oauth2/userInfo`,
    jwks_uri: `${cognito.issuer}/.well-known/jwks.json`,
    end_session_endpoint: `${cognito.domain}/logout`,
  };
  const client: oauth.Client = {
    client_id: cognito.clientId,
    token_endpoint_auth_method: "client_secret_basic",
  };
  const clientAuth = oauth.ClientSecretBasic(cognito.clientSecret);
  return { as, client, clientAuth };
}

/** Random base64url, used for `state` and PKCE `code_verifier`. */
export function generateRandomToken(): string {
  return oauth.generateRandomState();
}

export async function pkceChallenge(codeVerifier: string): Promise<string> {
  return oauth.calculatePKCECodeChallenge(codeVerifier);
}

export function buildAuthorizeUrl(opts: {
  state: string;
  codeChallenge: string;
  nonce: string;
}): string {
  const { cognito } = getAuthConfig();
  const url = new URL(`${cognito.domain}/oauth2/authorize`);
  url.searchParams.set("client_id", cognito.clientId);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid email profile");
  url.searchParams.set("redirect_uri", cognito.redirectUri);
  url.searchParams.set("state", opts.state);
  url.searchParams.set("nonce", opts.nonce);
  url.searchParams.set("code_challenge", opts.codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  // Skip Cognito's IdP-picker; jump straight to Google.
  url.searchParams.set("identity_provider", "Google");
  return url.toString();
}

export function buildLogoutUrl(): string {
  const { cognito } = getAuthConfig();
  const url = new URL(`${cognito.domain}/logout`);
  url.searchParams.set("client_id", cognito.clientId);
  url.searchParams.set("logout_uri", cognito.postLogoutRedirectUri);
  return url.toString();
}

export type TokenSet = {
  idToken: string;
  refreshToken: string;
  accessToken: string;
  /** UNIX seconds. */
  idTokenExpiresAt: number;
  /** Verified ID-token claims (signature/aud/iss/nonce all checked). */
  claims: oauth.IDToken;
};

/**
 * Exchange an authorization code for tokens, verifying the returned ID
 * token's signature, issuer, audience, and nonce.
 */
export async function exchangeAuthorizationCode(opts: {
  code: string;
  expectedState: string;
  expectedNonce: string;
  codeVerifier: string;
  callbackUrl: URL;
}): Promise<TokenSet> {
  const { as, client, clientAuth } = cognitoAs();
  const { cognito } = getAuthConfig();

  const params = oauth.validateAuthResponse(as, client, opts.callbackUrl, opts.expectedState);

  const tokenRes = await oauth.authorizationCodeGrantRequest(
    as,
    client,
    clientAuth,
    params,
    cognito.redirectUri,
    opts.codeVerifier,
  );

  const result = await oauth.processAuthorizationCodeResponse(as, client, tokenRes, {
    expectedNonce: opts.expectedNonce,
    requireIdToken: true,
  });

  const claims = oauth.getValidatedIdTokenClaims(result);
  if (!claims) {
    throw new Error("Cognito did not return a verifiable ID token.");
  }
  if (!result.id_token || !result.refresh_token || !result.access_token) {
    throw new Error("Cognito response missing id_token, access_token, or refresh_token.");
  }

  return {
    idToken: result.id_token,
    refreshToken: result.refresh_token,
    accessToken: result.access_token,
    idTokenExpiresAt: Number(claims.exp),
    claims,
  };
}

/**
 * Use the refresh token to mint a fresh ID/access token without a
 * round-trip through the Hosted UI. Cognito returns a new id_token +
 * access_token; refresh_token stays the same.
 */
export async function refreshTokens(refreshToken: string): Promise<TokenSet | null> {
  const { as, client, clientAuth } = cognitoAs();

  const tokenRes = await oauth.refreshTokenGrantRequest(as, client, clientAuth, refreshToken);
  const result = await oauth.processRefreshTokenResponse(as, client, tokenRes);

  if (!result.id_token || !result.access_token) return null;

  const claims = oauth.getValidatedIdTokenClaims(result);
  if (!claims) return null;

  return {
    idToken: result.id_token,
    refreshToken,
    accessToken: result.access_token,
    idTokenExpiresAt: Number(claims.exp),
    claims,
  };
}
