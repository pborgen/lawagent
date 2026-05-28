import "server-only";

/**
 * Single source of truth for auth env vars.
 *
 * - `authDisabled === true` short-circuits sign-in checks and stands in
 *   a synthetic dev user. Local dev only — production env never sets it.
 * - When auth is enabled, all six Cognito values are required. We fail
 *   loudly at first access rather than returning a partially-broken config.
 */

const TRUTHY = new Set(["1", "true", "yes", "on"]);

function bool(value: string | undefined): boolean {
  return TRUTHY.has((value ?? "").trim().toLowerCase());
}

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required env var ${name}. ` +
        `Set it in apps/web/.env.local — or set AUTH_DISABLED=true for local dev.`,
    );
  }
  return value;
}

const authDisabled = bool(process.env.AUTH_DISABLED);

/** Public surface used by the rest of the auth layer. */
export type AuthConfig = {
  authDisabled: boolean;
  cognito: {
    region: string;
    userPoolId: string;
    clientId: string;
    clientSecret: string;
    /** Hosted UI base URL, e.g. https://x.auth.us-east-1.amazoncognito.com */
    domain: string;
    /** OIDC issuer; matches the `iss` claim in the ID token. */
    issuer: string;
    redirectUri: string;
    /** Where Cognito sends the user after logout. */
    postLogoutRedirectUri: string;
  };
  /** 32+ byte hex/base64 string used to encrypt the session cookie. */
  sessionSecret: string;
};

let cached: AuthConfig | null = null;

export function getAuthConfig(): AuthConfig {
  if (cached) return cached;

  if (authDisabled) {
    // Synthetic config — the OIDC fields are never read in this path,
    // but having concrete strings keeps the type honest.
    cached = {
      authDisabled: true,
      cognito: {
        region: "",
        userPoolId: "",
        clientId: "",
        clientSecret: "",
        domain: "",
        issuer: "",
        redirectUri: "",
        postLogoutRedirectUri: "",
      },
      sessionSecret: "auth-disabled-no-secret-needed",
    };
    return cached;
  }

  const region = required("COGNITO_REGION", process.env.COGNITO_REGION);
  const userPoolId = required("COGNITO_USER_POOL_ID", process.env.COGNITO_USER_POOL_ID);
  const clientId = required("COGNITO_CLIENT_ID", process.env.COGNITO_CLIENT_ID);
  const clientSecret = required("COGNITO_CLIENT_SECRET", process.env.COGNITO_CLIENT_SECRET);
  const domain = required("COGNITO_DOMAIN", process.env.COGNITO_DOMAIN).replace(/\/+$/, "");
  const redirectUri = required("COGNITO_REDIRECT_URI", process.env.COGNITO_REDIRECT_URI);
  const postLogoutRedirectUri = required(
    "COGNITO_LOGOUT_REDIRECT_URI",
    process.env.COGNITO_LOGOUT_REDIRECT_URI,
  );
  const sessionSecret = required("SESSION_SECRET", process.env.SESSION_SECRET);
  if (sessionSecret.length < 32) {
    throw new Error("SESSION_SECRET must be at least 32 characters.");
  }

  cached = {
    authDisabled: false,
    cognito: {
      region,
      userPoolId,
      clientId,
      clientSecret,
      domain,
      issuer: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`,
      redirectUri,
      postLogoutRedirectUri,
    },
    sessionSecret,
  };
  return cached;
}
