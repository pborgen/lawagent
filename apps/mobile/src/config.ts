import Constants from "expo-constants";

// Typed accessor over the `extra` block populated in app.config.ts. Reading
// config through here (rather than process.env scattered everywhere) keeps a
// single, typed source of truth — mirroring the repo's packages/settings rule.
type Extra = {
  apiUrl: string;
  cognitoDomain: string;
  cognitoClientId: string;
  scheme: string;
  authDisabled: boolean;
};

const extra = (Constants.expoConfig?.extra ?? {}) as Partial<Extra>;

export const config = {
  apiUrl: (extra.apiUrl ?? "http://localhost:8000").replace(/\/$/, ""),
  cognitoDomain: (extra.cognitoDomain ?? "").replace(/\/$/, ""),
  cognitoClientId: extra.cognitoClientId ?? "",
  scheme: extra.scheme ?? "lawagent",
  authDisabled: extra.authDisabled === true,
} as const;

export function assertCognitoConfigured(): void {
  if (!config.cognitoDomain || !config.cognitoClientId) {
    throw new Error(
      "Cognito is not configured. Set EXPO_PUBLIC_COGNITO_DOMAIN and " +
        "EXPO_PUBLIC_COGNITO_CLIENT_ID in apps/mobile/.env (or use " +
        "EXPO_PUBLIC_AUTH_DISABLED=true for local dev).",
    );
  }
}
