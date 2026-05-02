"""Typed exceptions raised by LINA workers across subsystems."""

from __future__ import annotations


class WorkerError(Exception):
    """Base class for worker exceptions caught at the boundary."""


class UnknownTemplateError(WorkerError):
    """Raised when a query_type does not match any registered template."""


class AuthorizationError(WorkerError):
    """Raised when the caller lacks any role required by the template."""


class InvalidParametersError(WorkerError):
    """Raised when the parameters fail pydantic validation."""


class QueryTimeoutError(WorkerError):
    """Raised when statement_timeout is reached during execution."""


class BackendConnectionError(WorkerError):
    """Raised on driver-level connection failure for any backend (Redshift, OpenSearch, etc.)."""


class WorkerInternalError(WorkerError):
    """Raised on any other internal failure; logged with sql_trace_id."""
