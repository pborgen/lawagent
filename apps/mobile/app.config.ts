import type { ExpoConfig } from "expo/config";

// Expo app config as TypeScript so we can read environment at build time.
// Only EXPO_PUBLIC_* vars are inlined into the client bundle — that's fine
// here because the native Cognito client is public (no secret).
const scheme = process.env.EXPO_PUBLIC_SCHEME ?? "lawagent";

const config: ExpoConfig = {
  name: "Lawagent",
  slug: "lawagent-mobile",
  version: "0.1.0",
  orientation: "portrait",
  scheme,
  userInterfaceStyle: "automatic",
  newArchEnabled: true,
  ios: {
    bundleIdentifier: "com.pborgen.lawagent",
    supportsTablet: false,
  },
  plugins: ["expo-router", "expo-secure-store"],
  experiments: {
    typedRoutes: true,
  },
  // Surfaced to the app via expo-constants (see src/config.ts).
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000",
    cognitoDomain: process.env.EXPO_PUBLIC_COGNITO_DOMAIN ?? "",
    cognitoClientId: process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID ?? "",
    scheme,
    authDisabled: process.env.EXPO_PUBLIC_AUTH_DISABLED === "true",
  },
};

export default config;
