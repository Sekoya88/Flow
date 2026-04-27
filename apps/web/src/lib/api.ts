import { clearToken, getToken } from "./auth";

/** Browser + EventSource target. Docker Compose publishes API on host :18000 (see README). Local uvicorn defaults :8000 — set NEXT_PUBLIC_FLOW_API_URL in `.env.local` if needed. */
export const getApiBase = (): string =>
  process.env.NEXT_PUBLIC_FLOW_API_URL ?? "http://localhost:18000";

const base = getApiBase;

export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }
}

async function parse(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return text;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(init.json);
  } else if (init.body instanceof FormData) {
    /* boundary set by the browser */
  }
  const res = await fetch(`${base()}${path}`, { ...init, headers });
  if (res.status === 401) clearToken();
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return (await parse(res)) as T;
}
