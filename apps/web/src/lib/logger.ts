type LogLevel = "debug" | "info" | "warn" | "error";

function send(level: LogLevel, msg: string, props?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  try {
    navigator.sendBeacon?.(
      "/api/v1/analytics/events",
      JSON.stringify([{ event: "client_log", level, message: msg, props, ts: Date.now() }]),
    );
  } catch {
    // beacon failure is non-fatal
  }
}

export const logger = {
  debug: (msg: string, props?: Record<string, unknown>) => {
    if (process.env.NODE_ENV !== "production") console.debug(`[debug] ${msg}`, props);
  },
  info: (msg: string, props?: Record<string, unknown>) =>
    console.info(`[info] ${msg}`, props),
  warn: (msg: string, props?: Record<string, unknown>) => {
    console.warn(`[warn] ${msg}`, props);
    send("warn", msg, props);
  },
  error: (msg: string, props?: Record<string, unknown>) => {
    console.error(`[error] ${msg}`, props);
    send("error", msg, props);
  },
};
