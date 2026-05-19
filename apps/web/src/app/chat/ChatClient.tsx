"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import BrandLogo from "@/components/BrandLogo";

const MODES = [
  { id: "short", label: "Short", hint: "2–4 sentences + citations" },
  { id: "memo", label: "Memo", hint: "Issue / Rule / Analysis / Conclusion" },
  { id: "annotate", label: "Annotate", hint: "Statute text + annotations" },
] as const;

type Mode = (typeof MODES)[number]["id"];

type Source = {
  citation: string;
  url: string;
  source_type: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  mode?: Mode;
  sources?: Source[];
};

const EXAMPLES = [
  "What factors must a CT court consider when awarding alimony under § 46b-82?",
  "How does pendente lite alimony under § 46b-83 differ from a final award?",
  "What should I bring to a pendente lite alimony hearing?",
];

export default function ChatClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("short");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, mode }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "The assistant could not answer that.");
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          mode: data.mode,
          sources: data.sources ?? [],
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong.",
      );
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(input);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <main className="flex min-h-screen flex-col bg-[radial-gradient(circle_at_top,#1e293b_0%,#0f172a_38%,#020617_100%)] text-slate-50">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur sm:px-6">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4">
          <BrandLogo href="/" showWordmark={false} />
          <Link
            href="/"
            className="text-sm text-slate-300 transition hover:text-white"
          >
            ← Home
          </Link>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-6 sm:px-6"
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
          {messages.length === 0 && (
            <div className="space-y-5 rounded-3xl border border-white/10 bg-white/5 p-6">
              <div className="space-y-2">
                <h1 className="text-2xl font-semibold tracking-tight">
                  Ask about Connecticut divorce law
                </h1>
                <p className="text-sm leading-6 text-slate-300">
                  Every answer is grounded in retrieved statutes, rules, and
                  cases — with citations you can check. Initial focus: alimony
                  under §§ 46b-82 and 46b-83.
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                  Try one of these
                </p>
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    onClick={() => send(ex)}
                    disabled={loading}
                    className="block w-full rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-left text-sm leading-6 text-slate-200 transition hover:border-sky-400/40 hover:bg-slate-900 disabled:opacity-50"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user" ? "flex justify-end" : "flex justify-start"
              }
            >
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-3xl rounded-br-md bg-sky-400 px-4 py-3 text-sm leading-6 text-slate-950"
                    : "max-w-[90%] rounded-3xl rounded-bl-md border border-white/10 bg-white/5 px-4 py-3"
                }
              >
                {m.role === "assistant" && m.mode && (
                  <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-sky-200">
                    {m.mode} answer
                  </p>
                )}
                {m.role === "assistant" ? (
                  <div className="text-sm leading-7 text-slate-100">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ href, children }) => (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sky-300 underline decoration-sky-400/40 underline-offset-2 hover:text-sky-200"
                          >
                            {children}
                          </a>
                        ),
                        p: ({ children }) => (
                          <p className="my-2 first:mt-0 last:mb-0">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-white">{children}</strong>
                        ),
                        em: ({ children }) => <em className="italic">{children}</em>,
                        code: ({ children }) => (
                          <code className="rounded bg-slate-900 px-1.5 py-0.5 text-sky-200">
                            {children}
                          </code>
                        ),
                        blockquote: ({ children }) => (
                          <blockquote className="my-3 border-l-2 border-sky-400/40 pl-3 text-slate-300">
                            {children}
                          </blockquote>
                        ),
                        h1: ({ children }) => (
                          <h3 className="mt-3 mb-1 text-base font-semibold text-white">
                            {children}
                          </h3>
                        ),
                        h2: ({ children }) => (
                          <h3 className="mt-3 mb-1 text-base font-semibold text-white">
                            {children}
                          </h3>
                        ),
                        h3: ({ children }) => (
                          <h3 className="mt-3 mb-1 text-base font-semibold text-white">
                            {children}
                          </h3>
                        ),
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{m.content}</p>
                )}

                {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                  <div className="mt-3 border-t border-white/10 pt-3">
                    <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                      Sources
                    </p>
                    <ul className="mt-2 space-y-1.5">
                      {m.sources.map((s, j) => (
                        <li key={j} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                          {s.url ? (
                            <a
                              href={s.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-sky-300 underline decoration-sky-400/40 underline-offset-2 hover:text-sky-200"
                            >
                              {s.citation}
                            </a>
                          ) : (
                            <span className="text-sm text-slate-300">{s.citation}</span>
                          )}
                          {s.source_type && (
                            <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                              {s.source_type}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-3xl rounded-bl-md border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-400">
                Researching the corpus…
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-2xl border border-rose-400/30 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
              {error}
            </div>
          )}
        </div>
      </div>

      <div className="sticky bottom-0 border-t border-white/10 bg-slate-950/80 px-4 py-4 backdrop-blur sm:px-6">
        <form
          onSubmit={onSubmit}
          className="mx-auto flex w-full max-w-3xl flex-col gap-3"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
              Answer style
            </span>
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id)}
                title={m.hint}
                className={
                  mode === m.id
                    ? "rounded-full bg-sky-400 px-3 py-1 text-xs font-semibold text-slate-950"
                    : "rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-slate-300 transition hover:border-white/35 hover:text-white"
                }
              >
                {m.label}
              </button>
            ))}
          </div>

          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Ask a Connecticut divorce question…"
              className="min-h-12 flex-1 resize-none rounded-2xl border border-white/15 bg-slate-900/80 px-4 py-3 text-sm leading-6 text-slate-100 placeholder:text-slate-500 focus:border-sky-400/50 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="inline-flex min-h-12 items-center justify-center rounded-2xl bg-sky-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "…" : "Send"}
            </button>
          </div>

          <p className="text-xs leading-5 text-slate-500">
            Research assistance, not legal advice. divorse.ai is not a law
            firm and does not replace counsel.
          </p>
        </form>
      </div>
    </main>
  );
}
