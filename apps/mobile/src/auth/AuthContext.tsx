import { exchangeCodeAsync } from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { config } from "@/config";
import type { Me } from "@/api/types";

import { registerAuthBridge } from "./bridge";
import {
  buildAuthRequest,
  discovery,
  redirectUri,
} from "./cognito";
import { RefreshError, refreshTokens } from "./refresh";
import {
  clearTokens,
  loadTokens,
  saveTokens,
  type StoredTokens,
} from "./tokenStore";

// Lets the system browser close itself and return to the app after the
// OAuth redirect (required by expo-auth-session on iOS).
WebBrowser.maybeCompleteAuthSession();

type Status = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: Status;
  user: Me | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  // Used by the API client; returns a non-expired ID token, refreshing first.
  getValidIdToken: () => Promise<string>;
  setUser: (me: Me) => void;
  error: string | null;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// Refresh this many ms before actual expiry so a request never races the cutoff.
const REFRESH_SKEW_MS = 120_000;

const DEV_TOKEN = "dev-auth-disabled";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Single in-memory copy of tokens; persisted to Keychain on every change.
  const tokensRef = useRef<StoredTokens | null>(null);
  // De-dupes concurrent refreshes into one network call.
  const refreshInFlight = useRef<Promise<string> | null>(null);

  const applyTokens = useCallback(async (t: StoredTokens) => {
    tokensRef.current = t;
    await saveTokens(t);
  }, []);

  const signOut = useCallback(async () => {
    tokensRef.current = null;
    await clearTokens();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const doRefresh = useCallback(async (): Promise<string> => {
    const current = tokensRef.current;
    if (!current) throw new RefreshError(401);
    if (refreshInFlight.current) return refreshInFlight.current;

    const p = (async () => {
      try {
        const next = await refreshTokens(current);
        await applyTokens(next);
        return next.idToken;
      } finally {
        refreshInFlight.current = null;
      }
    })();
    refreshInFlight.current = p;
    return p;
  }, [applyTokens]);

  const getValidIdToken = useCallback(async (): Promise<string> => {
    if (config.authDisabled) return DEV_TOKEN;
    const current = tokensRef.current;
    if (!current) throw new RefreshError(401);
    if (current.expiresAt - Date.now() > REFRESH_SKEW_MS) {
      return current.idToken;
    }
    return doRefresh();
  }, [doRefresh]);

  const signIn = useCallback(async () => {
    setError(null);
    if (config.authDisabled) {
      // Dev path: no real Cognito flow. The API (with auth disabled) returns
      // a synthetic user from /me, which the root layout fetches.
      setStatus("authenticated");
      return;
    }
    try {
      const request = buildAuthRequest();
      const result = await request.promptAsync(discovery());
      if (result.type !== "success" || !result.params.code) {
        if (result.type === "error") {
          setError(result.error?.message ?? "Sign-in failed.");
        }
        return;
      }
      const tokenResult = await exchangeCodeAsync(
        {
          clientId: config.cognitoClientId,
          code: result.params.code,
          redirectUri: redirectUri(),
          extraParams: request.codeVerifier
            ? { code_verifier: request.codeVerifier }
            : {},
        },
        discovery(),
      );
      if (!tokenResult.idToken || !tokenResult.refreshToken) {
        setError("Cognito did not return the expected tokens.");
        return;
      }
      await applyTokens({
        idToken: tokenResult.idToken,
        refreshToken: tokenResult.refreshToken,
        expiresAt:
          Date.now() + (tokenResult.expiresIn ?? 3600) * 1000,
      });
      setStatus("authenticated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed.");
    }
  }, [applyTokens]);

  // On launch: restore tokens from the Keychain (or dev bypass).
  useEffect(() => {
    let active = true;
    (async () => {
      if (config.authDisabled) {
        if (active) setStatus("authenticated");
        return;
      }
      const stored = await loadTokens();
      if (!active) return;
      if (stored) {
        tokensRef.current = stored;
        setStatus("authenticated");
      } else {
        setStatus("unauthenticated");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Register the bridge so the API client can fetch tokens / react to 401.
  useEffect(() => {
    registerAuthBridge({
      getValidIdToken,
      forceRefresh: doRefresh,
      onUnauthorized: () => {
        void signOut();
      },
    });
  }, [getValidIdToken, doRefresh, signOut]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, signIn, signOut, getValidIdToken, setUser, error }),
    [status, user, signIn, signOut, getValidIdToken, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
