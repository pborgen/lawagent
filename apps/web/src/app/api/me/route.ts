import { NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";

/**
 * Server-side proxy to FastAPI `/me`.
 *
 * Returns the authenticated user's identity and admin flag so the client
 * can decide whether to show admin-only UI. FastAPI re-verifies the token.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    const res = await fetch(`${AGENT_API_URL}/me`, {
      cache: "no-store",
      headers,
    });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: "Could not reach the user service." },
      { status: 502 },
    );
  }
}
