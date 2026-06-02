import * as SecureStore from "expo-secure-store";

// Tokens live in the iOS Keychain (encrypted at rest), never AsyncStorage.
// We store one JSON blob under a single key.
const KEY = "lawagent.tokens";

export type StoredTokens = {
  idToken: string;
  refreshToken: string;
  // Absolute expiry of the ID token, in epoch milliseconds.
  expiresAt: number;
};

export async function loadTokens(): Promise<StoredTokens | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredTokens;
    if (!parsed.idToken || !parsed.refreshToken) return null;
    return parsed;
  } catch {
    return null;
  }
}

export async function saveTokens(tokens: StoredTokens): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(tokens), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}
