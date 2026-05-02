"""RedshiftWorker — the boundary that resolves a query plan into a ResultPacket."""

from __future__ import annotations

import time
from typing import Any

from psycopg2.extensions import connection as PgConnection  # noqa: N812
from psycopg2.extras import RealDictCursor
from pydantic import ValidationError
from ulid import ULID

from lina_redshift.caller import CallerContext
from lina_redshift.errors import (
    AuthorizationError,
    InvalidParametersError,
    QueryTimeoutError,
    RedshiftConnectionError,
    UnknownTemplateError,
    WorkerError,
    WorkerInternalError,
)
from lina_redshift.logging_config import bind_call_context, get_logger
from lina_redshift.packet import ErrorPacket, ResultPacket
from lina_redshift.templates import TEMPLATE_REGISTRY, get_template


class RedshiftWorker:
    def __init__(self, *, connection: PgConnection) -> None:
        self._conn = connection
        self._log = get_logger("lina_redshift.worker")

    def run(
        self,
        *,
        query_type: str,
        params: dict[str, Any],
        caller: CallerContext,
    ) -> ResultPacket | ErrorPacket:
        sql_trace_id = str(ULID())
        log = bind_call_context(
            self._log,
            sql_trace_id=sql_trace_id,
            request_id=caller.request_id,
            user_id=caller.user_id,
            query_type=query_type,
            template_version="?",
        )
        try:
            template = get_template(query_type)
        except UnknownTemplateError as exc:
            log.warning("unknown_template", outcome=type(exc).__name__)
            return ErrorPacket.from_exception(
                exc, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        log = bind_call_context(
            self._log,
            sql_trace_id=sql_trace_id,
            request_id=caller.request_id,
            user_id=caller.user_id,
            query_type=query_type,
            template_version=template.template_version,
        )

        if not caller.has_any_role(template.allowed_roles):
            auth_exc = AuthorizationError(
                f"caller {caller.user_id!r} lacks any of {sorted(template.allowed_roles)} "
                f"required by {query_type!r}"
            )
            log.warning("authorization_failed", outcome="AuthorizationError")
            return ErrorPacket.from_exception(
                auth_exc, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        try:
            parsed = template.Params.model_validate(params)
        except ValidationError as exc:
            wrapped = InvalidParametersError(str(exc))
            log.warning("invalid_parameters", outcome="InvalidParametersError")
            return ErrorPacket.from_exception(
                wrapped, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        try:
            sql, binds = template.build_sql(parsed)
        except Exception as exc:  # build_sql failures are programmer error
            log.error("build_sql_failed", outcome="WorkerInternalError", exc_info=exc)
            return ErrorPacket.from_exception(
                WorkerInternalError(str(exc)),
                sql_trace_id=sql_trace_id, result_type=query_type,
            )

        start = time.perf_counter()
        try:
            rows = self._execute(sql=sql, binds=binds)
        except WorkerError as exc:
            log.warning("query_failed", outcome=type(exc).__name__)
            return ErrorPacket.from_exception(
                exc, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        shaped = template.shape_packet(rows)
        truncated = len(shaped) >= binds.get("limit", 0)
        log.info(
            "call_complete",
            outcome="success",
            duration_ms=duration_ms,
            row_count=len(shaped),
            truncated=truncated,
        )
        return ResultPacket(
            result_type=query_type,
            metrics=shaped,
            sql_trace_id=sql_trace_id,
            row_count=len(shaped),
            truncated=truncated,
        )

    def _execute(self, *, sql: str, binds: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, binds)
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            msg = str(exc).lower()
            if "statement timeout" in msg or "canceling statement due to" in msg:
                raise QueryTimeoutError(str(exc)) from exc
            if "connection" in msg or "ssl" in msg:
                raise RedshiftConnectionError(str(exc)) from exc
            raise WorkerInternalError(str(exc)) from exc


# Sanity check: importing this module ensures every template is registered.
assert TEMPLATE_REGISTRY, "no templates registered"
