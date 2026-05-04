"""`lina-chat` CLI — chat with the supervisor over Subsystems A, B, C.

Two modes:

  - ``lina-chat ask``  — one-shot question, response, exit.
  - ``lina-chat repl`` — interactive REPL maintaining a Session in memory.

Both modes stream by default. ``--no-stream`` emits a single JSON
``SupervisorResponse`` at the end. Backends are detected lazily: a worker is
only constructed if its environment variables are set; otherwise the
corresponding tool definition is omitted.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import click
from ulid import ULID

from lina_core.logging_config import configure_logging
from lina_supervisor.caller_resolver import CallerResolver, UserNotFoundError
from lina_supervisor.config import SupervisorConfig, resolve_config
from lina_supervisor.graph import SupervisorState, build_graph
from lina_supervisor.packet import SupervisorResponse
from lina_supervisor.session import InMemorySessionStore
from lina_supervisor.workers import WorkerHub

# ---------------------------------------------------------------------------
# Backend factories (overridable by tests via monkeypatch)
# ---------------------------------------------------------------------------


def _build_openai_client(config: SupervisorConfig) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=config.openai_api_key)


def _build_redshift_worker() -> Any:
    if not os.environ.get("LINA_REDSHIFT_DSN"):
        return None
    import psycopg2

    from lina_redshift.connection import resolve_config as redshift_config
    from lina_redshift.worker import RedshiftWorker

    cfg = redshift_config()
    conn = psycopg2.connect(cfg.dsn)
    return RedshiftWorker(connection=conn)


def _build_users_worker() -> Any:
    if not os.environ.get("LINA_OPENSEARCH_HOST"):
        return None
    from lina_users.connection import open_client
    from lina_users.connection import resolve_config as users_config
    from lina_users.worker import UserSearchWorker

    cfg = users_config()
    return UserSearchWorker(client=open_client(cfg), config=cfg)


def _build_vendors_worker() -> Any:
    if not os.environ.get("LINA_OPENSEARCH_HOST"):
        return None
    from lina_vendors.connection import open_client
    from lina_vendors.connection import resolve_config as vendors_config
    from lina_vendors.worker import VendorSearchWorker

    cfg = vendors_config()
    return VendorSearchWorker(client=open_client(cfg), config=cfg)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def _build_supervisor(
    *,
    config: SupervisorConfig,
    redshift_worker: Any,
    users_worker: Any,
    vendors_worker: Any,
    llm_client: Any,
) -> tuple[Any, WorkerHub, InMemorySessionStore]:
    hub = WorkerHub(
        redshift_worker=redshift_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
    )
    session_store = InMemorySessionStore()
    graph = build_graph(
        config=config,
        hub=hub,
        session_store=session_store,
        llm_client=llm_client,
    )
    return graph, hub, session_store


def _connected_backends(
    *,
    redshift_worker: Any,
    users_worker: Any,
    vendors_worker: Any,
) -> list[str]:
    out: list[str] = []
    if redshift_worker is not None:
        out.append("redshift")
    if users_worker is not None:
        out.append("users")
    if vendors_worker is not None:
        out.append("vendors")
    return out


def _emit_response(
    *,
    session_id: str,
    request_id: str,
    user_id: str,
    final_state: SupervisorState,
    config: SupervisorConfig,
    started_at: float,
    sql_trace_id: str,
) -> SupervisorResponse:
    return SupervisorResponse(
        session_id=session_id,
        request_id=request_id,
        user_id=user_id,
        answer_text=final_state["answer_text"],
        worker_packets=final_state["worker_packets"],
        worker_call_count=final_state["worker_call_count"],
        truncated=final_state["truncated"],
        model=config.model,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        sql_trace_id=sql_trace_id,
    )


def _override_config(
    base: SupervisorConfig,
    *,
    max_worker_calls: int | None,
    model: str | None,
) -> SupervisorConfig:
    return SupervisorConfig(
        openai_api_key=base.openai_api_key,
        model=model or base.model,
        max_worker_calls=max_worker_calls or base.max_worker_calls,
        route_max_tokens=base.route_max_tokens,
        synthesize_max_tokens=base.synthesize_max_tokens,
        request_timeout_seconds=base.request_timeout_seconds,
    )


def _run_turn(
    *,
    graph: Any,
    config: SupervisorConfig,
    user_id: str,
    session_id: str,
    query: str,
    caller: Any,
    no_stream: bool,
) -> SupervisorResponse:
    request_id = f"req_{ULID()}"
    started_at = time.perf_counter()
    from lina_supervisor.system_prompt import build_initial_messages

    initial_state: SupervisorState = {
        "messages": build_initial_messages(query),
        "caller": caller,
        "worker_call_count": 0,
        "worker_packets": [],
        "truncated": False,
        "answer_text": "",
    }
    final_state = graph.invoke(initial_state)
    response = _emit_response(
        session_id=session_id,
        request_id=request_id,
        user_id=user_id,
        final_state=final_state,
        config=config,
        started_at=started_at,
        sql_trace_id=request_id,
    )
    if not no_stream:
        click.echo(response.answer_text)
    return response


# ---------------------------------------------------------------------------
# Click commands
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """lina-chat — supervisor for the Subsystems A, B, C workers."""
    configure_logging()


@main.command("ask")
@click.option("--user-id", required=True, help="User who is asking.")
@click.option("--query", required=True, help="The question to ask.")
@click.option("--session-id", default=None, help="Session id (defaults to a new ULID).")
@click.option(
    "--no-stream",
    is_flag=True,
    default=False,
    help="Disable streaming and emit a single JSON SupervisorResponse.",
)
@click.option(
    "--max-worker-calls",
    type=int,
    default=None,
    help="Cap on worker calls per user turn (default 8).",
)
@click.option("--model", default=None, help="Override the OpenAI model.")
def ask_cmd(
    user_id: str,
    query: str,
    session_id: str | None,
    no_stream: bool,
    max_worker_calls: int | None,
    model: str | None,
) -> None:
    """One-shot mode: single ask, response, exit."""
    base_config = resolve_config()
    config = _override_config(base_config, max_worker_calls=max_worker_calls, model=model)

    redshift_worker = _build_redshift_worker()
    users_worker = _build_users_worker()
    vendors_worker = _build_vendors_worker()
    llm_client = _build_openai_client(config)

    backends = _connected_backends(
        redshift_worker=redshift_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
    )
    click.echo(
        f"connected backends: {','.join(backends) if backends else '(none)'} "
        f"| LLM: OpenAI {config.model}",
        err=True,
    )

    if users_worker is None:
        # Caller resolution requires Subsystem A. Fall back to a permissive
        # caller derived directly from the CLI input. This keeps `lina-chat`
        # usable when only Redshift is configured.
        from lina_core.caller import CallerContext

        session_id_resolved = session_id or f"sess_{ULID()}"
        caller = CallerContext(
            user_id=user_id,
            roles=frozenset({"reader"}),
            request_id=session_id_resolved,
        )
    else:
        resolver = CallerResolver(users_worker=users_worker)
        session_id_resolved = session_id or f"sess_{ULID()}"
        try:
            caller = resolver.resolve(user_id=user_id, request_id=session_id_resolved)
        except UserNotFoundError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(2)

    graph, _hub, _store = _build_supervisor(
        config=config,
        redshift_worker=redshift_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
        llm_client=llm_client,
    )

    response = _run_turn(
        graph=graph,
        config=config,
        user_id=user_id,
        session_id=session_id_resolved,
        query=query,
        caller=caller,
        no_stream=no_stream,
    )

    if no_stream:
        click.echo(response.model_dump_json(indent=2))


@main.command("repl")
@click.option("--user-id", required=True, help="User who is asking.")
@click.option(
    "--session-id",
    default=None,
    help="Session id (defaults to a new ULID).",
)
def repl_cmd(user_id: str, session_id: str | None) -> None:
    """Interactive REPL — multi-turn chat with the supervisor."""
    base_config = resolve_config()

    redshift_worker = _build_redshift_worker()
    users_worker = _build_users_worker()
    vendors_worker = _build_vendors_worker()
    llm_client = _build_openai_client(base_config)

    backends = _connected_backends(
        redshift_worker=redshift_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
    )
    click.echo(
        f"connected backends: {','.join(backends) if backends else '(none)'} "
        f"| LLM: OpenAI {base_config.model}",
        err=True,
    )

    session_id_resolved = session_id or f"sess_{ULID()}"

    if users_worker is None:
        from lina_core.caller import CallerContext

        caller = CallerContext(
            user_id=user_id,
            roles=frozenset({"reader"}),
            request_id=session_id_resolved,
        )
    else:
        resolver = CallerResolver(users_worker=users_worker)
        try:
            caller = resolver.resolve(user_id=user_id, request_id=session_id_resolved)
        except UserNotFoundError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(2)

    graph, _hub, _store = _build_supervisor(
        config=base_config,
        redshift_worker=redshift_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
        llm_client=llm_client,
    )

    click.echo(f"lina-chat repl — session {session_id_resolved}", err=True)
    click.echo("type 'exit' or Ctrl-D to quit", err=True)

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("", err=True)
            break
        if not line:
            continue
        if line.lower() in {"exit", "quit"}:
            break
        _run_turn(
            graph=graph,
            config=base_config,
            user_id=user_id,
            session_id=session_id_resolved,
            query=line,
            caller=caller,
            no_stream=False,
        )


if __name__ == "__main__":
    main()


__all__ = [
    "_build_openai_client",
    "_build_redshift_worker",
    "_build_supervisor",
    "_build_users_worker",
    "_build_vendors_worker",
    "main",
]
