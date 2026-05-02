"""Supervisor configuration: SupervisorConfig + resolve_config()."""

from __future__ import annotations

import os
from dataclasses import dataclass


class MissingApiKeyError(RuntimeError):
    """Raised when OPENAI_API_KEY is unset."""


@dataclass(frozen=True)
class SupervisorConfig:
    openai_api_key: str
    model: str = "gpt-4o"
    max_worker_calls: int = 8
    route_max_tokens: int = 2048
    synthesize_max_tokens: int = 4096
    request_timeout_seconds: int = 60


def resolve_config() -> SupervisorConfig:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise MissingApiKeyError("OPENAI_API_KEY is not set")
    return SupervisorConfig(
        openai_api_key=api_key,
        model=os.environ.get("LINA_SUPERVISOR_MODEL", "gpt-4o"),
        max_worker_calls=int(os.environ.get("LINA_SUPERVISOR_MAX_WORKER_CALLS", "8")),
        route_max_tokens=int(os.environ.get("LINA_SUPERVISOR_ROUTE_MAX_TOKENS", "2048")),
        synthesize_max_tokens=int(os.environ.get("LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS", "4096")),
        request_timeout_seconds=int(
            os.environ.get("LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS", "60")
        ),
    )
