"""OpenSearch connection re-exports for Subsystem B.

The actual implementation lives in `lina_core.opensearch` and is shared with
Subsystem A (`lina_users`).
"""

from __future__ import annotations

from lina_core.opensearch import (
    AuthMode,
    MissingHostError,
    OpenSearchConfig,
    open_client,
    resolve_config,
)

__all__ = [
    "AuthMode",
    "MissingHostError",
    "OpenSearchConfig",
    "open_client",
    "resolve_config",
]
