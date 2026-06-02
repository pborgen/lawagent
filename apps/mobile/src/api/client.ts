import { config } from "@/config";
import { getAuthBridge } from "@/auth/bridge";

// Single chokepoint for talking to FastAPI: injects the bearer token and
// retries once on a 401 after forcing a token refresh (covers the case where
// the server rejects a token our local clock still considered valid).
export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type RequestOpts = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | undefined>;
  _retried?: boolean;
};

function buildUrl(path: string, query?: RequestOpts["query"]): string {
  const url = new URL(config.apiUrl + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined) url.searchParams.set(k, v);
    }
  }
  return url.toString();
}

export async function apiFetch<T>(
  path: string,
  opts: RequestOpts = {},
): Promise<T> {
  const bridge = getAuthBridge();
  const token = await bridge.getValidIdToken();

  const res = await fetch(buildUrl(path, opts.query), {
    method: opts.method ?? "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(opts.body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 401 && !opts._retried) {
    try {
      await bridge.forceRefresh();
      return apiFetch<T>(path, { ...opts, _retried: true });
    } catch {
      bridge.onUnauthorized();
    }
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    if (res.status === 401) bridge.onUnauthorized();
    throw new ApiError(
      res.status,
      detail,
      typeof detail?.detail === "string" ? detail.detail : undefined,
    );
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
