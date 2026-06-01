import { NextRequest, NextResponse } from "next/server";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";
import { readActiveProjectId } from "@/lib/projects/active";

/**
 * Server-side proxy to the Python agent API (`apps/api`).
 *
 * The browser never talks to the Python service directly — it POSTs
 * here, and this route forwards to FastAPI with the user's verified
 * Cognito ID token as a Bearer credential. FastAPI re-verifies the
 * token against the Cognito JWKS on every call.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

const MODES = ["short", "memo", "annotate"] as const;
type Mode = (typeof MODES)[number];

// The LLM call can take a while; allow this handler to run longer than
// the platform default before timing out.
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  let body: { question?: unknown; mode?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const question =
    typeof body.question === "string" ? body.question.trim() : "";
  if (!question) {
    return NextResponse.json(
      { error: "A question is required." },
      { status: 400 },
    );
  }

  const mode: Mode = MODES.includes(body.mode as Mode)
    ? (body.mode as Mode)
    : "short";

  const headers = await buildBackendHeaders({ "Content-Type": "application/json" });
  if (!headers) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // Attribute this question's LLM usage to the active project, if any.
  // The backend re-verifies ownership and ignores an unowned/stale id.
  const projectId = await readActiveProjectId();

  try {
    const res = await fetch(`${AGENT_API_URL}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        question,
        mode,
        ...(projectId ? { project_id: projectId } : {}),
      }),
    });

    if (!res.ok) {
      const detail = await res.text();
      return NextResponse.json(
        { error: `The assistant returned an error (${res.status}). ${detail}` },
        { status: 502 },
      );
    }

    // FastAPI returns { answer, mode }.
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json(
      {
        error:
          "Could not reach the assistant service. Make sure the agent API " +
          "is running (lawagent-api).",
      },
      { status: 502 },
    );
  }
}
