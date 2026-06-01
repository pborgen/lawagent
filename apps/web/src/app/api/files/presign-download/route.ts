import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";
import { readActiveProjectId } from "@/lib/projects/active";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "Missing key." }, { status: 400 });
  }
  const projectId = await readActiveProjectId();
  if (!projectId) {
    return NextResponse.json(
      { error: "No project selected. Choose one from /projects." },
      { status: 400 },
    );
  }
  const headers = await buildBackendHeaders();
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    const res = await fetch(
      `${AGENT_API_URL}/files/presign-download?project_id=${encodeURIComponent(projectId)}&key=${encodeURIComponent(key)}`,
      { cache: "no-store", headers },
    );
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
