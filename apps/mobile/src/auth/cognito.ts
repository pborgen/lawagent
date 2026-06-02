import {
  AuthRequest,
  makeRedirectUri,
  type DiscoveryDocument,
} from "expo-auth-session";

import { config } from "@/config";

// Cognito Hosted UI endpoints, derived from the configured domain. We hand
// these to expo-auth-session as a discovery document instead of fetching
// /.well-known (Cognito's OIDC config URL works too, but the three endpoints
// are stable and avoid an extra round trip).
export function discovery(): DiscoveryDocument {
  return {
    authorizationEndpoint: `${config.cognitoDomain}/oauth2/authorize`,
    tokenEndpoint: `${config.cognitoDomain}/oauth2/token`,
    endSessionEndpoint: `${config.cognitoDomain}/logout`,
  };
}

// lawagent://callback — captured by the app as a deep link. makeRedirectUri
// also handles the Expo Go / dev-client variants automatically.
export function redirectUri(): string {
  return makeRedirectUri({ scheme: config.scheme, path: "callback" });
}

// Build the PKCE authorization request. `identity_provider=Google` forces
// Cognito straight to Google, skipping its IdP chooser (the pool only
// federates Google anyway).
export function buildAuthRequest(): AuthRequest {
  return new AuthRequest({
    clientId: config.cognitoClientId,
    scopes: ["openid", "email", "profile"],
    redirectUri: redirectUri(),
    usePKCE: true,
    extraParams: { identity_provider: "Google" },
  });
}

// URL to drop the Hosted UI session cookie on sign-out, so the next sign-in
// re-prompts rather than silently reusing the browser session.
export function logoutUrl(): string {
  const params = new URLSearchParams({
    client_id: config.cognitoClientId,
    logout_uri: redirectUri(),
  });
  return `${config.cognitoDomain}/logout?${params.toString()}`;
}
