"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import BrandLogo from "@/components/BrandLogo";

type FileItem = {
  /** Full S3 key, e.g. "projects/<uuid>/drafts/motion.pdf". Round-tripped to the backend. */
  key: string;
  /** Project-relative path, e.g. "drafts/motion.pdf". What we display. */
  name: string;
  size: number;
  last_modified: string;
};

type CaseFileList = {
  bucket: string;
  /** S3 prefix the project's files live under, e.g. "projects/<uuid>/". */
  prefix: string;
  items: FileItem[];
};

type ActiveProject = {
  id: string;
  name: string;
  matter_type: string | null;
};

type Upload = {
  id: string;
  name: string;
  size: number;
  progress: number;
  status: "uploading" | "done" | "error";
  error?: string;
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

type FolderEntry = {
  name: string;
  fileCount: number;
  totalSize: number;
};

function partitionAtPath(
  items: FileItem[],
  path: string,
): { folders: FolderEntry[]; files: FileItem[] } {
  const folderMap = new Map<string, FolderEntry>();
  const files: FileItem[] = [];
  const normalized = path && !path.endsWith("/") ? `${path}/` : path;
  for (const item of items) {
    if (normalized && !item.key.startsWith(normalized)) continue;
    const rest = item.key.slice(normalized.length);
    if (!rest) continue;
    const slash = rest.indexOf("/");
    if (slash === -1) {
      files.push(item);
    } else {
      const name = rest.slice(0, slash);
      const entry = folderMap.get(name) ?? { name, fileCount: 0, totalSize: 0 };
      entry.fileCount += 1;
      entry.totalSize += item.size;
      folderMap.set(name, entry);
    }
  }
  const folders = Array.from(folderMap.values()).sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  return { folders, files };
}

export default function FilesClient() {
  const [list, setList] = useState<CaseFileList | null>(null);
  const [activeProject, setActiveProject] = useState<ActiveProject | null>(null);
  const [noActiveProject, setNoActiveProject] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [path, setPath] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const { folders, files } = useMemo(
    () => partitionAtPath(list?.items ?? [], path),
    [list, path],
  );
  const crumbs = path ? path.split("/").filter(Boolean) : [];

  const refresh = useCallback(async () => {
    setError(null);
    try {
      // Step 1: which project are we in?
      const activeRes = await fetch("/api/projects/active", { cache: "no-store" });
      const activeData = await activeRes.json().catch(() => ({}));
      const projectId: string | null = activeData.projectId ?? null;
      if (!projectId) {
        setActiveProject(null);
        setNoActiveProject(true);
        setList(null);
        return;
      }
      setNoActiveProject(false);

      // Step 2: project metadata + file list, in parallel.
      const [projectRes, filesRes] = await Promise.all([
        fetch(`/api/projects/${projectId}`, { cache: "no-store" }),
        fetch("/api/files", { cache: "no-store" }),
      ]);
      if (projectRes.ok) {
        const p = await projectRes.json();
        setActiveProject({
          id: p.id,
          name: p.name,
          matter_type: p.matter_type ?? null,
        });
      }
      const data = await filesRes.json();
      if (!filesRes.ok) {
        throw new Error(data.detail ?? data.error ?? "Could not load files.");
      }
      setList(data as CaseFileList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load files.");
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

  function uploadOne(file: File) {
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${file.name}`;

    setUploads((prev) => [
      ...prev,
      {
        id,
        name: file.name,
        size: file.size,
        progress: 0,
        status: "uploading",
      },
    ]);

    const fail = (message: string) => {
      setUploads((prev) =>
        prev.map((u) =>
          u.id === id ? { ...u, status: "error", error: message } : u,
        ),
      );
    };

    (async () => {
      const presignRes = await fetch("/api/files/presign-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          subfolder: path,
        }),
      });
      const presign = await presignRes.json();
      if (!presignRes.ok) {
        fail(presign.detail ?? presign.error ?? "Could not start upload.");
        return;
      }

      // Use XHR for progress events — fetch can't report upload progress.
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", presign.url, true);
      for (const [k, v] of Object.entries(presign.headers as Record<string, string>)) {
        xhr.setRequestHeader(k, v);
      }
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        setUploads((prev) =>
          prev.map((u) => (u.id === id ? { ...u, progress: pct } : u)),
        );
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploads((prev) =>
            prev.map((u) =>
              u.id === id ? { ...u, status: "done", progress: 100 } : u,
            ),
          );
          refresh();
        } else {
          fail(`S3 rejected the upload (${xhr.status}).`);
        }
      };
      xhr.onerror = () =>
        fail(
          "Upload failed. If this is a new bucket, make sure CORS allows PUT from this origin.",
        );
      xhr.send(file);
    })().catch((err) =>
      fail(err instanceof Error ? err.message : "Upload failed."),
    );
  }

  function handleFiles(files: FileList | File[] | null) {
    if (!files) return;
    Array.from(files).forEach(uploadOne);
  }

  async function handleDelete(item: FileItem) {
    if (!confirm(`Delete "${item.name}"? This cannot be undone.`)) return;
    setBusyKey(item.key);
    try {
      const res = await fetch(`/api/files?key=${encodeURIComponent(item.key)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? data.error ?? "Delete failed.");
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleConvert(item: FileItem) {
    setBusyKey(item.key);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/files/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: item.key }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? data.error ?? "Could not convert this PDF.");
      }
      await refresh();
      const basename = (data.name as string)?.split("/").pop() ?? "the Word file";
      setNotice(
        data.scanned
          ? `Converted to ${basename}. This looks like a scanned PDF, so the Word file contains page images, not editable text.`
          : `Converted to ${basename}. Open it to edit in Word.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not convert this PDF.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDownload(item: FileItem) {
    setBusyKey(item.key);
    try {
      const res = await fetch(
        `/api/files/presign-download?key=${encodeURIComponent(item.key)}`,
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? data.error ?? "Could not open file.");
      }
      window.open(data.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open file.");
    } finally {
      setBusyKey(null);
    }
  }

  const activeUploads = uploads.filter((u) => u.status === "uploading");

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#1e293b_0%,#0f172a_38%,#020617_100%)] text-slate-50">
      <div className="mx-auto flex w-full max-w-4xl flex-col px-4 pb-16 pt-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-20 -mx-4 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
            <BrandLogo href="/" />
            <nav className="flex items-center gap-4 text-sm text-slate-300">
              <Link className="hidden transition hover:text-white sm:inline" href="/projects">
                Projects
              </Link>
              <Link className="hidden transition hover:text-white sm:inline" href="/chat">
                Assistant
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
            Project files
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {activeProject
              ? `Documents — ${activeProject.name}`
              : "Documents"}
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-300 sm:text-base sm:leading-7">
            Upload PDFs, motions, financial affidavits, and discovery here.
            Files are stored under this project&rsquo;s private S3 prefix and
            used by the assistant when you ask it to ground answers in
            your record.{" "}
            <Link href="/projects" className="underline-offset-2 hover:underline">
              Switch project
            </Link>
            .
          </p>
        </section>

        {noActiveProject ? (
          <section className="rounded-[2rem] border border-amber-300/30 bg-amber-300/10 p-6 text-sm text-amber-100">
            <p className="font-semibold text-amber-50">No project selected.</p>
            <p className="mt-1 text-amber-100/90">
              Files are stored per-project. Pick or create a project first.
            </p>
            <Link
              href="/projects"
              className="mt-3 inline-flex items-center rounded-full bg-sky-400 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-sky-300"
            >
              Go to projects
            </Link>
          </section>
        ) : (
          <section
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFiles(e.dataTransfer.files);
            }}
            className={`rounded-[2rem] border border-dashed p-6 text-center transition ${
              dragOver
                ? "border-sky-300/70 bg-sky-400/10"
                : "border-white/20 bg-white/5"
            }`}
          >
            <p className="text-sm text-slate-300">
              Drag files here, or
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="ml-1.5 rounded-full bg-sky-400 px-3 py-1 text-xs font-semibold text-slate-950 transition hover:bg-sky-300"
              >
                Choose files
              </button>
            </p>
            <p className="mt-2 text-xs text-slate-400">
              Uploads land in{" "}
              <span className="font-mono text-slate-300">
                {path ? path : "the project root"}
              </span>
              . Navigate into a folder below to upload there.
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                handleFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </section>
        )}

        {uploads.length > 0 ? (
          <section className="mt-4 space-y-2">
            {uploads.map((u) => (
              <article
                key={u.id}
                className="rounded-2xl border border-white/10 bg-slate-900/70 p-3 text-sm"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate text-slate-100">{u.name}</span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {formatBytes(u.size)}
                  </span>
                </div>
                {u.status === "uploading" ? (
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full bg-sky-400 transition-[width]"
                      style={{ width: `${u.progress}%` }}
                    />
                  </div>
                ) : null}
                {u.status === "done" ? (
                  <p className="mt-1 text-xs text-emerald-300">Uploaded</p>
                ) : null}
                {u.status === "error" ? (
                  <p className="mt-1 text-xs text-rose-300">{u.error}</p>
                ) : null}
              </article>
            ))}
            {activeUploads.length === 0 && uploads.some((u) => u.status !== "uploading") ? (
              <button
                type="button"
                onClick={() => setUploads([])}
                className="text-xs text-slate-400 underline-offset-2 hover:underline"
              >
                Clear finished
              </button>
            ) : null}
          </section>
        ) : null}

        {error ? (
          <p className="mt-6 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {error}
          </p>
        ) : null}

        {notice ? (
          <div className="mt-6 flex items-start justify-between gap-3 rounded-2xl border border-sky-400/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-100">
            <span>{notice}</span>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="shrink-0 text-sky-200/70 underline-offset-2 hover:underline"
            >
              Dismiss
            </button>
          </div>
        ) : null}

        {noActiveProject ? null : (
        <section className="mt-8 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Your files</h2>
            <button
              type="button"
              onClick={refresh}
              className="text-xs text-slate-300 underline-offset-2 hover:underline"
            >
              Refresh
            </button>
          </div>

          <nav className="flex flex-wrap items-center gap-1 text-sm text-slate-300">
            <button
              type="button"
              onClick={() => setPath("")}
              className={`rounded px-1.5 py-0.5 transition hover:bg-white/10 ${
                path === "" ? "text-white" : "text-slate-400"
              }`}
            >
              All files
            </button>
            {crumbs.map((segment, i) => {
              const target = crumbs.slice(0, i + 1).join("/") + "/";
              const isLast = i === crumbs.length - 1;
              return (
                <span key={target} className="flex items-center gap-1">
                  <span className="text-slate-500">/</span>
                  <button
                    type="button"
                    onClick={() => setPath(target)}
                    className={`rounded px-1.5 py-0.5 transition hover:bg-white/10 ${
                      isLast ? "text-white" : "text-slate-400"
                    }`}
                  >
                    {segment}
                  </button>
                </span>
              );
            })}
          </nav>

          {loading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : !list || list.items.length === 0 ? (
            <p className="rounded-2xl border border-white/10 bg-white/4 px-4 py-6 text-sm text-slate-300">
              No files yet. Upload your first document above.
            </p>
          ) : folders.length === 0 && files.length === 0 ? (
            <p className="rounded-2xl border border-white/10 bg-white/4 px-4 py-6 text-sm text-slate-300">
              This folder is empty.
            </p>
          ) : (
            <ul className="divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/60">
              {folders.map((folder) => {
                const target = (path ? path : "") + folder.name + "/";
                return (
                  <li
                    key={`d:${folder.name}`}
                    className="flex items-center justify-between gap-3 px-4 py-3"
                  >
                    <button
                      type="button"
                      onClick={() => setPath(target)}
                      className="flex min-w-0 flex-1 items-center gap-3 text-left"
                    >
                      <span aria-hidden className="text-base">📁</span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-slate-100">
                          {folder.name}
                        </span>
                        <span className="mt-0.5 block text-xs text-slate-400">
                          {folder.fileCount}{" "}
                          {folder.fileCount === 1 ? "file" : "files"} ·{" "}
                          {formatBytes(folder.totalSize)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
              {files.map((item) => {
                const basename = item.name.split("/").pop() ?? item.name;
                return (
                  <li
                    key={item.key}
                    className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span aria-hidden className="text-base">📄</span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-100">
                          {basename}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-400">
                          {formatBytes(item.size)} · {formatDate(item.last_modified)}
                        </p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {basename.toLowerCase().endsWith(".pdf") ? (
                        <button
                          type="button"
                          disabled={busyKey === item.key}
                          onClick={() => handleConvert(item)}
                          className="rounded-full border border-sky-400/30 px-3 py-1 text-xs font-medium text-sky-100 transition hover:border-sky-400/60 hover:bg-sky-500/10 disabled:opacity-50"
                        >
                          {busyKey === item.key ? "Converting…" : "Convert to Word"}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        disabled={busyKey === item.key}
                        onClick={() => handleDownload(item)}
                        className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-white transition hover:border-white/35 hover:bg-white/5 disabled:opacity-50"
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        disabled={busyKey === item.key}
                        onClick={() => handleDelete(item)}
                        className="rounded-full border border-rose-400/30 px-3 py-1 text-xs font-medium text-rose-100 transition hover:border-rose-400/60 hover:bg-rose-500/10 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {list?.bucket ? (
            <p className="text-xs text-slate-500">
              s3://{list.bucket}/{list.prefix}{path}
            </p>
          ) : null}
        </section>
        )}
      </div>
    </main>
  );
}
