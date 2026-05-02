"""Supervisor configuration: SupervisorConfig + resolve_config()."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]
_VALID_REASONING_EFFORTS: frozenset[str] = frozenset({"none", "low", "medium", "high", "xhigh"})


class MissingApiKeyError(RuntimeError):
    """Raised when OPENAI_API_KEY is unset."""


class InvalidReasoningEffortError(ValueError):
    """Raised when LINA_SUPERVISOR_REASONING_EFFORT is not in the allowed set."""


@dataclass(frozen=True)
class SupervisorConfig:
    openai_api_key: str
    model: str = "gpt-5.2"
    max_worker_calls: int = 8
    route_max_tokens: int = 2048
    synthesize_max_tokens: int = 4096
    request_timeout_seconds: int = 60
    # gpt-5.x family parameter; "none" means treat as a non-reasoning chat model.
    # Ignored on chat.completions calls when set to "none".
    reasoning_effort: ReasoningEffort = "none"


def resolve_config() -> SupervisorConfig:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise MissingApiKeyError("OPENAI_API_KEY is not set")
    reasoning_effort = os.environ.get("LINA_SUPERVISOR_REASONING_EFFORT", "none")
    if reasoning_effort not in _VALID_REASONING_EFFORTS:
        raise InvalidReasoningEffortError(
            f"LINA_SUPERVISOR_REASONING_EFFORT={reasoning_effort!r} not in "
            f"{sorted(_VALID_REASONING_EFFORTS)}"
        )
    return SupervisorConfig(
        openai_api_key=api_key,
        model=os.environ.get("LINA_SUPERVISOR_MODEL", "gpt-5.2"),
        max_worker_calls=int(os.environ.get("LINA_SUPERVISOR_MAX_WORKER_CALLS", "8")),
        route_max_tokens=int(os.environ.get("LINA_SUPERVISOR_ROUTE_MAX_TOKENS", "2048")),
        synthesize_max_tokens=int(os.environ.get("LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS", "4096")),
        request_timeout_seconds=int(
            os.environ.get("LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS", "60")
        ),
        reasoning_effort=reasoning_effort,  # type: ignore[arg-type]
    )
