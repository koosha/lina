"""Unit tests for WorkerHub.dispatch."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_core.caller import CallerContext
from lina_core.errors import AuthorizationError, InvalidParametersError
from lina_core.packet import ErrorPacket, ResultPacket
from lina_supervisor.workers import WorkerHub


def _caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane",
        roles=frozenset({"reader"}),
        request_id="req-1",
    )


def _ok_packet(*, source: str, query_type: str, value: int = 1) -> ResultPacket:
    return ResultPacket(
        source_engine=source,
        result_type=query_type,
        metrics=[{"value": value}],
        sql_trace_id="01J0000000000000000000000",
        row_count=1,
        truncated=False,
    )


def _err_packet(exc: Exception, *, source: str, query_type: str) -> ErrorPacket:
    return ErrorPacket.from_exception(
        exc,
        source_engine=source,
        schema_name="legal",
        sql_trace_id="01J0000000000000000000000",
        result_type=query_type,
    )


def _hub_with_mocks() -> tuple[WorkerHub, MagicMock, MagicMock, MagicMock]:
    redshift = MagicMock()
    users = MagicMock()
    vendors = MagicMock()
    hub = WorkerHub(redshift_worker=redshift, users_worker=users, vendors_worker=vendors)
    return hub, redshift, users, vendors


@pytest.mark.unit
def test_dispatch_query_redshift_routes_to_redshift_worker() -> None:
    hub, redshift, _users, _vendors = _hub_with_mocks()
    redshift.run.return_value = _ok_packet(source="redshift", query_type="matter_lookup")
    caller = _caller()
    result = hub.dispatch(
        tool_name="query_redshift",
        tool_input={"query_type": "matter_lookup", "params": {"matter_id": "m1"}},
        caller=caller,
    )
    redshift.run.assert_called_once_with(
        query_type="matter_lookup",
        params={"matter_id": "m1"},
        caller=caller,
    )
    assert result["source_engine"] == "redshift"
    assert result["result_type"] == "matter_lookup"


@pytest.mark.unit
def test_dispatch_search_users_routes_to_users_worker() -> None:
    hub, _redshift, users, _vendors = _hub_with_mocks()
    users.run.return_value = _ok_packet(source="users", query_type="user_lookup")
    caller = _caller()
    result = hub.dispatch(
        tool_name="search_users",
        tool_input={"query_type": "user_lookup", "params": {"user_id": "u1"}},
        caller=caller,
    )
    users.run.assert_called_once_with(
        query_type="user_lookup",
        params={"user_id": "u1"},
        caller=caller,
    )
    assert result["source_engine"] == "users"


@pytest.mark.unit
def test_dispatch_search_vendors_routes_to_vendors_worker() -> None:
    hub, _redshift, _users, vendors = _hub_with_mocks()
    vendors.run.return_value = _ok_packet(source="vendors", query_type="lawyer_search")
    caller = _caller()
    result = hub.dispatch(
        tool_name="search_vendors",
        tool_input={"query_type": "lawyer_search", "params": {"q": "walker"}},
        caller=caller,
    )
    vendors.run.assert_called_once()
    assert result["source_engine"] == "vendors"


@pytest.mark.unit
def test_dispatch_unknown_tool_returns_error_packet_dict() -> None:
    hub, *_ = _hub_with_mocks()
    result = hub.dispatch(
        tool_name="search_aliens",
        tool_input={"query_type": "what", "params": {}},
        caller=_caller(),
    )
    assert result["source_engine"] == "supervisor"
    assert result["error"]["type"] == "UnknownToolError"
    assert "search_aliens" in result["error"]["message"]


@pytest.mark.unit
def test_dispatch_returns_json_serializable_dict_for_tool_result() -> None:
    import json

    hub, redshift, _users, _vendors = _hub_with_mocks()
    redshift.run.return_value = _ok_packet(source="redshift", query_type="matter_lookup")
    result = hub.dispatch(
        tool_name="query_redshift",
        tool_input={"query_type": "matter_lookup", "params": {}},
        caller=_caller(),
    )
    encoded = json.dumps(result)
    assert "matter_lookup" in encoded


@pytest.mark.unit
def test_dispatch_handles_authorization_error_via_error_packet() -> None:
    hub, redshift, _users, _vendors = _hub_with_mocks()
    redshift.run.return_value = _err_packet(
        AuthorizationError("nope"),
        source="redshift",
        query_type="matter_lookup",
    )
    result = hub.dispatch(
        tool_name="query_redshift",
        tool_input={"query_type": "matter_lookup", "params": {}},
        caller=_caller(),
    )
    assert result["error"]["type"] == "AuthorizationError"


@pytest.mark.unit
def test_dispatch_handles_invalid_params_via_error_packet() -> None:
    hub, _redshift, users, _vendors = _hub_with_mocks()
    users.run.return_value = _err_packet(
        InvalidParametersError("missing user_id"),
        source="users",
        query_type="user_lookup",
    )
    result: dict[str, Any] = hub.dispatch(
        tool_name="search_users",
        tool_input={"query_type": "user_lookup", "params": {}},
        caller=_caller(),
    )
    assert result["error"]["type"] == "InvalidParametersError"


@pytest.mark.unit
def test_dispatch_returns_backend_unavailable_when_worker_is_none() -> None:
    """A None worker would otherwise raise AttributeError on .run(...).

    The Lambda's ``_build_workers_default`` and the CLI both produce None
    workers when the underlying backend isn't configured. Hub must turn
    that into a structured packet, not a crash.
    """
    hub = WorkerHub(redshift_worker=None, users_worker=MagicMock(), vendors_worker=MagicMock())
    result = hub.dispatch(
        tool_name="query_redshift",
        tool_input={"query_type": "matter_lookup", "params": {}},
        caller=_caller(),
    )
    assert result["source_engine"] == "supervisor"
    assert result["error"]["type"] == "BackendUnavailableError"
    assert "query_redshift" in result["error"]["message"]


@pytest.mark.unit
def test_dispatch_backend_unavailable_for_each_subsystem() -> None:
    """Confirm the null-check covers all three subsystem entries."""
    cases = [
        ("query_redshift", {"redshift_worker": None}),
        ("search_users", {"users_worker": None}),
        ("search_vendors", {"vendors_worker": None}),
    ]
    for tool_name, override in cases:
        kwargs = {"redshift_worker": MagicMock(), "users_worker": MagicMock(), "vendors_worker": MagicMock()}
        kwargs.update(override)
        hub = WorkerHub(**kwargs)
        result = hub.dispatch(
            tool_name=tool_name,
            tool_input={"query_type": "x", "params": {}},
            caller=_caller(),
        )
        assert result["error"]["type"] == "BackendUnavailableError", tool_name
