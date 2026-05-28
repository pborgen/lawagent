import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";

/**
 * Server-side proxy to the Python file-management API.
 *
 * GET    /api/files            → list objects under the case prefix
 * DELETE /api/files?key=<key>  → delete one object
 *
 * Forwards the Cognito ID token to FastAPI. FastAPI re-verifies the
 * JWT and enforces the email allowlist.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    const res = await fetch(`${AGENT_API_URL}/files`, {
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
      { error: "Could not reach the file service." },
      { status: 502 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "Missing key." }, { status: 400 });
  }
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    const res = await fetch(
      `${AGENT_API_URL}/files?key=${encodeURIComponent(key)}`,
      { method: "DELETE", headers },
    );
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: "Could not reach the file service." },
      { status: 502 },
    );
  }
}
