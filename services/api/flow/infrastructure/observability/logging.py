from __future__ import annotations

import logging
import os
import sys

import structlog

# ── Node colour / prefix map for agentic logs ────────────────────────
_NODE_STYLES: dict[str, tuple[str, str]] = {
    # (ANSI colour, glyph)
    "planner": ("\033[94m", "◈"),  # blue
    "worker": ("\033[96m", "⚙"),  # cyan
    "synthesizer": ("\033[95m", "✦"),  # magenta
    "reflector": ("\033[93m", "⟳"),  # yellow
    "tool_agent": ("\033[92m", "⚡"),  # green
    "retriever": ("\033[36m", "⌕"),  # teal
    "router": ("\033[33m", "⇒"),  # orange
}
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"

_LOG_LEVEL_COLORS = {
    "debug": "\033[2m",  # dim
    "info": "\033[0m",  # normal
    "warning": "\033[33m",  # yellow
    "error": "\033[31m",  # red
    "critical": "\033[1;31m",  # bold red
}

_HTTP_METHOD_COLORS: dict[str, str] = {
    "GET":     "\033[94m",   # bright blue
    "POST":    "\033[92m",   # bright green
    "PUT":     "\033[93m",   # yellow
    "PATCH":   "\033[33m",   # orange
    "DELETE":  "\033[91m",   # bright red
    "HEAD":    "\033[2m",    # dim
    "OPTIONS": "\033[2m",    # dim
}


def _status_color(status: int) -> str:
    if status < 300:
        return "\033[92m"   # green
    if status < 400:
        return "\033[96m"   # cyan
    if status < 500:
        return "\033[93m"   # yellow
    return "\033[91m"       # red


def _duration_color(ms: int) -> str:
    if ms < 100:
        return "\033[2m"    # dim — fast, background noise
    if ms < 500:
        return "\033[93m"   # yellow — slow
    return "\033[91m"       # red — very slow


class AgenticConsoleRenderer:
    """ConsoleRenderer that adds node-specific glyphs and indentation for flow.graph.* events."""

    def __init__(self, *, colors: bool = True) -> None:
        self._colors = colors

    def __call__(self, logger: logging.Logger, method: str, event_dict: dict) -> str:
        level = event_dict.pop("level", "info").lower()
        timestamp = event_dict.pop("timestamp", "")
        event = event_dict.pop("event", "")

        # Shorten timestamp to HH:MM:SS.mmm
        ts_short = timestamp[11:23] if len(timestamp) >= 23 else timestamp

        if self._colors:
            ts_part = f"{_DIM}{ts_short}{_RESET}"
        else:
            ts_part = ts_short

        # ── Special formatting for HTTP request logs ──────────────────────
        if event == "http.request":
            http_method = str(event_dict.pop("method", ""))
            path = str(event_dict.pop("path", ""))
            status = int(event_dict.pop("status", 0))
            duration_ms = int(event_dict.pop("duration_ms", 0))
            event_dict.pop("service", None)

            if self._colors:
                m_color = _HTTP_METHOD_COLORS.get(http_method, "\033[0m")
                s_color = _status_color(status)
                d_color = _duration_color(duration_ms)
                method_part = f"{m_color}{_BOLD}{http_method:<7}{_RESET}"
                status_part = f"{s_color}{_BOLD}{status}{_RESET}"
                dur_part = f"{d_color}{duration_ms}ms{_RESET}"
                return f"{ts_part}  {method_part} {path}  {status_part}  {dur_part}"
            else:
                return f"{ts_short}  {http_method:<7} {path}  {status}  {duration_ms}ms"

        # ── Default agentic log formatting ────────────────────────────────
        node = event_dict.get("node") or event_dict.get("component") or ""

        if self._colors:
            style, glyph = _NODE_STYLES.get(str(node), ("\033[0m", "·"))
            lvl_color = _LOG_LEVEL_COLORS.get(level, "\033[0m")
            glyph_part = f"{style}{glyph}{_RESET}" if node else f"{_DIM}·{_RESET}"
            event_part = f"{lvl_color}{event}{_RESET}"
            if level in ("warning", "error", "critical"):
                event_part = f"{_LOG_LEVEL_COLORS[level]}{_BOLD}{event}{_RESET}"
        else:
            glyph_part = ""
            event_part = event

        extras = []
        for k, v in event_dict.items():
            if k in ("service",):
                continue
            if self._colors:
                extras.append(f"{_DIM}{k}{_RESET}={_BOLD}{v!r}{_RESET}")
            else:
                extras.append(f"{k}={v!r}")

        parts = [ts_part, glyph_part, event_part]
        if extras:
            parts.append("  " + "  ".join(extras))

        return " ".join(p for p in parts if p)


def configure_logging(
    *,
    level: str,
    json_output: bool,
    service: str | None = None,
    force_colors: bool = False,
) -> None:
    """Human-readable logs by default. Use json_output=True for machine parsing."""
    tty = sys.stderr.isatty()
    force_color_env = os.environ.get("FORCE_COLOR", "").strip().lower() in ("1", "true", "yes")
    colors = (not json_output) and (force_colors or tty or force_color_env)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_output:
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(AgenticConsoleRenderer(colors=colors))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.clear_contextvars()
    if service:
        structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
