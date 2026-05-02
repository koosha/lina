# LINA — Supervisor (Subsystem D) Design

**Status:** Approved for planning
**Date:** 2026-05-02
**Source spec:** [`lina.md`](../../../lina.md) — Scope section + worker contracts
**Scope:** Fourth and final sub-project. The supervisor wires Subsystems A, B, C into a chat-style interface for lawyers. Reads but does not modify any of the three data stores.

This spec **inherits** locked decisions from C ([2026-05-02-lina-redshift-worker-design.md](2026-05-02-lina-redshift-worker-design.md)) and A+B ([2026-05-02-lina-opensearch-workers-design.md](2026-05-02-lina-opensearch-workers-design.md)) where applicable: Python 3.12, monorepo, `lina_core` shared package, structlog, `koosha`-only commits.

---

## 1. Goal

Ship `lina_supervisor` — a Python package + CLI (`lina-chat`) that takes a natural-language question from a lawyer, decides which worker(s) to call, dispatches typed query plans to A/B/C, synthesizes the result with an LLM (OpenAI `gpt-5.2`), and returns a normalized answer. Multi-turn conversation supported via in-memory session state. Production hardening (durable state, FastAPI, AWS deployment) deferred.

End-to-end example flow:

```text
User: "How much have we spent with Walker & Associates on the Acme litigation last quarter?"

Supervisor LLM thinks:
  -> needs vendor_id for Walker & Associates → tool_call: search_vendors {query: "Walker & Associates"}
  -> Subsystem B returns vendor_id: vendor_walker
  -> needs spend → tool_call: query_redshift {query_type: "vendor_spend_summary", filters: {vendor_ids: ["vendor_walker"], fiscal_periods: ["2024-Q4"]}}
  -> Subsystem C returns total_approved_amount: 130000
  -> synthesize answer

Supervisor returns:
  "Walker & Associates billed $130,000 (approved) in 2024-Q4 across the Acme v. Beta litigation."
```

---

## 2. Architectural Decisions (Locked)

| # | Decision | Choice | Notes |
|---|---|---|---|
| 1 | LLM provider | OpenAI API direct (`openai` SDK), model `gpt-5.2` (`chat.completions` endpoint) | AWS / Azure proxy via `base_url` deferred. `gpt-5.2` knowledge cutoff Aug 31 2025; 400k context, 128k max output. |
| 2 | Reasoning effort | `reasoning_effort=none` by default (treats `gpt-5.2` as a non-reasoning chat model). Configurable via `LINA_SUPERVISOR_REASONING_EFFORT` to `low`/`medium`/`high`/`xhigh` for harder multi-hop questions. Only sent to API when not `none` for forward compatibility with non-reasoning families. | Higher levels improve multi-hop tool routing at higher latency + cost |
| 3 | Token cap parameter | `max_completion_tokens` (newer canonical name; works for both reasoning and non-reasoning families) | `max_tokens` is deprecated for the `gpt-5.x` family |
| 4 | Orchestration framework | LangGraph 0.2+ | Python-native supervisor pattern; integrates with OpenAI SDK |
| 5 | Worker invocation | OpenAI function tool calls; one tool per worker template surface | LLM never sees raw SQL or DSL |
| 6 | Streaming | Yes — token streaming for synthesis + structured events for routing | Better CLI UX |
| 7 | Conversation state | In-memory `SessionStore` keyed by `request_id`; pluggable backend interface for future durability | |
| 8 | Routing | LLM-driven (no separate semantic router) | Deterministic *contracts*, not deterministic routing |
| 9 | Synthesis | Single OpenAI pass receiving worker `ResultPacket`s as `tool` role messages | Standard tool-use loop |
| 10 | Deliverable | Library + `lina-chat` CLI | Service deferred |
| 11 | Test strategy | Mock-based unit + VCR-replayed integration | Cost discipline |
| 12 | Cost guardrails | Token budget per call + `max_worker_calls=8` per user turn + `reasoning_effort=none` default | Prevents loops and stops reasoning-token blowup |

---

## 3. Repository Layout

```text
src/lina_supervisor/
├── __init__.py
├── config.py                # SupervisorConfig (model, max_tokens, max_worker_calls, ...)
├── tools.py                 # Tool definitions exposed to OpenAI (one per worker template family)
├── workers.py               # WorkerHub: holds RedshiftWorker, UserSearchWorker, VendorSearchWorker; dispatches tool calls
├── session.py               # SessionStore + Session models (multi-turn state)
├── graph.py                 # LangGraph state machine (nodes: route → execute_tools → synthesize → respond)
├── synthesizer.py           # Final-pass prompt + streaming response handling
├── packet.py                # SupervisorResponse (normalized output across turns)
├── caller_resolver.py       # Resolves user_id → CallerContext (calls Subsystem A internally)
└── cli.py                   # `lina-chat` Click app

tests/unit/lina_supervisor/
├── test_tools.py
├── test_workers_dispatch.py
├── test_session.py
├── test_graph_routing.py    # mocked OpenAI responses
├── test_synthesizer.py
├── test_caller_resolver.py
└── test_cli.py

tests/integration/lina_supervisor/
├── conftest.py              # VCR setup; OPENAI_API_KEY required for record mode
├── test_smoke_simple_query.py
├── test_smoke_multi_step.py
└── cassettes/               # VCR YAML recordings
```

### 3.1 New dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # existing
    "openai>=1.50",
    "langgraph>=0.2",
    "langchain-core>=0.3",          # for LangGraph types
]

[project.optional-dependencies]
dev = [
    # existing
    "vcrpy>=6.0",
    "pytest-vcr>=1.0",
]

[project.scripts]
# existing
lina-chat = "lina_supervisor.cli:main"
```

---

## 4. Tool Schema (LLM ↔ Worker Contract)

OpenAI sees tools defined as JSON-schema function specs. We expose **3 tools** corresponding to the three worker subsystems. The LLM picks which tool, supplies a typed `query_type` + `params` matching the worker's existing template registry, and receives a `ResultPacket` back.

### 4.1 Tool: `query_redshift`

```json
{
  "type": "function",
  "function": {
    "name": "query_redshift",
    "description": "Run a typed query against the legal_matter_spend Redshift store. Use for matter, vendor, timekeeper spend analytics; invoice or budget data; rate analysis. Specify a `query_type` from the catalog and structured `params`.",
    "parameters": {
      "type": "object",
      "properties": {
        "query_type": {
          "type": "string",
          "enum": ["matter_lookup", "matter_spend_summary", "vendor_spend_summary", "timekeeper_rate_analysis", "invoice_search", "line_item_detail"]
        },
        "params": {"type": "object", "description": "Per-query_type parameter object; see template-specific schemas in the system prompt."}
      },
      "required": ["query_type", "params"]
    }
  }
}
```

### 4.2 Tool: `search_users`

```json
{
  "type": "function",
  "function": {
    "name": "search_users",
    "description": "Search corporate user profiles. Use for finding internal users by name, role, department, or to walk reporting chains.",
    "parameters": {
      "type": "object",
      "properties": {
        "query_type": {"type": "string", "enum": ["user_lookup", "user_search", "manager_chain", "people_filter"]},
        "params": {"type": "object"}
      },
      "required": ["query_type", "params"]
    }
  }
}
```

### 4.3 Tool: `search_vendors`

```json
{
  "type": "function",
  "function": {
    "name": "search_vendors",
    "description": "Search outside counsel lawyer profiles. Use for finding vendor lawyers by name, vendor, practice area, jurisdiction, or hourly-rate band.",
    "parameters": {
      "type": "object",
      "properties": {
        "query_type": {"type": "string", "enum": ["timekeeper_lookup", "lawyer_search", "outside_counsel_filter", "practice_area_match"]},
        "params": {"type": "object"}
      },
      "required": ["query_type", "params"]
    }
  }
}
```

### 4.4 Per-template parameter schemas

The supervisor's system prompt includes a condensed catalog of each `query_type`'s `params` schema, generated at startup by walking each subsystem's `TEMPLATE_REGISTRY` and calling `template.Params.model_json_schema()`. This is large but cacheable; included verbatim in the system prompt so the LLM doesn't have to be reminded mid-conversation.

---

## 5. Graph Topology (LangGraph)

```text
┌────────────────────┐
│ user_message_in    │
│ (turn N starts)    │
└─────────┬──────────┘
          ▼
    ┌─────────────┐
    │ route_node  │ ← LLM decides: tool calls vs final answer
    └─────┬───────┘
          │
   ┌──────┴───────────┐
   │                  │
   ▼                  ▼
┌──────────┐   ┌────────────┐
│ execute_ │   │ synthesize │
│ tools    │ → │ _node      │  (after up to max_worker_calls iterations)
└────┬─────┘   └──────┬─────┘
     │                │
     └────► loop ─────┘
          (back to route_node)
                       │
                       ▼
                ┌─────────────┐
                │ respond_node│
                └─────────────┘
```

**Node responsibilities:**

- `route_node`: sends current message thread + tool definitions to OpenAI. Receives either:
  - `tool_calls` on the assistant message → push to execute_tools_node
  - text-only response (no tools) → push to respond_node (synthesizer fallback)
- `execute_tools_node`: for each tool_call, calls the matching worker's `run()` with caller context, gets `ResultPacket`, appends a `tool` role message keyed by `tool_call_id`. Increments `worker_call_count`. If count ≥ `max_worker_calls`, force-skip to `synthesize_node`.
- `synthesize_node`: identical to route_node but with `tool_choice="auto"` and an explicit "you have all the data; produce the final answer now" message appended; streams via `stream=True`.
- `respond_node`: emits final `SupervisorResponse`.

State carried between nodes: a list of provider-shaped chat messages plus auxiliary fields:
- `caller: CallerContext`
- `session_id: str`
- `worker_call_count: int`
- `worker_packets: list[ResultPacket]` (for debugging/audit; final response includes them as references)

---

## 6. Worker Hub

`WorkerHub` is a thin façade that:
1. Owns instantiated `RedshiftWorker`, `UserSearchWorker`, `VendorSearchWorker`.
2. Routes OpenAI function tool calls to the right worker:
   - `query_redshift` → `RedshiftWorker.run(query_type, params, caller)`
   - `search_users` → `UserSearchWorker.run(query_type, params, caller)`
   - `search_vendors` → `VendorSearchWorker.run(query_type, params, caller)`
3. Returns normalized `tool` message content: a string-encoded JSON of the packet's `model_dump(by_alias=True)`, plus an `is_error` flag if the packet is an `ErrorPacket`.
4. Logs every call with `request_id` + worker_call_count for audit.

The hub doesn't transform packets — the LLM reads the JSON directly.

---

## 7. Caller Resolver

The CLI takes a `--user-id` flag. The supervisor needs a full `CallerContext` (with `roles`, `permission_tags`). To get it, on session start the supervisor calls Subsystem A's `user_lookup` template internally:

1. CLI gets `--user-id user_jane_smith`.
2. Supervisor's `caller_resolver` calls `UserSearchWorker.run(query_type="user_lookup", params={"user_id": "user_jane_smith"}, caller=BOOTSTRAP_CALLER)` where `BOOTSTRAP_CALLER` is a built-in identity with role `caller_resolver`.
3. Subsystem A returns the user's profile; resolver builds a `CallerContext(user_id=..., roles=frozenset(profile["roles"]), permission_tags=frozenset(profile["permission_tags"]), request_id=session_id)`.
4. That context is passed to all subsequent worker calls in the session.

If the user is not found, the supervisor returns an error response and refuses to start the session.

A few templates have role gates that exclude `caller_resolver` (e.g., `outside_counsel_filter` requires `legal_ops`/`finance`/`procurement`). The bootstrap caller is intentionally limited — it's only allowed to call `user_lookup`.

---

## 8. Session Storage

```python
@dataclass
class Session:
    session_id: str
    user_id: str
    caller: CallerContext
    messages: list[BaseMessage]    # LangGraph message list
    created_at: datetime
    last_activity: datetime
    worker_call_count_total: int


class SessionStore(Protocol):
    def get_or_create(self, session_id: str, user_id: str) -> Session: ...
    def append_message(self, session_id: str, message: BaseMessage) -> None: ...
    def update_caller(self, session_id: str, caller: CallerContext) -> None: ...


class InMemorySessionStore:
    """Default v1 backend. Pluggable by subclassing the protocol."""
```

Future backends (DynamoDB, Redis) implement the same Protocol.

---

## 9. CLI

`lina-chat`:

| Command | Purpose |
|---|---|
| `lina-chat ask --user-id <id> --query "..."` | One-shot mode: single ask, response, exit. Stateless. |
| `lina-chat repl --user-id <id> [--session-id <sid>]` | Interactive REPL. Maintains `Session` in memory. Auto-creates session_id if absent. |
| `lina-chat sessions list \| show <sid>` | (in-memory only — useful in REPL mode for current process) |

Both modes stream output by default. The REPL prints worker tool calls as inline status lines (`> calling query_redshift(matter_spend_summary)...`) before the final synthesized text streams.

`--no-stream` flag disables streaming and produces a single JSON `SupervisorResponse` at end.

`--max-worker-calls` overrides the default 8.

`--model` overrides the default `gpt-5.2`. `--reasoning-effort` (or `LINA_SUPERVISOR_REASONING_EFFORT`) overrides the default `none`.

Configuration:
- `OPENAI_API_KEY` — required.
- `LINA_REDSHIFT_DSN` — required for query_redshift.
- `LINA_OPENSEARCH_HOST` + auth — required for search_users / search_vendors.

If any backend is unavailable, the supervisor still starts but the corresponding tool definition is omitted from the system prompt (the LLM can't choose a tool that isn't defined). README documents this.

---

## 10. SupervisorResponse Shape

Mirrors the `ResultPacket` family but for synthesis output:

```python
class SupervisorResponse(BaseModel):
    source_engine: Literal["supervisor"] = "supervisor"
    session_id: str
    request_id: str
    user_id: str
    answer_text: str                     # final synthesized answer
    worker_packets: list[dict[str, Any]] # echoes of each worker tool result, in order
    worker_call_count: int
    truncated: bool                      # True if max_worker_calls was hit
    model: str                           # gpt-5.2 or override
    duration_ms: int
    sql_trace_id: str                    # ULID; same field name as ResultPacket for audit consistency
```

Streaming mode emits SSE-style events: `{"type": "tool_call", "name": "...", "input": {...}}`, `{"type": "tool_result", "result_type": "..."}`, `{"type": "answer_token", "text": "..."}`, terminating with the full `SupervisorResponse` as `{"type": "complete", "response": {...}}`.

---

## 11. Cost & Safety Guardrails

| Guardrail | Mechanism |
|---|---|
| Max worker calls per user turn | `max_worker_calls=8` config; force-stop and synthesize from current data |
| LLM token budget per request | `max_tokens=2048` for route, `max_tokens=4096` for synthesize |
| Worker timeout propagation | If a worker raises `QueryTimeoutError`, the resulting `ErrorPacket` becomes a `tool_result` and the LLM can choose to retry with narrower params or proceed |
| Caller authorization | Every worker call uses the resolved CallerContext; auth failures show as `ErrorPacket(AuthorizationError)` and the LLM can adapt |
| Prompt-injection resistance | Tool definitions hard-coded; user message body is wrapped in `<user_message>` tags; final answer must include a "Sources:" section listing worker packets used |
| API key handling | `OPENAI_API_KEY` from env only; never logged |

---

## 12. Out of Scope

1. Durable session storage (DynamoDB/Redis adapter).
2. FastAPI HTTP service (the CLI is the only deliverable).
3. AWS Bedrock or Azure OpenAI backend (would set `base_url` on the SDK).
4. Multi-user concurrent sessions in a single process (in-memory store is single-tenant per process).
5. Long-term conversation memory across sessions / personalization.
6. RAG over case documents or contracts (only structured worker calls).
7. UI (web/mobile chat surface).
8. Cost telemetry export (per-request cost is logged; no Prometheus/CloudWatch).
9. A/B model comparison or model fallback (one model per session).
10. Fine-tuning or custom OpenAI model variants.

---

## 13. Success Criteria

- `lina-chat ask --user-id user_jane_smith --query "How much did Walker bill on the Acme litigation last quarter?"` produces a sensible answer that cites a real `vendor_spend_summary` packet from Subsystem C.
- All 6 query templates from C, 4 from A, 4 from B are reachable via the LLM (tool definitions enumerate all `query_type` values).
- Multi-turn REPL maintains context across at least 5 turns without losing track of the caller's identity.
- Mock-based unit suite ≥ 30 tests, all passing in under 5 seconds.
- VCR-replayed integration suite passes without an OpenAI API key (using committed cassettes).
- Caller resolution gracefully fails with a clear error when `user_id` is unknown to Subsystem A.
- `mypy --strict` and `ruff check` clean across all four subsystems.
- Total project test count ≥ 280 (252 baseline + ~30 new).
- Tag `v1.0.0` on the integrated milestone.
