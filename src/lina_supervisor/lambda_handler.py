"""AWS Lambda handler for ``lina-chat ask`` over the v1.1 sandbox stack.

This module is plain Python so it can be unit-tested without spinning up
Lambda. The deployment shim at ``deploy/lambda/lambda_handler.py`` imports
``handler`` from here and exposes it as the container's entry point.

Module-level globals cache the OpenAI key (and, in production, the worker
hub) across warm invocations so we only pay the Secrets Manager round-trip
on cold starts.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from lina_core.caller import CallerContext
from lina_core.opensearch import OpenSearchConfig, open_client
from lina_supervisor.caller_resolver import CallerResolver
from lina_supervisor.config import SupervisorConfig
from lina_supervisor.graph import build_graph
from lina_supervisor.session import InMemorySessionStore
from lina_supervisor.system_prompt import build_initial_messages
from lina_supervisor.workers import WorkerHub

_LOG = logging.getLogger(__name__)


def _make_secrets_client() -> Any:
    """Construct the boto3 Secrets Manager client lazily.

    boto3 is only available inside the Lambda container; at unit-test time
    the tests monkey-patch ``_secrets_client`` directly, so the real client
    is never built locally.
    """
    try:
        import boto3
    except ImportError:  # pragma: no cover - exercised only outside Lambda
        return None
    return boto3.client("secretsmanager")


_secrets_client: Any = _make_secrets_client()
_OPENAI_KEY_CACHE: dict[str, str] = {}


def _get_openai_key() -> str:
    """Return the cached OpenAI API key, loading once from Secrets Manager."""
    if "value" not in _OPENAI_KEY_CACHE:
        arn = os.environ["LINA_OPENAI_SECRET_ARN"]
        secret = _secrets_client.get_secret_value(SecretId=arn)
        _OPENAI_KEY_CACHE["value"] = json.loads(secret["SecretString"])["api_key"]
    return _OPENAI_KEY_CACHE["value"]


def _redshift_connect_kwargs() -> dict[str, Any]:
    """Read the Redshift admin secret + env to build keyword args.

    Keyword args avoid the silent breakage f-string DSNs hit when the
    password contains URL-sensitive characters (``@``, ``/``, ``:``, ``#``,
    ``%``) — psycopg2 would misparse the host or refuse the connection.
    """
    arn = os.environ["LINA_REDSHIFT_SECRET_ARN"]
    secret = _secrets_client.get_secret_value(SecretId=arn)
    payload = json.loads(secret["SecretString"])
    return {
        "host": os.environ["LINA_REDSHIFT_HOST"],
        "port": int(payload.get("port", 5439)),
        "dbname": payload.get("dbname", "dev"),
        "user": payload.get("username", "lina_admin"),
        "password": payload["password"],
    }


def _build_llm_default(*, config: SupervisorConfig) -> Any:
    """Default OpenAI client builder. Substitutable in unit tests.

    Applies ``config.request_timeout_seconds`` so a hung upstream call
    doesn't blow past API Gateway's 30-second integration timeout while
    Lambda keeps burning compute and the client sees a generic gateway
    timeout instead of our error envelope.
    """
    from openai import OpenAI

    return OpenAI(
        api_key=config.openai_api_key,
        timeout=config.request_timeout_seconds,
    )


def _build_workers_default(
    *,
    config: SupervisorConfig,
    os_client: Any,
    secrets_client: Any,
    request_id: str,
    user_id: str,
) -> tuple[WorkerHub, CallerContext]:
    """Default worker hub builder. Substitutable in unit tests.

    Constructs the three real workers, resolves the caller via Subsystem A,
    and returns the assembled hub plus the resolved caller context.
    """
    _ = config  # config kept in signature for future per-config tuning
    _ = secrets_client  # passed through for potential per-call overrides
    from lina_redshift.connection import connect_with_kwargs
    from lina_redshift.worker import RedshiftWorker
    from lina_users.worker import UserSearchWorker
    from lina_vendors.worker import VendorSearchWorker

    os_config = OpenSearchConfig(
        host=os.environ["LINA_OPENSEARCH_HOST"],
        auth_mode="aws_sigv4",
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
    )
    rs_connection = connect_with_kwargs(
        connect_timeout=int(os.environ.get("LINA_REDSHIFT_CONNECT_TIMEOUT", "5")),
        statement_timeout_ms=int(os.environ.get("LINA_STATEMENT_TIMEOUT_MS", "25000")),
        read_only=True,
        **_redshift_connect_kwargs(),
    )
    redshift_worker = RedshiftWorker(connection=rs_connection)
    users_worker = UserSearchWorker(client=os_client, config=os_config)
    vendors_worker = VendorSearchWorker(client=os_client, config=os_config)
    hub = WorkerHub(
        redshift_worker=redshift_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
    )
    resolver = CallerResolver(users_worker=users_worker)
    caller = resolver.resolve(user_id=user_id, request_id=request_id)
    return hub, caller


def _error_response(
    status: int,
    message: str,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": message}
    if request_id:
        body["request_id"] = request_id
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def handler(
    event: dict[str, Any],
    _context: Any,
    *,
    _build_workers: Any = _build_workers_default,
    _build_llm: Any = _build_llm_default,
) -> dict[str, Any]:
    """API Gateway HTTP API → Lambda handler entry point.

    The factory parameters (``_build_workers``, ``_build_llm``) are private
    seams that let unit tests substitute mocks without monkey-patching boto3.
    """
    request_id = (event.get("requestContext") or {}).get("requestId") or "lambda-req"
    try:
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _error_response(400, "request body must be valid JSON", request_id=request_id)
        user_id = body.get("user_id", "")
        query = body.get("query", "")
        history = body.get("history") or []
        if not user_id:
            return _error_response(400, "user_id is required", request_id=request_id)
        if not query:
            return _error_response(400, "query is required", request_id=request_id)
        if not isinstance(history, list):
            return _error_response(
                400,
                "history must be a list of {role, content} entries",
                request_id=request_id,
            )

        config = SupervisorConfig(
            openai_api_key=_get_openai_key(),
            model=os.environ.get("LINA_SUPERVISOR_MODEL", "gpt-5.2"),
        )
        llm = _build_llm(config=config)

        os_config = OpenSearchConfig(
            host=os.environ.get("LINA_OPENSEARCH_HOST", ""),
            auth_mode="aws_sigv4",
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        )
        # The default builder ignores ``os_client`` for tests; production
        # path inside ``_build_workers_default`` recomputes via os_config.
        os_client: Any = None
        if os_config.host:
            try:
                os_client = open_client(os_config)
            except Exception:  # noqa: BLE001 - tests skip this branch
                os_client = None

        hub, caller = _build_workers(
            config=config,
            os_client=os_client,
            secrets_client=_secrets_client,
            request_id=request_id,
            user_id=user_id,
        )

        graph = build_graph(
            config=config,
            hub=hub,
            session_store=InMemorySessionStore(),
            llm_client=llm,
        )
        final = graph.invoke(
            {
                "messages": build_initial_messages(query, history=history),
                "caller": caller,
                "worker_call_count": 0,
                "worker_packets": [],
                "truncated": False,
                "answer_text": "",
            }
        )
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(
                {
                    "answer_text": final["answer_text"],
                    "worker_call_count": final["worker_call_count"],
                    "worker_packets": final["worker_packets"],
                    "truncated": final["truncated"],
                },
                default=str,
            ),
        }
    except Exception:  # noqa: BLE001 - handler-level catchall by design
        # Stack trace and exception details land in CloudWatch via .exception().
        # Client gets a generic message + request_id so they can ask us to
        # cross-reference logs without us leaking internal exception strings
        # (DSNs, secret names, SQL, stack frames).
        _LOG.exception("lambda handler failed", extra={"request_id": request_id})
        return _error_response(500, "Internal server error", request_id=request_id)


__all__ = ["handler"]
