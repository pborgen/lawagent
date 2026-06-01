import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";
import { readActiveProjectId } from "@/lib/projects/active";

/**
 * Server-side proxy to the Python file-management API.
 *
 * GET    /api/files            → list objects in the active project
 * DELETE /api/files?key=<key>  → delete one object from the active project
 *
 * The active project_id comes from the cookie set by /api/projects/active.
 * The browser never sees or passes a project_id — every browser call is
 * implicitly scoped to whichever project the user has selected.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

async function requireActiveProject(): Promise<
  { ok: true; projectId: string } | { ok: false; res: NextResponse }
> {
  const projectId = await readActiveProjectId();
  if (!projectId) {
    return {
      ok: false,
      res: NextResponse.json(
        { error: "No project selected. Choose one from /projects." },
        { status: 400 },
      ),
    };
  }
  return { ok: true, projectId };
}

export async function GET() {
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const active = await requireActiveProject();
  if (!active.ok) return active.res;
  try {
    const res = await fetch(
      `${AGENT_API_URL}/files?project_id=${encodeURIComponent(active.projectId)}`,
      { cache: "no-store", headers },
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

export async function DELETE(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "Missing key." }, { status: 400 });
  }
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const active = await requireActiveProject();
  if (!active.ok) return active.res;
  try {
    const res = await fetch(
      `${AGENT_API_URL}/files?project_id=${encodeURIComponent(active.projectId)}&key=${encodeURIComponent(key)}`,
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
