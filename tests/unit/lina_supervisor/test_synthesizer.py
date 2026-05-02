"""Unit tests for the synthesizer module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_supervisor.config import SupervisorConfig
from lina_supervisor.synthesizer import stream_final_answer


def _config(**overrides: Any) -> SupervisorConfig:
    base = {
        "openai_api_key": "sk-test",
        "model": "gpt-4o",
        "synthesize_max_tokens": 1234,
        "request_timeout_seconds": 42,
    }
    base.update(overrides)
    return SupervisorConfig(**base)  # type: ignore[arg-type]


def _stream_chunk(text: str | None) -> Any:
    delta = MagicMock()
    delta.content = text
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _client_with_chunks(chunks: list[str | None]) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = iter(_stream_chunk(c) for c in chunks)
    return client


@pytest.mark.unit
def test_yields_chunks_in_order() -> None:
    client = _client_with_chunks(["The ", "answer ", "is 42"])
    out = list(
        stream_final_answer(
            llm_client=client,
            config=_config(),
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    assert out == ["The ", "answer ", "is 42"]


@pytest.mark.unit
def test_skips_chunks_with_none_content() -> None:
    """OpenAI yields a final chunk with delta.content=None alongside finish_reason."""
    client = _client_with_chunks(["hello", None])
    out = list(
        stream_final_answer(
            llm_client=client,
            config=_config(),
            messages=[],
        )
    )
    assert out == ["hello"]


@pytest.mark.unit
def test_appends_final_instruction_message() -> None:
    client = _client_with_chunks(["ok"])
    list(
        stream_final_answer(
            llm_client=client,
            config=_config(),
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    sent = client.chat.completions.create.call_args.kwargs["messages"]
    assert len(sent) == 2
    assert sent[0] == {"role": "user", "content": "hi"}
    assert sent[1]["role"] == "user"
    assert "final answer" in sent[1]["content"].lower()


@pytest.mark.unit
def test_passes_max_tokens_and_model_and_stream() -> None:
    client = _client_with_chunks(["ok"])
    cfg = _config(synthesize_max_tokens=2048)
    list(
        stream_final_answer(
            llm_client=client,
            config=cfg,
            messages=[],
        )
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == cfg.model
    assert kwargs["max_tokens"] == 2048
    assert kwargs["stream"] is True


@pytest.mark.unit
def test_handles_empty_stream() -> None:
    client = _client_with_chunks([])
    out = list(
        stream_final_answer(
            llm_client=client,
            config=_config(),
            messages=[],
        )
    )
    assert out == []


@pytest.mark.unit
def test_propagates_stream_errors() -> None:
    client = MagicMock()

    def _boom() -> Any:
        raise RuntimeError("openai boom")
        yield  # pragma: no cover

    client.chat.completions.create.return_value = _boom()
    with pytest.raises(RuntimeError, match="openai boom"):
        list(
            stream_final_answer(
                llm_client=client,
                config=_config(),
                messages=[],
            )
        )
