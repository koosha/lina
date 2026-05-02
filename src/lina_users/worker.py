"""UserSearchWorker — boundary that resolves a query plan into a ResultPacket."""

from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError
from ulid import ULID

from lina_core.caller import CallerContext
from lina_core.errors import (
    AuthorizationError,
    BackendConnectionError,
    InvalidParametersError,
    QueryTimeoutError,
    UnknownTemplateError,
    WorkerError,
    WorkerInternalError,
)
from lina_core.logging_config import bind_call_context, get_logger
from lina_users.connection import OpenSearchConfig
from lina_users.packet import ErrorPacket, ResultPacket
from lina_users.templates import TEMPLATE_REGISTRY, get_template
from lina_users.templates.base import (
    APPROVED_INDICES,
    TemplateValidationError,
    validate_template_query,
)
from lina_users.templates.manager_chain import ManagerChainTemplate


class UserSearchWorker:
    def __init__(self, *, client: Any, config: OpenSearchConfig | None = None) -> None:
        self._client = client
        self._config = config
        self._log = get_logger("lina_users.worker")

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
                exc,
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )

        log = bind_call_context(
            self._log,
            sql_trace_id=sql_trace_id,
            request_id=caller.request_id,
            user_id=caller.user_id,
            query_type=query_type,
            template_version=template.template_version,
        )

        if template.index not in APPROVED_INDICES:
            err = WorkerInternalError(f"template index {template.index!r} not in APPROVED_INDICES")
            log.error("approved_index_violation", outcome="WorkerInternalError")
            return ErrorPacket.from_exception(
                err,
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )

        if not caller.has_any_role(template.allowed_roles):
            auth_exc = AuthorizationError(
                f"caller {caller.user_id!r} lacks any of {sorted(template.allowed_roles)} "
                f"required by {query_type!r}"
            )
            log.warning("authorization_failed", outcome="AuthorizationError")
            return ErrorPacket.from_exception(
                auth_exc,
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )

        try:
            parsed = template.Params.model_validate(params)
        except ValidationError as exc:
            wrapped = InvalidParametersError(str(exc))
            log.warning("invalid_parameters", outcome="InvalidParametersError")
            return ErrorPacket.from_exception(
                wrapped,
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )

        try:
            body = template.build_query(parsed)
            validate_template_query(
                body,
                allowed_fields=template.allowed_fields,
                default_size=template.default_size,
                max_size=template.max_size,
            )
        except TemplateValidationError as exc:
            log.error("template_validation_failed", outcome="WorkerInternalError")
            return ErrorPacket.from_exception(
                WorkerInternalError(str(exc)),
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )
        except Exception as exc:  # build_query failures are programmer error
            log.error("build_query_failed", outcome="WorkerInternalError", exc_info=exc)
            return ErrorPacket.from_exception(
                WorkerInternalError(str(exc)),
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )

        start = time.perf_counter()
        try:
            if isinstance(template, ManagerChainTemplate):
                source_rows = template.walk_chain(self._client, parsed)
                synthetic_hits = [{"_source": row} for row in source_rows]
                shaped = template.shape_packet(synthetic_hits)
                effective_max = template.max_size
            else:
                resp = self._search(body=body, index=template.index)
                hits = resp.get("hits", {}).get("hits", [])
                shaped = template.shape_packet(hits)
                effective_max = body.get("size", template.default_size)
        except WorkerError as exc:
            log.warning("query_failed", outcome=type(exc).__name__)
            return ErrorPacket.from_exception(
                exc,
                sql_trace_id=sql_trace_id,
                result_type=query_type,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        truncated = len(shaped) >= effective_max if effective_max else False
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

    def _search(self, *, body: dict[str, Any], index: str) -> dict[str, Any]:
        from opensearchpy.exceptions import (
            ConnectionError as OSConnectionError,
        )
        from opensearchpy.exceptions import (
            OpenSearchException,
            RequestError,
        )

        timeout_s = self._config.request_timeout_seconds if self._config else 30
        try:
            return dict(self._client.search(index=index, body=body, request_timeout=timeout_s))
        except OSConnectionError as exc:
            raise BackendConnectionError(str(exc)) from exc
        except RequestError as exc:
            msg = str(exc).lower()
            if "timed_out" in msg or "timeout" in msg:
                raise QueryTimeoutError(str(exc)) from exc
            raise WorkerInternalError(str(exc)) from exc
        except OpenSearchException as exc:
            raise WorkerInternalError(str(exc)) from exc


# Sanity check: importing this module ensures every template is registered.
assert TEMPLATE_REGISTRY, "no templates registered"
