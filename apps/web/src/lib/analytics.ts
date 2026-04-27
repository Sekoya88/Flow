import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";

type AnalyticsProps = Record<string, string | number | boolean | null | undefined>;

declare global {
  interface Window {
    __flowAnalytics?: Array<{ name: string; props: AnalyticsProps }>;
  }
}

/** Batched product analytics (no third party; server logs only). */
export function track(name: string, props: AnalyticsProps = {}): void {
  if (typeof window === "undefined") return;
  window.__flowAnalytics = window.__flowAnalytics ?? [];
  window.__flowAnalytics.push({ name, props: { ...props, path: window.location.pathname } });
  void flushSoon();
}

let flushTimer: ReturnType<typeof setTimeout> | null = null;

function flushSoon() {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flush();
  }, 2000);
}

async function flush() {
  const batch = window.__flowAnalytics;
  if (!batch?.length || !getToken()) {
    window.__flowAnalytics = [];
    return;
  }
  window.__flowAnalytics = [];
  const events = batch.map((e) => ({ name: e.name, props: e.props }));
  try {
    await apiFetch("/api/v1/analytics/events", { method: "POST", json: { events } });
  } catch {
    /* offline — drop batch */
  }
}
