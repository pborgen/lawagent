"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import BrandLogo from "@/components/BrandLogo";

type FileItem = {
  key: string;
  name: string;
  size: number;
  last_modified: string;
};

type CaseFileList = {
  bucket: string;
  prefix: string;
  items: FileItem[];
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

export default function FilesClient() {
  const [list, setList] = useState<CaseFileList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch("/api/files", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok) {
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
            Case files
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Documents for your case
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-300 sm:text-base sm:leading-7">
            Upload PDFs, motions, financial affidavits, and discovery here.
            Files are stored in your case&rsquo;s private S3 bucket and used by
            the assistant when you ask it to ground answers in your record.
          </p>
        </section>

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
            PDFs, Word docs, images, or text — any document for your case.
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

          {loading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : !list || list.items.length === 0 ? (
            <p className="rounded-2xl border border-white/10 bg-white/4 px-4 py-6 text-sm text-slate-300">
              No files yet. Upload your first document above.
            </p>
          ) : (
            <ul className="divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/60">
              {list.items.map((item) => (
                <li
                  key={item.key}
                  className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-100">
                      {item.name}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {formatBytes(item.size)} · {formatDate(item.last_modified)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
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
              ))}
            </ul>
          )}

          {list?.bucket ? (
            <p className="text-xs text-slate-500">
              s3://{list.bucket}/{list.prefix}
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}
