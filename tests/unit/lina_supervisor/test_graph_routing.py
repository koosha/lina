"""Unit tests for the supervisor LangGraph state machine.

These tests use a stub OpenAI client that returns canned ``ChatCompletion``
objects with predictable ``tool_calls`` / text content. Real API calls never
happen here.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_core.caller import CallerContext
from lina_supervisor.config import SupervisorConfig
from lina_supervisor.graph import SupervisorState, build_graph
from lina_supervisor.session import InMemorySessionStore
from lina_supervisor.workers import WorkerHub


def _config() -> SupervisorConfig:
    return SupervisorConfig(openai_api_key="sk-test", max_worker_calls=3)


def _caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane",
        roles=frozenset({"reader"}),
        request_id="req-1",
    )


def _tool_call(*, name: str, tool_id: str, tool_input: dict[str, Any]) -> Any:
    """Build a mock OpenAI tool_call object."""
    function = MagicMock()
    function.name = name
    function.arguments = json.dumps(tool_input)
    call = MagicMock()
    call.id = tool_id
    call.type = "function"
    call.function = function
    return call


def _text_response(text: str) -> Any:
    """Build a mock ChatCompletion with text-only content."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]
    return response


def _tool_response(tool_calls: list[Any]) -> Any:
    """Build a mock ChatCompletion that contains tool_calls."""
    message = MagicMock()
    message.content = None
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "tool_calls"
    response = MagicMock()
    response.choices = [choice]
    return response


def _stream_chunk(text: str | None) -> Any:
    delta = MagicMock()
    delta.content = text
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _stub_openai_client(
    *,
    routing_responses: list[Any],
    final_chunks: list[str] | None = None,
) -> MagicMock:
    """Return a MagicMock that yields routing responses then a stream iterator."""
    client = MagicMock()
    chunks = [_stream_chunk(c) for c in (final_chunks or ["final"])]

    def _create(*_args: Any, **kwargs: Any) -> Any:
        if kwargs.get("stream"):
            return iter(chunks)
        return routing_responses.pop(0)

    client.chat.completions.create.side_effect = _create
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
def test_route_node_calls_openai_with_tools_and_messages() -> None:
    hub, _rs, _users, _vendors = _hub()
    routing = [_text_response("done")]
    client = _stub_openai_client(routing_responses=routing)
    config = _config()

    graph = build_graph(
        config=config,
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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

    create_kwargs = client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == config.model
    assert "tools" in create_kwargs
    assert any(t["function"]["name"] == "query_redshift" for t in create_kwargs["tools"])
    assert create_kwargs["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.unit
def test_execute_tools_node_dispatches_each_tool_call() -> None:
    hub, rs, users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")
    users.run.return_value = _ok_packet("opensearch", "user_lookup")

    routing = [
        _tool_response(
            [
                _tool_call(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={
                        "query_type": "matter_lookup",
                        "params": {"matter_id": "m1"},
                    },
                ),
                _tool_call(
                    name="search_users",
                    tool_id="t2",
                    tool_input={
                        "query_type": "user_lookup",
                        "params": {"user_id": "u1"},
                    },
                ),
            ]
        ),
        _text_response("done"),
    ]
    client = _stub_openai_client(routing_responses=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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
        _tool_response(
            [
                _tool_call(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ]
        ),
        _text_response("ok"),
    ]
    client = _stub_openai_client(routing_responses=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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

    # Each routing call yields one tool_call. With max_worker_calls=2,
    # after 2 calls the loop forces synthesize.
    routing = [
        _tool_response(
            [
                _tool_call(
                    name="query_redshift",
                    tool_id=f"t{n}",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ]
        )
        for n in range(5)
    ]
    client = _stub_openai_client(
        routing_responses=routing,
        final_chunks=["The ", "answer"],
    )
    config = SupervisorConfig(openai_api_key="sk-test", max_worker_calls=2)
    graph = build_graph(
        config=config,
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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
    # Synthesize streams via stream=True kwarg on chat.completions.create.
    stream_calls = [
        c for c in client.chat.completions.create.call_args_list if c.kwargs.get("stream")
    ]
    assert stream_calls
    assert final["answer_text"] == "The answer"


@pytest.mark.unit
def test_truncated_flag_set_when_max_calls_reached() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")

    routing = [
        _tool_response(
            [
                _tool_call(
                    name="query_redshift",
                    tool_id=f"t{n}",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ]
        )
        for n in range(10)
    ]
    client = _stub_openai_client(
        routing_responses=routing,
        final_chunks=["ok"],
    )
    config = SupervisorConfig(openai_api_key="sk-test", max_worker_calls=1)
    graph = build_graph(
        config=config,
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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
def test_graph_terminates_when_assistant_response_has_no_tool_calls() -> None:
    hub, _rs, _users, _vendors = _hub()
    routing = [_text_response("hello")]
    client = _stub_openai_client(routing_responses=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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
    stream_calls = [
        c for c in client.chat.completions.create.call_args_list if c.kwargs.get("stream")
    ]
    assert stream_calls == []
    assert final["answer_text"] == "hello"


@pytest.mark.unit
def test_graph_propagates_caller_context_to_each_worker_call() -> None:
    hub, rs, _users, _vendors = _hub()
    rs.run.return_value = _ok_packet("redshift", "matter_lookup")
    routing = [
        _tool_response(
            [
                _tool_call(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ]
        ),
        _text_response("done"),
    ]
    client = _stub_openai_client(routing_responses=routing)
    caller = _caller()
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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
        _tool_response(
            [
                _tool_call(
                    name="query_redshift",
                    tool_id="t1",
                    tool_input={"query_type": "matter_lookup", "params": {}},
                ),
            ]
        ),
        _text_response("done"),
    ]
    client = _stub_openai_client(routing_responses=routing)
    graph = build_graph(
        config=_config(),
        hub=hub,
        session_store=InMemorySessionStore(),
        llm_client=client,
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
    # Initial user + assistant tool_calls + tool result + final assistant text >= 3
    assert len(final["messages"]) >= 3
    # First non-initial message should be assistant
    assert final["messages"][1]["role"] == "assistant"
