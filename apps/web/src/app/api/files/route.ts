import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side proxy to the Python file-management API.
 *
 * GET    /api/files            → list objects under the case prefix
 * DELETE /api/files?key=<key>  → delete one object
 *
 * The browser never talks to the agent service directly; keeping the
 * proxy here lets us hide the agent URL and avoid CORS in dev.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const res = await fetch(`${AGENT_API_URL}/files`, { cache: "no-store" });
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
  try {
    const res = await fetch(
      `${AGENT_API_URL}/files?key=${encodeURIComponent(key)}`,
      { method: "DELETE" },
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
