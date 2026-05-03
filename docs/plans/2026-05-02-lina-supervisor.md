# LINA Supervisor (Subsystem D) Implementation Plan

> **Update 2026-05-02:** Subsystem D shipped initially against Anthropic Claude. Per a follow-up dispatch, the LLM provider was swapped to OpenAI (interim default `gpt-4o`, then retuned to `gpt-5.2` with optional `reasoning_effort=none|low|medium|high|xhigh` and `max_completion_tokens` instead of `max_tokens`). The architecture and task structure described below are unchanged; replace any reference to the `anthropic` SDK with `openai` and `ANTHROPIC_API_KEY` with `OPENAI_API_KEY`. Tool definitions moved from Anthropic's `{name, description, input_schema}` shape to OpenAI's `{type: "function", function: {name, description, parameters}}` shape; tool results moved from `user`-role `tool_result` blocks to `tool`-role messages keyed by `tool_call_id`.

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Ship `lina_supervisor` — a Python package + `lina-chat` CLI that turns natural-language questions from lawyers into typed worker calls (Subsystems A, B, C) and synthesizes answers via Claude tool use, orchestrated by LangGraph.

**Architecture:** LangGraph state machine with three nodes (route → execute_tools → synthesize → respond). Three Claude tool definitions (`query_redshift`, `search_users`, `search_vendors`), each accepting `{query_type, params}` matching existing template registries. In-memory session store. Streaming output. Cost cap via `max_worker_calls=8` per user turn.

**Tech Stack:** Python 3.12, anthropic>=0.42, langgraph>=0.2, langchain-core, langchain-anthropic, pydantic v2, click, structlog, vcrpy + pytest-vcr (dev).

**Spec reference:** `docs/design/2026-05-02-lina-supervisor-design.md`. Read §4–§10 for tool/graph/session details.

**Pattern reference:** the worker plumbing patterns from C (and the OpenSearch dispatch from A/B) are reused here. The supervisor is a *consumer* of those workers — it never reaches into their templates directly.

**Authorized minor deviations** (silent):
- UP035, UP037, RET504, N812 noqa
- `result.stdout` for Click 8.3 CliRunner
- Pin `anthropic` SDK minor version if VCR cassettes prove sensitive (record once, replay forever — pin to whatever was used to record)

**Commit authorship:** Every commit + tag annotation authored by `koosha <koosha.g@gmail.com>`. **No** `Co-Authored-By: Claude` or AI attribution anywhere.

---

## Task D0: Dependencies + Skeleton

**Files:**
- Modify: `pyproject.toml`
- Modify: `mypy.ini`
- Create: `src/lina_supervisor/__init__.py`
- Create: `src/lina_supervisor/cli.py` (placeholder so console-script entry resolves)
- Create: `tests/unit/lina_supervisor/__init__.py`
- Create: `tests/integration/lina_supervisor/__init__.py`

- [ ] **Step 1:** Add to `pyproject.toml` `dependencies`: `anthropic>=0.42`, `langgraph>=0.2`, `langchain-core>=0.3`, `langchain-anthropic>=0.2`. Add to `[project.optional-dependencies].dev`: `vcrpy>=6.0`, `pytest-vcr>=1.0`. Add to `[project.scripts]`: `lina-chat = "lina_supervisor.cli:main"`.
- [ ] **Step 2:** Update `mypy.ini` `files = src/lina_core, src/lina_redshift, src/lina_users, src/lina_vendors, src/lina_supervisor`. Add ignore_missing_imports stanzas for `langgraph.*`, `langchain_core.*`, `langchain_anthropic.*`, `vcr.*`.
- [ ] **Step 3:** Create `src/lina_supervisor/__init__.py` with `__version__ = "0.1.0"`. Create placeholder `src/lina_supervisor/cli.py` with a `def main(): raise SystemExit("not implemented")` stub.
- [ ] **Step 4:** Create the test-package `__init__.py` files (empty).
- [ ] **Step 5:** Reinstall: `.venv/bin/pip install -e ".[dev]"`. Verify imports: `.venv/bin/python -c "import lina_supervisor, anthropic, langgraph; print('ok')"`.
- [ ] **Step 6:** Run full suite + mypy + ruff. All green (no new tests yet; existing 252 unit tests still pass except the pre-existing 56 pytest-postgresql memory errors which are environment-specific).
- [ ] **Step 7:** Commit. `chore: add anthropic + langgraph deps and lina_supervisor package skeleton`

---

## Task D1: SupervisorConfig + SessionStore

**Files:**
- Create: `src/lina_supervisor/config.py`
- Create: `src/lina_supervisor/session.py`
- Create: `src/lina_supervisor/packet.py`
- Create: `tests/unit/lina_supervisor/test_config.py`
- Create: `tests/unit/lina_supervisor/test_session.py`
- Create: `tests/unit/lina_supervisor/test_packet.py`

- [ ] **Step 1: Failing tests for `SupervisorConfig`**

`tests/unit/lina_supervisor/test_config.py` — 5 tests:
- `test_default_model_is_claude_sonnet_4_7`
- `test_default_max_worker_calls_is_8`
- `test_resolve_config_from_env_overrides`
- `test_resolve_config_requires_anthropic_api_key`
- `test_resolve_config_reads_max_tokens_overrides`

- [ ] **Step 2: Implement `SupervisorConfig`**

```python
"""Supervisor configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


class MissingApiKeyError(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is unset."""


@dataclass(frozen=True)
class SupervisorConfig:
    anthropic_api_key: str
    model: str = "claude-sonnet-4-7"
    max_worker_calls: int = 8
    route_max_tokens: int = 2048
    synthesize_max_tokens: int = 4096
    request_timeout_seconds: int = 60


def resolve_config() -> SupervisorConfig:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingApiKeyError("ANTHROPIC_API_KEY is not set")
    return SupervisorConfig(
        anthropic_api_key=api_key,
        model=os.environ.get("LINA_SUPERVISOR_MODEL", "claude-sonnet-4-7"),
        max_worker_calls=int(os.environ.get("LINA_SUPERVISOR_MAX_WORKER_CALLS", "8")),
        route_max_tokens=int(os.environ.get("LINA_SUPERVISOR_ROUTE_MAX_TOKENS", "2048")),
        synthesize_max_tokens=int(
            os.environ.get("LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS", "4096")
        ),
        request_timeout_seconds=int(
            os.environ.get("LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS", "60")
        ),
    )
```

- [ ] **Step 3: Failing tests for `Session` + `InMemorySessionStore`**

`tests/unit/lina_supervisor/test_session.py` — 6 tests:
- `test_session_creation_with_caller`
- `test_get_or_create_returns_existing_session`
- `test_get_or_create_initializes_new_session`
- `test_append_message_grows_list`
- `test_update_caller_replaces_caller`
- `test_protocol_compliance` (assert `InMemorySessionStore` satisfies `SessionStore` Protocol via duck-type checks)

- [ ] **Step 4: Implement `session.py`**

`src/lina_supervisor/session.py`:
```python
"""Session models and in-memory store. Pluggable backend via SessionStore Protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from lina_core.caller import CallerContext


@dataclass
class Session:
    session_id: str
    user_id: str
    caller: CallerContext
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    worker_call_count_total: int = 0


class SessionStore(Protocol):
    def get_or_create(
        self, *, session_id: str, user_id: str, caller: CallerContext,
    ) -> Session: ...

    def append_message(self, *, session_id: str, message: dict[str, Any]) -> None: ...

    def update_caller(self, *, session_id: str, caller: CallerContext) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(
        self, *, session_id: str, user_id: str, caller: CallerContext,
    ) -> Session:
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_activity = datetime.now(UTC)
            return session
        session = Session(session_id=session_id, user_id=user_id, caller=caller)
        self._sessions[session_id] = session
        return session

    def append_message(self, *, session_id: str, message: dict[str, Any]) -> None:
        session = self._sessions[session_id]
        session.messages.append(message)
        session.last_activity = datetime.now(UTC)

    def update_caller(self, *, session_id: str, caller: CallerContext) -> None:
        self._sessions[session_id].caller = caller
```

- [ ] **Step 5: Failing tests + implementation for `SupervisorResponse`**

`packet.py`:
```python
"""SupervisorResponse — final shape returned by lina-chat."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SupervisorResponse(BaseModel):
    source_engine: Literal["supervisor"] = "supervisor"
    session_id: str
    request_id: str
    user_id: str
    answer_text: str
    worker_packets: list[dict[str, Any]] = []
    worker_call_count: int = 0
    truncated: bool = False
    model: str
    duration_ms: int
    sql_trace_id: str
```

`test_packet.py` — 3 tests asserting the shape, JSON serialization, default values.

- [ ] **Step 6: Run all D1 tests, full suite, mypy, ruff. Commit.**
  ```bash
  git -C "..." commit -m "feat(supervisor): add SupervisorConfig, Session store, and response packet"
  ```

---

## Task D2: WorkerHub + Tool Definitions

**Files:**
- Create: `src/lina_supervisor/tools.py`
- Create: `src/lina_supervisor/workers.py`
- Create: `tests/unit/lina_supervisor/test_tools.py`
- Create: `tests/unit/lina_supervisor/test_workers_dispatch.py`

- [ ] **Step 1: Failing tests for tool definitions**

`tests/unit/lina_supervisor/test_tools.py` — 6 tests:
- `test_three_tools_defined` (exactly `query_redshift`, `search_users`, `search_vendors`)
- `test_each_tool_has_input_schema`
- `test_query_redshift_query_type_enum_matches_redshift_registry` (asserts the JSON schema's `query_type` enum equals `set(TEMPLATE_REGISTRY.keys())` for `lina_redshift`)
- `test_search_users_query_type_enum_matches_users_registry`
- `test_search_vendors_query_type_enum_matches_vendors_registry`
- `test_build_tool_definitions_per_template_params_schemas` (asserts each `query_type` has its detailed Params schema available)

- [ ] **Step 2: Implement `tools.py`**

```python
"""Claude tool definitions exposed to the supervisor LLM."""

from __future__ import annotations

from typing import Any

from lina_redshift.templates import TEMPLATE_REGISTRY as RS_REGISTRY
from lina_users.templates import TEMPLATE_REGISTRY as USERS_REGISTRY
from lina_vendors.templates import TEMPLATE_REGISTRY as VENDORS_REGISTRY


def build_tool_definitions() -> list[dict[str, Any]]:
    return [
        _tool_for_subsystem(
            name="query_redshift",
            description=(
                "Run a typed query against the legal_matter_spend Redshift store. "
                "Use for matter, vendor, timekeeper spend analytics; invoice or "
                "budget data; rate analysis."
            ),
            registry=RS_REGISTRY,
        ),
        _tool_for_subsystem(
            name="search_users",
            description=(
                "Search corporate user profiles. Use for finding internal users by "
                "name, role, department, or to walk reporting chains."
            ),
            registry=USERS_REGISTRY,
        ),
        _tool_for_subsystem(
            name="search_vendors",
            description=(
                "Search outside counsel lawyer profiles. Use for finding vendor "
                "lawyers by name, vendor, practice area, jurisdiction, or "
                "hourly-rate band."
            ),
            registry=VENDORS_REGISTRY,
        ),
    ]


def _tool_for_subsystem(*, name: str, description: str, registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {"type": "string", "enum": sorted(registry.keys())},
                "params": {"type": "object"},
            },
            "required": ["query_type", "params"],
        },
    }


def per_template_params_schemas() -> dict[str, dict[str, Any]]:
    """Return query_type → Params JSON schema for the system prompt."""
    out: dict[str, dict[str, Any]] = {}
    for registry in (RS_REGISTRY, USERS_REGISTRY, VENDORS_REGISTRY):
        for query_type, template in registry.items():
            out[query_type] = template.Params.model_json_schema()
    return out
```

- [ ] **Step 3: Failing tests for `WorkerHub`**

`tests/unit/lina_supervisor/test_workers_dispatch.py` — 7 tests using mocked workers:
- `test_dispatch_query_redshift_routes_to_redshift_worker`
- `test_dispatch_search_users_routes_to_users_worker`
- `test_dispatch_search_vendors_routes_to_vendors_worker`
- `test_dispatch_unknown_tool_returns_error_packet_dict`
- `test_dispatch_returns_json_serializable_dict_for_tool_result`
- `test_dispatch_handles_authorization_error_via_error_packet`
- `test_dispatch_handles_invalid_params_via_error_packet`

- [ ] **Step 4: Implement `workers.py`**

```python
"""Façade that dispatches Claude tool calls to the right subsystem worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lina_core.caller import CallerContext


@dataclass
class WorkerHub:
    redshift_worker: Any   # RedshiftWorker; typed as Any to avoid hard import dependency for tests
    users_worker: Any      # UserSearchWorker
    vendors_worker: Any    # VendorSearchWorker

    def dispatch(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        caller: CallerContext,
    ) -> dict[str, Any]:
        query_type = tool_input.get("query_type", "")
        params = tool_input.get("params", {})
        if tool_name == "query_redshift":
            packet = self.redshift_worker.run(
                query_type=query_type, params=params, caller=caller,
            )
        elif tool_name == "search_users":
            packet = self.users_worker.run(
                query_type=query_type, params=params, caller=caller,
            )
        elif tool_name == "search_vendors":
            packet = self.vendors_worker.run(
                query_type=query_type, params=params, caller=caller,
            )
        else:
            return {
                "source_engine": "supervisor",
                "result_type": tool_name,
                "error": {
                    "type": "UnknownToolError",
                    "message": f"no worker registered for tool {tool_name!r}",
                },
            }
        return packet.model_dump(by_alias=True)
```

- [ ] **Step 5: Run tests, full suite, mypy, ruff. Commit.**
  ```bash
  git -C "..." commit -m "feat(supervisor): add Claude tool definitions and WorkerHub dispatch"
  ```

---

## Task D3: CallerResolver

**Files:**
- Create: `src/lina_supervisor/caller_resolver.py`
- Create: `tests/unit/lina_supervisor/test_caller_resolver.py`

- [ ] **Step 1: Failing tests** — 5 tests covering: bootstrap caller construction, resolves user via `user_lookup`, builds CallerContext from profile, raises on unknown user, falls back to defaults when role fields missing.

- [ ] **Step 2: Implement `caller_resolver.py`**

```python
"""Resolve a user_id into a fully populated CallerContext via Subsystem A."""

from __future__ import annotations

from dataclasses import dataclass

from lina_core.caller import CallerContext


_BOOTSTRAP_CALLER = CallerContext(
    user_id="lina_supervisor_bootstrap",
    roles=frozenset({"caller_resolver"}),
    permission_tags=frozenset(),
    request_id="bootstrap",
)


class UserNotFoundError(RuntimeError):
    pass


@dataclass
class CallerResolver:
    users_worker: object  # UserSearchWorker

    def resolve(self, *, user_id: str, request_id: str) -> CallerContext:
        packet = self.users_worker.run(  # type: ignore[attr-defined]
            query_type="user_lookup",
            params={"user_id": user_id},
            caller=_BOOTSTRAP_CALLER,
        )
        # Allow bootstrap caller through user_lookup. The user_lookup template
        # has allowed_roles == frozenset({"*"}) so caller_resolver passes.
        if not getattr(packet, "metrics", None):
            raise UserNotFoundError(f"user_id {user_id!r} not found")
        profile = packet.metrics[0]
        return CallerContext(
            user_id=profile["user_id"],
            roles=frozenset(profile.get("roles", [])) or frozenset({"reader"}),
            permission_tags=frozenset(profile.get("permission_tags", [])),
            request_id=request_id,
        )
```

- [ ] **Step 3: Tests pass, full suite, mypy, ruff. Commit.**
  ```bash
  git -C "..." commit -m "feat(supervisor): add CallerResolver via Subsystem A user_lookup"
  ```

---

## Task D4: Graph + Routing Logic

**Files:**
- Create: `src/lina_supervisor/graph.py`
- Create: `tests/unit/lina_supervisor/test_graph_routing.py`

- [ ] **Step 1: Failing tests** — 8 tests using a mocked `anthropic.Anthropic` client whose `messages.create()` returns canned responses:
  - `test_route_node_calls_claude_with_tools_and_messages`
  - `test_execute_tools_node_dispatches_each_tool_use_block`
  - `test_execute_tools_node_increments_worker_call_count`
  - `test_synthesize_node_called_after_max_worker_calls_hit`
  - `test_truncated_flag_set_when_max_calls_reached`
  - `test_graph_terminates_when_assistant_response_has_no_tool_use`
  - `test_graph_propagates_caller_context_to_each_worker_call`
  - `test_graph_appends_each_message_to_session_store`

- [ ] **Step 2: Implement `graph.py`**

LangGraph 0.2 API. Build a `StateGraph` with the node sequence described in the spec. Use `langchain_core.messages.{HumanMessage, AIMessage, ToolMessage}` for the message list. Use `anthropic.Anthropic` directly (not `langchain_anthropic`) for tighter control over `tool_use` parsing.

Key implementation:

```python
from langgraph.graph import StateGraph, START, END
from anthropic import Anthropic

class SupervisorState(TypedDict):
    messages: list[dict]
    caller: CallerContext
    worker_call_count: int
    worker_packets: list[dict]
    truncated: bool


def build_graph(*, config, hub, session_store, anthropic_client):
    graph = StateGraph(SupervisorState)
    graph.add_node("route", make_route_node(config, anthropic_client))
    graph.add_node("execute_tools", make_execute_tools_node(hub, config))
    graph.add_node("synthesize", make_synthesize_node(config, anthropic_client))
    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        condition=route_condition,
        path_map={"tools": "execute_tools", "answer": END},
    )
    graph.add_conditional_edges(
        "execute_tools",
        condition=loop_condition,  # if worker_call_count >= max → synthesize, else → route
        path_map={"more": "route", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)
    return graph.compile()
```

The `route_node` makes a non-streaming Claude call to reduce complexity in the routing layer. Streaming happens only in `synthesize_node`.

- [ ] **Step 3: Tests pass, full suite, mypy, ruff. Commit.**
  ```bash
  git -C "..." commit -m "feat(supervisor): add LangGraph state machine for routing and tool execution"
  ```

---

## Task D5: Synthesizer + Streaming

**Files:**
- Create: `src/lina_supervisor/synthesizer.py`
- Create: `tests/unit/lina_supervisor/test_synthesizer.py`

- [ ] **Step 1: Failing tests** — 5 tests on streaming chunk handling, final-pass prompt contents, max_tokens enforcement, error handling.

- [ ] **Step 2: Implement `synthesizer.py`**

```python
"""Final synthesis pass: combines worker results into the user-facing answer."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


_FINAL_INSTRUCTION = (
    "You have all the data needed. Produce the final answer for the user. "
    "Cite the worker results you used (\"Sources: ...\") at the end. "
    "Do not call any more tools."
)


def stream_final_answer(
    *,
    anthropic_client: Any,
    config: Any,  # SupervisorConfig
    messages: list[dict[str, Any]],
) -> Iterator[str]:
    """Yield text chunks from the synthesizer pass."""
    final_messages = [*messages, {"role": "user", "content": _FINAL_INSTRUCTION}]
    with anthropic_client.messages.stream(
        model=config.model,
        max_tokens=config.synthesize_max_tokens,
        messages=final_messages,
        timeout=config.request_timeout_seconds,
    ) as stream:
        for event in stream.text_stream:
            yield event
```

- [ ] **Step 3: Commit.**
  ```bash
  git -C "..." commit -m "feat(supervisor): add streaming synthesizer for final answer"
  ```

---

## Task D6: CLI

**Files:**
- Replace: `src/lina_supervisor/cli.py` (currently a stub)
- Create: `tests/unit/lina_supervisor/test_cli.py`

- [ ] **Step 1: Failing tests** — 6 tests using `CliRunner` and mocked Anthropic + workers:
  - `test_ask_one_shot_emits_supervisor_response_json`
  - `test_ask_streams_token_by_token`
  - `test_ask_returns_error_for_unknown_user_id`
  - `test_repl_handles_multiple_turns`
  - `test_max_worker_calls_override`
  - `test_no_stream_flag_emits_single_json`

- [ ] **Step 2: Implement `cli.py`**

```python
"""lina-chat CLI."""

from __future__ import annotations

import json
import sys

import click

from lina_core.logging_config import configure_logging
from lina_supervisor.config import resolve_config
# ... (rest of imports)


@click.group()
def main() -> None:
    configure_logging()


@main.command("ask")
@click.option("--user-id", required=True)
@click.option("--query", required=True)
@click.option("--session-id", default=None)
@click.option("--no-stream", is_flag=True, default=False)
@click.option("--max-worker-calls", type=int, default=None)
@click.option("--model", default=None)
def ask_cmd(...) -> None:
    """One-shot mode: single ask, response, exit."""
    ...


@main.command("repl")
@click.option("--user-id", required=True)
@click.option("--session-id", default=None)
def repl_cmd(...) -> None:
    """Interactive REPL."""
    ...
```

Implementation: build the supervisor via factory functions that compose `SupervisorConfig`, instantiate workers (lazy: only if backend env vars are set), wire `WorkerHub`, `CallerResolver`, `InMemorySessionStore`, the LangGraph compiled graph, and the streaming synthesizer.

- [ ] **Step 3: Tests pass, full suite, mypy, ruff. Commit.**
  ```bash
  git -C "..." commit -m "feat(supervisor): add lina-chat CLI (ask + repl modes)"
  ```

---

## Task D7: VCR-Replayed Integration Tests

**Files:**
- Create: `tests/integration/lina_supervisor/conftest.py`
- Create: `tests/integration/lina_supervisor/test_smoke_simple_query.py`
- Create: `tests/integration/lina_supervisor/test_smoke_multi_step.py`
- Create: `tests/integration/lina_supervisor/cassettes/` (committed YAML)

- [ ] **Step 1:** Create `conftest.py` configuring `pytest-vcr` to filter `Authorization` and `x-api-key` headers from cassettes (security). Mark all tests in this directory `@pytest.mark.integration`.

- [ ] **Step 2:** Write `test_smoke_simple_query.py`:
  - One test that asks "How many open litigation matters do we have?" and asserts the answer text mentions a count + cites `query_redshift(matter_spend_summary)` or similar.
  - Skipped without `ANTHROPIC_API_KEY` for record mode; cassettes-only mode replays without the key.

- [ ] **Step 3:** Write `test_smoke_multi_step.py`:
  - Two-step query: "How much did Walker bill on the Acme litigation last quarter?" — requires search_vendors + query_redshift sequence.

- [ ] **Step 4:** Run tests in record mode once with a real API key (locally), commit the resulting YAML cassettes. Tests then replay deterministically without an API key.

- [ ] **Step 5:** Commit.
  ```bash
  git -C "..." commit -m "test(supervisor): add VCR-replayed integration smoke tests"
  ```

Note: if recording cassettes requires interactive use of an API key the user holds, the implementer should prepare the cassette infrastructure but stop at the record step and report DONE_WITH_CONCERNS. Cassette recording can be a follow-up.

---

## Task D8: README + Final Sweep + Tag v1.0.0 + Push

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Extend README with:
  - `lina-chat` quickstart (`ANTHROPIC_API_KEY=... lina-chat ask --user-id user_jane_smith --query "..."`)
  - REPL example
  - "How the supervisor works" section (3-4 sentences linking to spec §5 graph)
  - Cost guardrails note
  - Add `lina-chat` to the env-var table

- [ ] **Step 2:** Final sweep:
  ```bash
  .venv/bin/pytest -v
  .venv/bin/mypy
  .venv/bin/ruff check src tests
  .venv/bin/ruff format --check src tests
  .venv/bin/coverage run -m pytest && .venv/bin/coverage report --fail-under=80
  ```

- [ ] **Step 3:** Commit. `docs: extend README for supervisor and lina-chat CLI`

- [ ] **Step 4:** Tag.
  ```bash
  git -C "..." tag -a v1.0.0 -m "LINA v1.0.0 — full system (Subsystems A + B + C + D)"
  ```
  Tag annotation **must** have no AI attribution.

- [ ] **Step 5:** Push (to a NEW branch — no force-push to existing). Suggested branch: `init/full-system`. The user can promote it to default via GitHub UI.
  ```bash
  git -C "..." push origin master:init/full-system
  git -C "..." push origin v1.0.0
  ```

  Both pushes may be blocked by the default-branch hook. If so, report BLOCKED and request the user lift the hook or push manually.

---

## Self-Review

**Spec coverage:** §4 tools (D2), §5 graph (D4), §6 worker hub (D2), §7 caller resolver (D3), §8 session store (D1), §9 CLI (D6), §10 SupervisorResponse (D1), §11 cost guardrails (config + graph), §12 out-of-scope (none in plan), §13 success criteria (D7 integration + D8 final sweep).

**Type consistency:** `SupervisorConfig`, `WorkerHub.dispatch(*, tool_name, tool_input, caller) -> dict`, `CallerResolver.resolve(*, user_id, request_id) -> CallerContext`, `Session`, `SessionStore` Protocol, `SupervisorResponse` — names consistent across tasks.

**Placeholder scan:** No "TBD"; every step has actionable code or a concrete command.

---

**Estimated commit count:** 9 (1 chore + 7 features + 1 docs + 1 tag).
**Estimated test count delta:** +45-55 unit tests (≈300+ total).
