import "server-only";

import { cookies } from "next/headers";
import { EncryptJWT, jwtDecrypt } from "jose";

import { getAuthConfig } from "@/lib/auth/config";

/**
 * Session cookies, encrypted with the local SESSION_SECRET (JWE A256GCM).
 *
 * Why JWE and not the raw Cognito ID token in a cookie?
 *  - The cookie holds both the ID token *and* the refresh token; the
 *    refresh token must stay confidential to the server.
 *  - Encrypting locally means losing the cookie ≠ a compromised user — the
 *    attacker still needs SESSION_SECRET to decrypt.
 *  - All cookie reads happen server-side; this is never sent to the client
 *    as readable data.
 */

export const SESSION_COOKIE = "lawagent.sid";

export type SessionData = {
  /** Cognito 'sub' claim — stable user ID. */
  sub: string;
  email: string;
  /** Cognito ID token; forwarded to FastAPI as a Bearer credential. */
  idToken: string;
  /** Used to mint a new ID token when the current one expires. */
  refreshToken: string;
  /** Absolute UNIX seconds when idToken expires. */
  idTokenExpiresAt: number;
};

const ENC_ALG = "dir";
const ENC = "A256GCM";

function key(): Uint8Array {
  // jose wants exactly 32 bytes for A256GCM. Hash-truncate so any secret
  // ≥ 32 chars works; the hashing also lets a base64 secret slot in.
  const secret = getAuthConfig().sessionSecret;
  const raw = new TextEncoder().encode(secret);
  if (raw.byteLength === 32) return raw;
  // Simple truncation/padding — SESSION_SECRET is validated ≥ 32 chars
  // upstream, so we always have enough entropy to truncate.
  const out = new Uint8Array(32);
  out.set(raw.subarray(0, 32));
  return out;
}

export async function encryptSession(data: SessionData): Promise<string> {
  // Match the session lifetime to the refresh token's max age — Cognito's
  // refresh window is the real ceiling on how long this cookie can be useful.
  return new EncryptJWT({ ...data })
    .setProtectedHeader({ alg: ENC_ALG, enc: ENC })
    .setIssuedAt()
    .setExpirationTime("30d")
    .encrypt(key());
}

export async function decryptSession(token: string): Promise<SessionData | null> {
  try {
    const { payload } = await jwtDecrypt(token, key());
    return payload as unknown as SessionData;
  } catch {
    // Tampered, expired, or signed with an old SESSION_SECRET.
    return null;
  }
}

export async function writeSessionCookie(data: SessionData): Promise<void> {
  const value = await encryptSession(data);
  const store = await cookies();
  store.set(SESSION_COOKIE, value, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  });
}

export async function clearSessionCookie(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}

export async function readSessionCookie(): Promise<SessionData | null> {
  const store = await cookies();
  const raw = store.get(SESSION_COOKIE)?.value;
  if (!raw) return null;
  return decryptSession(raw);
}
