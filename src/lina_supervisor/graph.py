"""LangGraph state machine for the supervisor.

Three nodes:
  - ``route``: send the message thread + tool definitions to Claude. The model
    either replies with a text-only answer (we end) or with one or more
    ``tool_use`` blocks (we proceed to ``execute_tools``).
  - ``execute_tools``: dispatch each ``tool_use`` block via the WorkerHub.
    Append a single user-role message containing all ``tool_result`` blocks.
  - ``synthesize``: when the worker-call cap is hit, force a final streaming
    answer pass via ``synthesizer.stream_final_answer``.

The graph never speaks to the real Anthropic API in tests; the
``anthropic_client`` parameter is plain duck-typed and easily mocked.
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
    anthropic_client: Any,
) -> Any:
    """Compile the supervisor LangGraph state machine."""
    _ = session_store  # kept for API symmetry; future durability hook

    graph: Any = StateGraph(SupervisorState)
    graph.add_node("route", _make_route_node(config=config, client=anthropic_client))
    graph.add_node("execute_tools", _make_execute_tools_node(hub=hub))
    graph.add_node(
        "synthesize",
        _make_synthesize_node(config=config, client=anthropic_client),
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
        message = client.messages.create(
            model=config.model,
            max_tokens=config.route_max_tokens,
            tools=tools,
            messages=state["messages"],
        )
        assistant_message = _assistant_message_from_response(message)
        new_messages = [*state["messages"], assistant_message]

        # If the response is text-only, capture it as the answer.
        text_blocks = [b for b in assistant_message["content"] if b["type"] == "text"]
        tool_use_blocks = [b for b in assistant_message["content"] if b["type"] == "tool_use"]
        update: dict[str, Any] = {"messages": new_messages}
        if text_blocks and not tool_use_blocks:
            update["answer_text"] = "".join(b["text"] for b in text_blocks)
        return update

    return route_node


def _make_execute_tools_node(*, hub: WorkerHub) -> Callable[[SupervisorState], dict[str, Any]]:
    def execute_tools_node(state: SupervisorState) -> dict[str, Any]:
        last_message = state["messages"][-1]
        assert last_message["role"] == "assistant"

        tool_use_blocks = [b for b in last_message["content"] if b["type"] == "tool_use"]
        tool_results: list[dict[str, Any]] = []
        new_packets: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            packet_dict = hub.dispatch(
                tool_name=block["name"],
                tool_input=block["input"],
                caller=state["caller"],
            )
            new_packets.append(packet_dict)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(packet_dict, default=str),
                }
            )

        tool_results_message = {"role": "user", "content": tool_results}
        return {
            "messages": [*state["messages"], tool_results_message],
            "worker_call_count": state["worker_call_count"] + len(tool_use_blocks),
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
            anthropic_client=client,
            config=config,
            messages=state["messages"],
        ):
            chunks.append(chunk)
        # Reaching synthesize means the worker-call cap was hit mid-conversation.
        return {"answer_text": "".join(chunks), "truncated": True}

    return synthesize_node


def _route_condition(state: SupervisorState) -> str:
    """Route to ``execute_tools`` if the latest assistant message has tool_use."""
    last = state["messages"][-1]
    if last["role"] != "assistant":
        return "answer"
    tool_use = [b for b in last["content"] if b["type"] == "tool_use"]
    return "tools" if tool_use else "answer"


def _make_loop_condition(*, max_worker_calls: int) -> Callable[[SupervisorState], str]:
    def loop_condition(state: SupervisorState) -> str:
        if state["worker_call_count"] >= max_worker_calls:
            return "synthesize"
        return "more"

    return loop_condition


def _assistant_message_from_response(response: Any) -> dict[str, Any]:
    """Convert an anthropic Message response to a serializable assistant turn."""
    blocks: list[dict[str, Any]] = []
    for block in response.content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            blocks.append({"type": "text", "text": block.text})
        elif block_type == "tool_use":
            blocks.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input) if block.input is not None else {},
                }
            )
        else:
            # Unknown block type — ignore silently, the LLM may have produced
            # something we don't model yet.
            continue
    return {"role": "assistant", "content": blocks}
