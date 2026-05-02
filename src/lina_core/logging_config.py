"""structlog setup with JSON renderer (prod) or console renderer (dev)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.stdlib import BoundLogger


def configure_logging(*, handler: logging.Handler | None = None, fmt: str | None = None) -> None:
    chosen_fmt = (fmt or os.environ.get("LINA_LOG_FORMAT") or "console").lower()

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    if chosen_fmt == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler or logging.StreamHandler(sys.stderr))
    root.setLevel(logging.INFO)


def get_logger(name: str = "lina_core") -> BoundLogger:
    logger: BoundLogger = structlog.stdlib.get_logger(name)
    return logger


def bind_call_context(
    logger: BoundLogger,
    *,
    sql_trace_id: str,
    request_id: str,
    user_id: str,
    query_type: str,
    template_version: str,
) -> BoundLogger:
    bound: BoundLogger = logger.bind(
        sql_trace_id=sql_trace_id,
        request_id=request_id,
        user_id=user_id,
        query_type=query_type,
        template_version=template_version,
    )
    return bound
