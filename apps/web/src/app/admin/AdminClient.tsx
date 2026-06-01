"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import BrandLogo from "@/components/BrandLogo";

type UsageBucket = {
  label: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
};

type UsageOverview = {
  days: number;
  since: string;
  totals: UsageBucket;
  by_user: UsageBucket[];
  by_model: UsageBucket[];
  daily: UsageBucket[];
};

const RANGES = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
];

const numberFmt = new Intl.NumberFormat("en-US");

function formatTokens(n: number): string {
  return numberFmt.format(n);
}

function formatCost(usd: number): string {
  if (!usd) return "—";
  // Show more precision for tiny amounts so embedding-only spend isn't $0.00.
  const digits = usd < 1 ? 4 : 2;
  return `$${usd.toFixed(digits)}`;
}

export default function AdminClient() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<UsageOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (range: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/usage/overview?days=${range}`, {
        cache: "no-store",
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail ?? body.error ?? "Could not load usage.");
      }
      setData(body as UsageOverview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load usage.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount / on-range-change. refresh() owns loading + error state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh(days);
  }, [days, refresh]);

  const totals = data?.totals;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#1e293b_0%,#0f172a_38%,#020617_100%)] text-slate-50">
      <div className="mx-auto flex w-full max-w-5xl flex-col px-4 pb-16 pt-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-20 -mx-4 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
            <BrandLogo href="/" />
            <nav className="flex items-center gap-4 text-sm text-slate-300">
              <Link className="hidden transition hover:text-white sm:inline" href="/projects">
                Projects
              </Link>
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
            Admin
          </p>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                LLM usage
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-slate-300">
                Token consumption and estimated cost across all users. Costs
                are approximate (list prices) and embedding token counts are
                estimated.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="inline-flex rounded-full border border-white/15 bg-slate-950/40 p-1">
                {RANGES.map((r) => (
                  <button
                    key={r.value}
                    type="button"
                    onClick={() => setDays(r.value)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      days === r.value
                        ? "bg-sky-400 text-slate-950"
                        : "text-slate-300 hover:text-white"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => refresh(days)}
                className="text-xs text-slate-300 underline-offset-2 hover:underline"
              >
                Refresh
              </button>
            </div>
          </div>
        </section>

        {error ? (
          <p className="mb-6 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {error}
          </p>
        ) : null}

        {/* Summary cards */}
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryCard label="Requests" value={formatTokens(totals?.requests ?? 0)} loading={loading} />
          <SummaryCard label="Input tokens" value={formatTokens(totals?.input_tokens ?? 0)} loading={loading} />
          <SummaryCard label="Output tokens" value={formatTokens(totals?.output_tokens ?? 0)} loading={loading} />
          <SummaryCard label="Est. cost" value={formatCost(totals?.cost_usd ?? 0)} loading={loading} />
        </section>

        <UsageTable
          title="By user"
          firstColumn="User"
          rows={data?.by_user ?? []}
          loading={loading}
          emptyText="No usage recorded yet."
        />

        <UsageTable
          title="By model"
          firstColumn="Model"
          rows={data?.by_model ?? []}
          loading={loading}
          emptyText="No usage recorded yet."
        />

        <UsageTable
          title="By day"
          firstColumn="Date"
          rows={data?.daily ?? []}
          loading={loading}
          emptyText="No usage in this window."
        />
      </div>
    </main>
  );
}

function SummaryCard({
  label,
  value,
  loading,
}: {
  label: string;
  value: string;
  loading: boolean;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-5">
      <p className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-white">
        {loading ? "…" : value}
      </p>
    </div>
  );
}

function UsageTable({
  title,
  firstColumn,
  rows,
  loading,
  emptyText,
}: {
  title: string;
  firstColumn: string;
  rows: UsageBucket[];
  loading: boolean;
  emptyText: string;
}) {
  return (
    <section className="mt-8 space-y-3">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      {loading ? (
        <p className="text-sm text-slate-400">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-2xl border border-white/10 bg-white/4 px-4 py-6 text-sm text-slate-300">
          {emptyText}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/60">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="px-4 py-3 font-medium">{firstColumn}</th>
                <th className="px-4 py-3 text-right font-medium">Requests</th>
                <th className="px-4 py-3 text-right font-medium">Input</th>
                <th className="px-4 py-3 text-right font-medium">Output</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 text-right font-medium">Est. cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {rows.map((row) => (
                <tr key={row.label} className="text-slate-200">
                  <td className="max-w-[16rem] truncate px-4 py-3 font-medium text-slate-100">
                    {row.label}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatTokens(row.requests)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-400">
                    {formatTokens(row.input_tokens)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-400">
                    {formatTokens(row.output_tokens)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatTokens(row.total_tokens)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatCost(row.cost_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
