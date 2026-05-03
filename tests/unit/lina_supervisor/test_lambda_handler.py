"""Unit tests for the AWS Lambda handler module.

The handler is plain Python that re-uses ``WorkerHub`` + ``build_graph``. Tests
mock the AWS surface (Secrets Manager) and inject mock factory functions for
the worker hub and the LLM client. Real AWS calls never happen here.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_core.caller import CallerContext
from lina_supervisor import lambda_handler


@pytest.fixture(autouse=True)
def _reset_handler_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the module-level OpenAI key cache between tests."""
    lambda_handler._OPENAI_KEY_CACHE.clear()
    monkeypatch.setenv("LINA_OPENAI_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:0:secret:openai")
    monkeypatch.setenv(
        "LINA_REDSHIFT_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:0:secret:redshift"
    )
    monkeypatch.setenv(
        "LINA_REDSHIFT_HOST", "lina-sandbox-wg.0.us-east-1.redshift-serverless.amazonaws.com"
    )
    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "https://search-lina.us-east-1.es.amazonaws.com")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def _stub_secrets_client(*, openai_key: str = "sk-test") -> MagicMock:
    secrets = MagicMock()
    secrets.get_secret_value.return_value = {
        "SecretString": json.dumps({"api_key": openai_key}),
    }
    return secrets


def _stub_workers() -> tuple[MagicMock, MagicMock, MagicMock]:
    return MagicMock(), MagicMock(), MagicMock()


def _build_workers_factory(
    *,
    redshift_worker: MagicMock,
    users_worker: MagicMock,
    vendors_worker: MagicMock,
    caller: CallerContext,
) -> Any:
    def _factory(
        *,
        config: Any,
        os_client: Any,
        secrets_client: Any,
        request_id: str,
        user_id: str,
    ) -> Any:
        from lina_supervisor.workers import WorkerHub

        hub = WorkerHub(
            redshift_worker=redshift_worker,
            users_worker=users_worker,
            vendors_worker=vendors_worker,
        )
        return hub, caller

    return _factory


def _stub_llm_client_factory(client: MagicMock) -> Any:
    def _factory(*, config: Any) -> Any:
        return client

    return _factory


def _text_response(text: str) -> Any:
    message = MagicMock()
    message.content = text
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]
    return response


def _llm_with_text(text: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _text_response(text)
    return client


def _caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane_smith",
        roles=frozenset({"reader"}),
        request_id="req-1",
    )


@pytest.mark.unit
def test_handler_rejects_missing_user_id_with_400(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = _stub_secrets_client()
    monkeypatch.setattr(lambda_handler, "_secrets_client", secrets)
    rs, users, vendors = _stub_workers()
    response = lambda_handler.handler(
        {"body": json.dumps({"query": "hi"})},
        None,
        _build_workers=_build_workers_factory(
            redshift_worker=rs, users_worker=users, vendors_worker=vendors, caller=_caller()
        ),
        _build_llm=_stub_llm_client_factory(_llm_with_text("hi")),
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "user_id" in body["error"]


@pytest.mark.unit
def test_handler_rejects_missing_query_with_400(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = _stub_secrets_client()
    monkeypatch.setattr(lambda_handler, "_secrets_client", secrets)
    rs, users, vendors = _stub_workers()
    response = lambda_handler.handler(
        {"body": json.dumps({"user_id": "user_jane_smith"})},
        None,
        _build_workers=_build_workers_factory(
            redshift_worker=rs, users_worker=users, vendors_worker=vendors, caller=_caller()
        ),
        _build_llm=_stub_llm_client_factory(_llm_with_text("hi")),
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "query" in body["error"]


@pytest.mark.unit
def test_handler_returns_200_with_answer_for_valid_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets = _stub_secrets_client()
    monkeypatch.setattr(lambda_handler, "_secrets_client", secrets)
    rs, users, vendors = _stub_workers()
    response = lambda_handler.handler(
        {
            "body": json.dumps(
                {
                    "user_id": "user_jane_smith",
                    "query": "How many open litigation matters do we have?",
                }
            ),
            "requestContext": {"requestId": "rid-123"},
        },
        None,
        _build_workers=_build_workers_factory(
            redshift_worker=rs, users_worker=users, vendors_worker=vendors, caller=_caller()
        ),
        _build_llm=_stub_llm_client_factory(
            _llm_with_text("There are 14 open litigation matters.")
        ),
    )
    assert response["statusCode"] == 200
    assert response["headers"]["content-type"] == "application/json"
    body = json.loads(response["body"])
    assert body["answer_text"] == "There are 14 open litigation matters."


@pytest.mark.unit
def test_handler_caches_openai_key_across_warm_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets = _stub_secrets_client()
    monkeypatch.setattr(lambda_handler, "_secrets_client", secrets)
    rs, users, vendors = _stub_workers()
    builder = _build_workers_factory(
        redshift_worker=rs, users_worker=users, vendors_worker=vendors, caller=_caller()
    )
    llm = _stub_llm_client_factory(_llm_with_text("hello"))
    event = {
        "body": json.dumps({"user_id": "user_jane_smith", "query": "hi"}),
        "requestContext": {"requestId": "rid-1"},
    }
    lambda_handler.handler(event, None, _build_workers=builder, _build_llm=llm)
    lambda_handler.handler(event, None, _build_workers=builder, _build_llm=llm)
    assert secrets.get_secret_value.call_count == 1


@pytest.mark.unit
def test_handler_response_includes_worker_packets_and_call_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets = _stub_secrets_client()
    monkeypatch.setattr(lambda_handler, "_secrets_client", secrets)
    rs, users, vendors = _stub_workers()
    response = lambda_handler.handler(
        {
            "body": json.dumps({"user_id": "user_jane_smith", "query": "hi"}),
            "requestContext": {"requestId": "rid-2"},
        },
        None,
        _build_workers=_build_workers_factory(
            redshift_worker=rs, users_worker=users, vendors_worker=vendors, caller=_caller()
        ),
        _build_llm=_stub_llm_client_factory(_llm_with_text("answer")),
    )
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "worker_packets" in body
    assert "worker_call_count" in body
    assert "truncated" in body
    assert body["worker_call_count"] == 0
    assert body["worker_packets"] == []
    assert body["truncated"] is False


@pytest.mark.unit
def test_handler_translates_handler_exception_to_500_with_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets = _stub_secrets_client()
    monkeypatch.setattr(lambda_handler, "_secrets_client", secrets)

    def _exploding_factory(**_kwargs: Any) -> Any:
        raise RuntimeError("boom")

    response = lambda_handler.handler(
        {
            "body": json.dumps({"user_id": "user_jane_smith", "query": "hi"}),
            "requestContext": {"requestId": "rid-3"},
        },
        None,
        _build_workers=_exploding_factory,
        _build_llm=_stub_llm_client_factory(_llm_with_text("answer")),
    )
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "boom" in body["error"]
