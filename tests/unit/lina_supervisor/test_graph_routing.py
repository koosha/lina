"""Unit tests for the supervisor LangGraph state machine.

These tests use a stub Anthropic client that returns canned ``Message``
objects with predictable ``tool_use`` / ``text`` content blocks. Real API
calls never happen here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_core.caller import CallerContext
from lina_supervisor.config import SupervisorConfig
from lina_supervisor.graph import SupervisorState, build_graph
from lina_supervisor.session import InMemorySessionStore
from lina_supervisor.workers import WorkerHub


def _config() -> SupervisorConfig:
    return SupervisorConfig(anthropic_api_key="sk-test", max_worker_calls=3)


def _caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane",
        roles=frozenset({"reader"}),
        request_id="req-1",
    )


def _text_block(text: str) -> Any:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(*, name: str, tool_id: str, tool_input: dict[str, Any]) -> Any:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = tool_input
    return block


def _message(*, blocks: list[Any], stop_reason: str = "end_turn") -> Any:
    msg = MagicMock()
    msg.content = blocks
    msg.role = "assistant"
    msg.stop_reason = stop_reason
    return msg


class _StreamCtx:
    def __init__(self, chunks: list[str]) -> None:
        self.text_stream = iter(chunks)

    def __enter__(self) -> _StreamCtx:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None


def _stub_anthropic_client(
    *,
    routing_messages: list[Any],
    final_chunks: list[str] | None = None,
) -> MagicMock:
    """Return a MagicMock that yields routing messages then a stream context."""
    client = MagicMock()
    client.messages.create.side_effect = list(routing_messages)
    client.messages.stream.return_value = _StreamCtx(final_chunks or ["final"])
    return client


def _hub() -> tuple[WorkerHub, MagicMock, MagicMock, MagicMock]:
    rs = MagicMock()
    users = MagicMock()
    vendors = MagicMock()
    hub = WorkerHub(redshift_worker=rs, users_worker=users, vendors_worker=vendors)
    return hub, rs, users, vendors


def _ok_packet(source: str, query_type: str) -> Any:
    packet = MagicMock()
    packet.model_dump.return_value = {
        "source_engine": source,
        "result_type": query_type,
        "metrics": [{"value": 1}],
        "sql_trace_id": "trace",
        "row_count": 1,
        "truncated": False,
    }
    return packet


@pytest.mark.unit
def test_route_node_calls_claude_with_tools_and_messages() -> None:
    hub, _rs, _users, _vendors = _hub()
    routing = [_message(blocks=[_text_block("done")], stop_reason="end_turn")]
    client = _stub_anthropic_client(routing_messages=routing)
    config = _config()

    graph = build_graph(
        config=config,
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    state: SupervisorState = {
        "messages": [{"role": "user", "content": "hi"}],
        "caller": _caller(),
        "worker_call_count": 0,
        "worker_packets": [],
        "truncated": False,
        "answer_text": "",
    }
    graph.invoke(state)

    create_kwargs = client.messages.create.call_args.kwargs
    assert create_kwargs["model"] == config.model
    assert "tools" in create_kwargs
    assert any(t["name"] == "query_redshift" for t in create_kwargs["tools"])
    assert create_kwargs["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.unit
def test_execute_tools_node_dispatches_each_tool_use_block() -> None:
    hub, rs, users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")
    users.run.return_value = _ok_packet("opensearch", "user_lookup")

    routing = [
        _message(
            blocks=[
                _tool_use_block(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={
                        "query_type": "matter_lookup",
                        "params": {"matter_id": "m1"},
                    },
                ),
                _tool_use_block(
                    name="search_users",
                    tool_id="t2",
                    tool_input={
                        "query_type": "user_lookup",
                        "params": {"user_id": "u1"},
                    },
                ),
            ],
            stop_reason="tool_use",
        ),
        _message(blocks=[_text_block("done")], stop_reason="end_turn"),
    ]
    client = _stub_anthropic_client(routing_messages=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    final = graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": _caller(),
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    assert rs.run.call_count == 1
    assert users.run.call_count == 1
    assert final["worker_call_count"] == 2
    assert len(final["worker_packets"]) == 2


@pytest.mark.unit
def test_execute_tools_node_increments_worker_call_count() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")
    routing = [
        _message(
            blocks=[
                _tool_use_block(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ],
            stop_reason="tool_use",
        ),
        _message(blocks=[_text_block("ok")], stop_reason="end_turn"),
    ]
    client = _stub_anthropic_client(routing_messages=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    final = graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": _caller(),
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    assert final["worker_call_count"] == 1


@pytest.mark.unit
def test_synthesize_node_called_after_max_worker_calls_hit() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")

    # Each routing call yields one tool_use block. With max_worker_calls=2,
    # after 2 calls the loop forces synthesize.
    routing = [
        _message(
            blocks=[
                _tool_use_block(
                    name="query_redshift",
                    tool_id=f"t{n}",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ],
            stop_reason="tool_use",
        )
        for n in range(5)
    ]
    client = _stub_anthropic_client(
        routing_messages=routing,
        final_chunks=["The ", "answer"],
    )
    config = SupervisorConfig(anthropic_api_key="sk-test", max_worker_calls=2)
    graph = build_graph(
        config=config,
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    final = graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": _caller(),
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    assert final["worker_call_count"] == 2
    assert final["truncated"] is True
    assert client.messages.stream.called
    assert final["answer_text"] == "The answer"


@pytest.mark.unit
def test_truncated_flag_set_when_max_calls_reached() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")

    routing = [
        _message(
            blocks=[
                _tool_use_block(
                    name="query_redshift",
                    tool_id=f"t{n}",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ],
            stop_reason="tool_use",
        )
        for n in range(10)
    ]
    client = _stub_anthropic_client(
        routing_messages=routing,
        final_chunks=["ok"],
    )
    config = SupervisorConfig(anthropic_api_key="sk-test", max_worker_calls=1)
    graph = build_graph(
        config=config,
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    final = graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": _caller(),
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    assert final["truncated"] is True


@pytest.mark.unit
def test_graph_terminates_when_assistant_response_has_no_tool_use() -> None:
    hub, _rs, _users, _vendors = _hub()
    routing = [_message(blocks=[_text_block("hello")], stop_reason="end_turn")]
    client = _stub_anthropic_client(routing_messages=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    final = graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": _caller(),
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    # No tools were invoked; synthesizer was not used (text-only path).
    assert final["worker_call_count"] == 0
    assert client.messages.stream.called is False
    assert final["answer_text"] == "hello"


@pytest.mark.unit
def test_graph_propagates_caller_context_to_each_worker_call() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")
    routing = [
        _message(
            blocks=[
                _tool_use_block(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ],
            stop_reason="tool_use",
        ),
        _message(blocks=[_text_block("done")], stop_reason="end_turn"),
    ]
    client = _stub_anthropic_client(routing_messages=routing)
    caller = _caller()
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": caller,
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    assert rs.run.call_args.kwargs["caller"] == caller


@pytest.mark.unit
def test_graph_appends_each_message_to_state_messages() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")
    routing = [
        _message(
            blocks=[
                _tool_use_block(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ],
            stop_reason="tool_use",
        ),
        _message(blocks=[_text_block("done")], stop_reason="end_turn"),
    ]
    client = _stub_anthropic_client(routing_messages=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        anthropic_client=client,
    )
    final = graph.invoke(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "caller": _caller(),
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )
    # Initial user + assistant tool_use + tool_result + final assistant text = 4
    assert len(final["messages"]) >= 3
    # First non-initial message should be assistant
    assert final["messages"][1]["role"] == "assistant"
