from __future__ import annotations

import logging
import os
import sys

import structlog

# ── Node colour / prefix map for agentic logs ────────────────────────
_NODE_STYLES: dict[str, tuple[str, str]] = {
    # (ANSI colour, glyph)
    "planner":     ("\033[94m", "◈"),   # blue
    "worker":      ("\033[96m", "⚙"),   # cyan
    "synthesizer": ("\033[95m", "✦"),   # magenta
    "reflector":   ("\033[93m", "⟳"),   # yellow
    "tool_agent":  ("\033[92m", "⚡"),  # green
    "retriever":   ("\033[36m", "⌕"),   # teal
    "router":      ("\033[33m", "⇒"),   # orange
}
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"

_LOG_LEVEL_COLORS = {
    "debug":    "\033[2m",      # dim
    "info":     "\033[0m",      # normal
    "warning":  "\033[33m",     # yellow
    "error":    "\033[31m",     # red
    "critical": "\033[1;31m",   # bold red
}


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

        # Determine node context
        node = event_dict.get("node") or event_dict.get("component") or ""

        # Build prefix
        if self._colors:
            style, glyph = _NODE_STYLES.get(str(node), ("\033[0m", "·"))
            lvl_color = _LOG_LEVEL_COLORS.get(level, "\033[0m")
            ts_part = f"{_DIM}{ts_short}{_RESET}"
            glyph_part = f"{style}{glyph}{_RESET}" if node else f"{_DIM}·{_RESET}"
            event_part = f"{lvl_color}{event}{_RESET}"
            if level in ("warning", "error", "critical"):
                event_part = f"{_LOG_LEVEL_COLORS[level]}{_BOLD}{event}{_RESET}"
        else:
            glyph_part = ""
            ts_part = ts_short
            event_part = event

        # Format extra keys
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
