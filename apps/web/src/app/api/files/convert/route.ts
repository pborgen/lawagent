import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";
import { readActiveProjectId } from "@/lib/projects/active";

/**
 * Server-side proxy: convert a project PDF to Word (.docx).
 *
 * POST /api/files/convert  body { key }
 *
 * Mirrors presign-upload: the browser sends only the source key, and we
 * inject the active project_id from the cookie so the client stays
 * project-agnostic. The backend writes the .docx into the same project
 * prefix and returns its key/name plus a `scanned` flag.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const projectId = await readActiveProjectId();
  if (!projectId) {
    return NextResponse.json(
      { error: "No project selected. Choose one from /projects." },
      { status: 400 },
    );
  }

  const headers = await buildBackendHeaders({ "Content-Type": "application/json" });
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const forwarded = { ...body, project_id: projectId };

  try {
    const res = await fetch(`${AGENT_API_URL}/files/convert`, {
      method: "POST",
      headers,
      body: JSON.stringify(forwarded),
    });
    const text = await res.text();
    return new NextResponse(text, {
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
