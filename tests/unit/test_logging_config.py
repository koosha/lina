"""Unit tests for logging configuration."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from lina_redshift.logging_config import bind_call_context, configure_logging, get_logger


@pytest.mark.unit
def test_configure_logging_json_emits_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_LOG_FORMAT", "json")
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    configure_logging(handler=handler)

    logger = get_logger("test")
    logger.info("hello", foo="bar")

    line = buf.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["foo"] == "bar"


@pytest.mark.unit
def test_bind_call_context_attaches_trace_fields() -> None:
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    configure_logging(handler=handler, fmt="json")

    logger = get_logger("test")
    bound = bind_call_context(
        logger,
        sql_trace_id="01HZX0",
        request_id="req_1",
        user_id="user_jane",
        query_type="matter_lookup",
        template_version="1.0.0",
    )
    bound.info("call_start")

    parsed = json.loads(buf.getvalue().strip())
    assert parsed["sql_trace_id"] == "01HZX0"
    assert parsed["query_type"] == "matter_lookup"
