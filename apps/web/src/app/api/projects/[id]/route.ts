import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";

/**
 * Server-side proxy for one project.
 *
 * GET    /api/projects/[id]
 * PATCH  /api/projects/[id]
 * DELETE /api/projects/[id]
 *
 * `[id]` is forwarded verbatim; the backend rejects non-UUIDs with 422
 * and unowned UUIDs with 404.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

type RouteContext = { params: Promise<{ id: string }> };

async function forward(
  method: "GET" | "PATCH" | "DELETE",
  id: string,
  body?: unknown,
) {
  const wantsBody = method !== "GET" && method !== "DELETE";
  const headers = wantsBody
    ? await buildBackendHeaders({ "Content-Type": "application/json" })
    : await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(`${AGENT_API_URL}/projects/${encodeURIComponent(id)}`, {
      method,
      headers,
      body: wantsBody && body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    if (res.status === 204) {
      // FastAPI returns 204 with no body for delete; preserve that shape.
      return new NextResponse(null, { status: 204 });
    }
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

export async function GET(_req: NextRequest, ctx: RouteContext) {
  const { id } = await ctx.params;
  return forward("GET", id);
}

export async function PATCH(request: NextRequest, ctx: RouteContext) {
  const { id } = await ctx.params;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  return forward("PATCH", id, body);
}

export async function DELETE(_req: NextRequest, ctx: RouteContext) {
  const { id } = await ctx.params;
  return forward("DELETE", id);
}
