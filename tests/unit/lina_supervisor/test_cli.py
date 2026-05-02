"""Unit tests for the lina-chat CLI.

Backends are stubbed via monkeypatching the worker factory functions in
``lina_supervisor.cli`` and the OpenAI client returned by
``_build_openai_client``. No real network calls happen.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from lina_users.packet import ResultPacket as UsersResultPacket


def _users_lookup_packet() -> UsersResultPacket:
    return UsersResultPacket(
        result_type="user_lookup",
        metrics=[
            {
                "user_id": "user_jane",
                "roles": ["legal_ops"],
                "permission_tags": ["all_matters"],
            }
        ],
        sql_trace_id="01J0000000000000000000000",
        row_count=1,
        truncated=False,
    )


def _stream_chunk(text: str | None) -> Any:
    delta = MagicMock()
    delta.content = text
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _text_response(text: str) -> Any:
    """Build a mock OpenAI ChatCompletion with text-only content."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]
    return response


def _stub_openai(
    *,
    routing_responses: list[Any],
    final_chunks: list[str] | None = None,
) -> MagicMock:
    client = MagicMock()
    chunks = [_stream_chunk(c) for c in (final_chunks or ["final"])]

    def _create(*_args: Any, **kwargs: Any) -> Any:
        if kwargs.get("stream"):
            return iter(chunks)
        return routing_responses.pop(0)

    client.chat.completions.create.side_effect = _create
    return client


def _patch_cli(
    monkeypatch: pytest.MonkeyPatch,
    *,
    llm_client: MagicMock,
    user_lookup_packet: UsersResultPacket | None = None,
    user_lookup_raises: Exception | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Stub CLI factory functions and return (users, redshift, vendors) workers."""
    import lina_supervisor.cli as cli

    redshift_worker = MagicMock()
    users_worker = MagicMock()
    vendors_worker = MagicMock()
    if user_lookup_raises is not None:
        users_worker.run.side_effect = user_lookup_raises
    elif user_lookup_packet is not None:
        users_worker.run.return_value = user_lookup_packet

    monkeypatch.setattr(cli, "_build_openai_client", lambda _cfg: llm_client)
    monkeypatch.setattr(cli, "_build_redshift_worker", lambda: redshift_worker)
    monkeypatch.setattr(cli, "_build_users_worker", lambda: users_worker)
    monkeypatch.setattr(cli, "_build_vendors_worker", lambda: vendors_worker)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    return users_worker, redshift_worker, vendors_worker


@pytest.mark.unit
def test_ask_one_shot_emits_supervisor_response_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lina_supervisor.cli import main

    client = _stub_openai(routing_responses=[_text_response("Hello, Jane.")])
    _patch_cli(monkeypatch, llm_client=client, user_lookup_packet=_users_lookup_packet())

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "ask",
            "--user-id",
            "user_jane",
            "--query",
            "hi",
            "--no-stream",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["source_engine"] == "supervisor"
    assert payload["user_id"] == "user_jane"
    assert payload["answer_text"] == "Hello, Jane."


@pytest.mark.unit
def test_ask_streams_token_by_token_in_default_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lina_supervisor.cli import main

    client = _stub_openai(routing_responses=[_text_response("streamed text")])
    _patch_cli(monkeypatch, llm_client=client, user_lookup_packet=_users_lookup_packet())

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ask", "--user-id", "user_jane", "--query", "hi"],
    )
    assert result.exit_code == 0, result.stdout
    # Streaming default prints the answer text directly.
    assert "streamed text" in result.stdout


@pytest.mark.unit
def test_ask_returns_error_for_unknown_user_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lina_supervisor.cli import main

    client = _stub_openai(routing_responses=[_text_response("never reached")])
    empty_lookup = UsersResultPacket(
        result_type="user_lookup",
        metrics=[],
        sql_trace_id="01J0000000000000000000000",
        row_count=0,
        truncated=False,
    )
    _patch_cli(monkeypatch, llm_client=client, user_lookup_packet=empty_lookup)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ask", "--user-id", "user_ghost", "--query", "hi", "--no-stream"],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "user_ghost" in combined or "not found" in combined.lower()


@pytest.mark.unit
def test_repl_handles_multiple_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    from lina_supervisor.cli import main

    client = _stub_openai(
        routing_responses=[
            _text_response("turn one answer"),
            _text_response("turn two answer"),
        ]
    )
    _patch_cli(monkeypatch, llm_client=client, user_lookup_packet=_users_lookup_packet())

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["repl", "--user-id", "user_jane"],
        input="first\nsecond\n",
    )
    assert result.exit_code == 0, result.stdout
    assert "turn one answer" in result.stdout
    assert "turn two answer" in result.stdout


@pytest.mark.unit
def test_max_worker_calls_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """The --max-worker-calls flag is forwarded into SupervisorConfig."""
    import lina_supervisor.cli as cli

    captured: dict[str, Any] = {}
    real_build_supervisor = cli._build_supervisor

    def _capture(*, config: Any, **kwargs: Any) -> Any:
        captured["max_worker_calls"] = config.max_worker_calls
        return real_build_supervisor(config=config, **kwargs)

    monkeypatch.setattr(cli, "_build_supervisor", _capture)
    client = _stub_openai(routing_responses=[_text_response("ok")])
    _patch_cli(monkeypatch, llm_client=client, user_lookup_packet=_users_lookup_packet())

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "ask",
            "--user-id",
            "user_jane",
            "--query",
            "hi",
            "--no-stream",
            "--max-worker-calls",
            "3",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert captured["max_worker_calls"] == 3


@pytest.mark.unit
def test_no_stream_flag_emits_single_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from lina_supervisor.cli import main

    client = _stub_openai(routing_responses=[_text_response("Hi.")])
    _patch_cli(monkeypatch, llm_client=client, user_lookup_packet=_users_lookup_packet())

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ask", "--user-id", "user_jane", "--query", "hi", "--no-stream"],
    )
    assert result.exit_code == 0
    # Output must be a single, parsable JSON document and nothing else.
    payload = json.loads(result.stdout)
    assert payload["answer_text"] == "Hi."
