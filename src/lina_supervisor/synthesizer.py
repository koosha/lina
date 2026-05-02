"""Final synthesis pass: combines worker results into the user-facing answer.

Streams text chunks from Claude. Called only when the supervisor has hit
the worker-call cap mid-conversation; the standard text-only-no-tools path
in ``route`` short-circuits to END without invoking the synthesizer.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from lina_supervisor.config import SupervisorConfig

_FINAL_INSTRUCTION = (
    "You have all the data needed. Produce the final answer for the user. "
    'Cite the worker results you used ("Sources: ...") at the end. '
    "Do not call any more tools."
)


def stream_final_answer(
    *,
    anthropic_client: Any,
    config: SupervisorConfig,
    messages: list[dict[str, Any]],
) -> Iterator[str]:
    """Yield text chunks from the synthesizer pass."""
    final_messages = [
        *messages,
        {"role": "user", "content": _FINAL_INSTRUCTION},
    ]
    with anthropic_client.messages.stream(
        model=config.model,
        max_tokens=config.synthesize_max_tokens,
        messages=final_messages,
    ) as stream:
        yield from stream.text_stream
