import { NextRequest, NextResponse } from "next/server";

import {
  clearActiveProjectId,
  readActiveProjectId,
  writeActiveProjectId,
} from "@/lib/projects/active";

/**
 * Active-project cookie endpoints.
 *
 * GET    /api/projects/active            → { projectId: string | null }
 * POST   /api/projects/active            → set active project (body: { projectId })
 * DELETE /api/projects/active            → clear it
 *
 * Pure cookie I/O. No backend round-trip — the next /files call carries
 * the ID, and the backend verifies ownership there.
 */
export async function GET() {
  return NextResponse.json({ projectId: await readActiveProjectId() });
}

export async function POST(request: NextRequest) {
  let body: { projectId?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  if (typeof body.projectId !== "string") {
    return NextResponse.json(
      { error: "projectId is required." },
      { status: 400 },
    );
  }
  try {
    await writeActiveProjectId(body.projectId);
  } catch {
    return NextResponse.json(
      { error: "projectId is not a valid UUID." },
      { status: 400 },
    );
  }
  return NextResponse.json({ projectId: body.projectId });
}

export async function DELETE() {
  await clearActiveProjectId();
  return NextResponse.json({ projectId: null });
}
