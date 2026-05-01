from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_logging(
    *,
    level: str,
    json_output: bool,
    service: str | None = None,
    force_colors: bool = False,
) -> None:
    """Human-readable logs by default (Rich tracebacks). Use log_json for machine parsing."""
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
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=colors,
                force_colors=force_colors,
                pad_level=True,
                pad_event=36,
            )
        )

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
