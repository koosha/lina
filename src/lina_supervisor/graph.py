"""LangGraph state machine for the supervisor.

Three nodes:
  - ``route``: send the message thread + tool definitions to OpenAI. The model
    either replies with a text-only answer (we end) or with one or more
    ``tool_calls`` (we proceed to ``execute_tools``).
  - ``execute_tools``: dispatch each ``tool_call`` via the WorkerHub. Append a
    ``tool``-role message per tool result keyed by ``tool_call_id``.
  - ``synthesize``: when the worker-call cap is hit, force a final streaming
    answer pass via ``synthesizer.stream_final_answer``.

The graph never speaks to the real OpenAI API in tests; the
``llm_client`` parameter is plain duck-typed and easily mocked.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lina_core.caller import CallerContext
from lina_supervisor.config import SupervisorConfig
from lina_supervisor.session import SessionStore
from lina_supervisor.synthesizer import stream_final_answer
from lina_supervisor.tools import build_tool_definitions
from lina_supervisor.workers import WorkerHub


class SupervisorState(TypedDict):
    """State carried through the LangGraph state machine."""

    messages: list[dict[str, Any]]
    caller: CallerContext
    worker_call_count: int
    worker_packets: list[dict[str, Any]]
    truncated: bool
    answer_text: str


def build_graph(
    *,
    config: SupervisorConfig,
    hub: WorkerHub,
    session_store: SessionStore,
    llm_client: Any,
) -> Any:
    """Compile the supervisor LangGraph state machine."""
    _ = session_store  # kept for API symmetry; future durability hook

    graph: Any = StateGraph(SupervisorState)
    graph.add_node("route", _make_route_node(config=config, client=llm_client))
    graph.add_node("execute_tools", _make_execute_tools_node(hub=hub))
    graph.add_node(
        "synthesize",
        _make_synthesize_node(config=config, client=llm_client),
    )

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        _route_condition,
        path_map={"tools": "execute_tools", "answer": END},
    )
    graph.add_conditional_edges(
        "execute_tools",
        _make_loop_condition(max_worker_calls=config.max_worker_calls),
        path_map={"more": "route", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)
    return graph.compile()


def _make_route_node(
    *,
    config: SupervisorConfig,
    client: Any,
) -> Callable[[SupervisorState], dict[str, Any]]:
    tools = build_tool_definitions()

    def route_node(state: SupervisorState) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_completion_tokens": config.route_max_tokens,
            "tools": tools,
            "tool_choice": "auto",
            "messages": state["messages"],
        }
        if config.reasoning_effort != "none":
            kwargs["reasoning_effort"] = config.reasoning_effort
        response = client.chat.completions.create(**kwargs)
        assistant_message = _assistant_message_from_response(response)
        new_messages = [*state["messages"], assistant_message]

        update: dict[str, Any] = {"messages": new_messages}
        # If the response is text-only, capture it as the answer.
        if not assistant_message.get("tool_calls") and assistant_message.get("content"):
            update["answer_text"] = assistant_message["content"]
        return update

    return route_node


def _make_execute_tools_node(*, hub: WorkerHub) -> Callable[[SupervisorState], dict[str, Any]]:
    def execute_tools_node(state: SupervisorState) -> dict[str, Any]:
        last_message = state["messages"][-1]
        assert last_message["role"] == "assistant"

        tool_calls = last_message.get("tool_calls") or []
        new_messages: list[dict[str, Any]] = []
        new_packets: list[dict[str, Any]] = []
        for call in tool_calls:
            function = call["function"]
            tool_name = function["name"]
            arguments_raw = function.get("arguments") or "{}"
            try:
                tool_input = json.loads(arguments_raw)
            except json.JSONDecodeError:
                tool_input = {}
            packet_dict = hub.dispatch(
                tool_name=tool_name,
                tool_input=tool_input,
                caller=state["caller"],
            )
            new_packets.append(packet_dict)
            new_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(packet_dict, default=str),
                }
            )

        return {
            "messages": [*state["messages"], *new_messages],
            "worker_call_count": state["worker_call_count"] + len(tool_calls),
            "worker_packets": [*state["worker_packets"], *new_packets],
        }

    return execute_tools_node


def _make_synthesize_node(
    *,
    config: SupervisorConfig,
    client: Any,
) -> Callable[[SupervisorState], dict[str, Any]]:
    def synthesize_node(state: SupervisorState) -> dict[str, Any]:
        chunks: list[str] = []
        for chunk in stream_final_answer(
            llm_client=client,
            config=config,
            messages=state["messages"],
        ):
            chunks.append(chunk)
        # Reaching synthesize means the worker-call cap was hit mid-conversation.
        return {"answer_text": "".join(chunks), "truncated": True}

    return synthesize_node


def _route_condition(state: SupervisorState) -> str:
    """Route to ``execute_tools`` if the latest assistant message has tool_calls."""
    last = state["messages"][-1]
    if last["role"] != "assistant":
        return "answer"
    return "tools" if last.get("tool_calls") else "answer"


def _make_loop_condition(*, max_worker_calls: int) -> Callable[[SupervisorState], str]:
    def loop_condition(state: SupervisorState) -> str:
        if state["worker_call_count"] >= max_worker_calls:
            return "synthesize"
        return "more"

    return loop_condition


def _assistant_message_from_response(response: Any) -> dict[str, Any]:
    """Convert an OpenAI ChatCompletion response to a serializable assistant turn."""
    message = response.choices[0].message
    content = getattr(message, "content", None)
    raw_tool_calls = getattr(message, "tool_calls", None) or []
    tool_calls: list[dict[str, Any]] = []
    for call in raw_tool_calls:
        function = getattr(call, "function", None)
        if function is None:
            continue
        tool_calls.append(
            {
                "id": getattr(call, "id", ""),
                "type": getattr(call, "type", "function"),
                "function": {
                    "name": getattr(function, "name", ""),
                    "arguments": getattr(function, "arguments", "") or "",
                },
            }
        )
    assistant: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        assistant["tool_calls"] = tool_calls
    return assistant
