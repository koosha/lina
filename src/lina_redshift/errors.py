"""Re-export typed exceptions from lina_core; keep Redshift-named alias."""

from lina_core.errors import (
    AuthorizationError,
    BackendConnectionError,
    InvalidParametersError,
    QueryTimeoutError,
    UnknownTemplateError,
    WorkerError,
    WorkerInternalError,
)

# Backward-compatible alias for the Redshift-specific name
RedshiftConnectionError = BackendConnectionError

__all__ = [
    "AuthorizationError",
    "BackendConnectionError",
    "InvalidParametersError",
    "QueryTimeoutError",
    "RedshiftConnectionError",
    "UnknownTemplateError",
    "WorkerError",
    "WorkerInternalError",
]
