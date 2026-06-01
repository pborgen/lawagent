"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import BrandLogo from "@/components/BrandLogo";

type Project = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  matter_type: string | null;
  created_at: string;
  updated_at: string;
};

const MATTER_TYPES = [
  { value: "divorce", label: "Divorce" },
  { value: "custody", label: "Custody" },
  { value: "child_support", label: "Child support" },
  { value: "post_judgment", label: "Post-judgment" },
  { value: "other", label: "Other" },
];

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function ProjectsClient() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [matterType, setMatterType] = useState<string>("divorce");
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [projectsRes, activeRes] = await Promise.all([
        fetch("/api/projects", { cache: "no-store" }),
        fetch("/api/projects/active", { cache: "no-store" }),
      ]);
      const projectsData = await projectsRes.json();
      if (!projectsRes.ok) {
        throw new Error(
          projectsData.detail ?? projectsData.error ?? "Could not load projects.",
        );
      }
      const activeData = await activeRes.json().catch(() => ({}));
      setProjects(projectsData.items ?? []);
      setActiveId(activeData.projectId ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load projects.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount: refresh() sets loading/error state. Intentional;
    // exempt from the cascading-render rule.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          matter_type: matterType || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? data.error ?? "Could not create project.");
      }
      setName("");
      setDescription("");
      setMatterType("divorce");
      // Auto-select the brand-new project so the user can jump into files right away.
      await fetch("/api/projects/active", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId: data.id }),
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project.");
    } finally {
      setCreating(false);
    }
  }

  async function handleSelect(projectId: string) {
    setError(null);
    try {
      const res = await fetch("/api/projects/active", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? "Could not select project.");
      }
      setActiveId(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not select project.");
    }
  }

  async function handleDelete(project: Project) {
    if (
      !confirm(
        `Delete "${project.name}"? Files for this project will remain in S3 until garbage-collected.`,
      )
    ) {
      return;
    }
    try {
      const res = await fetch(`/api/projects/${project.id}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? data.error ?? "Could not delete.");
      }
      if (activeId === project.id) {
        await fetch("/api/projects/active", { method: "DELETE" });
        setActiveId(null);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete project.");
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#1e293b_0%,#0f172a_38%,#020617_100%)] text-slate-50">
      <div className="mx-auto flex w-full max-w-4xl flex-col px-4 pb-16 pt-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-20 -mx-4 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
            <BrandLogo href="/" />
            <nav className="flex items-center gap-4 text-sm text-slate-300">
              <Link className="hidden transition hover:text-white sm:inline" href="/files">
                Files
              </Link>
              <Link
                className="rounded-full bg-sky-400 px-3 py-1.5 font-semibold text-slate-950 transition hover:bg-sky-300"
                href="/chat"
              >
                Open assistant
              </Link>
            </nav>
          </div>
        </header>

        <section className="space-y-3 py-8 sm:py-12">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-400">
            Projects
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Your matters
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-300 sm:text-base sm:leading-7">
            Each project is a self-contained matter with its own files,
            drafts, and (later) its own slice of the assistant&rsquo;s
            knowledge base. Switch between them from the picker in the
            header.
          </p>
        </section>

        <section className="rounded-[2rem] border border-white/10 bg-white/5 p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-white">Create a project</h2>
          <p className="mt-1 text-sm text-slate-400">
            Start with a short name &mdash; you can edit the details later.
          </p>
          <form
            onSubmit={handleCreate}
            className="mt-4 space-y-3"
          >
            <label className="block">
              <span className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
                Project name
              </span>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Smith v. Smith — divorce"
                className="mt-1 w-full rounded-2xl border border-white/15 bg-slate-950/40 px-4 py-2 text-sm text-white outline-none transition focus:border-sky-400/60"
              />
            </label>

            <label className="block">
              <span className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
                Matter type
              </span>
              <select
                value={matterType}
                onChange={(e) => setMatterType(e.target.value)}
                className="mt-1 w-full rounded-2xl border border-white/15 bg-slate-950/40 px-4 py-2 text-sm text-white outline-none transition focus:border-sky-400/60"
              >
                {MATTER_TYPES.map((t) => (
                  <option key={t.value} value={t.value} className="bg-slate-900">
                    {t.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
                Description (optional)
              </span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder="Brief context — counsel, docket, key issues."
                className="mt-1 w-full rounded-2xl border border-white/15 bg-slate-950/40 px-4 py-2 text-sm text-white outline-none transition focus:border-sky-400/60"
              />
            </label>

            <div className="flex items-center justify-end">
              <button
                type="submit"
                disabled={creating || !name.trim()}
                className="rounded-full bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300 disabled:opacity-50"
              >
                {creating ? "Creating…" : "Create project"}
              </button>
            </div>
          </form>
        </section>

        {error ? (
          <p className="mt-6 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {error}
          </p>
        ) : null}

        <section className="mt-8 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">All projects</h2>
            <button
              type="button"
              onClick={refresh}
              className="text-xs text-slate-300 underline-offset-2 hover:underline"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : !projects || projects.length === 0 ? (
            <p className="rounded-2xl border border-white/10 bg-white/4 px-4 py-6 text-sm text-slate-300">
              You don&rsquo;t have any projects yet. Create one above.
            </p>
          ) : (
            <ul className="divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/60">
              {projects.map((project) => {
                const isActive = activeId === project.id;
                return (
                  <li
                    key={project.id}
                    className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-slate-100">
                          {project.name}
                        </p>
                        {isActive ? (
                          <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-sky-200">
                            Active
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {project.matter_type ?? "Unspecified"} · created{" "}
                        {formatDate(project.created_at)}
                      </p>
                      {project.description ? (
                        <p className="mt-2 max-w-xl text-xs text-slate-300">
                          {project.description}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {isActive ? (
                        <Link
                          href="/files"
                          className="rounded-full bg-sky-400 px-3 py-1 text-xs font-semibold text-slate-950 transition hover:bg-sky-300"
                        >
                          Open files
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleSelect(project.id)}
                          className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-white transition hover:border-white/35 hover:bg-white/5"
                        >
                          Select
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(project)}
                        className="rounded-full border border-rose-400/30 px-3 py-1 text-xs font-medium text-rose-100 transition hover:border-rose-400/60 hover:bg-rose-500/10"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
