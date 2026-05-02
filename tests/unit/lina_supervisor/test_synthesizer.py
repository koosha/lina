"""Unit tests for the synthesizer module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_supervisor.config import SupervisorConfig
from lina_supervisor.synthesizer import stream_final_answer


def _config(**overrides: Any) -> SupervisorConfig:
    base = {
        "anthropic_api_key": "sk-test",
        "model": "claude-sonnet-4-7",
        "synthesize_max_tokens": 1234,
        "request_timeout_seconds": 42,
    }
    base.update(overrides)
    return SupervisorConfig(**base)  # type: ignore[arg-type]


class _StreamCtx:
    def __init__(self, chunks: list[str]) -> None:
        self.text_stream = iter(chunks)

    def __enter__(self) -> _StreamCtx:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None


def _client_with_chunks(chunks: list[str]) -> MagicMock:
    client = MagicMock()
    client.messages.stream.return_value = _StreamCtx(chunks)
    return client


@pytest.mark.unit
def test_yields_chunks_in_order() -> None:
    client = _client_with_chunks(["The ", "answer ", "is 42"])
    out = list(
        stream_final_answer(
            anthropic_client=client,
            config=_config(),
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    assert out == ["The ", "answer ", "is 42"]


@pytest.mark.unit
def test_appends_final_instruction_message() -> None:
    client = _client_with_chunks(["ok"])
    list(
        stream_final_answer(
            anthropic_client=client,
            config=_config(),
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    sent = client.messages.stream.call_args.kwargs["messages"]
    assert len(sent) == 2
    assert sent[0] == {"role": "user", "content": "hi"}
    assert sent[1]["role"] == "user"
    assert "final answer" in sent[1]["content"].lower()


@pytest.mark.unit
def test_passes_max_tokens_and_model() -> None:
    client = _client_with_chunks(["ok"])
    cfg = _config(synthesize_max_tokens=2048)
    list(
        stream_final_answer(
            anthropic_client=client,
            config=cfg,
            messages=[],
        )
    )
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == cfg.model
    assert kwargs["max_tokens"] == 2048


@pytest.mark.unit
def test_handles_empty_stream() -> None:
    client = _client_with_chunks([])
    out = list(
        stream_final_answer(
            anthropic_client=client,
            config=_config(),
            messages=[],
        )
    )
    assert out == []


@pytest.mark.unit
def test_propagates_stream_errors() -> None:
    client = MagicMock()

    class _Boom:
        def __enter__(self) -> _Boom:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        @property
        def text_stream(self) -> Any:
            raise RuntimeError("anthropic boom")

    client.messages.stream.return_value = _Boom()
    with pytest.raises(RuntimeError, match="anthropic boom"):
        list(
            stream_final_answer(
                anthropic_client=client,
                config=_config(),
                messages=[],
            )
        )
