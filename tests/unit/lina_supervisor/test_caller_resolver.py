"""Unit tests for CallerResolver."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_supervisor.caller_resolver import (
    CallerResolver,
    UserNotFoundError,
)
from lina_users.packet import ResultPacket as UsersResultPacket


def _ok_packet(profile: dict[str, Any]) -> UsersResultPacket:
    return UsersResultPacket(
        result_type="user_lookup",
        metrics=[profile],
        sql_trace_id="01J0000000000000000000000",
        row_count=1,
        truncated=False,
    )


def _empty_packet() -> UsersResultPacket:
    return UsersResultPacket(
        result_type="user_lookup",
        metrics=[],
        sql_trace_id="01J0000000000000000000000",
        row_count=0,
        truncated=False,
    )


@pytest.mark.unit
def test_bootstrap_caller_used_for_user_lookup() -> None:
    users_worker = MagicMock()
    users_worker.run.return_value = _ok_packet(
        {
            "user_id": "user_jane",
            "roles": ["legal_ops"],
            "permission_tags": ["finance"],
        }
    )
    resolver = CallerResolver(users_worker=users_worker)
    resolver.resolve(user_id="user_jane", request_id="req-1")

    call_kwargs = users_worker.run.call_args.kwargs
    assert call_kwargs["query_type"] == "user_lookup"
    assert call_kwargs["params"] == {"user_id": "user_jane"}
    bootstrap = call_kwargs["caller"]
    assert bootstrap.user_id == "lina_supervisor_bootstrap"
    assert "caller_resolver" in bootstrap.roles


@pytest.mark.unit
def test_resolves_user_via_user_lookup() -> None:
    users_worker = MagicMock()
    users_worker.run.return_value = _ok_packet(
        {
            "user_id": "user_jane",
            "roles": ["legal_ops"],
            "permission_tags": ["finance"],
        }
    )
    resolver = CallerResolver(users_worker=users_worker)
    caller = resolver.resolve(user_id="user_jane", request_id="req-1")
    assert caller.user_id == "user_jane"
    assert caller.request_id == "req-1"


@pytest.mark.unit
def test_builds_caller_context_from_profile() -> None:
    users_worker = MagicMock()
    users_worker.run.return_value = _ok_packet(
        {
            "user_id": "user_jane",
            "roles": ["legal_ops", "finance"],
            "permission_tags": ["all_matters"],
        }
    )
    resolver = CallerResolver(users_worker=users_worker)
    caller = resolver.resolve(user_id="user_jane", request_id="req-1")
    assert caller.roles == frozenset({"legal_ops", "finance"})
    assert caller.permission_tags == frozenset({"all_matters"})


@pytest.mark.unit
def test_raises_on_unknown_user() -> None:
    users_worker = MagicMock()
    users_worker.run.return_value = _empty_packet()
    resolver = CallerResolver(users_worker=users_worker)
    with pytest.raises(UserNotFoundError):
        resolver.resolve(user_id="user_ghost", request_id="req-1")


@pytest.mark.unit
def test_falls_back_to_reader_role_when_role_field_missing() -> None:
    users_worker = MagicMock()
    users_worker.run.return_value = _ok_packet(
        {
            "user_id": "user_jane",
            # no roles key
        }
    )
    resolver = CallerResolver(users_worker=users_worker)
    caller = resolver.resolve(user_id="user_jane", request_id="req-1")
    assert caller.roles == frozenset({"reader"})
    assert caller.permission_tags == frozenset()
