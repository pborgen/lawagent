// Bridge between the React auth context and the plain-module API client.
// The api client (src/api/client.ts) is not a hook, so it can't read context
// directly. AuthContext registers these callbacks on mount; the client calls
// them to get a valid bearer token and to react to a 401.

type AuthBridge = {
  getValidIdToken: () => Promise<string>;
  forceRefresh: () => Promise<string>;
  onUnauthorized: () => void;
};

let bridge: AuthBridge | null = null;

export function registerAuthBridge(b: AuthBridge): void {
  bridge = b;
}

export function getAuthBridge(): AuthBridge {
  if (!bridge) {
    throw new Error("Auth bridge not registered yet (AuthProvider not mounted).");
  }
  return bridge;
}
