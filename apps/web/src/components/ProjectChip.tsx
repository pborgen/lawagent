import Link from "next/link";

import { buildBackendHeaders } from "@/lib/auth/proxy-headers";
import { readActiveProjectId } from "@/lib/projects/active";

/**
 * Header chip showing which project is active, with a link to /projects
 * to switch. Server component — uses the verified session to fetch the
 * project name straight from the backend so the chip is always accurate.
 *
 * Failure modes are deliberate:
 *   - No active cookie  → "Choose a project" call-to-action.
 *   - Cookie points at a deleted/unowned project → "Unknown project"
 *     with a link to switch. The cookie is left in place; clearing it
 *     would race with the user navigating to /projects.
 */
const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

async function fetchProjectName(projectId: string): Promise<string | null> {
  const headers = await buildBackendHeaders();
  if (!headers) return null;
  try {
    const res = await fetch(`${AGENT_API_URL}/projects/${projectId}`, {
      cache: "no-store",
      headers,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { name?: string };
    return data.name ?? null;
  } catch {
    return null;
  }
}

export default async function ProjectChip() {
  const projectId = await readActiveProjectId();
  if (!projectId) {
    return (
      <Link
        href="/projects"
        className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1.5 text-xs font-medium text-amber-100 transition hover:border-amber-300/60"
      >
        Choose a project
      </Link>
    );
  }

  const name = await fetchProjectName(projectId);
  if (!name) {
    return (
      <Link
        href="/projects"
        className="rounded-full border border-rose-400/30 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-100 transition hover:border-rose-400/60"
      >
        Unknown project · Switch
      </Link>
    );
  }

  return (
    <Link
      href="/projects"
      title="Switch project"
      className="flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-white/35 hover:bg-white/10"
    >
      <span aria-hidden className="text-[10px] text-sky-300">●</span>
      <span className="max-w-[14rem] truncate">{name}</span>
    </Link>
  );
}
