"""Unit tests for UserSearchWorker.

Uses an in-memory fake client to validate worker control flow without Docker.
"""

from __future__ import annotations

from typing import Any

import pytest

from lina_core.caller import CallerContext
from lina_users.packet import ErrorPacket, ResultPacket
from lina_users.worker import UserSearchWorker


class _FakeClient:
    def __init__(
        self, hits: list[dict[str, Any]] | None = None, *, exc: Exception | None = None
    ) -> None:
        self._hits = hits or []
        self._exc = exc
        self.calls: list[dict[str, Any]] = []

    def search(self, *, index: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body, "kwargs": kwargs})
        if self._exc is not None:
            raise self._exc
        return {"hits": {"hits": self._hits}}


def _caller(*roles: str) -> CallerContext:
    return CallerContext(
        user_id="caller_test",
        roles=frozenset(roles),
        request_id="req_test",
    )


@pytest.mark.unit
def test_run_unknown_template_returns_error_packet() -> None:
    worker = UserSearchWorker(client=_FakeClient())
    result = worker.run(
        query_type="not_a_real_template",
        params={},
        caller=_caller("legal_ops"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "UnknownTemplateError"


@pytest.mark.unit
def test_run_authorization_failure_returns_error_packet() -> None:
    worker = UserSearchWorker(client=_FakeClient())
    result = worker.run(
        query_type="manager_chain",
        params={"start_user_id": "user_jane_smith"},
        caller=_caller("billing_clerk"),  # not legal_ops or hr_ops
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "AuthorizationError"


@pytest.mark.unit
def test_run_invalid_params_returns_error_packet() -> None:
    worker = UserSearchWorker(client=_FakeClient())
    result = worker.run(
        query_type="user_lookup",
        params={},  # zero of user_id/email/employee_id provided
        caller=_caller("any_role"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "InvalidParametersError"


@pytest.mark.unit
def test_run_user_lookup_returns_result_packet_shaped() -> None:
    fake = _FakeClient(
        hits=[
            {
                "_source": {
                    "user_id": "user_jane_smith",
                    "display_name": "Jane Smith",
                    "department": "Legal",
                    "internal_secret": "redacted",
                }
            }
        ]
    )
    worker = UserSearchWorker(client=fake)
    result = worker.run(
        query_type="user_lookup",
        params={"user_id": "user_jane_smith"},
        caller=_caller("any_role"),
    )
    assert isinstance(result, ResultPacket)
    assert result.row_count == 1
    assert result.metrics == [
        {"user_id": "user_jane_smith", "display_name": "Jane Smith", "department": "Legal"}
    ]
    assert fake.calls[0]["index"] == "corp_user_profiles_v1"


@pytest.mark.unit
def test_run_maps_connection_error_to_backend_connection_error() -> None:
    from opensearchpy.exceptions import ConnectionError as OSConnectionError

    fake = _FakeClient(exc=OSConnectionError(599, "conn refused", {}))
    worker = UserSearchWorker(client=fake)
    result = worker.run(
        query_type="user_lookup",
        params={"user_id": "u1"},
        caller=_caller("any_role"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "BackendConnectionError"


@pytest.mark.unit
def test_run_maps_timeout_request_error_to_query_timeout_error() -> None:
    from opensearchpy.exceptions import RequestError

    fake = _FakeClient(exc=RequestError(408, "request timed_out", {"error": "timed_out"}))
    worker = UserSearchWorker(client=fake)
    result = worker.run(
        query_type="user_lookup",
        params={"user_id": "u1"},
        caller=_caller("any_role"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "QueryTimeoutError"


@pytest.mark.unit
def test_run_manager_chain_dispatches_to_walk_chain() -> None:
    """When query_type == manager_chain, worker iterates via walk_chain."""

    class _ChainClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def search(self, *, index: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            self.calls.append({"index": index, "body": body})
            query = body.get("query", {})
            if "term" in query and query["term"].get("user_id") == "user_alex_lee":
                return {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "user_id": "user_alex_lee",
                                    "display_name": "Alex Lee",
                                    "manager_user_id": "user_sam_rodriguez",
                                }
                            }
                        ]
                    }
                }
            if "term" in query and query["term"].get("user_id") == "user_sam_rodriguez":
                return {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "user_id": "user_sam_rodriguez",
                                    "display_name": "Sam Rodriguez",
                                    "manager_user_id": None,
                                }
                            }
                        ]
                    }
                }
            return {"hits": {"hits": []}}

    fake = _ChainClient()
    worker = UserSearchWorker(client=fake)
    result = worker.run(
        query_type="manager_chain",
        params={"start_user_id": "user_alex_lee", "direction": "up", "max_depth": 5},
        caller=_caller("legal_ops"),
    )
    assert isinstance(result, ResultPacket)
    ids = [m["user_id"] for m in result.metrics]
    assert ids == ["user_alex_lee", "user_sam_rodriguez"]
