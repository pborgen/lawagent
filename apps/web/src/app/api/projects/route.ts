import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";

/**
 * Server-side proxy for project CRUD.
 *
 * GET  /api/projects  → list the caller's projects
 * POST /api/projects  → create one
 *
 * Forwards the Cognito ID token to FastAPI. FastAPI re-verifies the
 * JWT and scopes every query to `owner_sub = <verified caller>`.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    const res = await fetch(`${AGENT_API_URL}/projects`, {
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
      { error: "Could not reach the projects service." },
      { status: 502 },
    );
  }
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const headers = await buildBackendHeaders({ "Content-Type": "application/json" });
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(`${AGENT_API_URL}/projects`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: "Could not reach the projects service." },
      { status: 502 },
    );
  }
}
