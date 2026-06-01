import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";

/**
 * Server-side proxy to FastAPI `/admin/usage/overview`.
 *
 * Admin-only on the backend: FastAPI 403s any caller whose user row isn't
 * flagged is_admin, so this route doesn't re-check — it just forwards the
 * verified token and relays the status.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // Pass through `days` (the backend validates the range).
  const days = request.nextUrl.searchParams.get("days") ?? "30";
  const url = `${AGENT_API_URL}/admin/usage/overview?days=${encodeURIComponent(days)}`;

  try {
    const res = await fetch(url, { cache: "no-store", headers });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: "Could not reach the usage service." },
      { status: 502 },
    );
  }
}
